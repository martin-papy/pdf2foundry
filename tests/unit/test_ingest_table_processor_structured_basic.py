"""Tests for basic structured table processing functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from pdf2foundry.ingest.table_processor import (
    _process_tables_with_options,
    replace_table_placeholders_in_pages,
)
from pdf2foundry.model.content import TableContent
from pdf2foundry.model.pipeline_options import PdfPipelineOptions, TableMode


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

            updated_html, tables = _process_tables_with_options(doc, html, page_no, assets_dir, options, name_prefix)

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

            updated_html, tables = _process_tables_with_options(doc, html, page_no, assets_dir, options, name_prefix)

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

            updated_html, tables = _process_tables_with_options(doc, html, page_no, assets_dir, options, name_prefix)

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

            updated_html, tables = _process_tables_with_options(doc, html, page_no, assets_dir, options, name_prefix)

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

            updated_html, tables = _process_tables_with_options(doc, html, page_no, assets_dir, options, name_prefix)

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

    with patch("pdf2foundry.transform.table_renderer.replace_structured_table_placeholders") as mock_replace:
        mock_replace.return_value = "<p>Before</p><table>Structured content</table><p>After</p>"

        replace_table_placeholders_in_pages(pages, tables)

        # Should call the replacement function with original HTML and page tables
        mock_replace.assert_called_once_with("<p>Before</p><!-- structured table 1 --><p>After</p>", tables)
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
        TableContent(kind="structured", page_no=1, html=None, image_name=None, structured_table=mock_table1),
        TableContent(kind="structured", page_no=2, html=None, image_name=None, structured_table=mock_table2),
    ]

    with patch("pdf2foundry.transform.table_renderer.replace_structured_table_placeholders") as mock_replace:
        mock_replace.side_effect = lambda html, page_tables: f"Replaced page {page_tables[0].page_no}"

        replace_table_placeholders_in_pages(pages, tables)

        # Should call replacement for each page
        assert mock_replace.call_count == 2
        assert mock_page1.html == "Replaced page 1"
        assert mock_page2.html == "Replaced page 2"
