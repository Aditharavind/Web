from __future__ import annotations

import os
import secrets
import time

from fastapi import HTTPException, Request, status
from passlib.context import CryptContext

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.security import sign_value, verify_signed_value


# Use passlib CryptContext for bcrypt hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SessionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def authenticate(self, username: str, password: str) -> str:
        if secrets.compare_digest(username, self.settings.admin_username) is False:
            raise AuthenticationError("Invalid credentials")

        fallback_password = os.getenv("ADMIN_PASSWORD", "").strip()
        if fallback_password and secrets.compare_digest(password, fallback_password):
            expires_at = int(time.time()) + self.settings.session_max_age_seconds
            raw_value = f"{self.settings.admin_username}:{expires_at}"
            return sign_value(raw_value, self.settings.secret_key)

        # verify bcrypt hash if plain fallback is not configured or does not match
        stored = self.settings.admin_password_hash
        try:
            if not pwd_context.verify(password, stored):
                raise AuthenticationError("Invalid credentials")
        except Exception:
            raise AuthenticationError("Invalid credentials")

        expires_at = int(time.time()) + self.settings.session_max_age_seconds
        raw_value = f"{self.settings.admin_username}:{expires_at}"
        return sign_value(raw_value, self.settings.secret_key)

    def _decode_token(self, token: str | None) -> bool:
        if not token:
            return False

        value = verify_signed_value(token, self.settings.secret_key)
        if value is None or ":" not in value:
            return False

        username, expires_at = value.rsplit(":", 1)
        if username != self.settings.admin_username:
            return False

        try:
            return int(expires_at) >= int(time.time())
        except ValueError:
            return False

    def is_admin(self, request: Request) -> bool:
        return self._decode_token(request.cookies.get(self.settings.session_cookie_name))

    def require_admin(self, request: Request) -> None:
        if not self.is_admin(request):
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                headers={"Location": f"{self.settings.admin_route}/login"},
            )

    def clear(self, token: str | None) -> None:
        return None
