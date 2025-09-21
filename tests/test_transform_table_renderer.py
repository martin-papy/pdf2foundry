"""Tests for HTML table rendering functionality."""

from __future__ import annotations

from pdf2foundry.model.content import BBox, StructuredTable, TableCell, TableContent
from pdf2foundry.transform.table_renderer import (
    render_structured_table_html,
    replace_structured_table_placeholders,
)


class TestRenderStructuredTableHtml:
    """Test rendering StructuredTable to HTML."""

    def test_basic_table_rendering(self) -> None:
        """Test rendering a basic table with no spans or headers."""
        bbox = BBox(x=10.5, y=20.0, w=100.0, h=50.0)
        cell1 = TableCell(text="Cell 1", bbox=BBox(x=10, y=20, w=50, h=25))
        cell2 = TableCell(text="Cell 2", bbox=BBox(x=60, y=20, w=50, h=25))

        table = StructuredTable(
            id="test-table",
            bbox=bbox,
            rows=[[cell1, cell2]],
        )

        html = render_structured_table_html(table)

        # Check table structure
        assert '<table data-bbox="10.5,20.0,100.0,50.0">' in html
        assert "<tbody>" in html
        assert "</tbody>" in html
        assert "<tr>" in html
        assert "</tr>" in html
        assert "<td>Cell 1</td>" in html
        assert "<td>Cell 2</td>" in html
        assert "</table>" in html

        # Should not have thead since no header cells
        assert "<thead>" not in html
        assert "<th>" not in html

    def test_table_with_caption(self) -> None:
        """Test rendering table with caption."""
        bbox = BBox(x=0, y=0, w=100, h=50)
        cell = TableCell(text="Data", bbox=BBox(x=0, y=0, w=100, h=50))

        table = StructuredTable(
            id="captioned-table",
            bbox=bbox,
            rows=[[cell]],
            caption="Sample Table Caption",
        )

        html = render_structured_table_html(table)

        assert "<caption>Sample Table Caption</caption>" in html

    def test_table_with_header_cells(self) -> None:
        """Test rendering table with header cells in first row."""
        bbox = BBox(x=0, y=0, w=200, h=100)

        # First row with mixed header and non-header cells
        header_cell = TableCell(text="Header", bbox=BBox(x=0, y=0, w=100, h=25), is_header=True)
        regular_cell = TableCell(text="Regular", bbox=BBox(x=100, y=0, w=100, h=25))

        # Second row with regular cells
        data1 = TableCell(text="Data 1", bbox=BBox(x=0, y=25, w=100, h=25))
        data2 = TableCell(text="Data 2", bbox=BBox(x=100, y=25, w=100, h=25))

        table = StructuredTable(
            id="header-table",
            bbox=bbox,
            rows=[[header_cell, regular_cell], [data1, data2]],
        )

        html = render_structured_table_html(table)

        # Should have thead with only header cells
        assert "<thead>" in html
        assert "<th>Header</th>" in html
        assert "</thead>" in html

        # Should have tbody with non-header cells from first row and all cells from other rows
        assert "<tbody>" in html
        assert "<td>Regular</td>" in html  # Non-header cell from first row
        assert "<td>Data 1</td>" in html  # All cells from second row
        assert "<td>Data 2</td>" in html
        assert "</tbody>" in html

    def test_table_with_colspan_rowspan(self) -> None:
        """Test rendering table with colspan and rowspan attributes."""
        bbox = BBox(x=0, y=0, w=300, h=100)

        # Cell with both colspan and rowspan
        spanned_cell = TableCell(
            text="Spanned Cell",
            bbox=BBox(x=0, y=0, w=200, h=50),
            col_span=2,
            row_span=2,
        )

        # Regular cell
        regular_cell = TableCell(text="Regular", bbox=BBox(x=200, y=0, w=100, h=25))

        table = StructuredTable(
            id="spanned-table",
            bbox=bbox,
            rows=[[spanned_cell, regular_cell]],
        )

        html = render_structured_table_html(table)

        assert '<td colspan="2" rowspan="2">Spanned Cell</td>' in html
        assert "<td>Regular</td>" in html

    def test_html_escaping(self) -> None:
        """Test that cell text is properly HTML-escaped."""
        bbox = BBox(x=0, y=0, w=100, h=50)

        # Cell with HTML-sensitive characters
        cell = TableCell(
            text='<script>alert("xss")</script> & "quotes"',
            bbox=BBox(x=0, y=0, w=100, h=50),
        )

        table = StructuredTable(
            id="escaped-table",
            bbox=bbox,
            rows=[[cell]],
        )

        html = render_structured_table_html(table)

        # Should be properly escaped
        assert (
            "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt; &amp; &quot;quotes&quot;" in html
        )
        # Should not contain unescaped HTML
        assert "<script>" not in html
        assert 'alert("xss")' not in html

    def test_caption_escaping(self) -> None:
        """Test that table caption is properly HTML-escaped."""
        bbox = BBox(x=0, y=0, w=100, h=50)
        cell = TableCell(text="Data", bbox=BBox(x=0, y=0, w=100, h=50))

        table = StructuredTable(
            id="caption-escaped-table",
            bbox=bbox,
            rows=[[cell]],
            caption='<b>Bold</b> & "Special" Caption',
        )

        html = render_structured_table_html(table)

        assert (
            "<caption>&lt;b&gt;Bold&lt;/b&gt; &amp; &quot;Special&quot; Caption</caption>" in html
        )


