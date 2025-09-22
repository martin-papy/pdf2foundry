"""Layout detection and flattening utilities.

For v1 we implement conservative multi-column detection with robust fallbacks,
and return HTML unchanged while logging a warning when multi-column is detected.
This sets up the plumbing for future, deeper reflow if/when needed.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

logger = logging.getLogger(__name__)


def _get_page_blocks(doc, page_no: int) -> Sequence[object]:  # type: ignore[no-untyped-def]
    """Best-effort retrieval of block objects for a given page.

    Tries common docling interfaces across versions; returns an empty sequence
    if not available.
    """

    # Common: doc.pages[page_index].blocks
    pages = getattr(doc, "pages", None)
    if pages and 1 <= page_no <= len(pages):
        page = pages[page_no - 1]
        blocks = getattr(page, "blocks", None)
        if blocks:
            return list(blocks)

    # Fallback: doc.get_blocks(page_no)
    get_blocks = getattr(doc, "get_blocks", None)
    if callable(get_blocks):
        try:
            blocks = get_blocks(page_no)
            if blocks:
                return list(blocks)
        except Exception:
            pass

    return []


def _block_x_center(block: object) -> float | None:
    """Try to compute the horizontal center of a block using its bbox."""

    bbox = getattr(block, "bbox", None) or getattr(block, "bounding_box", None)
    if not bbox:
        # Sometimes bbox may be an object with attributes x0/x1
        x0 = getattr(block, "x0", None)
        x1 = getattr(block, "x1", None)
        if isinstance(x0, int | float) and isinstance(x1, int | float):
            return (float(x0) + float(x1)) / 2.0
        return None

    # bbox could be a tuple (x0, y0, x1, y1) or an object with fields
    if isinstance(bbox, list | tuple) and len(bbox) >= 4:
        x0, _, x1, _ = bbox[:4]
        try:
            return (float(x0) + float(x1)) / 2.0
        except Exception:
            return None

    x0 = getattr(bbox, "x0", None)
    x1 = getattr(bbox, "x1", None)
    if isinstance(x0, int | float) and isinstance(x1, int | float):
        return (float(x0) + float(x1)) / 2.0

    return None


def detect_column_count(doc, page_no: int) -> int:  # type: ignore[no-untyped-def]
    """Detect an approximate number of text columns on a page.

    Heuristic: compute x-centers of blocks and look for bi-modality. If two
    clusters separated by a noticeable gap exist, return 2; otherwise 1.
    """

    blocks = _get_page_blocks(doc, page_no)
    if len(blocks) < 8:
        return 1

    xs = [xc for b in blocks if (xc := _block_x_center(b)) is not None]
    if len(xs) < 8:
        return 1

    xs_sorted = sorted(xs)
    # Gap-based two-cluster detection: find the maximal gap and split
    max_gap = 0.0
    split_idx = -1
    for i in range(1, len(xs_sorted)):
        gap = xs_sorted[i] - xs_sorted[i - 1]
        if gap > max_gap:
            max_gap = gap
            split_idx = i

    if split_idx <= 0 or split_idx >= len(xs_sorted) - 1:
        return 1

    left = xs_sorted[:split_idx]
    right = xs_sorted[split_idx:]

    # If the clusters are relatively balanced and the gap is significant
    # compared to their spread, infer 2 columns.
    def _spread(vals: list[float]) -> float:
        return (max(vals) - min(vals)) if vals else 0.0

    if not left or not right:
        return 1

    gap_score = max_gap / max(1.0, _spread(xs_sorted))
    balance = min(len(left), len(right)) / max(1, len(xs_sorted))

    if gap_score >= 0.3 and balance >= 0.3:
        return 2

    return 1


def flatten_page_html(
    html: str,
    doc: Any,
    page_no: int,
    *,
    reflow_enabled: bool = False,
    page_width: float | None = None,
) -> str:
    """Return a linearized HTML for a multi-column page.

    For v1, we rely on Docling to produce reasonable reading order. When a
    multi-column layout is detected, we log a warning to inform the user that
    we may need deeper reflow in future iterations.

    Args:
        html: HTML content from Docling
        doc: Docling document object
        page_no: 1-based page number
        reflow_enabled: Enable experimental multi-column reflow
        page_width: Page width in points (defaults to 612 for US Letter)

    Returns:
        HTML content, potentially reordered if reflow is enabled
    """
    # Use default US Letter width if not provided
    if page_width is None:
        page_width = 612.0  # US Letter width in points

    columns = detect_column_count(doc, page_no)
    if columns >= 2:
        if reflow_enabled:
            logger.info(
                "Multi-column layout detected on page %d; applying experimental reflow.",
                page_no,
            )

            # Get page blocks and apply reflow
            blocks = _get_page_blocks(doc, page_no)
            if blocks:
                try:
                    from pdf2foundry.transform.reflow import reflow_columns

                    reordered_blocks = reflow_columns(list(blocks), page_width)
                    if reordered_blocks != list(blocks):
                        logger.debug("Reordered %d blocks on page %d", len(reordered_blocks), page_no)
                        # Note: For now, we return the original HTML since we don't have
                        # a way to reconstruct HTML from reordered blocks. This sets up
                        # the infrastructure for future HTML reconstruction.
                        return html
                except Exception as e:
                    logger.warning("Column reflow failed on page %d: %s", page_no, e)

            return html
        else:
            logger.warning(
                "Multi-column layout detected on page %d; using Docling reading order to flatten.",
                page_no,
            )
            # TODO: future iterations may reorder blocks within HTML by column
            return html

    return html
