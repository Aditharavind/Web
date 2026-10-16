from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.core import content
from app.core.security import get_or_create_csrf_token
from app.utils.text import build_query_string, decode_query_text, whatsapp_number


settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))


def template_context(request: Request | None = None, **extra: object) -> dict[str, Any]:
    context: dict[str, Any] = {
        "settings": settings,
        "company_intro": content.INTRO,
        "mission": content.MISSION,
        "vision": content.VISION,
        "capabilities": content.CAPABILITIES,
        "values": content.VALUES,
        "reasons": content.REASONS,
        "sectors": content.SECTORS,
        "process": content.PROCESS,
        "current_year": datetime.now().year,
        "site_url": settings.site_url,
        "contact_whatsapp_number": whatsapp_number(settings.contact_whatsapp),
        "contact_whatsapp_url": f"https://wa.me/{whatsapp_number(settings.contact_whatsapp)}",
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
        "decode_query_text": decode_query_text,
        "csp_nonce": getattr(request.state, "csp_nonce", "") if request else "",
        "csrf_token": get_or_create_csrf_token(request, settings) if request else "",
    }
    context.update(extra)
    return context
