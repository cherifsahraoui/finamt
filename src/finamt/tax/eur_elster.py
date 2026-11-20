"""
finamt.tax.eur_elster
~~~~~~~~~~~~~~~~~~~~~
ELSTER boundary for the Einnahmen-Überschuss-Rechnung (Anlage EÜR).

Status
------
- ``build_xml``     — Anlage EÜR 2025 envelope (datenartVersion ``EUER_2025``), test
                      builds only (Testmerker). Every element name, format and order is
                      listed in ``docs/tax-rules.md`` ("Anlage EÜR 2025 XML").
                      Not built yet: AfA / GWG (Kz 130/131/132/136/137, EUR-3, needs
                      Anlage AVEÜR), Kz 151 (needs the Zeile 42 split, Kz 153) and
                      Kz 234 above 2 050 € (needs Anlage SZ). Those raise
                      ``NotImplementedError``.
- ``validate``      — local, offline structural check of an ELSTER envelope.
- ``eric_validate`` — ERiC validation only (``ERIC_VALIDIERE``): nothing is sent.
- ``submit``        — ``mode="dry_run"`` (default): validate locally, send nothing.
                      ``mode="test"``: validate + send via ERiC **with Testmerker only**.
                      ``mode="live"``: always raises ``NotImplementedError``.

ERiC
----
The ERiC library directory is read from the ``ERIC_LIBRARY_PATH`` environment
variable only (not ``FINAMT_ERIC_HOME``, not the project database).
The ctypes bridge is :mod:`finamt.tax.eric_wrapper`.
"""

from __future__ import annotations

import contextlib
import os
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from lxml import etree

from .elster import (
    NS,
    PRODUKT_NAME,
    PRODUKT_VERSION,
    TESTMERKER,
    ElsterConfig,
    ElsterEricClient,
    SubmissionResult,
    _druck_params,
    _sent_despite_print_error,
)
from .eric_wrapper import (
    ERIC_DRUCKE,
    ERIC_SENDE,
    ERIC_VALIDIERE,
    EricBuffer,
    EricCertificate,
    EricError,
    EricSession,
)
from .eur import FORM_YEAR, EURReport

ERIC_LIBRARY_ENV = "ERIC_LIBRARY_PATH"
MODES = ("dry_run", "test", "live")
LIVE_DISABLED_MESSAGE = "Live ELSTER submission requires a Hersteller-ID and is disabled."

# ---------------------------------------------------------------------------
# Anlage EÜR 2025 schema facts (docs/tax-rules.md → "Anlage EÜR 2025 XML")
# ---------------------------------------------------------------------------

#: Form year the element names below were verified for (E77-2025.xsd).
SCHEMA_YEAR = 2025
DATENART_VERSION = f"EUER_{SCHEMA_YEAR}"
VERFAHREN = "ElsterErklaerung"
DATENART = "EUER"
E77_NS = f"http://finkonsens.de/elster/elstererklaerung/euer/e77/v{SCHEMA_YEAR}"
COPYRIGHT = "(c) FreiBuch contributors, AGPL-3.0"

#: (Kennzahl, element path under ``EUER/``, signed). ``signed=True`` is format ``P``
#: (sign allowed), ``False`` is format ``%`` (no sign). Order = E77-2025.xsd order.
_BEIN_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ("111", "BEin/Kleinunternehmer/Sum/E6000101", True),
    ("112", "BEin/USt_StPflicht/Sum/E6000401", True),
    ("103", "BEin/USt_StFrei/Sum/E6000501", True),
    ("140", "BEin/USt_Vereinnahmt_Unentgeltl/Sum/E6000601", True),
    ("141", "BEin/USt_Erstattet_Verrechnet/Sum/E6000701", False),
    ("102", "BEin/Anlagevermoegen/Sum/E6000801", True),
    ("106", "BEin/Nutzung_Priv_Kfz/Sum/E6000901", False),
    ("108", "BEin/Entnahme_Sonst/Sum/E6001001", False),
)
_BEIN_TOTAL_PATH = "BEin/GesamtSum/E6001201"  # Kz 159

