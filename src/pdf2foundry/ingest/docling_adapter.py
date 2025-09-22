from __future__ import annotations

import logging
from functools import cache
from pathlib import Path
from typing import Protocol, cast

from pdf2foundry.ingest.error_handling import ErrorContext, ErrorManager, PdfParseError

logger = logging.getLogger(__name__)


class DoclingDocumentLike(Protocol):
    """Minimal surface used downstream by content extraction.

    Must be compatible with DocumentLike from content_extractor.
    """

    def num_pages(self) -> int: ...  # pragma: no cover - interface
    def export_to_html(self, **kwargs: object) -> str:  # pragma: no cover - interface
        ...


def run_docling_conversion(
    pdf_path: Path,
    *,
    images: bool = True,
    ocr: bool = False,
    tables_mode: str = "auto",
    vlm: str | None = None,
    pages: list[int] | None = None,
    workers: int = 0,
) -> DoclingDocumentLike:
    """Convert a PDF to a Docling document with caching and light API guards.

    Results are cached per normalized parameter tuple to ensure a single conversion
    per unique configuration within the process lifetime.
    """
    key = (
        str(pdf_path),
        bool(images),
        bool(ocr),
        str(tables_mode),
        vlm,
        tuple(pages) if pages is not None else None,
        int(workers),
    )
    doc = _cached_convert(key)

    # Basic type/surface guard to fail fast if upstream API changes
    if not hasattr(doc, "export_to_html") or not callable(doc.export_to_html):
        raise TypeError("Docling conversion result lacks required 'export_to_html' method")
    return doc


def load_docling_document(
    pdf: Path,
    *,
    images: bool = True,
    ocr: bool = False,
    tables_mode: str = "auto",
    vlm: str | None = None,
    pages: list[int] | None = None,
    workers: int = 0,
) -> DoclingDocumentLike:
    """Convenience shim around run_docling_conversion with the same parameters."""
    return run_docling_conversion(
        pdf,
        images=images,
        ocr=ocr,
        tables_mode=tables_mode,
        vlm=vlm,
        pages=pages,
        workers=workers,
    )


@cache
def _cached_convert(
    key: tuple[
        str,
        bool,
        bool,
        str,
        str | None,
        tuple[int, ...] | None,
        int,
    ],
) -> DoclingDocumentLike:
    pdf_path_str, images, ocr, tables_mode, vlm, pages_tuple, workers = key
    pdf_path = Path(pdf_path_str)
    pages = list(pages_tuple) if pages_tuple is not None else None
    return _do_docling_convert_impl(
        pdf_path,
        images=images,
        ocr=ocr,
        tables_mode=tables_mode,
        vlm=vlm,
        pages=pages,
        workers=workers,
    )


def _do_docling_convert_impl(
    pdf_path: Path,
    *,
    images: bool,
    ocr: bool,
    tables_mode: str,
    vlm: str | None,
    pages: list[int] | None,
    workers: int,
) -> DoclingDocumentLike:
    """Actual Docling call isolated for monkeypatching in tests.

    Imports are inside the function to avoid hard dependency at module import time.
    Non-essential parameters like tables_mode/vlm/pages/workers are accepted for
    forward-compatibility and included in the cache key, even if not all are used
    by the underlying Docling API.

    Raises:
        PdfParseError: If PDF conversion fails fatally
    """
    # Set up error handling context
    context = ErrorContext(
        pdf_path=pdf_path,
        source_module="docling_adapter",
        flags={
            "images": images,
            "ocr": ocr,
            "tables_mode": tables_mode,
            "vlm": vlm,
            "pages": pages,
            "workers": workers,
        },
    )
    error_mgr = ErrorManager(context)

    try:
        # Local import to avoid mandatory dependency at module import time
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import (
            DocumentConverter,
            PdfFormatOption,
        )

        pipe_opts = PdfPipelineOptions(
            generate_picture_images=images,
            generate_page_images=images,
            do_ocr=ocr,
        )

        # Note: pages, workers, tables_mode, vlm are accepted but may require
        # additional wiring based on Docling capabilities; kept in signature and
        # cache key for deterministic behavior across configurations.
        conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipe_opts)})

        # Attempt the conversion with proper error handling
        result = conv.convert(str(pdf_path))
        doc: DoclingDocumentLike = cast(DoclingDocumentLike, result.document)

        logger.info(
            ("Converted PDF to Docling document: path=%s images=%s ocr=%s " "tables_mode=%s vlm=%s pages=%s workers=%s"),
            pdf_path,
            images,
            ocr,
            tables_mode,
            vlm,
            pages,
            workers,
        )
        return doc

    except ImportError as e:
        # Docling not available
        error_mgr.error(
            "DL-PDF001",
            f"Docling library not available: {e}",
            extra={"error_type": "missing_dependency", "user_action": "Install docling package"},
            exception=e,
        )
        raise PdfParseError(pdf_path, cause=e) from e

    except Exception as e:
        # Any other conversion error
        error_mgr.error(
            "DL-PDF001",
            f"PDF conversion failed: {e}",
            extra={
                "error_type": "conversion_failed",
                "user_action": "Check PDF file integrity and Docling compatibility",
            },
            exception=e,
        )
        raise PdfParseError(pdf_path, cause=e) from e


__all__ = [
    "DoclingDocumentLike",
    "load_docling_document",
    "run_docling_conversion",
]
