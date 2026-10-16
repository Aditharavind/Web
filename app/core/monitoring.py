"""Optional error tracking without performance tracing or request bodies."""

from __future__ import annotations

import logging
import os

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

logger = logging.getLogger(__name__)


def setup_monitoring() -> None:
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        logger.info("No Sentry DSN provided; skipping error tracking setup.")
        return

    # Framework integrations already install ASGI instrumentation.
    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            StarletteIntegration(),
            FastApiIntegration(),
        ],
        traces_sample_rate=0.0,
        send_default_pii=False,
        max_request_body_size="never",
    )
    logger.info("Sentry error tracking configured.")
