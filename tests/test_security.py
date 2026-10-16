"""Reject expired or malformed CSRF tokens without breaking signed sessions."""

from dataclasses import replace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core import security
from app.core.config import get_settings
from app.services.auth import SessionService


def request_with_cookie(token):
    return Request(
        {
            "type": "http",
            "headers": [(b"cookie", f"csrf_token={token}".encode("ascii"))],
        }
    )


@pytest.mark.parametrize("token", ["missing-dot", "value.☃", "value.wrong", "."])
def test_malformed_signature_is_rejected(token):
    assert security.verify_signed_value(token, "secret") is None


def test_signed_session_value_remains_compatible(monkeypatch):
    monkeypatch.setattr(security.time, "time", lambda: 1000)
    settings = get_settings()
    token = SessionService(settings).authenticate(settings.admin_username, "admin123")
    assert SessionService(settings)._decode_token(token)
    assert not SessionService(settings)._decode_token(token + "☃")


@pytest.mark.parametrize(
    "raw",
    [
        "699:random",
        "700:random",
        "1001:random",
        "oops:random",
        "1000:",
        "1000",
    ],
)
def test_invalid_csrf_is_rejected_and_replaced(monkeypatch, raw):
    monkeypatch.setattr(security.time, "time", lambda: 1000)
    settings = replace(get_settings(), session_max_age_seconds=300)
    token = security.sign_value(raw, settings.secret_key)
    request = request_with_cookie(token)
    with pytest.raises(HTTPException) as exc:
        security.validate_csrf(request, token, settings)
    assert exc.value.status_code == 403
    replacement = security.get_or_create_csrf_token(request, settings)
    assert replacement != token
    assert security.get_or_create_csrf_token(request, settings) == replacement
    security.validate_csrf(request_with_cookie(replacement), replacement, settings)


def test_valid_csrf_is_reused_and_requires_matching_form_token(monkeypatch):
    monkeypatch.setattr(security.time, "time", lambda: 1000)
    settings = get_settings()
    token = security.generate_csrf_token(settings.secret_key)
    request = request_with_cookie(token)
    assert security.get_or_create_csrf_token(request, settings) == token
    security.validate_csrf(request, token, settings)
    for submitted in (None, token + "☃", "different"):
        with pytest.raises(HTTPException) as exc:
            security.validate_csrf(request, submitted, settings)
        assert exc.value.status_code == 403
