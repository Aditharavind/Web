"""Public website routes and search-engine discovery endpoints."""
from __future__ import annotations

from typing import Annotated
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from pydantic import StringConstraints
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from app.core import seo
from app.core.config import get_settings
from app.core.exceptions import ProductNotFoundError
from app.core.rate_limiter import allow_request
from app.core.templates import template_context, templates
from app.models.schemas import MAX_TEXT_LENGTH, Product
from app.services.dependencies import get_product_service, get_visit_service
from app.services.product_service import ProductService
from app.services.visit_service import VisitService
from app.utils.pagination import build_pagination
from app.utils.text import build_query_string, mailto_url, whatsapp_message_url

router = APIRouter()
settings = get_settings()


def _canonical_url(path: str, **params: str | int | list[str] | None) -> str:
    url = f"{settings.site_url}{path}"
    query = build_query_string(params)
    return f"{url}?{query}" if query else url


def _render_page(request: Request, template: str, **context: object) -> Response:
    return templates.TemplateResponse(
        request, template, template_context(request, **context),
        background=getattr(request.state, "visit_background", None),
    )


def _track_visit(request: Request, visit_service: VisitService) -> None:
    if request.method != "GET":
        return  # Monitors and link checkers using HEAD are not visitors.
    client = request.client.host if request.client else "unknown"
    request.state.visit_background = BackgroundTask(visit_service.log_visit, client)


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
@router.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def home(
    request: Request,
    product_service: ProductService = Depends(get_product_service),
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    _track_visit(request, visit_service)
    return _render_page(
        request,
        "home.html",
        page_title="NAWA Global | Oilfield & Industrial Supplies in Abu Dhabi, UAE",
        page_description=(
            "Oilfield equipment, valves, MRO supplies, lubricants and industrial safety "
            "products from NAWA Global, a general trading company in Mussafah, Abu Dhabi. "
            "Request a quote on WhatsApp or email."
        ),
        canonical_url=_canonical_url("/"),
        active_nav="home",
        homepage_product_cards=_build_product_cards(
            product_service.homepage_products(6), product_service
        ),
    )


@router.api_route("/about", methods=["GET", "HEAD"], response_class=HTMLResponse)
def about(
    request: Request,
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    _track_visit(request, visit_service)
    return _render_page(
        request,
        "about.html",
        page_title="About NAWA Global | General Trading, Abu Dhabi",
        page_description=(
            "NAWA Global is an Abu Dhabi general trading company supplying oilfield products, "
            "industrial essentials and sourcing support."
        ),
        canonical_url=_canonical_url("/about"),
        active_nav="about",
    )


@router.api_route("/services", methods=["GET", "HEAD"], include_in_schema=False)
def services_page() -> RedirectResponse:
    return RedirectResponse("/#supply", status_code=301)


@router.api_route("/contact", methods=["GET", "HEAD"], response_class=HTMLResponse)
def contact(
    request: Request,
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    _track_visit(request, visit_service)
    return _render_page(
        request,
        "contact.html",
        page_title="Contact NAWA Global | WhatsApp, Phone & Email",
        page_description=(
            "Contact NAWA Global in Abu Dhabi on WhatsApp, phone or email for product "
            "enquiries and quotes."
        ),
        canonical_url=_canonical_url("/contact"),
        active_nav="contact",
        schema_type="ContactPage",
    )


@router.api_route("/catalog", methods=["GET", "HEAD"], response_class=HTMLResponse)
def catalog(
    request: Request,
    cat: Annotated[
        list[Annotated[str, StringConstraints(max_length=MAX_TEXT_LENGTH)]],
        Query(default_factory=list, max_length=20),
    ],
    page: int = 1,
    q: str = Query(default="", max_length=MAX_TEXT_LENGTH),
    product_service: ProductService = Depends(get_product_service),
    visit_service: VisitService = Depends(get_visit_service),
) -> Response:
    _track_visit(request, visit_service)
    result = product_service.search_catalog(page=page, query=q, category=cat)
    start = (result.page - 1) * settings.products_per_page
    title, description, robots = seo.catalog_seo(
        result.categories, result.query, result.page, result.total
    )
    return _render_page(
        request,
        "catalog.html",
        page_title=title,
        page_description=description,
        meta_robots=robots,
        canonical_url=_canonical_url(
            "/catalog",
            q=result.query or None,
            cat=result.categories or None,
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


@router.get("/api/suggest", include_in_schema=False)
async def suggest(
    request: Request,
    q: str = Query(default="", max_length=80),
    product_service: ProductService = Depends(get_product_service),
) -> JSONResponse:
    client = request.client.host if request.client else "unknown"
    if not await allow_request(f"suggest:{client}", 90, 60):
        return JSONResponse({"items": []}, status_code=429, headers={"Cache-Control": "no-store"})
    items = await run_in_threadpool(product_service.suggest_products, q)
    return JSONResponse({"items": items}, headers={"Cache-Control": "no-store"})


@router.api_route("/product/{product_id}", methods=["GET", "HEAD"], response_class=HTMLResponse)
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
        page_title=seo.product_title(product),
        page_description=seo.product_description(product),
        page_keywords=", ".join(
            item
            for item in (product.name, product.category, product.tags, "NAWA Global")
            if item
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
        structured_data=seo.product_structured_data(
            product,
            canonical=canonical,
            image_urls=image_urls,
            home_url=_canonical_url("/"),
            catalog_url=_canonical_url("/catalog"),
        ),
    )


@router.api_route("/robots.txt", methods=["GET", "HEAD"], response_class=PlainTextResponse)
def robots_txt() -> PlainTextResponse:
    return PlainTextResponse(
        "\n".join([
            "User-agent: *",
            "Allow: /",
            "Disallow: /api/",
            f"Sitemap: {_canonical_url('/sitemap.xml')}",
        ]),
        media_type="text/plain; charset=utf-8",
    )


@router.api_route("/sitemap.xml", methods=["GET", "HEAD"])
def sitemap(
    product_service: ProductService = Depends(get_product_service),
) -> Response:
    """Pages, one listing page per category that has products, and every product with its photos."""
    products = product_service.sitemap_entries()
    categories = sorted({entry["category"] for entry in products if entry["category"]}, key=str.casefold)
    entries = [f"<url><loc>{escape(_canonical_url(path))}</loc></url>" for path in ("/", "/catalog", "/about", "/contact")]
    entries.extend(
        f"<url><loc>{escape(_canonical_url('/catalog', cat=[category]))}</loc></url>"
        for category in categories
    )
    for entry in products:
        photos = "".join(
            f"<image:image><image:loc>{escape(f'{settings.site_url}/uploads/{image}')}</image:loc></image:image>"
            for image in entry["images"][:10]
        )
        entries.append(
            f"<url><loc>{escape(_canonical_url('/product/' + entry['id']))}</loc>{photos}</url>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">'
        f'{"".join(entries)}</urlset>'
    )
    return Response(content=xml, media_type="application/xml")


@router.api_route("/media/{width}/{filename}", methods=["GET", "HEAD"], include_in_schema=False)
async def product_image(
    width: str,
    filename: str,
    product_service: ProductService = Depends(get_product_service),
) -> Response:
    """Smaller WebP copy of a product photo (320, 640 or 960 px wide), made on first request."""
    path = (
        await run_in_threadpool(product_service.image_service.derived_path, filename, int(width))
        if width.isdecimal()
        else None
    )
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")
    return FileResponse(
        path,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
