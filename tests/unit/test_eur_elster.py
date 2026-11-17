"""
tests/unit/test_eur_elster.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
EÜR ELSTER boundary: build_xml stub, local validation, submit modes.

Offline: ERiC is never loaded for real (EricSession is replaced where needed).
"""

from __future__ import annotations

import pytest

from finamt.tax import eur_elster
from finamt.tax.elster import NS, TESTMERKER, ElsterConfig
from finamt.tax.eur import EURReport
from finamt.tax.safety import LIVE_SUBMISSION_ENV


def _envelope(*, testmerker: bool = True, nutzdaten: bool = True) -> bytes:
    tm = f"<Testmerker>{TESTMERKER}</Testmerker>" if testmerker else ""
    nd = "<Nutzdaten><X/></Nutzdaten>" if nutzdaten else ""
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<Elster xmlns="{NS}">'
        f"<TransferHeader><Verfahren>V</Verfahren><DatenArt>D</DatenArt>{tm}</TransferHeader>"
        f"<DatenTeil><Nutzdatenblock>{nd}</Nutzdatenblock></DatenTeil>"
        f"</Elster>"
    ).encode()


def _cfg() -> ElsterConfig:
    return ElsterConfig(
        cert_path="/nonexistent/test.pfx",
        cert_password="secret",
        steuernummer="21/815/08150",
        finanzamt_nr="2181",
        bundesland_kz="21",
    )


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(eur_elster.ERIC_LIBRARY_ENV, raising=False)
    monkeypatch.delenv("FINAMT_ERIC_HOME", raising=False)


@pytest.fixture
def no_eric(monkeypatch):
    """Fail the test if ERiC would be loaded."""

    def _boom(*_a, **_k):
        raise AssertionError("ERiC must not be loaded in this test")

    monkeypatch.setattr(eur_elster, "EricSession", _boom)


class TestBuildXml:
    def test_not_implemented_until_kennzahlen_verified(self):
        with pytest.raises(NotImplementedError, match="docs/TODO.md"):
            eur_elster.build_xml(EURReport(year=2024))

    def test_docstring_points_to_todo(self):
        assert "docs/TODO.md" in eur_elster.build_xml.__doc__


class TestValidate:
    def test_minimal_envelope_ok(self):
        assert eur_elster.validate(_envelope()) == []

    @pytest.mark.parametrize("xml", [b"", b"   ", "<Elster/>"])
    def test_empty_or_not_bytes(self, xml):
        assert eur_elster.validate(xml) != []

    def test_not_well_formed(self):
        errors = eur_elster.validate(b"<Elster><open></Elster>")
        assert any("well-formed" in e for e in errors)

    def test_doctype_rejected(self):
        xml = b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><Elster>&e;</Elster>'
        assert eur_elster.validate(xml) == ["DOCTYPE declarations are not allowed"]

    def test_wrong_root_and_namespace(self):
        errors = eur_elster.validate(b"<Foo/>")
        assert any("'Elster'" in e for e in errors)
        assert any("namespace" in e for e in errors)

    def test_missing_nutzdaten(self):
        errors = eur_elster.validate(_envelope(nutzdaten=False))
        assert errors == ["Missing DatenTeil//Nutzdaten"]

    def test_missing_transfer_header_fields(self):
        xml = f'<Elster xmlns="{NS}"><TransferHeader/><DatenTeil/></Elster>'.encode()
        errors = eur_elster.validate(xml)
        assert "Missing TransferHeader/Verfahren" in errors
        assert "Missing TransferHeader/DatenArt" in errors
        assert "Missing DatenTeil//Nutzdaten" in errors


class TestSubmitModes:
    def test_default_mode_is_dry_run(self, no_eric):
        result = eur_elster.submit(_envelope())
        assert result.success is True
        assert "dry_run" in result.raw_response

    def test_dry_run_reports_validation_errors(self, no_eric):
        result = eur_elster.submit(b"<Foo/>", mode="dry_run")
        assert result.success is False
        assert result.error_code == "VALIDATION_ERROR"

    def test_live_always_raises(self, monkeypatch, no_eric):
        monkeypatch.setenv(LIVE_SUBMISSION_ENV, "1")
        with pytest.raises(NotImplementedError) as exc:
            eur_elster.submit(_envelope(), mode="live")
        assert str(exc.value) == (
            "Live ELSTER submission requires a Hersteller-ID and is disabled."
        )

    def test_unknown_mode(self, no_eric):
        with pytest.raises(ValueError):
            eur_elster.submit(_envelope(), mode="production")

    def test_test_mode_requires_testmerker(self, monkeypatch, tmp_path, no_eric):
        monkeypatch.setenv(eur_elster.ERIC_LIBRARY_ENV, str(tmp_path))
        result = eur_elster.submit(
            _envelope(testmerker=False), mode="test", datenart_version="X", config=_cfg()
        )
        assert result.success is False
        assert result.error_code == "TESTMERKER_MISSING"

    def test_test_mode_requires_datenart_version(self, monkeypatch, tmp_path, no_eric):
        monkeypatch.setenv(eur_elster.ERIC_LIBRARY_ENV, str(tmp_path))
        with pytest.raises(ValueError, match="datenart_version"):
            eur_elster.submit(_envelope(), mode="test", config=_cfg())

    def test_test_mode_reads_only_eric_library_path(self, monkeypatch, tmp_path, no_eric):
        monkeypatch.setenv("FINAMT_ERIC_HOME", str(tmp_path))  # must be ignored
        result = eur_elster.submit(_envelope(), mode="test", datenart_version="X", config=_cfg())
        assert result.success is False
        assert result.error_code == "ERIC_LIBRARY_PATH_MISSING"

    def test_test_mode_missing_library_fails_gracefully(self, monkeypatch, tmp_path):
        monkeypatch.setenv(eur_elster.ERIC_LIBRARY_ENV, str(tmp_path))
        result = eur_elster.submit(_envelope(), mode="test", datenart_version="X", config=_cfg())
        assert result.success is False
        assert result.error_code == "ERIC_LOAD_ERROR"


class _FakeBuffer:
    def __init__(self, session, content=b""):
        self._content = content

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def handle(self):
        return None

    def content(self):
        return self._content


class _FakeCert:
    verschluesselungs_parameter = object()

    def __init__(self, *_a, **_k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


class TestSubmitTestModeWithFakeEric:
    def test_sends_with_validate_and_send_flags(self, monkeypatch, tmp_path):
        calls = {}

        class _FakeSession:
            def __init__(self, eric_home, log_dir=None):
                calls["eric_home"] = eric_home

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def bearbeite_vorgang(self, **kwargs):
                calls.update(kwargs)
                return 0, 1

        server = b"<Elster><TransferHeader><TransferTicket>TT1</TransferTicket></TransferHeader></Elster>"
        monkeypatch.setenv(eur_elster.ERIC_LIBRARY_ENV, str(tmp_path))
        monkeypatch.setattr(eur_elster, "EricSession", _FakeSession)
        monkeypatch.setattr(eur_elster, "EricCertificate", _FakeCert)
        buffers = iter([b"", server])
        monkeypatch.setattr(eur_elster, "EricBuffer", lambda s: _FakeBuffer(s, next(buffers)))

        xml = _envelope()
        result = eur_elster.submit(xml, mode="test", datenart_version="DV_TEST", config=_cfg())

        assert result.success is True
        assert calls["eric_home"] == str(tmp_path)
        assert calls["xml_bytes"] == xml
        assert calls["datenart_version"] == "DV_TEST"
        assert calls["flags"] == eur_elster.ERIC_VALIDIERE | eur_elster.ERIC_SENDE
