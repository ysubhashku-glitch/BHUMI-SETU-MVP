"""
Kaithi Historical Document Image Preprocessing Module
Designed specifically for historical Bihar Cadastral Survey (CS) Khatiyans,
revenue registers, and zamindari deeds on aged parchment or handmade paper.

Operations:
1. Input format validation & boundary security.
2. Grayscale conversion.
3. Contrast normalization & dynamic range expansion (mitigates yellowed/faded ink).
4. Noise reduction via median filtering (removes paper foxing & dust spots).
5. Deskewing via projection-profile variance optimization.
6. Adaptive Otsu binarization preserving delicate pen strokes.
"""

import io
import time
import math
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageOps, ImageFilter, ImageEnhance

class PreprocessingError(Exception):
    """Raised when document image validation or transformation fails."""
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class PreprocessedImageResult:
    def __init__(
        self,
        image: Image.Image,
        image_bytes: bytes,
        width: int,
        height: int,
        skew_angle: float,
        transformations: List[str],
        duration_sec: float,
        histogram_summary: Dict[str, Any]
    ):
        self.image = image
        self.image_bytes = image_bytes
        self.width = width
        self.height = height
        self.skew_angle = round(skew_angle, 2)
        self.transformations = transformations
        self.duration_sec = round(duration_sec, 3)
        self.histogram_summary = histogram_summary

    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "skew_angle_deg": self.skew_angle,
            "transformations": self.transformations,
            "processing_duration_sec": self.duration_sec,
            "histogram": self.histogram_summary
        }


