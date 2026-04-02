from __future__ import annotations

from datetime import datetime

from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.utils.text import whatsapp_number


settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))


def template_context(**extra: object) -> dict[str, object]:
    return {
        "settings": settings,
        "current_year": datetime.now().year,
        "contact_whatsapp_number": whatsapp_number(settings.contact_whatsapp),
        "contact_whatsapp_url": f"https://wa.me/{whatsapp_number(settings.contact_whatsapp)}",
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
        **extra,
    }
