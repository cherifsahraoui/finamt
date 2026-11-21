"""
Server-rendered UI under ``/app`` (decision D2, tasks UI-1 … UI-4, UI-7).

Pages call the library directly. ELSTER sending reuses the existing submit functions in
``ui/api.py`` in-process (not over HTTP), so the live-submission gate (403) stays in one place.
"""

from __future__ import annotations

import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from finamt.agents.prompts import RECEIPT_CATEGORIES
from finamt.tax.bundesland import BUNDESLAENDER, bundesland_by_name, steuernummer_info
from finamt.tax.elster import _ustva_kennzahlen
from finamt.tax.eur import generate_eur
from finamt.tax.safety import LIVE_SUBMISSION_ENV, live_submission_allowed
from finamt.tax.ustva import generate_ustva
from finamt.ui.web import helpers as h
from finamt.ui.web import i18n, uploads

_HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(_HERE / "templates"))
templates.env.filters["eur"] = h.eur
templates.env.filters["datum"] = h.datum
templates.env.filters["zahl"] = h.zahl
templates.env.filters["dezimal"] = lambda s: Decimal(str(s)) if s not in (None, "") else None

router = APIRouter(prefix="/app", include_in_schema=False)

# Short German labels for the UStVA Kennzahlen the code produces (tax-rules.md, USt1A-2026)
KZ_LABELS = {
    "Kz81": "Umsätze 19 % (Bemessungsgrundlage, volle Euro)",
    "Kz86": "Umsätze 7 % (Bemessungsgrundlage, volle Euro)",
    "Kz35": "Umsätze zu anderen Steuersätzen (Bemessungsgrundlage)",
    "Kz36": "Steuer zu anderen Steuersätzen",
    "Kz66": "Vorsteuer aus Rechnungen anderer Unternehmer",
    "Kz62": "Einfuhrumsatzsteuer",
    "Kz87": "Umsätze zum Steuersatz 0 % (§ 12 Abs. 3 UStG)",
    "Kz48": "Steuerfreie Umsätze ohne Vorsteuerabzug",
    "Kz21": "Nicht steuerbare sonstige Leistungen (§ 18b S. 1 Nr. 2 UStG)",
    "Kz45": "Übrige nicht steuerbare Umsätze",
    "Kz60": "Umsätze, für die der Empfänger die Steuer schuldet (§ 13b Abs. 5 UStG)",
    "Kz46": "Leistungen nach § 13b Abs. 1 UStG (Bemessungsgrundlage)",
    "Kz47": "Steuer auf Leistungen nach § 13b Abs. 1 UStG",
    "Kz84": "Andere Leistungen nach § 13b UStG (Bemessungsgrundlage)",
    "Kz85": "Steuer auf andere Leistungen nach § 13b UStG",
    "Kz67": "Vorsteuer aus Leistungen nach § 13b UStG",
    "Kz83": "Verbleibende Vorauszahlung (+) / Überschuss (−)",
}

TYP_LABELS = {"purchase": "Ausgabe", "sale": "Einnahme"}
# ReceiptData.vat_treatment choices (UST-3, UST-4); "" = ordinary receipt
UST_ARTEN = {
    "": "normal (USt laut Beleg)",
    "zero_rate": "0 % (§ 12 Abs. 3 UStG)",
    "tax_free": "steuerfrei",
    "reverse_charge": "Reverse Charge (§ 13b UStG / EU-Leistung)",
}
templates.env.globals["ust_arten"] = UST_ARTEN
BESTEUERUNGSARTEN = (  # codes as used by ui/api.py UStESubmitRequest
    ("1", "Sollversteuerung (vereinbarte Entgelte)"),
    ("2", "Istversteuerung (vereinnahmte Entgelte)"),
    ("3", "teils Soll-, teils Istversteuerung"),
)


def register(app: FastAPI) -> None:
    """Mount static files and the ``/app`` pages. Call before the SPA catch-all route."""
    app.mount("/app/static", StaticFiles(directory=str(_HERE / "static")), name="web-static")
    app.include_router(router)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _i18n_ctx(request: Request) -> dict:
    lang = i18n.lang_from(request)
    return {
        "lang": lang,
        "_": i18n.translator(lang),
        "zlabel": lambda z: i18n.zeitraum_label(z, lang),
        "sprachen": i18n.SPRACHEN,
    }


def _render(request: Request, name: str, layout, nav: str, **ctx) -> HTMLResponse:
    projekt = layout.name

    def href(path: str, **params) -> str:
        q = {"projekt": projekt, **{k: v for k, v in params.items() if v not in (None, "")}}
        return f"/app{path}?{urlencode(q)}"

    return templates.TemplateResponse(
        request,
        name,
        {
            **_i18n_ctx(request),
            "projekt": projekt,
            "projekte": h.project_names(projekt),
            "nav": nav,
            "href": href,
            "live_allowed": live_submission_allowed(),
            "heute": date.today(),
            "upload_job": uploads.current(),
            "pfad": request.url.path + (f"?{request.url.query}" if request.url.query else ""),
            **ctx,
        },
    )


def _redirect(path: str, projekt: str, **params) -> RedirectResponse:
    q = {"projekt": projekt, **{k: v for k, v in params.items() if v not in (None, "")}}
    return RedirectResponse(f"/app{path}?{urlencode(q)}", status_code=303)


def _settings(layout) -> dict:
    s = h.get_meta(layout, h.SETTINGS_KEY)
    jahre = sorted(int(j) for j in s.get("kleinunternehmer_jahre") or [] if str(j).isdigit())
    return {
        "monatlich": bool(s.get("monatlich")),
        "dauerfrist": bool(s.get("dauerfrist")),
        "kleinunternehmer_jahre": jahre,
    }


def _kleinunternehmer(layout, jahr: int) -> bool:
    """EUR-8 / decision D7: is ``jahr`` a Kleinunternehmer year (§ 19 UStG) in the settings?"""
    return jahr in _settings(layout)["kleinunternehmer_jahre"]


def _merge_settings(layout, **werte) -> None:
    with h.open_repo(layout, create=True) as repo:
        s = repo.get_metadata(h.SETTINGS_KEY) or {}
        s.update(werte)
        repo.set_metadata(h.SETTINGS_KEY, s)


def _receipts(layout, start: date | None = None, end: date | None = None) -> list:
    with h.open_repo(layout) as repo:
        if repo is None:
            return []
        if start and end:
            return list(repo.find_by_period(start, end))
        return list(repo.list_all())


def _assets(layout) -> list:
    """The project's asset register (EUR-3b): AfA for the EÜR and the Anlage AVEÜR."""
    with h.open_repo(layout) as repo:
        return [] if repo is None else repo.list_assets()


def _sort(receipts: list) -> list:
    return sorted(receipts, key=lambda r: r.receipt_date or datetime.min, reverse=True)


