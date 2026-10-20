from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.core import content
from app.core.config import get_settings
from app.core.security import get_or_create_csrf_token
from app.utils.text import build_query_string, mailto_url, whatsapp_message_url, whatsapp_number

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))


def _static_asset_version() -> str:
    timestamps = (
        path.stat().st_mtime_ns
        for path in settings.static_dir.rglob("*")
        if path.is_file()
    )
    return str(max(timestamps, default=0))


STATIC_ASSET_VERSION = _static_asset_version()


def template_context(request: Request | None = None, **extra: object) -> dict[str, Any]:
    context: dict[str, Any] = {
        "settings": settings,
        "company_intro": content.INTRO,
        "mission": content.MISSION,
        "vision": content.VISION,
        "capabilities": content.CAPABILITIES,
        "reasons": content.REASONS,
        "current_year": datetime.now().year,
        "site_url": settings.site_url,
        "static_asset_version": STATIC_ASSET_VERSION,
        "primary_phone_display": "+971 50 546 4847"
        if settings.contact_whatsapp == "+971505464847"
        else settings.contact_whatsapp,
        "secondary_phone_display": "+971 50 661 2605"
        if settings.contact_secondary == "+971506612605"
        else settings.contact_secondary,
        "secondary_whatsapp_url": f"https://wa.me/{whatsapp_number(settings.contact_secondary)}",
        "contact_whatsapp_url": whatsapp_message_url(
            settings.contact_whatsapp,
            "Hello NAWA Global, I would like to enquire about your products.",
        ),
        "contact_email_url": mailto_url(
            settings.contact_email,
            subject="Product enquiry - NAWA Global",
            body="Hello NAWA Global,\n\nI would like to enquire about:\n\nProduct / part number:\nQuantity:\nDelivery location:\n",
        ),
        "page_description": (
            "NAWA Global General Trading supports oilfield and industrial procurement with "
            "components, MRO essentials, lubricants, safety products and sourcing coordination."
        ),
        "page_keywords": (
            "oilfield equipment supplier, industrial supply UAE, PPE supplier Abu Dhabi, "
            "lubricants supplier, NAWA Global"
        ),
        "canonical_url": None,
        "page_image": None,
        "meta_robots": "index,follow",
        "twitter_card": "summary_large_image",
        "og_type": "website",
        "schema_type": "WebSite",
        "structured_data": [],
        "build_query_string": build_query_string,
        "csp_nonce": getattr(request.state, "csp_nonce", "") if request else "",
        "csrf_token": get_or_create_csrf_token(request, settings) if request else "",
    }
    context.update(extra)
    return context
