"""Search visibility: structured data, titles, sitemap, caching and image delivery."""

import io
import json
import re
from dataclasses import replace
from datetime import datetime
from xml.etree import ElementTree

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.api.routes import public
from app.core import seo
from app.core.config import get_settings
from app.core.templates import STATIC_ASSET_VERSION
from app.main import app
from app.models.schemas import Product, ProductCreate
from app.services.dependencies import get_product_service
from tests.test_admin_routes import login

SITE = "https://nawaglobalgtd.com"


class Upload:
    def __init__(self, content, filename="photo.jpg"):
        self.filename = filename
        self.content = content

    async def read(self, size=-1):
        return self.content if size < 0 else self.content[:size]


def photo(size=(1200, 900), color="steelblue"):
    buffer = io.BytesIO()
    Image.effect_noise(size, 40).convert("RGB").save(buffer, "JPEG", quality=90)
    return Upload(buffer.getvalue())


def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


def json_ld(html):
    blocks = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
    return [json.loads(block) for block in blocks]


def make_product(**overrides):
    data = dict(
        id="abc", name="Name", category="Tools", description="", specs=[], tags="",
        featured=False, image=None, images=[], created=datetime(2026, 1, 1),
    )
    data.update(overrides)
    return Product(**data)


@pytest.fixture
def live_site(monkeypatch):
    monkeypatch.setattr(public, "settings", replace(public.settings, site_url=SITE))


# --- Structured data -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_product_schema_never_invents_commercial_data(live_site):
    product = await get_product_service().create_product(
        ProductCreate(
            name="Gate valve 2 in",
            category="Valves",
            description="Carbon steel gate valve for water, oil and gas lines, supplied on request.",
            specs=["Size: 2 in", "Class: 150", "Suitable for outdoor use"],
            tags="gate valve, flow control",
        ),
        [photo()],
    )
    async with client() as http:
        page = await http.get(f"/product/{product.id}")
    blocks = json_ld(page.text)
    record = next(block for block in blocks if block.get("@type") == "Product")
    crumbs = next(block for block in blocks if block.get("@type") == "BreadcrumbList")

    for forbidden in ("offers", "aggregateRating", "review", "brand", "price", "sku", "gtin", "mpn"):
        assert forbidden not in record
    assert not re.search(r"price|availability|InStock|aggregateRating", json.dumps(record), re.I)
    assert record["name"] == "Gate valve 2 in"
    assert record["url"] == f"{SITE}/product/{product.id}"
    assert record["image"] and record["image"][0].startswith(f"{SITE}/uploads/")
    assert record["additionalProperty"] == [
        {"@type": "PropertyValue", "name": "Size", "value": "2 in"},
        {"@type": "PropertyValue", "name": "Class", "value": "150"},
    ]
    assert [item["name"] for item in crumbs["itemListElement"]] == ["Home", "Products", "Gate valve 2 in"]
    assert crumbs["itemListElement"][2]["item"] == record["url"]


@pytest.mark.asyncio
async def test_organization_schema_only_contains_verified_details():
    async with client() as http:
        home = await http.get("/")
    graph = json_ld(home.text)[0]["@graph"]
    organization = next(item for item in graph if item["@type"] == "Organization")
    settings = get_settings()
    assert organization["image"] == f"{settings.site_url}/static/nawa-logo.png"
    assert organization["contactPoint"]["email"] == settings.contact_email
    assert organization["contactPoint"]["telephone"] == settings.contact_whatsapp
    # The street and postal code are not known, so they must not be made up.
    assert set(organization["address"]) == {"@type", "addressLocality", "addressCountry"}
    assert "postalCode" not in json.dumps(organization) and "streetAddress" not in json.dumps(organization)


# --- Titles and descriptions -----------------------------------------------------------


