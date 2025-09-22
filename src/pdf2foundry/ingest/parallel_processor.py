"""Parallel processing utilities for CPU-bound page-level operations.

This module provides ProcessPoolExecutor-based parallelization for per-page
content extraction stages while maintaining compatibility with sequential
processing and ensuring deterministic output ordering.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pdf2foundry.ingest.table_processor import (
    _process_tables,
    _process_tables_with_options,
)
from pdf2foundry.model.content import HtmlPage, ImageAsset, LinkRef, TableContent
from pdf2foundry.model.pipeline_options import PdfPipelineOptions, TableMode

logger = logging.getLogger(__name__)


@dataclass
class PageProcessingContext:
    """Serializable context for processing a single page."""

    page_no: int
    out_assets_path: str  # Path as string for serialization
    name_prefix: str
    pipeline_options: PdfPipelineOptions
    # Note: We'll pass the document separately as it may not be serializable


@dataclass
class PageProcessingResult:
    """Result of processing a single page."""

    page_no: int
    html_page: HtmlPage
    images: list[ImageAsset]
    tables: list[TableContent]
    links: list[LinkRef]
    processing_time: float


def _extract_images_from_html(html: str, page_no: int, out_assets: Path, name_prefix: str) -> tuple[str, list[ImageAsset]]:
    """Extract base64-encoded images from HTML and save to files.

    This is imported from the content_extractor module.
    """
    # Import here to avoid circular imports
    from pdf2foundry.ingest.content_extractor import _extract_images_from_html as _extract

    return _extract(html, page_no, out_assets, name_prefix)


def _rewrite_and_copy_referenced_images(
    html: str, page_no: int, out_assets: Path, name_prefix: str
) -> tuple[str, list[ImageAsset]]:
    """Copy referenced images and rewrite HTML paths.

    This is imported from the content_extractor module.
    """
    # Import here to avoid circular imports
    from pdf2foundry.ingest.content_extractor import _rewrite_and_copy_referenced_images as _rewrite

    return _rewrite(html, page_no, out_assets, name_prefix)


def _detect_links(html: str, page_no: int) -> list[LinkRef]:
    """Detect links in HTML content.

    This is imported from the content_extractor module.
    """
    # Import here to avoid circular imports
    from pdf2foundry.ingest.content_extractor import _detect_links as _detect

    return _detect(html, page_no)


def process_page_content(
    doc: Any,
    context: PageProcessingContext,
    include_layers: Any = None,
    image_mode: Any = None,
) -> PageProcessingResult:
    """Process a single page's content extraction.

    This function performs all CPU-bound operations for a single page:
    - HTML export from Docling document
    - Layout transformation
    - Image extraction and processing
    - Table processing
    - Link detection
    - OCR processing (if enabled)

    Args:
        doc: Docling document object
        context: Page processing context with serializable parameters
        include_layers: Optional content layers for HTML export
        image_mode: Optional image mode for HTML export

    Returns:
        PageProcessingResult with all extracted content
    """
    start_time = time.perf_counter()

    page_no = context.page_no
    out_assets = Path(context.out_assets_path)
    pipeline_options = context.pipeline_options
    name_prefix = context.name_prefix

    logger.debug(f"Processing page {page_no} in worker process")

    # 1. Export HTML from Docling document
    try:
        if include_layers is not None:
            if image_mode is not None:
                html = doc.export_to_html(
                    page_no=page_no,
                    split_page_view=False,
                    included_content_layers=include_layers,
                    image_mode=image_mode,
                )
            else:
                html = doc.export_to_html(
                    page_no=page_no,
                    split_page_view=False,
                    included_content_layers=include_layers,
                )
        else:
            if image_mode is not None:
                html = doc.export_to_html(
                    page_no=page_no,
                    split_page_view=False,
                    image_mode=image_mode,
                )
            else:
                html = doc.export_to_html(
                    page_no=page_no,
                    split_page_view=False,
                )
    except Exception:
        html = ""

    # 2. Multi-column detection and flattening (no-op + warning in v1)
    try:
        from pdf2foundry.transform.layout import flatten_page_html

        html = flatten_page_html(html, doc, page_no, reflow_enabled=pipeline_options.reflow_columns)
    except Exception:
        # If transform fails for any reason, proceed with original HTML
        pass

    # 3. Extract images (embedded base64)
    html, page_images = _extract_images_from_html(html, page_no, out_assets, name_prefix)
    images = list(page_images)

    # 4. Copy referenced images (local paths)
    html, ref_images = _rewrite_and_copy_referenced_images(html, page_no, out_assets, name_prefix)
    images.extend(ref_images)

    # 5. Tables - use new structured processing if available, fall back to legacy
    if pipeline_options.tables_mode in (TableMode.STRUCTURED, TableMode.AUTO) and hasattr(doc, "pages"):
        # Use new structured table processing
        html, page_tables = _process_tables_with_options(doc, html, page_no, out_assets, pipeline_options, name_prefix)
    else:
        # Fall back to legacy HTML-only processing
        html, page_tables = _process_tables(html, page_no, out_assets, pipeline_options.tables_mode.value, name_prefix)
    tables = list(page_tables)

    # 6. Links
    page_links = _detect_links(html, page_no)
    links = list(page_links)

    # 7. OCR processing is not supported in parallel mode due to cache serialization issues
    # OCR processing is handled separately in sequential mode when enabled

    processing_time = time.perf_counter() - start_time

    return PageProcessingResult(
        page_no=page_no,
        html_page=HtmlPage(html=html, page_no=page_no),
        images=images,
        tables=tables,
        links=links,
        processing_time=processing_time,
    )


def process_pages_parallel(
    doc: Any,
    selected_pages: list[int],
    out_assets: Path,
    pipeline_options: PdfPipelineOptions,
    include_layers: Any = None,
    image_mode: Any = None,
) -> tuple[list[HtmlPage], list[ImageAsset], list[TableContent], list[LinkRef], float]:
    """Process multiple pages in parallel using ProcessPoolExecutor.

    Args:
        doc: Docling document object
        selected_pages: List of 1-based page numbers to process
        out_assets: Directory for extracted assets
        pipeline_options: Pipeline configuration options
        include_layers: Optional content layers for HTML export
        image_mode: Optional image mode for HTML export

    Returns:
        Tuple of (pages, images, tables, links, total_time)
    """
    start_time = time.perf_counter()

    workers = getattr(pipeline_options, "workers_effective", pipeline_options.workers)

    if workers <= 1:
        # Fall back to sequential processing
        return _process_pages_sequential(doc, selected_pages, out_assets, pipeline_options, include_layers, image_mode)

    logger.info(f"Processing {len(selected_pages)} pages using {workers} workers")

    # Prepare contexts for each page
    contexts = []
    for page_no in selected_pages:
        context = PageProcessingContext(
            page_no=page_no,
            out_assets_path=str(out_assets),
            name_prefix=f"page-{page_no:04d}",
            pipeline_options=pipeline_options,
        )
        contexts.append(context)

    # Process pages in parallel
    results: dict[int, PageProcessingResult] = {}

    try:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            # Submit all tasks
            future_to_page = {}
            for context in contexts:
                try:
                    future = executor.submit(
                        process_page_content,
                        doc,
                        context,
                        include_layers,
                        image_mode,
                    )
                    future_to_page[future] = context.page_no
                except Exception as e:
                    # Handle pickling/serialization errors at submission time
                    logger.warning(f"Failed to submit page {context.page_no} for parallel processing: {e}")
                    raise

            # Collect results as they complete
            for future in as_completed(future_to_page):
                page_no = future_to_page[future]
                try:
                    result = future.result()
                    results[page_no] = result
                    logger.debug(f"Page {page_no} completed in {result.processing_time:.3f}s")
                except Exception as e:
                    logger.error(f"Page {page_no} failed: {e}")
                    # Cancel remaining futures and re-raise
                    for remaining_future in future_to_page:
                        remaining_future.cancel()
                    raise RuntimeError(f"Page {page_no} processing failed: {e}") from e

    except Exception as e:
        # Handle various failure modes:
        # - Pickling/serialization errors (Windows/macOS spawn mode)
        # - Process creation failures
        # - Platform-specific multiprocessing issues
        logger.warning(
            "Parallel processing failed (%s: %s). Falling back to sequential mode.",
            type(e).__name__,
            e,
        )
        return _process_pages_sequential(doc, selected_pages, out_assets, pipeline_options, include_layers, image_mode)

    # Collect results in deterministic order (by page number)
    pages = []
    images = []
    tables = []
    links = []

    for page_no in selected_pages:
        if page_no in results:
            result = results[page_no]
            pages.append(result.html_page)
            images.extend(result.images)
            tables.extend(result.tables)
            links.extend(result.links)
        else:
            logger.error(f"Missing result for page {page_no}")
            # Create empty page as fallback
            pages.append(HtmlPage(html="", page_no=page_no))

    total_time = time.perf_counter() - start_time
    logger.info(f"Page-level transforms completed in {total_time:.3f}s using {workers} workers")

    return pages, images, tables, links, total_time


def _process_pages_sequential(
    doc: Any,
    selected_pages: list[int],
    out_assets: Path,
    pipeline_options: PdfPipelineOptions,
    include_layers: Any = None,
    image_mode: Any = None,
) -> tuple[list[HtmlPage], list[ImageAsset], list[TableContent], list[LinkRef], float]:
    """Process pages sequentially (fallback mode).

    This function replicates the original sequential processing logic
    for compatibility when parallel processing is not available.
    """
    start_time = time.perf_counter()

    logger.info(f"Processing {len(selected_pages)} pages sequentially")

    pages = []
    images = []
    tables = []
    links = []

    for page_no in selected_pages:
        context = PageProcessingContext(
            page_no=page_no,
            out_assets_path=str(out_assets),
            name_prefix=f"page-{page_no:04d}",
            pipeline_options=pipeline_options,
        )

        result = process_page_content(doc, context, include_layers, image_mode)

        pages.append(result.html_page)
        images.extend(result.images)
        tables.extend(result.tables)
        links.extend(result.links)

    total_time = time.perf_counter() - start_time
    logger.info(f"Page-level transforms completed in {total_time:.3f}s using 1 worker")

    return pages, images, tables, links, total_time
