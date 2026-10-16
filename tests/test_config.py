"""Configuration must fail clearly instead of weakening production defaults."""

import pytest

from app.core.config import _as_bool, _normalize_site_url, get_settings, pwd_context


@pytest.mark.parametrize(
    "value",
    [
        "https://",
        "ftp://example.com",
        "https://user:pass@example.com",
        "https://example.com/path",
        "https://example.com?q=1",
        "https://example.com#section",
        "https://example.com:bad",
        "https://exa mple.com",
    ],
)
def test_invalid_site_origins(value):
    with pytest.raises(ValueError):
        _normalize_site_url(value)


def test_normalize_site_origin():
    assert _normalize_site_url(" nawaglobalgtd.com/ ") == "https://nawaglobalgtd.com"
    assert _normalize_site_url("http://localhost:8000") == "http://localhost:8000"


@pytest.mark.parametrize(
    "value,expected", [("true", True), ("0", False), (" YES ", True), ("off", False)]
)
def test_boolean_values(value, expected):
    assert _as_bool(value) is expected


def test_invalid_boolean():
    with pytest.raises(ValueError):
        _as_bool("tru")


def test_environment_typo_is_rejected(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "producton")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="ENVIRONMENT"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_production_host_defaults_and_wildcard(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SITE_URL", "https://nawaglobalgtd.com")
    monkeypatch.setenv("SECRET_KEY", "a" * 40)
    monkeypatch.setenv("ADMIN_USERNAME", "owner")
    monkeypatch.setenv(
        "ADMIN_PASSWORD_HASH", pwd_context.hash("test-only-strong-password")
    )
    monkeypatch.setenv("SECURE_COOKIES", "1")
    monkeypatch.delenv("TRUSTED_HOSTS", raising=False)
    get_settings.cache_clear()
    try:
        assert get_settings().trusted_hosts == ["nawaglobalgtd.com"]
        monkeypatch.setenv("TRUSTED_HOSTS", "*")
        get_settings.cache_clear()
        with pytest.raises(ValueError, match="TRUSTED_HOSTS"):
            get_settings()
        monkeypatch.delenv("TRUSTED_HOSTS")
        monkeypatch.setenv("ADMIN_PASSWORD_HASH", "$2b$invalid")
        get_settings.cache_clear()
        with pytest.raises(ValueError, match="valid bcrypt hash"):
            get_settings()
    finally:
        get_settings.cache_clear()