# ---------------------------------------------------------------------------
# Übersicht
# ---------------------------------------------------------------------------


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def uebersicht(request: Request, projekt: str | None = None):
    layout = h.resolve(projekt)
    settings = _settings(layout)
    heute = date.today()
    z, frist = h.naechste_ustva(heute, settings["monatlich"], settings["dauerfrist"])
    period_receipts = _receipts(layout, z.start, z.end)
    report = generate_ustva(period_receipts, z.start, z.end)
    submitted = [
        s
        for s in h.get_meta(layout, "submissions") or []
        if isinstance(s, dict) and s.get("type") == z.submission_type and s.get("year") == z.jahr
    ]

    jahr_receipts = _receipts(layout, date(heute.year, 1, 1), date(heute.year, 12, 31))
    eur = generate_eur(
        jahr_receipts,
        heute.year,
        kleinunternehmer=_kleinunternehmer(layout, heute.year),
        assets=_assets(layout),
    )
    mit_warnung = [r for r in jahr_receipts if r.validation_warnings]

    stamm = h.get_meta(layout, h.TAXPAYER_KEY)
    info = steuernummer_info(stamm.get("tax_number"), bundesland_by_name(stamm.get("state")))
    return _render(
        request,
        "uebersicht.html",
        layout,
        "uebersicht",
        z=z,
        frist=frist,
        tage=(frist - heute).days,
        report=report,
        submitted=submitted,
        settings=settings,
        jahr=heute.year,
        anzahl=len(jahr_receipts),
        mit_warnung=len(mit_warnung),
        review=sum(ln.count for ln in eur.review_lines.values()),
        eur=eur,
        stammdaten_fehler=info.fehler,
    )


# ---------------------------------------------------------------------------
# Belege (UI-1 list, UI-2 upload / edit / delete)
# ---------------------------------------------------------------------------


@router.get("/belege", response_class=HTMLResponse)
def belege(
    request: Request,
    projekt: str | None = None,
    jahr: int | None = Query(default=None, ge=2000, le=2100),
    zeitraum: str | None = None,
    typ: str | None = None,
    kategorie: str | None = None,
    pruefen: str | None = None,
    meldung: str | None = None,
    fehler: str | None = None,
):
    layout = h.resolve(projekt)
    jahr = jahr or date.today().year
    z = h.zeitraum(jahr, zeitraum) if zeitraum else h.zeitraum(jahr, "jahr")
    rows = []
    for r in _sort(_receipts(layout, z.start, z.end)):
        if typ in TYP_LABELS and str(r.receipt_type) != typ:
            continue
        if kategorie and str(r.category) != kategorie:
            continue
        zeile = h.eur_zeile(r)
        if pruefen and not (r.validation_warnings or (zeile and zeile.zu_pruefen)):
            continue
        rows.append((r, zeile))
    return _render(
        request,
        "belege.html",
        layout,
        "belege",
        rows=rows,
        jahr=jahr,
        zeitraum=zeitraum or "",
        typ=typ or "",
        kategorie=kategorie or "",
        pruefen=bool(pruefen),
        kategorien=RECEIPT_CATEGORIES,
        typen=TYP_LABELS,
        meldung=meldung,
        fehler=fehler,
        summe_netto=sum((r.net_amount or Decimal("0") for r, _ in rows), Decimal("0")),
        summe_ust=sum((r.vat_amount or Decimal("0") for r, _ in rows), Decimal("0")),
    )


@router.post("/belege/upload", response_class=HTMLResponse)
def belege_upload(
    request: Request,
    projekt: str | None = Query(default=None),
    typ: str = Form("purchase"),
    dateien: list[UploadFile] = File(...),
):
    """
    Store the files and read them in a background job (same agent pipeline as
    POST /receipts/upload). Only one job runs at a time; while it runs this refuses.
    """
    from finamt.ui import api as _api  # lazy: api.py imports this module

    layout = h.resolve(projekt)
    if uploads.busy():
        return _redirect("/belege/upload", layout.name, besetzt="1")
    receipt_type = typ if typ in TYP_LABELS else "purchase"
    items: list[uploads.UploadItem] = []
    for upload in dateien:
        name = upload.filename or "Beleg"
        if upload.content_type not in _api.ALLOWED_MIME_TYPES:
            items.append(
                uploads.UploadItem(
                    name=name,
                    path=None,
                    status=uploads.FERTIG,
                    fehler="Dateityp {typ} nicht erlaubt.",
                    fehler_args={"typ": upload.content_type},
                )
            )
            continue
        suffix = Path(name).suffix or ".pdf"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(upload.file.read())
            items.append(uploads.UploadItem(name=name, path=Path(tmp.name)))

    def process(path: Path, rtype: str) -> tuple[str | None, str, dict]:
        layout.create_dirs()
        agent = _api.FinanceAgent(
            db_path=layout.db_path,
            config=_api._effective_ocr_cfg(),
            agents_cfg=_api._effective_agents_cfg(),
        )
        result = agent.process_receipt(path, receipt_type=rtype)
        if not result.success:
            return None, "Auslesen fehlgeschlagen: {msg}", {"msg": result.error_message}
        if result.duplicate:
            return result.existing_id, "Schon vorhanden (gleicher Inhalt).", {}
        return result.data.id, "", {}

    if uploads.start(layout.name, receipt_type, items, process) is None:
        # Another request started a job in the meantime: drop our temp files.
        for item in items:
            if item.path is not None:
                item.path.unlink(missing_ok=True)
        return _redirect("/belege/upload", layout.name, besetzt="1")
    return _redirect("/belege/upload", layout.name)


@router.get("/belege/upload", response_class=HTMLResponse)
def belege_upload_seite(request: Request, projekt: str | None = None, besetzt: str | None = None):
    """Progress and results of the current (or last) upload job."""
    layout = h.resolve(projekt)
    return _render(
        request, "upload.html", layout, "belege", besetzt=bool(besetzt), ohne_upload_status=True
    )


@router.get("/belege/upload/status", response_class=HTMLResponse)
def belege_upload_status(request: Request, projekt: str | None = None, details: str | None = None):
    """The progress box alone, polled by htmx from every page."""
    layout = h.resolve(projekt)
    ctx = {"details": bool(details)}
    current_url = request.headers.get("HX-Current-URL")
    if current_url:  # the page the box sits on, so "Ausblenden" returns there
        parts = urlsplit(current_url)
        ctx["pfad"] = parts.path + (f"?{parts.query}" if parts.query else "")
    return _render(request, "_upload_status.html", layout, "belege", **ctx)


@router.post("/belege/upload/ausblenden")
def belege_upload_ausblenden(
    projekt: str | None = Query(default=None), job: str = Form(""), zurueck: str = Form("")
):
    layout = h.resolve(projekt)
    uploads.dismiss(job)
    if zurueck.startswith("/app") and "//" not in zurueck:
        return RedirectResponse(zurueck, status_code=303)
    return _redirect("/belege", layout.name)


def _beleg_or_404(layout, receipt_id: str):
    with h.open_repo(layout) as repo:
        r = repo.get(receipt_id) if repo else None
    if r is None:
        raise HTTPException(status_code=404, detail="Beleg nicht gefunden.")
    return r


