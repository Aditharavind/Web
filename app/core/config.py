from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = BASE_DIR / "app.db"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_site_url(value: str) -> str:
    site_url = value.strip()
    if not site_url:
        raise ValueError("SITE_URL must not be empty.")
    if not site_url.startswith(("http://", "https://")):
        site_url = f"https://{site_url}"
    return site_url.rstrip("/")


def _normalize_admin_route(value: str) -> str:
    route = value.strip() or "/admin"
    if not route.startswith("/"):
        route = f"/{route}"
    return route.rstrip("/") or "/admin"


def _parse_csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_title: str
    environment: str
    debug: bool
    is_production: bool
    site_url: str
    admin_username: str
    admin_password_hash: str
    secret_key: str
    admin_route: str
    log_level: str
    trusted_hosts: list[str]
    database_url: str
    products_per_page: int
    contact_whatsapp: str
    contact_email: str
    contact_website: str
    contact_website_url: str
    contact_address: str
    uploads_dir: Path
    static_dir: Path
    templates_dir: Path
    session_cookie_name: str
    session_max_age_seconds: int
    secure_cookies: bool
    max_upload_files: int
    max_upload_size_bytes: int
    image_max_dimension: int


@lru_cache
def get_settings() -> Settings:
    environment = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).strip().lower()
    is_production = environment == "production"
    debug = _as_bool(os.getenv("DEBUG"), default=not is_production) and not is_production

    site_url = _normalize_site_url(
        os.getenv("SITE_URL", os.getenv("CONTACT_WEBSITE", "http://localhost:8000")),
    )
    contact_website = os.getenv("CONTACT_WEBSITE", site_url.replace("https://", "").replace("http://", "")).strip()
    contact_website_url = _normalize_site_url(contact_website or site_url)
    uploads_dir = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads")

    admin_username = os.getenv("ADMIN_USERNAME", "admin").strip()
    admin_password_hash = os.getenv(
        "ADMIN_PASSWORD_HASH",
        _sha256(os.getenv("ADMIN_PASSWORD", "admin123")),
    ).strip()
    secret_key = os.getenv("SECRET_KEY", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()

    if is_production:
        missing = [
            name
            for name, value in {
                "DATABASE_URL": database_url,
                "SECRET_KEY": secret_key,
                "ADMIN_USERNAME": admin_username,
                "ADMIN_PASSWORD_HASH": admin_password_hash,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Missing required production environment variables: {', '.join(sorted(missing))}"
            )
        insecure_password_hash = admin_password_hash == _sha256("admin123")
        if admin_username == "admin" and insecure_password_hash:
            raise RuntimeError("Refusing to start in production with default admin credentials.")

    if not secret_key:
        secret_key = "dev-secret-key-change-me"
    if not database_url:
        database_url = f"sqlite:///{DEFAULT_SQLITE_PATH}"

    trusted_hosts = _parse_csv(
        os.getenv("TRUSTED_HOSTS"),
        ["localhost", "127.0.0.1", "testserver"],
    )
    if is_production:
        site_host = site_url.split("://", 1)[1]
        if site_host not in trusted_hosts:
            trusted_hosts.append(site_host)

    return Settings(
        app_title=os.getenv("APP_TITLE", "NAWA Global General Trading"),
        environment=environment,
        debug=debug,
        is_production=is_production,
        site_url=site_url,
        admin_username=admin_username,
        admin_password_hash=admin_password_hash,
        secret_key=secret_key,
        admin_route=_normalize_admin_route(os.getenv("ADMIN_ROUTE", "/admin12")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        trusted_hosts=trusted_hosts,
        database_url=database_url,
        products_per_page=max(1, int(os.getenv("PRODUCTS_PER_PAGE", "9"))),
        contact_whatsapp=os.getenv("CONTACT_WHATSAPP", "+971505464847").strip(),
        contact_email=os.getenv("CONTACT_EMAIL", "info@nawaglobalgtd.com").strip(),
        contact_website=contact_website,
        contact_website_url=contact_website_url,
        contact_address=os.getenv(
            "CONTACT_ADDRESS",
            "Mussafah, Abu Dhabi, United Arab Emirates",
        ).strip(),
        uploads_dir=uploads_dir,
        static_dir=BASE_DIR / "app" / "static",
        templates_dir=BASE_DIR / "app" / "templates",
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "session"),
        session_max_age_seconds=max(300, int(os.getenv("SESSION_MAX_AGE_SECONDS", "28800"))),
        secure_cookies=_as_bool(os.getenv("SECURE_COOKIES"), default=is_production),
        max_upload_files=max(1, int(os.getenv("MAX_UPLOAD_FILES", "10"))),
        max_upload_size_bytes=max(1024, int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(4 * 1024 * 1024)))),
        image_max_dimension=max(256, int(os.getenv("IMAGE_MAX_DIMENSION", "1600"))),
    )

