from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError as PydanticValidationError

from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    DuplicateProductError,
    ProductNotFoundError,
    ValidationError,
)
from app.core.security import validate_csrf
from app.core.templates import template_context, templates
from app.models.schemas import ProductCreate, ProductUpdate
from app.services.auth import SessionService
from app.services.dependencies import (
    get_product_service,
    get_session_service,
    get_visit_service,
)
from app.services.product_service import ProductService
from app.services.visit_service import VisitService
from app.utils.text import build_query_string, decode_query_text
from app.core.rate_limiter import allow_request


# Simple brute-force protection: track recent failed attempts per client for login
_FAILED_LOGIN: dict[str, list[float]] = {}
_LOCKOUT_SECONDS = 300
_MAX_FAILED = 5


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _is_locked(request: Request) -> bool:
    key = _client_key(request)
    attempts = _FAILED_LOGIN.get(key, [])
    now = __import__("time").time()
    # clear old
    attempts = [t for t in attempts if t + _LOCKOUT_SECONDS > now]
    _FAILED_LOGIN[key] = attempts
    return len(attempts) >= _MAX_FAILED


def _record_failed(request: Request) -> None:
    key = _client_key(request)
    _FAILED_LOGIN.setdefault(key, []).append(__import__("time").time())


router = APIRouter()
settings = get_settings()


def _redirect(path: str, **params: str) -> RedirectResponse:
    query_string = build_query_string(params)
    location = f"{path}?{query_string}" if query_string else path
    return RedirectResponse(location, status_code=303)


def _split_specs(specs: str) -> list[str]:
    return [line.strip() for line in specs.splitlines() if line.strip()]


def _resolve_category_input(category: str, new_category: str) -> str:
    return (new_category or category).strip()


def _validation_message(exc: Exception) -> str:
    if isinstance(exc, PydanticValidationError):
        first_error = exc.errors()[0]
        return str(first_error.get("msg", "Invalid data."))
    return str(exc)


def _product_rows(
    product_service: ProductService,
    products: list[object],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for product in products:
        rows.append(
            {
                "product": product,
                "images": product_service.get_product_images(product),
            }
        )
    return rows


@router.get(f"{settings.admin_route}")
async def admin_root() -> RedirectResponse:
    return _redirect(f"{settings.admin_route}/login")


@router.get(f"{settings.admin_route}/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    error: str = "",
    session_service: SessionService = Depends(get_session_service),
) -> Response:
    if session_service.is_admin(request):
        return _redirect(f"{settings.admin_route}/dashboard")

    return templates.TemplateResponse(
        request,
        "admin/login.html",
        template_context(
            request,
            page_title="Admin Login — NAWA Global",
            page_description="Secure administrator access for the NAWA Global product catalog.",
            meta_robots="noindex,nofollow",
            error=decode_query_text(error),
        ),
    )


@router.post(f"{settings.admin_route}/login")
async def do_login(
    request: Request,
    csrf_token: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    session_service: SessionService = Depends(get_session_service),
) -> RedirectResponse:
    validate_csrf(request, csrf_token, settings)
    # Check lockout
    if _is_locked(request):
        return _redirect(f"{settings.admin_route}/login", error="Too many failed login attempts. Try again later.")
    # simple per-IP rate limit for login: allow 10 per 60s
    if not await allow_request(_client_key(request), 10, 60):
        return _redirect(f"{settings.admin_route}/login", error="Too many requests. Slow down.")
    try:
        token = session_service.authenticate(username, password)
    except AuthenticationError:
        _record_failed(request)
        return _redirect(f"{settings.admin_route}/login", error="Invalid credentials")

    response = _redirect(f"{settings.admin_route}/dashboard")
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=settings.session_max_age_seconds,
        path="/",
    )
    return response


@router.post(f"{settings.admin_route}/logout")
async def logout(
    request: Request,
    csrf_token: str = Form(...),
    session_service: SessionService = Depends(get_session_service),
) -> RedirectResponse:
    validate_csrf(request, csrf_token, settings)
    session_service.clear(request.cookies.get(settings.session_cookie_name))
    response = _redirect(f"{settings.admin_route}/login")
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response


@router.get(f"{settings.admin_route}/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    session_service: SessionService = Depends(get_session_service),
    product_service: ProductService = Depends(get_product_service),
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    session_service.require_admin(request)
    summary = visit_service.summary()
    visits = visit_service.list_visits()
    products = product_service.list_products()
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        template_context(
            request,
            page_title="Dashboard — Admin",
            meta_robots="noindex,nofollow",
            admin_section="dashboard",
            products=products,
            visits=visits,
            visit_summary=summary,
            category_count=len({product.category for product in products}),
        ),
    )


@router.get(f"{settings.admin_route}/products", response_class=HTMLResponse)
async def admin_products(
    request: Request,
    msg: str = "",
    error: str = "",
    session_service: SessionService = Depends(get_session_service),
    product_service: ProductService = Depends(get_product_service),
) -> Response:
    session_service.require_admin(request)
    products = product_service.list_products()
    return templates.TemplateResponse(
        request,
        "admin/products.html",
        template_context(
            request,
            page_title="Products — Admin",
            meta_robots="noindex,nofollow",
            admin_section="products",
            product_rows=_product_rows(product_service, products),
            categories=product_service.get_categories(),
            message=decode_query_text(msg),
            error=decode_query_text(error),
        ),
    )


