from __future__ import annotations

import base64
import logging
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Literal, Protocol

from pdf2foundry.ingest.caption_processor import (
    apply_captions_to_images,
    initialize_caption_components,
)
from pdf2foundry.ingest.feature_logger import (
    log_feature_availability,
    log_pipeline_configuration,
)
from pdf2foundry.ingest.ocr_engine import OcrCache, TesseractOcrEngine
from pdf2foundry.ingest.ocr_processor import apply_ocr_to_page
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


def _resolve_selected_pages(total_pages: int, pages_option: list[int] | None) -> list[int]:
    """Resolve and validate the selected pages for processing.

    Args:
        total_pages: Total number of pages in the document
        pages_option: Optional list of 1-based page indices from CLI options

    Returns:
        List of 1-based page numbers to process, sorted in ascending order

    Raises:
        ValueError: If any requested page exceeds the document length
    """
    if pages_option is None:
        # Process all pages
        return list(range(1, total_pages + 1))

    # Validate that all requested pages exist
    max_requested = max(pages_option) if pages_option else 0
    if max_requested > total_pages:
        raise ValueError(f"Requested page {max_requested} exceeds document length {total_pages}")

    # Return sorted, deduplicated list (pages_option should already be sorted from CLI parsing)
    return sorted(set(pages_option))


def yield_pages(doc: DocumentLike, selected_pages: list[int]) -> Iterator[tuple[int, int]]:
    """Yield (page_no, zero_based_index) pairs for the selected pages in deterministic order.

    Args:
        doc: Document object (not used currently but kept for future extensibility)
        selected_pages: List of 1-based page numbers to process

    Yields:
        Tuples of (page_no, zero_based_index) for each selected page
    """
    for page_no in selected_pages:
        yield page_no, page_no - 1


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


def _extract_images_from_html(html: str, page_no: int, assets_dir: Path, name_prefix: str) -> tuple[str, list[ImageAsset]]:
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


