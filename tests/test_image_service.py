"""Image upload limits, safe processing, and cleanup regression checks."""

from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from starlette.datastructures import UploadFile

from app.core.exceptions import ValidationError
from app.services.image_service import ImageService


@pytest.fixture
def service(tmp_path):
    return ImageService(tmp_path / "uploads", 100_000, 100)


def upload(
    mode="RGB",
    color="red",
    size=(200, 100),
    format="PNG",
    filename="photo.png",
    exif=None,
):
    buffer = BytesIO()
    with Image.new(mode, size, color) as image:
        image.save(buffer, format, **({"exif": exif} if exif else {}))
    buffer.seek(0)
    return UploadFile(buffer, filename=filename)


@pytest.mark.asyncio
async def test_bounded_upload_read(service):
    image = AsyncMock(filename="large.jpg")
    image.read.return_value = b"x" * (service.max_upload_size_bytes + 1)
    with pytest.raises(ValidationError, match="size limit"):
        await service.save_image(image, "product")
    image.read.assert_awaited_once_with(service.max_upload_size_bytes + 1)
    assert list(service.upload_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_transparency_and_resize(service):
    name = await service.save_image(upload("RGBA", (0, 0, 0, 0)), "product")
    with Image.open(service.upload_dir / name) as saved:
        assert saved.format == "JPEG"
        assert saved.size == (100, 50)
        assert saved.getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.asyncio
async def test_exif_orientation(service):
    exif = Image.Exif()
    exif[274] = 6
    name = await service.save_image(
        upload(format="JPEG", filename="photo.jpg", exif=exif), "product"
    )
    with Image.open(service.upload_dir / name) as saved:
        assert saved.size == (50, 100)
        assert not saved.getexif()


@pytest.mark.asyncio
async def test_pixel_limit_and_disguised_format(service, monkeypatch):
    monkeypatch.setattr(service, "max_input_pixels", 100)
    with pytest.raises(ValidationError, match="megapixel"):
        await service.save_image(upload(), "product")
    with pytest.raises(ValidationError, match="supported"):
        await service.save_image(upload(format="GIF", filename="fake.png"), "product")
    assert list(service.upload_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_partial_save_is_removed(service, monkeypatch):
    source = upload()

    def broken_save(image, path, **kwargs):
        path.write_bytes(b"partial")
        raise OSError("disk failure")

    monkeypatch.setattr(Image.Image, "save", broken_save)
    with pytest.raises(ValidationError):
        await service.save_image(source, "product")
    assert list(service.upload_dir.iterdir()) == []


def test_delete_rejects_path_traversal(service):
    target = service.upload_dir / "keep.jpg"
    target.write_bytes(b"keep")
    service.delete_image("../keep.jpg")
    assert target.exists()
    service.delete_image("keep.jpg")
    service.delete_image("keep.jpg")
    assert not target.exists()


@pytest.mark.asyncio
async def test_png_checksum_failure_is_validation_error(service):
    import base64

    malformed = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
    with pytest.raises(ValidationError, match="could not be processed"):
        await service.save_image(
            UploadFile(BytesIO(malformed), filename="broken.png"), "product"
        )
    assert list(service.upload_dir.iterdir()) == []
