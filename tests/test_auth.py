"""Credential and session boundary regression tests."""

from dataclasses import replace

import pytest

from app.core.config import get_settings, pwd_context
from app.core.exceptions import AuthenticationError
from app.core.security import sign_value
from app.services import auth


@pytest.mark.parametrize(
    "username,password", [("☃", "admin123"), ("admin", "wrong"), ("admin", "x" * 73)]
)
def test_invalid_credentials_are_rejected(username, password):
    with pytest.raises(AuthenticationError):
        auth.SessionService(get_settings()).authenticate(username, password)


def test_bcrypt_truncated_password_is_rejected():
    prefix = "x" * 72
    settings = replace(get_settings(), admin_password_hash=pwd_context.hash(prefix))
    service = auth.SessionService(settings)
    assert service._decode_token(service.authenticate(settings.admin_username, prefix))
    with pytest.raises(AuthenticationError):
        service.authenticate(settings.admin_username, prefix + "extra")


@pytest.mark.parametrize(
    "expiry,valid",
    [
        (999, False),
        (1000, False),
        (1001, True),
        (1300, True),
        (1301, False),
        ("invalid", False),
    ],
)
def test_session_expiry_boundaries(monkeypatch, expiry, valid):
    monkeypatch.setattr(auth.time, "time", lambda: 1000)
    settings = replace(get_settings(), session_max_age_seconds=300)
    token = sign_value(f"{settings.admin_username}:{expiry}", settings.secret_key)
    assert auth.SessionService(settings)._decode_token(token) is valid


def test_unicode_admin_name_supported():
    settings = replace(get_settings(), admin_username="مدير")
    service = auth.SessionService(settings)
    assert service._decode_token(
        service.authenticate(settings.admin_username, "admin123")
    )