@router.post("/belege/neu")
def beleg_neu(
    projekt: str | None = Query(default=None),
    receipt_type: str = Form("purchase"),
    receipt_date: str = Form(""),
    receipt_number: str = Form(""),
    counterparty_name: str = Form(""),
    category: str = Form("other"),
    subcategory: str = Form(""),
    total_amount: str = Form(""),
    vat_percentage: str = Form(""),
    vat_amount: str = Form(""),
    einfuhr_vat: str = Form(""),
    vat_treatment: str = Form(""),
    private_use_percent: str = Form(""),
    description: str = Form(""),
):
    """UI-8 (1): a receipt entered by hand, without a file (old UI: POST /receipts)."""
    import uuid

    from finamt.models import Counterparty, ReceiptCategory, ReceiptData, ReceiptType

    layout = h.resolve(projekt)
    try:
        brutto = h.parse_betrag(total_amount)
        satz = h.parse_betrag(vat_percentage)
        ust = h.parse_betrag(vat_amount)
        privat = h.parse_betrag(private_use_percent)
        if brutto is None:
            raise ValueError("Bruttobetrag fehlt.")
        if not counterparty_name.strip():
            raise ValueError("Partner fehlt.")
        datum = date.fromisoformat(receipt_date) if receipt_date else None
        if datum is None:
            raise ValueError("Datum fehlt.")
        if ust is None and satz is not None:
            # VAT contained in the gross amount: brutto − brutto / (1 + satz/100)
            ust = (brutto - brutto / (Decimal("1") + satz / Decimal("100"))).quantize(
                Decimal("0.01")
            )
    except ValueError as exc:
        return _redirect("/belege", layout.name, fehler=str(exc))

    rtype = receipt_type if receipt_type in TYP_LABELS else "purchase"
    r = ReceiptData(
        # unique text, so the content hash (receipt id) never collides
        raw_text=f"MANUAL:{rtype}:{datum}:{brutto}:{counterparty_name.strip()}:{uuid.uuid4().hex}",
        receipt_type=ReceiptType(rtype),
        counterparty=Counterparty(name=counterparty_name.strip()),
        receipt_date=datetime(datum.year, datum.month, datum.day),
        total_amount=brutto,
        vat_percentage=satz,
        vat_amount=ust,
        category=ReceiptCategory(category if category in RECEIPT_CATEGORIES else "other"),
        subcategory=subcategory.strip() or None,
        receipt_number=receipt_number.strip() or None,
        description=description.strip(),
        private_use_share=(privat or Decimal("0")) / Decimal("100"),
        vat_treatment=vat_treatment if vat_treatment in UST_ARTEN and vat_treatment else None,
    )
    if einfuhr_vat.strip():
        r.einfuhr_vat = h.parse_betrag(einfuhr_vat)
    r.validate()
    layout.create_dirs()
    with h.open_repo(layout, create=True) as repo:
        repo.save(r)
    return _redirect(f"/belege/{r.id}", layout.name, gespeichert="1")


def _original_url(layout, receipt_id: str) -> str | None:
    """URL of the stored original file, or None (e.g. for a manually entered receipt)."""
    from finamt.ui import api as _api  # lazy: api.py imports this module

    if not _api._find_stored_file(receipt_id, layout.db_path):
        return None
    return f"/receipts/{receipt_id}/pdf?{urlencode({'db': str(layout.db_path)})}"


@router.get("/belege/{receipt_id}", response_class=HTMLResponse)
def beleg(request: Request, receipt_id: str, projekt: str | None = None, gespeichert: str = ""):
    layout = h.resolve(projekt)
    r = _beleg_or_404(layout, receipt_id)
    return _render(
        request,
        "beleg.html",
        layout,
        "belege",
        r=r,
        zeile=h.eur_zeile(r),
        kategorien=RECEIPT_CATEGORIES,
        typen=TYP_LABELS,
        gespeichert=bool(gespeichert),
        fehler=None,
        pdf_url=_original_url(layout, receipt_id),
    )


@router.post("/belege/{receipt_id}", response_class=HTMLResponse)
def beleg_speichern(
    request: Request,
    receipt_id: str,
    projekt: str | None = Query(default=None),
    receipt_type: str = Form(...),
    receipt_date: str = Form(""),
    receipt_number: str = Form(""),
    counterparty_name: str = Form(""),
    category: str = Form("other"),
    subcategory: str = Form(""),
    total_amount: str = Form(""),
    vat_percentage: str = Form(""),
    vat_amount: str = Form(""),
    einfuhr_vat: str = Form(""),
    vat_treatment: str = Form(""),
    private_use_percent: str = Form(""),
    description: str = Form(""),
):
    layout = h.resolve(projekt)
    r = _beleg_or_404(layout, receipt_id)
    try:
        privat = h.parse_betrag(private_use_percent)
        fields = {
            "receipt_type": receipt_type if receipt_type in TYP_LABELS else str(r.receipt_type),
            "receipt_number": receipt_number.strip() or None,
            "counterparty_name": counterparty_name.strip(),
            "category": category if category in RECEIPT_CATEGORIES else "other",
            "subcategory": subcategory.strip() or None,
            "total_amount": h.parse_betrag(total_amount),
            "vat_percentage": h.parse_betrag(vat_percentage),
            "vat_amount": h.parse_betrag(vat_amount),
            "einfuhr_vat": h.parse_betrag(einfuhr_vat),
            "vat_treatment": vat_treatment if vat_treatment in UST_ARTEN else "",
            "private_use_share": (privat or Decimal("0")) / Decimal("100"),
            "description": description.strip(),
        }
        if receipt_date:
            # a plain date: the repository stores date.isoformat() and reads it back as such
            fields["receipt_date"] = date.fromisoformat(receipt_date)
    except ValueError as exc:
        return _render(
            request,
            "beleg.html",
            layout,
            "belege",
            r=r,
            zeile=h.eur_zeile(r),
            kategorien=RECEIPT_CATEGORIES,
            typen=TYP_LABELS,
            gespeichert=False,
            fehler=str(exc),
            pdf_url=_original_url(layout, receipt_id),
        )
    with h.open_repo(layout) as repo:
        repo.update(receipt_id, fields)
        updated = repo.get(receipt_id)
        updated.validate()  # refresh the warnings for the corrected values
        repo.update(receipt_id, {"validation_warnings": updated.validation_warnings})
    return _redirect(f"/belege/{receipt_id}", layout.name, gespeichert="1")


@router.post("/belege/{receipt_id}/loeschen")
def beleg_loeschen(receipt_id: str, projekt: str | None = Query(default=None)):
    layout = h.resolve(projekt)
    with h.open_repo(layout) as repo:
        if repo is None or not repo.delete(receipt_id):
            raise HTTPException(status_code=404, detail="Beleg nicht gefunden.")
    return _redirect("/belege", layout.name, meldung="Beleg gelöscht.")


# ---------------------------------------------------------------------------
# UStVA and annual USt (UI-3)
# ---------------------------------------------------------------------------


def _ustva_context(layout, z) -> dict:
    report = generate_ustva(_receipts(layout, z.start, z.end), z.start, z.end)
    kz = _ustva_kennzahlen(report) if not z.is_jahr else {}
    subs = [s for s in h.get_meta(layout, "submissions") or [] if isinstance(s, dict)]
    subs.sort(key=lambda s: s.get("submitted_at") or "", reverse=True)
    settings = _settings(layout)
    return {
        "z": z,
        "report": report,
        "kz": kz,
        "kz_labels": KZ_LABELS,
        "frist": None if z.is_jahr else h.ustva_frist(z, settings["dauerfrist"]),
        "keys": h.zeitraum_keys(settings["monatlich"]),
        "submissions": subs,
        "besteuerungsarten": BESTEUERUNGSARTEN,
        "live_env": LIVE_SUBMISSION_ENV,
    }


