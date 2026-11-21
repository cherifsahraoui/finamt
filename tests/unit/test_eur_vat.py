"""
tests/unit/test_eur_vat.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
EUR-2: VAT lines in the EÜR (Kz 140 / 141 / 185 / 186, decision D6) and the
Kleinunternehmer mode (Kz 111, decision D7). Rules: docs/tax-rules.md rows
"VAT is income/expense", Kz 111, 112, 140, 141, 185, 186, Kleinunternehmer.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from finamt.models import Counterparty, ReceiptCategory, ReceiptData, ReceiptType
from finamt.tax.eur import generate_eur

YEAR = 2025


def _r(
    total: str,
    vat: str | None = None,
    *,
    pct: str | None = None,
    category: str = "software",
    sub: str | None = None,
    receipt_type: str = "purchase",
    private_use_share: str = "0",
) -> ReceiptData:
    r = ReceiptData(
        raw_text=f"vat {uuid.uuid4()}",
        receipt_type=ReceiptType(receipt_type),
        counterparty=Counterparty(name="Test"),
        receipt_date=datetime(YEAR, 6, 1),
        total_amount=Decimal(total),
        vat_amount=Decimal(vat) if vat is not None else None,
        vat_percentage=Decimal(pct) if pct is not None else None,
        category=ReceiptCategory(category),
        private_use_share=Decimal(private_use_share),
    )
    r.subcategory = sub
    return r


def _sale(total: str, vat: str, pct: str = "19") -> ReceiptData:
    return _r(total, vat, pct=pct, category="services", receipt_type="sale")


class TestRegelbesteuerung:
    def test_card_example(self):
        report = generate_eur(
            [
                _sale("1190.00", "190.00"),
                _r("119.00", "19.00", pct="19"),
                _r("171.00", category="tax_settlement", sub="vat_payment"),
            ],
            YEAR,
        )
        totals = report.kz_totals()
        assert totals["112"] == Decimal("1000.00")
        assert totals["140"] == Decimal("190.00")
        assert totals["185"] == Decimal("19.00")
        assert totals["186"] == Decimal("171.00")
        assert report.review_lines == {}
        # 1000 + 190 − 100 − 19 − 171
        assert report.gewinn == Decimal("900.00")
        assert report.total_betriebseinnahmen == Decimal("1190.00")
        assert report.total_betriebsausgaben == Decimal("290.00")

    def test_vat_refund_is_kz_141(self):
        report = generate_eur(
            [_r("80.00", category="tax_settlement", sub="vat_refund", receipt_type="sale")],
            YEAR,
        )
        assert report.kz_totals() == {"141": Decimal("80.00")}
        assert report.gewinn == Decimal("80.00")

    def test_vat_payment_ignores_vat_fields(self):
        # A payment to the Finanzamt carries no VAT; the amount paid is the expense.
        r = _r("171.00", "0.00", pct="0", category="tax_settlement", sub="vat_payment")
        report = generate_eur([r], YEAR)
        assert report.kz_totals() == {"186": Decimal("171.00")}

    def test_other_tax_payments_stay_in_review(self):
        report = generate_eur([_r("500.00", category="tax_settlement", sub="income_tax")], YEAR)
        assert list(report.review_lines) == ["tax_settlement"]
        assert report.gewinn == Decimal("0")

    def test_kz_185_is_business_share_only(self):
        report = generate_eur([_r("119.00", "19.00", pct="19", private_use_share="0.5")], YEAR)
        assert report.kz_totals() == {"185": Decimal("9.50"), "228": Decimal("50.00")}

    def test_no_vat_lines_when_no_vat(self):
        report = generate_eur([_sale("1000.00", "0.00", pct="0")], YEAR)
        assert report.kz_totals() == {"103": Decimal("1000.00")}

    def test_summary_shows_vat_lines_without_net_method_warning(self):
        s = generate_eur([_sale("1190.00", "190.00"), _r("119.00", "19.00", pct="19")], YEAR)
        text = s.summary()
        assert "Kz 140" in text
        assert "Kz 185" in text
        assert "Nettomethode" not in text

    def test_to_dict_has_new_totals(self):
        d = generate_eur([_sale("1190.00", "190.00")], YEAR).to_dict()
        assert d["kleinunternehmer"] is False
        assert d["total_betriebseinnahmen"] == "1190.00"
        assert d["kz_totals"]["140"] == "190.00"


class TestKleinunternehmer:
    def test_card_example(self):
        report = generate_eur(
            [
                _r("1000.00", category="services", receipt_type="sale"),
                _r("119.00", "19.00", pct="19"),
            ],
            YEAR,
            kleinunternehmer=True,
        )
        assert report.kz_totals() == {"111": Decimal("1000.00"), "228": Decimal("119.00")}
        assert report.total_betriebsausgaben == Decimal("119.00")
        assert report.gewinn == Decimal("881.00")

    def test_sale_with_vat_counts_gross_in_kz_111(self):
        report = generate_eur([_sale("1190.00", "190.00")], YEAR, kleinunternehmer=True)
        assert report.kz_totals() == {"111": Decimal("1190.00")}

    def test_no_kz_112_140_185(self):
        report = generate_eur(
            [_sale("1190.00", "190.00"), _r("119.00", "19.00", pct="19")],
            YEAR,
            kleinunternehmer=True,
        )
        assert not {"112", "140", "185"} & set(report.kz_totals())

    def test_gwg_limit_compares_gross(self):
        # 900 net + 171 VAT: for a Kleinunternehmer the VAT is part of the cost → review.
        r = _r("1071.00", "171.00", pct="19", category="equipment")
        assert generate_eur([r], YEAR).review_lines  # 900 > 800 net as well
        r2 = _r("952.00", "152.00", pct="19", category="equipment")  # 800 net, 952 gross
        assert "equipment" in generate_eur([r2], YEAR).ausgaben_lines
        assert generate_eur([r2], YEAR, kleinunternehmer=True).review_lines

    def test_summary_mentions_mode(self):
        report = generate_eur([_sale("100.00", "0.00")], YEAR, kleinunternehmer=True)
        assert "Kleinunternehmer" in report.summary()
        assert report.to_dict()["kleinunternehmer"] is True
