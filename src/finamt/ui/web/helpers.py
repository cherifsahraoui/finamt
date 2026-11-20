"""
Helpers for the server-rendered UI: projects, formatting, periods, deadlines.

Deadline rules (docs/tax-rules.md, "UStVA periods and deadlines"):
- the Voranmeldung is due on the 10th day after the period ends (§ 18 Abs. 1 S. 1 UStG);
- Dauerfristverlängerung moves it by one month (§ 46 UStDV).
No weekend/holiday shift is applied; that rule is not in tax-rules.md.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from finamt.models import ReceiptData
from finamt.storage import project as _project
from finamt.storage.sqlite import SQLiteRepository
from finamt.tax.bundesland import SteuernummerInfo, bundesland_by_name, steuernummer_info
from finamt.tax.eur import REVIEW, generate_eur

MONATE = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)  # fmt: skip

SETTINGS_KEY = "freibuch_settings"  # UStVA period and Dauerfristverlängerung
TAXPAYER_KEY = "taxpayer"  # same key as ui/api.py _TAXPAYER_KEY (old UI)
ELSTER_MISC_KEY = "elster_misc"  # same keys as /tax/ebilanz/settings
ERIC_HOME_KEY = "elster_eric_home"
CERT_FILENAME = "elster_cert.pfx"


# ---------------------------------------------------------------------------
# Projects and repository
# ---------------------------------------------------------------------------


def resolve(projekt: str | None) -> _project.ProjectLayout:
    """Layout for a project name from the URL; unknown or invalid names fall back to default."""
    if projekt and _project.validate_project_name(projekt) is None:
        return _project.resolve_project(projekt, env_var=False)
    return _project.resolve_project(None)


def project_names(current: str) -> list[str]:
    names = [p.name for p in _project.list_projects()]
    if current not in names:
        names.insert(0, current)
    return names


@contextmanager
def open_repo(layout: _project.ProjectLayout, *, create: bool = False) -> Iterator:
    """Yield a repository, or ``None`` when the DB doesn't exist and ``create`` is False."""
    if not layout.db_path.exists():
        if not create:
            yield None
            return
        layout.create_dirs()
    with SQLiteRepository(db_path=layout.db_path) as repo:
        yield repo


EUER_WAHL = {"est": "Einkommensteuer-Nummer", "ust": "Umsatzsteuer-Nummer"}


def steuernummer_fuer(tp: dict, zweck: str) -> SteuernummerInfo:
    """The Steuernummer to use for ``zweck``: ``"ust"`` (UStVA, USt), ``"est"`` or ``"euer"``.

    Profile keys: ``tax_number`` (Umsatzsteuer; the old UI uses it for UStVA/USt),
    ``tax_number_est`` (Einkommensteuer, optional: empty = the same number for everything),
    ``euer_steuernummer`` (``"est"``/``"ust"``: which one the Anlage EÜR is filed under).
    With two different numbers the EÜR choice is the owner's: the official sources read so far
    don't say which one (docs/tax-rules.md, row "two Steuernummern").
    """
    land = bundesland_by_name(tp.get("state"))
    ust = steuernummer_info(tp.get("tax_number"), land)
    if zweck == "ust" or not (tp.get("tax_number_est") or "").strip():
        return ust
    est = steuernummer_info(tp.get("tax_number_est"), land)
    if zweck == "est":
        return est
    if est.elster13 and est.elster13 == ust.elster13:
        return est
    wahl = tp.get("euer_steuernummer")
    if wahl == "est":
        return est
    if wahl == "ust":
        return ust
    return SteuernummerInfo(
        fehler=(
            "Zwei Steuernummern eingetragen: in den Stammdaten festlegen, "
            "unter welcher die Anlage EÜR abgegeben wird."
        )
    )


def get_meta(layout: _project.ProjectLayout, key: str) -> dict:
    with open_repo(layout) as repo:
        if repo is None:
            return {}
        return repo.get_metadata(key) or {}


# ---------------------------------------------------------------------------
# Formatting and parsing (German)
# ---------------------------------------------------------------------------


def eur(value: Decimal | int | str | None) -> str:
    """``Decimal("1234.5")`` → ``"1.234,50 €"``; ``None`` → ``"—"``."""
    if value is None or value == "":
        return "—"
    d = Decimal(str(value)).quantize(Decimal("0.01"))
    s = format(d, ",.2f")
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".") + " €"


def zahl(value: Decimal | None) -> str:
    """Decimal for an input field, German style without thousands separator."""
    if value is None:
        return ""
    return str(value).replace(".", ",")


def datum(value: date | datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d.%m.%Y")


def parse_betrag(text: str | None) -> Decimal | None:
    """Parse ``"1.234,56"``, ``"1234.56"`` or ``"1234,56 €"``. Empty → ``None``.

    Raises ``ValueError`` with a German message on bad input.
    """
    s = (text or "").strip().replace("€", "").replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"Kein gültiger Betrag: {text!r}") from exc


# ---------------------------------------------------------------------------
# Periods and deadlines
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Zeitraum:
    key: str  # "q1".."q4", "m01".."m12", "jahr"
    jahr: int
    start: date
    end: date
    label: str
    quarter: int | None = None
    month: int | None = None

    @property
    def is_jahr(self) -> bool:
        return self.key == "jahr"

    @property
    def submission_type(self) -> str:
        """Key used in the project's ``submissions`` metadata (same as ui/api.py)."""
        if self.is_jahr:
            return "uste"
        return f"ustva_q{self.quarter}" if self.quarter else f"ustva_m{self.month:02d}"


