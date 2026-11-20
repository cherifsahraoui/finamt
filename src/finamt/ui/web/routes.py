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

router = APIRouter(prefix="/app", include_in_schema=False)

# Short German labels for the UStVA Kennzahlen the code produces (tax-rules.md, USt1A-2026)
KZ_LABELS = {
    "Kz81": "Umsätze 19 % (Bemessungsgrundlage, volle Euro)",
    "Kz86": "Umsätze 7 % (Bemessungsgrundlage, volle Euro)",
    "Kz35": "Umsätze zu anderen Steuersätzen (Bemessungsgrundlage)",
    "Kz36": "Steuer zu anderen Steuersätzen",
    "Kz66": "Vorsteuer aus Rechnungen anderer Unternehmer",
    "Kz62": "Einfuhrumsatzsteuer",
    "Kz83": "Verbleibende Vorauszahlung (+) / Überschuss (−)",
}

TYP_LABELS = {"purchase": "Ausgabe", "sale": "Einnahme"}
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
        jahr_receipts, heute.year, kleinunternehmer=_kleinunternehmer(layout, heute.year)
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
        pdf_url=f"/receipts/{receipt_id}/pdf?{urlencode({'db': str(layout.db_path)})}",
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
            pdf_url=f"/receipts/{receipt_id}/pdf?{urlencode({'db': str(layout.db_path)})}",
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
):
    """aktion: ``pruefen`` (ERiC validation only), ``test`` (Testmerker), ``live``."""
    from finamt.ui import api as _api  # lazy: api.py imports this module

    layout = h.resolve(projekt)
    z = h.zeitraum(jahr, zeitraum)
    if z is None or aktion not in ("pruefen", "test", "live"):
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
            "validate_only": aktion == "pruefen",
        }
        try:
            if z.is_jahr:
                vz = h.parse_betrag(vorauszahlungssoll) or Decimal("0")
                body = _api.UStESubmitRequest(
                    **common,
                    besteuerungsart=besteuerungsart if besteuerungsart in ("1", "2", "3") else "1",
                    # the existing API model takes a float; it converts back to Decimal
                    vorauszahlungssoll=float(vz),
                )
                res = _api.post_uste_submit(body, db=str(layout.db_path))
            else:
                body = _api.UStVASubmitRequest(
                    **common,
                    quarter=z.quarter,
                    month=z.month,
                    is_berichtigung=bool(berichtigung),
                )
                res = _api.post_ustva_submit(body, db=str(layout.db_path))
            ergebnis = {
                "success": bool(res.get("success")),
                "message": res.get("message") or res.get("error_message") or "",
                "telenummer": res.get("telenummer"),
                "error_code": res.get("error_code"),
                "aktion": aktion,
            }
        except HTTPException as exc:
            ergebnis = {"success": False, "message": str(exc.detail), "status": exc.status_code}
        except ValueError as exc:
            ergebnis = {"success": False, "message": str(exc)}
    return _render(
        request, "ustva.html", layout, "ustva", ergebnis=ergebnis, **_ustva_context(layout, z)
    )


# ---------------------------------------------------------------------------
# EÜR (UI-4)
# ---------------------------------------------------------------------------


@router.get("/euer", response_class=HTMLResponse)
def euer(request: Request, projekt: str | None = None, jahr: int | None = None):
    layout = h.resolve(projekt)
    jahr = jahr if jahr and 2000 <= jahr <= 2100 else date.today().year - 1
    receipts = _receipts(layout, date(jahr, 1, 1), date(jahr, 12, 31))
    report = generate_eur(receipts, jahr, kleinunternehmer=_kleinunternehmer(layout, jahr))
    zu_pruefen = []
    for r in _sort(receipts):
        zeile = h.eur_zeile(r)
        if zeile and zeile.zu_pruefen:
            zu_pruefen.append((r, zeile))
    return _render(
        request,
        "euer.html",
        layout,
        "euer",
        report=report,
        jahr=jahr,
        zu_pruefen=zu_pruefen,
        stnr=h.steuernummer_fuer(h.get_meta(layout, h.TAXPAYER_KEY), "euer"),
    )


@router.get("/euer/{jahr}.json")
def euer_json(jahr: int, projekt: str | None = None):
    layout = h.resolve(projekt)
    receipts = _receipts(layout, date(jahr, 1, 1), date(jahr, 12, 31))
    body = generate_eur(receipts, jahr, kleinunternehmer=_kleinunternehmer(layout, jahr)).to_json()
    return Response(
        body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="euer_{jahr}.json"'},
    )


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
# Rechnungen (UI-5 waits for INV-1)
# ---------------------------------------------------------------------------


@router.get("/rechnungen", response_class=HTMLResponse)
def rechnungen(request: Request, projekt: str | None = None):
    return _render(request, "rechnungen.html", h.resolve(projekt), "rechnungen")


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