def test_short_descriptions_are_completed_with_real_facts_only():
    product = make_product(
        name="Trident Marine Systems heavy duty degreaser",
        category="Lubricants & Chemicals",
        description="Trident Marine Systems heavy duty degreaser.",
    )
    text = seo.product_description(product)
    assert text == (
        "Trident Marine Systems heavy duty degreaser. Category: Lubricants & Chemicals. "
        "Request a quote from NAWA Global, Abu Dhabi."
    )
    assert seo.has_short_description(product)
    assert not re.search(r"best|leading|popular|cheap|price|in stock", text, re.I)


def test_long_descriptions_are_trimmed_at_a_word_boundary():
    product = make_product(description="Metal-free thread compound for drill collars and tool joints. " * 6)
    text = seo.product_description(product)
    assert len(text) <= 158 and text.endswith("…")
    assert not seo.has_short_description(product)
    assert not text[:-1].endswith(" ")


@pytest.mark.parametrize(
    "name,category",
    [("Gate valve", "Valves"), ("X" * 120, "Valves"), ("Molyslip® GRAPHSLIP TJC Metal-Free Double-Duty Drill Collar", "Lubricants"), ("Plain", "Tools")],
)
def test_product_titles_fit_and_name_the_company(name, category):
    title = seo.product_title(make_product(name=name, category=category))
    assert len(title) <= 66 and title.endswith("| NAWA Global")


@pytest.mark.asyncio
async def test_catalogue_titles_and_indexing_rules(live_site):
    service = get_product_service()
    for index in range(14):
        await service.create_product(ProductCreate(name=f"Valve {index:02}", category="Valves"), [])
    await service.create_product(ProductCreate(name="Boots", category="Safety Equipment"), [])

    def head(html):
        return (
            re.search(r"<title>(.*?)</title>", html).group(1),
            re.search(r'name="robots" content="([^"]+)"', html).group(1),
        )

    async with client() as http:
        everything = head((await http.get("/catalog")).text)
        valves = head((await http.get("/catalog", params={"cat": "Valves"})).text)
        second = head((await http.get("/catalog", params={"cat": "Valves", "page": 2})).text)
        equipment = head((await http.get("/catalog", params={"cat": "Safety Equipment"})).text)
        searched = head((await http.get("/catalog", params={"q": "valve"})).text)
        two = head((await http.get("/catalog", params=[("cat", "Valves"), ("cat", "Safety Equipment")])).text)
        empty = head((await http.get("/catalog", params={"cat": "Nothing here"})).text)

    assert everything == ("Oilfield &amp; Industrial Products in UAE | NAWA Global", "index,follow")
    assert valves == ("Valves Products in UAE | NAWA Global", "index,follow")
    assert second[0] == "Valves Products in UAE - Page 2 | NAWA Global" and second[1] == "index,follow"
    assert equipment[0] == "Safety Equipment in UAE | NAWA Global"
    assert searched[1] == two[1] == empty[1] == "noindex,follow"


@pytest.mark.asyncio
async def test_every_product_page_has_unique_title_description_and_canonical(live_site):
    service = get_product_service()
    ids = [
        (await service.create_product(ProductCreate(name=f"Item {index}", category="Tools"), [])).id
        for index in range(4)
    ]
    seen = set()
    async with client() as http:
        for product_id in ids:
            html = (await http.get(f"/product/{product_id}")).text
            title = re.search(r"<title>(.*?)</title>", html).group(1)
            description = re.search(r'name="description" content="([^"]+)"', html).group(1)
            canonical = re.search(r'rel="canonical" href="([^"]+)"', html).group(1)
            assert canonical == f"{SITE}/product/{product_id}"
            assert 'content="index,follow"' in html
            seen.add((title, description, canonical))
    assert len(seen) == 4


