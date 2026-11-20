"""CLN-3: mixed-rate receipts use ``vat_splits`` in the UStVA."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from finamt.models import Counterparty, ReceiptCategory, ReceiptData, ReceiptType
from finamt.tax.elster import _ustva_kennzahlen
from finamt.tax.ustva import generate_ustva

Q1 = (date(2026, 1, 1), date(2026, 3, 31))


def _mixed(receipt_type: str = "sale", splits=None, vat: str = "26.00", private: str = "0"):
    return ReceiptData(
        raw_text=f"mixed {uuid.uuid4()}",
        receipt_type=ReceiptType(receipt_type),
        counterparty=Counterparty(name="Kunde"),
        receipt_date=datetime(2026, 2, 1),
        total_amount=Decimal("226.00"),
        vat_amount=Decimal(vat),
        vat_percentage=None,
        category=ReceiptCategory("services"),
        # floats, as SQLiteRepository loads them
        vat_splits=splits
        if splits is not None
        else [
            {"vat_rate": 19.0, "vat_amount": 19.0, "net_amount": 100.0},
            {"vat_rate": 7.0, "vat_amount": 7.0, "net_amount": 100.0},
        ],
        private_use_share=Decimal(private),
    )


def test_sale_splits_land_on_their_rate_lines():
    report = generate_ustva([_mixed()], *Q1)
    assert report.lines["19"].sale_net == Decimal("100.00")
    assert report.lines["7"].sale_vat == Decimal("7.00")
    assert "unknown" not in report.lines
    assert report.total_receipts == 1
    assert report.warnings == []
    kz = _ustva_kennzahlen(report)
    assert kz["Kz81"] == "100" and kz["Kz86"] == "100" and kz["Kz83"] == "26.00"


def test_purchase_splits_business_share():
    report = generate_ustva([_mixed("purchase", private="0.5")], *Q1)
    assert report.lines["19"].purchase_vat == Decimal("9.50")
    assert report.lines["7"].purchase_net == Decimal("50.00")


def test_missing_net_derived_from_vat():
    report = generate_ustva(
        [_mixed(splits=[{"vat_rate": 19.0, "vat_amount": 19.0, "net_amount": None}], vat="19.00")],
        *Q1,
    )
    assert report.lines["19"].sale_net == Decimal("100.00")


def test_incomplete_split_falls_back_with_warning():
    report = generate_ustva(
        [_mixed(splits=[{"vat_rate": None, "vat_amount": 19.0, "net_amount": 100.0}])], *Q1
    )
    assert "unknown" in report.lines
    assert any("ohne USt-Satz" in w for w in report.warnings)


def test_unknown_rate_without_splits_warns():
    report = generate_ustva([_mixed(splits=[])], *Q1)
    assert "unknown" in report.lines
    assert len(report.warnings) == 1


def test_split_sum_mismatch_warns():
    report = generate_ustva([_mixed(vat="30.00")], *Q1)
    assert report.lines["19"].sale_vat == Decimal("19.00")
    assert any("weicht" in w for w in report.warnings)


def test_rate_key_without_exponent():
    r = _mixed(splits=[{"vat_rate": 10.0, "vat_amount": 10.0, "net_amount": 100.0}], vat="10.00")
    assert "10" in generate_ustva([r], *Q1).lines
