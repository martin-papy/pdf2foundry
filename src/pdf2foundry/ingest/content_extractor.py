from __future__ import annotations

import base64
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Protocol

from pdf2foundry.ingest.structured_tables import _extract_structured_tables
from pdf2foundry.model.content import (
    HtmlPage,
    ImageAsset,
    LinkRef,
    ParsedContent,
    TableContent,
)
from pdf2foundry.model.pipeline_options import PdfPipelineOptions, TableMode

ProgressCallback = Callable[[str, dict[str, int | str]], None] | None


def _safe_emit(on_progress: ProgressCallback, event: str, payload: dict[str, int | str]) -> None:
    if on_progress is None:
        return
    from contextlib import suppress

    with suppress(Exception):
        on_progress(event, payload)


class DocumentLike(Protocol):
    def num_pages(self) -> int: ...
    def export_to_html(self, **kwargs: object) -> str: ...


def _write_base64_image(data_b64: str, dest_dir: Path, filename: str) -> str:
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        data_bytes = base64.b64decode(data_b64)
    except Exception:
        data_bytes = b""
    (dest_dir / filename).write_bytes(data_bytes)
    return filename


def _extract_images_from_html(
    html: str, page_no: int, assets_dir: Path, name_prefix: str
) -> tuple[str, list[ImageAsset]]:
    pattern = re.compile(r'src="data:image/(?P<ext>[^;\"]+);base64,(?P<data>[^\"]+)"')
    images: list[ImageAsset] = []
    counter = {"n": 0}

    def repl(m: re.Match[str]) -> str:
        counter["n"] += 1
        raw_ext = m.group("ext").lower().strip()
        ext = "jpg" if raw_ext == "jpeg" else ("svg" if "svg" in raw_ext else raw_ext)
        fname = f"{name_prefix}_img_{counter['n']:04d}.{ext}"
        _write_base64_image(m.group("data"), assets_dir, fname)
        rel = f"assets/{fname}"
        images.append(ImageAsset(src=rel, page_no=page_no, name=fname))
        return f'src="{rel}"'

    updated = pattern.sub(repl, html)
    return updated, images


def _rewrite_and_copy_referenced_images(
    html: str, page_no: int, assets_dir: Path, name_prefix: str
) -> tuple[str, list[ImageAsset]]:
    """Copy non-embedded image sources to assets and rewrite src to assets/.

    Handles local file paths, file:// URIs, and relative paths; leaves http(s) and
    data URIs untouched.
    """
    pattern = re.compile(r'src="(?P<src>(?!data:|https?://|mailto:|assets/)[^"]+)"', re.IGNORECASE)
    assets_dir.mkdir(parents=True, exist_ok=True)
    images: list[ImageAsset] = []
    counter = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal counter
        raw = m.group("src")
        src_path = raw
        if raw.lower().startswith("file://"):
            from urllib.parse import urlparse as _urlparse

            src_path = _urlparse(raw).path or ""
        p = Path(src_path)
        if not p.exists():
            return m.group(0)
        counter += 1
        fname = p.name if p.name else f"{name_prefix}_img_{counter:04d}.bin"
        dest = assets_dir / fname
        try:
            dest.write_bytes(p.read_bytes())
        except Exception:
            return m.group(0)
        rel = f"assets/{fname}"
        images.append(ImageAsset(src=rel, page_no=page_no, name=fname))
        return f'src="{rel}"'

    updated = pattern.sub(repl, html)
    return updated, images


def _rasterize_table_placeholder(dest_dir: Path, filename: str) -> str:
    """Write a tiny 1x1 PNG placeholder to dest_dir/filename and return filename.

    We avoid heavy dependencies during tests; real rasterization can replace this later.
    """

    # 1x1 transparent PNG (short constant split to satisfy line length)
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJ"
        "TYQAAAAASUVORK5CYII="
    )
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        data = base64.b64decode(png_b64)
    except Exception:
        data = b""
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
        logger.debug(
            "Table mode IMAGE_ONLY: forcing rasterization for all tables on page %d", page_no
        )
        return _process_tables(html, page_no, assets_dir, "image-only", name_prefix)

    # For AUTO and STRUCTURED modes, try structured extraction first
    structured_tables = _extract_structured_tables(doc, page_no)

    if not structured_tables:
        logger.debug(
            "No structured tables found on page %d, falling back to HTML processing", page_no
        )
        # No structured tables available, fall back to HTML processing
        if options.tables_mode == TableMode.AUTO:
            return _process_tables(html, page_no, assets_dir, "auto", name_prefix)
        else:  # STRUCTURED mode
            logger.warning(
                "STRUCTURED mode requested but no structured tables found on page %d", page_no
            )
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
                        "Low confidence structured table on page %d (%.3f), "
                        "including raster fallback: %s",
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
                        "AUTO mode: structured table confidence too low on page %d "
                        "(%.3f < %.3f), falling back to HTML",
                        page_no,
                        table_confidence,
                        confidence_threshold,
                    )
                    # Fall back to HTML table
                    tables.append(
                        TableContent(kind="html", page_no=page_no, html=block, image_name=None)
                    )
                    current_structured = next(structured_iter, None)
                    return block

        # No structured table available for this HTML table, keep as HTML
        logger.debug("No structured table available for HTML table %d on page %d", counter, page_no)
        tables.append(TableContent(kind="html", page_no=page_no, html=block, image_name=None))
        return block

    updated = pattern.sub(repl, html)

    # Log summary
    structured_count = sum(1 for t in tables if t.kind == "structured")
    html_count = sum(1 for t in tables if t.kind == "html")
    logger.info(
        "Processed tables on page %d: %d structured, %d HTML (mode=%s)",
        page_no,
        structured_count,
        html_count,
        options.tables_mode.value,
    )

    return updated, tables


