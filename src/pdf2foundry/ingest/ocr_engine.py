"""OCR engine abstraction for PDF2Foundry.

This module provides an abstraction layer for OCR engines, with a Tesseract-based
implementation. OCR is used to extract text from scanned pages or images when
text coverage is insufficient.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Protocol

from PIL import Image  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)


class OcrResult:
    """Result from OCR processing containing extracted text and metadata."""

    def __init__(
        self,
        text: str,
        confidence: float = 0.0,
        language: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> None:
        """Initialize OCR result.

        Args:
            text: Extracted text content
            confidence: OCR confidence score (0.0-1.0)
            language: Detected or specified language code
            bbox: Bounding box as (x, y, width, height) if available
        """
        self.text = text
        self.confidence = confidence
        self.language = language
        self.bbox = bbox

    def to_html_span(self) -> str:
        """Convert OCR result to HTML span with metadata attributes."""
        attrs = ['data-ocr="true"']
        if self.confidence > 0:
            attrs.append(f'data-ocr-confidence="{self.confidence:.3f}"')
        if self.language:
            attrs.append(f'data-ocr-language="{self.language}"')
        if self.bbox:
            x, y, w, h = self.bbox
            attrs.append(f'data-bbox="{x},{y},{w},{h}"')

        attrs_str = " " + " ".join(attrs) if attrs else ""
        return f"<span{attrs_str}>{self._escape_html(self.text)}</span>"

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )


class OcrEngine(Protocol):
    """Protocol for OCR engines."""

    def run(
        self,
        image: Image.Image | Path | bytes,
        language: str | None = None,
    ) -> list[OcrResult]:
        """Run OCR on an image and return extracted text results.

        Args:
            image: PIL Image, file path, or image bytes
            language: Language hint for OCR (e.g., 'eng', 'fra')

        Returns:
            List of OCR results with text and metadata
        """
        ...

    def is_available(self) -> bool:
        """Check if the OCR engine is available and functional."""
        ...


class TesseractOcrEngine:
    """Tesseract-based OCR engine implementation."""

    def __init__(self) -> None:
        """Initialize Tesseract OCR engine."""
        self._pytesseract = None
        self._available: bool | None = None

    def _ensure_pytesseract(self) -> Any:
        """Lazy-load pytesseract module."""
        if self._pytesseract is None:
            try:
                import pytesseract  # type: ignore[import-not-found]

                self._pytesseract = pytesseract
                # Test if tesseract is actually available
                pytesseract.get_tesseract_version()
                self._available = True
            except (ImportError, Exception) as e:
                logger.warning(f"Tesseract OCR not available: {e}")
                self._available = False
                raise ImportError(f"pytesseract not available: {e}") from e
        return self._pytesseract

    def is_available(self) -> bool:
        """Check if Tesseract is available."""
        if self._available is None:
            from contextlib import suppress

            with suppress(ImportError):
                self._ensure_pytesseract()
        return self._available or False

    def run(
        self,
        image: Image.Image | Path | bytes,
        language: str | None = None,
    ) -> list[OcrResult]:
        """Run Tesseract OCR on an image.

        Args:
            image: PIL Image, file path, or image bytes
            language: Language code for OCR (e.g., 'eng', 'fra')

        Returns:
            List of OCR results with extracted text and confidence

        Raises:
            ImportError: If pytesseract is not available
            Exception: If OCR processing fails
        """
        pytesseract = self._ensure_pytesseract()

        # Convert input to PIL Image
        if isinstance(image, Path | str):
            pil_image = Image.open(image)
        elif isinstance(image, bytes):
            from io import BytesIO

            pil_image = Image.open(BytesIO(image))
        else:
            pil_image = image

        # Prepare OCR configuration
        config = "--psm 6"  # Assume uniform block of text
        if language:
            config += f" -l {language}"

        try:
            # Extract text with confidence data
            data = pytesseract.image_to_data(
                pil_image, config=config, output_type=pytesseract.Output.DICT
            )

            # Extract text
            text = pytesseract.image_to_string(pil_image, config=config).strip()

            # Calculate average confidence
            confidences = [int(conf) for conf in data.get("conf", []) if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0

            # Detect language if not specified
            detected_lang = language
            if not detected_lang:
                try:
                    lang_data = pytesseract.image_to_osd(
                        pil_image, output_type=pytesseract.Output.DICT
                    )
                    detected_lang = lang_data.get("script", "unknown")
                except Exception:
                    detected_lang = "unknown"

            if text:
                return [
                    OcrResult(
                        text=text,
                        confidence=avg_confidence,
                        language=detected_lang,
                    )
                ]
            else:
                return []

        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            raise


class OcrCache:
    """Simple cache for OCR results to avoid reprocessing."""

    def __init__(self) -> None:
        """Initialize OCR cache."""
        self._cache: dict[str, list[OcrResult]] = {}

    def _get_image_hash(self, image: Image.Image | Path | bytes) -> str:
        """Generate a hash key for an image."""
        if isinstance(image, Image.Image):
            # Convert PIL image to bytes for hashing
            from io import BytesIO

            buf = BytesIO()
            image.save(buf, format="PNG")
            image_bytes = buf.getvalue()
        elif isinstance(image, Path | str):
            image_bytes = Path(image).read_bytes()
        else:
            image_bytes = image

        return hashlib.sha256(image_bytes).hexdigest()[:16]

    def get(
        self, image: Image.Image | Path | bytes, language: str | None = None
    ) -> list[OcrResult] | None:
        """Get cached OCR result if available."""
        key = f"{self._get_image_hash(image)}:{language or 'auto'}"
        return self._cache.get(key)

    def set(
        self, image: Image.Image | Path | bytes, language: str | None, results: list[OcrResult]
    ) -> None:
        """Cache OCR results."""
        key = f"{self._get_image_hash(image)}:{language or 'auto'}"
        self._cache[key] = results

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()


def compute_text_coverage(html: str) -> float:
    """Compute text coverage ratio for a page's HTML content.

    This estimates how much text content is present relative to the page size.
    A low ratio (< 0.05) might indicate a scanned page that needs OCR.

    Args:
        html: HTML content from the page

    Returns:
        Text coverage ratio (0.0 to 1.0+)
    """
    import re

    # Remove HTML tags and get plain text
    text_only = re.sub(r"<[^>]+>", " ", html)

    # Count meaningful characters (letters, numbers, basic punctuation)
    meaningful_chars = len(re.findall(r"[a-zA-Z0-9\.,;:!?\-\s]", text_only))

    # Estimate coverage based on character count
    # This is a heuristic - adjust threshold as needed
    # Typical page might have 2000-5000 characters
    # Coverage = chars / estimated_page_capacity
    estimated_page_capacity = 3000
    coverage = meaningful_chars / estimated_page_capacity

    return min(coverage, 1.0)  # Cap at 1.0


def needs_ocr(html: str, ocr_mode: str, threshold: float = 0.05) -> bool:
    """Determine if a page needs OCR processing.

    Args:
        html: HTML content from the page
        ocr_mode: OCR mode ('auto', 'on', 'off')
        threshold: Text coverage threshold for AUTO mode

    Returns:
        True if OCR should be applied
    """
    if ocr_mode == "off":
        return False
    elif ocr_mode == "on":
        return True
    elif ocr_mode == "auto":
        coverage = compute_text_coverage(html)
        return coverage < threshold
    else:
        return False


__all__ = [
    "OcrResult",
    "OcrEngine",
    "TesseractOcrEngine",
    "OcrCache",
    "compute_text_coverage",
    "needs_ocr",
]
