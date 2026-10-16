from __future__ import annotations

import secrets
import time

from fastapi import HTTPException, Request, status

from app.core.config import Settings, pwd_context
from app.core.exceptions import AuthenticationError
from app.core.security import sign_value, verify_signed_value


class SessionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def authenticate(self, username: str, password: str) -> str:
        if not secrets.compare_digest(
            username.encode("utf-8"), self.settings.admin_username.encode("utf-8")
        ):
            raise AuthenticationError("Invalid credentials")

        # bcrypt only considers the first 72 bytes; never accept a truncated password.
        if len(password.encode("utf-8")) > 72:
            raise AuthenticationError("Invalid credentials")
        try:
            valid = pwd_context.verify(password, self.settings.admin_password_hash)
        except (ValueError, TypeError) as exc:
            raise AuthenticationError("Invalid credentials") from exc
        if not valid:
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
            remaining = int(expires_at) - int(time.time())
            return 0 < remaining <= self.settings.session_max_age_seconds
        except ValueError:
            return False

    def is_admin(self, request: Request) -> bool:
        return self._decode_token(
            request.cookies.get(self.settings.session_cookie_name)
        )

    def require_admin(self, request: Request) -> None:
        if not self.is_admin(request):
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                headers={"Location": f"{self.settings.admin_route}/login"},
            )