# --- Sitemap and robots ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_sitemap_lists_pages_categories_and_product_photos(live_site):
    service = get_product_service()
    first = await service.create_product(ProductCreate(name="Valve", category="Valves"), [photo(), photo()])
    await service.create_product(ProductCreate(name="Gloves", category="Safety & PPE"), [])
    await service.create_product(ProductCreate(name="Temporary", category="Gone"), [])
    async with client() as http:
        response = await http.get("/sitemap.xml")
    root = ElementTree.fromstring(response.text)
    urls = [node.text for node in root.findall("{*}url/{*}loc")]
    assert f"{SITE}/catalog?cat=Valves" in urls
    assert f"{SITE}/catalog?cat=Safety%20%26%20PPE" in urls
    assert f"{SITE}/product/{first.id}" in urls
    assert len(urls) == len(set(urls))
    photos = root.findall(f"{{*}}url[{{*}}loc='{SITE}/product/{first.id}']/{{*}}image/{{*}}loc")
    assert len(photos) == 2 and all(node.text.startswith(f"{SITE}/uploads/") for node in photos)


@pytest.mark.asyncio
async def test_sitemap_skips_categories_without_products(live_site):
    service = get_product_service()
    product = await service.create_product(ProductCreate(name="Only", category="Short lived"), [])
    import asyncio

    await asyncio.to_thread(service.delete_product, product.id)
    async with client() as http:
        urls = [n.text for n in ElementTree.fromstring((await http.get("/sitemap.xml")).text).findall("{*}url/{*}loc")]
    assert not any("Short" in url for url in urls)


@pytest.mark.asyncio
async def test_robots_blocks_api_only(live_site):
    async with client() as http:
        robots = (await http.get("/robots.txt")).text
    assert "Disallow: /api/" in robots and f"Sitemap: {SITE}/sitemap.xml" in robots
    assert "admin" not in robots.lower()


# --- Caching and preloads --------------------------------------------------------------


@pytest.mark.asyncio
async def test_static_cache_lifetimes_are_long_only_for_files_that_cannot_go_stale():
    year = "public, max-age=31536000, immutable"
    async with client() as http:
        versioned_css = await http.get("/static/css/site.css", params={"v": "123"})
        plain_css = await http.get("/static/css/site.css")
        font = await http.get("/static/fonts/inter-latin-400-normal.woff2")
        logo_plain = await http.get("/static/nawa-logo.png")
        logo_versioned = await http.get("/static/nawa-logo-208.webp", params={"v": "123"})
    assert versioned_css.headers["cache-control"] == year
    assert plain_css.headers["cache-control"] == "public, max-age=0, must-revalidate"
    assert font.headers["cache-control"] == year
    assert logo_plain.headers["cache-control"] == "public, max-age=86400"
    assert logo_versioned.headers["cache-control"] == year


@pytest.mark.asyncio
async def test_page_asset_urls_carry_the_build_version():
    async with client() as http:
        html = (await http.get("/")).text
    assert f"/static/css/site.css?v={STATIC_ASSET_VERSION}" in html
    assert f"/static/nawa-logo-208.webp?v={STATIC_ASSET_VERSION}" in html
    assert "/static/css/fonts.css" not in html  # public pages use a single stylesheet
    assert "manrope-latin-800-normal.woff2" in html and "inter-latin-400-normal.woff2" in html


@pytest.mark.asyncio
async def test_preload_header_names_the_stylesheet_each_page_really_uses():
    prefix = get_settings().admin_route
    async with client() as http:
        public_page = await http.get("/")
        admin_page = await http.get(f"{prefix}/login")
    assert public_page.headers["link"] == f"</static/css/site.css?v={STATIC_ASSET_VERSION}>; rel=preload; as=style"
    assert admin_page.headers["link"] == f"</static/css/app.css?v={STATIC_ASSET_VERSION}>; rel=preload; as=style"


