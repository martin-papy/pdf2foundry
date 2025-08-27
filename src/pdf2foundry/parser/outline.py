from __future__ import annotations

import logging

from ..types import OutlineItem, PdfDocumentLike, PdfPagesLike

logger = logging.getLogger(__name__)


def extract_outline(
    document: PdfDocumentLike, *, log: logging.Logger | None = None
) -> list[OutlineItem]:
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

        page_index = max(0, page_obj - 1)
        items.append(OutlineItem(level=level_obj, title=title_obj.strip(), page_index=page_index))

    return items


def detect_headings_heuristic(document: PdfPagesLike, *, max_levels: int = 3) -> list[OutlineItem]:
    def _normalize_span_text(text: str) -> str:
        return " ".join(text.split()).strip()

    all_spans: list[tuple[int, float, str]] = []
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

    sizes_desc = sorted({size for (_, size, _) in all_spans}, reverse=True)
    top_sizes = sizes_desc[:max_levels]
    size_to_level: dict[float, int] = {size: idx + 1 for idx, size in enumerate(top_sizes)}

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