def zeitraum(jahr: int, key: str | None) -> Zeitraum | None:
    key = (key or "").lower()
    if key == "jahr":
        return Zeitraum("jahr", jahr, date(jahr, 1, 1), date(jahr, 12, 31), f"Jahr {jahr}")
    if len(key) == 2 and key[0] == "q" and key[1] in "1234":
        q = int(key[1])
        end_month = 3 * q
        end = date(jahr, end_month, calendar.monthrange(jahr, end_month)[1])
        return Zeitraum(key, jahr, date(jahr, end_month - 2, 1), end, f"Q{q} {jahr}", quarter=q)
    if len(key) == 3 and key[0] == "m" and key[1:].isdigit() and 1 <= int(key[1:]) <= 12:
        m = int(key[1:])
        end = date(jahr, m, calendar.monthrange(jahr, m)[1])
        return Zeitraum(key, jahr, date(jahr, m, 1), end, f"{MONATE[m - 1]} {jahr}", month=m)
    return None


def zeitraum_keys(monatlich: bool) -> list[str]:
    return [f"m{m:02d}" for m in range(1, 13)] if monatlich else ["q1", "q2", "q3", "q4"]


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, d.day)


def ustva_frist(z: Zeitraum, dauerfrist: bool) -> date:
    """10th day after the period ends; one month later with Dauerfristverlängerung."""
    due = _add_months(date(z.end.year, z.end.month, 10), 1)
    return _add_months(due, 1) if dauerfrist else due


def naechste_ustva(heute: date, monatlich: bool, dauerfrist: bool) -> tuple[Zeitraum, date]:
    """The first UStVA period (from last year on) whose deadline is today or later."""
    for jahr in (heute.year - 1, heute.year, heute.year + 1):
        for key in zeitraum_keys(monatlich):
            z = zeitraum(jahr, key)
            frist = ustva_frist(z, dauerfrist)
            if frist >= heute:
                return z, frist
    raise AssertionError("unreachable")  # pragma: no cover


# ---------------------------------------------------------------------------
# EÜR line of one receipt
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EurZeile:
    kz: str  # Kennzahl, or "review"
    label: str
    reason: str = ""

    @property
    def zu_pruefen(self) -> bool:
        return self.kz == REVIEW


def eur_zeile(r: ReceiptData) -> EurZeile | None:
    """Which Anlage EÜR line this receipt lands on, using the same logic as the report."""
    if r.receipt_date is None:
        return None
    rep = generate_eur([r], r.receipt_date.year)
    for ln in (
        *rep.review_lines.values(),
        *rep.einnahmen_lines.values(),
        *rep.ausgaben_lines.values(),
    ):
        return EurZeile(ln.kz, ln.label, ln.reason)
    return None


# ---------------------------------------------------------------------------
# Anlage EÜR to ELSTER (EUR-9)
# ---------------------------------------------------------------------------

#: Stammdaten "Rechtsform" → Anlage EÜR code E6000602 (eur_elster, verified in EUR-4).
EUER_RECHTSFORM = {"Freiberuflich": "140"}


def eur_taxpayer(tp: dict, art_des_betriebs: str, grundstuecke_entnommen: bool | None):
    """
    ``(EURTaxpayer, None)`` from the Stammdaten plus the two Anlage EÜR answers, or
    ``(None, German error)`` naming what is missing.
    """
    from finamt.tax.eur_elster import EURTaxpayer

    info = steuernummer_fuer(tp, "euer")
    if info.fehler:
        return None, f"Steuernummer: {info.fehler}"
    if not all((tp.get("name"), tp.get("street"), tp.get("postcode"), tp.get("city"))):
        return None, "Name und Anschrift fehlen in den Stammdaten."
    rechtsform = EUER_RECHTSFORM.get(tp.get("rechtsform") or "Freiberuflich")
    if rechtsform is None:
        return (
            None,
            f"Rechtsform „{tp.get('rechtsform')}“ wird für die Anlage EÜR nicht unterstützt.",
        )
    if not (art_des_betriebs or "").strip():
        return None, "Art des Betriebs fehlt."
    if grundstuecke_entnommen is None:
        return None, "Zeile 11 (Grundstücke entnommen oder veräußert) bitte beantworten."
    return (
        EURTaxpayer(
            name=tp["name"].strip(),
            street=tp["street"].strip(),
            postal_code=tp["postcode"].strip(),
            city=tp["city"].strip(),
            steuernummer=info.elster13,
            art_des_betriebs=art_des_betriebs.strip(),
            grundstuecke_entnommen=grundstuecke_entnommen,
            rechtsform=rechtsform,
        ),
        None,
    )


def eric_library_path(layout) -> str:
    """``ERIC_LIBRARY_PATH`` (decision D4), else the ERiC path saved in Stammdaten."""
    import os

    from finamt.tax.eur_elster import ERIC_LIBRARY_ENV

    return (
        os.environ.get(ERIC_LIBRARY_ENV, "").strip()
        or (get_meta(layout, ERIC_HOME_KEY).get("path") or "").strip()
    )


def elster_cert_config(layout, steuernummer: str, finanzamt_nr: str, bundesland_kz: str):
    """``ElsterConfig`` with the certificate and PIN saved in Stammdaten, or ``None``."""
    from finamt.tax.elster import ElsterConfig

    cert = layout.root / CERT_FILENAME
    pin = get_meta(layout, ELSTER_MISC_KEY).get("cert_pin") or ""
    if not cert.exists() or not pin:
        return None
    return ElsterConfig(
        cert_path=str(cert),
        cert_password=pin,
        steuernummer=steuernummer,
        finanzamt_nr=finanzamt_nr,
        bundesland_kz=bundesland_kz,
    )
