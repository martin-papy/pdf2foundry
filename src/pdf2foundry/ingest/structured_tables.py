"""Structured table extraction from Docling documents.

This module provides functionality to extract structured table information
from Docling documents, including cell-level data, bounding boxes, and
confidence scores.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from pdf2foundry.ingest.error_handling import ErrorContext, ErrorManager
from pdf2foundry.model.content import BBox, StructuredTable, TableCell
from pdf2foundry.model.id_utils import sha1_16_hex
from pdf2foundry.model.pipeline_options import PdfPipelineOptions


def _iter_structured_tables(doc: Any, page_index: int | None = None) -> Iterable[dict[str, Any]]:
    """Extract structured table information from a Docling document.

    Args:
        doc: Docling document with structured table data
        page_index: Optional page filter (1-based), None for all pages

    Yields:
        Dict with table information: page_no, table_id, bbox, confidence, cells
    """
    try:
        pages = getattr(doc, "pages", [])
        table_store = getattr(doc, "table_store", None) or getattr(doc, "tables", None)

        for p_idx, page in enumerate(pages, start=1):
            # Skip pages not matching filter
            if page_index is not None and p_idx != page_index:
                continue

            items = getattr(page, "items", []) or getattr(page, "elements", [])

            for item in items:
                # Check if this is a table item
                cls_name = item.__class__.__name__.lower()
                is_table = (cls_name == "table") or (getattr(item, "type", None) == "table")

                # Handle TableRef case - resolve from table store
                if not is_table and "tableref" in cls_name and table_store is not None:
                    ref_id = getattr(item, "id", None) or getattr(item, "ref_id", None)
                    if ref_id:
                        item = table_store.get(ref_id)
                        is_table = item is not None

                if not is_table or item is None:
                    continue

                # Extract table metadata
                table_id = getattr(item, "id", None) or f"table_{p_idx}_{len(list(items))}"
                bbox = getattr(item, "bbox", None) or getattr(item, "quad", None)
                confidence = getattr(item, "confidence", None)

                # Extract cells
                cells = []
                for cell in getattr(item, "cells", []):
                    cells.append(
                        {
                            "row": getattr(cell, "row", None),
                            "col": getattr(cell, "col", None),
                            "rowspan": getattr(cell, "rowspan", 1),
                            "colspan": getattr(cell, "colspan", 1),
                            "text": getattr(cell, "text", ""),
                            "bbox": getattr(cell, "bbox", None) or getattr(cell, "quad", None),
                            "confidence": getattr(cell, "confidence", None),
                        }
                    )

                yield {
                    "page_no": p_idx,
                    "table_id": table_id,
                    "bbox": bbox,
                    "confidence": confidence,
                    "cells": cells,
                }

    except Exception as e:
        # Use centralized error handling
        context = ErrorContext(source_module="structured_tables", page=page_index)
        error_mgr = ErrorManager(context)
        error_mgr.warn(
            "DL-TB001",
            f"Failed to extract structured tables from Docling document: {e}",
            extra={"error_type": "extraction_failed"},
            exception=e,
        )


def _extract_structured_tables(doc: Any, page_index: int, region: BBox | None = None) -> list[StructuredTable]:
    """Extract structured tables from a Docling document for a specific page.

    Args:
        doc: Docling document with structured table data
        page_index: Page number (1-based)
        region: Optional region filter for table overlap

    Returns:
        List of StructuredTable instances found on the page
    """
    logger = logging.getLogger(__name__)
    structured_tables = []

    try:
        for table_data in _iter_structured_tables(doc, page_index):
            # Convert Docling table data to StructuredTable
            table_bbox = table_data["bbox"]
            if table_bbox is None:
                logger.warning("Table on page %d has no bounding box, skipping", page_index)
                continue

            # Convert bbox format if needed (handle different Docling bbox formats)
            if hasattr(table_bbox, "x0"):  # BBox-like object
                bbox = BBox(
                    x=float(table_bbox.x0),
                    y=float(table_bbox.y0),
                    w=float(table_bbox.x1 - table_bbox.x0),
                    h=float(table_bbox.y1 - table_bbox.y0),
                )
            elif isinstance(table_bbox, list | tuple) and len(table_bbox) >= 4:
                # [x0, y0, x1, y1] format
                bbox = BBox(
                    x=float(table_bbox[0]),
                    y=float(table_bbox[1]),
                    w=float(table_bbox[2] - table_bbox[0]),
                    h=float(table_bbox[3] - table_bbox[1]),
                )
            else:
                logger.warning("Unsupported bbox format for table on page %d: %s", page_index, table_bbox)
                continue

            # Apply region filter if specified
            if region is not None:
                # Calculate overlap between table bbox and region
                overlap = _calculate_bbox_overlap(bbox, region)
                if overlap < 0.1:  # Less than 10% overlap, skip
                    continue

            # Convert cells
            rows: dict[int, dict[int, TableCell]] = {}
            max_row = 0
            max_col = 0

            for cell_data in table_data["cells"]:
                row = cell_data["row"]
                col = cell_data["col"]

                if row is None or col is None:
                    continue

                # Convert cell bbox
                cell_bbox_data = cell_data["bbox"]
                if cell_bbox_data:
                    if hasattr(cell_bbox_data, "x0"):
                        cell_bbox = BBox(
                            x=float(cell_bbox_data.x0),
                            y=float(cell_bbox_data.y0),
                            w=float(cell_bbox_data.x1 - cell_bbox_data.x0),
                            h=float(cell_bbox_data.y1 - cell_bbox_data.y0),
                        )
                    elif isinstance(cell_bbox_data, list | tuple) and len(cell_bbox_data) >= 4:
                        cell_bbox = BBox(
                            x=float(cell_bbox_data[0]),
                            y=float(cell_bbox_data[1]),
                            w=float(cell_bbox_data[2] - cell_bbox_data[0]),
                            h=float(cell_bbox_data[3] - cell_bbox_data[1]),
                        )
                    else:
                        cell_bbox = BBox(x=0.0, y=0.0, w=0.0, h=0.0)
                else:
                    cell_bbox = BBox(x=0.0, y=0.0, w=0.0, h=0.0)

                cell = TableCell(
                    text=cell_data["text"],
                    row_span=max(1, cell_data["rowspan"]),
                    col_span=max(1, cell_data["colspan"]),
                    bbox=cell_bbox,
                    is_header=False,  # TODO: Detect header cells based on position or styling
                )

                if row not in rows:
                    rows[row] = {}
                rows[row][col] = cell

                max_row = max(max_row, row + cell.row_span - 1)
                max_col = max(max_col, col + cell.col_span - 1)

            # Convert to 2D array format
            table_rows = []
            for r in range(max_row + 1):
                row_cells = []
                for c in range(max_col + 1):
                    if r in rows and c in rows[r]:
                        row_cells.append(rows[r][c])
                    else:
                        # Empty cell placeholder
                        row_cells.append(
                            TableCell(
                                text="",
                                row_span=1,
                                col_span=1,
                                bbox=BBox(x=0.0, y=0.0, w=0.0, h=0.0),
                                is_header=False,
                            )
                        )
                table_rows.append(row_cells)

            # Generate deterministic ID
            id_seed = f"table_{page_index}_{table_data['table_id']}"
            table_id = sha1_16_hex(id_seed)

            # Create StructuredTable
            structured_table = StructuredTable(
                id=table_id,
                bbox=bbox,
                rows=table_rows,
                caption=None,  # TODO: Extract caption if available
                meta={
                    "source_page": page_index,
                    "confidence": table_data["confidence"],
                    "docling_table_id": table_data["table_id"],
                },
            )

            structured_tables.append(structured_table)
            logger.debug(
                "Extracted structured table on page %d: id=%s, confidence=%s, cells=%d",
                page_index,
                table_id,
                table_data["confidence"],
                len(table_data["cells"]),
            )

    except Exception as e:
        # Use centralized error handling
        context = ErrorContext(source_module="structured_tables", page=page_index)
        error_mgr = ErrorManager(context)
        error_mgr.warn(
            "DL-TB002",
            f"Failed to extract structured tables from page {page_index}: {e}",
            extra={"error_type": "page_extraction_failed"},
            exception=e,
        )

    return structured_tables


def _calculate_bbox_overlap(bbox1: BBox, bbox2: BBox) -> float:
    """Calculate the overlap ratio between two bounding boxes.

    Args:
        bbox1: First bounding box
        bbox2: Second bounding box

    Returns:
        Overlap ratio (intersection area / bbox1 area), 0.0 to 1.0
    """
    # Calculate intersection
    x_left = max(bbox1.x, bbox2.x)
    y_top = max(bbox1.y, bbox2.y)
    x_right = min(bbox1.x + bbox1.w, bbox2.x + bbox2.w)
    y_bottom = min(bbox1.y + bbox1.h, bbox2.y + bbox2.h)

    if x_right <= x_left or y_bottom <= y_top:
        return 0.0  # No intersection

    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    bbox1_area = bbox1.w * bbox1.h

    if bbox1_area <= 0:
        return 0.0

    return intersection_area / bbox1_area


def try_structured_table(
    doc: Any, page_index: int, region: BBox | None, options: PdfPipelineOptions
) -> tuple[StructuredTable | None, float]:
    """Attempt to extract a structured table from the specified region.

    Args:
        doc: Docling document with structured table data
        page_index: Page number (1-based)
        region: Optional region to search for tables
        options: Pipeline options with table configuration

    Returns:
        Tuple of (StructuredTable or None, confidence score 0.0-1.0)
    """
    logger = logging.getLogger(__name__)

    # Extract all structured tables from the page
    structured_tables = _extract_structured_tables(doc, page_index, region)

    if not structured_tables:
        logger.debug("No structured tables found on page %d", page_index)
        return None, 0.0

    # Find the best table based on confidence and overlap
    best_table = None
    best_confidence = 0.0

    for table in structured_tables:
        # Get base confidence from table metadata
        base_conf = table.meta.get("confidence")
        base_conf = 0.5 if base_conf is None else float(base_conf)

        # Calculate mean cell confidence if available
        cell_confidences = []
        for row in table.rows:
            for _cell in row:
                # Cell confidence would be in cell metadata if available
                # For now, use base confidence as fallback
                cell_confidences.append(base_conf)

        mean_cell_conf = sum(cell_confidences) / len(cell_confidences) if cell_confidences else base_conf

        # Combine confidences (70% table, 30% cells)
        combined_conf = 0.7 * base_conf + 0.3 * mean_cell_conf

        # Apply overlap scoring if region is specified
        if region is not None:
            overlap_score = _calculate_bbox_overlap(table.bbox, region)
            final_confidence = combined_conf * overlap_score
        else:
            final_confidence = combined_conf

        # Clamp to [0, 1]
        final_confidence = max(0.0, min(1.0, final_confidence))

        if final_confidence > best_confidence:
            best_table = table
            best_confidence = final_confidence

    if best_table:
        logger.debug(
            "Selected structured table on page %d: confidence=%.3f, bbox=(%s)",
            page_index,
            best_confidence,
            f"{best_table.bbox.x:.1f},{best_table.bbox.y:.1f},{best_table.bbox.w:.1f},{best_table.bbox.h:.1f}",
        )

    return best_table, best_confidence


__all__ = [
    "_calculate_bbox_overlap",
    "_extract_structured_tables",
    "try_structured_table",
]
