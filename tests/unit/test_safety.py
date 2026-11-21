"""
tests/unit/test_safety.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Live ELSTER submission must be impossible unless FINAMT_ALLOW_LIVE_SUBMISSION=1.

Offline: no ERiC library, no certificate, no network.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from finamt.tax.elster import ElsterClient, ElsterConfig, ElsterEricClient
from finamt.tax.safety import (
    LIVE_SUBMISSION_ENV,
    LiveSubmissionDisabledError,
    live_submission_allowed,
    require_live_submission_allowed,
)
from finamt.tax.ustva import generate_ustva

pytestmark = pytest.mark.filterwarnings("ignore:ElsterEricClient is in PRODUCTION mode")


def _cfg() -> ElsterConfig:
    return ElsterConfig(
        cert_path="/nonexistent/test.pfx",
        cert_password="secret",
        steuernummer="21/815/08150",
        finanzamt_nr="2181",
        bundesland_kz="21",
    )


def _empty_report():
    return generate_ustva([], date(2024, 1, 1), date(2024, 3, 31))


@pytest.fixture(autouse=True)
def _no_live_env(monkeypatch):
    monkeypatch.delenv(LIVE_SUBMISSION_ENV, raising=False)


class TestFlag:
    def test_disabled_by_default(self):
        assert live_submission_allowed() is False

    @pytest.mark.parametrize("value", ["", "0", "true", "yes", "2"])
    def test_only_exact_one_enables(self, monkeypatch, value):
        monkeypatch.setenv(LIVE_SUBMISSION_ENV, value)
        assert live_submission_allowed() is False

    def test_one_enables(self, monkeypatch):
        monkeypatch.setenv(LIVE_SUBMISSION_ENV, "1")
        assert live_submission_allowed() is True
        require_live_submission_allowed()  # does not raise

    def test_require_raises_when_disabled(self):
        with pytest.raises(LiveSubmissionDisabledError):
            require_live_submission_allowed()


class TestEricClientGate:
    def test_live_submit_blocked(self, tmp_path):
        client = ElsterEricClient(_cfg(), eric_home=str(tmp_path), use_test=False)
        with pytest.raises(LiveSubmissionDisabledError):
            client.submit_ust(_empty_report(), year=2024, period=41)

    def test_validate_only_not_blocked(self, tmp_path):
        client = ElsterEricClient(_cfg(), eric_home=str(tmp_path), use_test=False)
        result = client.validate_ust(_empty_report(), year=2024, period=41)
        assert result.success is False  # no ERiC library here, but no gate error

    def test_test_mode_submit_not_blocked(self, tmp_path):
        client = ElsterEricClient(_cfg(), eric_home=str(tmp_path), use_test=True)
        result = client.submit_ust(_empty_report(), year=2024, period=41)
        assert result.success is False
        assert result.error_code != "LIVE_DISABLED"

    def test_opt_in_reaches_eric(self, tmp_path, monkeypatch):
        monkeypatch.setenv(LIVE_SUBMISSION_ENV, "1")
        client = ElsterEricClient(_cfg(), eric_home=str(tmp_path), use_test=False)
        result = client.submit_ust(_empty_report(), year=2024, period=41)
        # Gate passed; fails later because no ERiC library exists in tmp_path.
        assert result.success is False


class TestHttpClientGate:
    def test_live_post_blocked(self):
        client = ElsterClient.__new__(ElsterClient)  # skip cert loading
        client.use_test = False
        with pytest.raises(LiveSubmissionDisabledError):
            client._post(b"<Elster/>", timeout=1)


class TestApiGate:
    @pytest.fixture
    def api(self):
        from finamt.ui.api import app

        return TestClient(app)

    @pytest.mark.parametrize(
        "path,payload",
        [
            ("/tax/ustva/submit", {"year": 2024, "quarter": 1}),
            ("/tax/uste/submit", {"year": 2024}),
        ],
    )
    def test_live_returns_403(self, api, path, payload):
        resp = api.post(path, json={**payload, "use_test": False})
        assert resp.status_code == 403
        assert LIVE_SUBMISSION_ENV in resp.json()["detail"]
