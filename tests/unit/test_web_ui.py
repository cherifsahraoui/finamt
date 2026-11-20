"""
Tests for the server-rendered UI under /app (UI-1 … UI-4, UI-7).

Offline: projects live in a temp FINAMT_HOME; the receipt agent and ERiC are replaced by fakes.
The live-submission flag is never set (AGENTS.md rule 6); the page's own check is patched.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from finamt.models import Counterparty, ExtractionResult, ReceiptCategory, ReceiptData, ReceiptType
from finamt.storage import project as project_mod
from finamt.storage.sqlite import SQLiteRepository
from finamt.tax.safety import LIVE_SUBMISSION_ENV
from finamt.ui.web import helpers as h

PROJEKT = "testprojekt"


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(project_mod, "FINAMT_HOME", tmp_path)
    monkeypatch.delenv("FINAMT_PROJECT", raising=False)
    monkeypatch.delenv(LIVE_SUBMISSION_ENV, raising=False)
    return tmp_path


@pytest.fixture
def client(home):
    from finamt.ui.api import app

    return TestClient(app)


def _layout():
    return project_mod.resolve_project(PROJEKT, env_var=False)


def _receipt(
    *,
    total="119.00",
    vat="19.00",
    pct="19",
    typ="purchase",
    cat="software",
    when=datetime(2025, 2, 14),
    name="Test GmbH",
    sub=None,
) -> ReceiptData:
    r = ReceiptData(
        raw_text=f"Test {uuid.uuid4()}",
        receipt_type=ReceiptType(typ),
        counterparty=Counterparty(name=name),
        receipt_date=when,
        total_amount=Decimal(total),
        vat_amount=Decimal(vat),
        vat_percentage=Decimal(pct),
        category=ReceiptCategory(cat),
        subcategory=sub,
    )
    r.validate()
    return r


def _save(*receipts: ReceiptData) -> None:
    layout = _layout()
    layout.create_dirs()
    with SQLiteRepository(db_path=layout.db_path) as repo:
        for r in receipts:
            repo.save(r)


def _set_meta(key: str, value: dict) -> None:
    layout = _layout()
    layout.create_dirs()
    with SQLiteRepository(db_path=layout.db_path) as repo:
        repo.set_metadata(key, value)


def _get(client, path, **params):
    return client.get(path, params={"projekt": PROJEKT, **params})


TEST_TAXPAYER = {
    "name": "Erika Muster",
    "street": "Teststraße 1",
    "postcode": "80331",
    "city": "München",
    "state": "Bayern",
    "tax_number": "198/113/10010",  # ERiC test number, Finanzamt 9198
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_eur_format(self):
        assert h.eur(Decimal("1234.5")) == "1.234,50 €"
        assert h.eur(Decimal("-0.5")) == "-0,50 €"
        assert h.eur(None) == "—"

    @pytest.mark.parametrize(
        "text,expected",
        [("1.234,56", "1234.56"), ("1234.56", "1234.56"), ("19,00 €", "19.00"), (" 7 ", "7")],
    )
    def test_parse_betrag(self, text, expected):
        assert h.parse_betrag(text) == Decimal(expected)

    def test_parse_betrag_empty_and_bad(self):
        assert h.parse_betrag("") is None
        with pytest.raises(ValueError, match="Kein gültiger Betrag"):
            h.parse_betrag("zwölf")

    def test_frist_quarter_and_month(self):
        # 10th day after the period ends (§ 18 Abs. 1 S. 1 UStG)
        assert h.ustva_frist(h.zeitraum(2026, "q1"), False) == date(2026, 4, 10)
        assert h.ustva_frist(h.zeitraum(2026, "m12"), False) == date(2027, 1, 10)
        # Dauerfristverlängerung: one month later (§ 46 UStDV)
        assert h.ustva_frist(h.zeitraum(2026, "q4"), True) == date(2027, 2, 10)

    def test_naechste_ustva(self):
        z, frist = h.naechste_ustva(date(2026, 4, 11), monatlich=False, dauerfrist=False)
        assert (z.key, z.jahr, frist) == ("q2", 2026, date(2026, 7, 10))
        z, frist = h.naechste_ustva(date(2026, 4, 10), monatlich=False, dauerfrist=False)
        assert (z.key, frist) == ("q1", date(2026, 4, 10))
        z, _ = h.naechste_ustva(date(2026, 1, 5), monatlich=True, dauerfrist=False)
        assert (z.key, z.jahr) == ("m12", 2025)

    def test_zeitraum_rejects_garbage(self):
        assert h.zeitraum(2026, "q5") is None
        assert h.zeitraum(2026, "m13") is None
        assert h.zeitraum(2026, "x") is None

    def test_invalid_project_name_falls_back(self, home):
        assert h.resolve("../etc").name == "default"


# ---------------------------------------------------------------------------
# UI-1: skeleton and receipt list
# ---------------------------------------------------------------------------


class TestSkeleton:
    @pytest.mark.parametrize(
        "path,text",
        [
            ("/app", "Nächste UStVA"),
            ("/app/belege", "Keine Belege"),
            ("/app/ustva", "Umsatzsteuer-Voranmeldung"),
            ("/app/euer", "Einnahmenüberschussrechnung"),
            ("/app/rechnungen", "INV-1"),
            ("/app/stammdaten", "Bundesland"),
        ],
    )
    def test_pages_render_for_empty_project(self, client, home, path, text):
        resp = _get(client, path)
        assert resp.status_code == 200
        assert text in resp.text
        assert not (home / PROJEKT / "finamt.db").exists()  # reading never creates a DB

    def test_navigation_and_project_selector(self, client, home):
        (home / "default").mkdir()
        (home / "zweites").mkdir()
        html = _get(client, "/app").text
        for label in ("Übersicht", "Belege", "UStVA", "EÜR", "Rechnungen", "Stammdaten"):
            assert f">{label}</a>" in html
        assert '<option value="zweites"' in html
        assert f'<option value="{PROJEKT}" selected' in html

    def test_static_files(self, client):
        assert client.get("/app/static/app.css").status_code == 200
        assert "htmx" in client.get("/app/static/htmx.min.js").text[:200]

    def test_old_ui_still_served(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert '<div id="root">' in resp.text


class TestBelegeList:
    def test_list_with_amounts_and_eur_line(self, client):
        _save(
            _receipt(name="Softwarehaus"),
            _receipt(typ="sale", cat="services", name="Kunde AG", total="1190.00", vat="190.00"),
        )
        html = _get(client, "/app/belege", jahr=2025).text
        assert "Softwarehaus" in html and "Kunde AG" in html
        assert "1.190,00 €" in html
        assert "Kz 228" in html  # software purchase (Anlage EÜR 2025)
        assert "Kz 112" in html  # taxable sale
        assert "2 Beleg(e)" in html

    def test_filters(self, client):
        _save(
            _receipt(name="Januar-Beleg", when=datetime(2025, 1, 10)),
            _receipt(name="Mai-Beleg", when=datetime(2025, 5, 10)),
            _receipt(name="Verkauf", typ="sale", cat="services", when=datetime(2025, 1, 20)),
        )
        q1 = _get(client, "/app/belege", jahr=2025, zeitraum="q1").text
        assert "Januar-Beleg" in q1 and "Mai-Beleg" not in q1
        sales = _get(client, "/app/belege", jahr=2025, typ="sale").text
        assert "Verkauf" in sales and "Januar-Beleg" not in sales
        cat = _get(client, "/app/belege", jahr=2025, kategorie="services").text
        assert "Verkauf" in cat and "Mai-Beleg" not in cat

    def test_warnings_and_review_filter(self, client):
        _save(
            _receipt(name="Sauber"),
            _receipt(name="Zukunft", when=datetime(2099, 1, 1)),
            _receipt(name="Laptop", cat="equipment", total="1190.00", vat="190.00"),
        )
        html = _get(client, "/app/belege", jahr=2099).text
        assert "Future date" in html
        review = _get(client, "/app/belege", jahr=2025, pruefen="1").text
        assert "Laptop" in review and "Sauber" not in review
        assert "ZU PRÜFEN" in review


# ---------------------------------------------------------------------------
# UI-2: upload, edit, delete
# ---------------------------------------------------------------------------


class _FakeAgent:
    """Stands in for FinanceAgent: saves a fixed receipt, no OCR/LLM."""

    calls: list = []

    def __init__(self, db_path, config=None, agents_cfg=None):
        self.db_path = db_path

    def process_receipt(self, path, receipt_type="purchase"):
        _FakeAgent.calls.append((path.suffix, receipt_type))
        r = _receipt(name="Hochgeladen GmbH", typ=receipt_type)
        with SQLiteRepository(db_path=self.db_path) as repo:
            repo.save(r)
        return ExtractionResult(success=True, data=r)


class TestUpload:
    def test_upload_runs_pipeline_and_lists_result(self, client, monkeypatch):
        import finamt.ui.api as api

        _FakeAgent.calls = []
        monkeypatch.setattr(api, "FinanceAgent", _FakeAgent)
        resp = client.post(
            "/app/belege/upload",
            params={"projekt": PROJEKT},
            data={"typ": "sale"},
            files=[("dateien", ("rechnung.pdf", b"%PDF-1.4 test", "application/pdf"))],
        )
        assert resp.status_code == 200
        assert "gespeichert" in resp.text
        assert _FakeAgent.calls == [(".pdf", "sale")]
        assert "Hochgeladen GmbH" in _get(client, "/app/belege", jahr=2025).text

    def test_upload_rejects_wrong_type(self, client, monkeypatch):
        import finamt.ui.api as api

        _FakeAgent.calls = []
        monkeypatch.setattr(api, "FinanceAgent", _FakeAgent)
        resp = client.post(
            "/app/belege/upload",
            params={"projekt": PROJEKT},
            data={"typ": "purchase"},
            files=[("dateien", ("notiz.txt", b"hallo", "text/plain"))],
        )
        assert "nicht erlaubt" in resp.text
        assert _FakeAgent.calls == []

    def test_upload_shows_extraction_failure(self, client, monkeypatch):
        import finamt.ui.api as api

        class Failing(_FakeAgent):
            def process_receipt(self, path, receipt_type="purchase"):
                return ExtractionResult(success=False, error_message="kein Text")

        monkeypatch.setattr(api, "FinanceAgent", Failing)
        resp = client.post(
            "/app/belege/upload",
            params={"projekt": PROJEKT},
            files=[("dateien", ("a.pdf", b"%PDF", "application/pdf"))],
        )
        assert "Auslesen fehlgeschlagen: kein Text" in resp.text


class TestEdit:
    def test_edit_page_shows_eur_line_and_values(self, client):
        r = _receipt(name="Softwarehaus")
        _save(r)
        html = _get(client, f"/app/belege/{r.id}").text
        assert "Kz 228" in html
        assert 'value="119,00"' in html
        assert "/receipts/" in html and "/pdf" in html

    def test_save_german_amounts_and_recompute_warnings(self, client):
        r = _receipt(name="Alt")
        _save(r)
        resp = client.post(
            f"/app/belege/{r.id}",
            params={"projekt": PROJEKT},
            data={
                "receipt_type": "purchase",
                "receipt_date": "2025-03-01",
                "counterparty_name": "Neu GmbH",
                "category": "software",
                "total_amount": "1.190,00",
                "vat_percentage": "19",
                "vat_amount": "190,00",
                "private_use_percent": "20",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        with SQLiteRepository(db_path=_layout().db_path) as repo:
            saved = repo.get(r.id)
        assert saved.total_amount == Decimal("1190.00")
        assert saved.vat_amount == Decimal("190.00")
        assert saved.private_use_share == Decimal("0.2")
        assert saved.receipt_date.date() == date(2025, 3, 1)
        assert saved.vendor == "Neu GmbH"
        assert saved.validation_warnings == []

        # A negative total produces a warning that the list shows
        client.post(
            f"/app/belege/{r.id}",
            params={"projekt": PROJEKT},
            data={"receipt_type": "purchase", "category": "software", "total_amount": "-5"},
        )
        with SQLiteRepository(db_path=_layout().db_path) as repo:
            assert repo.get(r.id).validation_warnings

    def test_bad_amount_shows_error_and_keeps_data(self, client):
        r = _receipt()
        _save(r)
        resp = client.post(
            f"/app/belege/{r.id}",
            params={"projekt": PROJEKT},
            data={"receipt_type": "purchase", "total_amount": "viel"},
        )
        assert resp.status_code == 200
        assert "Kein gültiger Betrag" in resp.text
        with SQLiteRepository(db_path=_layout().db_path) as repo:
            assert repo.get(r.id).total_amount == Decimal("119.00")

    def test_delete(self, client):
        r = _receipt()
        _save(r)
        resp = client.post(f"/app/belege/{r.id}/loeschen", params={"projekt": PROJEKT})
        assert resp.status_code == 200
        assert "Beleg gelöscht" in resp.text
        assert _get(client, f"/app/belege/{r.id}").status_code == 404


# ---------------------------------------------------------------------------
# UI-3: UStVA and annual USt
# ---------------------------------------------------------------------------


class TestUStVA:
    def test_preview_kennzahlen(self, client):
        _save(
            _receipt(typ="sale", cat="services", total="1190.00", vat="190.00"),
            _receipt(total="119.00", vat="19.00"),
        )
        html = _get(client, "/app/ustva", jahr=2025, zeitraum="q1").text
        assert "Q1 2025" in html
        assert re.search(r">81</span>.*?>1000<", html, re.S)
        assert re.search(r">66</span>.*?>19.00<", html, re.S)
        assert re.search(r">83</span>.*?>171.00<", html, re.S)
        assert "10.04.2025" in html  # deadline

    def test_live_button_only_when_allowed(self, client, monkeypatch):
        import finamt.ui.web.routes as routes

        assert 'value="live"' not in _get(client, "/app/ustva", jahr=2025, zeitraum="q1").text
        monkeypatch.setattr(routes, "live_submission_allowed", lambda: True)
        assert 'value="live"' in _get(client, "/app/ustva", jahr=2025, zeitraum="q1").text

    def test_live_post_is_refused_by_backend_gate(self, client):
        _set_meta("taxpayer", TEST_TAXPAYER)
        resp = client.post(
            "/app/ustva",
            params={"projekt": PROJEKT},
            data={"jahr": "2025", "zeitraum": "q1", "aktion": "live"},
        )
        assert resp.status_code == 200
        assert "Live ELSTER submission is disabled" in resp.text
        assert LIVE_SUBMISSION_ENV in resp.text

    def test_missing_stammdaten(self, client):
        resp = client.post(
            "/app/ustva",
            params={"projekt": PROJEKT},
            data={"jahr": "2025", "zeitraum": "q1", "aktion": "pruefen"},
        )
        assert "Stammdaten unvollständig: Bundesland fehlt." in resp.text

    def test_validate_passes_computed_elster_fields(self, client, monkeypatch):
        import finamt.ui.api as api

        _set_meta("taxpayer", TEST_TAXPAYER)
        _set_meta("elster_misc", {"hersteller_id": "12345", "cert_pin": "geheim"})
        seen = {}

        def fake_submit(body, db=None):
            seen["body"], seen["db"] = body, db
            return {"success": True, "validate_only": True, "message": "ok"}

        monkeypatch.setattr(api, "post_ustva_submit", fake_submit)
        resp = client.post(
            "/app/ustva",
            params={"projekt": PROJEKT},
            data={"jahr": "2026", "zeitraum": "m03", "aktion": "pruefen"},
        )
        assert "ERiC-Prüfung ohne Fehler" in resp.text
        b = seen["body"]
        assert (b.steuernummer, b.finanzamt_nr, b.bundesland_kz) == ("9198011310010", "9198", "09")
        assert (b.year, b.month, b.quarter) == (2026, 3, None)
        assert b.validate_only and b.use_test
        assert (b.hersteller_id, b.cert_password) == ("12345", "geheim")
        assert seen["db"] == str(_layout().db_path)

    def test_annual_test_send(self, client, monkeypatch):
        import finamt.ui.api as api

        _set_meta("taxpayer", TEST_TAXPAYER)
        seen = {}

        def fake_submit(body, db=None):
            seen["body"] = body
            return {"success": True, "telenummer": "T-1"}

        monkeypatch.setattr(api, "post_uste_submit", fake_submit)
        resp = client.post(
            "/app/ustva",
            params={"projekt": PROJEKT},
            data={
                "jahr": "2025",
                "zeitraum": "jahr",
                "aktion": "test",
                "besteuerungsart": "2",
                "vorauszahlungssoll": "1.234,56",
            },
        )
        assert "Testfall gesendet" in resp.text and "T-1" in resp.text
        b = seen["body"]
        assert b.use_test and not b.validate_only
        assert b.besteuerungsart == "2"
        assert Decimal(str(b.vorauszahlungssoll)) == Decimal("1234.56")

    def test_submissions_listed(self, client):
        _set_meta("submissions", [{"type": "ustva_q1", "year": 2025, "telenummer": "ET123"}])
        assert "ET123" in _get(client, "/app/ustva", jahr=2025, zeitraum="q1").text


# ---------------------------------------------------------------------------
# UI-4: EÜR
# ---------------------------------------------------------------------------


class TestEuer:
    def test_year_view_and_review_list(self, client):
        laptop = _receipt(name="Laptop-Shop", cat="equipment", total="1190.00", vat="190.00")
        _save(
            _receipt(name="Softwarehaus"),
            _receipt(typ="sale", cat="services", total="1190.00", vat="190.00"),
            laptop,
        )
        html = _get(client, "/app/euer", jahr=2025).text
        assert ">228</span>" in html and ">112</span>" in html
        assert "1.000,00 €" in html
        assert "Laptop-Shop" in html
        assert f"/app/belege/{laptop.id}" in html
        # Gewinn = 1000 − 100; the laptop is not counted
        assert "900,00 €" in html

    def test_json_download(self, client):
        _save(_receipt())
        resp = _get(client, "/app/euer/2025.json")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        assert resp.json()["year"] == 2025


# ---------------------------------------------------------------------------
# UI-7: Stammdaten
# ---------------------------------------------------------------------------


class TestStammdaten:
    def test_select_has_16_laender(self, client):
        html = _get(client, "/app/stammdaten").text
        select = re.search(r'<select name="state".*?</select>', html, re.S).group(0)
        assert len(re.findall(r'<option value="[^"]+"', select)) == 16

    def test_save_shows_13_digit_number_and_old_ui_reads_it(self, client):
        resp = client.post(
            "/app/stammdaten/steuerpflichtiger",
            params={"projekt": PROJEKT},
            data={**TEST_TAXPAYER, "vat_id": "de 123456789"},
        )
        assert resp.status_code == 200
        assert "9198011310010" in resp.text
        assert ">9198<" in resp.text
        old = client.get("/taxpayer", params={"db": str(_layout().db_path)}).json()["taxpayer"]
        assert old["state"] == "Bayern"
        assert old["tax_number"] == "198/113/10010"
        assert old["vat_id"] == "DE123456789"

    def test_keeps_fields_written_by_old_ui(self, client):
        _set_meta("taxpayer", {**TEST_TAXPAYER, "gegenstand": "IT-Beratung"})
        client.post(
            "/app/stammdaten/steuerpflichtiger",
            params={"projekt": PROJEKT},
            data=TEST_TAXPAYER,
        )
        assert h.get_meta(_layout(), "taxpayer")["gegenstand"] == "IT-Beratung"

    def test_htmx_partial_names_the_error(self, client):
        resp = client.get(
            "/app/stammdaten/steuernummer",
            params={"state": "Bayern", "tax_number": "123/4567"},
        )
        assert "7 Ziffern" in resp.text
        assert "Bundesland erforderlich" not in resp.text
        ok = client.get(
            "/app/stammdaten/steuernummer",
            params={"state": "Bayern", "tax_number": "198/113/10010"},
        )
        assert "9198011310010" in ok.text

    def test_unknown_old_state_value_is_flagged(self, client):
        _set_meta("taxpayer", {**TEST_TAXPAYER, "state": "Bay."})
        assert "nicht eindeutig" in _get(client, "/app/stammdaten").text

    def test_elster_settings_pin_never_shown(self, client):
        resp = client.post(
            "/app/stammdaten/elster",
            params={"projekt": PROJEKT},
            data={"hersteller_id": "12345", "cert_pin": "sehr-geheim-4711", "eric_home": "C:/eric"},
            files={"zertifikat": ("mein.pfx", b"PFXDATA", "application/x-pkcs12")},
        )
        assert resp.status_code == 200
        assert "sehr-geheim-4711" not in resp.text
        assert 'placeholder="gespeichert"' in resp.text
        # Same storage the old UI and the submit routes read
        settings = client.get("/tax/ebilanz/settings", params={"db": str(_layout().db_path)}).json()
        assert settings["hersteller_id"] == "12345"
        assert settings["cert_pin"] == "sehr-geheim-4711"
        assert settings["eric_home"] == "C:/eric"
        assert (_layout().root / "elster_cert.pfx").read_bytes() == b"PFXDATA"

        # An empty PIN field keeps the stored PIN
        client.post(
            "/app/stammdaten/elster",
            params={"projekt": PROJEKT},
            data={"hersteller_id": "12345", "cert_pin": ""},
        )
        assert h.get_meta(_layout(), "elster_misc")["cert_pin"] == "sehr-geheim-4711"

    def test_period_settings_drive_overview(self, client):
        client.post(
            "/app/stammdaten/zeitraum",
            params={"projekt": PROJEKT},
            data={"monatlich": "1", "dauerfrist": "1"},
        )
        html = _get(client, "/app").text
        assert "monatlich, mit Dauerfristverlängerung" in html
