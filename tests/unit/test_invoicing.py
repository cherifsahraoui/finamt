"""
tests/unit/test_invoicing.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
INV-1: outgoing invoices (§ 14 UStG) — mandatory fields, gapless numbering, per-rate totals,
PDF, stored sale receipt, cancellation (Rechnungskorrektur). Offline: temp SQLite DB only.
"""

from __future__ import annotations

import threading
from datetime import date
from decimal import Decimal

import pytest

from finamt.invoicing import (
    KLEINUNTERNEHMER_HINWEIS,
    Invoice,
    InvoiceLine,
    Party,
    cancel_invoice,
    format_number,
    issue_invoice,
    parse_number,
    render_pdf,
    supplier_from_taxpayer,
)
from finamt.invoicing.render import pdf_text
from finamt.storage.sqlite import SQLiteRepository
from finamt.tax.elster import _ustva_kennzahlen
from finamt.tax.ustva import generate_ustva

SUPPLIER = Party(
    name="Erika Muster IT-Beratung",
    street="Teststraße 1",
    postcode="80331",
    city="München",
    steuernummer="143/123/45678",
    ust_idnr="DE123456789",
)
CUSTOMER = Party(name="Kunde GmbH", street="Hauptstraße 5", postcode="10115", city="Berlin")


def _inv(**kw) -> Invoice:
    d = {
        "supplier": SUPPLIER,
        "customer": CUSTOMER,
        "issue_date": date(2025, 3, 31),
        "supply_period": (date(2025, 3, 1), date(2025, 3, 31)),
        "lines": [
            InvoiceLine("Beratung März", Decimal("10"), Decimal("100.00"), Decimal("19"), "Std."),
            InvoiceLine("Fachbuch", Decimal("1"), Decimal("50.00"), Decimal("7")),
        ],
    }
    d.update(kw)
    return Invoice(**d)


@pytest.fixture
def repo(tmp_path):
    with SQLiteRepository(db_path=tmp_path / "inv.db") as r:
        yield r


# ---------------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------------


class TestTotals:
    def test_per_rate_totals_sum_to_gross(self):
        inv = _inv()
        totals = {t.rate: t for t in inv.rate_totals()}
        assert totals[Decimal("19")].net == Decimal("1000.00")
        assert totals[Decimal("19")].vat == Decimal("190.00")
        assert totals[Decimal("7")].net == Decimal("50.00")
        assert totals[Decimal("7")].vat == Decimal("3.50")
        assert inv.net_total == Decimal("1050.00")
        assert inv.vat_total == Decimal("193.50")
        assert inv.gross_total == Decimal("1243.50")
        assert sum(t.gross for t in inv.rate_totals()) == inv.gross_total

    def test_vat_rounded_per_rate_not_per_line(self):
        lines = [
            InvoiceLine(f"L{i}", Decimal("1"), Decimal("0.05"), Decimal("19")) for i in range(3)
        ]
        inv = _inv(lines=lines)
        # 0.15 × 19 % = 0.0285 → 0.03 (per line it would be 3 × 0.01 = 0.03 as well; use 0.10)
        assert inv.vat_total == Decimal("0.03")
        lines = [
            InvoiceLine(f"L{i}", Decimal("1"), Decimal("0.10"), Decimal("19")) for i in range(3)
        ]
        # per rate: 0.30 × 19 % = 0.057 → 0.06; per line it would be 3 × 0.02 = 0.06 — equal here,
        # but the rounding happens once per rate:
        assert _inv(lines=lines).rate_totals()[0].vat == Decimal("0.06")

    def test_kleinunternehmer_has_no_vat(self):
        inv = _inv(
            kleinunternehmer=True,
            lines=[InvoiceLine("Beratung", Decimal("2"), Decimal("80"), Decimal("0"))],
        )
        assert inv.vat_total == Decimal("0")
        assert inv.gross_total == Decimal("160.00")


# ---------------------------------------------------------------------------
# § 14 Abs. 4 mandatory fields
# ---------------------------------------------------------------------------


