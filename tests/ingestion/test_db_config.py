"""Tests for portable, environment-only database credentials."""

from __future__ import annotations

import pytest

from src.ingestion.db import connection_info


def test_database_password_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRAGMENT_DB_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="FRAGMENT_DB_PASSWORD"):
        connection_info()


def test_database_settings_come_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRAGMENT_DB_PASSWORD", "test-only-value")
    monkeypatch.setenv("FRAGMENT_DB_PORT", "60000")

    settings = connection_info()

    assert settings["password"] == "test-only-value"
    assert settings["port"] == "60000"
