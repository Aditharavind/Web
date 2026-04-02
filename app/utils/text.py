from __future__ import annotations

from urllib.parse import quote, urlencode


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

    encoded_items = [f"{key}={quote(value, safe='')}" for key, value in query.items()]
    return f"mailto:{email}?{'&'.join(encoded_items)}"
