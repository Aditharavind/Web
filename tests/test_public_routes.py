"""Public-page regressions for canonical URLs, pagination and product metadata."""
import json
import re
from dataclasses import replace
from html import unescape
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routes import public
from app.main import app
from app.models.schemas import ProductCreate
from app.services.dependencies import get_product_service


@pytest.mark.asyncio
async def test_catalogue_pagination_and_configured_canonical_host(monkeypatch):
    monkeypatch.setattr(public, "settings", replace(public.settings, site_url="https://nawaglobalgtd.com"))
    service = get_product_service()
    for index in range(11):
        await service.create_product(ProductCreate(name=f"Valve {index:02}", category="MRO & Tools"), [])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/catalog", params={"q": "Valve", "cat": "MRO & Tools", "page": 2, "utm_source": "test"})
    assert response.status_code == 200
    canonical = unescape(re.search(r'rel="canonical" href="([^"]+)"', response.text).group(1))
    url = urlsplit(canonical)
    assert (url.scheme, url.netloc, url.path) == ("https", "nawaglobalgtd.com", "/catalog")
    assert parse_qs(url.query) == {"q": ["Valve"], "cat": ["MRO & Tools"], "page": ["2"]}
    assert "Showing 10–11 of 11" in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("parameter", ["q", "cat"])
async def test_catalogue_rejects_oversized_search_inputs(parameter):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/catalog", params={parameter: "x" * 256})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_product_metadata_and_sitemap_use_configured_urls(monkeypatch):
    monkeypatch.setattr(public, "settings", replace(public.settings, site_url="https://nawaglobalgtd.com"))
    product = await get_product_service().create_product(ProductCreate(name="Valve & coupling", category="Mechanical"), [])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        detail = await client.get(f"/product/{product.id}", params={"utm_source": "test"})
        sitemap = await client.get("/sitemap.xml")
        missing = await client.get("/product/not-a-product")
    scripts = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', detail.text, re.S)
    data = [json.loads(script) for script in scripts]
    record = next(item for item in data if item["@type"] == "Product")
    assert record["name"] == "Valve & coupling"
    assert "brand" not in record
    assert record["url"] == f"https://nawaglobalgtd.com/product/{product.id}"
    root = ElementTree.fromstring(sitemap.text)
    urls = [node.text for node in root.findall("{*}url/{*}loc")]
    assert len(urls) == 6
    assert record["url"] in urls
    assert all(url.startswith("https://nawaglobalgtd.com/") for url in urls)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_product_displays_plain_and_structured_specs_safely():
    service = get_product_service()
    product = await service.create_product(
        ProductCreate(name="Specification test", category="Tools", specs=["Material: Steel", "Suitable for outdoor use", "<script>alert(1)</script>"]), []
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        page = await client.get(f"/product/{product.id}")
    assert page.status_code == 200
    assert "Suitable for outdoor use" in page.text
    assert "Material" in page.text and "Steel" in page.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page.text
    assert "<script>alert(1)</script>" not in page.text
