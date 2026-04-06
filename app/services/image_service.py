from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable, Tuple

from fastapi import BackgroundTasks
from PIL import Image, UnidentifiedImageError

from app.core.exceptions import ValidationError

# ImageService responsibilities:
# - Validate image bytes
# - Provide a background-safe entrypoint to process and persist images
# - Delete images from storage


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

    def _validate_payload(self, filename: str | None, payload: bytes) -> None:
        extension = Path(filename or "").suffix.lower()
        if extension not in self.allowed_extensions:
            raise ValidationError("Only JPG, JPEG, PNG, and WEBP images are supported.")
        if not payload:
            raise ValidationError("Uploaded image is empty.")
        if len(payload) > self.max_upload_size_bytes:
            raise ValidationError("Uploaded image exceeds the size limit.")

    def _process_image_sync(self, payload: bytes) -> Image.Image:
        try:
            img = Image.open(BytesIO(payload))
            img.verify()
            img = Image.open(BytesIO(payload)).convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise ValidationError("One of the uploaded files is not a valid image.") from exc
        img.thumbnail((self.image_max_dimension, self.image_max_dimension))
        return img

    def process_and_store_images(self, product_id: str, images: Iterable[Tuple[str, bytes]], storage=None) -> list[str]:
        """
        Synchronous method intended to run in BackgroundTasks/threadpool.

        images: iterable of (original_filename, bytes)
        Returns list of stored filenames.
        """
        stored: list[str] = []
        index = 0

        for original_name, payload in images:
            # validate first
            self._validate_payload(original_name, payload)
            processed = self._process_image_sync(payload)
            suffix = "" if index == 0 else f"-{index + 1}"
            filename = f"{product_id}{suffix}.jpg"
            # write bytes to memory then persist via storage backend
            buf = BytesIO()
            processed.save(buf, format="JPEG", quality=82, optimize=True, progressive=True)
            buf.seek(0)
            data = buf.read()
            if storage is not None:
                storage.save(filename, data)
            else:
                # fallback to local upload_dir
                (self.upload_dir / filename).write_bytes(data)
            stored.append(filename)
            index += 1

        # Note: updating DB with image names is the responsibility of the caller/background job.
        return stored

    def delete_image(self, filename: str) -> None:
        safe_name = Path(filename).name
        path = self.upload_dir / safe_name
        if path.exists() and path.is_file():
            path.unlink()
