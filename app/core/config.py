from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from passlib.context import CryptContext

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = BASE_DIR / "app.db"


# CryptContext for bcrypt password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("Boolean settings must use true/false, yes/no, on/off, or 1/0.")


def _normalize_site_url(value: str) -> str:
    site_url = value.strip()
    if not site_url:
        raise ValueError("SITE_URL must not be empty.")
    if "://" not in site_url:
        site_url = f"https://{site_url}"
    try:
        parsed = urlsplit(site_url)
        _ = parsed.port  # Validate the optional port.
        valid = (
            parsed.scheme in {"http", "https"}
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
            and not any(character.isspace() for character in site_url)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(
            "Website URLs must be HTTP(S) origins without credentials, paths, queries, or fragments."
        )
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
    company_name: str
    contact_secondary: str
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
    environment = (
        os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development")).strip().lower()
    )
    if environment not in {"development", "testing", "production"}:
        raise ValueError("ENVIRONMENT must be development, testing, or production.")
    is_production = environment == "production"
    debug = (
        _as_bool(os.getenv("DEBUG"), default=not is_production) and not is_production
    )

    site_url = _normalize_site_url(
        os.getenv("SITE_URL", os.getenv("CONTACT_WEBSITE", "http://localhost:8000")),
    )
    contact_website = os.getenv("CONTACT_WEBSITE", "nawaglobalgtd.com").strip()
    contact_website_url = _normalize_site_url(contact_website or site_url)
    uploads_dir = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads")

    admin_username = os.getenv("ADMIN_USERNAME", "admin").strip()
    # prefer bcrypt hashed password via ADMIN_PASSWORD_HASH; in dev, allow ADMIN_PASSWORD and
    # derive bcrypt hash for runtime use.
    admin_password_hash = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
    if not admin_password_hash and not is_production:
        admin_password_plain = os.getenv("ADMIN_PASSWORD", "admin123")
        admin_password_hash = pwd_context.hash(admin_password_plain)
    secret_key = os.getenv("SECRET_KEY", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()

    if is_production:
        required = {
            "DATABASE_URL": database_url,
            "SECRET_KEY": secret_key,
            "ADMIN_USERNAME": os.getenv("ADMIN_USERNAME", "").strip(),
            "ADMIN_PASSWORD_HASH": admin_password_hash,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError("Missing production settings: " + ", ".join(missing))
        if len(secret_key) < 32 or secret_key == "dev-secret-key-change-me":
            raise ValueError(
                "SECRET_KEY must be a strong random value of at least 32 characters."
            )
        if not site_url.startswith("https://"):
            raise ValueError("Production SITE_URL must use HTTPS.")
        if not _as_bool(os.getenv("SECURE_COOKIES"), default=True):
            raise ValueError("Production requires secure cookies.")
        if not admin_password_hash.startswith(("$2a$", "$2b$", "$2y$")):
            raise ValueError("ADMIN_PASSWORD_HASH must be a bcrypt hash.")
        try:
            default_password = pwd_context.verify("admin123", admin_password_hash)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                "ADMIN_PASSWORD_HASH must be a valid bcrypt hash."
            ) from exc
        if default_password:
            raise ValueError("Default admin password is forbidden in production.")

    secret_key = secret_key or "dev-secret-key-change-me"
    database_url = database_url or f"sqlite:///{DEFAULT_SQLITE_PATH}"

    trusted_hosts = _parse_csv(
        os.getenv("TRUSTED_HOSTS"),
        [] if is_production else ["localhost", "127.0.0.1", "testserver"],
    )
    if is_production and "*" in trusted_hosts:
        raise ValueError(
            "Production TRUSTED_HOSTS must name explicit hosts or domain patterns."
        )
    site_host = urlsplit(site_url).hostname
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
        company_name=os.getenv(
            "COMPANY_NAME", "Nawa Global General Trading LLC SPC"
        ).strip(),
        contact_secondary=os.getenv("CONTACT_SECONDARY", "+971506612605").strip(),
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
        session_max_age_seconds=max(
            300, int(os.getenv("SESSION_MAX_AGE_SECONDS", "28800"))
        ),
        secure_cookies=_as_bool(os.getenv("SECURE_COOKIES"), default=is_production),
        max_upload_files=max(1, int(os.getenv("MAX_UPLOAD_FILES", "10"))),
        max_upload_size_bytes=max(
            1024, int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(4 * 1024 * 1024)))
        ),
        image_max_dimension=max(256, int(os.getenv("IMAGE_MAX_DIMENSION", "1600"))),
    )
