from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypedDict, cast

logger = logging.getLogger(__name__)


class PdfDocumentLike(Protocol):
    """Minimal protocol for the PyMuPDF document object we rely on."""

    def get_toc(self, simple: bool = ...) -> list[list[object]]:  # pragma: no cover - typing
        ...


class PdfDocumentWithImages(Protocol):
    def extract_image(self, xref: int) -> dict[str, Any]:  # pragma: no cover - typing
        ...


class PdfPageLike(Protocol):
    def get_text(self, option: str) -> PageTextDict:  # pragma: no cover - typing
        ...

    def get_links(self) -> list[RawLinkDict]:  # pragma: no cover - typing
        ...

    def get_images(self, full: bool = ...) -> list[object]:  # pragma: no cover - typing
        ...


class PdfPagesLike(Protocol):
    def __len__(self) -> int:  # pragma: no cover - typing
        ...

    def __getitem__(self, index: int) -> PdfPageLike:  # pragma: no cover - typing
        ...


class SpanDict(TypedDict):
    text: str
    size: float


class LineDict(TypedDict):
    spans: list[SpanDict]


class BlockDict(TypedDict, total=False):
    lines: list[LineDict]
    type: int
    bbox: list[float]


class PageTextDict(TypedDict):
    blocks: list[BlockDict]


class RawLinkDict(TypedDict, total=False):
    # As returned by PyMuPDF page.get_links(): may contain 'uri' for external links
    # or 'page' for internal links; 'from' is the source rectangle
    uri: str
    page: int
    from_: list[float]


@dataclass(frozen=True)
class OutlineItem:
    """Represents a single outline/bookmark entry.

    - level: 1-based hierarchical level
    - title: text label of the entry
    - page_index: 0-based page index within the document
    """

    level: int
    title: str
    page_index: int


@dataclass(frozen=True)
class LinkAnnotation:
    page_index: int
    bbox: tuple[float, float, float, float]
    uri: str | None
    target_page_index: int | None


@dataclass(frozen=True)
class PageContent:
    page_index: int
    text_lines: list[str]
    links: list[LinkAnnotation]


@dataclass(frozen=True)
class ImageReference:
    page_index: int
    xref: int
    width: int | None
    height: int | None
    name: str | None
    ext: str | None


@dataclass(frozen=True)
class TableCandidate:
    page_index: int
    bbox: tuple[float, float, float, float]


def extract_image_bytes(document: PdfDocumentWithImages, xref: int) -> tuple[bytes, str]:
    """Return image bytes and extension for a given xref using PyMuPDF-like API.

    The returned extension is lowercased and defaults to 'bin' if unknown.
    """

    info = document.extract_image(int(xref))
    data = info.get("image", b"")
    if not isinstance(data, bytes | bytearray):
        data = b""
    ext = info.get("ext", "bin")
    if not isinstance(ext, str) or not ext:
        ext = "bin"
    return bytes(data), ext.lower()


def generate_deterministic_image_name(
    mod_id: str, page_index: int, image_seq: int, ext: str
) -> str:
    """Generate a deterministic image filename based on stable context.

    Uses the project's deterministic ID helper to ensure stability across runs.
    """

    from .ids import compute_deterministic_id

    chapter_key = f"page-{page_index:04d}"
    section_key = f"image-{image_seq:04d}"
    suffix = compute_deterministic_id(mod_id, chapter_key, section_key)[:8]
    safe_ext = (ext or "bin").lower()
    return f"p{page_index:04d}_i{image_seq:04d}_{suffix}.{safe_ext}"


