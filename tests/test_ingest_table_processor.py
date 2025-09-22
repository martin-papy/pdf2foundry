"""Tests for table processing functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from pdf2foundry.ingest.table_processor import (
    _process_tables,
    _process_tables_with_options,
    _rasterize_table_placeholder,
    replace_table_placeholders_in_pages,
)
from pdf2foundry.model.content import TableContent
from pdf2foundry.model.pipeline_options import PdfPipelineOptions, TableMode


def test_rasterize_table_placeholder() -> None:
    """Test creating a PNG placeholder for rasterized tables."""
    with tempfile.TemporaryDirectory() as temp_dir:
        dest_dir = Path(temp_dir)
        filename = "test_table.png"

        result = _rasterize_table_placeholder(dest_dir, filename)

        assert result == filename
        placeholder_file = dest_dir / filename
        assert placeholder_file.exists()
        assert placeholder_file.stat().st_size == 51  # Expected size of 1x1 transparent PNG


def test_process_tables_auto_mode() -> None:
    """Test processing tables in auto mode (keep as HTML)."""
    html = "<p>Before</p><table><tr><td>Cell</td></tr></table><p>After</p>"
    page_no = 1
    name_prefix = "test"

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        updated_html, tables = _process_tables(html, page_no, assets_dir, "auto", name_prefix)

        # HTML should be unchanged in auto mode
        assert updated_html == html
        assert len(tables) == 1
        assert tables[0].kind == "html"
        assert tables[0].page_no == page_no
        assert tables[0].html == "<table><tr><td>Cell</td></tr></table>"
        assert tables[0].image_name is None


def test_process_tables_image_only_mode() -> None:
    """Test processing tables in image-only mode."""
    html = "<p>Before</p><table><tr><td>Cell</td></tr></table><p>After</p>"
    page_no = 1
    name_prefix = "test"

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        updated_html, tables = _process_tables(html, page_no, assets_dir, "image-only", name_prefix)

        # HTML should have table replaced with img tag
        assert "<table>" not in updated_html
        assert '<img src="assets/test_table_0001.png">' in updated_html

        assert len(tables) == 1
        assert tables[0].kind == "image"
        assert tables[0].page_no == page_no
        assert tables[0].html is None
        assert tables[0].image_name == "test_table_0001.png"

        # Check that PNG file was created
        assert (assets_dir / "test_table_0001.png").exists()


def test_process_tables_multiple_tables() -> None:
    """Test processing multiple tables."""
    html = """
    <p>Before</p>
    <table><tr><td>Table 1</td></tr></table>
    <p>Between</p>
    <table><tr><td>Table 2</td></tr></table>
    <p>After</p>
    """
    page_no = 1
    name_prefix = "test"

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        updated_html, tables = _process_tables(html, page_no, assets_dir, "image-only", name_prefix)

        assert len(tables) == 2
        assert tables[0].image_name == "test_table_0001.png"
        assert tables[1].image_name == "test_table_0002.png"

        # Both PNG files should be created
        assert (assets_dir / "test_table_0001.png").exists()
        assert (assets_dir / "test_table_0002.png").exists()


def test_process_tables_no_tables() -> None:
    """Test processing HTML with no tables."""
    html = "<p>No tables here</p><div>Just content</div>"
    page_no = 1
    name_prefix = "test"

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        updated_html, tables = _process_tables(html, page_no, assets_dir, "auto", name_prefix)

        assert updated_html == html
        assert len(tables) == 0


def test_process_tables_with_options_image_only() -> None:
    """Test processing tables with IMAGE_ONLY mode option."""
    html = "<table><tr><td>Test</td></tr></table>"
    page_no = 1
    name_prefix = "test"
    options = PdfPipelineOptions(tables_mode=TableMode.IMAGE_ONLY)
    doc = Mock()

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        with patch("pdf2foundry.ingest.table_processor.log_feature_decision") as mock_log:
            updated_html, tables = _process_tables_with_options(
                doc, html, page_no, assets_dir, options, name_prefix
            )

            # Should call log_feature_decision for force_rasterization
            mock_log.assert_called_with(
                "Tables", "force_rasterization", {"page": page_no, "mode": "IMAGE_ONLY"}
            )

        assert len(tables) == 1
        assert tables[0].kind == "image"


def test_process_tables_with_options_no_structured_tables() -> None:
    """Test processing when no structured tables are available."""
    html = "<table><tr><td>Test</td></tr></table>"
    page_no = 1
    name_prefix = "test"
    options = PdfPipelineOptions(tables_mode=TableMode.AUTO)
    doc = Mock()

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        with patch("pdf2foundry.ingest.table_processor._extract_structured_tables") as mock_extract:
            mock_extract.return_value = []  # No structured tables

            with patch("pdf2foundry.ingest.table_processor.log_feature_decision") as mock_log:
                updated_html, tables = _process_tables_with_options(
                    doc, html, page_no, assets_dir, options, name_prefix
                )

                # Should call log_feature_decision for fallback
                mock_log.assert_called_with(
                    "Tables",
                    "fallback_to_html",
                    {"page": page_no, "reason": "no_structured_tables"},
                )

        assert len(tables) == 1
        assert tables[0].kind == "html"


def test_process_tables_with_options_structured_mode_no_tables() -> None:
    """Test STRUCTURED mode when no structured tables are available."""
    html = "<table><tr><td>Test</td></tr></table>"
    page_no = 1
    name_prefix = "test"
    options = PdfPipelineOptions(tables_mode=TableMode.STRUCTURED)
    doc = Mock()

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        with patch("pdf2foundry.ingest.table_processor._extract_structured_tables") as mock_extract:
            mock_extract.return_value = []  # No structured tables

            with patch("pdf2foundry.ingest.error_handling.ErrorManager.warn") as mock_warn:
                updated_html, tables = _process_tables_with_options(
                    doc, html, page_no, assets_dir, options, name_prefix
                )

                # Should call ErrorManager.warn for structured mode fallback
                mock_warn.assert_called()

        # Should fall back to HTML processing
        assert len(tables) == 1
        assert tables[0].kind == "html"


def test_process_tables_with_structured_tables_auto_mode() -> None:
    """Test processing with structured tables in AUTO mode."""
    html = "<table><tr><td>Test</td></tr></table>"
    page_no = 1
    name_prefix = "test"
    options = PdfPipelineOptions(tables_mode=TableMode.AUTO)
    doc = Mock()

    # Mock structured table with high confidence
    mock_table = Mock()
    mock_table.meta = {"confidence": 0.8}

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        with patch("pdf2foundry.ingest.table_processor._extract_structured_tables") as mock_extract:
            mock_extract.return_value = [mock_table]

            updated_html, tables = _process_tables_with_options(
                doc, html, page_no, assets_dir, options, name_prefix
            )

        # Should use structured table due to high confidence
        assert len(tables) == 1
        assert tables[0].kind == "structured"
        assert tables[0].structured_table == mock_table
        assert "<!-- structured table 1 -->" in updated_html


def test_process_tables_with_structured_tables_low_confidence() -> None:
    """Test processing with low confidence structured tables in AUTO mode."""
    html = "<table><tr><td>Test</td></tr></table>"
    page_no = 1
    name_prefix = "test"
    options = PdfPipelineOptions(tables_mode=TableMode.AUTO)
    doc = Mock()

    # Mock structured table with low confidence
    mock_table = Mock()
    mock_table.meta = {"confidence": 0.3}  # Below default threshold of 0.6

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        with patch("pdf2foundry.ingest.table_processor._extract_structured_tables") as mock_extract:
            mock_extract.return_value = [mock_table]

            updated_html, tables = _process_tables_with_options(
                doc, html, page_no, assets_dir, options, name_prefix
            )

        # Should fall back to HTML due to low confidence
        assert len(tables) == 1
        assert tables[0].kind == "html"
        assert tables[0].html == "<table><tr><td>Test</td></tr></table>"


def test_process_tables_structured_mode_with_low_confidence() -> None:
    """Test STRUCTURED mode with low confidence table (should still use structured)."""
    html = "<table><tr><td>Test</td></tr></table>"
    page_no = 1
    name_prefix = "test"
    options = PdfPipelineOptions(tables_mode=TableMode.STRUCTURED)
    doc = Mock()

    # Mock structured table with very low confidence
    mock_table = Mock()
    mock_table.meta = {"confidence": 0.2}  # Very low confidence

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        with patch("pdf2foundry.ingest.table_processor._extract_structured_tables") as mock_extract:
            mock_extract.return_value = [mock_table]

            updated_html, tables = _process_tables_with_options(
                doc, html, page_no, assets_dir, options, name_prefix
            )

        # Should use structured table even with low confidence in STRUCTURED mode
        assert len(tables) == 1
        assert tables[0].kind == "structured"
        assert tables[0].structured_table == mock_table

        # Should also create fallback PNG due to very low confidence
        assert (assets_dir / "test_table_0001_fallback.png").exists()


def test_process_tables_structured_table_no_confidence() -> None:
    """Test structured table with no confidence metadata."""
    html = "<table><tr><td>Test</td></tr></table>"
    page_no = 1
    name_prefix = "test"
    options = PdfPipelineOptions(tables_mode=TableMode.AUTO)
    doc = Mock()

    # Mock structured table with no confidence metadata
    mock_table = Mock()
    mock_table.meta = {}  # No confidence key

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        with patch("pdf2foundry.ingest.table_processor._extract_structured_tables") as mock_extract:
            mock_extract.return_value = [mock_table]

            updated_html, tables = _process_tables_with_options(
                doc, html, page_no, assets_dir, options, name_prefix
            )

        # Should fall back to HTML due to default confidence (0.5) being below threshold (0.6)
        assert len(tables) == 1
        assert tables[0].kind == "html"


def test_process_tables_structured_table_none_confidence() -> None:
    """Test structured table with None confidence."""
    html = "<table><tr><td>Test</td></tr></table>"
    page_no = 1
    name_prefix = "test"
    options = PdfPipelineOptions(tables_mode=TableMode.AUTO)
    doc = Mock()

    # Mock structured table with None confidence
    mock_table = Mock()
    mock_table.meta = {"confidence": None}

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        with patch("pdf2foundry.ingest.table_processor._extract_structured_tables") as mock_extract:
            mock_extract.return_value = [mock_table]

            updated_html, tables = _process_tables_with_options(
                doc, html, page_no, assets_dir, options, name_prefix
            )

        # Should fall back to HTML due to None confidence being treated as 0.5
        assert len(tables) == 1
        assert tables[0].kind == "html"


def test_replace_table_placeholders_no_structured_tables() -> None:
    """Test placeholder replacement when there are no structured tables."""
    mock_page = Mock()
    mock_page.html = "<p>No placeholders here</p>"
    pages = [mock_page]

    # Tables with no structured ones
    tables = [TableContent(kind="html", page_no=1, html="<table></table>", image_name=None)]

    replace_table_placeholders_in_pages(pages, tables)

    # HTML should be unchanged
    assert mock_page.html == "<p>No placeholders here</p>"


def test_replace_table_placeholders_with_structured_tables() -> None:
    """Test placeholder replacement with structured tables."""
    mock_page = Mock()
    mock_page.page_no = 1
    mock_page.html = "<p>Before</p><!-- structured table 1 --><p>After</p>"
    pages = [mock_page]

    # Tables with structured ones
    mock_structured_table = Mock()
    tables = [
        TableContent(
            kind="structured",
            page_no=1,
            html=None,
            image_name=None,
            structured_table=mock_structured_table,
        )
    ]

    with patch(
        "pdf2foundry.transform.table_renderer.replace_structured_table_placeholders"
    ) as mock_replace:
        mock_replace.return_value = "<p>Before</p><table>Structured content</table><p>After</p>"

        replace_table_placeholders_in_pages(pages, tables)

        # Should call the replacement function with original HTML and page tables
        mock_replace.assert_called_once_with(
            "<p>Before</p><!-- structured table 1 --><p>After</p>", tables
        )
        assert mock_page.html == "<p>Before</p><table>Structured content</table><p>After</p>"


def test_replace_table_placeholders_multiple_pages() -> None:
    """Test placeholder replacement across multiple pages."""
    mock_page1 = Mock()
    mock_page1.page_no = 1
    mock_page1.html = "<!-- structured table 1 -->"

    mock_page2 = Mock()
    mock_page2.page_no = 2
    mock_page2.html = "<!-- structured table 1 -->"

    pages = [mock_page1, mock_page2]

    # Tables for different pages
    mock_table1 = Mock()
    mock_table2 = Mock()
    tables = [
        TableContent(
            kind="structured", page_no=1, html=None, image_name=None, structured_table=mock_table1
        ),
        TableContent(
            kind="structured", page_no=2, html=None, image_name=None, structured_table=mock_table2
        ),
    ]

    with patch(
        "pdf2foundry.transform.table_renderer.replace_structured_table_placeholders"
    ) as mock_replace:
        mock_replace.side_effect = (
            lambda html, page_tables: f"Replaced page {page_tables[0].page_no}"
        )

        replace_table_placeholders_in_pages(pages, tables)

        # Should call replacement for each page
        assert mock_replace.call_count == 2
        assert mock_page1.html == "Replaced page 1"
        assert mock_page2.html == "Replaced page 2"


def test_process_tables_case_insensitive() -> None:
    """Test that table processing is case insensitive."""
    html = "<p>Before</p><TABLE><TR><TD>Cell</TD></TR></TABLE><p>After</p>"
    page_no = 1
    name_prefix = "test"

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        updated_html, tables = _process_tables(html, page_no, assets_dir, "auto", name_prefix)

        # Should find uppercase TABLE tag
        assert len(tables) == 1
        assert tables[0].html == "<TABLE><TR><TD>Cell</TD></TR></TABLE>"


def test_process_tables_nested_content() -> None:
    """Test processing tables with nested content."""
    html = """
    <table>
        <tr>
            <td>
                <div>Nested content</div>
                <span>More content</span>
            </td>
        </tr>
    </table>
    """
    page_no = 1
    name_prefix = "test"

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        updated_html, tables = _process_tables(html, page_no, assets_dir, "auto", name_prefix)

        assert len(tables) == 1
        # Should capture the entire table including nested content
        assert tables[0].html is not None
        assert "<div>Nested content</div>" in tables[0].html
        assert "<span>More content</span>" in tables[0].html
