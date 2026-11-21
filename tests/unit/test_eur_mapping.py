"""
tests/unit/test_eur_mapping.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Category → Anlage EÜR 2025 Kennzahl mapping (task EUR-1, docs/TODO.md).

Every Kennzahl asserted here is listed as verified in docs/tax-rules.md
(BMF-Schreiben 29.08.2025, Anlage EÜR 2025).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from finamt.agents.prompts import RECEIPT_CATEGORIES
from finamt.models import Counterparty, ReceiptCategory, ReceiptData, ReceiptType
from finamt.tax.eur import (
    _PURCHASE_KZ,
    _PURCHASE_SUB_KZ,
    FORM_YEAR,
    GWG_LIMIT,
    KZ_LABELS,
    REVIEW,
    generate_eur,
)

YEAR = FORM_YEAR
TAX_RULES = Path(__file__).resolve().parents[2] / "docs" / "tax-rules.md"


def _r(
    category: str,
    *,
    sub: str | None = None,
    total: str = "119.00",
    vat: str | None = "19.00",
    pct: str | None = None,
    receipt_type: str = "purchase",
) -> ReceiptData:
    r = ReceiptData(
        raw_text=f"map {uuid.uuid4()}",
        receipt_type=ReceiptType(receipt_type),
        counterparty=Counterparty(name="X"),
        receipt_date=datetime(YEAR, 3, 1),
        total_amount=Decimal(total),
        vat_amount=Decimal(vat) if vat is not None else None,
        vat_percentage=Decimal(pct) if pct is not None else None,
        category=ReceiptCategory(category),
    )
    r.subcategory = sub
    return r


def _only_line(report):
    lines = {**report.einnahmen_lines, **report.ausgaben_lines, **report.review_lines}
    assert len(lines) == 1, lines
    return next(iter(lines.items()))


# ---------------------------------------------------------------------------
# Every Kennzahl used is verified and labelled
# ---------------------------------------------------------------------------


def test_every_mapped_kz_has_a_label():
    used = set(_PURCHASE_KZ.values()) | set(_PURCHASE_SUB_KZ.values()) | {"112", "103", "102"}
    assert used <= set(KZ_LABELS)


def test_every_labelled_kz_is_verified_in_tax_rules():
    text = TAX_RULES.read_text(encoding="utf-8")
    verified = set()
    for line in text.splitlines():
        if line.startswith("| Kz ") and "verified" in line:
            verified |= set(re.findall(r"\b(\d{3})\b", line.split("|")[1]))
    missing = set(KZ_LABELS) - verified
    assert not missing, f"Kennzahlen without a verified row in docs/tax-rules.md: {missing}"


def test_every_receipt_category_is_handled():
    review_only = {"donations", "tax_settlement", "capital_movement"}
    for cat in RECEIPT_CATEGORIES:
        assert cat in _PURCHASE_KZ or cat in review_only, cat


# ---------------------------------------------------------------------------
# Purchases: category defaults
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "category,kz",
    [
        ("material", "100"),
        ("products", "100"),
        ("services", "110"),
        ("equipment", "132"),
        ("software", "228"),
        ("licensing", "183"),
        ("telecommunication", "280"),
        ("travel", "221"),
        ("car", "146"),
        ("education", "281"),
        ("utilities", "151"),
        ("insurance", "223"),
        ("financial", "183"),
        ("office", "150"),
        ("marketing", "224"),
        ("public_fees", "223"),
        ("other", "183"),
    ],
)
def test_purchase_category_default(category, kz):
    key, ln = _only_line(generate_eur([_r(category)], YEAR))
    assert (key, ln.kz) == (category, kz)
    assert ln.label == KZ_LABELS[kz]


@pytest.mark.parametrize(
    "category,sub,kz",
    [
        ("services", "legal", "194"),
        ("services", "accounting", "194"),
        ("material", "consumables", "229"),
        ("education", "books", "229"),
        ("travel", "transport", "146"),
        ("car", "leasing", "144"),
        ("car", "insurance", "145"),
        ("insurance", "vehicle", "145"),
        ("financial", "interest", "234"),
        ("office", "cleaning", "151"),
        ("other", "membership_fees", "223"),
    ],
)
def test_purchase_subcategory_override(category, sub, kz):
    key, ln = _only_line(generate_eur([_r(category, sub=sub)], YEAR))
    assert ln.kz == kz
    assert key == f"{category}:{kz}"


def test_subcategory_is_case_insensitive():
    _, ln = _only_line(generate_eur([_r("travel", sub="Transport")], YEAR))
    assert ln.kz == "146"


def test_subcategory_without_override_uses_default():
    key, ln = _only_line(generate_eur([_r("software", sub="subscriptions")], YEAR))
    assert (key, ln.kz) == ("software", "228")


# ---------------------------------------------------------------------------
# GWG limit (§ 6 Abs. 2 EStG: 800 € net)
# ---------------------------------------------------------------------------


class TestGwg:
    def test_limit_value(self):
        assert GWG_LIMIT == Decimal("800")

    def test_exactly_800_net_is_gwg(self):
        _, ln = _only_line(generate_eur([_r("equipment", total="952.00", vat="152.00")], YEAR))
        assert ln.kz == "132"
        assert ln.net_amount == Decimal("800.00")

    def test_above_800_net_goes_to_review(self):
        report = generate_eur([_r("equipment", total="952.01", vat="152.00")], YEAR)
        key, ln = _only_line(report)
        assert ln.kz == REVIEW and key == "equipment"
        assert "AfA" in ln.reason
        assert report.total_ausgaben_netto == Decimal("0")
        assert report.total_review_netto == Decimal("800.01")


# ---------------------------------------------------------------------------
# Review items: listed, never part of the profit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "category,sub,key",
    [
        ("travel", "meals", "travel/meals"),
        ("travel", "per_diem", "travel/per_diem"),
        ("marketing", "gifts", "marketing/gifts"),
        ("insurance", "health", "insurance/health"),
        ("donations", None, "donations"),
        ("tax_settlement", "income_tax", "tax_settlement"),
        ("tax_settlement", None, "tax_settlement"),
        ("capital_movement", "withdrawal", "capital_movement"),
    ],
)
def test_purchase_review_items_excluded_from_profit(category, sub, key):
    report = generate_eur([_r(category, sub=sub)], YEAR)
    assert list(report.review_lines) == [key]
    assert report.review_lines[key].reason
    assert report.ausgaben_lines == {}
    assert report.gewinn == Decimal("0")


@pytest.mark.parametrize("category", ["capital_movement", "tax_settlement"])
def test_sale_review_items_excluded_from_profit(category):
    report = generate_eur([_r(category, receipt_type="sale")], YEAR)
    assert list(report.review_lines) == [category]
    assert report.einnahmen_lines == {}
    assert report.gewinn == Decimal("0")


# ---------------------------------------------------------------------------
# Sales (Regelbesteuerung)
# ---------------------------------------------------------------------------


class TestSales:
    def test_taxable_sale_is_112(self):
        key, ln = _only_line(generate_eur([_r("services", receipt_type="sale")], YEAR))
        assert (key, ln.kz) == ("services", "112")

    def test_zero_rate_sale_is_103(self):
        r = _r("services", receipt_type="sale", total="1000.00", vat="0.00", pct="0")
        key, ln = _only_line(generate_eur([r], YEAR))
        assert (key, ln.kz) == ("services:103", "103")
        assert ln.net_amount == Decimal("1000.00")

    def test_unknown_vat_status_goes_to_review(self):
        r = _r("services", receipt_type="sale", total="1000.00", vat=None, pct=None)
        report = generate_eur([r], YEAR)
        assert list(report.review_lines) == ["services"]
        assert report.gewinn == Decimal("0")

    def test_taxable_and_zero_rate_sales_split(self):
        report = generate_eur(
            [
                _r("services", receipt_type="sale"),
                _r("services", receipt_type="sale", total="50.00", vat="0.00", pct="0"),
            ],
            YEAR,
        )
        assert report.kz_totals() == {
            "103": Decimal("50.00"),
            "112": Decimal("100.00"),
            "140": Decimal("19.00"),
        }

    def test_equipment_sale_is_102(self):
        _, ln = _only_line(generate_eur([_r("equipment", receipt_type="sale")], YEAR))
        assert ln.kz == "102"

    def test_credit_note_stays_on_112(self):
        r = _r("services", receipt_type="sale", total="-119.00", vat="-19.00")
        _, ln = _only_line(generate_eur([r], YEAR))
        assert ln.kz == "112" and ln.net_amount == Decimal("-100.00")


# ---------------------------------------------------------------------------
# Report metadata
# ---------------------------------------------------------------------------


class TestReport:
    def test_no_warning_for_form_year(self):
        assert generate_eur([], FORM_YEAR).warnings == []

    def test_warning_for_other_years(self):
        report = generate_eur([], FORM_YEAR + 1)
        assert any(str(FORM_YEAR) in w for w in report.warnings)

    def test_to_dict_contains_review_and_form_year(self):
        d = generate_eur([_r("donations")], YEAR).to_dict()
        assert d["form_year"] == FORM_YEAR
        assert "donations" in d["review"]
        assert d["review"]["donations"]["reason"]
        assert d["total_review_netto"] == "100.00"

    def test_summary_lists_review_items(self):
        s = generate_eur([_r("donations")], YEAR).summary()
        assert "ZU PRÜFEN" in s and "donations" in s