def save_images(
    document: PdfDocumentWithImages,
    image_refs: list[ImageReference],
    assets_dir: Path,
    mod_id: str,
) -> list[tuple[ImageReference, Path, str]]:
    """Save images to assets_dir and return tuples of (ref, file_path, module_rel_path).

    module_rel_path uses the Foundry convention: modules/<mod-id>/assets/<filename>.
    """

    assets_dir.mkdir(parents=True, exist_ok=True)
    results: list[tuple[ImageReference, Path, str]] = []
    # Maintain a per-page sequence to ensure stable indices even if xrefs reorder
    per_page_counts: dict[int, int] = {}

    for ref in image_refs:
        seq = per_page_counts.get(ref.page_index, 0) + 1
        per_page_counts[ref.page_index] = seq

        data, ext = extract_image_bytes(document, ref.xref)
        filename = generate_deterministic_image_name(mod_id, ref.page_index, seq, ext)
        dest = assets_dir / filename
        dest.write_bytes(data)
        module_rel = f"modules/{mod_id}/assets/{filename}"
        results.append((ref, dest, module_rel))

    return results


def open_pdf(path: Path) -> PdfDocumentLike:
    """Open a PDF with PyMuPDF and return the document object.

    Importing fitz inside this function avoids import costs for callers that
    don't need PDF capabilities (and eases testing).
    """

    import fitz

    return cast(PdfDocumentLike, fitz.open(str(path)))


def extract_outline(
    document: PdfDocumentLike, *, log: logging.Logger | None = None
) -> list[OutlineItem]:
    """Extract the PDF outline (bookmarks) into a normalized list.

    If the document has no outline, a warning is logged per policy and an empty
    list is returned. Page numbers reported by PyMuPDF are 1-based; we convert
    them to 0-based indices.
    """

    active_logger = log or logger

    raw_toc: list[list[object]] = document.get_toc(simple=True)
    if not raw_toc:
        active_logger.warning(
            "No bookmarks found; will fall back to heading heuristic in later stages."
        )
        return []

    items: list[OutlineItem] = []
    for entry in raw_toc:
        if len(entry) < 3:
            # Unexpected shape; skip with a debug note
            active_logger.debug("Skipping malformed TOC entry: %r", entry)
            continue

        level_obj, title_obj, page_obj = entry[0], entry[1], entry[2]
        if (
            not isinstance(level_obj, int)
            or not isinstance(title_obj, str)
            or not isinstance(page_obj, int)
        ):
            active_logger.debug("Skipping TOC entry with wrong types: %r", entry)
            continue

        # PyMuPDF returns 1-based page numbers; convert to 0-based index
        page_index = max(0, page_obj - 1)
        items.append(OutlineItem(level=level_obj, title=title_obj.strip(), page_index=page_index))

    return items


def detect_headings_heuristic(document: PdfPagesLike, *, max_levels: int = 3) -> list[OutlineItem]:
    """Detect headings when bookmarks are missing using simple font-size heuristics.

    Strategy:
    - Collect all text spans with their font sizes across pages (from get_text("dict")).
    - Determine the top-N distinct font sizes globally (N = max_levels).
    - Treat spans whose size matches these top sizes as headings; map size rank to level (1..N).
    - For simplicity, pick the largest heading candidate per page to avoid duplicates.
    """

    all_spans: list[tuple[int, float, str]] = []  # (page_index, size, text)
    num_pages = len(document)
    for page_index in range(num_pages):
        page = document[page_index]
        page_dict = page.get_text("dict")
        for block in page_dict.get("blocks", []):
            for line in block.get("lines", []) if isinstance(block.get("lines"), list) else []:
                for span in line.get("spans", []):
                    text = _normalize_span_text(span.get("text", ""))
                    size_obj = span.get("size")
                    if not text or not isinstance(size_obj, int | float):
                        continue
                    all_spans.append((page_index, float(size_obj), text))

    if not all_spans:
        return []

    # Global size ranking
    sizes_desc = sorted({size for (_, size, _) in all_spans}, reverse=True)
    top_sizes = sizes_desc[:max_levels]
    size_to_level: dict[float, int] = {size: idx + 1 for idx, size in enumerate(top_sizes)}

    # One (largest) heading per page to keep structure simple
    per_page_best: dict[int, tuple[float, str]] = {}
    for page_index, size, text in all_spans:
        if size not in size_to_level:
            continue
        prev = per_page_best.get(page_index)
        if prev is None or size > prev[0]:
            per_page_best[page_index] = (size, text)

    results: list[OutlineItem] = []
    for page_index in sorted(per_page_best.keys()):
        size, text = per_page_best[page_index]
        level = size_to_level.get(size, max_levels)
        results.append(OutlineItem(level=level, title=text, page_index=page_index))

    return results


