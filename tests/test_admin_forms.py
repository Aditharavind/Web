"""Regression checks for the browser form structure and real admin endpoints."""
import io
from html.parser import HTMLParser

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.main import app
from app.core.config import get_settings
from app.services.dependencies import get_product_service


class FormStructure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.nested = False
        self.ids = set()
        self.delete_targets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.nested |= self.depth > 0
            self.depth += 1
            self.ids.add(attrs.get("id"))
        if tag == "button" and attrs.get("form"):
            self.delete_targets.append(attrs["form"])

    def handle_endtag(self, tag):
        if tag == "form":
            self.depth -= 1


def jpeg(color):
    data = io.BytesIO()
    Image.new("RGB", (80, 60), color).save(data, "JPEG")
    return data.getvalue()


@pytest.mark.asyncio
async def test_admin_add_edit_images_and_delete():
    prefix = get_settings().admin_route
    service = get_product_service()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        await client.get(f"{prefix}/login")
        token = client.cookies.get("csrf_token")
        login = await client.post(f"{prefix}/login", data={"csrf_token": token, "username": "admin", "password": "admin123"})
        assert login.status_code == 303
        added = await client.post(f"{prefix}/products/add", data={"csrf_token": token, "name": "Valve", "new_category": "Oilfield", "description": "Before edit"}, files=[("images", ("red.jpg", jpeg("red"), "image/jpeg"))])
        assert added.status_code == 303
        product = service.list_products()[0]
        original = product.images[0]
        original_bytes = (service.image_service.upload_dir / original).read_bytes()
        page = await client.get(f"{prefix}/products/edit/{product.id}")
        forms = FormStructure()
        forms.feed(page.text)
        assert not forms.nested
        assert "edit-product-form" in forms.ids
        assert len(forms.delete_targets) == 1
        assert all(target in forms.ids for target in forms.delete_targets)

        updated = await client.post(f"{prefix}/products/edit/{product.id}", data={"csrf_token": token, "name": "Updated valve", "new_category": "Mechanical", "description": "Revised description", "specs": "Size: 2 inch\nMaterial: Steel", "tags": "valve, steel", "featured": "true"}, files=[("images", ("blue.jpg", jpeg("blue"), "image/jpeg"))])
        assert updated.status_code == 303
        assert "error=" not in updated.headers["location"]
        fresh = service.get_product(product.id)
        assert fresh.name == "Updated valve"
        assert fresh.category == "Mechanical"
        assert fresh.description == "Revised description"
        assert fresh.specs == ["Size: 2 inch", "Material: Steel"]
        assert fresh.featured is True
        assert len(fresh.images) == 2
        assert (service.image_service.upload_dir / original).read_bytes() == original_bytes
        detail = await client.get(f"/product/{product.id}")
        assert "Revised description" in detail.text
        assert "Updated valve" in (await client.get("/catalog")).text
        assert "Updated valve" in (await client.get("/")).text

        # Saving text without a new file must preserve the gallery.
        again = await client.post(f"{prefix}/products/edit/{product.id}", data={"csrf_token": token, "name": "Final valve", "category": "Mechanical"})
        assert again.status_code == 303
        assert service.get_product(product.id).images == fresh.images
        removed = await client.post(f"{prefix}/products/delete-image/{product.id}/{original}", data={"csrf_token": token})
        assert removed.status_code == 303
        assert not (service.image_service.upload_dir / original).exists()
        assert len(service.get_product(product.id).images) == 1
        deleted = await client.post(f"{prefix}/products/delete/{product.id}", data={"csrf_token": token})
        assert deleted.status_code == 303
        assert service.list_products() == []
        assert (await client.get(f"/product/{product.id}")).status_code == 404