@router.post(f"{settings.admin_route}/products/add")
async def add_product(
    request: Request,
    csrf_token: str = Form(...),
    name: str = Form(...),
    category: str = Form(""),
    new_category: str = Form(""),
    description: str = Form(""),
    specs: str = Form(""),
    tags: str = Form(""),
    images: list[UploadFile] = File(default=[]),
    session_service: SessionService = Depends(get_session_service),
    product_service: ProductService = Depends(get_product_service),
) -> RedirectResponse:
    session_service.require_admin(request)
    validate_csrf(request, csrf_token, settings)
    # protect product creation from mass requests
    if not await allow_request(_client_key(request), 20, 60):
        return _redirect(f"{settings.admin_route}/products", error="Too many requests. Try again later.")
    try:
        await product_service.create_product(
            ProductCreate(
                name=name,
                category=_resolve_category_input(category, new_category),
                description=description,
                specs=_split_specs(specs),
                tags=tags,
            ),
            images,
        )
    except DuplicateProductError:
        return _redirect(f"{settings.admin_route}/products", error="Product already exists")
    except (ValidationError, PydanticValidationError, ProductNotFoundError) as exc:
        return _redirect(f"{settings.admin_route}/products", error=_validation_message(exc))

    return _redirect(f"{settings.admin_route}/products", msg="Product added")


@router.get(f"{settings.admin_route}/products/edit/{{product_id}}", response_class=HTMLResponse)
async def edit_product_page(
    product_id: str,
    request: Request,
    session_service: SessionService = Depends(get_session_service),
    product_service: ProductService = Depends(get_product_service),
) -> Response:
    session_service.require_admin(request)
    try:
        product = product_service.get_product(product_id)
    except ProductNotFoundError:
        return _redirect(f"{settings.admin_route}/products")

    return templates.TemplateResponse(
        request,
        "admin/edit_product.html",
        template_context(
            request,
            page_title="Edit — Admin",
            meta_robots="noindex,nofollow",
            admin_section="products",
            categories=product_service.get_categories(),
            product=product,
            product_images=product_service.get_product_images(product),
            message=decode_query_text(request.query_params.get("msg")),
            error=decode_query_text(request.query_params.get("error")),
        ),
    )


@router.post(f"{settings.admin_route}/products/edit/{{product_id}}")
async def update_product(
    product_id: str,
    request: Request,
    csrf_token: str = Form(...),
    name: str = Form(...),
    category: str = Form(""),
    new_category: str = Form(""),
    description: str = Form(""),
    specs: str = Form(""),
    tags: str = Form(""),
    images: list[UploadFile] = File(default=[]),
    session_service: SessionService = Depends(get_session_service),
    product_service: ProductService = Depends(get_product_service),
) -> RedirectResponse:
    session_service.require_admin(request)
    validate_csrf(request, csrf_token, settings)
    if not await allow_request(_client_key(request), 20, 60):
        return _redirect(f"{settings.admin_route}/products", error="Too many requests. Try again later.")
    try:
        await product_service.update_product(
            product_id,
            ProductUpdate(
                name=name,
                category=_resolve_category_input(category, new_category),
                description=description,
                specs=_split_specs(specs),
                tags=tags,
            ),
            images,
        )
    except DuplicateProductError:
        return _redirect(f"{settings.admin_route}/products", error="Product already exists")
    except (ValidationError, ProductNotFoundError, PydanticValidationError) as exc:
        return _redirect(f"{settings.admin_route}/products", error=_validation_message(exc))

    return _redirect(f"{settings.admin_route}/products", msg="Product updated successfully")


@router.post(f"{settings.admin_route}/products/delete-image/{{product_id}}/{{filename}}")
async def delete_product_image(
    product_id: str,
    filename: str,
    request: Request,
    csrf_token: str = Form(...),
    session_service: SessionService = Depends(get_session_service),
    product_service: ProductService = Depends(get_product_service),
) -> RedirectResponse:
    session_service.require_admin(request)
    validate_csrf(request, csrf_token, settings)
    try:
        product_service.delete_product_image(product_id, filename)
    except (ProductNotFoundError, ValidationError) as exc:
        return _redirect(f"{settings.admin_route}/products", error=str(exc))
    return _redirect(
        f"{settings.admin_route}/products/edit/{product_id}",
        msg="Image deleted successfully",
    )


@router.post(f"{settings.admin_route}/products/delete/{{product_id}}")
async def delete_product(
    product_id: str,
    request: Request,
    csrf_token: str = Form(...),
    session_service: SessionService = Depends(get_session_service),
    product_service: ProductService = Depends(get_product_service),
) -> RedirectResponse:
    session_service.require_admin(request)
    validate_csrf(request, csrf_token, settings)
    if not await allow_request(_client_key(request), 20, 60):
        return _redirect(f"{settings.admin_route}/products", error="Too many requests. Try again later.")
    try:
        product_service.delete_product(product_id)
    except ProductNotFoundError as exc:
        return _redirect(f"{settings.admin_route}/products", error=str(exc))
    return _redirect(f"{settings.admin_route}/products", msg="Product deleted")


@router.get(f"{settings.admin_route}/visitors", response_class=HTMLResponse)
async def visitors(
    request: Request,
    period: str = "week",
    session_service: SessionService = Depends(get_session_service),
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    session_service.require_admin(request)
    analytics = visit_service.analytics(period)
    return templates.TemplateResponse(
        request,
        "admin/visitors.html",
        template_context(
            request,
            page_title="Visitors — Admin",
            meta_robots="noindex,nofollow",
            admin_section="visitors",
            analytics=analytics,
            period=analytics["period"],
        ),
    )