def _normalize_span_text(text: str) -> str:
    return " ".join(text.split()).strip()


def extract_page_content(document: PdfPagesLike) -> list[PageContent]:
    """Extract text (in reading order) and link annotations for each page.

    - Linearizes multi-column by sorting blocks by (y0, x0)
    - Concatenates spans within lines and lines within blocks into simple lines
    - Collects external (uri) and internal (page) links with their rectangles
    """

    results: list[PageContent] = []
    for page_index in range(len(document)):
        page = document[page_index]
        page_dict = page.get_text("dict")

        # Sort text blocks by top-left coordinate
        ordered_blocks: list[BlockDict] = []
        for block in page_dict.get("blocks", []):
            if block.get("type", 0) != 0:
                continue
            ordered_blocks.append(block)
        ordered_blocks.sort(
            key=lambda b: (
                float(b.get("bbox", [0.0, 0.0])[1]),
                float(b.get("bbox", [0.0, 0.0, 0.0, 0.0])[0]),
            )
        )

        text_lines: list[str] = []
        for block in ordered_blocks:
            lines = block.get("lines", [])
            for line in lines:
                spans = line.get("spans", [])
                merged = " ".join(
                    _normalize_span_text(span.get("text", ""))
                    for span in spans
                    if _normalize_span_text(span.get("text", ""))
                )
                if merged:
                    text_lines.append(merged)

        # Collect links
        raw_links = page.get_links()
        links: list[LinkAnnotation] = []
        for link in raw_links:
            rect_seq = cast(list[float], link.get("from_") or link.get("from") or [])
            bbox = (
                float(rect_seq[0]) if len(rect_seq) > 0 else 0.0,
                float(rect_seq[1]) if len(rect_seq) > 1 else 0.0,
                float(rect_seq[2]) if len(rect_seq) > 2 else 0.0,
                float(rect_seq[3]) if len(rect_seq) > 3 else 0.0,
            )
            uri = link.get("uri") if isinstance(link.get("uri"), str) else None
            target_page = link.get("page") if isinstance(link.get("page"), int) else None
            links.append(
                LinkAnnotation(
                    page_index=page_index,
                    bbox=bbox,
                    uri=uri,
                    target_page_index=target_page,
                )
            )

        results.append(PageContent(page_index=page_index, text_lines=text_lines, links=links))

    return results


def extract_images(document: PdfPagesLike) -> list[ImageReference]:
    """Collect references to embedded images by xref and basic metadata.

    Caller can later use the document object (fitz) to extract image data by xref
    and write to disk as-is, preserving original format/resolution.
    """

    images: list[ImageReference] = []
    for page_index in range(len(document)):
        page = document[page_index]
        try:
            raw_list = page.get_images(full=True)
        except Exception:  # pragma: no cover - passthrough safety
            raw_list = []
        for item in raw_list:
            # PyMuPDF returns tuples; common tuple fields include:
            # (xref, smask, width, height, bpc, colorspace, alt. name, name)
            # We attempt to read by position with fallbacks.
            seq = cast(tuple[Any, ...], item)
            xref = int(seq[0]) if len(seq) > 0 else -1
            width = int(seq[2]) if len(seq) > 2 else None
            height = int(seq[3]) if len(seq) > 3 else None
            name = str(seq[7]) if len(seq) > 7 else None
            # ext is not directly known here; derive later when extracting
            images.append(
                ImageReference(
                    page_index=page_index,
                    xref=xref,
                    width=width,
                    height=height,
                    name=name,
                    ext=None,
                )
            )

    return images