_BAUS_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ("100", "BAus/Ware_Rohstoff_Hilfsstoff/Sum/E6001601", True),
    ("110", "BAus/Fremdleistung/Sum/E6001701", True),
    ("136", "BAus/AfA/E6001901", False),
    ("131", "BAus/AfA/E6002001", False),
    ("130", "BAus/AfA/E6002101", True),
    ("132", "BAus/AfA/Wirtschaftsgut_geringwertig/Sum/E6002301", False),
    ("137", "BAus/AfA/Weitere_Angabe/E6003302", False),
    ("150", "BAus/Raumkosten_u_sonst/Miete_Pacht/Sum/E6003201", True),
    ("151", "BAus/Raumkosten_u_sonst/Sonst_Aufw_betr_Grund/Sum/E6003301", True),
    ("280", "BAus/Sonst_unbeschraenkt/Kommunikation/Sum/E6003901", True),
    ("221", "BAus/Sonst_unbeschraenkt/Auswertstaetigkeit/Sum/E6004004", True),
    ("281", "BAus/Sonst_unbeschraenkt/Fortbildung/Sum/E6004003", True),
    ("194", "BAus/Sonst_unbeschraenkt/Rechtsberatung_StB_Buchf/Sum/E6004801", True),
    ("222", "BAus/Sonst_unbeschraenkt/Miete_Leasing_bewegl_WG/Sum/E6004304", True),
    ("223", "BAus/Sonst_unbeschraenkt/Beitrag_Gebuehr_Abgabe_Versicherung/Sum/E6004402", True),
    ("228", "BAus/Sonst_unbeschraenkt/EDV/Sum/E6004405", True),
    ("229", "BAus/Sonst_unbeschraenkt/Arbeitsmittel/Sum/E6004408", True),
    ("227", "BAus/Sonst_unbeschraenkt/Verpackung_Transport/Sum/E6004414", True),
    ("224", "BAus/Sonst_unbeschraenkt/Werbung/Sum/E6004501", True),
    ("232", "BAus/Sonst_unbeschraenkt/Schuldzins_AnlageVerm/Sum/E6004202", True),
    ("234", "BAus/Sonst_unbeschraenkt/Schuldzins_Uebrige/Sum/E6004303", True),
    ("185", "BAus/Sonst_unbeschraenkt/Vorsteuer/Sum/E6005001", True),
    ("186", "BAus/Sonst_unbeschraenkt/USt/Sum/E6005101", False),
    ("183", "BAus/Sonst_unbeschraenkt/Sonst_unbeschr_abziehbar/Sum/E6004901", True),
    ("164", "BAus/Beschr_abziehbar/Nicht_abziehbar/Geschenke/Sum/E6004001", False),
    ("165", "BAus/Beschr_abziehbar/Nicht_abziehbar/Bewirtung/Sum/E6004101", False),
    ("174", "BAus/Beschr_abziehbar/Abziehbar/Geschenke/Sum/E6004002", True),
    ("175", "BAus/Beschr_abziehbar/Abziehbar/Bewirtung/Sum/E6004102", True),
    ("171", "BAus/Beschr_abziehbar/Abziehbar/Verpflegung/Sum/E6005002", False),
    ("144", "BAus/KFZ_u_Fahrtkosten/Leasing/Sum/E6005801", True),
    ("145", "BAus/KFZ_u_Fahrtkosten/Steuer_Versicherung_Maut/Sum/E6005903", True),
    ("146", "BAus/KFZ_u_Fahrtkosten/Sonst/Sum/E6006003", True),
    ("147", "BAus/KFZ_u_Fahrtkosten/Fahrtkosten_Nutzungseinlage/Sum/E6006103", False),
    ("176", "BAus/KFZ_u_Fahrtkosten/Entfernungspausch_Familienheimfahrt/Sum/E6003702", False),
)
_BAUS_TOTAL_PATH = "BAus/Summe_BAus/E6005301"  # Kz 199

#: Not deductible: shown on the form but not part of the Kz 199 total (ERiC rule 600614).
_NOT_IN_BAUS_TOTAL = frozenset({"164", "165"})

