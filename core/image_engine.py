import os
import shutil
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from PIL import Image, ImageOps
import pillow_heif
from core.metadata_engine import MetadataEngine
from utils.logger import get_logger

logger = get_logger()

# Register HEIF opener so PIL recognizes .heic / .heif seamlessly
pillow_heif.register_heif_opener()

@dataclass
class ImageProcessResult:
    status: str  # 'SUCCESS', 'SKIPPED_LARGER', 'FAILED'
    original_size: int
    compressed_size: int
    duration_sec: float
    error_message: str = ""

class ImageEngine:
    """High-performance image compression engine supporting HEIC, JPG, PNG, and TIFF."""

    def __init__(
        self,
        metadata_engine: MetadataEngine,
        heic_quality: int = 72,
        jpeg_quality: int = 78,
        max_dimension: int = 0,
        keep_if_larger: bool = True,
        convert_png_to_jpg: bool = True,
        convert_nonstandard_to_jpg: bool = True
    ):
        self.metadata_engine = metadata_engine
        self.heic_quality = heic_quality
        self.jpeg_quality = jpeg_quality
        self.max_dimension = max_dimension
        self.keep_if_larger = keep_if_larger
        self.convert_png_to_jpg = convert_png_to_jpg
        self.convert_nonstandard_to_jpg = convert_nonstandard_to_jpg

    def verify_image(self, file_path: str) -> bool:
        """Verifies that the image can be opened and decoded without corruption."""
        try:
            if not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
                return False
            with Image.open(file_path) as img:
                img.verify()
            return True
        except Exception:
            return False

    def process_image(
        self,
        source_path: str,
        dest_path: str
    ) -> ImageProcessResult:
        """
        Compresses an image, preserves orientation, injects metadata, and validates output.
        Automatically normalizes PNG and WebP to standard JPEG to prevent iOS import issues.
        """
        start_time = time.time()
        if not os.path.isfile(source_path) or os.path.getsize(source_path) == 0:
            return ImageProcessResult(
                status="FAILED",
                original_size=0,
                compressed_size=0,
                duration_sec=0,
                error_message="File does not exist or is 0 bytes (corrupted)"
            )

        orig_size = os.path.getsize(source_path)
        ext = os.path.splitext(source_path)[1].lower()

        # Check if output should be standardized to .jpg
        standardize_to_jpg = (
            (ext == ".png" and self.convert_png_to_jpg) or
            (ext in (".webp", ".psd", ".bmp", ".tif", ".tiff") and self.convert_nonstandard_to_jpg)
        )
        if standardize_to_jpg:
            dest_path = os.path.splitext(dest_path)[0] + ".jpg"
            out_ext = ".jpg"
        else:
            out_ext = ext

        dest_dir = os.path.dirname(os.path.abspath(dest_path))
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)
        tmp_output = dest_path + ".tmp" + out_ext

        try:
            with Image.open(source_path) as img:
                # Transpose according to EXIF orientation so pixels aren't flipped
                try:
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass

                # Optional downscaling for massive 48MP photos if configured
                if self.max_dimension > 0:
                    w, h = img.size
                    if max(w, h) > self.max_dimension:
                        ratio = self.max_dimension / float(max(w, h))
                        new_size = (int(w * ratio), int(h * ratio))
                        img = img.resize(new_size, Image.Resampling.LANCZOS)

                # Compression and normalization by format
                if out_ext in (".heic", ".heif"):
                    img.save(
                        tmp_output,
                        format="HEIF",
                        quality=self.heic_quality,
                        chroma=420
                    )
                elif out_ext in (".jpg", ".jpeg") or standardize_to_jpg:
                    # Convert transparent PNG/WebP to RGB with clean white background
                    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                        bg = Image.new("RGB", img.size, (255, 255, 255))
                        alpha = img.convert("RGBA").split()[3]
                        bg.paste(img.convert("RGBA"), mask=alpha)
                        img = bg
                    elif img.mode != "RGB":
                        img = img.convert("RGB")

                    img.save(
                        tmp_output,
                        format="JPEG",
                        quality=self.jpeg_quality,
                        optimize=True,
                        progressive=True
                    )
                elif out_ext == ".png":
                    img.save(
                        tmp_output,
                        format="PNG",
                        optimize=True,
                        compress_level=9
                    )
                else:
                    img.save(tmp_output, optimize=True)

            # Validate integrity of generated file
            if not self.verify_image(tmp_output):
                logger.error(f"Integrity check failed for compressed image: {tmp_output}")
                if os.path.isfile(tmp_output):
                    os.remove(tmp_output)
                return ImageProcessResult(
                    status="FAILED",
                    original_size=orig_size,
                    compressed_size=0,
                    duration_sec=time.time() - start_time,
                    error_message="Image verification failed"
                )

            # Metadata copy
            self.metadata_engine.copy_metadata(source_path, tmp_output, is_video=False)

            compressed_size = os.path.getsize(tmp_output)

            # Check if compressed file is larger or equal to original
            if self.keep_if_larger and compressed_size >= orig_size:
                logger.info(f"Compressed image was larger than original ({compressed_size} >= {orig_size}). Retaining original.")
                if os.path.isfile(tmp_output):
                    os.remove(tmp_output)
                shutil.copy2(source_path, dest_path)
                return ImageProcessResult(
                    status="SKIPPED_LARGER",
                    original_size=orig_size,
                    compressed_size=orig_size,
                    duration_sec=time.time() - start_time
                )

            # Atomic move
            if os.path.isfile(dest_path):
                os.remove(dest_path)
            shutil.move(tmp_output, dest_path)

            return ImageProcessResult(
                status="SUCCESS",
                original_size=orig_size,
                compressed_size=compressed_size,
                duration_sec=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"Unexpected error processing image {source_path}: {e}")
            if os.path.isfile(tmp_output):
                try: os.remove(tmp_output)
                except Exception: pass
            return ImageProcessResult(
                status="FAILED",
                original_size=orig_size,
                compressed_size=0,
                duration_sec=time.time() - start_time,
                error_message=str(e)
            )
