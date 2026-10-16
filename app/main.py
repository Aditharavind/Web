from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes.admin import router as admin_router
from app.api.routes.health import router as health_router
from app.api.routes.public import router as public_router
from app.core.config import get_settings
from app.core.exceptions import AppError, ProductNotFoundError, ValidationError
from app.core.logging import setup_logging
from app.core.monitoring import setup_monitoring
from app.core.rate_limiter import close_redis_client, get_redis_client
from app.core.security import (
    CSRF_COOKIE_NAME,
    build_csp,
    generate_nonce,
    get_or_create_csrf_token,
)
from app.core.templates import template_context, templates
from app.database import models  # noqa: F401
from app.database.db import engine, ensure_database_schema


settings = get_settings()
setup_logging(settings)
logger = logging.getLogger(__name__)
settings.uploads_dir.mkdir(parents=True, exist_ok=True)


class CustomStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            if path.startswith("css/") or path.startswith("js/"):
                response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
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

        path = request.url.path
        is_html = response.headers.get("content-type", "").startswith("text/html")
        is_asset = any(
            path == prefix or path.startswith(f"{prefix}/")
            for prefix in ("/static", "/uploads")
        )
        is_admin = path == settings.admin_route or path.startswith(
            f"{settings.admin_route}/"
        )
        if is_admin:
            response.headers["Cache-Control"] = "no-store"
        elif is_html and "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-cache"

        if is_html and not is_asset:
            response.headers.setdefault(
                "Link", "</static/css/app.css>; rel=preload; as=style"
            )
            csrf_token = get_or_create_csrf_token(request, settings)
            if request.cookies.get(CSRF_COOKIE_NAME) != csrf_token:
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
    redis = None
    try:
        ensure_database_schema()
        redis = get_redis_client()
        if redis is not None:
            await redis.ping()
        yield
    finally:
        try:
            if redis is not None:
                await close_redis_client(redis)
        finally:
            engine.dispose()
            logger.info("Application shutdown cleanup complete.")


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


app = FastAPI(
    title=settings.app_title,
    debug=False,
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

# Starlette runs user middleware in reverse registration order. Preserve:
# access log -> HTTPS (production) -> trusted host -> gzip -> security headers.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
if settings.is_production:
    app.add_middleware(HTTPSRedirectMiddleware)

try:
    setup_monitoring(app)
except Exception:
    logger.exception("Failed to initialize optional monitoring")

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
        status_code = 500
        public_message = "A temporary server error occurred. Please try again later."

    if status_code >= 500:
        logger.exception("Application error on %s", request.url.path, exc_info=exc)
    else:
        logger.warning("Application error on %s: %s", request.url.path, exc)

    if _wants_json(request):
        return JSONResponse(
            _error_payload(status_code, public_message), status_code=status_code
        )

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
    if 300 <= exc.status_code < 400 and exc.headers:
        return Response(status_code=exc.status_code, headers=exc.headers)
    detail = (
        "Page not found."
        if exc.status_code == 404
        else str(exc.detail or "The request could not be completed.")
    )
    if _wants_json(request):
        return JSONResponse(
            _error_payload(exc.status_code, detail),
            status_code=exc.status_code,
            headers=exc.headers,
        )

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
        headers=exc.headers,
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
