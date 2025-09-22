"""Tests for basic table processing functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from pdf2foundry.ingest.table_processor import (
    _process_tables,
    _process_tables_with_options,
    _rasterize_table_placeholder,
)
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
            updated_html, tables = _process_tables_with_options(doc, html, page_no, assets_dir, options, name_prefix)

            # Should call log_feature_decision for force_rasterization
            mock_log.assert_called_with("Tables", "force_rasterization", {"page": page_no, "mode": "IMAGE_ONLY"})

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
                updated_html, tables = _process_tables_with_options(doc, html, page_no, assets_dir, options, name_prefix)

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
                updated_html, tables = _process_tables_with_options(doc, html, page_no, assets_dir, options, name_prefix)

                # Should call ErrorManager.warn for structured mode fallback
                mock_warn.assert_called()

        # Should fall back to HTML processing
        assert len(tables) == 1
        assert tables[0].kind == "html"


def test_process_tables_case_insensitive() -> None:
    """Test that table processing is case insensitive."""
    html = "<p>Before</p><TABLE><TR><TD>Cell</TD></TR></TABLE><p>After</p>"
    page_no = 1
    name_prefix = "test"

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        updated_html, tables = _process_tables(html, page_no, assets_dir, "auto", name_prefix)

        # HTML should be unchanged in auto mode
        assert updated_html == html
        assert len(tables) == 1
        assert tables[0].kind == "html"
        assert tables[0].html == "<TABLE><TR><TD>Cell</TD></TR></TABLE>"


def test_process_tables_nested_content() -> None:
    """Test processing tables with nested content."""
    html = """
    <div>
        <p>Some text</p>
        <table>
            <tr>
                <td>Cell with <strong>bold</strong> text</td>
                <td>Cell with <em>italic</em> text</td>
            </tr>
        </table>
        <p>More text</p>
    </div>
    """
    page_no = 1
    name_prefix = "test"

    with tempfile.TemporaryDirectory() as temp_dir:
        assets_dir = Path(temp_dir)

        updated_html, tables = _process_tables(html, page_no, assets_dir, "auto", name_prefix)

        # HTML should be unchanged in auto mode
        assert updated_html == html
        assert len(tables) == 1
        assert tables[0].kind == "html"
        # Check that nested content is preserved
        assert tables[0].html is not None
        assert "<strong>bold</strong>" in tables[0].html
        assert "<em>italic</em>" in tables[0].html
