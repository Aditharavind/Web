from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_title: str
    admin_username: str
    admin_password_hash: str
    secret_key: str
    admin_route: str
    products_per_page: int
    contact_whatsapp: str
    contact_email: str
    contact_website: str
    contact_address: str
    uploads_dir: Path
    static_dir: Path
    templates_dir: Path


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@lru_cache
def get_settings() -> Settings:
    uploads_dir = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads")

    return Settings(
        app_title="NAWA Global General Trading",
        admin_username=os.getenv("ADMIN_USERNAME", "admin"),
        admin_password_hash=os.getenv(
            "ADMIN_PASSWORD_HASH",
            _sha256(os.getenv("ADMIN_PASSWORD", "admin123")),
        ),
        secret_key=os.getenv("SECRET_KEY", secrets.token_hex(32)),
        admin_route=os.getenv("ADMIN_ROUTE", "/admin12"),
        products_per_page=int(os.getenv("PRODUCTS_PER_PAGE", "9")),
        contact_whatsapp=os.getenv("CONTACT_WHATSAPP", "+971505464847"),
        contact_email=os.getenv("CONTACT_EMAIL", "info@nawaglobalgtd.com"),
        contact_website=os.getenv("CONTACT_WEBSITE", "www.nawaglobalgtd.com"),
        contact_address=os.getenv(
            "CONTACT_ADDRESS", "Mussafah, Abu Dhabi, United Arab Emirates"
        ),
        uploads_dir=uploads_dir,
        static_dir=BASE_DIR / "app" / "static",
        templates_dir=BASE_DIR / "app" / "templates",
    )
