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
from pathlib import Path

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


@pytest.fixture(autouse=True)
def upload_jobs(monkeypatch):
    """Upload jobs run inline (no thread) and start from a clean state in every test."""
    from finamt.ui.web import uploads

    uploads.reset()
    monkeypatch.setattr(uploads, "_spawn", lambda fn: fn())
    yield uploads
    uploads.reset()


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
            ("/app/rechnungen", "Neue Rechnung"),
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
        (
            home / "zweites" / "finamt.db"
        ).touch()  # a project has a database (bare folders are leftovers)
        html = _get(client, "/app").text
        for label in ("Übersicht", "Belege", "UStVA", "EÜR", "Rechnungen", "Stammdaten"):
            assert f">{label}</a>" in html
        assert '<option value="zweites"' in html
        assert f'<option value="{PROJEKT}" selected' in html

    def test_static_files(self, client):
        assert client.get("/app/static/app.css").status_code == 200
        assert "htmx" in client.get("/app/static/htmx.min.js").text[:200]

    def test_start_page_is_new_ui(self, client):
        # UI-6: "/" opens /app
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 307
        assert resp.headers["location"] == "/app"
        assert '<nav class="sidebar"' in client.get("/").text

    def test_old_ui_moved_to_legacy_path(self, client):
        for path in ("/legacy-ui", "/legacy-ui/", "/legacy-ui/anything"):
            resp = client.get(path)
            assert resp.status_code == 200, path
            assert '<div id="root">' in resp.text
        assert 'href="/legacy-ui"' in _get(client, "/app").text

    def test_old_ui_assets_keep_their_urls(self, client):
        assert client.get("/finamt_icon.svg").status_code == 200
        from finamt.ui.api import STATIC_DIR

        js = next((STATIC_DIR / "assets").glob("*.js")).name
        assert client.get(f"/assets/{js}").status_code == 200

    def test_unknown_path_is_404_not_old_ui(self, client):
        resp = client.get("/no-such-page")
        assert resp.status_code == 404
        assert '<div id="root">' not in resp.text

    def test_static_path_traversal_refused(self, client):
        assert client.get("/..%2F..%2Fapi.py").status_code == 404


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
        assert resp.status_code == 200  # redirected to the job page
        assert "/app/belege/upload" in str(resp.url)
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


def _start_running_job(uploads, monkeypatch, n=1):
    """A job that stays "running": _spawn does nothing."""
    monkeypatch.setattr(uploads, "_spawn", lambda fn: None)
    items = [uploads.UploadItem(name=f"r{i}.pdf", path=None) for i in range(n)]
    uploads.start(PROJEKT, "purchase", items, lambda p, t: (None, "", {}))
    return items


def _upload(client, name="a.pdf"):
    return client.post(
        "/app/belege/upload",
        params={"projekt": PROJEKT},
        files=[("dateien", (name, b"%PDF", "application/pdf"))],
    )


class TestUploadJob:
    """The upload runs as a background job: progress on every page, one job at a time."""

    def test_progress_shown_on_other_pages_and_polls(self, client, upload_jobs, monkeypatch):
        items = _start_running_job(upload_jobs, monkeypatch, n=3)
        items[0].status = upload_jobs.FERTIG
        for path in ("/app", "/app/euer", "/app/stammdaten"):
            html = _get(client, path).text
            assert "Belege werden ausgelesen: 1 von 3 fertig" in html, path
            assert 'hx-trigger="every 2s"' in html

    def test_new_upload_refused_while_running(self, client, upload_jobs, monkeypatch):
        import finamt.ui.api as api

        _start_running_job(upload_jobs, monkeypatch)
        _FakeAgent.calls = []
        monkeypatch.setattr(api, "FinanceAgent", _FakeAgent)
        resp = _upload(client, "b.pdf")
        assert "Es läuft schon ein Upload" in resp.text
        assert _FakeAgent.calls == []
        assert [i.name for i in upload_jobs.current().items] == ["r0.pdf"]

    def test_upload_form_locked_while_running(self, client, upload_jobs, monkeypatch):
        _start_running_job(upload_jobs, monkeypatch)
        html = _get(client, "/app/belege").text
        assert re.search(r"<fieldset[^>]*data-upload-gesperrt[^>]*disabled", html)
        assert "Gesperrt, bis der laufende Upload fertig ist." in html

    def test_status_partial_stops_polling_when_done(self, client, monkeypatch):
        import finamt.ui.api as api

        monkeypatch.setattr(api, "FinanceAgent", _FakeAgent)
        _upload(client)
        html = _get(client, "/app/belege/upload/status").text
        assert "Upload fertig:" in html
        assert "1 gespeichert" in html
        assert "every 2s" not in html
        assert not re.search(r"<fieldset[^>]*disabled", _get(client, "/app/belege").text)

    def test_results_stay_until_dismissed(self, client, upload_jobs, monkeypatch):
        import finamt.ui.api as api

        monkeypatch.setattr(api, "FinanceAgent", _FakeAgent)
        _upload(client)
        assert "Upload fertig:" in _get(client, "/app/euer").text
        job = upload_jobs.current()
        resp = client.post(
            "/app/belege/upload/ausblenden",
            params={"projekt": PROJEKT},
            data={"job": job.id, "zurueck": "/app/euer?projekt=" + PROJEKT},
        )
        assert str(resp.url).endswith("/app/euer?projekt=" + PROJEKT)
        assert upload_jobs.current() is None
        assert "Upload fertig:" not in resp.text

    def test_dismiss_ignores_foreign_redirect(self, client):
        resp = client.post(
            "/app/belege/upload/ausblenden",
            params={"projekt": PROJEKT},
            data={"job": "x", "zurueck": "https://evil.example/"},
            follow_redirects=False,
        )
        assert resp.headers["location"].startswith("/app/belege")

    def test_pipeline_exception_is_reported(self, client, monkeypatch):
        import finamt.ui.api as api

        class Boom(_FakeAgent):
            def process_receipt(self, path, receipt_type="purchase"):
                raise RuntimeError("OCR kaputt")

        monkeypatch.setattr(api, "FinanceAgent", Boom)
        assert "Fehler: OCR kaputt" in _upload(client).text


