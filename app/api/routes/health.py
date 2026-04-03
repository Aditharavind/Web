from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from sqlalchemy import text
from app.database.db import engine

router = APIRouter()


@router.get("/health")
async def health_check():
    # basic liveness + DB connectivity check
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        return JSONResponse({"status": "unhealthy", "db": False, "error": str(exc)}, status_code=503)
    return JSONResponse({"status": "ok", "db": True})
