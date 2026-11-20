"""Tests for finamt.tax.assets and the asset register in generate_eur (EUR-3)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from finamt.models import Counterparty, ReceiptCategory, ReceiptData, ReceiptType
from finamt.tax.assets import COMPUTER_ONE_YEAR, LINEAR, Asset, afa_for_year, restwert
from finamt.tax.eur import generate_eur

D = Decimal


def _asset(cost="1200", acquired=date(2025, 10, 5), **kw) -> Asset:
    kw.setdefault("method", LINEAR)
    kw.setdefault("useful_life_years", 3)
    return Asset("Test", acquired, D(cost), **kw)


class TestAfa:
    def test_linear_pro_rata_counts_acquisition_month(self):
        a = _asset()  # 1200 / 3 = 400 a year, Oct-Dec = 3 months
        assert afa_for_year(a, 2024) == D("0")
        assert afa_for_year(a, 2025) == D("100.00")
        assert afa_for_year(a, 2026) == D("400.00")
        assert afa_for_year(a, 2027) == D("400.00")
        assert afa_for_year(a, 2028) == D("300.00")
        assert afa_for_year(a, 2029) == D("0")

    def test_linear_sums_to_cost_without_rounding_remainder(self):
        a = _asset(cost="1000.01", acquired=date(2025, 3, 31), useful_life_years=7)
        total = sum(afa_for_year(a, y) for y in range(2025, 2035))
        assert total == D("1000.01")
        assert restwert(a, 2040) == D("0.00")

    def test_january_purchase_is_a_full_first_year(self):
        a = _asset(cost="900", acquired=date(2025, 1, 15), useful_life_years=3)
        assert afa_for_year(a, 2025) == D("300.00")
        assert afa_for_year(a, 2027) == D("300.00")
        assert afa_for_year(a, 2028) == D("0")

    def test_computer_one_year_writes_off_everything_at_once(self):
        a = _asset(
            cost="1500",
            acquired=date(2025, 12, 20),
            method=COMPUTER_ONE_YEAR,
            useful_life_years=None,
        )
        assert afa_for_year(a, 2025) == D("1500.00")
        assert afa_for_year(a, 2026) == D("0")
        assert restwert(a, 2025) == D("0.00")

    def test_linear_needs_a_useful_life(self):
        with pytest.raises(ValueError, match="useful_life_years"):
            Asset("x", date(2025, 1, 1), D("900"))

    def test_rejects_float_and_nonpositive_cost(self):
        with pytest.raises(TypeError):
            Asset("x", date(2025, 1, 1), 900.0, useful_life_years=3)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            Asset("x", date(2025, 1, 1), D("0"), useful_life_years=3)

    def test_dict_roundtrip(self):
        a = _asset(receipt_id="abc", intangible=True)
        assert Asset.from_dict(a.to_dict()) == a


def _equipment(net="1500.00", vat="285.00", when=datetime(2025, 10, 5)) -> ReceiptData:
    return ReceiptData(
        raw_text="laptop",
        receipt_type=ReceiptType("purchase"),
        counterparty=Counterparty(name="Shop"),
        receipt_date=when,
        total_amount=D(net) + D(vat),
        vat_amount=D(vat),
        category=ReceiptCategory("equipment"),
    )


class TestEurWithRegister:
    def test_unregistered_asset_stays_in_review(self):
        rep = generate_eur([_equipment()], 2025)
        assert "equipment" in rep.review_lines
        assert rep.gewinn == D("0.00")

    def test_computer_one_year_goes_to_kz130_and_vorsteuer_to_kz185(self):
        r = _equipment()
        a = Asset("Laptop", date(2025, 10, 5), D("1500"), method=COMPUTER_ONE_YEAR, receipt_id=r.id)
        rep = generate_eur([r], 2025, assets=[a])
        assert not rep.review_lines
        assert rep.kz_totals()["130"] == D("1500.00")
        assert rep.kz_totals()["185"] == D("285.00")
        assert rep.gewinn == D("-1785.00")

    def test_linear_asset_from_earlier_year_gives_afa_without_receipt(self):
        a = _asset(acquired=date(2024, 7, 1), cost="2400", useful_life_years=4)
        rep = generate_eur([], 2025, assets=[a])
        assert rep.kz_totals() == {"130": D("600.00")}
        assert rep.gewinn == D("-600.00")

    def test_intangible_goes_to_kz131(self):
        a = _asset(intangible=True, method=COMPUTER_ONE_YEAR, useful_life_years=None)
        rep = generate_eur([], 2025, assets=[a])
        assert rep.kz_totals() == {"131": D("1200.00")}

    def test_kleinunternehmer_books_no_vorsteuer(self):
        r = _equipment(net="1500.00", vat="0.00")
        a = Asset("Laptop", date(2025, 10, 5), D("1500"), method=COMPUTER_ONE_YEAR, receipt_id=r.id)
        rep = generate_eur([r], 2025, kleinunternehmer=True, assets=[a])
        assert rep.kz_totals() == {"130": D("1500.00")}
