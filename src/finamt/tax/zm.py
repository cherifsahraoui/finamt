"""
finamt.tax.zm
~~~~~~~~~~~~~
Zusammenfassende Meldung (ZM, § 18a UStG) for a Freiberufler: B2B services under
§ 3a Abs. 2 UStG to businesses in other EU member states, where the recipient owes the
tax. These are the receipts that the UStVA reports in Kz 21 (``vat_treatment`` =
``"reverse_charge"`` and an EU, non-German customer).

The ZM is due by the 25th day after the end of each calendar quarter
(§ 18a Abs. 2 UStG, docs/tax-rules.md). Intra-EU supplies of goods (§ 18a Abs. 1, monthly)
are out of scope: FreiBuch has no goods flag.

Only the calculation lives here; the BZSt/ELSTER boundary (``zm_elster.py``) is a later task.

Usage::

    report = generate_zm(receipts, year=2026, quarter=1)
    print(report.summary())
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from ..models import ReceiptData
from .ustva import counterparty_region

_TWO = Decimal("0.01")

# § 18a Abs. 2 UStG: "bis zum 25. Tag nach Ablauf jedes Kalendervierteljahres".
# No shift for weekends or holidays is applied (not verified, see docs/tax-rules.md).
DUE_DAYS_AFTER_QUARTER = 25


def _r(d: Decimal) -> Decimal:
    return d.quantize(_TWO, rounding=ROUND_HALF_UP)


def _to_date(dt: date | datetime) -> date:
    return dt.date() if isinstance(dt, datetime) else dt


def quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    if quarter not in (1, 2, 3, 4):
        raise ValueError(f"quarter must be 1–4, got {quarter}")
    start = date(year, 3 * quarter - 2, 1)
    end = date(year + 1, 1, 1) if quarter == 4 else date(year, 3 * quarter + 1, 1)
    return start, end - timedelta(days=1)


def normalise_vat_id(vat_id: str) -> str:
    """Upper case, without spaces, dots and dashes ("fr 12-345" → "FR12345")."""
    return "".join(ch for ch in vat_id.upper() if ch.isalnum())


@dataclass
class ZMLine:
    """Sum of the services to one customer VAT ID in the quarter."""

    vat_id: str
    country: str  # the VAT ID prefix, e.g. "FR" (Greece: "EL")
    name: str
    amount: Decimal = field(default_factory=Decimal)
    count: int = 0

    def to_dict(self) -> dict:
        return {
            "vat_id": self.vat_id,
            "country": self.country,
            "name": self.name,
            "amount": str(self.amount),
            "count": self.count,
        }


@dataclass
class ZMReport:
    year: int
    quarter: int
    lines: dict[str, ZMLine] = field(default_factory=dict)
    # Receipts that belong in the ZM but cannot be reported (e.g. no VAT ID).
    errors: list[str] = field(default_factory=list)

    @property
    def period_start(self) -> date:
        return quarter_bounds(self.year, self.quarter)[0]

    @property
    def period_end(self) -> date:
        return quarter_bounds(self.year, self.quarter)[1]

    @property
    def due_date(self) -> date:
        return self.period_end + timedelta(days=DUE_DAYS_AFTER_QUARTER)

    @property
    def total(self) -> Decimal:
        return sum((ln.amount for ln in self.lines.values()), Decimal("0"))

    def to_dict(self) -> dict:
        return {
            "year": self.year,
            "quarter": self.quarter,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "due_date": self.due_date.isoformat(),
            "total": str(self.total),
            "lines": [ln.to_dict() for _, ln in sorted(self.lines.items())],
            "errors": list(self.errors),
        }

    def to_json(self, path: str | Path | None = None) -> str:
        raw = json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        if path:
            Path(path).write_text(raw, encoding="utf-8")
        return raw

    def summary(self) -> str:
        w = 60
        out = [
            "=" * w,
            f"  Zusammenfassende Meldung {self.year} Q{self.quarter}",
            f"  Zeitraum {self.period_start} bis {self.period_end}, fällig {self.due_date}",
            "=" * w,
        ]
        if not self.lines:
            out.append("  Keine sonstigen Leistungen an EU-Unternehmer.")
        for _, ln in sorted(self.lines.items()):
            out.append(f"  {ln.vat_id:<16} {ln.name[:24]:<24} {ln.amount:>12.2f} EUR")
        out.append("-" * w)
        out.append(f"  Summe{'':<36} {self.total:>12.2f} EUR")
        for e in self.errors:
            out.append(f"  ! {e}")
        out.append("=" * w)
        return "\n".join(out)


def generate_zm(receipts: Iterable[ReceiptData], year: int, quarter: int) -> ZMReport:
    """Sum the EU B2B services (Kz 21 receipts) per customer VAT ID for one quarter.

    Credit notes (negative ``total_amount``) reduce the sum of their VAT ID. A reverse-charge
    sale whose customer is in another EU member state by country but has no VAT ID becomes
    an error entry: each ZM line is keyed by the recipient's VAT ID.
    """
    report = ZMReport(year=year, quarter=quarter)
    start, end = report.period_start, report.period_end

    for r in receipts:
        if not r.is_sale or not r.reverse_charge or r.receipt_date is None:
            continue
        if not (start <= _to_date(r.receipt_date) <= end):
            continue
        if not r.total_amount:
            continue
        region = counterparty_region(r)
        if region in ("DE", "NON_EU"):
            continue  # Kz 60 / Kz 45 in the UStVA, not part of the ZM
        cp = r.counterparty
        vat_id = normalise_vat_id(cp.vat_id or "") if cp else ""
        label = f"{_to_date(r.receipt_date).isoformat()} {r.vendor or '?'} {r.total_amount} €"
        if region is None or not vat_id:
            report.errors.append(f"USt-IdNr des Kunden fehlt: {label}")
            continue
        ln = report.lines.get(vat_id)
        if ln is None:
            ln = report.lines[vat_id] = ZMLine(
                vat_id=vat_id, country=vat_id[:2], name=(cp.name or "") if cp else ""
            )
        ln.amount += _r(r.total_amount)
        ln.count += 1

    for ln in report.lines.values():
        ln.amount = _r(ln.amount)
    return report
