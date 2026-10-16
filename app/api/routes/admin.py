"""Administrator pages and authenticated product actions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError as PydanticValidationError
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    DuplicateProductError,
    ProductNotFoundError,
    ValidationError,
)
from app.core.rate_limiter import allow_request
from app.core.security import validate_csrf
from app.core.templates import template_context, templates
from app.models.schemas import Product, ProductCreate, ProductUpdate
from app.services.auth import SessionService
from app.services.dependencies import (
    get_product_service,
    get_session_service,
    get_visit_service,
)
from app.services.product_service import ProductService
from app.services.visit_service import VisitService
from app.utils.text import build_query_string


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


router = APIRouter()
settings = get_settings()


def _redirect(path: str, **params: str) -> RedirectResponse:
    query_string = build_query_string(params)
    location = f"{path}?{query_string}" if query_string else path
    return RedirectResponse(location, status_code=303)


def _render_admin(request: Request, template: str, **context: object) -> Response:
    return templates.TemplateResponse(
        request,
        template,
        template_context(request, meta_robots="noindex,nofollow", **context),
    )


async def _allow_product_write(
    request: Request, csrf_token: str, session_service: SessionService
) -> bool:
    await run_in_threadpool(session_service.require_admin, request)
    validate_csrf(request, csrf_token, settings)
    return await allow_request(f"products:{_client_key(request)}", 20, 60)


def _split_specs(specs: str) -> list[str]:
    return [line.strip() for line in specs.splitlines() if line.strip()]


def _resolve_category_input(category: str, new_category: str) -> str:
    return new_category.strip() or category.strip()


def _validation_message(exc: Exception) -> str:
    if isinstance(exc, PydanticValidationError):
        first_error = exc.errors()[0]
        return str(first_error.get("msg", "Invalid data."))
    return str(exc)


def _product_rows(
    product_service: ProductService, products: list[Product]
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for product in products:
        rows.append(
            {"product": product, "images": product_service.get_product_images(product)}
        )
    return rows


@router.get(f"{settings.admin_route}")
def admin_root(
    request: Request, session_service: SessionService = Depends(get_session_service)
) -> RedirectResponse:
    destination = "dashboard" if session_service.is_admin(request) else "login"
    return _redirect(f"{settings.admin_route}/{destination}")


@router.get(f"{settings.admin_route}/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    error: str = "",
    session_service: SessionService = Depends(get_session_service),
) -> Response:
    if session_service.is_admin(request):
        return _redirect(f"{settings.admin_route}/dashboard")
    return _render_admin(
        request,
        "admin/login.html",
        page_title="Admin Login — NAWA Global",
        page_description="Secure administrator access for the NAWA Global product catalog.",
        error=error.strip(),
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
    if not await allow_request(f"login:{_client_key(request)}", 5, 300):
        return _redirect(
            f"{settings.admin_route}/login",
            error="Too many login attempts. Try again in five minutes.",
        )
    try:
        token = await run_in_threadpool(
            session_service.authenticate, username, password
        )
    except AuthenticationError:
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
def logout(
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
def dashboard(
    request: Request,
    session_service: SessionService = Depends(get_session_service),
    product_service: ProductService = Depends(get_product_service),
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    session_service.require_admin(request)
    summary = visit_service.summary()
    visits = visit_service.recent_visits(8)
    counts = product_service.counts()
    return _render_admin(
        request,
        "admin/dashboard.html",
        page_title="Dashboard — Admin",
        admin_section="dashboard",
        product_count=counts["products"],
        visits=visits,
        visit_summary=summary,
        category_count=counts["categories"],
    )


@router.get(f"{settings.admin_route}/products", response_class=HTMLResponse)
def admin_products(
    request: Request,
    msg: str = "",
    error: str = "",
    session_service: SessionService = Depends(get_session_service),
    product_service: ProductService = Depends(get_product_service),
) -> Response:
    session_service.require_admin(request)
    products = product_service.list_products()
    return _render_admin(
        request,
        "admin/products.html",
        page_title="Products — Admin",
        admin_section="products",
        product_rows=_product_rows(product_service, products),
        categories=product_service.get_categories(),
        message=msg.strip(),
        error=error.strip(),
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
    if not await _allow_product_write(request, csrf_token, session_service):
        return _redirect(
            f"{settings.admin_route}/products",
            error="Too many requests. Try again later.",
        )
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
        return _redirect(
            f"{settings.admin_route}/products", error="Product already exists"
        )
    except (ValidationError, PydanticValidationError, ProductNotFoundError) as exc:
        return _redirect(
            f"{settings.admin_route}/products", error=_validation_message(exc)
        )
    return _redirect(f"{settings.admin_route}/products", msg="Product added")


@router.get(
    f"{settings.admin_route}/products/edit/{{product_id}}", response_class=HTMLResponse
)
def edit_product_page(
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
    return _render_admin(
        request,
        "admin/edit_product.html",
        page_title="Edit — Admin",
        admin_section="products",
        categories=product_service.get_categories(),
        product=product,
        product_images=product_service.get_product_images(product),
        message=request.query_params.get("msg", "").strip(),
        error=request.query_params.get("error", "").strip(),
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
    edit_path = f"{settings.admin_route}/products/edit/{product_id}"
    if not await _allow_product_write(request, csrf_token, session_service):
        return _redirect(edit_path, error="Too many requests. Try again later.")
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
        return _redirect(edit_path, error="Product already exists")
    except ProductNotFoundError:
        return _redirect(f"{settings.admin_route}/products", error="Product not found.")
    except (ValidationError, PydanticValidationError) as exc:
        return _redirect(edit_path, error=_validation_message(exc))
    return _redirect(
        f"{settings.admin_route}/products", msg="Product updated successfully"
    )


@router.post(
    f"{settings.admin_route}/products/delete-image/{{product_id}}/{{filename}}"
)
async def delete_product_image(
    product_id: str,
    filename: str,
    request: Request,
    csrf_token: str = Form(...),
    session_service: SessionService = Depends(get_session_service),
    product_service: ProductService = Depends(get_product_service),
) -> RedirectResponse:
    edit_path = f"{settings.admin_route}/products/edit/{product_id}"
    if not await _allow_product_write(request, csrf_token, session_service):
        return _redirect(edit_path, error="Too many requests. Try again later.")
    try:
        await run_in_threadpool(
            product_service.delete_product_image, product_id, filename
        )
    except ProductNotFoundError:
        return _redirect(f"{settings.admin_route}/products", error="Product not found.")
    except ValidationError as exc:
        return _redirect(edit_path, error=str(exc))
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
    if not await _allow_product_write(request, csrf_token, session_service):
        return _redirect(
            f"{settings.admin_route}/products",
            error="Too many requests. Try again later.",
        )
    try:
        await run_in_threadpool(product_service.delete_product, product_id)
    except ProductNotFoundError as exc:
        return _redirect(f"{settings.admin_route}/products", error=str(exc))
    return _redirect(f"{settings.admin_route}/products", msg="Product deleted")


@router.get(f"{settings.admin_route}/visitors", response_class=HTMLResponse)
def visitors(
    request: Request,
    period: str = "week",
    session_service: SessionService = Depends(get_session_service),
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    session_service.require_admin(request)
    analytics = visit_service.analytics(period)
    return _render_admin(
        request,
        "admin/visitors.html",
        page_title="Visitors — Admin",
        admin_section="visitors",
        analytics=analytics,
        period=analytics["period"],
    )
