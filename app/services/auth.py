from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException, Request, status

from app.core.config import Settings, pwd_context
from app.core.exceptions import AuthenticationError
from app.core.security import sign_value, verify_signed_value
from app.database.db import SessionLocal
from app.database.models import AdminSession


class SessionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # Password or secret rotation invalidates existing cookies.
        self.signing_key = hmac.new(
            settings.secret_key.encode("utf-8"),
            settings.admin_password_hash.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

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
        raw_value = (
            f"{self.settings.admin_username}:{expires_at}:{secrets.token_urlsafe(24)}"
        )
        token = sign_value(raw_value, self.signing_key)
        with SessionLocal() as db:
            db.query(AdminSession).filter(
                AdminSession.expires_at <= int(time.time())
            ).delete()
            db.add(
                AdminSession(token_hash=self._token_hash(token), expires_at=expires_at)
            )
            db.commit()
        return token

    def _decode_token(self, token: str | None) -> bool:
        if not token:
            return False

        value = verify_signed_value(token, self.signing_key)
        if value is None or value.count(":") < 2:
            return False

        username, expires_at, nonce = value.rsplit(":", 2)
        if not nonce:
            return False
        if username != self.settings.admin_username:
            return False

        try:
            remaining = int(expires_at) - int(time.time())
            if not 0 < remaining <= self.settings.session_max_age_seconds:
                return False
        except ValueError:
            return False
        with SessionLocal() as db:
            record = db.get(AdminSession, self._token_hash(token))
            return record is not None and record.expires_at == int(expires_at)

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def clear(self, token: str | None) -> None:
        if token:
            with SessionLocal() as db:
                db.query(AdminSession).filter(
                    AdminSession.token_hash == self._token_hash(token)
                ).delete()
                db.commit()

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
