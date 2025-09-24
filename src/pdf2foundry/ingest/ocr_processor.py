"""OCR processing functionality for content extraction."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from typing import Any

from pdf2foundry.ingest.error_handling import ErrorContext, ErrorManager
from pdf2foundry.ingest.ocr_engine import (
    OcrCache,
    OcrResult,
    TesseractOcrEngine,
    compute_text_coverage,
    needs_ocr,
)
from pdf2foundry.model.pipeline_options import PdfPipelineOptions

ProgressCallback = Callable[[str, dict[str, int | str]], None] | None

logger = logging.getLogger(__name__)


def _safe_emit(callback: ProgressCallback, event: str, payload: dict[str, int | str]) -> None:
    """Safely emit progress event, ignoring any exceptions."""
    if callback is not None:
        with contextlib.suppress(Exception):
            callback(event, payload)


def apply_ocr_to_page(
    doc: Any,
    html: str,
    page_no: int,
    options: PdfPipelineOptions,
    ocr_engine: TesseractOcrEngine,
    ocr_cache: OcrCache,
    on_progress: ProgressCallback = None,
    shared_image_cache: Any = None,
) -> str:
    """Apply OCR processing to a page if needed and merge results into HTML.

    Args:
        doc: Document object for page rasterization
        html: Current HTML content for the page
        page_no: 1-based page number
        options: Pipeline options with OCR settings
        ocr_engine: OCR engine instance
        ocr_cache: OCR result cache
        on_progress: Progress callback
        shared_image_cache: Shared image cache for optimization

    Returns:
        HTML content with OCR results merged in
    """
    # Check if OCR is needed for this page
    if not needs_ocr(html, options.ocr_mode.value, options.text_coverage_threshold):
        # Log OCR auto decision when in auto mode
        if options.ocr_mode.value == "auto":
            context = ErrorContext(
                source_module="ocr_processor",
                page=page_no,
                object_kind="ocr",
                flags={"ocr_mode": options.ocr_mode.value},
            )
            error_mgr = ErrorManager(context)
            error_mgr.decision(
                "DL-OCR-DEC",
                "ocr.auto",
                "disabled",
                extra={
                    "reason": "sufficient_text_coverage",
                    "coverage": compute_text_coverage(html),
                    "threshold": options.text_coverage_threshold,
                },
            )
        logger.debug(f"Page {page_no}: OCR not needed (mode={options.ocr_mode.value})")
        return html

    # Set up error handling context
    context = ErrorContext(
        source_module="ocr_processor",
        page=page_no,
        object_kind="ocr",
        flags={"ocr_mode": options.ocr_mode.value},
    )
    error_mgr = ErrorManager(context)

    # Check if OCR engine is available
    if not ocr_engine.is_available():
        if options.ocr_mode.value == "on":
            # When OCR is explicitly requested, fail hard if Tesseract is not available
            error_mgr.error_policy(
                "OCR",
                "missing_dependency",
                "fail",
                details="OCR mode 'on' but Tesseract not available",
                event_code="DL-OCR001",
            )
            # Import and raise the appropriate exception
            from pdf2foundry.core.exceptions import FeatureNotAvailableError

            raise FeatureNotAvailableError(
                "OCR mode 'on' requires Tesseract but it is not available. "
                "Please install Tesseract or use '--ocr auto' to allow graceful degradation.",
                feature="OCR",
            )
        else:
            # For auto mode, gracefully degrade with a warning
            error_mgr.error_policy(
                "OCR",
                "missing_dependency",
                "skip",
                details="OCR mode 'auto' but Tesseract not available",
                event_code="DL-OCR002",
            )
        return html

    try:
        # Get page as image for OCR - use shared cache if available
        if shared_image_cache is not None:
            # Convert to 0-based page index
            cached_image = shared_image_cache.get_cached_page_image(doc, page_no - 1)
            if cached_image is None:
                logger.warning(f"Page {page_no}: Could not rasterize page for OCR")
                return html
            page_image = cached_image.image
        else:
            # Fallback to direct rasterization
            page_image = _rasterize_page(doc, page_no)
            if page_image is None:
                logger.warning(f"Page {page_no}: Could not rasterize page for OCR")
                return html

        # Check cache first
        ocr_results = ocr_cache.get(page_image)
        if ocr_results is None:
            # Log OCR decision when actually running OCR
            if options.ocr_mode.value == "auto":
                error_mgr.decision(
                    "DL-OCR-DEC",
                    "ocr.auto",
                    "enabled",
                    extra={
                        "reason": "low_text_coverage",
                        "coverage": compute_text_coverage(html),
                        "threshold": options.text_coverage_threshold,
                        "engine": "tesseract",
                    },
                )

            # Run OCR
            logger.info(f"Page {page_no}: Running OCR (coverage={compute_text_coverage(html):.3f})")
            ocr_results = ocr_engine.run(page_image)
            ocr_cache.set(page_image, None, ocr_results)

            _safe_emit(
                on_progress,
                "ocr:page_processed",
                {"page_no": page_no, "results_count": len(ocr_results)},
            )
        else:
            logger.debug(f"Page {page_no}: Using cached OCR results")

        # Merge OCR results into HTML
        if ocr_results:
            ocr_html = _merge_ocr_results(ocr_results, html)
            logger.info(f"Page {page_no}: OCR added {len(ocr_results)} text blocks")
            return ocr_html
        else:
            logger.info(f"Page {page_no}: OCR found no text")
            return html

    except Exception as e:
        if options.ocr_mode.value == "on":
            error_mgr.error_policy(
                "OCR",
                "processing_failed",
                "continue",
                details=f"OCR processing failed: {e}",
                event_code="DL-OCR003",
            )
        else:
            error_mgr.error_policy(
                "OCR",
                "processing_failed",
                "skip",
                details=f"OCR processing failed: {e}",
                event_code="DL-OCR004",
            )
        return html


def _rasterize_page(doc: Any, page_no: int) -> Any | None:
    """Rasterize a page to a PIL Image for OCR processing.

    Args:
        doc: Document object
        page_no: 1-based page number

    Returns:
        PIL Image of the page, or None if rasterization fails
    """
    try:
        # Try to use Docling's page rasterization if available
        if hasattr(doc, "pages") and hasattr(doc, "render_page"):
            # Use Docling's built-in page rendering
            page_image = doc.render_page(page_no - 1)  # Docling uses 0-based indexing
            return page_image

        # Fallback: try to export page as image via other methods
        # This is a simplified approach - in practice, you might need
        # to use pdf2image or similar libraries

        # For now, return None to indicate rasterization not available
        # In a full implementation, you would use pdf2image or similar
        return None

    except Exception:
        return None


def _merge_ocr_results(ocr_results: list[OcrResult], html: str) -> str:
    """Merge OCR results into HTML content.

    Args:
        ocr_results: List of OCR results to merge
        html: Original HTML content

    Returns:
        HTML with OCR results merged in
    """
    if not ocr_results:
        return html

    # Filter out empty or whitespace-only results
    valid_results = [result for result in ocr_results if result.text.strip()]

    if not valid_results:
        return html

    # Create OCR content section
    ocr_html_parts = ['<div class="ocr-content" data-source="ocr">']

    for result in valid_results:
        # Build attributes for the paragraph tag
        attrs = ['data-ocr="true"']

        if result.confidence > 0:
            attrs.append(f'data-ocr-confidence="{result.confidence:.3f}"')

        if result.language:
            attrs.append(f'data-ocr-language="{result.language}"')

        if result.bbox:
            # Convert bbox to x,y,w,h format expected by tests
            x, y, w, h = result.bbox
            attrs.append(f'data-bbox="{x},{y},{w},{h}"')

        attrs_str = " " + " ".join(attrs) if attrs else ""

        # Escape HTML in the text content
        escaped_text = result.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        ocr_html_parts.append(f"<p{attrs_str}>{escaped_text}</p>")

    ocr_html_parts.append("</div>")

    # Append OCR content to existing HTML
    # Insert before closing body/html tags if present, otherwise append
    ocr_content = "\n".join(ocr_html_parts)

    if "</body>" in html:
        return html.replace("</body>", f"{ocr_content}\n</body>")
    elif "</html>" in html:
        return html.replace("</html>", f"{ocr_content}\n</html>")
    else:
        return html + "\n" + ocr_content


__all__ = [
    "apply_ocr_to_page",
]
