from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes.admin import router as admin_router
from app.api.routes.public import router as public_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.exceptions import AppError, DataAccessError, ProductNotFoundError, ValidationError
from app.core.logging import setup_logging
from app.core.monitoring import setup_monitoring
from app.core.security import CSRF_COOKIE_NAME, build_csp, generate_nonce, get_or_create_csrf_token
from app.core.templates import template_context, templates
from app.database import models  # noqa: F401
from app.database.db import ensure_database_schema


settings = get_settings()
setup_logging(settings)
logger = logging.getLogger(__name__)
settings.uploads_dir.mkdir(parents=True, exist_ok=True)


class CustomStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            if path.startswith("css/") or path.startswith("js/"):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                response.headers["Cache-Control"] = "public, max-age=86400"
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.csp_nonce = generate_nonce()
        response = await call_next(request)

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = build_csp(
            settings,
            request.state.csp_nonce,
        )
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        if request.url.path.startswith(settings.admin_route):
            response.headers["Cache-Control"] = "no-store"
        elif response.media_type == "text/html" and "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-cache"
        # Preload critical CSS to improve first render / Lighthouse
        if response.media_type == "text/html":
            response.headers.setdefault("Link", f'<{settings.site_url}/static/css/app.css>; rel=preload; as=style')

        csrf_token = get_or_create_csrf_token(request, settings)
        response.set_cookie(
            CSRF_COOKIE_NAME,
            csrf_token,
            httponly=True,
            secure=settings.secure_cookies,
            samesite="strict",
            max_age=settings.session_max_age_seconds,
            path="/",
        )
        return response


def _wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "application/json" in accept.lower()


def _error_payload(status_code: int, message: str) -> dict[str, object]:
    return {"error": {"status": status_code, "message": message}}


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting application in %s mode.", settings.environment)
    ensure_database_schema()
    yield
    logger.info("Application shutdown complete.")


app = FastAPI(title=settings.app_title, debug=False, lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
if settings.is_production:
    app.add_middleware(HTTPSRedirectMiddleware)

# setup optional monitoring (Sentry)
try:
    setup_monitoring(app)
except Exception:
    logger.exception("Failed to initialize monitoring")


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        logger.info(
            "%s %s %s %s",
            request.client.host if request.client else "-",
            request.method,
            request.url.path,
            response.status_code,
        )
        return response

app.add_middleware(AccessLogMiddleware)

app.mount("/static", CustomStaticFiles(directory=str(settings.static_dir)), name="static")
app.mount("/uploads", CustomStaticFiles(directory=str(settings.uploads_dir)), name="uploads")

app.include_router(public_router)
app.include_router(admin_router)
app.include_router(health_router)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> Response:
    if isinstance(exc, ValidationError):
        status_code = 400
        public_message = str(exc)
    elif isinstance(exc, ProductNotFoundError):
        status_code = 404
        public_message = "The requested resource was not found."
    else:
        status_code = 500 if isinstance(exc, DataAccessError) else 500
        public_message = (
            "A temporary server error occurred. Please try again later."
            if status_code == 500
            else str(exc)
        )

    if status_code >= 500:
        logger.exception("Application error on %s", request.url.path, exc_info=exc)
    else:
        logger.warning("Application error on %s: %s", request.url.path, exc)

    if _wants_json(request):
        return JSONResponse(_error_payload(status_code, public_message), status_code=status_code)

    return templates.TemplateResponse(
        request,
        "error.html",
        template_context(
            request,
            page_title="Application Error",
            error_title="Something went wrong" if status_code >= 500 else "Request failed",
            error_message=public_message,
            meta_robots="noindex,nofollow",
        ),
        status_code=status_code,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> Response:
    detail = (
        "Page not found."
        if exc.status_code == 404
        else str(exc.detail or "The request could not be completed.")
    )
    if _wants_json(request):
        return JSONResponse(_error_payload(exc.status_code, detail), status_code=exc.status_code)

    return templates.TemplateResponse(
        request,
        "error.html",
        template_context(
            request,
            page_title="Not Found" if exc.status_code == 404 else "Application Error",
            error_title="Page not found" if exc.status_code == 404 else "Request failed",
            error_message=detail,
            meta_robots="noindex,nofollow",
        ),
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> Response:
    logger.exception("Unhandled error on %s", request.url.path, exc_info=exc)
    message = "An unexpected error occurred. Please try again later."
    if _wants_json(request):
        return JSONResponse(_error_payload(500, message), status_code=500)
    return templates.TemplateResponse(
        request,
        "error.html",
        template_context(
            request,
            page_title="Server Error",
            error_title="Unexpected error",
            error_message=message,
            meta_robots="noindex,nofollow",
        ),
        status_code=500,
    )
