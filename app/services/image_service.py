from __future__ import annotations

import os
import re
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
    # Widths for the smaller WebP copies served to browsers (see derived_path).
    derived_widths = (160, 320, 480, 720, 960)
    _stored_name = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,200}\.jpg$")

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
        for width in self.derived_widths:
            (self.upload_dir / f"_w{width}" / f"{Path(filename).stem}.webp").unlink(missing_ok=True)

    def derived_path(self, filename: str, width: int) -> Path | None:
        """Smaller WebP copy of a stored image, created on first request and then reused.

        Returns None for unknown widths, names that are not stored images, or missing files,
        so nothing outside the upload folder can ever be read or written.
        """
        if width not in self.derived_widths or not self._stored_name.fullmatch(filename or ""):
            return None
        source = self.upload_dir / filename
        if not source.is_file() or source.is_symlink():
            return None
        target = self.upload_dir / f"_w{width}" / f"{source.stem}.webp"
        if target.is_file():
            return target
        target.parent.mkdir(exist_ok=True)
        temporary = target.with_name(f"{target.stem}.{os.getpid()}.tmp")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(source) as image:
                    image.thumbnail((width, width))
                    image.convert("RGB").save(temporary, format="WEBP", quality=76, method=6)
            os.replace(temporary, target)
        except (OSError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            temporary.unlink(missing_ok=True)
            return None
        return target
