from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.exceptions import ValidationError


class ImageService:
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}

    def __init__(
        self,
        upload_dir: Path,
        max_upload_size_bytes: int,
        image_max_dimension: int,
    ) -> None:
        self.upload_dir = upload_dir
        self.max_upload_size_bytes = max_upload_size_bytes
        self.image_max_dimension = image_max_dimension
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_image(self, image: UploadFile, product_id: str, suffix: str = "") -> str:
        extension = Path(image.filename or "").suffix.lower()
        if extension not in self.allowed_extensions:
            raise ValidationError("Only JPG, JPEG, PNG, and WEBP images are supported.")

        payload = await image.read()
        if not payload:
            raise ValidationError("Uploaded image is empty.")
        if len(payload) > self.max_upload_size_bytes:
            raise ValidationError("Uploaded image exceeds the size limit.")

        try:
            processed = Image.open(BytesIO(payload))
            processed.verify()
            processed = Image.open(BytesIO(payload)).convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise ValidationError("One of the uploaded files is not a valid image.") from exc

        processed.thumbnail((self.image_max_dimension, self.image_max_dimension))
        filename = f"{product_id}{suffix}.jpg"
        processed.save(
            self.upload_dir / filename,
            format="JPEG",
            quality=82,
            optimize=True,
            progressive=True,
        )
        return filename

    def delete_image(self, filename: str) -> None:
        safe_name = Path(filename).name
        path = self.upload_dir / safe_name
        if path.exists() and path.is_file():
            path.unlink()