@router.get("/ustva", response_class=HTMLResponse)
def ustva(
    request: Request,
    projekt: str | None = None,
    jahr: int | None = Query(default=None, ge=2000, le=2100),
    zeitraum: str | None = None,
):
    layout = h.resolve(projekt)
    if not jahr or not h.zeitraum(jahr, zeitraum):
        settings = _settings(layout)
        z, _ = h.naechste_ustva(date.today(), settings["monatlich"], settings["dauerfrist"])
    else:
        z = h.zeitraum(jahr, zeitraum)
    return _render(
        request, "ustva.html", layout, "ustva", ergebnis=None, **_ustva_context(layout, z)
    )


def _elster_request_fields(layout) -> tuple[dict, str | None]:
    """Fields shared by both submit requests, from the Stammdaten. Returns (fields, error)."""
    tp = h.get_meta(layout, h.TAXPAYER_KEY)
    misc = h.get_meta(layout, h.ELSTER_MISC_KEY)
    land = bundesland_by_name(tp.get("state"))
    info = h.steuernummer_fuer(tp, "ust")  # UStVA and USt use the Umsatzsteuer number
    if info.fehler:
        return {}, f"Stammdaten unvollständig: {info.fehler}"
    return {
        "steuernummer": info.elster13,
        "finanzamt_nr": info.finanzamt_nr,
        "bundesland_kz": land.kz,
        "hersteller_id": misc.get("hersteller_id") or "",
        "cert_password": misc.get("cert_pin") or None,
        "company_name": tp.get("name") or "",
        "street": tp.get("street") or "",
        "postal_code": tp.get("postcode") or "",
        "city": tp.get("city") or "",
    }, None


@router.post("/ustva", response_class=HTMLResponse)
def ustva_senden(
    request: Request,
    projekt: str | None = Query(default=None),
    jahr: int = Form(...),
    zeitraum: str = Form(...),
    aktion: str = Form(...),
    berichtigung: str = Form(""),
    besteuerungsart: str = Form("1"),
    vorauszahlungssoll: str = Form(""),
    pdf_kopie: str = Form(""),
):
    """
    aktion: ``pruefen`` (ERiC validation only), ``test`` (Testmerker), ``live``, or ``xml``
    (download the XML without sending; built with the Testmerker, like the old UI).
    """
    from finamt.ui import api as _api  # lazy: api.py imports this module

    layout = h.resolve(projekt)
    z = h.zeitraum(jahr, zeitraum)
    if z is None or aktion not in ("pruefen", "test", "live", "xml", "vorschau"):
        raise HTTPException(status_code=400, detail="Ungültiger Zeitraum oder Aktion.")

    fields, fehler = _elster_request_fields(layout)
    ergebnis: dict
    if fehler:
        ergebnis = {"success": False, "message": fehler}
    else:
        common = {
            **fields,
            "year": jahr,
            "use_test": aktion != "live",
            "validate_only": aktion in ("pruefen", "vorschau"),
            # PRINT-1: preview, or the official copy stored in the archive after a send
            "pdf": aktion == "vorschau" or (aktion in ("test", "live") and pdf_kopie == "1"),
        }
        xml_name = f"{'USt' if z.is_jahr else 'UStVA'}_{jahr}_{z.key}.xml"
        try:
            if z.is_jahr:
                vz = h.parse_betrag(vorauszahlungssoll) or Decimal("0")
                body = _api.UStESubmitRequest(
                    **common,
                    besteuerungsart=besteuerungsart if besteuerungsart in ("1", "2", "3") else "1",
                    # the existing API model takes a float; it converts back to Decimal
                    vorauszahlungssoll=float(vz),
                )
                if aktion == "xml":
                    return _xml_download(_api.post_uste_xml(body, db=str(layout.db_path)), xml_name)
                res = _api.post_uste_submit(body, db=str(layout.db_path))
                if aktion == "vorschau":
                    return _pdf_vorschau(res, f"USt_{jahr}_Vorschau.pdf") or _vorschau_fehler(
                        request, layout, z, res
                    )
            else:
                body = _api.UStVASubmitRequest(
                    **common,
                    quarter=z.quarter,
                    month=z.month,
                    is_berichtigung=bool(berichtigung),
                )
                if aktion == "xml":
                    return _xml_download(
                        _api.post_ustva_xml(body, db=str(layout.db_path)), xml_name
                    )
                res = _api.post_ustva_submit(body, db=str(layout.db_path))
                if aktion == "vorschau":
                    return _pdf_vorschau(
                        res, f"UStVA_{jahr}_{z.key}_Vorschau.pdf"
                    ) or _vorschau_fehler(request, layout, z, res)
            ergebnis = {
                "success": bool(res.get("success")),
                "message": res.get("message") or res.get("error_message") or "",
                "telenummer": res.get("telenummer"),
                "error_code": res.get("error_code"),
                "aktion": aktion,
                "pdf_filename": res.get("pdf_filename"),
            }
        except HTTPException as exc:
            ergebnis = {"success": False, "message": str(exc.detail), "status": exc.status_code}
        except ValueError as exc:
            ergebnis = {"success": False, "message": str(exc)}
        except Exception as exc:  # noqa: BLE001 — e.g. signing without a certificate
            ergebnis = {"success": False, "message": str(exc)}
    return _render(
        request, "ustva.html", layout, "ustva", ergebnis=ergebnis, **_ustva_context(layout, z)
    )


def _pdf_vorschau(res: dict, filename: str) -> Response | None:
    """The preview PDF ERiC wrote to a temp file (PRINT-1), served inline and then deleted."""
    pfad = res.get("pdf_path")
    if not (res.get("success") and pfad and Path(pfad).exists()):
        return None
    data = Path(pfad).read_bytes()
    Path(pfad).unlink(missing_ok=True)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


def _vorschau_fehler(request: Request, layout, z, res: dict) -> HTMLResponse:
    meldung = res.get("message") if not res.get("success") else ""
    return _render(
        request,
        "ustva.html",
        layout,
        "ustva",
        ergebnis={
            "success": False,
            "message": meldung or "ERiC hat keine Druckansicht erstellt.",
            "error_code": res.get("error_code"),
            "aktion": "vorschau",
        },
        **_ustva_context(layout, z),
    )