#: Profit lines (Ermittlung des Gewinns), all format ``P``.
_GEWINN_PATHS = (
    "Ermittlung_Gewinn/Uebertrag/E6005501",  # Zeile 76 = Kz 159 (rule 604030)
    "Ermittlung_Gewinn/Uebertrag/E6005601",  # Zeile 77 = Kz 199 (rule 604040)
    "Ermittlung_Gewinn/Korrektur_GuV/E6006801",  # Zeile 92 (rules 600640, 600648)
    "Ermittlung_Gewinn/Stpfl_GuV/E6007002",  # Zeile 95, Kz 293 (rules 600641, 600644)
    "Ermittlung_Gewinn/Stpfl_GuV/E6007202",  # Zeile 97, Kz 219 (rules 600642, 600645)
)

#: AfA / GWG need Anlage AVEÜR and the depreciation decision (EUR-3, MANUAL-STEPS M3).
_AFA_KZ = frozenset({"130", "131", "132", "136", "137"})

#: Kz 151 (Zeile 41) must come with Zeile 42 "davon Erhaltungsaufwendungen" (Kz 153,
#: ERiC rule 600522). The report has no such split yet.
_NEEDS_SPLIT_KZ = frozenset({"151"})

#: Zeilen 106/107 (Kz 122/123), format ``%``. ERiC rule 600904: both are mandatory for
#: natural persons / sole proprietors.
_ENTNAHMEN_PATH = "Zus_Angabe_EinzelUntern/Entnahme_Einlage/Entnahme/Sum/E6006601"
_EINLAGEN_PATH = "Zus_Angabe_EinzelUntern/Entnahme_Einlage/Einlage/Sum/E6006701"

#: Above this, Kz 234 needs Anlage SZ and Entnahmen/Einlagen (ERiC rules 600068, 600902).
SCHULDZINSEN_LIMIT = Decimal("2050.00")

#: Rechtsform codes for natural persons / sole proprietors (code list RECHTSFORM_EUER_V2_TID).
_RECHTSFORM_TID = frozenset({"110", "120", "130", "140", "150", "160", "190"})
_EINKUNFTSART = frozenset({"2", "3"})  # 2 Gewerbebetrieb, 3 Selbständige Arbeit
_BETRIEBSINHABER = frozenset({"1", "2", "3"})

_MAX_AMOUNT = Decimal("1000000000000")  # 12 digits before the comma
_CENT = Decimal("0.01")
_STNR_RE = re.compile(r"[0-9]{4}0[0-9]{8}")
_PLZ_RE = re.compile(r"(0[1-9][0-9]{3})|([1-9][0-9]{4})")
_HERSTELLER_ID_RE = re.compile(r"[0-9]{5}")


@dataclass(frozen=True)
class EURTaxpayer:
    """
    Taxpayer and business data for ``EUER/Allg`` and ``Vorsatz`` of the Anlage EÜR.

    Codes: ``rechtsform`` "140" = Angehörige(r) der freien Berufe, ``einkunftsart`` "3" =
    Selbständige Arbeit, ``betriebsinhaber`` "1" = steuerpflichtige Person / Person A.
    ``grundstuecke_entnommen`` answers form line 11 (land or buildings withdrawn or sold
    in the year). It has no default because it is a declaration.
    """

    name: str  # E6000016 and Vorsatz/AbsName (max 45)
    street: str  # "Straße Hausnummer": E6000023 and AbsStr (max 30)
    postal_code: str  # E6000024 and AbsPlz (5 digits)
    city: str  # E6000025 and AbsOrt (max 29)
    steuernummer: str  # 13-digit ELSTER format: Vorsatz/StNr
    art_des_betriebs: str  # E6000017 (max 25)
    grundstuecke_entnommen: bool  # E6000019
    rechtsform: str = "140"  # E6000602
    einkunftsart: str = "3"  # E6000603
    betriebsinhaber: str = "1"  # E6000604


def _check_text(label: str, value: str, max_len: int) -> None:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{label} is missing")
    if len(value) > max_len:
        raise ValueError(f"{label} is longer than {max_len} characters: {value!r}")


