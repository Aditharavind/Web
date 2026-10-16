"""Monitoring setup checks use a mocked SDK and send no events."""

from unittest.mock import Mock

from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.core import monitoring


def test_monitoring_disabled_without_dsn(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "  ")
    initialize = Mock()
    monkeypatch.setattr(monitoring.sentry_sdk, "init", initialize)
    monitoring.setup_monitoring()
    initialize.assert_not_called()


def test_monitoring_uses_framework_integrations_without_request_bodies(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", " https://public@example.invalid/1 ")
    initialize = Mock()
    monkeypatch.setattr(monitoring.sentry_sdk, "init", initialize)
    monitoring.setup_monitoring()
    initialize.assert_called_once()
    options = initialize.call_args.kwargs
    assert options["dsn"] == "https://public@example.invalid/1"
    assert options["traces_sample_rate"] == 0.0
    assert options["send_default_pii"] is False
    assert options["max_request_body_size"] == "never"
    assert {type(item) for item in options["integrations"]} >= {
        FastApiIntegration,
        StarletteIntegration,
    }
