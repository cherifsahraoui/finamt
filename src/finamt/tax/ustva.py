"""
finamt.tax.ustva
~~~~~~~~~~~~~~~~~~~
Umsatzsteuer-Voranmeldung (UStVA) — German VAT pre-return.

VAT flow
--------
Purchase invoices (Eingangsrechnung)
    You paid a vendor.  Their VAT charge = your Vorsteuer (input tax).
    You reclaim this from the Finamt.

Sales invoices (Ausgangsrechnung)
    You invoiced a client.  You charged VAT = Umsatzsteuer (output tax).
    You remit this to the Finanzamt.

Net UStVA liability = output_tax − input_tax
  > 0  → you owe the state
  < 0  → state owes you a refund (Erstattung)
  = 0  → break-even

Usage::

    from finamt.storage import get_repository
    from finamt.tax.ustva import generate_ustva

    with get_repository() as repo:
        receipts = repo.find_by_period(date(2024,1,1), date(2024,3,31))
    report = generate_ustva(receipts, date(2024,1,1), date(2024,3,31))
    print(report.summary())
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


def _r(d: Decimal) -> Decimal:
    return d.quantize(_TWO, rounding=ROUND_HALF_UP)


def _to_date(dt: date | datetime) -> date:
    return dt.date() if isinstance(dt, datetime) else dt


# Prefixes of EU VAT identification numbers (Greece: "EL"). Source: European Commission,
# "Annex 2: VAT identification number" (2014), without "GB" (no longer an EU member state).
# "XI" (Northern Ireland) is not in the list, so it counts as non-EU here.
# See docs/tax-rules.md row "EU VAT ID prefixes".
EU_VAT_PREFIXES: frozenset[str] = frozenset(
    "AT BE BG CY CZ DE DK EE EL ES FI FR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK".split()
)
# ISO country codes of the same states (Greece is "GR" as a country code).
_EU_COUNTRY_CODES = (EU_VAT_PREFIXES - {"EL"}) | {"GR"}
_GERMANY_NAMES = {"DE", "DEU", "DEUTSCHLAND", "GERMANY"}

# Default rate for § 13b purchases when the receipt names none (§ 12 Abs. 1 UStG).
_RC_DEFAULT_RATE = Decimal("19")


def counterparty_region(r: ReceiptData) -> str | None:
    """Return "DE", "EU" (other member state), "NON_EU" or None (unknown).

    Uses the counterparty's VAT ID prefix first, then a two-letter country code
    (or "Deutschland"/"Germany") in its address. Anything else is unknown: the
    caller must not guess.
    """
    cp = r.counterparty
    if cp is None:
        return None
    vat_id = (cp.vat_id or "").replace(" ", "").upper()
    if len(vat_id) >= 4 and vat_id[:2].isalpha():
        prefix = vat_id[:2]
        if prefix == "DE":
            return "DE"
        return "EU" if prefix in EU_VAT_PREFIXES else "NON_EU"
    country = ((cp.address.country if cp.address else None) or "").strip().upper()
    if country in _GERMANY_NAMES:
        return "DE"
    if len(country) == 2 and country.isalpha():
        return "EU" if country in _EU_COUNTRY_CODES else "NON_EU"
    return None


# ---------------------------------------------------------------------------
# Per-rate line
# ---------------------------------------------------------------------------


@dataclass
class USTVALineItem:
    """Aggregated figures for one VAT rate, split by receipt type."""

    vat_rate: Decimal
    # Purchase side (Vorsteuer — input tax you reclaim)
    purchase_net: Decimal = field(default_factory=Decimal)
    purchase_vat: Decimal = field(default_factory=Decimal)
    purchase_count: int = 0
    # Sale side (Umsatzsteuer — output tax you remit)
    sale_net: Decimal = field(default_factory=Decimal)
    sale_vat: Decimal = field(default_factory=Decimal)
    sale_count: int = 0

    @property
    def net_liability(self) -> Decimal:
        """Output VAT − input VAT for this rate. Positive = you owe."""
        return self.sale_vat - self.purchase_vat

    def to_dict(self) -> dict:
        return {
            "vat_rate": str(self.vat_rate),
            "purchase_net": str(self.purchase_net),
            "purchase_vat": str(self.purchase_vat),
            "purchase_count": self.purchase_count,
            "sale_net": str(self.sale_net),
            "sale_vat": str(self.sale_vat),
            "sale_count": self.sale_count,
            "net_liability": str(self.net_liability),
        }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass
class USTVAReport:
    """
    UStVA summary for a reporting period.

    ``net_liability > 0``  → you owe the Finanzamt
    ``net_liability < 0``  → the Finanzamt owes you (Erstattung)
    """

    period_start: date
    period_end: date
    lines: dict[str, USTVALineItem] = field(default_factory=dict)
    skipped_count: int = 0
    # Einfuhrumsatzsteuer (§ 15 Abs. 1 Satz 1 Nr. 2 UStG) — import VAT assessed
    # by customs; tracked separately for ELSTER line 62 (pre-return) / 124 (annual).
    einfuhr_vat: Decimal = field(default_factory=Decimal)

    # Receipts without German VAT, by ``ReceiptData.vat_treatment`` (UST-3, UST-4).
    # Bases are net amounts; see docs/tax-rules.md for each Kennzahl.
    zero_rate_net: Decimal = field(default_factory=Decimal)  # Kz 87 (§ 12 Abs. 3)
    tax_free_net: Decimal = field(default_factory=Decimal)  # Kz 48
    rc_eu_sales_net: Decimal = field(default_factory=Decimal)  # Kz 21 (§ 18b S. 1 Nr. 2)
    rc_domestic_sales_net: Decimal = field(default_factory=Decimal)  # Kz 60 (§ 13b Abs. 5)
    non_eu_sales_net: Decimal = field(default_factory=Decimal)  # Kz 45
    rc_eu_purchase_net: Decimal = field(default_factory=Decimal)  # Kz 46 (§ 13b Abs. 1)
    rc_eu_purchase_vat: Decimal = field(default_factory=Decimal)  # Kz 47
    rc_other_purchase_net: Decimal = field(default_factory=Decimal)  # Kz 84 (§ 13b Abs. 2)
    rc_other_purchase_vat: Decimal = field(default_factory=Decimal)  # Kz 85
    rc_input_vat: Decimal = field(default_factory=Decimal)  # Kz 67 (business share)
    # Receipts that could not be reported, with the reason (never silently dropped).
    warnings: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Aggregated totals
    # ------------------------------------------------------------------

    @property
    def total_input_vat(self) -> Decimal:
        """Total Vorsteuer: invoices (Kz 66) + Einfuhrumsatzsteuer (Kz 62) + § 13b (Kz 67)."""
        return (
            sum((ln.purchase_vat for ln in self.lines.values()), Decimal("0"))
            + self.einfuhr_vat
            + self.rc_input_vat
        )

    @property
    def total_output_vat(self) -> Decimal:
        """Total Umsatzsteuer: sales at all rates + tax owed as recipient (§ 13b, Kz 47/85)."""
        return (
            sum((ln.sale_vat for ln in self.lines.values()), Decimal("0"))
            + self.rc_eu_purchase_vat
            + self.rc_other_purchase_vat
        )

    @property
    def has_special_vat(self) -> bool:
        """True when any 0 %, tax-free or reverse-charge amount is present (UST-3/UST-4)."""
        return any(
            v != 0
            for v in (
                self.zero_rate_net,
                self.tax_free_net,
                self.rc_eu_sales_net,
                self.rc_domestic_sales_net,
                self.non_eu_sales_net,
                self.rc_eu_purchase_net,
                self.rc_other_purchase_net,
            )
        )

    @property
    def net_liability(self) -> Decimal:
        """output − input. Positive = you owe; negative = refund."""
        return self.total_output_vat - self.total_input_vat

    @property
    def total_purchase_net(self) -> Decimal:
        return sum((ln.purchase_net for ln in self.lines.values()), Decimal("0"))

    @property
    def total_sale_net(self) -> Decimal:
        return sum((ln.sale_net for ln in self.lines.values()), Decimal("0"))

    @property
    def total_receipts(self) -> int:
        return sum(ln.purchase_count + ln.sale_count for ln in self.lines.values())

    # Convenience accessors
    @property
    def line_19(self) -> USTVALineItem | None:
        return self.lines.get("19")

    @property
    def line_7(self) -> USTVALineItem | None:
        return self.lines.get("7")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_receipts": self.total_receipts,
            "skipped_count": self.skipped_count,
            "total_purchase_net": str(self.total_purchase_net),
            "total_input_vat": str(self.total_input_vat),
            "einfuhr_vat": str(self.einfuhr_vat),
            "total_sale_net": str(self.total_sale_net),
            "total_output_vat": str(self.total_output_vat),
            "net_liability": str(self.net_liability),
            "lines": {k: v.to_dict() for k, v in sorted(self.lines.items())},
            "zero_rate_net": str(self.zero_rate_net),
            "tax_free_net": str(self.tax_free_net),
            "rc_eu_sales_net": str(self.rc_eu_sales_net),
            "rc_domestic_sales_net": str(self.rc_domestic_sales_net),
            "non_eu_sales_net": str(self.non_eu_sales_net),
            "rc_eu_purchase_net": str(self.rc_eu_purchase_net),
            "rc_eu_purchase_vat": str(self.rc_eu_purchase_vat),
            "rc_other_purchase_net": str(self.rc_other_purchase_net),
            "rc_other_purchase_vat": str(self.rc_other_purchase_vat),
            "rc_input_vat": str(self.rc_input_vat),
            "warnings": list(self.warnings),
        }

    def to_json(self, path: str | Path | None = None) -> str:
        raw = json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        if path:
            Path(path).write_text(raw, encoding="utf-8")
        return raw

    def summary(self) -> str:
        W = 52
        div = "─" * W
        hdiv = "═" * W

        def owe_str() -> str:
            if self.net_liability > 0:
                return f"{self.net_liability:>10.2f} EUR  ← you owe the Finanzamt"
            elif self.net_liability < 0:
                return f"{abs(self.net_liability):>10.2f} EUR  ← Finanzamt owes you (Erstattung)"
            return "             0.00 EUR  (break-even)"

        lines = [
            "=" * W,
            f"  UStVA — {self.period_start} bis {self.period_end}",
            "=" * W,
            f"  Belege gesamt       : {self.total_receipts}",
            f"  Übersprungen        : {self.skipped_count}",
        ]

        if self.lines:
            lines.append(div)
            for _rate_key, ln in sorted(self.lines.items()):
                lines += [
                    f"  USt-Satz {ln.vat_rate} %",
                    "    Einkauf (Vorsteuer)",
                    f"      Nettobetrag    : {ln.purchase_net:>10.2f} EUR  ({ln.purchase_count} Belege)",
                    f"      Vorsteuer      : {ln.purchase_vat:>10.2f} EUR",
                    "    Verkauf (Umsatzsteuer)",
                    f"      Nettobetrag    : {ln.sale_net:>10.2f} EUR  ({ln.sale_count} Belege)",
                    f"      Umsatzsteuer   : {ln.sale_vat:>10.2f} EUR",
                    f"      Saldo          : {ln.net_liability:>+10.2f} EUR",
                ]

        special = [
            ("0 %-Umsätze (Kz 87)", self.zero_rate_net),
            ("Steuerfreie Umsätze (Kz 48)", self.tax_free_net),
            ("EU-Leistungen § 18b (Kz 21)", self.rc_eu_sales_net),
            ("§ 13b Abs. 5, Empfänger schuldet (Kz 60)", self.rc_domestic_sales_net),
            ("Nicht steuerbar, Drittland (Kz 45)", self.non_eu_sales_net),
            ("§ 13b Abs. 1 Einkauf netto (Kz 46)", self.rc_eu_purchase_net),
            ("§ 13b Abs. 1 Steuer (Kz 47)", self.rc_eu_purchase_vat),
            ("§ 13b Abs. 2 Einkauf netto (Kz 84)", self.rc_other_purchase_net),
            ("§ 13b Abs. 2 Steuer (Kz 85)", self.rc_other_purchase_vat),
            ("Vorsteuer § 13b (Kz 67)", self.rc_input_vat),
        ]
        shown = [(label, v) for label, v in special if v != 0]
        if shown:
            lines.append(div)
            lines += [f"  {label:<42}: {v:>10.2f} EUR" for label, v in shown]
        if self.warnings:
            lines.append(div)
            lines += [f"  ! {w}" for w in self.warnings]

        lines += [hdiv]
        if self.einfuhr_vat > 0:
            lines += [
                f"  Einfuhrumsatzsteuer : {self.einfuhr_vat:>10.2f} EUR  (\u00a7 15 Abs. 1 Nr. 2)",
            ]
        lines += [
            f"  Gesamt Vorsteuer    : {self.total_input_vat:>10.2f} EUR",
            f"  Gesamt Umsatzsteuer : {self.total_output_vat:>10.2f} EUR",
            hdiv,
            f"  Zahllast / Erstatt. : {owe_str()}",
            "=" * W,
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def generate_ustva(
    receipts: Iterable[ReceiptData],
    period_start: date,
    period_end: date,
) -> USTVAReport:
    """
    Compute the UStVA figures from an iterable of receipts.

    Skips receipts that:
    - have no ``receipt_date``
    - fall outside the period
    - have no VAT amount at all (``vat_amount`` zero or missing, and no ``einfuhr_vat``)

    Credit notes (negative ``vat_amount``) are kept: changes under § 17 Abs. 1 UStG go
    into the base and tax lines of their rate as negative amounts, in the period of the
    change (USt1A-2026 Anleitung, see docs/tax-rules.md row "Kz 50 / Kz 37").

    Receipts without German VAT are reported only when ``vat_treatment`` says why
    (UST-3, UST-4); see ``_add_special``. A 0 % sale without a reason adds a warning.
    """
    report = USTVAReport(period_start=period_start, period_end=period_end)
    start = _to_date(period_start)
    end = _to_date(period_end)

    for r in receipts:
        if r.receipt_date is None:
            report.skipped_count += 1
            continue
        if not (start <= _to_date(r.receipt_date) <= end):
            report.skipped_count += 1
            continue

        if getattr(r, "vat_treatment", None):
            _add_special(report, r)
            continue

        has_vat = bool(r.vat_amount and r.vat_amount != 0)
        ev = getattr(r, "einfuhr_vat", None)
        has_einfuhr = bool(r.is_purchase and ev and ev > 0)

        if not has_vat and not has_einfuhr:
            report.skipped_count += 1
            if r.is_sale and r.total_amount:
                report.warnings.append(
                    f"Ausgangsbeleg {_label(r)} ohne USt und ohne Grund (0 %, steuerfrei, "
                    "Reverse Charge): nicht gemeldet."
                )
            continue

        # Einfuhrumsatzsteuer — track at report level (not per-rate line)
        if has_einfuhr:
            report.einfuhr_vat += _r(ev)

        # Per-rate regular VAT lines
        if not has_vat:
            continue

        # Mixed-rate receipt: one line per split (CLN-3)
        if r.vat_percentage is None and getattr(r, "vat_splits", None):
            if _add_splits(report, r):
                continue

        # Rate key
        rate_key = _rate_key(r.vat_percentage) if r.vat_percentage else "unknown"
        if rate_key == "unknown":
            report.warnings.append(
                f"Beleg {_label(r)} ohne USt-Satz: "
                + (
                    "Umsatz in keiner Bemessungsgrundlage (Kz 81/86/35) gemeldet."
                    if r.is_sale
                    else "Vorsteuer in Kz 66 gemeldet; Satz bitte prüfen."
                )
            )
        if rate_key not in report.lines:
            report.lines[rate_key] = USTVALineItem(
                vat_rate=r.vat_percentage.normalize() if r.vat_percentage else Decimal("0")
            )

        ln = report.lines[rate_key]

        if r.is_purchase:
            # Only the *business* portion is tax-deductible.
            # business_vat / business_net already apply (1 - private_use_share).
            vat = _r(r.business_vat if r.business_vat is not None else r.vat_amount)
            net = _r(
                r.business_net if r.business_net is not None else (r.net_amount or Decimal("0"))
            )
            ln.purchase_vat += vat
            ln.purchase_net += net
            ln.purchase_count += 1
        else:  # sale — private_use_share does not reduce output VAT
            vat = _r(r.vat_amount)
            net = _r(r.net_amount or Decimal("0"))
            ln.sale_vat += vat
            ln.sale_net += net
            ln.sale_count += 1

    # Final rounding pass
    for name in (
        "zero_rate_net",
        "tax_free_net",
        "rc_eu_sales_net",
        "rc_domestic_sales_net",
        "non_eu_sales_net",
        "rc_eu_purchase_net",
        "rc_eu_purchase_vat",
        "rc_other_purchase_net",
        "rc_other_purchase_vat",
        "rc_input_vat",
    ):
        setattr(report, name, _r(getattr(report, name)))
    for ln in report.lines.values():
        ln.purchase_vat = _r(ln.purchase_vat)
        ln.purchase_net = _r(ln.purchase_net)
        ln.sale_vat = _r(ln.sale_vat)
        ln.sale_net = _r(ln.sale_net)

    return report


def _label(r: ReceiptData) -> str:
    d = _to_date(r.receipt_date).isoformat() if r.receipt_date else "?"
    return " ".join(x for x in (d, r.vendor or "", f"{r.total_amount} €") if x)


def _add_special(report: USTVAReport, r: ReceiptData) -> None:
    """Book a receipt whose ``vat_treatment`` is set (no German VAT on the invoice).

    The base is the invoice amount (``total_amount``): such an invoice shows no VAT.
    A receipt that does show VAT contradicts its treatment and is not reported.
    """
    treatment = r.vat_treatment
    if r.vat_amount:
        report.skipped_count += 1
        report.warnings.append(
            f"Beleg {_label(r)}: '{treatment}' gesetzt, aber USt {r.vat_amount} € "
            "ausgewiesen; nicht gemeldet."
        )
        return
    base = _r(r.total_amount or Decimal("0"))
    if base == 0:
        report.skipped_count += 1
        return

    if r.is_sale:
        if treatment == "zero_rate":
            report.zero_rate_net += base
        elif treatment == "tax_free":
            report.tax_free_net += base
        else:  # reverse_charge: place of supply abroad, or § 13b Abs. 5 recipient in DE
            region = counterparty_region(r)
            if region == "EU":
                report.rc_eu_sales_net += base
            elif region == "DE":
                report.rc_domestic_sales_net += base
            elif region == "NON_EU":
                report.non_eu_sales_net += base
            else:
                report.skipped_count += 1
                report.warnings.append(
                    f"Reverse-Charge-Ausgangsbeleg {_label(r)} ohne USt-IdNr oder Land des "
                    "Kunden: Kz 21, 45 oder 60 unklar; nicht gemeldet."
                )
        return

    # purchase
    if treatment != "reverse_charge":
        # A 0 % / tax-free purchase has no input tax: nothing to report in the UStVA.
        report.skipped_count += 1
        return
    region = counterparty_region(r)
    if region is None:
        report.skipped_count += 1
        report.warnings.append(
            f"Reverse-Charge-Eingangsbeleg {_label(r)} ohne USt-IdNr oder Land des "
            "Lieferanten: Kz 46/47 oder 84/85 unklar; nicht gemeldet."
        )
        return
    rate = r.vat_percentage if r.vat_percentage and r.vat_percentage > 0 else _RC_DEFAULT_RATE
    tax = _r(base * rate / Decimal("100"))
    if region == "EU":
        report.rc_eu_purchase_net += base
        report.rc_eu_purchase_vat += tax
    else:  # DE (§ 13b Abs. 2 Nr. 4 ff.) or non-EU supplier (§ 13b Abs. 2 Nr. 1)
        report.rc_other_purchase_net += base
        report.rc_other_purchase_vat += tax
    # Input tax (§ 15 Abs. 1 S. 1 Nr. 4 UStG) only for the business share.
    share = Decimal("1") - Decimal(str(r.private_use_share or 0))
    report.rc_input_vat += _r(tax * share)


def _rate_key(rate: Decimal) -> str:
    """Line key of a VAT rate: "19", "7", "10" (never exponent notation like "1E+1")."""
    return f"{rate.normalize():f}"


def _dec(v) -> Decimal | None:
    return None if v is None or v == "" else Decimal(str(v))


def _add_splits(report: USTVAReport, r: ReceiptData) -> bool:
    """Add each ``vat_splits`` entry of a mixed-rate receipt to its rate line (CLN-3).

    Returns False (receipt not booked) when a split lacks its rate or VAT amount, so the
    caller falls back to the ``"unknown"`` line with a warning. A split without a net
    amount gets net = VAT × 100 / rate. Purchases count only their business share.
    """
    parsed = []
    for sp in r.vat_splits:
        rate, vat, net = (
            _dec(sp.get("vat_rate")),
            _dec(sp.get("vat_amount")),
            _dec(sp.get("net_amount")),
        )
        if rate is None or vat is None or (net is None and rate == 0):
            return False
        if net is None:
            net = vat * Decimal("100") / rate
        parsed.append((rate, vat, net))

    split_vat = sum((vat for _, vat, _ in parsed), Decimal("0"))
    if r.vat_amount is not None and abs(split_vat - r.vat_amount) > _TWO:
        report.warnings.append(
            f"Beleg {_label(r)}: USt der Aufteilung ({_r(split_vat)} €) weicht von der "
            f"Beleg-USt ({r.vat_amount} €) ab; Aufteilung verwendet."
        )

    share = Decimal("1")
    if r.is_purchase:
        share -= Decimal(str(r.private_use_share or 0))
    touched: set[str] = set()
    for rate, vat, net in parsed:
        key = _rate_key(rate)
        ln = report.lines.setdefault(key, USTVALineItem(vat_rate=rate.normalize()))
        if r.is_purchase:
            ln.purchase_vat += _r(vat * share)
            ln.purchase_net += _r(net * share)
            if not touched:  # count the receipt once (total_receipts)
                ln.purchase_count += 1
        else:
            ln.sale_vat += _r(vat)
            ln.sale_net += _r(net)
            if not touched:  # count the receipt once (total_receipts)
                ln.sale_count += 1
        touched.add(key)
    return True
