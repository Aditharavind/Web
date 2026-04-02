from __future__ import annotations

from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError as PydanticValidationError

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ProductNotFoundError, ValidationError
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


router = APIRouter()
settings = get_settings()


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def _split_specs(specs: str) -> list[str]:
    return [line.strip() for line in specs.splitlines() if line.strip()]


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
        template_context(page_title="Admin Login — NAWA Global", error=error),
    )


@router.post(f"{settings.admin_route}/login")
async def do_login(
    username: str = Form(...),
    password: str = Form(...),
    session_service: SessionService = Depends(get_session_service),
) -> RedirectResponse:
    try:
        token = session_service.authenticate(username, password)
    except AuthenticationError:
        return _redirect(f"{settings.admin_route}/login?error=Invalid+credentials")

    response = _redirect(f"{settings.admin_route}/dashboard")
    response.set_cookie("session", token, httponly=True, samesite="lax", max_age=28800)
    return response


@router.get(f"{settings.admin_route}/logout")
async def logout(
    request: Request,
    session_service: SessionService = Depends(get_session_service),
) -> RedirectResponse:
    session_service.clear(request.cookies.get("session"))
    response = _redirect(f"{settings.admin_route}/login")
    response.delete_cookie("session")
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
            page_title="Dashboard — Admin",
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
            page_title="Products — Admin",
            admin_section="products",
            product_rows=_product_rows(product_service, products),
            message=msg,
            error=error,
        ),
    )


@router.post(f"{settings.admin_route}/products/add")
async def add_product(
    request: Request,
    name: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    specs: str = Form(""),
    tags: str = Form(""),
    images: list[UploadFile] = File(default=[]),
    session_service: SessionService = Depends(get_session_service),
    product_service: ProductService = Depends(get_product_service),
) -> RedirectResponse:
    session_service.require_admin(request)
    try:
        await product_service.create_product(
            ProductCreate(
                name=name,
                category=category,
                description=description,
                specs=_split_specs(specs),
                tags=tags,
            ),
            images,
        )
    except (ValidationError, PydanticValidationError) as exc:
        return _redirect(
            f"{settings.admin_route}/products?error={quote_plus(_validation_message(exc))}"
        )

    return _redirect(f"{settings.admin_route}/products?msg=Product+added+successfully")


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
            page_title="Edit — Admin",
            admin_section="products",
            product=product,
            product_images=product_service.get_product_images(product),
        ),
    )


@router.post(f"{settings.admin_route}/products/edit/{{product_id}}")
async def update_product(
    product_id: str,
    request: Request,
    name: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    specs: str = Form(""),
    tags: str = Form(""),
    images: list[UploadFile] = File(default=[]),
    session_service: SessionService = Depends(get_session_service),
    product_service: ProductService = Depends(get_product_service),
) -> RedirectResponse:
    session_service.require_admin(request)
    try:
        await product_service.update_product(
            product_id,
            ProductUpdate(
                name=name,
                category=category,
                description=description,
                specs=_split_specs(specs),
                tags=tags,
            ),
            images,
        )
    except (ValidationError, ProductNotFoundError, PydanticValidationError) as exc:
        return _redirect(
            f"{settings.admin_route}/products?error={quote_plus(_validation_message(exc))}"
        )

    return _redirect(f"{settings.admin_route}/products?msg=Product+updated+successfully")


@router.get(f"{settings.admin_route}/products/delete-image/{{product_id}}/{{filename}}")
async def delete_product_image(
    product_id: str,
    filename: str,
    request: Request,
    session_service: SessionService = Depends(get_session_service),
    product_service: ProductService = Depends(get_product_service),
) -> RedirectResponse:
    session_service.require_admin(request)
    try:
        product_service.delete_product_image(product_id, filename)
    except ProductNotFoundError as exc:
        return _redirect(f"{settings.admin_route}/products?error={quote_plus(str(exc))}")
    return _redirect(
        f"{settings.admin_route}/products/edit/{product_id}?msg=Image+deleted+successfully"
    )


@router.get(f"{settings.admin_route}/products/delete/{{product_id}}")
async def delete_product(
    product_id: str,
    request: Request,
    session_service: SessionService = Depends(get_session_service),
    product_service: ProductService = Depends(get_product_service),
) -> RedirectResponse:
    session_service.require_admin(request)
    try:
        product_service.delete_product(product_id)
    except ProductNotFoundError as exc:
        return _redirect(f"{settings.admin_route}/products?error={quote_plus(str(exc))}")
    return _redirect(f"{settings.admin_route}/products?msg=Product+deleted")


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
            page_title="Visitors — Admin",
            admin_section="visitors",
            analytics=analytics,
            period=analytics["period"],
        ),
    )
