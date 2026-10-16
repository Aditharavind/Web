"""Generated contact and catalogue links preserve user-entered text."""

from urllib.parse import parse_qs, urlsplit

from app.utils.pagination import build_pagination
from app.utils.text import (
    build_query_string,
    mailto_url,
    whatsapp_message_url,
    whatsapp_number,
)


def test_whatsapp_link_handles_phone_formatting_and_message_text():
    assert whatsapp_number("+971 (50) 546-4847") == "971505464847"
    message = "Valve A+B / 50% & seals? قطر"
    link = urlsplit(whatsapp_message_url("+971 (50) 546-4847", message))
    assert link.netloc == "wa.me"
    assert link.path == "/971505464847"
    assert parse_qs(link.query) == {"text": [message]}


def test_email_and_catalogue_query_round_trip():
    text = "A+B & 50% / fittings"
    email = urlsplit(
        mailto_url("info@nawaglobalgtd.com", subject=text, body="Hello\n" + text)
    )
    assert email.scheme == "mailto"
    assert parse_qs(email.query) == {"subject": [text], "body": ["Hello\n" + text]}
    assert mailto_url("info@nawaglobalgtd.com") == "mailto:info@nawaglobalgtd.com"
    query = build_query_string({"q": text, "cat": "", "unused": None, "page": 0})
    assert parse_qs(query) == {"q": [text], "page": ["0"]}


def test_large_pagination_is_bounded_and_has_one_active_page():
    pages = build_pagination(5000, 10000)
    numbered = [item for item in pages if item["kind"] == "page"]
    assert numbered[0]["value"] == 1
    assert numbered[-1]["value"] == 10000
    assert [item["value"] for item in numbered if item["active"]] == [5000]
    assert len(pages) <= 9
    assert build_pagination(1, 1) == []