def extract_semantic_content(
    doc: DocumentLike,
    out_assets: Path,
    options: PdfPipelineOptions,
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
        options: PdfPipelineOptions with table/OCR/caption settings
        on_progress: Optional callback for progress events

    Returns:
        ParsedContent with pages, images, tables, and links

    Note:
        - Images embedded as base64 are extracted to files and srcs rewritten
        - Links are collected from anchor tags in the HTML
        - Tables support structured extraction, HTML fallback, or image-only modes
    """

    pipeline_options = options

    # Determine page count
    try:
        page_count = int(doc.num_pages())
    except Exception:
        page_count = int(getattr(doc, "num_pages", 0) or 0)

    # Determine selected pages and validate
    selected_pages = _resolve_selected_pages(page_count, pipeline_options.pages)

    _safe_emit(on_progress, "extract_content:start", {"page_count": len(selected_pages)})

    # Log pipeline configuration for debugging
    log_pipeline_configuration(pipeline_options)

    # Log page processing summary
    if pipeline_options.pages is not None:
        from pdf2foundry.ingest.feature_logger import _format_page_spec

        logger.info(
            "Processing pages: %s (%d of %d)",
            _format_page_spec(selected_pages),
            len(selected_pages),
            page_count,
        )
    else:
        logger.info("Processing all pages (%d total)", page_count)

    image_mode: object | None = None
    try:
        # Optional advanced options when docling-core is present
        from docling_core.types.doc import ImageRefMode  # type: ignore[attr-defined]
        from docling_core.types.doc.document import ContentLayer

        include_layers = {ContentLayer.BODY, ContentLayer.BACKGROUND, ContentLayer.FURNITURE}
        image_mode = ImageRefMode.EMBEDDED
    except Exception:  # pragma: no cover - optional dependency path
        include_layers = None

    pages: list[HtmlPage] = []
    images: list[ImageAsset] = []
    tables: list[TableContent] = []
    links: list[LinkRef] = []

    # Initialize shared image cache if needed
    from pdf2foundry.ingest.image_cache import (
        CacheLimits,
        SharedImageCache,
        should_enable_image_cache,
    )

    shared_image_cache = None
    if should_enable_image_cache(
        pipeline_options.tables_mode.value,
        pipeline_options.ocr_mode.value,
        pipeline_options.picture_descriptions,
    ):
        # Get cache limits from options if available, otherwise use defaults
        cache_limits = getattr(pipeline_options, "cache_limits", None) or CacheLimits()
        shared_image_cache = SharedImageCache(cache_limits)
        logger.debug("Initialized shared image cache")

    # Initialize OCR components
    try:
        ocr_engine = TesseractOcrEngine()
        # Pass cache limits to OCR cache
        ocr_cache_size = cache_limits.ocr_cache if shared_image_cache else 2000
        ocr_cache = OcrCache(max_size=ocr_cache_size)
        if ocr_engine.is_available():
            log_feature_availability("OCR", True)
            _safe_emit(on_progress, "ocr:initialized", {"mode": pipeline_options.ocr_mode.value})
        else:
            log_feature_availability("OCR", False, "Tesseract not available")
            _safe_emit(on_progress, "ocr:unavailable", {"mode": pipeline_options.ocr_mode.value})
    except Exception as e:
        log_feature_availability("OCR", False, f"Initialization failed: {e}")
        logger.warning(f"OCR initialization failed: {e}")
        # Create dummy objects to avoid None checks
        ocr_engine = None
        ocr_cache = None

    # Initialize Caption components
    caption_engine, caption_cache = initialize_caption_components(pipeline_options, on_progress, shared_image_cache)

    # Check if we should use parallel processing
    # Note: Parallel processing is disabled when OCR or captions are enabled
    # because these components use caches that are not thread/process-safe
    workers_effective = getattr(pipeline_options, "workers_effective", pipeline_options.workers)
    use_parallel = workers_effective > 1 and ocr_engine is None and caption_engine is None

    if workers_effective > 1 and not use_parallel:
        logger.info(
            "Parallel processing disabled due to OCR or caption processing. " "Using sequential mode for cache safety."
        )

    if use_parallel:
        # Use parallel processing for CPU-bound page operations
        from pdf2foundry.ingest.parallel_processor import process_pages_parallel

        pages, images, tables, links, processing_time = process_pages_parallel(
            doc=doc,
            selected_pages=selected_pages,
            out_assets=out_assets,
            pipeline_options=pipeline_options,
            include_layers=include_layers,
            image_mode=image_mode,
        )

        # Emit progress events for parallel processing
        for page in pages:
            _safe_emit(on_progress, "extract_content:page_exported", {"page_no": page.page_no})

        if images:
            _safe_emit(
                on_progress,
                "extract_content:images_extracted",
                {"page_no": "all", "count": len(images)},
            )

        if links:
            _safe_emit(
                on_progress,
                "extract_content:links_detected",
                {"page_no": "all", "count": len(links)},
            )
    else:
        # Use sequential processing (original logic)
        pages = []
        images = []
        tables = []
        links = []

        # Per-page export with images embedded for reliable extraction
        for page_no, _p in yield_pages(doc, selected_pages):
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

                html = flatten_page_html(html, doc, page_no, reflow_enabled=pipeline_options.reflow_columns)
            except Exception:
                # If transform fails for any reason, proceed with original HTML
                pass

            # Extract images (embedded base64)
            html, page_images = _extract_images_from_html(html, page_no, out_assets, f"page-{page_no:04d}")
            images.extend(page_images)
            # Copy referenced images (local paths)
            html, ref_images = _rewrite_and_copy_referenced_images(html, page_no, out_assets, f"page-{page_no:04d}")
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
            if pipeline_options.tables_mode in (TableMode.STRUCTURED, TableMode.AUTO) and hasattr(doc, "pages"):
                # Use new structured table processing
                html, page_tables = _process_tables_with_options(
                    doc, html, page_no, out_assets, pipeline_options, f"page-{page_no:04d}"
                )
            else:
                # Fall back to legacy HTML-only processing
                html, page_tables = _process_tables(
                    html,
                    page_no,
                    out_assets,
                    pipeline_options.tables_mode.value,
                    f"page-{page_no:04d}",
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
                html = apply_ocr_to_page(
                    doc,
                    html,
                    page_no,
                    pipeline_options,
                    ocr_engine,
                    ocr_cache,
                    on_progress,
                    shared_image_cache,
                )

            pages.append(HtmlPage(html=html, page_no=page_no))

    # Replace structured table placeholders with actual HTML before finalizing
    replace_table_placeholders_in_pages(pages, tables)

    # Apply captions to images if picture descriptions are enabled
    if images and pipeline_options.picture_descriptions:
        apply_captions_to_images(images, out_assets, pipeline_options, caption_engine, caption_cache, on_progress)

        # Update HTML img tags with captions
        from pdf2foundry.ingest.caption_html import update_html_with_captions

        update_html_with_captions(pages, images)

    # Log cache metrics if shared cache was used
    if shared_image_cache is not None:
        metrics = shared_image_cache.get_metrics()
        logger.debug(
            "Image cache metrics: page_hits=%d page_misses=%d (%.1f%% hit rate), "
            "region_hits=%d region_misses=%d (%.1f%% hit rate), rasterize_calls=%d",
            metrics["page_hits"],
            metrics["page_misses"],
            metrics["page_hit_rate"] * 100,
            metrics["region_hits"],
            metrics["region_misses"],
            metrics["region_hit_rate"] * 100,
            metrics["rasterize_calls"],
        )

    _safe_emit(
        on_progress,
        "extract_content:success",
        {"pages": len(pages), "images": len(images), "tables": len(tables)},
    )

    return ParsedContent(pages=pages, images=images, tables=tables, links=links, assets_dir=out_assets)