def _check_taxpayer(tp: EURTaxpayer) -> None:
    _check_text("name", tp.name, 45)
    _check_text("street", tp.street, 30)
    _check_text("city", tp.city, 29)
    _check_text("art_des_betriebs", tp.art_des_betriebs, 25)
    if not _PLZ_RE.fullmatch(tp.postal_code or ""):
        raise ValueError(f"postal_code must be a 5-digit German PLZ, got {tp.postal_code!r}")
    if not _STNR_RE.fullmatch(tp.steuernummer or ""):
        raise ValueError(
            "steuernummer must be the 13-digit ELSTER format (5th digit 0), got "
            f"{tp.steuernummer!r}; see elster.normalise_steuernummer"
        )
    if tp.rechtsform not in _RECHTSFORM_TID:
        raise ValueError(f"rechtsform {tp.rechtsform!r} is not a sole-proprietor code")
    if tp.einkunftsart not in _EINKUNFTSART:
        raise ValueError(f"einkunftsart must be one of {sorted(_EINKUNFTSART)}")
    if tp.betriebsinhaber not in _BETRIEBSINHABER:
        raise ValueError(f"betriebsinhaber must be one of {sorted(_BETRIEBSINHABER)}")


def format_amount(amount: Decimal, *, signed: bool = True) -> str:
    """
    Format a Decimal for the Anlage EÜR: two decimals, decimal **comma** (``1234,50``).

    ``signed=False`` (format ``%``) rejects negative amounts. Zero is ``0,00``.
    """
    if not isinstance(amount, Decimal):
        raise TypeError(f"amount must be Decimal, got {type(amount).__name__}")
    q = amount.quantize(_CENT, rounding=ROUND_HALF_UP)
    if abs(q) >= _MAX_AMOUNT:
        raise ValueError(f"amount {amount} has more than 12 digits before the comma")
    if q == 0:
        return "0,00"
    if q < 0 and not signed:
        raise ValueError(f"amount {amount} must not be negative in this field")
    return f"{q:.2f}".replace(".", ",")


def _append(parent: etree._Element, path: str, text: str) -> None:
    """Append ``text`` at ``path`` below ``parent``. Callers must go in XSD order."""
    *contexts, leaf = path.split("/")
    node = parent
    for name in contexts:
        tag = f"{{{E77_NS}}}{name}"
        last = node[-1] if len(node) else None
        node = last if last is not None and last.tag == tag else etree.SubElement(node, tag)
    etree.SubElement(node, f"{{{E77_NS}}}{leaf}").text = text


def _checked_totals(report: EURReport) -> dict[str, Decimal]:
    """Return the non-zero Kennzahl totals, or refuse to build."""
    if report.year != FORM_YEAR:
        raise ValueError(
            f"Refusing to build: report year {report.year} is not the verified form year "
            f"{FORM_YEAR} (docs/tax-rules.md, YEAR-1)."
        )
    if FORM_YEAR != SCHEMA_YEAR:
        raise ValueError(
            f"Refusing to build: the Kennzahlen are for {FORM_YEAR}, the XML schema facts "
            f"for {SCHEMA_YEAR}. Verify the new schema first (YEAR-1)."
        )
    if report.review_lines:
        keys = ", ".join(sorted(report.review_lines))
        raise ValueError(
            f"Refusing to build: {len(report.review_lines)} receipt group(s) still need a "
            f"manual decision (ZU PRÜFEN): {keys}"
        )
    totals = {kz: v for kz, v in report.kz_totals().items() if v != 0}
    known = {kz for kz, _path, _signed in (*_BEIN_FIELDS, *_BAUS_FIELDS)}
    unknown = sorted(set(totals) - known)
    if unknown:
        raise ValueError(f"No verified Anlage EÜR element for Kennzahl(en) {unknown}")
    afa = sorted(set(totals) & _AFA_KZ)
    if afa:
        # TODO(verify): AfA / GWG lines need Anlage AVEÜR — see docs/tax-rules.md (EUR-3)
        raise NotImplementedError(
            f"Kz {', '.join(afa)}: AfA / GWG lines are not built yet (EUR-3, needs Anlage AVEÜR)."
        )
    split = sorted(set(totals) & _NEEDS_SPLIT_KZ)
    if split:
        raise NotImplementedError(
            f"Kz {', '.join(split)}: needs Zeile 42 (Erhaltungsaufwendungen, Kz 153), "
            "not tracked yet."
        )
    if "112" in totals and "140" not in totals:
        # ERiC rule 600240: taxable income (Kz 112) without collected VAT (Kz 140).
        raise ValueError(
            "Refusing to build: Kz 112 without Kz 140 (ERiC rule 600240). Was the report "
            "made with kleinunternehmer=True, or do the sales lack their VAT?"
        )
    if totals.get("234", Decimal("0")) > SCHULDZINSEN_LIMIT:
        raise NotImplementedError(
            "Kz 234 above 2 050 €: needs Anlage SZ and Entnahmen/Einlagen "
            "(Zeilen 106/107), not built yet."
        )
    return totals


