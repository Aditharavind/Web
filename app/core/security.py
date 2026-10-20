from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from typing import Final

from fastapi import HTTPException, Request, status

from app.core.config import Settings

CSRF_COOKIE_NAME: Final[str] = "csrf_token"


def generate_nonce() -> str:
    return secrets.token_urlsafe(16)


def build_csp(settings: Settings, nonce: str) -> str:
    site_host = settings.site_url.split("://", 1)[1]
    directives = {
        "default-src": ["'self'"],
        "base-uri": ["'self'"],
        "object-src": ["'none'"],
        "frame-ancestors": ["'none'"],
        "form-action": ["'self'"],
        "img-src": ["'self'", "data:", f"https://{site_host}"],
        "style-src": ["'self'"],
        "font-src": ["'self'"],
        "script-src": ["'self'", f"'nonce-{nonce}'"],
        "connect-src": ["'self'"],
    }
    if settings.is_production:
        directives["upgrade-insecure-requests"] = []
    return "; ".join(
        f"{name} {' '.join(values)}".rstrip() for name, values in directives.items()
    )


def sign_value(value: str, secret_key: str) -> str:
    signature = hmac.new(
        secret_key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256
    )
    encoded = base64.urlsafe_b64encode(signature.digest()).decode("ascii").rstrip("=")
    return f"{value}.{encoded}"


def verify_signed_value(token: str, secret_key: str) -> str | None:
    if "." not in token:
        return None
    value, signature = token.rsplit(".", 1)
    expected = sign_value(value, secret_key).rsplit(".", 1)[1]
    if hmac.compare_digest(signature.encode("utf-8"), expected.encode("ascii")):
        return value
    return None


def generate_csrf_token(secret_key: str) -> str:
    raw_value = f"{int(time.time())}:{secrets.token_urlsafe(24)}"
    return sign_value(raw_value, secret_key)


def _valid_csrf_token(token: str, settings: Settings) -> bool:
    value = verify_signed_value(token, settings.secret_key)
    if value is None:
        return False
    timestamp, separator, random_value = value.partition(":")
    if (
        not separator
        or not random_value
        or not timestamp.isascii()
        or not timestamp.isdecimal()
    ):
        return False
    try:
        age = int(time.time()) - int(timestamp)
    except ValueError:
        return False
    return 0 <= age < settings.session_max_age_seconds


def get_or_create_csrf_token(request: Request, settings: Settings) -> str:
    cached = getattr(request.state, "csrf_token", None)
    if cached:
        return cached

    existing = request.cookies.get(CSRF_COOKIE_NAME)
    if existing and _valid_csrf_token(existing, settings):
        request.state.csrf_token = existing
        return existing

    token = generate_csrf_token(settings.secret_key)
    request.state.csrf_token = token
    return token


def validate_csrf(
    request: Request, submitted_token: str | None, settings: Settings
) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not submitted_token or not cookie_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token."
        )
    if not hmac.compare_digest(
        submitted_token.encode("utf-8"), cookie_token.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token."
        )
    if not _valid_csrf_token(cookie_token, settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token."
        )
