from __future__ import annotations

import logging
from typing import Optional
import os

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

from app.core.config import get_settings


logger = logging.getLogger(__name__)


def setup_monitoring(app) -> Optional[object]:
    settings = get_settings()
    # Support optional SENTRY_DSN setting via env var; ensure it's present in production
    dsn = os.getenv("SENTRY_DSN", getattr(settings, "sentry_dsn", ""))
    if not dsn:
        if settings.is_production:
            raise RuntimeError("SENTRY_DSN must be set in production to enable error monitoring.")
        logger.info("No Sentry DSN provided; skipping error tracking setup.")
        return None

    sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
    sentry_sdk.init(dsn=dsn, integrations=[sentry_logging], traces_sample_rate=0.0)
    # attach middleware
    app.add_middleware(SentryAsgiMiddleware)
    logger.info("Sentry error tracking configured.")
    return sentry_sdk
