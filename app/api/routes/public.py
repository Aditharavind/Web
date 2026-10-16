"""Public website routes and search-engine discovery endpoints."""
from __future__ import annotations

from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from app.core.config import get_settings
from app.core.exceptions import ProductNotFoundError
from app.core.templates import template_context, templates
from app.models.schemas import MAX_TEXT_LENGTH, Product
from app.services.dependencies import get_product_service, get_visit_service
from app.services.product_service import ProductService
from app.services.visit_service import VisitService
from app.utils.pagination import build_pagination
from app.utils.text import build_query_string, mailto_url, whatsapp_message_url

router = APIRouter()
settings = get_settings()


def _canonical_url(path: str, **params: str | int | None) -> str:
    url = f"{settings.site_url}{path}"
    query = build_query_string(params)
    return f"{url}?{query}" if query else url


def _render_page(request: Request, template: str, **context: object) -> Response:
    return templates.TemplateResponse(
        request, template, template_context(request, **context)
    )


def _track_visit(request: Request, visit_service: VisitService) -> None:
    client = request.client.host if request.client else "unknown"
    visit_service.log_visit(client)


def _build_product_cards(
    products: list[Product], product_service: ProductService
) -> list[dict[str, object]]:
    return [
        {
            "product": product,
            "images": product_service.get_product_images(product),
            "whatsapp_url": whatsapp_message_url(
                settings.contact_whatsapp,
                f"Hello! I'm interested in: *{product.name}*. Please send me details.",
            ),
            "email_url": mailto_url(
                settings.contact_email,
                subject=f"Product Inquiry: {product.name}",
                body=(
                    f"Hello,\n\nI would like more information about {product.name}.\n\n"
                    "Please share the product details, pricing, and availability.\n"
                ),
            ),
        }
        for product in products
    ]


# These routes use synchronous SQLAlchemy services and template rendering.
# Normal endpoints run that work in FastAPI's thread pool.
@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    product_service: ProductService = Depends(get_product_service),
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    _track_visit(request, visit_service)
    return _render_page(
        request,
        "home.html",
        page_title="NAWA Global | Oilfield & Industrial Supply | Abu Dhabi",
        page_description=(
            "NAWA Global General Trading supplies oilfield equipment, industrial "
            "consumables, lubricants, PPE, and custom sourcing support in Abu Dhabi and across the UAE."
        ),
        canonical_url=_canonical_url("/"),
        active_nav="home",
        recent_product_cards=_build_product_cards(
            product_service.recent_products(6), product_service
        ),
    )