def _detect_links(html: str, page_no: int) -> list[LinkRef]:
    links: list[LinkRef] = []
    for m in re.finditer(r'<a\s+[^>]*href="(?P<href>[^"]+)"', html, re.IGNORECASE):
        href = m.group("href")
        kind: Literal["external", "internal"] = (
            "external" if href.startswith(("http://", "https://", "mailto:")) else "internal"
        )
        links.append(LinkRef(kind=kind, source_page=page_no, target=href))
    return links


def extract_semantic_content(
    doc: DocumentLike,
    out_assets: Path,
    options: PdfPipelineOptions | str,
    on_progress: ProgressCallback = None,
) -> ParsedContent:
    """Extract content from a pre-loaded Docling document for Foundry VTT.

    This function processes a DoclingDocument that has already been loaded or converted,
    extracting per-page HTML content, images, tables, and links. It's part of the
    single-pass ingestion design where the same document instance is used for both
    structure parsing and content extraction.

    Args:
        doc: A DoclingDocument-like object with num_pages() and export_to_html() methods
        out_assets: Directory where extracted images and assets will be saved
        options: PdfPipelineOptions with table/OCR/caption settings, or legacy string table_mode
        on_progress: Optional callback for progress events

    Returns:
        ParsedContent with pages, images, tables, and links

    Note:
        - Images embedded as base64 are extracted to files and srcs rewritten
        - Links are collected from anchor tags in the HTML
        - Tables support structured extraction, HTML fallback, or image-only modes
        - Backward compatibility maintained for string table_mode parameter
    """

    # Handle backward compatibility for string table_mode parameter
    if isinstance(options, str):
        # Legacy string mode - convert to PdfPipelineOptions
        table_mode = options
        if table_mode == "auto":
            pipeline_options = PdfPipelineOptions(tables_mode=TableMode.AUTO)
        elif table_mode == "image-only":
            pipeline_options = PdfPipelineOptions(tables_mode=TableMode.IMAGE_ONLY)
        else:
            pipeline_options = PdfPipelineOptions(tables_mode=TableMode.AUTO)
    else:
        # New PdfPipelineOptions format
        pipeline_options = options
        table_mode = pipeline_options.tables_mode.value  # For legacy _process_tables calls

    # Determine page count
    try:
        page_count = int(doc.num_pages())
    except Exception:
        page_count = int(getattr(doc, "num_pages", 0) or 0)

    _safe_emit(on_progress, "extract_content:start", {"page_count": page_count})

    image_mode: object | None = None
    try:
        # Optional advanced options when docling-core is present
        from docling_core.types.doc import ImageRefMode
        from docling_core.types.doc.document import ContentLayer

        include_layers = {ContentLayer.BODY, ContentLayer.BACKGROUND, ContentLayer.FURNITURE}
        image_mode = ImageRefMode.EMBEDDED
    except Exception:  # pragma: no cover - optional dependency path
        include_layers = None

    pages: list[HtmlPage] = []
    images: list[ImageAsset] = []
    tables: list[TableContent] = []
    links: list[LinkRef] = []

    # Per-page export with images embedded for reliable extraction
    for p in range(page_count):
        page_no = p + 1
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

        _safe_emit(on_progress, "extract_content:page_exported", {"page_no": page_no})

        # Multi-column detection and flattening (no-op + warning in v1)
        try:
            from pdf2foundry.transform.layout import flatten_page_html

            html = flatten_page_html(html, doc, page_no)
        except Exception:
            # If transform fails for any reason, proceed with original HTML
            pass

        # Extract images (embedded base64)
        html, page_images = _extract_images_from_html(
            html, page_no, out_assets, f"page-{page_no:04d}"
        )
        images.extend(page_images)
        # Copy referenced images (local paths)
        html, ref_images = _rewrite_and_copy_referenced_images(
            html, page_no, out_assets, f"page-{page_no:04d}"
        )
        images.extend(ref_images)
        if ref_images:
            _safe_emit(
                on_progress,
                "extract_content:images_copied",
                {"page_no": page_no, "count": len(ref_images)},
            )
        if page_images:
            _safe_emit(
                on_progress,
                "extract_content:images_extracted",
                {"page_no": page_no, "count": len(page_images)},
            )

        # Tables - use new structured processing if available, fall back to legacy
        if pipeline_options.tables_mode in (TableMode.STRUCTURED, TableMode.AUTO) and hasattr(
            doc, "pages"
        ):
            # Use new structured table processing
            html, page_tables = _process_tables_with_options(
                doc, html, page_no, out_assets, pipeline_options, f"page-{page_no:04d}"
            )
        else:
            # Fall back to legacy HTML-only processing
            html, page_tables = _process_tables(
                html, page_no, out_assets, table_mode, f"page-{page_no:04d}"
            )
        tables.extend(page_tables)

        # Links
        page_links = _detect_links(html, page_no)
        links.extend(page_links)
        if page_links:
            _safe_emit(
                on_progress,
                "extract_content:links_detected",
                {"page_no": page_no, "count": len(page_links)},
            )

        pages.append(HtmlPage(html=html, page_no=page_no))

    _safe_emit(
        on_progress,
        "extract_content:success",
        {"pages": len(pages), "images": len(images), "tables": len(tables)},
    )

    return ParsedContent(
        pages=pages, images=images, tables=tables, links=links, assets_dir=out_assets
    )
