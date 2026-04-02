from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.exceptions import ValidationError


class ImageService:
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}

    def __init__(self, upload_dir: Path) -> None:
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_image(self, image: UploadFile, product_id: str, suffix: str = "") -> str:
        extension = Path(image.filename or "").suffix.lower()
        if extension not in self.allowed_extensions:
            raise ValidationError("Only JPG, JPEG, PNG, and WEBP images are supported.")

        payload = await image.read()
        try:
            processed = Image.open(BytesIO(payload)).convert("RGB")
        except UnidentifiedImageError as exc:
            raise ValidationError("One of the uploaded files is not a valid image.") from exc

        processed.thumbnail((800, 800))
        filename = f"{product_id}{suffix}.jpg"
        processed.save(self.upload_dir / filename, format="JPEG", quality=85)
        return filename

    def delete_image(self, filename: str) -> None:
        path = self.upload_dir / filename
        if path.exists():
            path.unlink()