class TestSprache:
    def test_default_is_german(self, client):
        html = _get(client, "/app/belege").text
        assert '<html lang="de">' in html
        assert "Belege hochladen" in html

    def test_toggle_sets_cookie_and_returns(self, client):
        resp = client.get(
            "/app/sprache",
            params={"lang": "en", "zurueck": f"/app/belege?projekt={PROJEKT}"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == f"/app/belege?projekt={PROJEKT}"
        assert "freibuch_lang=en" in resp.headers["set-cookie"]

    def test_english_pages(self, client):
        client.cookies.set("freibuch_lang", "en")
        html = _get(client, "/app/belege").text
        assert '<html lang="en">' in html
        assert "Upload receipts" in html
        assert "Belege hochladen" not in html
        for path, text in (
            ("/app", "Next VAT return"),
            ("/app/euer", "Business income"),
            ("/app/ustva", "Form lines"),
            ("/app/stammdaten", "Federal state"),
        ):
            assert text in _get(client, path).text, path

    def test_toggle_shown_with_current_language(self, client):
        html = _get(client, "/app").text
        assert 'href="/app/sprache?lang=en&amp;zurueck=' in html
        assert re.search(r'hreflang="de"[^>]*aria-current="true"', html)

    def test_unknown_language_falls_back(self, client):
        client.cookies.set("freibuch_lang", "xx")
        assert '<html lang="de">' in _get(client, "/app").text

    def test_foreign_redirect_refused(self, client):
        resp = client.get(
            "/app/sprache",
            params={"lang": "en", "zurueck": "//evil.example"},
            follow_redirects=False,
        )
        assert resp.headers["location"] == "/app"

    def test_every_template_text_has_english(self):
        from pathlib import Path

        from finamt.ui.web import i18n

        tpl = Path(i18n.__file__).parent / "templates"
        pattern = re.compile(r"""_\(\s*(?:"([^"]+)"|'([^']+)')""")
        missing = set()
        for f in tpl.glob("*.html"):
            for m in pattern.finditer(f.read_text(encoding="utf-8")):
                key = m.group(1) or m.group(2)
                if key not in i18n.EN:
                    missing.add(key)
        assert not missing, sorted(missing)

    def test_python_side_labels_have_english(self):
        from finamt.ui.web import i18n, routes

        labels = [*routes.KZ_LABELS.values(), *routes.TYP_LABELS.values()]
        labels += [v for _k, v in routes.BESTEUERUNGSARTEN] + list(h.EUER_WAHL.values())
        assert [x for x in labels if x not in i18n.EN] == []


class TestKleinunternehmerJahre:
    def test_saved_years_switch_euer_mode(self, client):
        _save(_receipt(typ="sale", cat="services", total="1190.00", vat="190.00"))
        assert ">140</span>" in _get(client, "/app/euer", jahr=2025).text
        client.post(
            "/app/stammdaten/kleinunternehmer", params={"projekt": PROJEKT}, data={"jahre": "2025"}
        )
        html = _get(client, "/app/euer", jahr=2025).text
        assert ">111</span>" in html
        assert ">140</span>" not in html
        assert "1.190,00 €" in html
        assert 'value="2025"' in _get(client, "/app/stammdaten").text

    def test_bad_years_show_error(self, client):
        resp = client.post(
            "/app/stammdaten/kleinunternehmer", params={"projekt": PROJEKT}, data={"jahre": "25"}
        )
        assert "Bitte Jahreszahlen mit vier Ziffern" in resp.text

    def test_period_setting_keeps_years(self, client):
        client.post(
            "/app/stammdaten/kleinunternehmer", params={"projekt": PROJEKT}, data={"jahre": "2024"}
        )
        client.post(
            "/app/stammdaten/zeitraum", params={"projekt": PROJEKT}, data={"monatlich": "1"}
        )
        assert 'value="2024"' in _get(client, "/app/stammdaten").text


class TestEdit:
    def test_edit_page_shows_eur_line_and_values(self, client):
        r = _receipt(name="Softwarehaus")
        _save(r)
        html = _get(client, f"/app/belege/{r.id}").text
        assert "Kz 228" in html
        assert 'value="119,00"' in html
        assert "Kein Original (manuell erfasst)." in html  # no stored file for this receipt

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
        # Gewinn = 1000 + 190 (Kz 140) − 100 − 19 (Kz 185); the laptop is not counted
        assert ">140</span>" in html and ">185</span>" in html
        assert "1.071,00 €" in html

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


# ---------------------------------------------------------------------------
# Two Steuernummern (Umsatzsteuer / Einkommensteuer)
# ---------------------------------------------------------------------------

UST_NR, UST_13 = "198/113/10010", "9198011310010"
EST_NR, EST_13 = "101/123/45677", "9101012345677"  # ERiC-confirmed (test_bundesland.py)


class TestZweiSteuernummern:
    def test_one_number_is_used_for_everything(self):
        tp = {"state": "Bayern", "tax_number": UST_NR}
        for zweck in ("ust", "est", "euer"):
            assert h.steuernummer_fuer(tp, zweck).elster13 == UST_13

    def test_two_numbers_need_an_euer_choice(self):
        tp = {"state": "Bayern", "tax_number": UST_NR, "tax_number_est": EST_NR}
        assert h.steuernummer_fuer(tp, "ust").elster13 == UST_13
        assert h.steuernummer_fuer(tp, "est").elster13 == EST_13
        assert "festlegen" in h.steuernummer_fuer(tp, "euer").fehler
        assert h.steuernummer_fuer({**tp, "euer_steuernummer": "est"}, "euer").elster13 == EST_13
        assert h.steuernummer_fuer({**tp, "euer_steuernummer": "ust"}, "euer").elster13 == UST_13

    def test_same_number_twice_needs_no_choice(self):
        tp = {"state": "Bayern", "tax_number": UST_NR, "tax_number_est": UST_13}
        assert h.steuernummer_fuer(tp, "euer").elster13 == UST_13

    def test_stammdaten_save_and_show_both(self, client):
        resp = client.post(
            "/app/stammdaten/steuerpflichtiger",
            params={"projekt": PROJEKT},
            data={**TEST_TAXPAYER, "tax_number_est": EST_NR, "euer_steuernummer": "est"},
        )
        assert UST_13 in resp.text and EST_13 in resp.text
        assert "Bitte auswählen" not in resp.text
        tp = h.get_meta(_layout(), "taxpayer")
        assert (tp["tax_number"], tp["tax_number_est"], tp["euer_steuernummer"]) == (
            UST_NR,
            EST_NR,
            "est",
        )
        # The old UI keeps reading the Umsatzsteuer number for UStVA
        old = client.get("/taxpayer", params={"db": str(_layout().db_path)}).json()["taxpayer"]
        assert old["tax_number"] == UST_NR

    def test_missing_choice_is_flagged(self, client):
        _set_meta("taxpayer", {**TEST_TAXPAYER, "tax_number_est": EST_NR})
        assert "Bitte auswählen" in _get(client, "/app/stammdaten").text
        euer = _get(client, "/app/euer", jahr=2025).text
        assert "festlegen" in euer

    def test_euer_page_shows_chosen_number(self, client):
        _set_meta(
            "taxpayer", {**TEST_TAXPAYER, "tax_number_est": EST_NR, "euer_steuernummer": "est"}
        )
        assert EST_13 in _get(client, "/app/euer", jahr=2025).text

    def test_ustva_sends_the_umsatzsteuer_number(self, client, monkeypatch):
        import finamt.ui.api as api

        _set_meta(
            "taxpayer", {**TEST_TAXPAYER, "tax_number_est": EST_NR, "euer_steuernummer": "est"}
        )
        seen = {}
        monkeypatch.setattr(
            api, "post_ustva_submit", lambda body, db=None: seen.update(b=body) or {"success": 1}
        )
        client.post(
            "/app/ustva",
            params={"projekt": PROJEKT},
            data={"jahr": "2026", "zeitraum": "q1", "aktion": "pruefen"},
        )
        assert seen["b"].steuernummer == UST_13

    def test_partial_for_est_field(self, client):
        empty = client.get("/app/stammdaten/steuernummer", params={"state": "Bayern", "art": "est"})
        assert "Umsatzsteuer-Nummer gilt für alles" in empty.text
        ok = client.get(
            "/app/stammdaten/steuernummer",
            params={"state": "Bayern", "tax_number_est": EST_NR, "art": "est"},
        )
        assert EST_13 in ok.text


# ---------------------------------------------------------------------------
# UI-8: manual entry, projects, partners, XML download, archive
# ---------------------------------------------------------------------------


def _manuell(client, **data):
    felder = {
        "receipt_type": "purchase",
        "receipt_date": "2025-03-04",
        "counterparty_name": "Bäckerei Korn",
        "category": "travel",
        "total_amount": "11,90",
        "vat_percentage": "19",
    }
    felder.update(data)
    return client.post("/app/belege/neu", params={"projekt": PROJEKT}, data=felder)


def _alle(layout=None):
    with SQLiteRepository(db_path=(layout or _layout()).db_path) as repo:
        return list(repo.list_all())


class TestManuelleErfassung:
    def test_form_on_belege_page(self, client):
        html = _get(client, "/app/belege").text
        assert "Beleg manuell erfassen" in html
        assert 'action="/app/belege/neu?projekt=testprojekt"' in html

    def test_creates_receipt_with_vat_from_rate(self, client):
        resp = _manuell(client)
        assert resp.status_code == 200
        assert "Gespeichert." in resp.text
        assert "Kein Original (manuell erfasst)." in resp.text
        [r] = _alle()
        assert r.vendor == "Bäckerei Korn"
        assert r.total_amount == Decimal("11.90")
        assert r.vat_amount == Decimal("1.90")
        assert str(r.category) == "travel"
        assert r.receipt_date.date() == date(2025, 3, 4)

    def test_explicit_vat_kept(self, client):
        _manuell(client, vat_amount="1,50")
        assert _alle()[0].vat_amount == Decimal("1.50")

    def test_two_identical_entries_are_two_receipts(self, client):
        _manuell(client)
        _manuell(client)
        assert len(_alle()) == 2

    @pytest.mark.parametrize(
        "feld,wert,text",
        [
            ("total_amount", "", "Bruttobetrag fehlt."),
            ("total_amount", "abc", "Kein gültiger Betrag"),
            ("counterparty_name", " ", "Partner fehlt."),
            ("receipt_date", "", "Datum fehlt."),
        ],
    )
    def test_invalid_input_shows_error(self, client, feld, wert, text):
        resp = _manuell(client, **{feld: wert})
        assert "Nicht angelegt:" in resp.text
        assert text in resp.text
        assert '<details class="card" id="manuell" open>' in resp.text
        assert _alle() == []

    def test_original_shown_when_file_stored(self, client, monkeypatch):
        import finamt.ui.api as api

        r = _receipt()
        _save(r)
        monkeypatch.setattr(api, "_find_stored_file", lambda rid, db: Path("x.pdf"))
        html = _get(client, f"/app/belege/{r.id}").text
        assert f"/receipts/{r.id}/pdf" in html


class TestProjekte:
    def test_create_switches_to_new_project(self, client):
        resp = client.post("/app/projekte", params={"projekt": PROJEKT}, data={"name": "neu-2026"})
        assert "Projekt angelegt." in resp.text
        assert "projekt=neu-2026" in str(resp.url)
        assert "neu-2026" in _get(client, "/app/projekte").text

    def test_invalid_name_shows_error(self, client):
        resp = client.post("/app/projekte", params={"projekt": PROJEKT}, data={"name": "../x"})
        assert 'class="notice err"' in resp.text

    def test_duplicate_name_shows_error(self, client):
        client.post("/app/projekte", params={"projekt": PROJEKT}, data={"name": "doppelt"})
        resp = client.post("/app/projekte", params={"projekt": PROJEKT}, data={"name": "doppelt"})
        assert "already exists" in resp.text

    def test_delete_project(self, client):
        client.post("/app/projekte", params={"projekt": PROJEKT}, data={"name": "weg"})
        resp = client.post("/app/projekte/weg/loeschen", params={"projekt": "weg"})
        assert "Projekt gelöscht." in resp.text
        assert "projekt=default" in str(resp.url)
        assert not project_mod.resolve_project("weg", env_var=False).db_path.exists()

    def test_default_project_protected(self, client):
        resp = client.post("/app/projekte/default/loeschen", params={"projekt": PROJEKT})
        assert "Das Standardprojekt kann nicht gelöscht werden." in resp.text

    def test_counts_receipts(self, client):
        _save(_receipt(), _receipt())
        html = _get(client, "/app/projekte").text
        assert re.search(r"testprojekt</a>.*?<td class=\"num\">2</td>", html, re.S)


class TestPartner:
    def _ids(self):
        with SQLiteRepository(db_path=_layout().db_path) as repo:
            return {r["name"]: r for r in repo.list_all_counterparties()}

    def test_list_with_counts(self, client):
        _save(_receipt(name="Alpha GmbH"), _receipt(name="Alpha GmbH"), _receipt(name="Beta AG"))
        html = _get(client, "/app/partner").text
        assert 'value="Alpha GmbH"' in html and 'value="Beta AG"' in html
        assert '<span class="num">2</span>' in html

    def test_rename_and_verify(self, client):
        _save(_receipt(name="Alpha GmbH"))
        cp = self._ids()["Alpha GmbH"]
        resp = client.post(
            f"/app/partner/{cp['id']}",
            params={"projekt": PROJEKT},
            data={"name": "Alpha Software GmbH", "vat_id": "de 123456789", "verified": "1"},
        )
        assert "Partner gespeichert." in resp.text
        row = self._ids()["Alpha Software GmbH"]
        assert row["verified"]
        assert row["vat_id"] == "DE123456789"

    def test_merge_moves_receipts(self, client):
        _save(_receipt(name="Alpha GmbH"), _receipt(name="Alpha GmbH."), _receipt(name="Beta AG"))
        ids = self._ids()
        quelle, ziel = ids["Alpha GmbH."]["id"], ids["Alpha GmbH"]["id"]
        resp = client.post(
            f"/app/partner/{quelle}/zusammenfuehren",
            params={"projekt": PROJEKT},
            data={"ziel": ziel},
        )
        assert "Partner zusammengeführt." in resp.text
        assert "Alpha GmbH." not in self._ids()
        assert sorted(r.vendor for r in _alle()) == ["Alpha GmbH", "Alpha GmbH", "Beta AG"]

    def test_unknown_partner_404(self, client):
        _save(_receipt())
        resp = client.post("/app/partner/nope", params={"projekt": PROJEKT}, data={"name": "x"})
        assert resp.status_code == 404


class TestXmlDownload:
    def test_ustva_xml_download(self, client, monkeypatch):
        from fastapi.responses import Response as R

        import finamt.ui.api as api

        _set_meta(h.TAXPAYER_KEY, TEST_TAXPAYER)
        seen = {}

        def fake_xml(body, db=None):
            seen["body"] = body
            return R(content=b"<Elster/>", media_type="text/xml")

        monkeypatch.setattr(api, "post_ustva_xml", fake_xml)
        resp = client.post(
            "/app/ustva",
            params={"projekt": PROJEKT},
            data={"jahr": "2025", "zeitraum": "q1", "aktion": "xml"},
        )
        assert resp.status_code == 200
        assert resp.content == b"<Elster/>"
        assert 'filename="UStVA_2025_q1.xml"' in resp.headers["content-disposition"]
        assert seen["body"].use_test is True
        assert seen["body"].quarter == 1

    def test_annual_xml_download(self, client, monkeypatch):
        from fastapi.responses import Response as R

        import finamt.ui.api as api

        _set_meta(h.TAXPAYER_KEY, TEST_TAXPAYER)
        monkeypatch.setattr(api, "post_uste_xml", lambda body, db=None: R(content=b"<E50/>"))
        resp = client.post(
            "/app/ustva",
            params={"projekt": PROJEKT},
            data={"jahr": "2025", "zeitraum": "jahr", "aktion": "xml"},
        )
        assert resp.content == b"<E50/>"
        assert 'filename="USt_2025_jahr.xml"' in resp.headers["content-disposition"]

    def test_xml_needs_stammdaten(self, client):
        resp = client.post(
            "/app/ustva",
            params={"projekt": PROJEKT},
            data={"jahr": "2025", "zeitraum": "q1", "aktion": "xml"},
        )
        assert "Stammdaten unvollständig" in resp.text

    def test_button_present(self, client):
        assert 'value="xml"' in _get(client, "/app/ustva", jahr=2025, zeitraum="q1").text


class TestArchiv:
    def _submission(self):
        layout = _layout()
        layout.create_dirs()
        layout.submitted_returns_dir.mkdir(parents=True, exist_ok=True)
        (layout.submitted_returns_dir / "UStVA_2025_Q1_live.xml").write_bytes(b"<Elster/>")
        _set_meta(
            "submissions",
            [
                {
                    "type": "ustva_q1",
                    "year": 2025,
                    "submitted_at": "2025-04-08T10:00:00",
                    "telenummer": "T-1",
                    "xml_filename": "UStVA_2025_Q1_live.xml",
                }
            ],
        )

    def test_lists_submissions_and_files(self, client):
        self._submission()
        html = _get(client, "/app/archiv").text
        assert "T-1" in html
        assert "UStVA_2025_Q1_live.xml" in html

    def test_serves_file(self, client):
        self._submission()
        resp = _get(client, "/app/archiv/datei", name="UStVA_2025_Q1_live.xml")
        assert resp.content == b"<Elster/>"

    def test_path_traversal_refused(self, client):
        self._submission()
        resp = _get(client, "/app/archiv/datei", name="../finamt.db")
        assert resp.status_code == 400

    def test_attach_and_remove_bescheid(self, client):
        self._submission()
        resp = client.post(
            "/app/archiv/dokument",
            params={"projekt": PROJEKT},
            data={"typ": "ustva_q1", "jahr": "2025", "art": "final"},
            files={"datei": ("bescheid.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert "Bescheid</a>" in resp.text
        resp = client.post(
            "/app/archiv/dokument/loeschen",
            params={"projekt": PROJEKT},
            data={"typ": "ustva_q1", "jahr": "2025", "art": "final"},
        )
        assert "Bescheid</a>" not in resp.text

    def test_wrong_file_type_shows_error(self, client):
        self._submission()
        resp = client.post(
            "/app/archiv/dokument",
            params={"projekt": PROJEKT},
            data={"typ": "ustva_q1", "jahr": "2025", "art": "copy"},
            files={"datei": ("x.exe", b"MZ", "application/octet-stream")},
        )
        assert "Unsupported file type" in resp.text

    def test_empty_archive(self, client):
        assert "Keine archivierten Erklärungen." in _get(client, "/app/archiv").text


class TestNavigationUi8:
    def test_new_pages_in_navigation_and_render(self, client):
        html = _get(client, "/app").text
        for path in ("/app/partner", "/app/archiv", "/app/projekte"):
            assert f'href="{path}?projekt=testprojekt"' in html
            assert _get(client, path).status_code == 200


# ---------------------------------------------------------------------------
# UI-5: invoices (INV-1)
# ---------------------------------------------------------------------------

RECHNUNG = {
    "kunde_name": "Kunde GmbH",
    "kunde_strasse": "Hauptstraße 5",
    "kunde_plz": "10115",
    "kunde_ort": "Berlin",
    "issue_date": "2025-03-31",
    "supply_date": "2025-03-31",
    "pos_beschreibung": ["Beratung", ""],
    "pos_menge": ["10", ""],
    "pos_einheit": ["Std.", ""],
    "pos_preis": ["100,00", ""],
    "pos_satz": ["19", "19"],
}


class TestRechnungen:
    def _stamm(self):
        _set_meta(h.TAXPAYER_KEY, TEST_TAXPAYER)

    def _neu(self, client, **aend):
        data = {**RECHNUNG, **aend}
        return client.post("/app/rechnungen", params={"projekt": PROJEKT}, data=data)

    def test_create_lists_and_stores_receipt(self, client):
        self._stamm()
        resp = self._neu(client)
        assert "Rechnung 2025-0001 erstellt." in resp.text
        assert ">2025-0001</a>" in resp.text
        assert "1.190,00 €" in resp.text
        [r] = _alle()
        assert str(r.receipt_type) == "sale" and r.receipt_number == "2025-0001"
        pdf = _get(client, "/app/rechnungen/2025-0001.pdf")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    def test_numbers_are_sequential(self, client):
        self._stamm()
        self._neu(client)
        resp = self._neu(client)
        assert "Rechnung 2025-0002 erstellt." in resp.text

    def test_missing_fields_keep_input(self, client):
        self._stamm()
        resp = self._neu(client, kunde_strasse="", kunde_ort="")
        assert "Rechnung nicht erstellt:" in resp.text
        assert "Name und Anschrift des Leistungsempfängers fehlen." in resp.text
        assert 'value="Kunde GmbH"' in resp.text and 'value="Beratung"' in resp.text
        assert _alle() == []

    def test_missing_sender_warned(self, client):
        html = _get(client, "/app/rechnungen").text
        assert "Name und Anschrift für den Absender fehlen" in html
        resp = self._neu(client)
        assert "Name und Anschrift des leistenden Unternehmers fehlen." in resp.text

    def test_cancel_creates_correction(self, client):
        self._stamm()
        self._neu(client)
        resp = client.post("/app/rechnungen/2025-0001/stornieren", params={"projekt": PROJEKT})
        assert "storniert durch" in resp.text
        assert "Storno zu 2025-0001" in resp.text
        assert "stornieren</button>" not in resp.text.split("2025-0001</a>")[-1].split("</tr>")[0]
        resp = client.post("/app/rechnungen/2025-0001/stornieren", params={"projekt": PROJEKT})
        assert "schon durch" in resp.text

    def test_kleinunternehmer_invoice(self, client):
        self._stamm()
        resp = self._neu(
            client,
            kleinunternehmer="1",
            kleinunternehmer_hinweis="Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.",
        )
        assert "1.000,00 €" in resp.text
        assert _alle()[0].vat_amount == Decimal("0")

    def test_kleinunternehmer_year_preselects(self, client):
        _set_meta(h.SETTINGS_KEY, {"kleinunternehmer_jahre": [date.today().year]})
        html = _get(client, "/app/rechnungen").text
        assert re.search(r'name="kleinunternehmer" value="1" checked', html)

    def test_period_needs_both_ends(self, client):
        self._stamm()
        resp = self._neu(client, supply_von="2025-03-01", supply_bis="")
        assert "Beginn und Ende angeben" in resp.text

    def test_unknown_pdf_404(self, client):
        assert _get(client, "/app/rechnungen/2025-0099.pdf").status_code == 404

    def test_english(self, client):
        client.cookies.set("freibuch_lang", "en")
        assert "New invoice" in _get(client, "/app/rechnungen").text


# ---------------------------------------------------------------------------
# EUR-9: Anlage EÜR to ELSTER from the EÜR page
# ---------------------------------------------------------------------------


class TestEuerElster:
    FORM = {"jahr": "2025", "art_des_betriebs": "IT-Beratung", "grundstuecke": "nein"}

    def _daten(self, review=False):
        _set_meta(h.TAXPAYER_KEY, TEST_TAXPAYER)
        _set_meta(h.ELSTER_MISC_KEY, {"hersteller_id": "12345", "cert_pin": "123456"})
        receipts = [
            _receipt(typ="sale", cat="services", total="1190.00", vat="190.00"),
            _receipt(name="Softwarehaus"),
        ]
        if review:
            receipts.append(_receipt(cat="donations", total="50.00", vat="0.00", pct="0"))
        _save(*receipts)

    def _post(self, client, aktion, **aend):
        data = {**self.FORM, "aktion": aktion, **aend}
        return client.post("/app/euer", params={"projekt": PROJEKT}, data=data)

    def test_section_and_buttons(self, client, monkeypatch):
        import finamt.ui.web.routes as routes

        monkeypatch.setattr(routes, "live_submission_allowed", lambda: True)
        html = _get(client, "/app/euer", jahr=2025).text
        assert "An ELSTER (Anlage EÜR 2025)" in html
        for aktion in ("pruefen", "xml", "test"):
            assert f'name="aktion" value="{aktion}"' in html
        assert 'value="live"' not in html  # D3: never a live button for the EÜR

    def test_other_year_has_no_form(self, client):
        html = _get(client, "/app/euer", jahr=2024).text
        assert "Geprüft ist nur das Formular 2025" in html
        assert 'name="aktion" value="xml"' not in html

    def test_xml_download(self, client):
        from finamt.tax.elster import TESTMERKER

        self._daten()
        resp = self._post(client, "xml")
        assert resp.status_code == 200
        assert 'filename="EUER_2025.xml"' in resp.headers["content-disposition"]
        xml = resp.content.decode("utf-8")
        assert f"<Testmerker>{TESTMERKER}</Testmerker>" in xml
        assert "<E6000401>1000,00</E6000401>" in xml  # Kz 112
        assert "<E6000601>190,00</E6000601>" in xml  # Kz 140
        assert "IT-Beratung" in xml

    def test_check_uses_eric_path_from_env_then_stammdaten(self, client, monkeypatch):
        from finamt.tax import eur_elster
        from finamt.tax.elster import SubmissionResult

        self._daten()
        _set_meta(h.ERIC_HOME_KEY, {"path": "/stammdaten/eric"})
        seen = {}

        def fake(xml, **kw):
            seen.update(kw)
            return SubmissionResult(success=True)

        monkeypatch.setattr(eur_elster, "eric_validate", fake)
        monkeypatch.delenv(eur_elster.ERIC_LIBRARY_ENV, raising=False)
        resp = self._post(client, "pruefen")
        assert "ERiC-Prüfung ohne Fehler. Nichts gesendet." in resp.text
        assert seen["eric_home"] == "/stammdaten/eric"
        monkeypatch.setenv(eur_elster.ERIC_LIBRARY_ENV, "/env/eric")
        self._post(client, "pruefen")
        assert seen["eric_home"] == "/env/eric"

    def test_eric_errors_shown(self, client, monkeypatch):
        from finamt.tax import eur_elster
        from finamt.tax.elster import SubmissionResult

        self._daten()
        monkeypatch.setattr(
            eur_elster,
            "eric_validate",
            lambda xml, **kw: SubmissionResult(False, error_code="610301202", error_message="HID"),
        )
        resp = self._post(client, "pruefen")
        assert "Nicht übermittelt:" in resp.text and "610301202" in resp.text

    def test_test_send_needs_certificate(self, client):
        self._daten()
        assert "Zertifikat und PIN fehlen" in self._post(client, "test").text

    def test_test_send_uses_test_mode(self, client, monkeypatch):
        from finamt.tax import eur_elster
        from finamt.tax.elster import SubmissionResult

        self._daten()
        (_layout().root / h.CERT_FILENAME).write_bytes(b"pfx")
        seen = {}

        def fake(xml, mode="dry_run", **kw):
            seen.update(kw, mode=mode, xml=xml)
            return SubmissionResult(success=True, telenummer="T-42")

        monkeypatch.setattr(eur_elster, "submit", fake)
        resp = self._post(client, "test")
        assert "Testfall gesendet" in resp.text and "T-42" in resp.text
        assert seen["mode"] == "test"
        assert seen["config"].cert_password == "123456"
        assert eur_elster.has_testmerker(seen["xml"])

    @pytest.mark.parametrize(
        "aend,text",
        [
            ({"grundstuecke": ""}, "Zeile 11"),
            ({"art_des_betriebs": ""}, "Art des Betriebs fehlt."),
        ],
    )
    def test_missing_answers(self, client, aend, text):
        self._daten()
        resp = self._post(client, "xml", **aend)
        assert resp.headers["content-type"].startswith("text/html")
        assert text in resp.text

    def test_refusal_shown_for_review_lines(self, client):
        self._daten(review=True)
        resp = self._post(client, "xml")
        assert "Anlage EÜR nicht erstellt:" in resp.text
        assert "ZU PRÜFEN" in resp.text

    def test_missing_stammdaten(self, client):
        _save(_receipt(typ="sale", cat="services", total="1190.00", vat="190.00"))
        assert "Steuernummer:" in self._post(client, "xml").text

    def test_art_des_betriebs_remembered(self, client):
        self._daten()
        self._post(client, "xml")
        assert 'value="IT-Beratung"' in _get(client, "/app/euer", jahr=2025).text


# ---------------------------------------------------------------------------
# Bug (owner, 2026-11-20): deleting a project that only exists as a folder said "not found"
# ---------------------------------------------------------------------------


class TestProjektReste:
    def _rest(self, name="sahraoui-consulting", datei=False):
        root = project_mod.resolve_project(name, env_var=False).root
        (root / "pdfs").mkdir(parents=True)
        (root / "submitted_returns").mkdir()
        if datei:
            (root / "pdfs" / "beleg.pdf").write_bytes(b"%PDF")
        return root

    def test_leftover_folder_not_in_project_selection(self, client):
        self._rest()
        html = _get(client, "/app").text
        assert '<option value="sahraoui-consulting"' not in html

    def test_leftover_listed_and_removed(self, client):
        root = self._rest()
        html = _get(client, "/app/projekte").text
        assert "Ordner ohne Datenbank" in html and "sahraoui-consulting" in html
        resp = client.post(
            "/app/projekte/sahraoui-consulting/loeschen", params={"projekt": PROJEKT}
        )
        assert "Leerer Projektordner entfernt." in resp.text
        assert "not found" not in resp.text
        assert not root.exists()

    def test_leftover_with_files_is_kept(self, client):
        root = self._rest(datei=True)
        assert "1 Datei(en), bitte selbst prüfen" in _get(client, "/app/projekte").text
        resp = client.post(
            "/app/projekte/sahraoui-consulting/loeschen", params={"projekt": PROJEKT}
        )
        assert "enthält noch 1 Datei(en)" in resp.text
        assert (root / "pdfs" / "beleg.pdf").exists()

    def test_delete_leaves_no_empty_folder(self, client):
        client.post("/app/projekte", params={"projekt": PROJEKT}, data={"name": "kurz"})
        root = project_mod.resolve_project("kurz", env_var=False).root
        assert root.exists()
        resp = client.post("/app/projekte/kurz/loeschen", params={"projekt": "kurz"})
        assert "Projekt gelöscht." in resp.text
        assert not root.exists()
        assert "Ordner ohne Datenbank" not in resp.text

    def test_delete_with_pdfs_keeps_them_and_hides_project(self, client):
        client.post("/app/projekte", params={"projekt": PROJEKT}, data={"name": "mitpdf"})
        root = project_mod.resolve_project("mitpdf", env_var=False).root
        (root / "pdfs" / "a.pdf").write_bytes(b"%PDF")
        resp = client.post("/app/projekte/mitpdf/loeschen", params={"projekt": "mitpdf"})
        assert "Die Original-Dateien liegen weiter" in resp.text
        assert (root / "pdfs" / "a.pdf").exists()
        assert '<option value="mitpdf"' not in resp.text


# ---------------------------------------------------------------------------
# PRINT-1: ERiC print PDF (preview and archived copy)
# ---------------------------------------------------------------------------


class TestDruck:
    def _capture(self, monkeypatch, name, result):
        import finamt.ui.api as api

        seen = {}

        def fake(body, db=None):
            seen["body"] = body
            return result(body) if callable(result) else result

        monkeypatch.setattr(api, name, fake)
        return seen

    def _vorschau_datei(self, tmp_path):
        f = tmp_path / "vorschau.pdf"
        f.write_bytes(b"%PDF-1.7 vorschau")
        return f

    def test_ustva_preview_returns_pdf(self, client, monkeypatch, tmp_path):
        _set_meta(h.TAXPAYER_KEY, TEST_TAXPAYER)
        f = self._vorschau_datei(tmp_path)
        seen = self._capture(
            monkeypatch, "post_ustva_submit", {"success": True, "pdf_path": str(f)}
        )
        resp = client.post(
            "/app/ustva",
            params={"projekt": PROJEKT},
            data={"jahr": "2025", "zeitraum": "q1", "aktion": "vorschau"},
        )
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content == b"%PDF-1.7 vorschau"
        assert not f.exists()  # temp file removed after serving
        body = seen["body"]
        assert (body.validate_only, body.pdf, body.use_test) == (True, True, True)

    def test_preview_failure_shows_message(self, client, monkeypatch):
        _set_meta(h.TAXPAYER_KEY, TEST_TAXPAYER)
        self._capture(
            monkeypatch,
            "post_ustva_submit",
            {"success": False, "message": "Prüffehler Kz 81", "error_code": "610001002"},
        )
        resp = client.post(
            "/app/ustva",
            params={"projekt": PROJEKT},
            data={"jahr": "2025", "zeitraum": "q1", "aktion": "vorschau"},
        )
        assert resp.headers["content-type"].startswith("text/html")
        assert "Prüffehler Kz 81" in resp.text

    def test_annual_preview(self, client, monkeypatch, tmp_path):
        _set_meta(h.TAXPAYER_KEY, TEST_TAXPAYER)
        f = self._vorschau_datei(tmp_path)
        seen = self._capture(monkeypatch, "post_uste_submit", {"success": True, "pdf_path": str(f)})
        resp = client.post(
            "/app/ustva",
            params={"projekt": PROJEKT},
            data={"jahr": "2025", "zeitraum": "jahr", "aktion": "vorschau"},
        )
        assert resp.content.startswith(b"%PDF")
        assert seen["body"].pdf is True

    @pytest.mark.parametrize("kopie,erwartet", [("1", True), ("", False)])
    def test_test_send_pdf_copy_optional(self, client, monkeypatch, kopie, erwartet):
        _set_meta(h.TAXPAYER_KEY, TEST_TAXPAYER)
        seen = self._capture(
            monkeypatch,
            "post_ustva_submit",
            lambda body: {
                "success": True,
                "telenummer": "T-1",
                "pdf_filename": "UStVA_2025_Q1_x_test.pdf" if body.pdf else None,
            },
        )
        resp = client.post(
            "/app/ustva",
            params={"projekt": PROJEKT},
            data={"jahr": "2025", "zeitraum": "q1", "aktion": "test", "pdf_kopie": kopie},
        )
        assert seen["body"].pdf is erwartet
        assert seen["body"].validate_only is False
        assert ("PDF-Kopie öffnen" in resp.text) is erwartet

    def test_checkbox_checked_by_default(self, client):
        html = _get(client, "/app/ustva", jahr=2025, zeitraum="q1").text
        assert 'name="pdf_kopie" value="1" checked' in html
        assert 'value="vorschau"' in html

    def test_euer_preview(self, client, monkeypatch):
        from finamt.tax import eur_elster
        from finamt.tax.elster import SubmissionResult

        TestEuerElster()._daten()

        def fake(xml, pdf_path=None, **kw):
            Path(pdf_path).write_bytes(b"%PDF euer")
            return SubmissionResult(success=True)

        monkeypatch.setattr(eur_elster, "eric_validate", fake)
        resp = client.post(
            "/app/euer",
            params={"projekt": PROJEKT},
            data={**TestEuerElster.FORM, "aktion": "vorschau"},
        )
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content == b"%PDF euer"

    def test_euer_preview_failure(self, client, monkeypatch):
        from finamt.tax import eur_elster
        from finamt.tax.elster import SubmissionResult

        TestEuerElster()._daten()
        monkeypatch.setattr(
            eur_elster,
            "eric_validate",
            lambda xml, **kw: SubmissionResult(False, error_code="X", error_message="kaputt"),
        )
        resp = client.post(
            "/app/euer",
            params={"projekt": PROJEKT},
            data={**TestEuerElster.FORM, "aktion": "vorschau"},
        )
        assert "kaputt" in resp.text

    def test_archive_links_pdf(self, client):
        TestArchiv()._submission()
        subs = h.get_meta(_layout(), "submissions")
        subs[0]["pdf_filename"] = "UStVA_2025_Q1_live.pdf"
        _set_meta("submissions", subs)
        assert "PDF (ERiC)" in _get(client, "/app/archiv").text


class TestDruckApi:
    """The old API stores ERiC's copy next to the XML and records it (fake ERiC client)."""

    def _body(self, tmp_path, **kw):
        import finamt.ui.api as api

        cert = tmp_path / "c.pfx"
        cert.write_bytes(b"x")
        d = {
            "year": 2025,
            "quarter": 1,
            "steuernummer": "9198011310010",
            "finanzamt_nr": "9198",
            "bundesland_kz": "09",
            "hersteller_id": "12345",
            "cert_path": str(cert),
            "cert_password": "123456",
            "company_name": "E",
            "street": "S 1",
            "postal_code": "80331",
            "city": "M",
            **kw,
        }
        return api.UStVASubmitRequest(**d)

    def _fake_client(self, monkeypatch, tmp_path):
        import finamt.tax.elster as elster
        from finamt.tax.elster import SubmissionResult

        calls = {}

        class Fake:
            def __init__(self, *a, **k):
                pass

            def submit_ust(self, report, pdf_path=None, **k):
                calls["submit"] = pdf_path
                if pdf_path:
                    Path(pdf_path).write_bytes(b"%PDF copy")
                return SubmissionResult(success=True, telenummer="T-7")

            def validate_ust(self, report, pdf_path=None, **k):
                calls["validate"] = pdf_path
                if pdf_path:
                    Path(pdf_path).write_bytes(b"%PDF preview")
                return SubmissionResult(success=True)

        monkeypatch.setattr(elster, "ElsterEricClient", Fake)
        monkeypatch.setenv("FINAMT_ERIC_HOME", str(tmp_path))
        return calls

    def test_send_stores_and_records_pdf(self, home, monkeypatch, tmp_path):
        import finamt.tax.safety as safety
        import finamt.ui.api as api

        calls = self._fake_client(monkeypatch, tmp_path)
        monkeypatch.setattr(safety, "live_submission_allowed", lambda: True)  # flag never set
        _layout().create_dirs()
        _set_meta(h.TAXPAYER_KEY, TEST_TAXPAYER)
        res = api.post_ustva_submit(
            self._body(tmp_path, use_test=False, pdf=True), db=str(_layout().db_path)
        )
        assert res["success"] and res["pdf_filename"].endswith("_prod.pdf")
        assert (_layout().submitted_returns_dir / res["pdf_filename"]).read_bytes() == b"%PDF copy"
        assert Path(calls["submit"]).parent == _layout().submitted_returns_dir
        rec = h.get_meta(_layout(), "submissions")[-1]
        assert rec["pdf_filename"] == res["pdf_filename"]

    def test_send_without_pdf(self, home, monkeypatch, tmp_path):
        import finamt.ui.api as api

        calls = self._fake_client(monkeypatch, tmp_path)
        _layout().create_dirs()
        res = api.post_ustva_submit(self._body(tmp_path), db=str(_layout().db_path))
        assert calls["submit"] is None
        assert res["pdf_filename"] is None

    def test_preview_goes_to_temp_file(self, home, monkeypatch, tmp_path):
        import finamt.ui.api as api

        calls = self._fake_client(monkeypatch, tmp_path)
        _layout().create_dirs()
        res = api.post_ustva_submit(
            self._body(tmp_path, validate_only=True, pdf=True), db=str(_layout().db_path)
        )
        assert Path(res["pdf_path"]).read_bytes() == b"%PDF preview"
        assert Path(calls["validate"]).parent != _layout().submitted_returns_dir
        Path(res["pdf_path"]).unlink()
