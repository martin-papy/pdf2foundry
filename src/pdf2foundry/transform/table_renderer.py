"""HTML table rendering for structured tables.

This module provides functionality to convert StructuredTable objects into
semantic HTML markup with proper thead/tbody structure, colspan/rowspan
attributes, and data-bbox positioning information.
"""

from __future__ import annotations

import html
import re
from typing import Any

from pdf2foundry.model.content import StructuredTable, TableContent


def render_structured_table_html(table: StructuredTable) -> str:
    """Convert a StructuredTable to semantic HTML markup.

    Args:
        table: StructuredTable instance with rows, cells, and metadata

    Returns:
        HTML string with proper <table>, <thead>, <tbody> structure

    The generated HTML includes:
    - data-bbox attribute with table bounding box coordinates
    - <caption> element if table.caption is present
    - <thead> with header cells (is_header=True) from first row only
    - <tbody> with remaining rows and non-header cells from first row
    - colspan/rowspan attributes when cell spans > 1
    - Properly escaped cell text content
    """
    # Format bbox as comma-separated coordinates
    bbox_attr = f"{table.bbox.x},{table.bbox.y},{table.bbox.w},{table.bbox.h}"

    # Start table with data-bbox attribute
    parts = [f'<table data-bbox="{bbox_attr}">']

    # Add caption if present
    if table.caption:
        escaped_caption = html.escape(table.caption)
        parts.append(f"<caption>{escaped_caption}</caption>")

    # Process first row for thead (header cells only)
    if table.rows:
        first_row = table.rows[0]
        header_cells = [cell for cell in first_row if cell.is_header]

        if header_cells:
            parts.append("<thead>")
            parts.append("<tr>")
            for cell in header_cells:
                cell_html = _render_cell_html(cell, tag="th")
                parts.append(cell_html)
            parts.append("</tr>")
            parts.append("</thead>")

    # Process all rows for tbody
    if table.rows:
        parts.append("<tbody>")

        for row_idx, row in enumerate(table.rows):
            parts.append("<tr>")

            if row_idx == 0:
                # First row: include only non-header cells
                for cell in row:
                    if not cell.is_header:
                        cell_html = _render_cell_html(cell, tag="td")
                        parts.append(cell_html)
            else:
                # Subsequent rows: include all cells as td
                for cell in row:
                    cell_html = _render_cell_html(cell, tag="td")
                    parts.append(cell_html)

            parts.append("</tr>")

        parts.append("</tbody>")

    parts.append("</table>")

    return "".join(parts)


def _render_cell_html(cell: Any, tag: str = "td") -> str:
    """Render a single table cell as HTML.

    Args:
        cell: TableCell instance with text, spans, and metadata
        tag: HTML tag to use ("td" or "th")

    Returns:
        HTML string for the cell with proper attributes
    """
    # Escape cell text content
    escaped_text = html.escape(cell.text)

    # Build attributes list
    attrs = []

    # Add colspan if > 1
    if cell.col_span > 1:
        attrs.append(f'colspan="{cell.col_span}"')

    # Add rowspan if > 1
    if cell.row_span > 1:
        attrs.append(f'rowspan="{cell.row_span}"')

    # Combine attributes
    attr_str = " " + " ".join(attrs) if attrs else ""

    return f"<{tag}{attr_str}>{escaped_text}</{tag}>"


def replace_structured_table_placeholders(html: str, tables: list[TableContent]) -> str:
    """Replace structured table placeholder comments with actual HTML tables.

    Args:
        html: HTML content containing <!-- structured table N --> placeholders
        tables: List of TableContent objects, some with kind="structured"

    Returns:
        HTML with placeholders replaced by rendered table markup

    This function:
    - Finds placeholders matching <!-- structured table {counter} -->
    - Replaces each with rendered HTML for the corresponding structured table
    - Leaves non-structured table placeholders unchanged
    - Preserves all other HTML content exactly
    """
    # Extract structured tables in order
    structured_tables = [t for t in tables if t.kind == "structured" and t.structured_table is not None]

    if not structured_tables:
        # No structured tables to replace
        return html

    # Pattern to match structured table placeholders
    # Matches: <!-- structured table 1 --> or <!--structured table 2--> etc.
    pattern = re.compile(r"<!--\s*structured\s+table\s+(\d+)\s*-->", re.IGNORECASE)

    def replace_placeholder(match: re.Match[str]) -> str:
        """Replace a single placeholder with rendered table HTML."""
        counter_str = match.group(1)
        try:
            # Convert to 0-based index (placeholders are 1-based)
            table_index = int(counter_str) - 1

            if 0 <= table_index < len(structured_tables):
                table_content = structured_tables[table_index]
                if table_content.structured_table is not None:
                    return render_structured_table_html(table_content.structured_table)
        except (ValueError, IndexError):
            pass

        # If we can't find/render the table, leave placeholder unchanged
        return match.group(0)

    return pattern.sub(replace_placeholder, html)
