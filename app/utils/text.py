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


def build_query_string(params: dict[str, str | int | list[str] | None]) -> str:
    """Encode query parameters; list values become repeated keys."""
    pairs: list[tuple[str, str]] = []
    for key, value in params.items():
        values = value if isinstance(value, (list, tuple)) else [value]
        pairs.extend(
            (key, str(item)) for item in values if item is not None and str(item) != ""
        )
    return urlencode(pairs, quote_via=quote)
