from __future__ import annotations

from urllib.parse import quote, urlencode


def whatsapp_number(value: str) -> str:
    return "".join(character for character in value if "0" <= character <= "9")


def whatsapp_message_url(phone: str, message: str) -> str:
    return f"https://wa.me/{whatsapp_number(phone)}?text={quote(message, safe='')}"


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


def build_query_string(params: dict[str, str | int | None]) -> str:
    filtered = {
        key: str(value)
        for key, value in params.items()
        if value is not None and str(value) != ""
    }
    return urlencode(filtered, quote_via=quote)
