from __future__ import annotations

import logging
from typing import Optional
import os

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware



logger = logging.getLogger(__name__)


def setup_monitoring(app) -> Optional[object]:
    # Monitoring is optional in every environment.
    dsn = os.getenv("SENTRY_DSN", "")
    if not dsn:
        logger.info("No Sentry DSN provided; skipping error tracking setup.")
        return None

    sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
    sentry_sdk.init(dsn=dsn, integrations=[sentry_logging], traces_sample_rate=0.0)
    # attach middleware
    app.add_middleware(SentryAsgiMiddleware)
    logger.info("Sentry error tracking configured.")
    return sentry_sdk
