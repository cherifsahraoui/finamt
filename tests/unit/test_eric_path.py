"""CFG-1: one ERiC path setting (decision D4) for the UStVA / USt API routes."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from finamt.storage.sqlite import SQLiteRepository


def _eric_home(db_path):
    # Lazy import: finamt.ui.api loads .env on import, which must not happen at collection.
    from finamt.ui.api import _eric_home as resolve

    return resolve(db_path)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("ERIC_LIBRARY_PATH", raising=False)
    monkeypatch.delenv("FINAMT_ERIC_HOME", raising=False)


def test_eric_library_path_wins(monkeypatch, tmp_path, recwarn):
    monkeypatch.setenv("ERIC_LIBRARY_PATH", "/new")
    monkeypatch.setenv("FINAMT_ERIC_HOME", "/old")
    assert _eric_home(tmp_path / "none.db") == "/new"
    assert not [w for w in recwarn if issubclass(w.category, DeprecationWarning)]


def test_legacy_variable_warns(monkeypatch, tmp_path):
    monkeypatch.setenv("FINAMT_ERIC_HOME", "/old")
    with pytest.warns(DeprecationWarning, match="ERIC_LIBRARY_PATH"):
        assert _eric_home(tmp_path / "none.db") == "/old"


def test_project_value_fallback(tmp_path):
    db = tmp_path / "p.db"
    with SQLiteRepository(db_path=db) as repo:
        repo.set_metadata("elster_eric_home", {"path": "/saved"})
    assert _eric_home(db) == "/saved"


def test_missing_names_new_variable(tmp_path):
    with pytest.raises(HTTPException) as exc:
        _eric_home(tmp_path / "none.db")
    assert exc.value.status_code == 400
    assert "ERIC_LIBRARY_PATH" in exc.value.detail