# --- Responsive images -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_uploaded_photos_are_cached_for_a_year_and_cards_use_small_webp_copies():
    service = get_product_service()
    product = await service.create_product(
        ProductCreate(name="Photo item", category="Tools", featured=True), [photo(), photo()]
    )
    name = product.images[0]
    async with client() as http:
        upload = await http.get(f"/uploads/{name}")
        home = await http.get("/")
        detail = await http.get(f"/product/{product.id}")
    assert upload.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert f'src="/media/480/{name}"' in home.text and f"/media/320/{name} 320w" in home.text
    assert f'src="/uploads/{name}"' not in home.text
    assert f"/media/720/{name}" in detail.text and f"/media/160/{name}" in detail.text
    assert 'rel="preload" as="image"' in detail.text and 'fetchpriority="high"' in detail.text


@pytest.mark.asyncio
async def test_media_route_serves_smaller_webp_and_rejects_anything_else():
    service = get_product_service()
    product = await service.create_product(ProductCreate(name="Media", category="Tools"), [photo((1600, 1200))])
    name = product.images[0]
    upload_dir = service.image_service.upload_dir
    async with client() as http:
        small = await http.get(f"/media/320/{name}")
        large = await http.get(f"/media/960/{name}")
        head = await http.head(f"/media/320/{name}")
        original = await http.get(f"/uploads/{name}")
        rejected = [
            await http.get(f"/media/999/{name}"),
            await http.get(f"/media/abc/{name}"),
            await http.get("/media/320/missing.jpg"),
            await http.get(f"/media/320/{name[:-4]}.png"),
            await http.get("/media/320/..%2F..%2Fapp.db"),
            await http.get("/media/320/%2e%2e%2f%2e%2e%2fetc%2fpasswd.jpg"),
            await http.get("/media/320/.jpg"),
        ]
    assert small.status_code == 200 and small.headers["content-type"] == "image/webp"
    assert small.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert head.status_code == 200
    image = Image.open(io.BytesIO(small.content))
    assert image.format == "WEBP" and image.width == 320
    assert Image.open(io.BytesIO(large.content)).width == 960
    assert len(small.content) < len(large.content) < len(original.content)
    assert all(response.status_code == 404 for response in rejected)
    assert (upload_dir / "_w320" / f"{name[:-4]}.webp").is_file()

    service.image_service.delete_image(name)
    assert not list(upload_dir.glob("_w*/" + name[:-4] + ".webp"))


@pytest.mark.asyncio
async def test_small_images_are_never_enlarged():
    service = get_product_service()
    product = await service.create_product(ProductCreate(name="Tiny", category="Tools"), [photo((200, 150))])
    async with client() as http:
        response = await http.get(f"/media/960/{product.images[0]}")
    assert Image.open(io.BytesIO(response.content)).width == 200


# --- Admin content hint ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_flags_products_that_need_a_fuller_description():
    service = get_product_service()
    await service.create_product(ProductCreate(name="Thin", category="Tools", description="Short."), [])
    await service.create_product(
        ProductCreate(name="Rich", category="Tools", description="A complete description with enough real detail. " * 3), []
    )
    prefix = get_settings().admin_route
    async with client() as http:
        await login(http)
        page = await http.get(f"{prefix}/products")
    assert page.text.count("Add a fuller description") == 1
    assert "1 with a very short description" in page.text


@pytest.mark.asyncio
async def test_catalogue_loads_the_first_photo_eagerly_and_uses_a_valid_heading_order():
    service = get_product_service()
    for index in range(3):
        await service.create_product(ProductCreate(name=f"Card {index}", category="Tools", featured=True), [photo()])
    async with client() as http:
        catalogue = (await http.get("/catalog")).text
        home = (await http.get("/")).text
    first, *others = re.findall(r"<img src=\"/media/480/[^>]+>", catalogue, re.DOTALL)
    assert 'fetchpriority="high"' in first and 'loading="lazy"' not in first
    assert all('loading="lazy"' in image for image in others)
    assert "<h1>" in catalogue and "<h2 class=\"card-title\">" in catalogue and "<h3 class=\"card-title\">" not in catalogue
    # On the home page the cards sit under section headings, so they stay h3 and load lazily.
    assert "<h3 class=\"card-title\">" in home and "<h2 class=\"card-title\">" not in home
