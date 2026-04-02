from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes.admin import router as admin_router
from app.api.routes.public import router as public_router
from app.core.config import get_settings
from app.core.exceptions import AppError, DataAccessError, ValidationError
from app.core.templates import template_context, templates
from app.database import models  # noqa: F401
from app.database.db import ensure_postgres_schema


settings = get_settings()
settings.uploads_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_postgres_schema()
    yield


app = FastAPI(title=settings.app_title, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
app.mount("/uploads", StaticFiles(directory=str(settings.uploads_dir)), name="uploads")

app.include_router(public_router)
app.include_router(admin_router)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> HTMLResponse:
    status_code = 400 if isinstance(exc, ValidationError) else 500
    if isinstance(exc, DataAccessError):
        status_code = 500

    return templates.TemplateResponse(
        request,
        "error.html",
        template_context(
            page_title="Application Error",
            error_title="Something went wrong",
            error_message=str(exc),
        ),
        status_code=status_code,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> HTMLResponse:
    if exc.status_code != 404:
        return templates.TemplateResponse(
            request,
            "error.html",
            template_context(
                page_title="Application Error",
                error_title="Request failed",
                error_message=str(exc.detail),
            ),
            status_code=exc.status_code,
        )

    return templates.TemplateResponse(
        request,
        "error.html",
        template_context(
            page_title="Not Found",
            error_title="Page not found",
            error_message=str(exc.detail),
        ),
        status_code=404,
    )
