"""ZM-1: Zusammenfassende Meldung (§ 18a UStG) calculation."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest

from finamt.models import Address, Counterparty, ReceiptCategory, ReceiptData, ReceiptType
from finamt.tax import generate_zm
from finamt.tax.zm import normalise_vat_id, quarter_bounds


def _sale(
    total: str,
    *,
    vat_id: str | None = "FR12345678901",
    name: str = "Client SARL",
    day: datetime = datetime(2026, 2, 10),
    rc: bool = True,
    country: str | None = None,
    receipt_type: str = "sale",
) -> ReceiptData:
    r = ReceiptData(
        raw_text=f"zm {uuid.uuid4()}",
        receipt_type=ReceiptType(receipt_type),
        counterparty=Counterparty(name=name, vat_id=vat_id, address=Address(country=country)),
        receipt_date=day,
        total_amount=Decimal(total),
        category=ReceiptCategory("services"),
    )
    r.reverse_charge = rc
    return r


class TestGenerateZm:
    def test_sum_per_vat_id(self):
        report = generate_zm(
            [
                _sale("1000.00"),
                _sale("500.50", vat_id="fr 123 456 789 01"),
                _sale("200.00", vat_id="NL123456789B01", name="Klant BV"),
            ],
            2026,
            1,
        )
        assert set(report.lines) == {"FR12345678901", "NL123456789B01"}
        assert report.lines["FR12345678901"].amount == Decimal("1500.50")
        assert report.lines["FR12345678901"].count == 2
        assert report.lines["NL123456789B01"].country == "NL"
        assert report.total == Decimal("1700.50")
        assert report.errors == []

    def test_credit_note_reduces_sum(self):
        report = generate_zm([_sale("1000.00"), _sale("-250.00")], 2026, 1)
        assert report.lines["FR12345678901"].amount == Decimal("750.00")

    def test_missing_vat_id_is_error(self):
        report = generate_zm([_sale("1000.00", vat_id=None, country="FR")], 2026, 1)
        assert report.lines == {}
        assert len(report.errors) == 1
        assert "USt-IdNr" in report.errors[0]

    def test_unknown_country_is_error(self):
        report = generate_zm([_sale("1000.00", vat_id=None)], 2026, 1)
        assert len(report.errors) == 1

    @pytest.mark.parametrize(
        "receipt",
        [
            _sale("1000.00", day=datetime(2026, 4, 1)),  # next quarter
            _sale("1000.00", vat_id="DE123456789"),  # § 13b Abs. 5, Kz 60
            _sale("1000.00", vat_id=None, country="US"),  # non-EU, Kz 45
            _sale("1000.00", rc=False),  # ordinary sale
            _sale("1000.00", receipt_type="purchase"),  # purchase
        ],
    )
    def test_not_in_zm(self, receipt):
        report = generate_zm([receipt], 2026, 1)
        assert report.lines == {} and report.errors == []

    def test_due_date_25th_day_after_quarter(self):
        assert generate_zm([], 2026, 1).due_date == date(2026, 4, 25)
        assert generate_zm([], 2026, 4).due_date == date(2027, 1, 25)

    def test_quarter_bounds(self):
        assert quarter_bounds(2026, 2) == (date(2026, 4, 1), date(2026, 6, 30))
        with pytest.raises(ValueError):
            quarter_bounds(2026, 5)

    def test_export(self):
        report = generate_zm([_sale("1000.00")], 2026, 1)
        d = report.to_dict()
        assert d["lines"][0]["amount"] == "1000.00"
        assert '"due_date": "2026-04-25"' in report.to_json()
        assert "FR12345678901" in report.summary()

    def test_normalise(self):
        assert normalise_vat_id(" el-123.456 789 ") == "EL123456789"
