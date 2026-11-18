"""
finamt.tax.eur
~~~~~~~~~~~~~~
Einnahmen-Überschuss-Rechnung (EÜR) — German income-surplus statement.

Applicable to Freiberufler, Einzelunternehmer and small partnerships that do not keep
double-entry books (§ 4 Abs. 3 EStG). The result is filed as **Anlage EÜR**, electronically
(§ 60 Abs. 4 EStDV).

Cash principle (§ 11 EStG): income counts when received, expenses when paid. This module
treats ``receipt_date`` as the payment date. The 10-day rule for recurring payments
(§ 11 Abs. 1 S. 2, Abs. 2 S. 2 EStG) is not implemented.

Kennzahlen
----------
Mapped to the official **Anlage EÜR 2025** (BMF-Schreiben 29.08.2025). Every Kennzahl used
here is listed with its source in ``docs/tax-rules.md``. For other years a warning is added to
the report, because Kennzahlen can change.

How receipt categories map to Kennzahlen is a classification choice (``_PURCHASE_KZ``,
``_PURCHASE_SUB_KZ``, ``_sale_kz``). Receipts that need a human decision are not guessed:
they go to ``EURReport.review_lines`` with a reason and are **not** part of the profit.

Known gaps (see docs/TODO.md):
  - EUR-2: VAT is excluded from the profit (net method). The official form counts collected
    VAT (Kz 140), refunds (Kz 141), Vorsteuer paid (Kz 185) and VAT paid to the Finanzamt
    (Kz 186). There is no Kleinunternehmer mode (Kz 111).
  - EUR-3: assets above the GWG limit need depreciation (AfA, Anlage AVEÜR) and are sent to review.

Usage::

    from finamt.storage import get_repository
    from finamt.tax.eur import generate_eur

    with get_repository() as repo:
        receipts = repo.find_by_period(date(2025, 1, 1), date(2025, 12, 31))
    report = generate_eur(receipts, 2025)
    print(report.summary())
    report.to_json("eur_2025.json")
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from ..models import ReceiptData

_TWO = Decimal("0.01")

#: Anlage EÜR version the Kennzahlen below were verified against (docs/tax-rules.md).
FORM_YEAR = 2025

#: § 6 Abs. 2 S. 1 EStG: movable assets up to this net amount may be expensed at once (GWG).
GWG_LIMIT = Decimal("800")

#: Kennzahl used for receipts that need a manual decision (not part of the profit).
REVIEW = "review"


def _r(d: Decimal) -> Decimal:
    return d.quantize(_TWO, rounding=ROUND_HALF_UP)


def _to_date(dt: date | datetime) -> date:
    return dt.date() if isinstance(dt, datetime) else dt


# ---------------------------------------------------------------------------
# Anlage EÜR 2025 Kennzahlen used by this module (labels shortened from the form)
# ---------------------------------------------------------------------------

KZ_LABELS: dict[str, str] = {
    # Betriebseinnahmen
    "112": "Umsatzsteuerpflichtige Betriebseinnahmen",
    "103": "USt-freie / nicht steuerbare Betriebseinnahmen",
    "102": "Veräußerung oder Entnahme von Anlagevermögen",
    # Betriebsausgaben
    "100": "Waren, Rohstoffe und Hilfsstoffe",
    "110": "Bezogene Fremdleistungen",
    "132": "Geringwertige Wirtschaftsgüter (§ 6 Abs. 2 EStG)",
    "150": "Miete/Pacht für Geschäftsräume",
    "151": "Sonstige Aufwendungen für betriebliche Grundstücke",
    "280": "Aufwendungen für Telekommunikation",
    "221": "Übernachtungs- und Reisenebenkosten",
    "281": "Fortbildungskosten",
    "194": "Rechts- und Steuerberatung, Buchführung",
    "223": "Beiträge, Gebühren, Abgaben, Versicherungen",
    "228": "Laufende EDV-Kosten",
    "229": "Arbeitsmittel",
    "227": "Kosten für Verpackung und Transport",
    "224": "Werbekosten",
    "234": "Übrige Schuldzinsen",
    "144": "Kfz: Leasingkosten",
    "145": "Kfz: Steuern, Versicherungen und Maut",
    "146": "Sonstige tatsächliche Fahrtkosten",
    "183": "Übrige unbeschränkt abziehbare Betriebsausgaben",
}

# Purchases: category → Kennzahl (default for the category).
_PURCHASE_KZ: dict[str, str] = {
    "material": "100",
    "products": "100",
    "services": "110",
    "equipment": "132",  # only up to GWG_LIMIT, see _purchase_kz
    "software": "228",
    "licensing": "183",
    "telecommunication": "280",
    "travel": "221",
    "car": "146",
    "education": "281",
    "utilities": "151",
    "insurance": "223",
    "financial": "183",
    "office": "150",
    "marketing": "224",
    "public_fees": "223",
    "other": "183",
}

# Purchases: (category, subcategory) → Kennzahl, overriding the category default.
_PURCHASE_SUB_KZ: dict[tuple[str, str], str] = {
    ("services", "legal"): "194",
    ("services", "accounting"): "194",
    ("services", "notary"): "194",
    ("material", "consumables"): "229",
    ("material", "packaging"): "227",
    ("education", "books"): "229",
    ("travel", "transport"): "146",
    ("car", "leasing"): "144",
    ("car", "insurance"): "145",
    ("insurance", "vehicle"): "145",
    ("insurance", "property"): "151",
    ("financial", "interest"): "234",
    ("financial", "loan_costs"): "234",
    ("office", "cleaning"): "151",
    ("office", "security"): "151",
    ("other", "membership_fees"): "223",
}

# Receipts that need a manual decision. Key: (category, subcategory or None for all).
_PURCHASE_REVIEW: dict[tuple[str, str | None], str] = {
    ("travel", "meals"): "Verpflegung: nur Verpflegungsmehraufwand als Pauschale (Kz 171)",
    ("travel", "per_diem"): "Verpflegungsmehraufwand (Kz 171): Pauschale manuell eintragen",
    ("marketing", "gifts"): "Geschenke: abziehbar / nicht abziehbar (Kz 174 / 164) prüfen",
    ("insurance", "health"): "Kranken-/Pflegeversicherung: betrieblich veranlasst? prüfen",
    ("donations", None): "Spenden: keine Zuordnung in der Anlage EÜR, manuell prüfen",
    ("tax_settlement", None): "Steuerzahlung: USt an das Finanzamt → Kz 186 (EUR-2)",
    ("capital_movement", None): "Einlage / Entnahme / Darlehen: kein Betriebsvorgang",
}

_SALE_REVIEW: dict[str, str] = {
    "tax_settlement": "Steuererstattung: USt-Erstattung → Kz 141 (EUR-2)",
    "capital_movement": "Einlage / Darlehen: keine Betriebseinnahme",
}

_ASSET_REVIEW_REASON = (
    "Anlagegut über 800 € netto: Abschreibung (AfA, Anlage AVEÜR) oder Sammelposten (EUR-3)"
)
_UNKNOWN_VAT_REASON = "USt-Status unbekannt: steuerpflichtig (Kz 112) oder steuerfrei (Kz 103)?"


def _purchase_kz(cat: str, sub: str | None, net: Decimal) -> tuple[str, str]:
    """Return (kennzahl, review_reason) for a purchase."""
    reason = _PURCHASE_REVIEW.get((cat, sub)) or _PURCHASE_REVIEW.get((cat, None))
    if reason:
        return REVIEW, reason
    if cat == "equipment" and net > GWG_LIMIT:
        return REVIEW, _ASSET_REVIEW_REASON
    if sub and (cat, sub) in _PURCHASE_SUB_KZ:
        return _PURCHASE_SUB_KZ[(cat, sub)], ""
    return _PURCHASE_KZ.get(cat, "183"), ""


def _sale_kz(r: ReceiptData, cat: str) -> tuple[str, str]:
    """Return (kennzahl, review_reason) for a sale (Regelbesteuerung)."""
    if cat in _SALE_REVIEW:
        return REVIEW, _SALE_REVIEW[cat]
    if cat == "equipment":
        return "102", ""
    vat, pct = r.vat_amount, r.vat_percentage
    if (vat is not None and vat != 0) or (pct is not None and pct > 0):
        return "112", ""
    if vat is not None or pct is not None:  # explicitly 0 %
        return "103", ""
    return REVIEW, _UNKNOWN_VAT_REASON


# ---------------------------------------------------------------------------
# Per-line aggregate
# ---------------------------------------------------------------------------


@dataclass
class EURLinie:
    """Aggregated figures for one category (or category + subcategory) on one Kennzahl."""

    category: str
    kz: str  # Anlage EÜR Kennzahl, or REVIEW
    label: str
    net_amount: Decimal = field(default_factory=Decimal)
    vat_amount: Decimal = field(default_factory=Decimal)
    gross_amount: Decimal = field(default_factory=Decimal)
    count: int = 0
    reason: str = ""  # why a REVIEW line needs a manual decision

    def to_dict(self) -> dict:
        d = {
            "category": self.category,
            "kz": self.kz,
            "label": self.label,
            "net_amount": str(self.net_amount),
            "vat_amount": str(self.vat_amount),
            "gross_amount": str(self.gross_amount),
            "count": self.count,
        }
        if self.reason:
            d["reason"] = self.reason
        return d


# ---------------------------------------------------------------------------
# EÜR Report
# ---------------------------------------------------------------------------


@dataclass
class EURReport:
    """
    Einnahmen-Überschuss-Rechnung for one fiscal year.

    ``gewinn > 0``  → profit, ``gewinn < 0`` → loss.
    ``review_lines`` are excluded from all totals until a human decides.
    """

    year: int
    einnahmen_lines: dict[str, EURLinie] = field(default_factory=dict)
    ausgaben_lines: dict[str, EURLinie] = field(default_factory=dict)
    review_lines: dict[str, EURLinie] = field(default_factory=dict)
    skipped_count: int = 0
    form_year: int = FORM_YEAR
    warnings: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Aggregated totals
    # ------------------------------------------------------------------

    @property
    def total_einnahmen_netto(self) -> Decimal:
        """Total net revenue (excl. VAT charged to clients)."""
        return sum((ln.net_amount for ln in self.einnahmen_lines.values()), Decimal("0"))

    @property
    def total_einnahmen_ust(self) -> Decimal:
        """Total VAT collected from clients (Umsatzsteuer-Einnahme)."""
        return sum((ln.vat_amount for ln in self.einnahmen_lines.values()), Decimal("0"))

    @property
    def total_ausgaben_netto(self) -> Decimal:
        """Total net expenses (excl. VAT paid to vendors, claimable as Vorsteuer)."""
        return sum((ln.net_amount for ln in self.ausgaben_lines.values()), Decimal("0"))

    @property
    def total_ausgaben_vorsteuer(self) -> Decimal:
        """Total VAT paid on purchases (Vorsteuer — claimable separately via UStVA)."""
        return sum((ln.vat_amount for ln in self.ausgaben_lines.values()), Decimal("0"))

    @property
    def total_review_netto(self) -> Decimal:
        """Net total of receipts waiting for a manual decision (not in the profit)."""
        return sum((ln.net_amount for ln in self.review_lines.values()), Decimal("0"))

    @property
    def gewinn(self) -> Decimal:
        """
        Betriebsgewinn / -verlust (§ 4 Abs. 3 EStG) = net revenue − net expenses.

        VAT is excluded (net method). The official form includes it (Kz 140/141/185/186);
        that is task EUR-2 in docs/TODO.md.
        """
        return _r(self.total_einnahmen_netto - self.total_ausgaben_netto)

    # ------------------------------------------------------------------
    # Anlage EÜR aggregated by Kennzahl
    # ------------------------------------------------------------------

    def kz_totals(self) -> dict[str, Decimal]:
        """Net amounts aggregated by Kennzahl — for populating the official form."""
        totals: dict[str, Decimal] = {}
        for ln in (*self.einnahmen_lines.values(), *self.ausgaben_lines.values()):
            totals[ln.kz] = totals.get(ln.kz, Decimal("0")) + ln.net_amount
        return {k: _r(v) for k, v in sorted(totals.items())}

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "year": self.year,
            "form_year": self.form_year,
            "skipped_count": self.skipped_count,
            "warnings": list(self.warnings),
            "total_einnahmen_netto": str(self.total_einnahmen_netto),
            "total_einnahmen_ust": str(self.total_einnahmen_ust),
            "total_ausgaben_netto": str(self.total_ausgaben_netto),
            "total_ausgaben_vorsteuer": str(self.total_ausgaben_vorsteuer),
            "total_review_netto": str(self.total_review_netto),
            "gewinn": str(self.gewinn),
            "kz_totals": {k: str(v) for k, v in self.kz_totals().items()},
            "einnahmen": {k: v.to_dict() for k, v in self.einnahmen_lines.items()},
            "ausgaben": {k: v.to_dict() for k, v in self.ausgaben_lines.items()},
            "review": {k: v.to_dict() for k, v in self.review_lines.items()},
        }

    def to_json(self, path: str | Path | None = None) -> str:
        raw = json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        if path:
            Path(path).write_text(raw, encoding="utf-8")
        return raw

    def summary(self) -> str:
        W = 80
        div = "─" * W

        def fmt(label: str, amount: Decimal, indent: int = 2) -> str:
            pad = " " * indent
            return f"{pad}{label:<62} {amount:>10.2f} EUR"

        lines = [
            "=" * W,
            f"  Einnahmen-Überschuss-Rechnung — {self.year}",
            f"  (§ 4 Abs. 3 EStG, Kennzahlen Anlage EÜR {self.form_year})",
            "=" * W,
            f"  Übersprungene Belege: {self.skipped_count}",
        ]
        lines += [f"  ⚠  {w}" for w in self.warnings]
        lines += [div, "  BETRIEBSEINNAHMEN", div]
        for ln in sorted(self.einnahmen_lines.values(), key=lambda x: x.kz):
            lines.append(fmt(f"Kz {ln.kz}  {ln.label[:46]} ({ln.count})", ln.net_amount))
        lines += [
            fmt("Summe Betriebseinnahmen (netto)", self.total_einnahmen_netto),
            div,
            "  BETRIEBSAUSGABEN",
            div,
        ]
        for ln in sorted(self.ausgaben_lines.values(), key=lambda x: x.kz):
            lines.append(fmt(f"Kz {ln.kz}  {ln.label[:46]} ({ln.count})", ln.net_amount))
        lines += [
            fmt("Summe Betriebsausgaben (netto)", self.total_ausgaben_netto),
            "═" * W,
        ]

        if self.gewinn >= 0:
            lines.append(fmt("GEWINN (§ 4 Abs. 3 EStG)", self.gewinn))
        else:
            lines.append(fmt("VERLUST (§ 4 Abs. 3 EStG)", self.gewinn))

        if self.review_lines:
            lines += [div, "  ZU PRÜFEN (nicht im Gewinn enthalten)", div]
            for key, ln in sorted(self.review_lines.items()):
                lines.append(fmt(f"{key} ({ln.count})", ln.net_amount))
                lines.append(f"      → {ln.reason}")

        lines += [
            div,
            fmt("Vorsteuer gezahlt (→ UStVA Kz 66)", self.total_ausgaben_vorsteuer),
            fmt("Umsatzsteuer eingenommen (→ UStVA)", self.total_einnahmen_ust),
            "=" * W,
            "  ⚠  USt ist nicht im Gewinn enthalten (Nettomethode, siehe docs/TODO.md EUR-2).",
            "     Vor Abgabe mit der amtlichen Anlage EÜR abgleichen.",
            "=" * W,
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def _add(lines: dict[str, EURLinie], key: str, cat: str, kz: str, reason: str) -> EURLinie:
    if key not in lines:
        label = "Manuelle Prüfung" if kz == REVIEW else KZ_LABELS[kz]
        lines[key] = EURLinie(category=cat, kz=kz, label=label, reason=reason)
    return lines[key]


def generate_eur(
    receipts: Iterable[ReceiptData],
    year: int,
) -> EURReport:
    """
    Compute the EÜR figures from an iterable of receipts for a full fiscal year.

    Skips receipts that have no ``receipt_date``, fall outside the calendar year, or
    have no (or a zero) ``total_amount``.

    Line keys: the category name when the receipt uses the category's default Kennzahl,
    otherwise ``"<category>:<kz>"`` (e.g. ``"travel:146"``). Review lines use
    ``"<category>"`` or ``"<category>/<subcategory>"``.

    VAT: net amounts are used (VAT flows through UStVA). Kleinunternehmer (§ 19 UStG) are
    not supported yet (EUR-2): their purchase VAT would have to be an expense.
    """
    report = EURReport(year=year)
    if year != FORM_YEAR:
        report.warnings.append(
            f"Kennzahlen sind für die Anlage EÜR {FORM_YEAR} geprüft, nicht für {year}."
        )
    period_start = date(year, 1, 1)
    period_end = date(year, 12, 31)

    for r in receipts:
        if r.receipt_date is None:
            report.skipped_count += 1
            continue
        d = _to_date(r.receipt_date)
        if not (period_start <= d <= period_end):
            report.skipped_count += 1
            continue
        if not r.total_amount:
            report.skipped_count += 1
            continue

        cat = str(r.category) if r.category else "other"
        sub = str(r.subcategory).strip().lower() if r.subcategory else None
        net = _r(r.business_net if r.business_net is not None else (r.net_amount or Decimal("0")))
        vat = _r(r.business_vat if r.business_vat is not None else (r.vat_amount or Decimal("0")))
        gross = _r(net + vat)

        if r.is_purchase:
            full_net = r.net_amount if r.net_amount is not None else r.total_amount
            kz, reason = _purchase_kz(cat, sub, full_net)
            default_kz = _PURCHASE_KZ.get(cat, "183")
            lines = report.ausgaben_lines
        else:
            kz, reason = _sale_kz(r, cat)
            default_kz = "102" if cat == "equipment" else "112"
            lines = report.einnahmen_lines

        if kz == REVIEW:
            key = f"{cat}/{sub}" if sub and (cat, sub) in _PURCHASE_REVIEW else cat
            ln = _add(report.review_lines, key, cat, kz, reason)
        else:
            key = cat if kz == default_kz else f"{cat}:{kz}"
            ln = _add(lines, key, cat, kz, reason)
        ln.net_amount += net
        ln.vat_amount += vat
        ln.gross_amount += gross
        ln.count += 1

    # Final rounding pass
    for ln in (
        *report.einnahmen_lines.values(),
        *report.ausgaben_lines.values(),
        *report.review_lines.values(),
    ):
        ln.net_amount = _r(ln.net_amount)
        ln.vat_amount = _r(ln.vat_amount)
        ln.gross_amount = _r(ln.gross_amount)

    return report