class KaithiImagePreprocessor:
    """
    Modular, reproducible image preprocessor for historical handwritten manuscripts.
    Ensures faint ink is protected while paper discoloration is suppressed.
    """
    MAX_IMAGE_DIMENSION = 8000
    MIN_IMAGE_DIMENSION = 32
    MAX_FILE_SIZE_BYTES = 40 * 1024 * 1024  # 40MB

    @classmethod
    def validate_and_load(cls, content: bytes) -> Image.Image:
        """Validates payload security, size limits, and decodes image."""
        if not content:
            raise PreprocessingError("EMPTY_PAYLOAD", "Document image payload is empty.")

        if len(content) > cls.MAX_FILE_SIZE_BYTES:
            raise PreprocessingError(
                "FILE_TOO_LARGE",
                f"Image file size ({len(content)} bytes) exceeds 40MB limit."
            )

        if len(content) < 16:
            raise PreprocessingError("CORRUPT_PAYLOAD", "Image payload too small to be a valid file.")

        try:
            img = Image.open(io.BytesIO(content))
            img.load()  # Force decode to detect truncation
        except Exception as e:
            raise PreprocessingError(
                "DECODE_FAILURE",
                f"Failed to decode image stream: {str(e)}"
            )

        w, h = img.size
        if w < cls.MIN_IMAGE_DIMENSION or h < cls.MIN_IMAGE_DIMENSION:
            raise PreprocessingError(
                "DIMENSION_TOO_SMALL",
                f"Image dimensions ({w}x{h}) are below minimum {cls.MIN_IMAGE_DIMENSION}px."
            )

        if w > cls.MAX_IMAGE_DIMENSION or h > cls.MAX_IMAGE_DIMENSION:
            raise PreprocessingError(
                "DIMENSION_TOO_LARGE",
                f"Image dimensions ({w}x{h}) exceed maximum {cls.MAX_IMAGE_DIMENSION}px."
            )

        return img

    @classmethod
    def compute_otsu_threshold(cls, gray_image: Image.Image) -> int:
        """
        Computes Otsu's optimal global binarization threshold
        maximizing inter-class variance between ink and paper background.
        """
        histogram = gray_image.histogram()
        total_pixels = sum(histogram)
        if total_pixels == 0:
            return 128

        sum_all = sum(i * count for i, count in enumerate(histogram))
        sum_background = 0.0
        weight_background = 0
        max_variance = 0.0
        best_threshold = 128

        for t in range(256):
            weight_background += histogram[t]
            if weight_background == 0:
                continue

            weight_foreground = total_pixels - weight_background
            if weight_foreground == 0:
                break

            sum_background += t * histogram[t]
            mean_b = sum_background / weight_background
            mean_f = (sum_all - sum_background) / weight_foreground

            # Inter-class variance: w_b * w_f * (mean_b - mean_f)^2
            var_between = float(weight_background) * float(weight_foreground) * ((mean_b - mean_f) ** 2)

            if var_between > max_variance:
                max_variance = var_between
                best_threshold = t

        return best_threshold

    @classmethod
    def estimate_skew_angle(cls, binary_image: Image.Image, max_angle: float = 15.0, step: float = 1.0) -> float:
        """
        Estimates skew angle using horizontal projection profile variance.
        Horizontal text lines yield maximum row-variance when properly aligned.
        """
        # Downscale for fast orientation check
        w, h = binary_image.size
        scale = min(1.0, 600.0 / max(w, h))
        if scale < 1.0:
            small_img = binary_image.resize((int(w * scale), int(h * scale)), Image.Resampling.NEAREST)
        else:
            small_img = binary_image

        sw, sh = small_img.size
        pixels = small_img.load()

        best_angle = 0.0
        max_variance = -1.0

        angle = -max_angle
        while angle <= max_angle:
            rotated = small_img.rotate(angle, resample=Image.Resampling.NEAREST, expand=False, fillcolor=255)
            rot_pixels = rotated.load()

            # Compute horizontal projection profile (sum of dark ink pixels per row)
            row_sums = [0] * sh
            for y in range(sh):
                # Count black pixels (value == 0)
                row_sums[y] = sum(1 for x in range(sw) if rot_pixels[x, y] == 0)

            # Variance of row sums
            mean_sum = sum(row_sums) / sh
            variance = sum((r - mean_sum) ** 2 for r in row_sums) / sh

            if variance > max_variance:
                max_variance = variance
                best_angle = angle

            angle += step

        return best_angle

    @classmethod
    def process(
        cls,
        content: bytes,
        apply_contrast: bool = True,
        apply_noise_reduction: bool = True,
        apply_deskew: bool = True,
        apply_binarization: bool = True
    ) -> PreprocessedImageResult:
        """
        Executes full preprocessing pipeline and returns normalized output.
        """
        start_time = time.time()
        img = cls.validate_and_load(content)
        transformations: List[str] = ["INPUT_VALIDATION"]

        # Step 1: Grayscale conversion
        if img.mode != "L":
            gray = ImageOps.grayscale(img)
            transformations.append("GRAYSCALE_CONVERSION")
        else:
            gray = img.copy()

        # Step 2: Contrast normalization & Autocontrast
        if apply_contrast:
            # Autocontrast cuts top/bottom 1% tails to remove background haze
            gray = ImageOps.autocontrast(gray, cutoff=1)
            enhancer = ImageEnhance.Contrast(gray)
            gray = enhancer.enhance(1.4)
            transformations.append("CONTRAST_NORMALIZATION_CLAHE_APPROX")

        # Step 3: Noise Reduction (Median filter)
        if apply_noise_reduction:
            # 3x3 median filter suppresses isolated dirt specs without blurring edges
            gray = gray.filter(ImageFilter.MedianFilter(size=3))
            transformations.append("MEDIAN_NOISE_FILTER_3X3")

        # Step 4: Binarization (Otsu threshold)
        threshold = 128
        if apply_binarization:
            threshold = cls.compute_otsu_threshold(gray)
            # Threshold to pure black (0) and white (255)
            # Historical parchment: paper is light (255), ink is dark (0)
            bin_img = gray.point(lambda p: 0 if p < threshold else 255, mode="1").convert("L")
            transformations.append(f"OTSU_BINARIZATION(threshold={threshold})")
        else:
            bin_img = gray

        # Step 5: Deskewing
        skew_angle = 0.0
        if apply_deskew:
            skew_angle = cls.estimate_skew_angle(bin_img)
            if abs(skew_angle) > 0.5:
                bin_img = bin_img.rotate(skew_angle, resample=Image.Resampling.BILINEAR, expand=False, fillcolor=255)
                transformations.append(f"DESKEW_CORRECTION({round(skew_angle, 2)}deg)")

        # Export binary PNG
        out_buf = io.BytesIO()
        bin_img.save(out_buf, format="PNG", optimize=True)
        out_bytes = out_buf.getvalue()

        hist = bin_img.histogram()
        total = sum(hist)
        dark_pixels = sum(hist[:128]) if len(hist) >= 128 else (hist[0] if len(hist) > 0 else 0)
        ink_ratio = round(dark_pixels / max(total, 1), 4)

        return PreprocessedImageResult(
            image=bin_img,
            image_bytes=out_bytes,
            width=bin_img.width,
            height=bin_img.height,
            skew_angle=skew_angle,
            transformations=transformations,
            duration_sec=time.time() - start_time,
            histogram_summary={
                "total_pixels": total,
                "dark_pixel_ratio": ink_ratio,
                "otsu_threshold": threshold
            }
        )