def build_xml(
    eur_report: EURReport,
    taxpayer: EURTaxpayer,
    *,
    entnahmen: Decimal,
    einlagen: Decimal,
    hersteller_id: str,
    test: bool = True,
) -> bytes:
    """
    Build the ELSTER envelope for the Anlage EÜR (datenartVersion ``EUER_2025``).

    Amounts come from :meth:`EURReport.kz_totals`. Kz 159, Kz 199 and the profit lines
    (Zeilen 76, 77, 92, 95, 97) are computed here. Kennzahlen with 0 are left out; the
    totals and profit lines are always sent (ERiC requires them for natural persons).

    Parameters
    ----------
    eur_report:
        Report from :func:`finamt.tax.eur.generate_eur` for ``FORM_YEAR``.
    taxpayer:
        Name, address, Steuernummer and the form header answers.
    entnahmen, einlagen:
        Private withdrawals and deposits of the year incl. Sach-, Leistungs- und
        Nutzungsentnahmen/-einlagen (Zeilen 106/107). Not derived from receipts; ERiC
        requires both for sole proprietors. ``Decimal("0")`` if there were none.
    hersteller_id:
        Five-digit ELSTER Hersteller-ID.
    test:
        Must be ``True``: the envelope carries the Testmerker. Live builds are disabled.

    Raises
    ------
    ValueError
        Wrong year, open ``review_lines``, an unknown Kennzahl, Kz 112 without Kz 140,
        Einlagen below Kz 147, or invalid taxpayer data.
    NotImplementedError
        AfA / GWG (Kz 130/131/132/136/137), Kz 151, Kz 234 above 2 050 €, or ``test=False``.
    """
    if not test:
        raise NotImplementedError(LIVE_DISABLED_MESSAGE)
    if not _HERSTELLER_ID_RE.fullmatch(hersteller_id or ""):
        raise ValueError("hersteller_id must be the 5-digit ELSTER Hersteller-ID")
    _check_taxpayer(taxpayer)
    totals = _checked_totals(eur_report)
    entnahmen_text = format_amount(entnahmen, signed=False)
    einlagen_text = format_amount(einlagen, signed=False)
    if einlagen < totals.get("147", Decimal("0")):
        # ERiC rule 600903
        raise ValueError("einlagen must not be lower than Kz 147 (Fahrtkosten-Nutzungseinlage)")

    zero = Decimal("0")
    sum_bein = sum((totals.get(kz, zero) for kz, _p, _s in _BEIN_FIELDS), zero)
    sum_baus = sum(
        (totals.get(kz, zero) for kz, _p, _s in _BAUS_FIELDS if kz not in _NOT_IN_BAUS_TOTAL),
        zero,
    )
    gewinn = sum_bein - sum_baus

    def _t(tag: str) -> str:
        return f"{{{NS}}}{tag}"

    root = etree.Element(_t("Elster"), nsmap={None: NS})
    th = etree.SubElement(root, _t("TransferHeader"), version="11")
    etree.SubElement(th, _t("Verfahren")).text = VERFAHREN
    etree.SubElement(th, _t("DatenArt")).text = DATENART
    etree.SubElement(th, _t("Vorgang")).text = "send-Auth"
    etree.SubElement(th, _t("Testmerker")).text = TESTMERKER
    etree.SubElement(th, _t("HerstellerID")).text = hersteller_id
    etree.SubElement(th, _t("DatenLieferant")).text = taxpayer.name.strip()
    datei = etree.SubElement(th, _t("Datei"))
    etree.SubElement(datei, _t("Verschluesselung")).text = "CMSEncryptedData"
    etree.SubElement(datei, _t("Kompression")).text = "GZIP"
    etree.SubElement(datei, _t("TransportSchluessel"))

    ndb = etree.SubElement(etree.SubElement(root, _t("DatenTeil")), _t("Nutzdatenblock"))
    ndh = etree.SubElement(ndb, _t("NutzdatenHeader"), version="11")
    etree.SubElement(ndh, _t("NutzdatenTicket")).text = "1"  # one Nutzdatenblock
    etree.SubElement(ndh, _t("Empfaenger"), id="F").text = taxpayer.steuernummer[:4]
    herst = etree.SubElement(ndh, _t("Hersteller"))
    etree.SubElement(herst, _t("ProduktName")).text = PRODUKT_NAME
    etree.SubElement(herst, _t("ProduktVersion")).text = PRODUKT_VERSION
    nd = etree.SubElement(ndb, _t("Nutzdaten"))

    e77 = etree.SubElement(nd, f"{{{E77_NS}}}E77", nsmap={None: E77_NS}, version=str(SCHEMA_YEAR))
    euer = etree.SubElement(e77, f"{{{E77_NS}}}EUER")
    allg = (
        ("E6000016", taxpayer.name.strip()),
        ("E6000023", taxpayer.street.strip()),
        ("E6000024", taxpayer.postal_code),
        ("E6000025", taxpayer.city.strip()),
        ("E6000017", taxpayer.art_des_betriebs.strip()),
        ("E6000602", taxpayer.rechtsform),
        ("E6000603", taxpayer.einkunftsart),
        ("E6000604", taxpayer.betriebsinhaber),
        ("E6000019", "1" if taxpayer.grundstuecke_entnommen else "2"),
    )
    for name, value in allg:
        _append(euer, f"Allg/{name}", value)
    for kz, path, signed in _BEIN_FIELDS:
        if kz in totals:
            _append(euer, path, format_amount(totals[kz], signed=signed))
    _append(euer, _BEIN_TOTAL_PATH, format_amount(sum_bein))
    for kz, path, signed in _BAUS_FIELDS:
        if kz in totals:
            _append(euer, path, format_amount(totals[kz], signed=signed))
    _append(euer, _BAUS_TOTAL_PATH, format_amount(sum_baus))
    gewinn_values = (sum_bein, sum_baus, gewinn, gewinn, gewinn)
    for path, amount in zip(_GEWINN_PATHS, gewinn_values, strict=True):
        _append(euer, path, format_amount(amount))
    _append(euer, _ENTNAHMEN_PATH, entnahmen_text)
    _append(euer, _EINLAGEN_PATH, einlagen_text)

    vorsatz = (
        ("Unterfallart", "77"),
        ("Vorgang", "01"),
        ("StNr", taxpayer.steuernummer),
        ("Zeitraum", str(eur_report.year)),
        ("AbsName", taxpayer.name.strip()),
        ("AbsStr", taxpayer.street.strip()),
        ("AbsPlz", taxpayer.postal_code),
        ("AbsOrt", taxpayer.city.strip()),
        ("Copyright", COPYRIGHT),
        ("OrdNrArt", "S"),
        # Mandatory (ERiC rule 10438); "1" is not allowed for the EÜR (rule 600044).
        ("Rueckuebermittlung/Bescheid", "2"),
    )
    for name, value in vorsatz:
        _append(e77, f"Vorsatz/{name}", value)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def _parse(xml: bytes) -> etree._Element:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    return etree.fromstring(xml, parser=parser)


