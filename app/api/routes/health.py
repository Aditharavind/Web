"""Lightweight database connectivity check for health monitoring."""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database.db import engine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.api_route("/health", methods=["GET", "HEAD"])
def health_check() -> JSONResponse:
    # A normal endpoint keeps synchronous database I/O off the event loop.
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.warning("Health check could not reach the database.")
        return JSONResponse(
            {"status": "unhealthy", "db": False},
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )
    return JSONResponse(
        {"status": "ok", "db": True},
        headers={"Cache-Control": "no-store"},
    )