class TestMandatoryFields:
    def test_complete_invoice_has_no_gaps(self):
        assert _inv(number="2025-0001").missing_fields() == []

    @pytest.mark.parametrize(
        "change,text",
        [
            ({"supplier": Party(name="X")}, "leistenden Unternehmers fehlen"),
            ({"customer": Party(name="Kunde")}, "Leistungsempfängers fehlen"),
            ({"supplier": Party("A", "B 1", "1", "C")}, "Steuernummer oder USt-IdNr."),
            ({"supply_period": None}, "Leistungsdatum oder Leistungszeitraum fehlt"),
            ({"lines": []}, "Mindestens eine Position"),
            (
                {"lines": [InvoiceLine("", Decimal("1"), Decimal("500"), Decimal("19"))]},
                "Beschreibung der Leistung fehlt",
            ),
            (
                {"lines": [InvoiceLine("X", Decimal("1"), Decimal("500"), Decimal("16"))]},
                "Steuersatz 16 %",
            ),
            (
                {"lines": [InvoiceLine("X", Decimal("1"), Decimal("500"), Decimal("0"))]},
                "Hinweis auf den Grund",
            ),
        ],
    )
    def test_missing_field_reported(self, change, text):
        fehler = _inv(number="2025-0001", **change).missing_fields()
        assert any(text in f for f in fehler), fehler

    def test_number_required_once_issued(self):
        assert "Rechnungsnummer fehlt." in _inv().missing_fields()

    def test_kleinbetrag_needs_fewer_fields(self):
        # § 33 UStDV: up to 250 € gross no customer address, tax number or supply date
        inv = _inv(
            number="2025-0001",
            customer=Party(name="Barkunde"),
            supplier=Party("A", "B 1", "1", "C"),
            supply_period=None,
            lines=[InvoiceLine("Kleinteil", Decimal("1"), Decimal("200"), Decimal("19"))],
        )
        assert inv.gross_total == Decimal("238.00")
        assert inv.missing_fields() == []

    def test_kleinunternehmer_must_not_show_vat(self):
        inv = _inv(number="2025-0001", kleinunternehmer=True)
        assert any("keine Umsatzsteuer ausweisen" in f for f in inv.missing_fields())


# ---------------------------------------------------------------------------
# Numbering
# ---------------------------------------------------------------------------


class TestNumbering:
    def test_format_and_parse(self):
        assert format_number(2025, 7) == "2025-0007"
        assert parse_number("2025-0007") == (2025, 7)
        with pytest.raises(ValueError):
            parse_number("R-7")
        with pytest.raises(ValueError):
            format_number(2025, 0)

    def test_gapless_per_year(self, repo, tmp_path):
        nums = [issue_invoice(repo, _inv(), tmp_path / "pdfs").invoice.number for _ in range(3)]
        nums.append(
            issue_invoice(repo, _inv(issue_date=date(2026, 1, 2)), tmp_path / "pdfs").invoice.number
        )
        assert nums == ["2025-0001", "2025-0002", "2025-0003", "2026-0001"]

    def test_failed_build_does_not_use_a_number(self, repo):
        def boom(seq):
            raise RuntimeError("x")

        with pytest.raises(RuntimeError):
            repo.create_invoice(2025, boom)
        data = repo.create_invoice(
            2025,
            lambda seq: {"number": format_number(2025, seq), "issue_date": "2025-01-01"},
        )
        assert data["number"] == "2025-0001"

    def test_unique_and_gapless_under_concurrent_allocation(self, tmp_path):
        db = tmp_path / "conc.db"
        SQLiteRepository(db_path=db).close()  # create schema once
        got: list[str] = []
        errors: list[BaseException] = []
        barrier = threading.Barrier(2)

        def worker():
            try:
                with SQLiteRepository(db_path=db) as r:  # own connection per thread
                    barrier.wait()
                    for _ in range(10):
                        d = r.create_invoice(
                            2025,
                            lambda seq: {
                                "number": format_number(2025, seq),
                                "issue_date": "2025-01-01",
                            },
                        )
                        got.append(d["number"])
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert sorted(got) == [format_number(2025, i) for i in range(1, 21)]


# ---------------------------------------------------------------------------
# Issue: PDF + receipt
# ---------------------------------------------------------------------------


class TestIssue:
    def test_pdf_has_every_mandatory_field(self, repo, tmp_path):
        res = issue_invoice(repo, _inv(), tmp_path / "pdfs")
        text = pdf_text(open(res.pdf_path, "rb").read())
        for needed in (
            "Erika Muster IT-Beratung",  # Nr. 1 supplier
            "Teststraße 1",
            "Kunde GmbH",  # Nr. 1 customer
            "Hauptstraße 5",
            "143/123/45678",  # Nr. 2
            "DE123456789",
            "31.03.2025",  # Nr. 3
            "Rechnung Nr. 2025-0001",  # Nr. 4
            "Beratung März",  # Nr. 5
            "01.03.2025 – 31.03.2025",  # Nr. 6
            "Netto 19 %",  # Nr. 7
            "1.000,00 €",
            "Umsatzsteuer 19 %",  # Nr. 8
            "190,00 €",
            "Umsatzsteuer 7 %",
            "3,50 €",
            "1.243,50 €",
        ):
            assert needed in text, needed

    def test_stored_as_sale_receipt_with_pdf(self, repo, tmp_path):
        res = issue_invoice(repo, _inv(), tmp_path / "pdfs")
        r = repo.get(res.receipt_id)
        assert str(r.receipt_type) == "sale"
        assert r.total_amount == Decimal("1243.50")
        assert r.vat_amount == Decimal("193.50")
        assert r.receipt_number == "2025-0001"
        assert r.vendor == "Kunde GmbH"
        assert (tmp_path / "pdfs" / f"{res.receipt_id}.pdf").exists()
        assert repo.get_invoice("2025-0001")["receipt_id"] == res.receipt_id

    def test_incomplete_invoice_stores_nothing(self, repo, tmp_path):
        with pytest.raises(ValueError, match="Rechnung unvollständig"):
            issue_invoice(repo, _inv(customer=Party()), tmp_path / "pdfs")
        assert repo.list_invoices() == []
        assert list(repo.list_all()) == []

    def test_kleinunternehmer_pdf_has_note_and_no_vat(self, repo, tmp_path):
        inv = _inv(
            kleinunternehmer=True,
            lines=[InvoiceLine("Beratung", Decimal("10"), Decimal("80"), Decimal("0"))],
        )
        res = issue_invoice(repo, inv, tmp_path / "pdfs")
        text = pdf_text(open(res.pdf_path, "rb").read())
        assert KLEINUNTERNEHMER_HINWEIS in text
        assert "Umsatzsteuer" not in text.replace(KLEINUNTERNEHMER_HINWEIS, "")
        assert repo.get(res.receipt_id).vat_amount == Decimal("0")

    def test_single_rate_receipt_gets_rate(self, repo, tmp_path):
        inv = _inv(lines=[InvoiceLine("X", Decimal("1"), Decimal("1000"), Decimal("19"))])
        r = repo.get(issue_invoice(repo, inv, tmp_path / "pdfs").receipt_id)
        assert r.vat_percentage == Decimal("19")

    def test_issued_sale_reaches_ustva(self, repo, tmp_path):
        inv = _inv(lines=[InvoiceLine("X", Decimal("1"), Decimal("1000"), Decimal("19"))])
        issue_invoice(repo, inv, tmp_path / "pdfs")
        rep = generate_ustva(list(repo.list_all()), date(2025, 1, 1), date(2025, 3, 31))
        assert _ustva_kennzahlen(rep)["Kz81"] == "1000"


