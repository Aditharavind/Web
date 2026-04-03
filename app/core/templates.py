from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.core.security import get_or_create_csrf_token
from app.utils.text import build_query_string, decode_query_text, whatsapp_number


settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))


def template_context(request: Request | None = None, **extra: object) -> dict[str, Any]:
    context: dict[str, Any] = {
        "settings": settings,
        "current_year": datetime.now().year,
        "site_url": settings.site_url,
        "contact_whatsapp_number": whatsapp_number(settings.contact_whatsapp),
        "contact_whatsapp_url": f"https://wa.me/{whatsapp_number(settings.contact_whatsapp)}",
        "page_description": (
            "NAWA Global General Trading supplies premium oilfield equipment, "
            "industrial consumables, lubricants, PPE, and sourcing support across the UAE."
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
        "decode_query_text": decode_query_text,
        "brands": [
            "Molyslip",
            "Arrow",
            "Unispec",
            "Lubriplate",
            "Jet-Lube",
            "Ketch-All",
            "Beta",
            "JOST",
            "3M",
            "Ansell",
            "Fortwest",
            "Deltaplus",
            "CAT",
            "Mitutoyo",
        ],
        "csp_nonce": getattr(request.state, "csp_nonce", "") if request else "",
        "csrf_token": get_or_create_csrf_token(request, settings) if request else "",
    }
    context.update(extra)
    return context