def validate(xml: bytes) -> list[str]:
    """
    Check an ELSTER envelope locally. Returns a list of errors (empty = OK).

    Offline structural checks only: well-formed, no DOCTYPE, root ``Elster`` in the
    ELSTER namespace, ``TransferHeader`` with ``Verfahren`` and ``DatenArt``, and
    ``DatenTeil`` containing ``Nutzdaten``. It does **not** check Kennzahlen,
    the XSD, or plausibility rules — that is ERiC's job (``eric_validate``).
    """
    if not isinstance(xml, (bytes, bytearray)) or not xml.strip():
        return ["XML is empty"]
    if b"<!DOCTYPE" in xml:
        return ["DOCTYPE declarations are not allowed"]
    try:
        root = _parse(bytes(xml))
    except etree.XMLSyntaxError as exc:
        return [f"XML is not well-formed: {exc}"]

    errors: list[str] = []
    qname = etree.QName(root)
    if qname.localname != "Elster":
        errors.append(f"Root element must be 'Elster', got '{qname.localname}'")
    if qname.namespace != NS:
        errors.append(f"Root namespace must be '{NS}', got '{qname.namespace}'")

    ns = {"e": NS}
    th = root.find("e:TransferHeader", ns)
    if th is None:
        errors.append("Missing TransferHeader")
    else:
        for tag in ("Verfahren", "DatenArt"):
            el = th.find(f"e:{tag}", ns)
            if el is None or not (el.text or "").strip():
                errors.append(f"Missing TransferHeader/{tag}")
    if root.find("e:DatenTeil", ns) is None:
        errors.append("Missing DatenTeil")
    elif root.find(".//e:DatenTeil//e:Nutzdaten", ns) is None:
        errors.append("Missing DatenTeil//Nutzdaten")
    return errors