@router.get("/about", response_class=HTMLResponse)
def about(
    request: Request,
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    _track_visit(request, visit_service)
    return _render_page(
        request,
        "about.html",
        page_title="About Us — NAWA Global General Trading",
        page_description=(
            "Learn about NAWA Global General Trading, our industrial sourcing capabilities, "
            "mission, vision, values and approach to oilfield and industrial procurement."
        ),
        canonical_url=_canonical_url("/about"),
        active_nav="about",
    )


@router.get("/services", response_class=HTMLResponse)
def services_page(
    request: Request,
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    _track_visit(request, visit_service)
    return _render_page(
        request,
        "services.html",
        page_title="Products & Sourcing | NAWA Global",
        page_description=(
            "Explore NAWA Global's oilfield spare parts, industrial supplies, lubricants, "
            "safety PPE, and custom procurement services."
        ),
        canonical_url=_canonical_url("/services"),
        active_nav="services",
    )


@router.get("/contact", response_class=HTMLResponse)
def contact(
    request: Request,
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    _track_visit(request, visit_service)
    return _render_page(
        request,
        "contact.html",
        page_title="Contact Us — NAWA Global General Trading",
        page_description=(
            "Contact NAWA Global for industrial supply inquiries, quotes, and WhatsApp support."
        ),
        canonical_url=_canonical_url("/contact"),
        active_nav="contact",
        schema_type="ContactPage",
    )


@router.get("/catalog", response_class=HTMLResponse)
def catalog(
    request: Request,
    page: int = 1,
    q: str = Query(default="", max_length=MAX_TEXT_LENGTH),
    cat: str = Query(default="", max_length=MAX_TEXT_LENGTH),
    product_service: ProductService = Depends(get_product_service),
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    _track_visit(request, visit_service)
    result = product_service.search_catalog(page=page, query=q, category=cat)
    start = (result.page - 1) * settings.products_per_page
    return _render_page(
        request,
        "catalog.html",
        page_title="Product Catalogue | NAWA Global",
        page_description=(
            "Browse NAWA Global's catalog of oilfield equipment, industrial products, "
            "lubricants, and PPE."
        ),
        canonical_url=_canonical_url(
            "/catalog",
            q=result.query or None,
            cat=result.category or None,
            page=result.page if result.page > 1 else None,
        ),
        active_nav="catalog",
        catalog=result,
        categories=product_service.get_categories(),
        pagination=build_pagination(result.page, result.total_pages),
        result_start=start + 1 if result.total else 0,
        result_end=min(start + settings.products_per_page, result.total),
        product_cards=_build_product_cards(result.items, product_service),
        schema_type="CollectionPage",
    )


@router.get("/product/{product_id}", response_class=HTMLResponse)
def product_detail(
    product_id: str,
    request: Request,
    product_service: ProductService = Depends(get_product_service),
) -> Response:
    try:
        product = product_service.get_product(product_id)
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        ) from exc

    product_images = product_service.get_product_images(product)
    canonical = _canonical_url(f"/product/{product.id}")
    image_urls = [f"{settings.site_url}/uploads/{image}" for image in product_images]
    return _render_page(
        request,
        "product_detail.html",
        page_title=f"{product.name} — NAWA Global",
        page_description=(
            product.description[:150]
            if product.description
            else f"View specifications and inquiry options for {product.name} from NAWA Global."
        ),
        canonical_url=canonical,
        active_nav="catalog",
        product=product,
        product_images=product_images,
        product_image_urls=[f"/uploads/{image}" for image in product_images],
        page_image=image_urls[0] if image_urls else None,
        og_type="product",
        whatsapp_url=whatsapp_message_url(
            settings.contact_whatsapp,
            f"Hello! I'm interested in: *{product.name}*. Please send details and a quote.",
        ),
        email_url=mailto_url(
            settings.contact_email,
            subject=f"Product Inquiry: {product.name}",
            body=(
                f"Hello,\n\nI'm interested in {product.name}.\n\n"
                "Please send the product details, quotation, and lead time.\n"
            ),
        ),
        structured_data=[
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": _canonical_url("/")},
                    {"@type": "ListItem", "position": 2, "name": "Catalog", "item": _canonical_url("/catalog")},
                    {"@type": "ListItem", "position": 3, "name": product.name, "item": canonical},
                ],
            },
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": product.name,
                "description": product.description or product.name,
                "category": product.category,
                "image": image_urls,
                "url": canonical,
            },
        ],
    )


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt() -> PlainTextResponse:
    return PlainTextResponse(
        "\n".join([
            "User-agent: *",
            "Allow: /",
            f"Disallow: {settings.admin_route}",
            f"Sitemap: {_canonical_url('/sitemap.xml')}",
        ]),
        media_type="text/plain; charset=utf-8",
    )


@router.get("/sitemap.xml")
def sitemap(
    product_service: ProductService = Depends(get_product_service),
) -> Response:
    urls = [
        _canonical_url(path)
        for path in ("/", "/about", "/services", "/catalog", "/contact")
    ]
    urls.extend(
        _canonical_url(f"/product/{product_id}")
        for product_id in product_service.list_product_ids()
    )
    entries = "\n".join(f"<url><loc>{escape(url)}</loc></url>" for url in urls)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{entries}</urlset>"
    )
    return Response(content=xml, media_type="application/xml")
