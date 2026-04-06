from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from pydantic import ValidationError as PydanticValidationError
from xml.sax.saxutils import escape

from app.core.config import get_settings
from app.core.exceptions import ProductNotFoundError, ValidationError
from app.core.security import validate_csrf
from app.core.templates import template_context, templates
from app.models.schemas import ContactInquiry
from app.services.dependencies import get_product_service, get_visit_service
from fastapi.concurrency import run_in_threadpool
from app.services.product_service import ProductService
from app.services.visit_service import VisitService
from app.utils.pagination import build_pagination
from app.utils.text import (
    build_query_string,
    decode_query_text,
    mailto_url,
    normalize_site_url,
    whatsapp_message_url,
    whatsapp_number,
)


router = APIRouter()
settings = get_settings()
from app.core.rate_limiter import allow_request



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
    products = await run_in_threadpool(product_service.list_products)
    categories = await run_in_threadpool(product_service.get_categories)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            **template_context(
                request,
                page_title="NAWA Global General Trading — Premium Oilfield & Industrial Supply Partner",
                page_description=(
                    "NAWA Global General Trading supplies oilfield equipment, industrial "
                    "consumables, lubricants, PPE, and custom sourcing support in Abu Dhabi and across the UAE."
                ),
                canonical_url=normalize_site_url(str(request.url)),
                active_nav="home",
                recent_product_cards=_build_product_cards(
                    await run_in_threadpool(product_service.recent_products, 6),
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
                request,
                page_title="About Us — NAWA Global General Trading",
                page_description=(
                    "Learn about NAWA Global General Trading, our industrial sourcing capabilities, "
                    "quality-first approach, and sectors we serve."
                ),
                canonical_url=normalize_site_url(str(request.url)),
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
                request,
                page_title="Products & Services — NAWA Global General Trading",
                page_description=(
                    "Explore NAWA Global's oilfield spare parts, industrial supplies, lubricants, "
                    "safety PPE, and custom procurement services."
                ),
                canonical_url=normalize_site_url(str(request.url)),
                active_nav="services",
            ),
        },
    )


@router.get("/contact", response_class=HTMLResponse)
async def contact(
    request: Request,
    sent: str = "",
    error: str = "",
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    _track_visit(request, visit_service)
    return templates.TemplateResponse(
        request,
        "contact.html",
        {
            **template_context(
                request,
                page_title="Contact Us — NAWA Global General Trading",
                page_description=(
                    "Contact NAWA Global for industrial supply inquiries, quotes, and WhatsApp support."
                ),
                canonical_url=f"{settings.site_url}/contact",
                active_nav="contact",
                inquiry_sent=sent == "1",
                inquiry_error=decode_query_text(error),
                schema_type="ContactPage",
            ),
        },
    )


@router.post("/contact")
async def contact_submit(
    request: Request,
    csrf_token: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    company: str = Form(""),
    product: str = Form(""),
    message: str = Form(...),
) -> RedirectResponse:
    validate_csrf(request, csrf_token, settings)
    # basic rate limit per client to avoid spam
    key = request.client.host if request.client else "unknown"
    if not await allow_request(key, 5, 60):
        return RedirectResponse("/contact?" + "error=Too+many+requests", status_code=303)
    try:
        ContactInquiry(
            name=name,
            email=email,
            company=company,
            product=product,
            message=message,
        )
    except PydanticValidationError as exc:
        first_error = exc.errors()[0]
        error_message = str(first_error.get("msg", "Invalid inquiry details."))
        return RedirectResponse(
            f"/contact?{build_query_string({'error': error_message})}",
            status_code=303,
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
    result = await run_in_threadpool(product_service.search_catalog, page, q, cat)
    start = (result.page - 1) * settings.products_per_page
    result_start = start + 1 if result.total else 0
    result_end = min(start + settings.products_per_page, result.total)

    return templates.TemplateResponse(
        request,
        "catalog.html",
        {
            **template_context(
                request,
                page_title="Product Catalog — NAWA Global General Trading",
                page_description=(
                    "Browse NAWA Global's catalog of oilfield equipment, industrial products, "
                    "lubricants, and PPE."
                ),
                canonical_url=normalize_site_url(
                    str(
                        request.url.replace_query_params(
                            **{
                                key: value
                                for key, value in {
                                    "q": result.query or None,
                                    "cat": result.category or None,
                                    "page": result.page if result.page > 1 else None,
                                }.items()
                                if value is not None
                            }
                        )
                    )
                ),
                active_nav="catalog",
                catalog=result,
                categories=await run_in_threadpool(product_service.get_categories),
                pagination=build_pagination(result.page, result.total_pages),
                result_start=result_start,
                result_end=result_end,
                product_cards=_build_product_cards(result.items, product_service),
                schema_type="CollectionPage",
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
        product = await run_in_threadpool(product_service.get_product, product_id)
        product_images = await run_in_threadpool(product_service.get_product_images, product)
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        ) from exc

    return templates.TemplateResponse(
        request,
        "product_detail.html",
        {
            **template_context(
                request,
                page_title=f"{product.name} — NAWA Global",
                page_description=(
                    product.description[:150]
                    if product.description
                    else f"View specifications and inquiry options for {product.name} from NAWA Global."
                ),
                canonical_url=normalize_site_url(str(request.url)),
                active_nav="catalog",
                product=product,
                product_images=product_images,
                product_image_urls=[f"/uploads/{image}" for image in product_images],
                page_image=(
                    f"{settings.site_url}/uploads/{product_images[0]}"
                    if product_images
                    else None
                ),
                og_type="product",
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
                structured_data=[
                    {
                        "@context": "https://schema.org",
                        "@type": "BreadcrumbList",
                        "itemListElement": [
                            {"@type": "ListItem", "position": 1, "name": "Home", "item": settings.site_url},
                            {
                                "@type": "ListItem",
                                "position": 2,
                                "name": "Catalog",
                                "item": f"{settings.site_url}/catalog",
                            },
                            {"@type": "ListItem", "position": 3, "name": product.name, "item": str(request.url)},
                        ],
                    },
                    {
                        "@context": "https://schema.org",
                        "@type": "Product",
                        "name": product.name,
                        "description": product.description or product.name,
                        "category": product.category,
                        "image": [
                            f"{settings.site_url}/uploads/{image}"
                            for image in product_images
                        ],
                        "brand": {
                            "@type": "Brand",
                            "name": "NAWA Global General Trading",
                        },
                        "url": str(request.url),
                    },
                ],
            ),
        },
    )


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt() -> PlainTextResponse:
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            f"Disallow: {settings.admin_route}",
            f"Sitemap: {settings.site_url}/sitemap.xml",
        ]
    )
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8")


@router.get("/sitemap.xml")
async def sitemap(
    request: Request,
    product_service: ProductService = Depends(get_product_service),
) -> Response:
    del request
    static_urls = [
        settings.site_url,
        f"{settings.site_url}/about",
        f"{settings.site_url}/services",
        f"{settings.site_url}/catalog",
        f"{settings.site_url}/contact",
    ]
    product_urls = [
    f"{settings.site_url}/product/{product.id}"
    for product in await run_in_threadpool(product_service.list_products)
    ]
    entries = "\n".join(
        f"<url><loc>{escape(url)}</loc></url>"
        for url in [*static_urls, *product_urls]
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{entries}"
        "</urlset>"
    )
    return Response(content=xml, media_type="application/xml")