def has_testmerker(xml: bytes) -> bool:
    """True if the envelope's TransferHeader carries the ELSTER Testmerker."""
    try:
        root = _parse(bytes(xml))
    except etree.XMLSyntaxError:
        return False
    el = root.find(f"{{{NS}}}TransferHeader/{{{NS}}}Testmerker")
    return el is not None and (el.text or "").strip() == TESTMERKER


def eric_validate(
    xml: bytes,
    *,
    datenart_version: str = DATENART_VERSION,
    log_dir: str | None = None,
    eric_home: str | None = None,
    pdf_path: str | None = None,
) -> SubmissionResult:
    """
    Validate an EÜR envelope with the local ERiC library. **Nothing is sent.**

    ``pdf_path``: also write ERiC's print preview there (EBV-2, *** Vorschau ***; with the
    Testmerker also *** Testfall ***). Only written when validation succeeds.

    ``eric_home``: the ERiC lib directory; default ``ERIC_LIBRARY_PATH`` (decision D4).

    Runs ``EricBearbeiteVorgang`` with ``ERIC_VALIDIERE`` only and no certificate.
    ERiC still checks the Hersteller-ID in the envelope (a blocked demo ID fails).
    """
    errors = validate(xml)
    if errors:
        return SubmissionResult(
            success=False, error_code="VALIDATION_ERROR", error_message="; ".join(errors)
        )
    eric_home = (eric_home or os.environ.get(ERIC_LIBRARY_ENV, "")).strip()
    if not eric_home:
        return SubmissionResult(
            success=False,
            error_code="ERIC_LIBRARY_PATH_MISSING",
            error_message=f"Set {ERIC_LIBRARY_ENV} to the ERiC lib directory.",
        )
    return _eric_run(xml, eric_home, datenart_version, None, log_dir, pdf_path)


