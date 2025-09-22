"""Table processing functionality for content extraction.

This module handles table processing during content extraction, including
structured table extraction, HTML table processing, and placeholder replacement.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from pdf2foundry.ingest.error_handling import ErrorContext, ErrorManager
from pdf2foundry.ingest.feature_logger import log_feature_decision
from pdf2foundry.ingest.structured_tables import _extract_structured_tables
from pdf2foundry.model.content import TableContent
from pdf2foundry.model.pipeline_options import PdfPipelineOptions, TableMode


def _rasterize_table_placeholder(dest_dir: Path, filename: str) -> str:
    """Create a tiny PNG placeholder for rasterized tables."""
    # 1x1 transparent PNG (70 bytes) - properly formatted with all required chunks
    data = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c6360606060000000050001a5f645400000000049454e44ae426082"
    )

    (dest_dir / filename).write_bytes(data)
    return filename


def _process_tables(
    html: str, page_no: int, assets_dir: Path, table_mode: str, name_prefix: str
) -> tuple[str, list[TableContent]]:
    """Process <table> blocks.

    - auto: leave HTML tables intact; record TableContent(kind="html")
    - image-only: replace each table with an <img src="assets/..."> placeholder and
      write a tiny PNG file; record TableContent(kind="image")
    """

    tables: list[TableContent] = []
    # Simple, robust-enough pattern to capture table blocks
    pattern = re.compile(r"<table[\s\S]*?</table>", re.IGNORECASE)
    counter = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal counter
        counter += 1
        block = m.group(0)
        if table_mode == "image-only":
            fname = f"{name_prefix}_table_{counter:04d}.png"
            _rasterize_table_placeholder(assets_dir, fname)
            tables.append(TableContent(kind="image", page_no=page_no, html=None, image_name=fname))
            return f'<img src="assets/{fname}">'
        # auto mode: keep as HTML
        tables.append(TableContent(kind="html", page_no=page_no, html=block, image_name=None))
        return block

    updated = pattern.sub(repl, html)
    return updated, tables


def _process_tables_with_options(
    doc: Any,
    html: str,
    page_no: int,
    assets_dir: Path,
    options: PdfPipelineOptions,
    name_prefix: str,
) -> tuple[str, list[TableContent]]:
    """Process tables with structured extraction support based on pipeline options.

    Args:
        doc: Docling document with structured table data
        html: HTML content for the page
        page_no: Page number (1-based)
        assets_dir: Directory for assets
        options: Pipeline options with table configuration
        name_prefix: Prefix for generated asset filenames

    Returns:
        Tuple of (updated_html, table_content_list)
    """
    logger = logging.getLogger(__name__)
    tables: list[TableContent] = []

    # Handle IMAGE_ONLY mode - skip structured extraction entirely
    if options.tables_mode == TableMode.IMAGE_ONLY:
        log_feature_decision("Tables", "force_rasterization", {"page": page_no, "mode": "IMAGE_ONLY"})
        logger.debug("Table mode IMAGE_ONLY: forcing rasterization for all tables on page %d", page_no)
        return _process_tables(html, page_no, assets_dir, "image-only", name_prefix)

    # Set up error handling context
    context = ErrorContext(
        source_module="table_processor",
        page=page_no,
        object_kind="table",
        flags={"tables_mode": options.tables_mode.value},
    )
    error_mgr = ErrorManager(context)

    # For AUTO and STRUCTURED modes, try structured extraction first
    try:
        structured_tables = _extract_structured_tables(doc, page_no)
    except Exception as e:
        # Structured table extraction failed
        error_mgr.warn(
            "DL-TB003",
            f"Structured table extraction failed on page {page_no}: {e}",
            extra={
                "error_type": "extraction_failed",
                "fallback_used": "html_processing",
                "mode": options.tables_mode.value,
            },
            exception=e,
        )
        structured_tables = []

    if not structured_tables:
        if options.tables_mode == TableMode.STRUCTURED:
            # STRUCTURED mode but no tables found - this is a warning
            error_mgr.warn(
                "DL-TB004",
                f"STRUCTURED mode requested but no structured tables found on page {page_no}",
                extra={
                    "mode": "STRUCTURED",
                    "fallback_used": "html_processing",
                    "reason": "no_structured_tables",
                },
            )
        else:
            # AUTO mode - this is expected, just log decision
            log_feature_decision("Tables", "fallback_to_html", {"page": page_no, "reason": "no_structured_tables"})
            logger.debug("No structured tables found on page %d, falling back to HTML processing", page_no)

        # Fall back to HTML processing for both modes
        return _process_tables(html, page_no, assets_dir, "auto", name_prefix)

    # We have structured tables - process them based on mode
    confidence_threshold = getattr(options, "tables_confidence_threshold", 0.6)

    # Simple approach: replace HTML tables with structured ones
    # In a more sophisticated implementation, we'd match HTML tables to structured ones
    pattern = re.compile(r"<table[\s\S]*?</table>", re.IGNORECASE)
    counter = 0
    structured_iter = iter(structured_tables)
    current_structured = next(structured_iter, None)

    def repl(m: re.Match[str]) -> str:
        nonlocal counter, current_structured
        counter += 1
        block = m.group(0)

        if current_structured is not None:
            # Get confidence for this structured table
            table_confidence = current_structured.meta.get("confidence", 0.5)
            if table_confidence is None:
                table_confidence = 0.5

            # Decision logic based on mode and confidence
            if options.tables_mode == TableMode.STRUCTURED:
                # STRUCTURED mode: always use structured table, even if low confidence
                logger.debug(
                    "STRUCTURED mode: using structured table on page %d (confidence=%.3f)",
                    page_no,
                    table_confidence,
                )
                tables.append(
                    TableContent(
                        kind="structured",
                        page_no=page_no,
                        html=None,
                        image_name=None,
                        structured_table=current_structured,
                    )
                )

                # If confidence is very low, also provide raster fallback
                if table_confidence < 0.3:
                    fname = f"{name_prefix}_table_{counter:04d}_fallback.png"
                    _rasterize_table_placeholder(assets_dir, fname)
                    logger.warning(
                        "Low confidence structured table on page %d (%.3f), " "including raster fallback: %s",
                        page_no,
                        table_confidence,
                        fname,
                    )

                # Move to next structured table
                current_structured = next(structured_iter, None)
                return f"<!-- structured table {counter} -->"

            elif options.tables_mode == TableMode.AUTO:
                # AUTO mode: use structured if confidence is above threshold
                if table_confidence >= confidence_threshold:
                    logger.debug(
                        "AUTO mode: using structured table on page %d (confidence=%.3f >= %.3f)",
                        page_no,
                        table_confidence,
                        confidence_threshold,
                    )
                    tables.append(
                        TableContent(
                            kind="structured",
                            page_no=page_no,
                            html=None,
                            image_name=None,
                            structured_table=current_structured,
                        )
                    )
                    current_structured = next(structured_iter, None)
                    return f"<!-- structured table {counter} -->"
                else:
                    logger.debug(
                        "AUTO mode: structured table confidence too low on page %d " "(%.3f < %.3f), falling back to HTML",
                        page_no,
                        table_confidence,
                        confidence_threshold,
                    )
                    # Fall back to HTML table
                    tables.append(TableContent(kind="html", page_no=page_no, html=block, image_name=None))
                    current_structured = next(structured_iter, None)
                    return block

        # No structured table available for this HTML table, keep as HTML
        logger.debug("No structured table available for HTML table %d on page %d", counter, page_no)
        tables.append(TableContent(kind="html", page_no=page_no, html=block, image_name=None))
        return block

    updated = pattern.sub(repl, html)

    # Log summary
    structured_count = sum(1 for t in tables if t.kind == "structured")
    if structured_count > 0:
        logger.info(
            "Page %d: processed %d tables (%d structured, %d other)",
            page_no,
            len(tables),
            structured_count,
            len(tables) - structured_count,
        )

    return updated, tables


def replace_table_placeholders_in_pages(pages: list[Any], tables: list[TableContent]) -> None:
    """Replace structured table placeholders with actual HTML in page content.

    Args:
        pages: List of HtmlPage objects to process
        tables: List of TableContent objects containing structured tables

    This function modifies the pages in-place, replacing structured table
    placeholders with rendered HTML table markup.
    """
    if not any(t.kind == "structured" for t in tables):
        return

    from pdf2foundry.transform.table_renderer import replace_structured_table_placeholders

    # Group tables by page for efficient replacement
    tables_by_page: dict[int, list[TableContent]] = {}
    for table in tables:
        page_tables = tables_by_page.setdefault(table.page_no, [])
        page_tables.append(table)

    # Replace placeholders in each page's HTML
    for page in pages:
        page_tables = tables_by_page.get(page.page_no, [])
        if page_tables and any(t.kind == "structured" for t in page_tables):
            page.html = replace_structured_table_placeholders(page.html, page_tables)
