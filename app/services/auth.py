from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, Request, status

from app.core.config import Settings
from app.core.exceptions import AuthenticationError


class SessionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sessions: dict[str, datetime] = {}

    def authenticate(self, username: str, password: str) -> str:
        password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if (
            username != self.settings.admin_username
            or password_hash != self.settings.admin_password_hash
        ):
            raise AuthenticationError("Invalid credentials")

        token = secrets.token_hex(32)
        self._sessions[token] = datetime.now() + timedelta(hours=8)
        return token

    def is_admin(self, request: Request) -> bool:
        token = request.cookies.get("session")
        if not token:
            return False

        expiry = self._sessions.get(token)
        if expiry is None or datetime.now() > expiry:
            self._sessions.pop(token, None)
            return False
        return True

    def require_admin(self, request: Request) -> None:
        if not self.is_admin(request):
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                headers={"Location": f"{self.settings.admin_route}/login"},
            )

    def clear(self, token: str | None) -> None:
        if token:
            self._sessions.pop(token, None)
