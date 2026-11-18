"""
tests/unit/test_eur_edge_cases.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Edge cases for finamt.tax.eur.generate_eur that test_eur.py does not cover:
zero totals, negative amounts (credit notes), mixed VAT rates, and
Kleinunternehmer-style input without VAT.

These tests pin current behaviour. They do not assert that the Kennzahl
mapping is legally correct (it is unverified, see docs/tax-rules.md).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import pytest

from finamt.models import Counterparty, ReceiptCategory, ReceiptData, ReceiptType
from finamt.tax.eur import generate_eur

YEAR = 2024


def _r(
    total: str | None,
    vat: str | None = None,
    *,
    pct: str | None = None,
    category: str = "software",
    receipt_type: str = "purchase",
    private_use_share: str = "0",
) -> ReceiptData:
    return ReceiptData(
        raw_text=f"edge {uuid.uuid4()}",
        receipt_type=ReceiptType(receipt_type),
        counterparty=Counterparty(name="Test"),
        receipt_date=datetime(YEAR, 5, 1),
        total_amount=Decimal(total) if total is not None else None,
        vat_amount=Decimal(vat) if vat is not None else None,
        vat_percentage=Decimal(pct) if pct is not None else None,
        category=ReceiptCategory(category),
        private_use_share=Decimal(private_use_share),
    )


# ---------------------------------------------------------------------------
# Zero totals
# ---------------------------------------------------------------------------


class TestZeroTotals:
    def test_zero_total_receipt_is_skipped(self):
        report = generate_eur([_r("0.00", "0.00")], YEAR)
        assert report.skipped_count == 1
        assert report.ausgaben_lines == {}

    def test_only_zero_receipts_gives_zero_report(self):
        report = generate_eur(
            [_r("0", "0"), _r("0", "0", category="services", receipt_type="sale")], YEAR
        )
        assert report.gewinn == Decimal("0")
        assert report.total_einnahmen_netto == Decimal("0")
        assert report.total_ausgaben_netto == Decimal("0")
        assert report.kz_totals() == {}

    def test_zero_vat_receipt_is_counted_at_gross(self):
        report = generate_eur([_r("50.00", "0.00", pct="0")], YEAR)
        ln = report.ausgaben_lines["software"]
        assert ln.net_amount == Decimal("50.00")
        assert ln.vat_amount == Decimal("0.00")
        assert ln.gross_amount == Decimal("50.00")

    def test_net_zero_after_credit_note(self):
        report = generate_eur([_r("119.00", "19.00"), _r("-119.00", "-19.00")], YEAR)
        ln = report.ausgaben_lines["software"]
        assert ln.net_amount == Decimal("0.00")
        assert ln.vat_amount == Decimal("0.00")
        assert ln.count == 2
        assert report.gewinn == Decimal("0.00")


# ---------------------------------------------------------------------------
# Negative amounts (Gutschrift / Stornorechnung)
# ---------------------------------------------------------------------------


class TestNegativeAmounts:
    def test_purchase_credit_note_reduces_expenses(self):
        report = generate_eur([_r("238.00", "38.00"), _r("-119.00", "-19.00")], YEAR)
        ln = report.ausgaben_lines["software"]
        assert ln.net_amount == Decimal("100.00")
        assert ln.vat_amount == Decimal("19.00")
        assert report.total_ausgaben_vorsteuer == Decimal("19.00")

    def test_sale_credit_note_reduces_income(self):
        report = generate_eur(
            [
                _r("1190.00", "190.00", category="services", receipt_type="sale"),
                _r("-595.00", "-95.00", category="services", receipt_type="sale"),
            ],
            YEAR,
        )
        assert report.total_einnahmen_netto == Decimal("500.00")
        assert report.total_einnahmen_ust == Decimal("95.00")
        assert report.gewinn == Decimal("500.00")

    def test_negative_with_rate_derives_net_from_rate(self):
        report = generate_eur([_r("-119.00", pct="19")], YEAR)
        ln = report.ausgaben_lines["software"]
        assert ln.net_amount == Decimal("-100.00")
        assert ln.vat_amount == Decimal("-19.00")
        assert ln.gross_amount == Decimal("-119.00")

    def test_credit_notes_exceeding_income_produce_loss(self):
        report = generate_eur(
            [
                _r("119.00", "19.00", category="services", receipt_type="sale"),
                _r("-238.00", "-38.00", category="services", receipt_type="sale"),
            ],
            YEAR,
        )
        assert report.gewinn == Decimal("-100.00")
        assert "VERLUST" in report.summary()


# ---------------------------------------------------------------------------
# Mixed VAT rates
# ---------------------------------------------------------------------------


class TestMixedVatRates:
    def test_19_and_7_percent_in_one_category(self):
        report = generate_eur(
            [
                _r("119.00", pct="19", category="services", receipt_type="sale"),
                _r("107.00", pct="7", category="services", receipt_type="sale"),
            ],
            YEAR,
        )
        ln = report.einnahmen_lines["services"]
        assert ln.net_amount == Decimal("200.00")
        assert ln.vat_amount == Decimal("26.00")
        assert ln.gross_amount == Decimal("226.00")

    def test_mixed_rate_single_receipt_without_rate_uses_vat_amount(self):
        # One receipt with 100 € @ 19 % + 100 € @ 7 %: total 226, VAT 26, no single rate.
        report = generate_eur([_r("226.00", "26.00", pct=None)], YEAR)
        ln = report.ausgaben_lines["software"]
        assert ln.net_amount == Decimal("200.00")
        assert ln.vat_amount == Decimal("26.00")

    def test_rate_and_zero_rate_across_categories(self):
        report = generate_eur(
            [
                _r("119.00", pct="19", category="software"),
                _r("50.00", "0.00", pct="0", category="insurance"),
            ],
            YEAR,
        )
        assert report.total_ausgaben_netto == Decimal("150.00")
        assert report.total_ausgaben_vorsteuer == Decimal("19.00")

    def test_rounding_per_receipt_then_sum(self):
        # 10.00 gross @ 19 % → net 8.40 (8.403...), VAT 1.60; three receipts → 25.20 / 4.80
        report = generate_eur([_r("10.00", pct="19") for _ in range(3)], YEAR)
        ln = report.ausgaben_lines["software"]
        assert ln.net_amount == Decimal("25.20")
        assert ln.vat_amount == Decimal("4.80")
        assert ln.gross_amount == Decimal("30.00")


# ---------------------------------------------------------------------------
# Kleinunternehmer-style input (no VAT lines)
# ---------------------------------------------------------------------------


class TestKleinunternehmer:
    @pytest.fixture
    def report(self):
        return generate_eur(
            [
                _r("1000.00", "0.00", pct="0", category="services", receipt_type="sale"),
                _r("200.00", "0.00", pct="0", category="software"),
                _r("50.00", None, pct="0", category="travel"),
            ],
            YEAR,
        )

    def test_no_vat_anywhere(self, report):
        assert report.total_einnahmen_ust == Decimal("0")
        assert report.total_ausgaben_vorsteuer == Decimal("0")
        for ln in (*report.einnahmen_lines.values(), *report.ausgaben_lines.values()):
            assert ln.vat_amount == Decimal("0")
            assert ln.net_amount == ln.gross_amount

    def test_profit_is_gross_difference(self, report):
        assert report.gewinn == Decimal("750.00")

    def test_to_dict_has_zero_vat_totals(self, report):
        d = report.to_dict()
        assert Decimal(d["total_einnahmen_ust"]) == Decimal("0")
        assert Decimal(d["total_ausgaben_vorsteuer"]) == Decimal("0")

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "generate_eur has no Kleinunternehmer mode: input VAT on purchase invoices is "
            "excluded from expenses even though a Kleinunternehmer cannot reclaim it. "
            "Callers must pre-adjust receipts (see generate_eur docstring, docs/TODO.md)."
        ),
    )
    def test_purchase_vat_counts_as_expense_for_kleinunternehmer(self):
        report = generate_eur([_r("119.00", "19.00", pct="19")], YEAR)
        assert report.total_ausgaben_netto == Decimal("119.00")


# ---------------------------------------------------------------------------
# Private-use share (business portion only)
# ---------------------------------------------------------------------------


class TestPrivateUse:
    def test_half_private_purchase_counts_half(self):
        report = generate_eur([_r("119.00", pct="19", private_use_share="0.5")], YEAR)
        ln = report.ausgaben_lines["software"]
        assert ln.net_amount == Decimal("50.00")
        assert ln.vat_amount == Decimal("9.50")