class TestReplaceStructuredTablePlaceholders:
    """Test replacing structured table placeholders in HTML."""

    def test_no_placeholders(self) -> None:
        """Test HTML with no placeholders remains unchanged."""
        html = "<p>Some content</p><div>More content</div>"
        tables: list[TableContent] = []

        result = replace_structured_table_placeholders(html, tables)

        assert result == html

    def test_no_structured_tables(self) -> None:
        """Test HTML with placeholders but no structured tables."""
        html = "<p>Before</p><!-- structured table 1 --><p>After</p>"
        tables = [
            TableContent(kind="html", page_no=1, html="<table><tr><td>HTML</td></tr></table>"),
            TableContent(kind="image", page_no=1, image_name="table.png"),
        ]

        result = replace_structured_table_placeholders(html, tables)

        # Should remain unchanged since no structured tables
        assert result == html

    def test_single_placeholder_replacement(self) -> None:
        """Test replacing a single structured table placeholder."""
        html = "<p>Before</p><!-- structured table 1 --><p>After</p>"

        # Create a simple structured table
        bbox = BBox(x=0, y=0, w=100, h=50)
        cell = TableCell(text="Test Data", bbox=BBox(x=0, y=0, w=100, h=50))
        structured_table = StructuredTable(id="test", bbox=bbox, rows=[[cell]])

        tables = [
            TableContent(
                kind="structured",
                page_no=1,
                structured_table=structured_table,
            )
        ]

        result = replace_structured_table_placeholders(html, tables)

        # Should replace placeholder with rendered table
        assert "<!-- structured table 1 -->" not in result
        assert '<table data-bbox="0,0,100,50">' in result
        assert "<td>Test Data</td>" in result
        assert "<p>Before</p>" in result
        assert "<p>After</p>" in result

    def test_multiple_placeholder_replacement(self) -> None:
        """Test replacing multiple structured table placeholders."""
        html = """
        <h1>Document</h1>
        <!-- structured table 1 -->
        <p>Between tables</p>
        <!-- structured table 2 -->
        <p>End</p>
        """

        # Create two structured tables
        bbox1 = BBox(x=0, y=0, w=100, h=50)
        cell1 = TableCell(text="Table 1", bbox=BBox(x=0, y=0, w=100, h=50))
        table1 = StructuredTable(id="table1", bbox=bbox1, rows=[[cell1]])

        bbox2 = BBox(x=10, y=10, w=200, h=75)
        cell2 = TableCell(text="Table 2", bbox=BBox(x=10, y=10, w=200, h=75))
        table2 = StructuredTable(id="table2", bbox=bbox2, rows=[[cell2]])

        tables = [
            TableContent(kind="structured", page_no=1, structured_table=table1),
            TableContent(kind="structured", page_no=1, structured_table=table2),
        ]

        result = replace_structured_table_placeholders(html, tables)

        # Should replace both placeholders
        assert "<!-- structured table 1 -->" not in result
        assert "<!-- structured table 2 -->" not in result
        assert '<table data-bbox="0,0,100,50">' in result
        assert '<table data-bbox="10,10,200,75">' in result
        assert "<td>Table 1</td>" in result
        assert "<td>Table 2</td>" in result

    def test_mixed_table_types(self) -> None:
        """Test replacement with mixed structured and non-structured tables."""
        html = """
        <!-- structured table 1 -->
        <p>Text</p>
        <!-- structured table 2 -->
        """

        # Mix of structured and non-structured tables
        bbox = BBox(x=0, y=0, w=100, h=50)
        cell = TableCell(text="Structured", bbox=BBox(x=0, y=0, w=100, h=50))
        structured_table = StructuredTable(id="struct", bbox=bbox, rows=[[cell]])

        tables = [
            TableContent(kind="structured", page_no=1, structured_table=structured_table),
            TableContent(kind="html", page_no=1, html="<table><tr><td>HTML</td></tr></table>"),
        ]

        result = replace_structured_table_placeholders(html, tables)

        # Should only replace the first placeholder (structured table)
        assert "<!-- structured table 1 -->" not in result
        assert "<!-- structured table 2 -->" in result  # No corresponding structured table
        assert '<table data-bbox="0,0,100,50">' in result
        assert "<td>Structured</td>" in result

    def test_placeholder_case_insensitive(self) -> None:
        """Test that placeholder matching is case-insensitive."""
        html = "<!-- STRUCTURED TABLE 1 -->"

        bbox = BBox(x=0, y=0, w=100, h=50)
        cell = TableCell(text="Test", bbox=BBox(x=0, y=0, w=100, h=50))
        structured_table = StructuredTable(id="test", bbox=bbox, rows=[[cell]])

        tables = [TableContent(kind="structured", page_no=1, structured_table=structured_table)]

        result = replace_structured_table_placeholders(html, tables)

        assert "<!-- STRUCTURED TABLE 1 -->" not in result
        assert '<table data-bbox="0,0,100,50">' in result

    def test_placeholder_whitespace_tolerance(self) -> None:
        """Test that placeholder matching tolerates extra whitespace."""
        html = "<!--  structured   table   1  -->"

        bbox = BBox(x=0, y=0, w=100, h=50)
        cell = TableCell(text="Test", bbox=BBox(x=0, y=0, w=100, h=50))
        structured_table = StructuredTable(id="test", bbox=bbox, rows=[[cell]])

        tables = [TableContent(kind="structured", page_no=1, structured_table=structured_table)]

        result = replace_structured_table_placeholders(html, tables)

        assert "<!--  structured   table   1  -->" not in result
        assert '<table data-bbox="0,0,100,50">' in result

    def test_invalid_placeholder_numbers(self) -> None:
        """Test handling of invalid placeholder numbers."""
        html = """
        <!-- structured table 0 -->
        <!-- structured table 999 -->
        <!-- structured table abc -->
        """

        bbox = BBox(x=0, y=0, w=100, h=50)
        cell = TableCell(text="Test", bbox=BBox(x=0, y=0, w=100, h=50))
        structured_table = StructuredTable(id="test", bbox=bbox, rows=[[cell]])

        tables = [TableContent(kind="structured", page_no=1, structured_table=structured_table)]

        result = replace_structured_table_placeholders(html, tables)

        # Invalid placeholders should remain unchanged
        assert "<!-- structured table 0 -->" in result
        assert "<!-- structured table 999 -->" in result
        assert "<!-- structured table abc -->" in result

    def test_missing_structured_table_data(self) -> None:
        """Test handling when TableContent has no structured_table data."""
        html = "<!-- structured table 1 -->"

        tables = [TableContent(kind="structured", page_no=1, structured_table=None)]  # Missing data

        result = replace_structured_table_placeholders(html, tables)

        # Should leave placeholder unchanged when data is missing
        assert "<!-- structured table 1 -->" in result