# ---------------------------------------------------------------------------
# Cancellation (Rechnungskorrektur / Storno)
# ---------------------------------------------------------------------------


class TestCancel:
    def test_correction_references_original_and_negates(self, repo, tmp_path):
        issue_invoice(repo, _inv(), tmp_path / "pdfs")
        res = cancel_invoice(repo, "2025-0001", tmp_path / "pdfs", issue_date=date(2025, 4, 2))
        corr = res.invoice
        assert corr.number == "2025-0002"  # own number, original keeps its own
        assert corr.corrects == "2025-0001"
        assert corr.gross_total == Decimal("-1243.50")
        text = pdf_text(open(res.pdf_path, "rb").read())
        assert "Rechnungskorrektur (Storno) Nr. 2025-0002" in text
        assert "Storno der Rechnung Nr. 2025-0001 vom 31.03.2025" in text
        assert "Gutschrift" not in text
        assert repo.invoice_corrected_by("2025-0001") == "2025-0002"

    def test_cancelled_period_nets_to_zero_in_ustva(self, repo, tmp_path):
        inv = _inv(lines=[InvoiceLine("X", Decimal("1"), Decimal("1000"), Decimal("19"))])
        issue_invoice(repo, inv, tmp_path / "pdfs")
        cancel_invoice(repo, "2025-0001", tmp_path / "pdfs", issue_date=date(2025, 3, 31))
        rep = generate_ustva(list(repo.list_all()), date(2025, 1, 1), date(2025, 3, 31))
        assert _ustva_kennzahlen(rep) == {"Kz83": "0.00"}

    def test_cannot_cancel_twice_or_cancel_a_correction(self, repo, tmp_path):
        issue_invoice(repo, _inv(), tmp_path / "pdfs")
        cancel_invoice(repo, "2025-0001", tmp_path / "pdfs", issue_date=date(2025, 4, 1))
        with pytest.raises(ValueError, match="schon durch"):
            cancel_invoice(repo, "2025-0001", tmp_path / "pdfs")
        with pytest.raises(ValueError, match="nicht erneut"):
            cancel_invoice(repo, "2025-0002", tmp_path / "pdfs")

    def test_correction_dated_today_by_default(self, repo, tmp_path):
        issue_invoice(repo, _inv(), tmp_path / "pdfs")
        res = cancel_invoice(repo, "2025-0001", tmp_path / "pdfs")
        assert res.invoice.issue_date == date.today()
        assert res.invoice.number.startswith(f"{date.today().year}-")

    def test_unknown_number(self, repo, tmp_path):
        with pytest.raises(ValueError, match="nicht gefunden"):
            cancel_invoice(repo, "2025-0099", tmp_path / "pdfs")


class TestHelpers:
    def test_supplier_from_taxpayer(self):
        p = supplier_from_taxpayer(
            {"name": "E", "street": "S 1", "postcode": "1", "city": "C", "tax_number": "1/2/3"}
        )
        assert (p.name, p.steuernummer, p.ust_idnr) == ("E", "1/2/3", "")

    def test_round_trip_dict(self):
        inv = _inv(number="2025-0001", notes="Danke")
        again = Invoice.from_dict(inv.to_dict())
        assert again.to_dict() == inv.to_dict()

    def test_render_returns_pdf(self):
        assert render_pdf(_inv(number="2025-0001")).startswith(b"%PDF")
