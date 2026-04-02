from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.config import get_settings
from app.core.exceptions import ProductNotFoundError
from app.core.templates import template_context, templates
from app.models.schemas import ContactInquiry
from app.services.dependencies import get_product_service, get_visit_service
from app.services.product_service import ProductService
from app.services.visit_service import VisitService
from app.utils.pagination import build_pagination
from app.utils.text import mailto_url, whatsapp_message_url, whatsapp_number


router = APIRouter()
settings = get_settings()


def _track_visit(request: Request, visit_service: VisitService) -> None:
    client = request.client.host if request.client else "unknown"
    visit_service.log_visit(client)


def _build_product_cards(
    products: list,
    product_service: ProductService,
) -> list[dict[str, object]]:
    cards: list[dict[str, object]] = []
    for product in products:
        images = product_service.get_product_images(product)
        cards.append(
            {
                "product": product,
                "images": images,
                "whatsapp_url": whatsapp_message_url(
                    settings.contact_whatsapp,
                    f"Hello! I'm interested in: *{product.name}*. Please send me details.",
                ),
                "email_url": mailto_url(
                    settings.contact_email,
                    subject=f"Product Inquiry: {product.name}",
                    body=(
                        f"Hello,\n\n"
                        f"I would like more information about {product.name}.\n\n"
                        f"Please share the product details, pricing, and availability.\n"
                    ),
                ),
            }
        )
    return cards


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    product_service: ProductService = Depends(get_product_service),
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    _track_visit(request, visit_service)
    products = product_service.list_products()
    categories = product_service.get_categories()
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            **template_context(
                page_title="NAWA Global General Trading — Premium Oilfield & Industrial Supply Partner",
                active_nav="home",
                recent_product_cards=_build_product_cards(
                    product_service.recent_products(6),
                    product_service,
                ),
                total_products=len(products),
                total_categories=len(categories),
                whatsapp_number=whatsapp_number(settings.contact_whatsapp),
                whatsapp_quote_url=whatsapp_message_url(
                    settings.contact_whatsapp,
                    "Hello! Please send me a quote for your industrial supply products.",
                ),
            ),
        },
    )


@router.get("/about", response_class=HTMLResponse)
async def about(
    request: Request,
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    _track_visit(request, visit_service)
    return templates.TemplateResponse(
        request,
        "about.html",
        {
            **template_context(
            page_title="About Us — NAWA Global General Trading",
            active_nav="about",
            ),
        },
    )


@router.get("/services", response_class=HTMLResponse)
async def services_page(
    request: Request,
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    _track_visit(request, visit_service)
    return templates.TemplateResponse(
        request,
        "services.html",
        {
            **template_context(
            page_title="Products & Services — NAWA Global General Trading",
            active_nav="services",
            ),
        },
    )


@router.get("/contact", response_class=HTMLResponse)
async def contact(
    request: Request,
    sent: str = "",
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    _track_visit(request, visit_service)
    return templates.TemplateResponse(
        request,
        "contact.html",
        {
            **template_context(
            page_title="Contact Us — NAWA Global General Trading",
            active_nav="contact",
            inquiry_sent=sent == "1",
            ),
        },
    )


@router.post("/contact")
async def contact_submit(
    name: str = Form(...),
    email: str = Form(...),
    company: str = Form(""),
    product: str = Form(""),
    message: str = Form(...),
) -> RedirectResponse:
    ContactInquiry(
        name=name,
        email=email,
        company=company,
        product=product,
        message=message,
    )
    return RedirectResponse("/contact?sent=1", status_code=303)


@router.get("/catalog", response_class=HTMLResponse)
async def catalog(
    request: Request,
    page: int = 1,
    q: str = "",
    cat: str = "",
    product_service: ProductService = Depends(get_product_service),
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    _track_visit(request, visit_service)
    result = product_service.search_catalog(page=page, query=q, category=cat)
    start = (result.page - 1) * settings.products_per_page
    result_start = start + 1 if result.total else 0
    result_end = min(start + settings.products_per_page, result.total)

    return templates.TemplateResponse(
        request,
        "catalog.html",
        {
            **template_context(
                page_title="Product Catalog — NAWA Global General Trading",
                active_nav="catalog",
                catalog=result,
                categories=product_service.get_categories(),
                pagination=build_pagination(result.page, result.total_pages),
                result_start=result_start,
                result_end=result_end,
                product_cards=_build_product_cards(result.items, product_service),
            ),
        },
    )


@router.get("/product/{product_id}", response_class=HTMLResponse)
async def product_detail(
    product_id: str,
    request: Request,
    product_service: ProductService = Depends(get_product_service),
) -> Response:
    try:
        product = product_service.get_product(product_id)
        product_images = product_service.get_product_images(product)
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        ) from exc

    return templates.TemplateResponse(
        request,
        "product_detail.html",
        {
            **template_context(
                page_title=f"{product.name} — NAWA Global",
                active_nav="catalog",
                product=product,
                product_images=product_images,
                product_image_urls=[f"/uploads/{image}" for image in product_images],
                whatsapp_url=whatsapp_message_url(
                    settings.contact_whatsapp,
                    f"Hello! I'm interested in: *{product.name}*. Please send details and a quote.",
                ),
                email_url=mailto_url(
                    settings.contact_email,
                    subject=f"Product Inquiry: {product.name}",
                    body=(
                        f"Hello,\n\n"
                        f"I'm interested in {product.name}.\n\n"
                        f"Please send the product details, quotation, and lead time.\n"
                    ),
                ),
            ),
        },
    )
