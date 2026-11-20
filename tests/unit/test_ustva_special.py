"""
UST-3 / UST-4: receipts without German VAT.

0 % rate (Kz 87), tax-free sales (Kz 48), reverse charge (Kz 21 / 45 / 60 for sales,
Kz 46/47 or 84/85 plus Kz 67 for purchases). See docs/tax-rules.md.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest

from finamt.models import Address, Counterparty, ReceiptCategory, ReceiptData, ReceiptType
from finamt.tax.elster import ElsterConfig, ElsterXMLBuilder, _ustva_kennzahlen
from finamt.tax.eur import generate_eur
from finamt.tax.ustva import counterparty_region, generate_ustva

Q1 = (date(2026, 1, 1), date(2026, 3, 31))


def _r(
    *,
    receipt_type: str = "sale",
    total: str = "1000.00",
    vat_amount: str | None = None,
    vat_percentage: str | None = None,
    treatment: str | None = None,
    vat_id: str | None = None,
    country: str | None = None,
    private: str = "0",
) -> ReceiptData:
    return ReceiptData(
        raw_text=f"special {uuid.uuid4()}",
        receipt_type=ReceiptType(receipt_type),
        counterparty=Counterparty(name="Client", vat_id=vat_id, address=Address(country=country)),
        receipt_date=datetime(2026, 2, 10),
        total_amount=Decimal(total),
        vat_amount=Decimal(vat_amount) if vat_amount else None,
        vat_percentage=Decimal(vat_percentage) if vat_percentage else None,
        category=ReceiptCategory("services" if receipt_type == "sale" else "software"),
        vat_treatment=treatment,
        private_use_share=Decimal(private),
    )


def _kz(*receipts: ReceiptData) -> dict[str, str]:
    return _ustva_kennzahlen(generate_ustva(receipts, *Q1))


class TestModel:
    def test_unknown_treatment_rejected(self):
        with pytest.raises(ValueError):
            _r(treatment="exempt-ish")

    def test_reverse_charge_property(self):
        r = _r()
        assert r.reverse_charge is False
        r.reverse_charge = True
        assert r.vat_treatment == "reverse_charge"
        r.reverse_charge = False
        assert r.vat_treatment is None

    def test_to_dict(self):
        assert _r(treatment="tax_free").to_dict()["vat_treatment"] == "tax_free"


class TestUst3:
    def test_zero_rate_sale_kz87(self):
        kz = _kz(_r(treatment="zero_rate", total="1000.99"))
        assert kz == {"Kz87": "1000", "Kz83": "0.00"}

    def test_tax_free_sale_kz48(self):
        assert _kz(_r(treatment="tax_free", total="500.00")) == {"Kz48": "500", "Kz83": "0.00"}

    def test_unknown_reason_warns_not_reported(self):
        report = generate_ustva([_r(vat_amount="0", vat_percentage="0")], *Q1)
        assert _ustva_kennzahlen(report) == {"Kz83": "0.00"}
        assert len(report.warnings) == 1
        assert report.skipped_count == 1

    def test_treatment_with_vat_shown_is_refused(self):
        report = generate_ustva([_r(treatment="zero_rate", vat_amount="19.00")], *Q1)
        assert report.zero_rate_net == 0
        assert report.warnings

    def test_zero_rate_purchase_not_reported(self):
        assert _kz(_r(receipt_type="purchase", treatment="zero_rate")) == {"Kz83": "0.00"}


class TestUst4Sales:
    def test_eu_sale_kz21(self):
        kz = _kz(_r(treatment="reverse_charge", vat_id="FR12345678901"))
        assert kz == {"Kz21": "1000", "Kz83": "0.00"}

    def test_eu_sale_does_not_change_kz83(self):
        normal = _r(total="119.00", vat_amount="19.00", vat_percentage="19")
        kz = _kz(normal, _r(treatment="reverse_charge", vat_id="NL123456789B01"))
        assert kz["Kz83"] == "19.00"
        assert kz["Kz21"] == "1000"

    def test_domestic_13b_sale_kz60(self):
        assert _kz(_r(treatment="reverse_charge", vat_id="DE123456789"))["Kz60"] == "1000"

    def test_non_eu_sale_kz45(self):
        assert _kz(_r(treatment="reverse_charge", country="US"))["Kz45"] == "1000"

    def test_unknown_customer_warns(self):
        report = generate_ustva([_r(treatment="reverse_charge")], *Q1)
        assert _ustva_kennzahlen(report) == {"Kz83": "0.00"}
        assert report.warnings


class TestUst4Purchases:
    def test_eu_purchase_kz46_47_67(self):
        kz = _kz(
            _r(
                receipt_type="purchase",
                total="100.00",
                treatment="reverse_charge",
                vat_id="IE6388047V",
            )
        )
        assert kz == {"Kz46": "100", "Kz47": "19.00", "Kz67": "19.00", "Kz83": "0.00"}

    def test_non_eu_purchase_kz84_85(self):
        kz = _kz(
            _r(receipt_type="purchase", total="100.00", treatment="reverse_charge", country="US")
        )
        assert kz == {"Kz84": "100", "Kz85": "19.00", "Kz67": "19.00", "Kz83": "0.00"}

    def test_receipt_rate_used(self):
        kz = _kz(
            _r(
                receipt_type="purchase",
                total="100.00",
                treatment="reverse_charge",
                vat_percentage="7",
                vat_id="ATU12345678",
            )
        )
        assert kz["Kz47"] == "7.00"

    def test_private_share_reduces_only_kz67(self):
        kz = _kz(
            _r(
                receipt_type="purchase",
                total="100.00",
                treatment="reverse_charge",
                vat_id="ATU12345678",
                private="0.5",
            )
        )
        assert kz["Kz47"] == "19.00"
        assert kz["Kz67"] == "9.50"
        assert kz["Kz83"] == "9.50"

    def test_greece_prefix_el(self):
        assert counterparty_region(_r(vat_id="EL123456789")) == "EU"
        assert counterparty_region(_r(vat_id="GB123456789")) == "NON_EU"
        assert counterparty_region(_r(country="Deutschland")) == "DE"
        assert counterparty_region(_r(country="Frankreich")) is None


class TestXmlAndAnnual:
    def _cfg(self) -> ElsterConfig:
        return ElsterConfig(
            cert_path="/tmp/t.pfx",
            cert_password="x",
            steuernummer="21/815/08150",
            finanzamt_nr="2181",
            bundesland_kz="21",
            company_name="Muster",
            street="Weg",
            house_number="1",
            postal_code="24103",
            city="Kiel",
        )

    def test_ustva_xml_has_kz21(self):
        report = generate_ustva([_r(treatment="reverse_charge", vat_id="FR12345678901")], *Q1)
        xml = ElsterXMLBuilder(self._cfg()).build_ustva(report, 2026, 1).decode()
        assert ">1000</" in xml and "Kz21" in xml

    def test_annual_refuses_special_amounts(self):
        report = generate_ustva([_r(treatment="zero_rate")], *Q1)
        with pytest.raises(NotImplementedError):
            ElsterXMLBuilder(self._cfg()).build_ustva(report, 2025, 0)


class TestEur:
    def test_reverse_charge_sale_kz103(self):
        report = generate_eur([_r(treatment="reverse_charge", vat_id="FR12345678901")], 2026)
        kzs = {ln.kz for ln in report.einnahmen_lines.values()}
        assert kzs == {"103"}
        assert not report.review_lines
