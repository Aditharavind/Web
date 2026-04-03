from __future__ import annotations

from urllib.parse import quote, unquote_plus, urlencode


def whatsapp_number(value: str) -> str:
    return value.replace("+", "").replace(" ", "")


def whatsapp_message_url(phone: str, message: str) -> str:
    return f"https://wa.me/{whatsapp_number(phone)}?text={quote(message)}"


def mailto_url(email: str, subject: str = "", body: str = "") -> str:
    query: dict[str, str] = {}
    if subject:
        query["subject"] = subject
    if body:
        query["body"] = body

    if not query:
        return f"mailto:{email}"

    # Use urlencode to correctly encode keys and values
    return f"mailto:{email}?{urlencode(query, quote_via=quote)}"


def decode_query_text(value: str | None) -> str:
    return unquote_plus(str(value or "")).strip()


def build_query_string(params: dict[str, str | int | None]) -> str:
    filtered = {
        key: str(value)
        for key, value in params.items()
        if value is not None and str(value) != ""
    }
    return urlencode(filtered, quote_via=quote)


def normalize_site_url(value: str) -> str:
    site_url = (value or "").strip()
    if not site_url:
        return ""
    if not site_url.startswith(("http://", "https://")):
        site_url = f"https://{site_url}"
    return site_url.rstrip("/")