def _xml_download(resp: Response, filename: str) -> Response:
    """The old API's XML response, as a file download."""
    return Response(
        content=resp.body,
        media_type="text/xml; charset=UTF-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# EÜR (UI-4)
# ---------------------------------------------------------------------------


@router.get("/euer", response_class=HTMLResponse)
def euer(request: Request, projekt: str | None = None, jahr: int | None = None):
    layout = h.resolve(projekt)
    jahr = jahr if jahr and 2000 <= jahr <= 2100 else date.today().year - 1
    return _render(request, "euer.html", layout, "euer", **_euer_context(layout, jahr))


def _euer_context(layout, jahr: int, elster: dict | None = None, ergebnis: dict | None = None):
    from finamt.tax.eur import FORM_YEAR

    receipts = _receipts(layout, date(jahr, 1, 1), date(jahr, 12, 31))
    report = generate_eur(
        receipts, jahr, kleinunternehmer=_kleinunternehmer(layout, jahr), assets=_assets(layout)
    )
    zu_pruefen = []
    for r in _sort(receipts):
        zeile = h.eur_zeile(r)
        if zeile and zeile.zu_pruefen:
            zu_pruefen.append((r, zeile))
    s = h.get_meta(layout, h.SETTINGS_KEY)
    return {
        "report": report,
        "jahr": jahr,
        "zu_pruefen": zu_pruefen,
        "stnr": h.steuernummer_fuer(h.get_meta(layout, h.TAXPAYER_KEY), "euer"),
        "form_year": FORM_YEAR,
        "elster": elster
        or {
            "art_des_betriebs": s.get("euer_art_des_betriebs") or "",
            "grundstuecke": "",
            "entnahmen": "",
            "einlagen": "",
        },
        "ergebnis": ergebnis,
    }


@router.post("/euer", response_class=HTMLResponse)
def euer_elster(
    request: Request,
    projekt: str | None = Query(default=None),
    jahr: int = Form(...),
    aktion: str = Form(...),
    art_des_betriebs: str = Form(""),
    grundstuecke: str = Form(""),
    entnahmen: str = Form(""),
    einlagen: str = Form(""),
):
    """
    EUR-9: Anlage EÜR to ELSTER. ``aktion``: ``pruefen`` (ERiC, nothing sent), ``xml``
    (download, Testmerker), ``test`` (test send). Live sending is disabled for the EÜR (D3).
    """
    from finamt.tax import eur_elster

    layout = h.resolve(projekt)
    if aktion not in ("pruefen", "xml", "test", "vorschau") or not 2000 <= jahr <= 2100:
        raise HTTPException(status_code=400, detail="Ungültige Aktion oder ungültiges Jahr.")
    elster = {
        "art_des_betriebs": art_des_betriebs.strip(),
        "grundstuecke": grundstuecke,
        "entnahmen": entnahmen,
        "einlagen": einlagen,
    }
    if art_des_betriebs.strip():
        _merge_settings(layout, euer_art_des_betriebs=art_des_betriebs.strip())

    def fertig(ergebnis: dict) -> HTMLResponse:
        ergebnis["aktion"] = aktion
        return _render(
            request,
            "euer.html",
            layout,
            "euer",
            **_euer_context(layout, jahr, elster=elster, ergebnis=ergebnis),
        )

    tp = h.get_meta(layout, h.TAXPAYER_KEY)
    grund = {"ja": True, "nein": False}.get(grundstuecke)
    taxpayer, fehler = h.eur_taxpayer(tp, art_des_betriebs, grund)
    if fehler:
        return fertig({"success": False, "message": fehler})
    hersteller_id = (h.get_meta(layout, h.ELSTER_MISC_KEY).get("hersteller_id") or "").strip()
    try:
        ent = h.parse_betrag(entnahmen) or Decimal("0")
        ein = h.parse_betrag(einlagen) or Decimal("0")
        report = _euer_context(layout, jahr)["report"]
        xml = eur_elster.build_xml(
            report,
            taxpayer,
            entnahmen=ent,
            einlagen=ein,
            hersteller_id=hersteller_id,
            assets=_assets(layout),
        )
    except (ValueError, NotImplementedError) as exc:
        return fertig({"success": False, "message": str(exc), "nicht_erstellt": True})

    if aktion == "xml":
        return Response(
            content=xml,
            media_type="text/xml; charset=UTF-8",
            headers={"Content-Disposition": f'attachment; filename="EUER_{jahr}.xml"'},
        )
    eric = h.eric_library_path(layout)
    if aktion == "vorschau":
        import tempfile
        import uuid

        pfad = Path(tempfile.gettempdir()) / f"freibuch_vorschau_{uuid.uuid4().hex}.pdf"
        res = eur_elster.eric_validate(xml, eric_home=eric or None, pdf_path=str(pfad))
        pdf = _pdf_vorschau(
            {"success": res.success, "pdf_path": str(pfad)}, f"EUER_{jahr}_Vorschau.pdf"
        )
        if pdf is not None:
            return pdf
        return fertig(
            {
                "success": False,
                "message": res.error_message or "ERiC hat keine Druckansicht erstellt.",
                "error_code": res.error_code,
            }
        )
    if aktion == "pruefen":
        res = eur_elster.eric_validate(xml, eric_home=eric or None)
    else:
        land = bundesland_by_name(tp.get("state"))
        cfg = h.elster_cert_config(
            layout, taxpayer.steuernummer, taxpayer.steuernummer[:4], land.kz if land else ""
        )
        if cfg is None:
            return fertig(
                {"success": False, "message": "Zertifikat und PIN fehlen in den Stammdaten."}
            )
        res = eur_elster.submit(xml, mode="test", config=cfg, eric_home=eric or None)
    return fertig(
        {
            "success": res.success,
            "message": res.error_message or "",
            "error_code": res.error_code,
            "telenummer": res.telenummer,
        }
    )


@router.get("/euer/{jahr}.json")
def euer_json(jahr: int, projekt: str | None = None):
    layout = h.resolve(projekt)
    receipts = _receipts(layout, date(jahr, 1, 1), date(jahr, 12, 31))
    body = generate_eur(
        receipts, jahr, kleinunternehmer=_kleinunternehmer(layout, jahr), assets=_assets(layout)
    ).to_json()
    return Response(
        body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="euer_{jahr}.json"'},
    )


# ---------------------------------------------------------------------------
# Projekte (UI-8 item 2): reuse the old API's create / delete logic in-process
# ---------------------------------------------------------------------------


@router.get("/projekte", response_class=HTMLResponse)
def projekte(
    request: Request,
    projekt: str | None = None,
    meldung: str | None = None,
    fehler: str | None = None,
):
    layout = h.resolve(projekt)
    belege: dict[str, int] = {}
    for name in h.project_names(layout.name):
        with h.open_repo(h.resolve(name)) as repo:
            belege[name] = sum(1 for _ in repo.list_all()) if repo is not None else 0
    return _render(
        request,
        "projekte.html",
        layout,
        "projekte",
        meldung=meldung,
        fehler=fehler,
        projekt_belege=belege,
        reste=h.leftover_folders(),
    )


@router.post("/projekte")
def projekt_anlegen(projekt: str | None = Query(default=None), name: str = Form("")):
    from finamt.ui import api as _api  # lazy: api.py imports this module

    layout = h.resolve(projekt)
    try:
        neu = _api.create_project({"name": name})
    except HTTPException as exc:
        return _redirect("/projekte", layout.name, fehler=str(exc.detail))
    return _redirect("/projekte", neu["name"], meldung="Projekt angelegt.")


@router.post("/projekte/{name}/loeschen")
def projekt_loeschen(name: str, projekt: str | None = Query(default=None)):
    """Deletes the project's database; PDFs are kept, as in the old UI (keep_pdfs=True)."""
    from finamt.ui import api as _api  # lazy: api.py imports this module

    layout = h.resolve(projekt)
    if name == "default":
        return _redirect(
            "/projekte", layout.name, fehler="Das Standardprojekt kann nicht gelöscht werden."
        )
    ziel = "default" if layout.name == name else layout.name
    alt = h.resolve(name)
    if alt.name == name and not alt.db_path.exists() and alt.root.is_dir():
        # Only a folder is left (database already deleted, PDFs kept): remove empty dirs.
        rest = h.remove_empty_project_folder(alt)
        if rest:
            return _redirect(
                "/projekte",
                ziel,
                fehler=f"Ordner „{name}“ enthält noch {rest} Datei(en) und wurde nicht gelöscht: "
                f"{alt.root}",
            )
        return _redirect("/projekte", ziel, meldung="Leerer Projektordner entfernt.")
    try:
        _api.delete_project(name, keep_pdfs=True)
    except HTTPException as exc:
        return _redirect("/projekte", layout.name, fehler=str(exc.detail))
    rest = h.remove_empty_project_folder(alt)  # PDFs kept: drop the folder if nothing is in it
    if rest:
        return _redirect(
            "/projekte",
            ziel,
            meldung=f"Projekt gelöscht. Die Original-Dateien liegen weiter in {alt.root}.",
        )
    return _redirect("/projekte", ziel, meldung="Projekt gelöscht.")


# ---------------------------------------------------------------------------
# Partner (UI-8 item 3)
# ---------------------------------------------------------------------------


@router.get("/partner", response_class=HTMLResponse)
def partner(request: Request, projekt: str | None = None, meldung: str | None = None):
    layout = h.resolve(projekt)
    rows: list[dict] = []
    anzahl: dict[str, int] = {}
    with h.open_repo(layout) as repo:
        if repo is not None:
            rows = repo.list_all_counterparties()
            for r in repo.list_all():
                cp = r.counterparty.id if r.counterparty else None
                if cp:
                    anzahl[cp] = anzahl.get(cp, 0) + 1
    return _render(
        request, "partner.html", layout, "partner", rows=rows, anzahl=anzahl, meldung=meldung
    )


@router.post("/partner/{cp_id}")
def partner_speichern(
    cp_id: str,
    projekt: str | None = Query(default=None),
    name: str = Form(""),
    vat_id: str = Form(""),
    verified: str = Form(""),
):
    """Rename / set the VAT ID / mark verified (old UI: PATCH /counterparties/{id})."""
    layout = h.resolve(projekt)
    with h.open_repo(layout) as repo:
        if repo is None or not repo.update_counterparty(
            cp_id,
            {
                "name": name.strip() or None,
                "vat_id": vat_id.strip().upper().replace(" ", "") or None,
                "verified": verified == "1",
            },
        ):
            raise HTTPException(status_code=404, detail="Partner nicht gefunden.")
    return _redirect("/partner", layout.name, meldung="Partner gespeichert.")


@router.post("/partner/{cp_id}/zusammenfuehren")
def partner_zusammenfuehren(
    cp_id: str, projekt: str | None = Query(default=None), ziel: str = Form("")
):
    """Move every receipt of ``cp_id`` to partner ``ziel``, then delete ``cp_id``."""
    layout = h.resolve(projekt)
    if not ziel or ziel == cp_id:
        return _redirect("/partner", layout.name)
    with h.open_repo(layout) as repo:
        if repo is None:
            raise HTTPException(status_code=404, detail="Partner nicht gefunden.")
        rows = {r["id"]: r for r in repo.list_all_counterparties()}
        if cp_id not in rows or ziel not in rows:
            raise HTTPException(status_code=404, detail="Partner nicht gefunden.")
        z = rows[ziel]
        felder = {k: z.get(k) for k in ("name", "vat_id", "tax_number")}
        for r in list(repo.list_all()):
            if r.counterparty and r.counterparty.id == cp_id:
                repo.relink_counterparty(r.id, felder)
        repo.delete_counterparty(cp_id)
    return _redirect("/partner", layout.name, meldung="Partner zusammengeführt.")


# ---------------------------------------------------------------------------
# Archiv (UI-8 item 5): submitted returns and their documents
# ---------------------------------------------------------------------------


@router.get("/archiv", response_class=HTMLResponse)
def archiv(request: Request, projekt: str | None = None, fehler: str | None = None):
    layout = h.resolve(projekt)
    subs = [s for s in h.get_meta(layout, "submissions") or [] if isinstance(s, dict)]
    subs.sort(key=lambda s: s.get("submitted_at") or "", reverse=True)
    ordner = layout.submitted_returns_dir
    dateien = sorted(f.name for f in ordner.iterdir() if f.is_file()) if ordner.exists() else []
    return _render(
        request, "archiv.html", layout, "archiv", submissions=subs, dateien=dateien, fehler=fehler
    )


@router.get("/archiv/datei")
def archiv_datei(projekt: str | None = None, name: str = ""):
    """A file from submitted_returns/ (old API: GET /submissions/file, same path check)."""
    from finamt.ui import api as _api  # lazy: api.py imports this module

    layout = h.resolve(projekt)
    return _api.get_submission_file(filename=name, db=str(layout.db_path))


@router.post("/archiv/dokument")
async def archiv_dokument(
    projekt: str | None = Query(default=None),
    typ: str = Form(...),
    jahr: int = Form(...),
    art: str = Form(...),
    datei: UploadFile = File(...),
):
    """Attach the own copy (``art=copy``) or the Bescheid (``art=final``) to a submission."""
    from finamt.ui import api as _api  # lazy: api.py imports this module

    layout = h.resolve(projekt)
    try:
        await _api.upload_submission_document(
            file=datei, type=typ, year=jahr, kind=art, db=str(layout.db_path)
        )
    except HTTPException as exc:
        return _redirect("/archiv", layout.name, fehler=str(exc.detail))
    return _redirect("/archiv", layout.name)


@router.post("/archiv/dokument/loeschen")
def archiv_dokument_loeschen(
    projekt: str | None = Query(default=None),
    typ: str = Form(...),
    jahr: int = Form(...),
    art: str = Form(...),
):
    from finamt.ui import api as _api  # lazy: api.py imports this module

    layout = h.resolve(projekt)
    try:
        _api.delete_submission_document(type=typ, year=jahr, kind=art, db=str(layout.db_path))
    except HTTPException as exc:
        return _redirect("/archiv", layout.name, fehler=str(exc.detail))
    return _redirect("/archiv", layout.name)


# ---------------------------------------------------------------------------
# Language toggle
# ---------------------------------------------------------------------------


@router.get("/sprache")
def sprache(lang: str = "de", zurueck: str = "/app"):
    """Set the UI language cookie and go back to the page the toggle was clicked on."""
    ziel = zurueck if zurueck.startswith("/app") and "//" not in zurueck else "/app"
    resp = RedirectResponse(ziel, status_code=303)
    code = lang if lang in i18n.CODES else i18n.DEFAULT
    resp.set_cookie(i18n.COOKIE, code, max_age=365 * 24 * 3600, samesite="lax", httponly=True)
    return resp


# ---------------------------------------------------------------------------
# Rechnungen (UI-5, built on INV-1)
# ---------------------------------------------------------------------------

_RECHNUNG_SAETZE = ("19", "7", "0")


def _rechnungen_render(request: Request, layout, jahr: int, **ctx) -> HTMLResponse:
    from finamt.invoicing import KLEINUNTERNEHMER_HINWEIS

    with h.open_repo(layout) as repo:
        rows = repo.list_invoices(jahr) if repo is not None else []
        storniert = {r["corrects"] for r in rows if r.get("corrects")}
    tp = h.get_meta(layout, h.TAXPAYER_KEY)
    heute = date.today()
    form = ctx.pop("form", None) or {
        "issue_date": heute.isoformat(),
        "supply_date": heute.isoformat(),
        "kleinunternehmer": _kleinunternehmer(layout, heute.year),
        "kleinunternehmer_hinweis": KLEINUNTERNEHMER_HINWEIS,
        "positionen": [],
    }
    while len(form["positionen"]) < 3:
        form["positionen"].append({"satz": "0" if form.get("kleinunternehmer") else "19"})
    return _render(
        request,
        "rechnungen.html",
        layout,
        "rechnungen",
        rechnungen=rows,
        storniert=storniert,
        jahr=jahr,
        form=form,
        saetze=_RECHNUNG_SAETZE,
        absender_fehlt=not (tp.get("name") and tp.get("street") and tp.get("city")),
        **ctx,
    )


@router.get("/rechnungen", response_class=HTMLResponse)
def rechnungen(
    request: Request,
    projekt: str | None = None,
    jahr: int | None = Query(default=None, ge=2000, le=2100),
    meldung: str | None = None,
    fehler: str | None = None,
):
    layout = h.resolve(projekt)
    return _rechnungen_render(
        request, layout, jahr or date.today().year, meldung=meldung, fehler=fehler
    )


@router.post("/rechnungen", response_class=HTMLResponse)
def rechnung_anlegen(
    request: Request,
    projekt: str | None = Query(default=None),
    kunde_name: str = Form(""),
    kunde_strasse: str = Form(""),
    kunde_plz: str = Form(""),
    kunde_ort: str = Form(""),
    kunde_land: str = Form(""),
    kunde_ustid: str = Form(""),
    issue_date: str = Form(""),
    supply_date: str = Form(""),
    supply_von: str = Form(""),
    supply_bis: str = Form(""),
    notes: str = Form(""),
    kleinunternehmer: str = Form(""),
    kleinunternehmer_hinweis: str = Form(""),
    pos_beschreibung: list[str] = Form(default=[]),
    pos_menge: list[str] = Form(default=[]),
    pos_einheit: list[str] = Form(default=[]),
    pos_preis: list[str] = Form(default=[]),
    pos_satz: list[str] = Form(default=[]),
):
    """Issue an invoice (INV-1): number, PDF and a stored sale receipt."""
    from finamt.invoicing import Invoice, InvoiceLine, Party, issue_invoice, supplier_from_taxpayer

    layout = h.resolve(projekt)
    ku = kleinunternehmer == "1"
    n = max(len(pos_beschreibung), len(pos_preis))

    def at(values: list[str], i: int) -> str:
        return values[i].strip() if i < len(values) else ""

    positionen = [
        {
            "beschreibung": at(pos_beschreibung, i),
            "menge": at(pos_menge, i),
            "einheit": at(pos_einheit, i),
            "preis": at(pos_preis, i),
            "satz": at(pos_satz, i) or "19",
        }
        for i in range(n)
    ]
    form = {
        "kunde_name": kunde_name,
        "kunde_strasse": kunde_strasse,
        "kunde_plz": kunde_plz,
        "kunde_ort": kunde_ort,
        "kunde_land": kunde_land,
        "kunde_ustid": kunde_ustid,
        "issue_date": issue_date,
        "supply_date": supply_date,
        "supply_von": supply_von,
        "supply_bis": supply_bis,
        "notes": notes,
        "kleinunternehmer": ku,
        "kleinunternehmer_hinweis": kleinunternehmer_hinweis,
        "positionen": [p for p in positionen if p["beschreibung"] or p["preis"]],
    }
    try:
        lines = []
        for p in form["positionen"]:
            preis = h.parse_betrag(p["preis"])
            menge = h.parse_betrag(p["menge"]) if p["menge"] else Decimal("1")
            if preis is None:
                raise ValueError(f"Position „{p['beschreibung']}“: Einzelpreis fehlt.")
            satz = (
                Decimal("0")
                if ku
                else Decimal(p["satz"] if p["satz"] in _RECHNUNG_SAETZE else "19")
            )
            lines.append(InvoiceLine(p["beschreibung"], menge, preis, satz, p["einheit"]))
        von = date.fromisoformat(supply_von) if supply_von else None
        bis = date.fromisoformat(supply_bis) if supply_bis else None
        if bool(von) != bool(bis):
            raise ValueError("Leistungszeitraum: Beginn und Ende angeben.")
        inv = Invoice(
            supplier=supplier_from_taxpayer(h.get_meta(layout, h.TAXPAYER_KEY)),
            customer=Party(
                name=kunde_name.strip(),
                street=kunde_strasse.strip(),
                postcode=kunde_plz.strip(),
                city=kunde_ort.strip(),
                country=kunde_land.strip(),
                ust_idnr=kunde_ustid.strip().upper().replace(" ", ""),
            ),
            issue_date=date.fromisoformat(issue_date) if issue_date else date.today(),
            supply_date=None if von else (date.fromisoformat(supply_date) if supply_date else None),
            supply_period=(von, bis) if von and bis else None,
            lines=lines,
            notes=notes.strip(),
            kleinunternehmer=ku,
            kleinunternehmer_hinweis=kleinunternehmer_hinweis.strip(),
        )
        fehler = inv.missing_fields(need_number=False)
        if fehler:
            raise ValueError("\n".join(fehler))
        layout.create_dirs()
        with h.open_repo(layout, create=True) as repo:
            res = issue_invoice(repo, inv, layout.pdfs_dir)
    except ValueError as exc:
        return _rechnungen_render(
            request,
            layout,
            date.today().year,
            form=form,
            form_fehler=str(exc).split("\n"),
        )
    return _redirect(
        "/rechnungen",
        layout.name,
        jahr=res.invoice.issue_date.year,
        meldung=f"Rechnung {res.invoice.number} erstellt.",
    )


@router.post("/rechnungen/{nummer}/stornieren")
def rechnung_stornieren(nummer: str, projekt: str | None = Query(default=None)):
    from finamt.invoicing import cancel_invoice

    layout = h.resolve(projekt)
    try:
        with h.open_repo(layout, create=True) as repo:
            res = cancel_invoice(repo, nummer, layout.pdfs_dir)
    except ValueError as exc:
        return _redirect("/rechnungen", layout.name, fehler=str(exc))
    return _redirect(
        "/rechnungen",
        layout.name,
        jahr=res.invoice.issue_date.year,
        meldung=f"Rechnung {nummer} storniert durch {res.invoice.number}.",
    )


@router.get("/rechnungen/{nummer}.pdf")
def rechnung_pdf(nummer: str, projekt: str | None = None):
    """The invoice PDF (the original of its sale receipt)."""
    from fastapi.responses import FileResponse

    from finamt.ui import api as _api  # lazy: api.py imports this module

    layout = h.resolve(projekt)
    with h.open_repo(layout) as repo:
        data = repo.get_invoice(nummer) if repo is not None else None
    datei = (
        _api._find_stored_file(data["receipt_id"], layout.db_path)
        if data and data.get("receipt_id")
        else None
    )
    if datei is None:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden.")
    return FileResponse(
        datei,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="Rechnung_{nummer}.pdf"'},
    )


# ---------------------------------------------------------------------------
# Stammdaten (UI-7)
# ---------------------------------------------------------------------------


def _stammdaten_context(layout) -> dict:
    tp = h.get_meta(layout, h.TAXPAYER_KEY)
    misc = h.get_meta(layout, h.ELSTER_MISC_KEY)
    eric = h.get_meta(layout, h.ERIC_HOME_KEY)
    land = bundesland_by_name(tp.get("state"))
    return {
        "tp": tp,
        "land": land,
        "land_unbekannt": tp.get("state") if tp.get("state") and land is None else None,
        "laender": BUNDESLAENDER,
        "info": h.steuernummer_fuer(tp, "ust") if tp.get("tax_number") else None,
        "info_est": h.steuernummer_fuer(tp, "est") if tp.get("tax_number_est") else None,
        "art": "",
        "zwei_nummern": bool((tp.get("tax_number_est") or "").strip()),
        "euer_wahl": tp.get("euer_steuernummer") or "",
        "euer_wahlen": h.EUER_WAHL,
        "hersteller_id": misc.get("hersteller_id") or "",
        "pin_gespeichert": bool(misc.get("cert_pin")),
        "cert_gespeichert": (layout.root / h.CERT_FILENAME).exists(),
        "eric_home": eric.get("path") or "",
        "settings": _settings(layout),
    }


@router.get("/stammdaten", response_class=HTMLResponse)
def stammdaten(request: Request, projekt: str | None = None, gespeichert: str = ""):
    layout = h.resolve(projekt)
    return _render(
        request,
        "stammdaten.html",
        layout,
        "stammdaten",
        gespeichert=gespeichert,
        **_stammdaten_context(layout),
    )


@router.get("/stammdaten/steuernummer", response_class=HTMLResponse)
def stammdaten_steuernummer(
    request: Request, state: str = "", tax_number: str = "", tax_number_est: str = "", art: str = ""
):
    """htmx partial: the computed ELSTER numbers for one Steuernummer field (``art=est``: ESt)."""
    nr = tax_number_est if art == "est" else tax_number
    info = steuernummer_info(nr, bundesland_by_name(state)) if nr.strip() else None
    return templates.TemplateResponse(
        request, "_steuernummer.html", {**_i18n_ctx(request), "info": info, "art": art}
    )


@router.post("/stammdaten/steuerpflichtiger")
def stammdaten_speichern(
    projekt: str | None = Query(default=None),
    name: str = Form(""),
    street: str = Form(""),
    address_supplement: str = Form(""),
    postcode: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    tax_number: str = Form(""),
    tax_number_est: str = Form(""),
    euer_steuernummer: str = Form(""),
    vat_id: str = Form(""),
    rechtsform: str = Form("Freiberuflich"),
):
    layout = h.resolve(projekt)
    land = bundesland_by_name(state)
    with h.open_repo(layout, create=True) as repo:
        tp = repo.get_metadata(h.TAXPAYER_KEY) or {}
        # Keep fields the old UI stores (e.g. gegenstand, country); same keys as the old UI.
        tp.update(
            {
                "name": name.strip(),
                "street": street.strip(),
                "address_supplement": address_supplement.strip(),
                "postcode": postcode.strip(),
                "city": city.strip(),
                "state": land.name if land else "",
                "tax_number": tax_number.strip(),  # Umsatzsteuer (old UI uses it for UStVA)
                "tax_number_est": tax_number_est.strip(),  # Einkommensteuer; empty = same
                "euer_steuernummer": euer_steuernummer if euer_steuernummer in h.EUER_WAHL else "",
                "vat_id": vat_id.strip().upper().replace(" ", ""),
                "rechtsform": rechtsform.strip() or "Freiberuflich",
            }
        )
        tp.setdefault("country", "Deutschland")
        repo.set_metadata(h.TAXPAYER_KEY, tp)
    return _redirect("/stammdaten", layout.name, gespeichert="steuerpflichtiger")


@router.post("/stammdaten/elster")
def stammdaten_elster(
    projekt: str | None = Query(default=None),
    hersteller_id: str = Form(""),
    cert_pin: str = Form(""),
    eric_home: str = Form(""),
    zertifikat: UploadFile | None = File(None),
):
    layout = h.resolve(projekt)
    with h.open_repo(layout, create=True) as repo:
        misc = repo.get_metadata(h.ELSTER_MISC_KEY) or {}
        misc["hersteller_id"] = hersteller_id.strip()
        if cert_pin:  # empty field = keep the stored PIN
            misc["cert_pin"] = cert_pin
        repo.set_metadata(h.ELSTER_MISC_KEY, misc)
        if eric_home.strip():
            repo.set_metadata(h.ERIC_HOME_KEY, {"path": eric_home.strip()})
    if zertifikat is not None and zertifikat.filename:
        data = zertifikat.file.read()
        if data:
            (layout.root / h.CERT_FILENAME).write_bytes(data)
    return _redirect("/stammdaten", layout.name, gespeichert="elster")


@router.post("/stammdaten/zeitraum")
def stammdaten_zeitraum(
    projekt: str | None = Query(default=None),
    monatlich: str = Form(""),
    dauerfrist: str = Form(""),
):
    layout = h.resolve(projekt)
    _merge_settings(layout, monatlich=monatlich == "1", dauerfrist=dauerfrist == "1")
    return _redirect("/stammdaten", layout.name, gespeichert="zeitraum")


@router.post("/stammdaten/kleinunternehmer", response_class=HTMLResponse)
def stammdaten_kleinunternehmer(
    request: Request, projekt: str | None = Query(default=None), jahre: str = Form("")
):
    """EUR-8: the years in which the taxpayer is a Kleinunternehmer (§ 19 UStG)."""
    layout = h.resolve(projekt)
    teile = [t for t in jahre.replace(";", ",").replace(" ", ",").split(",") if t]
    if not all(t.isdigit() and len(t) == 4 and 2000 <= int(t) <= 2100 for t in teile):
        return _render(
            request,
            "stammdaten.html",
            layout,
            "stammdaten",
            gespeichert="",
            ku_fehler="Bitte Jahreszahlen mit vier Ziffern, durch Komma getrennt.",
            **_stammdaten_context(layout),
        )
    _merge_settings(layout, kleinunternehmer_jahre=sorted({int(t) for t in teile}))
    return _redirect("/stammdaten", layout.name, gespeichert="kleinunternehmer")
