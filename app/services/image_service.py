from __future__ import annotations

import warnings
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import ValidationError


class ImageService:
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    max_input_pixels = 20_000_000

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

    async def save_image(
        self, image: UploadFile, product_id: str, suffix: str = ""
    ) -> str:
        extension = Path(image.filename or "").suffix.lower()
        if extension not in self.allowed_extensions:
            raise ValidationError("Only JPG, JPEG, PNG, and WEBP images are supported.")

        payload = await image.read(self.max_upload_size_bytes + 1)
        if not payload:
            raise ValidationError("Uploaded image is empty.")
        if len(payload) > self.max_upload_size_bytes:
            raise ValidationError("Uploaded image exceeds the size limit.")
        return await run_in_threadpool(self._process_image, payload, product_id, suffix)

    def _process_image(self, payload: bytes, product_id: str, suffix: str) -> str:
        filename = f"{product_id}{suffix}-{uuid4().hex}.jpg"
        if Path(filename).name != filename or "\\" in filename:
            raise ValidationError("Invalid image identifier.")
        destination = self.upload_dir / filename
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(payload)) as source:
                    if source.format not in {"JPEG", "PNG", "WEBP"}:
                        raise ValidationError(
                            "Only JPG, JPEG, PNG, and WEBP images are supported."
                        )
                    if source.width * source.height > self.max_input_pixels:
                        raise ValidationError(
                            "Uploaded image exceeds the 20 megapixel limit."
                        )
                    source.verify()
                with Image.open(BytesIO(payload)) as source:
                    processed = ImageOps.exif_transpose(source)
                    try:
                        processed.thumbnail(
                            (self.image_max_dimension, self.image_max_dimension)
                        )
                        if (
                            processed.mode in {"RGBA", "LA"}
                            or "transparency" in processed.info
                        ):
                            with processed.convert("RGBA") as rgba:
                                rgb = Image.new("RGB", rgba.size, "white")
                                rgb.paste(rgba, mask=rgba.getchannel("A"))
                        else:
                            rgb = processed.convert("RGB")
                        try:
                            rgb.save(
                                destination,
                                format="JPEG",
                                quality=82,
                                optimize=True,
                                progressive=True,
                            )
                        finally:
                            rgb.close()
                    finally:
                        processed.close()
        except (
            UnidentifiedImageError,
            SyntaxError,
            OSError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as exc:
            destination.unlink(missing_ok=True)
            raise ValidationError(
                "The image could not be processed. Use a valid JPG, PNG, or WEBP image within the upload limits."
            ) from exc
        return filename

    def delete_image(self, filename: str) -> None:
        if not filename or Path(filename).name != filename or "\\" in filename:
            return
        path = self.upload_dir / filename
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)