def submit(
    xml: bytes,
    mode: str = "dry_run",
    *,
    datenart_version: str = DATENART_VERSION,
    config: ElsterConfig | None = None,
    log_dir: str | None = None,
    eric_home: str | None = None,
    pdf_path: str | None = None,
) -> SubmissionResult:
    """
    Validate and optionally transmit an EÜR envelope.

    Parameters
    ----------
    xml:
        ELSTER envelope bytes (from ``build_xml``).
    mode:
        ``"dry_run"`` (default): local validation only, nothing leaves the machine.
        ``"test"``: ERiC validate + send to ELSTER **test** processing. The XML must
        carry the Testmerker, otherwise the call is refused.
        ``"live"``: raises ``NotImplementedError``.
    datenart_version:
        ERiC ``datenartVersion``, default ``EUER_2025`` (verified, docs/tax-rules.md).
    config:
        ``ElsterConfig`` with certificate path and PIN. Defaults to
        ``ElsterConfig.from_env()`` in test mode.
    log_dir:
        Optional ERiC log directory.
    pdf_path:
        Test mode only: ERiC writes its copy there after the server accepted the case.
    eric_home:
        ERiC lib directory; default ``ERIC_LIBRARY_PATH`` (decision D4). Other variables such
        as ``FINAMT_ERIC_HOME`` are never read here.
    """
    if mode == "live":
        raise NotImplementedError(LIVE_DISABLED_MESSAGE)
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES[:2]}, got {mode!r}")

    errors = validate(xml)
    if errors:
        return SubmissionResult(
            success=False, error_code="VALIDATION_ERROR", error_message="; ".join(errors)
        )

    if mode == "dry_run":
        return SubmissionResult(
            success=True, raw_response="dry_run: validated locally, nothing was sent"
        )

    # mode == "test"
    if not has_testmerker(xml):
        return SubmissionResult(
            success=False,
            error_code="TESTMERKER_MISSING",
            error_message=f"Test mode requires TransferHeader/Testmerker={TESTMERKER}.",
        )
    if not datenart_version:
        raise ValueError("datenart_version must not be empty (e.g. 'EUER_2025').")
    eric_home = (eric_home or os.environ.get(ERIC_LIBRARY_ENV, "")).strip()
    if not eric_home:
        return SubmissionResult(
            success=False,
            error_code="ERIC_LIBRARY_PATH_MISSING",
            error_message=f"Set {ERIC_LIBRARY_ENV} to the ERiC lib directory.",
        )
    cfg = config or ElsterConfig.from_env()
    return _eric_run(xml, eric_home, datenart_version, cfg, log_dir, pdf_path)


def _eric_run(
    xml: bytes,
    eric_home: str,
    datenart_version: str,
    cfg: ElsterConfig | None,
    log_dir: str | None,
    pdf_path: str | None = None,
) -> SubmissionResult:
    """
    Run ERiC. ``cfg=None``: validate only, nothing is sent. With ``cfg``: validate + send
    (only reached from ``submit(mode="test")``, after the Testmerker check).
    """
    send = cfg is not None
    rc = 0
    response_xml = b""
    server_xml = b""
    eric_text = ""
    try:
        with EricSession(eric_home, log_dir=log_dir) as eric:
            with EricBuffer(eric) as resp_buf, EricBuffer(eric) as srv_buf:
                # ERiC needs crypto_params NULL when validating only (error 610001027).
                cert_cm = (
                    EricCertificate(eric, str(cfg.cert_path), cfg.cert_password)
                    if send
                    else contextlib.nullcontext()
                )
                with cert_cm as cert:
                    rc, _th = eric.bearbeite_vorgang(
                        xml_bytes=xml,
                        datenart_version=datenart_version,
                        flags=(ERIC_VALIDIERE | ERIC_SENDE if send else ERIC_VALIDIERE)
                        | (ERIC_DRUCKE if pdf_path else 0),
                        crypto_params=cert.verschluesselungs_parameter if send else None,
                        response_buffer=resp_buf.handle(),
                        server_buffer=srv_buf.handle(),
                        druck_params=_druck_params(pdf_path, send),
                    )
                    response_xml = resp_buf.content()
                    server_xml = srv_buf.content()
                    if rc != 0:
                        with contextlib.suppress(Exception):
                            eric_text = eric.get_error_text(rc)
    except EricError as exc:
        return SubmissionResult(success=False, error_code=str(exc.code), error_message=str(exc))
    except OSError as exc:
        return SubmissionResult(
            success=False,
            error_code="ERIC_LOAD_ERROR",
            error_message=f"Could not load ERiC library from {eric_home}: {exc}",
        )

    if rc != 0:
        sent = _sent_despite_print_error(rc, pdf_path, send, server_xml, eric_text)
        if sent is not None:
            return sent
        return SubmissionResult(
            success=False,
            error_code=str(rc),
            error_message=ElsterEricClient._extract_eric_error(
                rc, response_xml, server_xml, eric_text
            ),
            raw_response=(response_xml + server_xml).decode("utf-8", errors="replace"),
        )
    return SubmissionResult(
        success=True,
        telenummer=ElsterEricClient._extract_telenummer(server_xml),
        raw_response=(server_xml or response_xml).decode("utf-8", errors="replace"),
    )
