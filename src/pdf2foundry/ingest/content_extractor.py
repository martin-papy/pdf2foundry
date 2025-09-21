from __future__ import annotations

import base64
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol

from pdf2foundry.ingest.ocr_engine import (
    OcrCache,
    OcrResult,
    TesseractOcrEngine,
    compute_text_coverage,
    needs_ocr,
)
from pdf2foundry.ingest.table_processor import (
    _process_tables,
    _process_tables_with_options,
    replace_table_placeholders_in_pages,
)
from pdf2foundry.model.content import (
    HtmlPage,
    ImageAsset,
    LinkRef,
    ParsedContent,
    TableContent,
)
from pdf2foundry.model.pipeline_options import PdfPipelineOptions, TableMode

logger = logging.getLogger(__name__)

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


def _detect_links(html: str, page_no: int) -> list[LinkRef]:
    links: list[LinkRef] = []
    for m in re.finditer(r'<a\s+[^>]*href="(?P<href>[^"]+)"', html, re.IGNORECASE):
        href = m.group("href")
        kind: Literal["external", "internal"] = (
            "external" if href.startswith(("http://", "https://", "mailto:")) else "internal"
        )
        links.append(LinkRef(kind=kind, source_page=page_no, target=href))
    return links


def _apply_ocr_to_page(
    doc: DocumentLike,
    html: str,
    page_no: int,
    options: PdfPipelineOptions,
    ocr_engine: TesseractOcrEngine,
    ocr_cache: OcrCache,
    on_progress: ProgressCallback = None,
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

    Returns:
        HTML content with OCR results merged in
    """

    # Check if OCR is needed for this page
    if not needs_ocr(html, options.ocr_mode.value, options.text_coverage_threshold):
        logger.debug(f"Page {page_no}: OCR not needed (mode={options.ocr_mode.value})")
        return html

    # Check if OCR engine is available
    if not ocr_engine.is_available():
        if options.ocr_mode.value == "on":
            logger.error(f"Page {page_no}: OCR requested but Tesseract not available")
        else:
            logger.warning(f"Page {page_no}: OCR auto-triggered but Tesseract not available")
        return html

    try:
        # Get page as image for OCR
        page_image = _rasterize_page(doc, page_no)
        if page_image is None:
            logger.warning(f"Page {page_no}: Could not rasterize page for OCR")
            return html

        # Check cache first
        ocr_results = ocr_cache.get(page_image)
        if ocr_results is None:
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
            logger.error(f"Page {page_no}: OCR processing failed: {e}")
        else:
            logger.warning(f"Page {page_no}: OCR processing failed: {e}")
        return html


def _rasterize_page(doc: DocumentLike, page_no: int) -> object | None:
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
            return page_image  # type: ignore[no-any-return]

        # Fallback: try to export page as image via other methods
        # This is a simplified approach - in practice, you might need
        # to use pdf2image or similar libraries

        # For now, return None to indicate rasterization not available
        # In a full implementation, you would use pdf2image or similar
        return None

    except Exception:
        return None


def _merge_ocr_results(ocr_results: list[OcrResult], html: str) -> str:
    """Merge OCR results into existing HTML content.

    Args:
        ocr_results: List of OcrResult objects
        html: Existing HTML content

    Returns:
        HTML with OCR results appended
    """
    if not ocr_results:
        return html

    # Create OCR content section
    ocr_html_parts = ['<div class="ocr-content" data-source="ocr">']

    for result in ocr_results:
        if result.text.strip():
            ocr_html_parts.append(f"<p>{result.to_html_span()}</p>")

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

    # Initialize OCR components
    try:
        ocr_engine = TesseractOcrEngine()
        ocr_cache = OcrCache()
        if ocr_engine.is_available():
            _safe_emit(on_progress, "ocr:initialized", {"mode": pipeline_options.ocr_mode.value})
        else:
            _safe_emit(on_progress, "ocr:unavailable", {"mode": pipeline_options.ocr_mode.value})
    except Exception as e:
        logger.warning(f"OCR initialization failed: {e}")
        # Create dummy objects to avoid None checks
        ocr_engine = None
        ocr_cache = None

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

        # OCR processing
        if ocr_engine is not None and ocr_cache is not None:
            html = _apply_ocr_to_page(
                doc, html, page_no, pipeline_options, ocr_engine, ocr_cache, on_progress
            )

        pages.append(HtmlPage(html=html, page_no=page_no))

    # Replace structured table placeholders with actual HTML before finalizing
    replace_table_placeholders_in_pages(pages, tables)

    _safe_emit(
        on_progress,
        "extract_content:success",
        {"pages": len(pages), "images": len(images), "tables": len(tables)},
    )

    return ParsedContent(
        pages=pages, images=images, tables=tables, links=links, assets_dir=out_assets
    )
