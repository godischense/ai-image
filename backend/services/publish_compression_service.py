import os
import tempfile
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageOps


TARGET_PUBLISH_BYTES = 1024 * 1024
MIN_JPEG_QUALITY = 40
MAX_JPEG_QUALITY = 95
MIN_IMAGE_SIDE = 64


@dataclass
class PublishCompressionResult:
    output_path: str
    output_size: int
    width: int
    height: int
    quality: int


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        background.alpha_composite(rgba)
        return background.convert("RGB")
    if image.mode != "RGB":
        return image.convert("RGB")
    return image.copy()


def _save_jpeg(image: Image.Image, path: str, quality: int) -> int:
    image.save(
        path,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
        subsampling="4:2:0",
    )
    return os.path.getsize(path)


def _best_quality_under_target(image: Image.Image, temp_path: str, target_bytes: int) -> Optional[tuple[int, int]]:
    best: Optional[tuple[int, int]] = None
    low = MIN_JPEG_QUALITY
    high = MAX_JPEG_QUALITY
    while low <= high:
        quality = (low + high) // 2
        size = _save_jpeg(image, temp_path, quality)
        if size <= target_bytes:
            best = (quality, size)
            low = quality + 1
        else:
            high = quality - 1
    if best:
        _save_jpeg(image, temp_path, best[0])
    return best


def compress_image_to_publish_jpeg(source_path: str, output_path: str, target_bytes: int = TARGET_PUBLISH_BYTES) -> PublishCompressionResult:
    if not os.path.exists(source_path):
        raise FileNotFoundError("Source image does not exist")

    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(prefix=".publish_", suffix=".jpg", dir=output_dir)
    os.close(fd)

    try:
        with Image.open(source_path) as source_image:
            working_image = _flatten_to_rgb(source_image)

        while True:
            best = _best_quality_under_target(working_image, temp_path, target_bytes)
            if best:
                quality, size = best
                break

            width, height = working_image.size
            if min(width, height) <= MIN_IMAGE_SIDE:
                quality = MIN_JPEG_QUALITY
                size = _save_jpeg(working_image, temp_path, quality)
                if size > target_bytes:
                    raise RuntimeError("Unable to compress image under 1MB")
                break

            scale = max(0.75, (target_bytes / max(os.path.getsize(temp_path), 1)) ** 0.5 * 0.92)
            new_width = max(MIN_IMAGE_SIDE, int(width * scale))
            new_height = max(MIN_IMAGE_SIDE, int(height * scale))
            if new_width >= width and new_height >= height:
                new_width = max(MIN_IMAGE_SIDE, int(width * 0.9))
                new_height = max(MIN_IMAGE_SIDE, int(height * 0.9))
            working_image = working_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        os.replace(temp_path, output_path)
        final_width, final_height = working_image.size
        return PublishCompressionResult(
            output_path=output_path,
            output_size=size,
            width=final_width,
            height=final_height,
            quality=quality,
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
