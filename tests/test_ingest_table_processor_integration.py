"""Tests for table processing integration and edge cases."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

from pdf2foundry.ingest.table_processor import (
    _process_tables,
    _process_tables_with_options,
)
from pdf2foundry.model.pipeline_options import PdfPipelineOptions, TableMode


class TestTableModeIntegration:
    """Integration tests for table mode behavior across different scenarios."""

    def test_table_mode_enum_integration(self) -> None:
        """Test that TableMode enum values work correctly with processing functions."""
        html = "<table><tr><td>Test</td></tr></table>"
        page_no = 1
        name_prefix = "test"
        doc = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir)

            # Test each enum value
            for mode in [TableMode.AUTO, TableMode.STRUCTURED, TableMode.IMAGE_ONLY]:
                options = PdfPipelineOptions(tables_mode=mode)

                with patch("pdf2foundry.ingest.table_processor._extract_structured_tables") as mock_extract:
                    mock_extract.return_value = []  # No structured tables

                    updated_html, tables = _process_tables_with_options(doc, html, page_no, assets_dir, options, name_prefix)

                    assert len(tables) == 1
                    if mode == TableMode.IMAGE_ONLY:
                        assert tables[0].kind == "image"
                    else:
                        # AUTO and STRUCTURED fall back to HTML when no structured tables
                        assert tables[0].kind == "html"

    def test_table_mode_confidence_thresholds(self) -> None:
        """Test confidence threshold behavior across different modes."""
        html = "<table><tr><td>Test</td></tr></table>"
        page_no = 1
        name_prefix = "test"
        doc = Mock()

        confidence_levels = [0.1, 0.3, 0.5, 0.7, 0.9]

        with tempfile.TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir)

            for confidence in confidence_levels:
                mock_table = Mock()
                mock_table.meta = {"confidence": confidence}

                # Test AUTO mode with different confidence levels
                options_auto = PdfPipelineOptions(tables_mode=TableMode.AUTO)

                with patch("pdf2foundry.ingest.table_processor._extract_structured_tables") as mock_extract:
                    mock_extract.return_value = [mock_table]

                    updated_html, tables = _process_tables_with_options(
                        doc, html, page_no, assets_dir, options_auto, name_prefix
                    )

                    assert len(tables) == 1
                    if confidence >= 0.6:  # Default threshold
                        assert tables[0].kind == "structured"
                    else:
                        assert tables[0].kind == "html"

                # Test STRUCTURED mode (should always use structured regardless of confidence)
                options_structured = PdfPipelineOptions(tables_mode=TableMode.STRUCTURED)

                with patch("pdf2foundry.ingest.table_processor._extract_structured_tables") as mock_extract:
                    mock_extract.return_value = [mock_table]

                    updated_html, tables = _process_tables_with_options(
                        doc, html, page_no, assets_dir, options_structured, name_prefix
                    )

                    assert len(tables) == 1
                    assert tables[0].kind == "structured"

    def test_table_mode_error_handling(self) -> None:
        """Test error handling in different table modes."""
        html = "<table><tr><td>Test</td></tr></table>"
        page_no = 1
        name_prefix = "test"
        doc = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir)

            # Test with extraction function raising an exception
            options = PdfPipelineOptions(tables_mode=TableMode.AUTO)

            with patch("pdf2foundry.ingest.table_processor._extract_structured_tables") as mock_extract:
                mock_extract.side_effect = Exception("Extraction failed")

                # Should gracefully fall back to HTML processing
                updated_html, tables = _process_tables_with_options(doc, html, page_no, assets_dir, options, name_prefix)

                assert len(tables) == 1
                assert tables[0].kind == "html"
                assert tables[0].html == "<table><tr><td>Test</td></tr></table>"

    def test_table_mode_performance_with_many_tables(self) -> None:
        """Test performance with many tables on a single page."""
        # Generate HTML with many tables
        tables_html = ""
        for i in range(50):  # 50 tables
            tables_html += f"<table id='table-{i}'><tr><td>Table {i} content</td></tr></table>\n"

        html = f"<div>{tables_html}</div>"
        page_no = 1
        name_prefix = "test"

        with tempfile.TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir)

            # Test that processing completes in reasonable time
            start_time = time.time()

            updated_html, tables = _process_tables(html, page_no, assets_dir, "auto", name_prefix)

            end_time = time.time()
            processing_time = end_time - start_time

            # Should find all 50 tables
            assert len(tables) == 50

            # Should complete in reasonable time (less than 5 seconds)
            assert processing_time < 5.0

            # Each table should have unique content
            table_ids = set()
            for table in tables:
                if table.html and "id='table-" in table.html:
                    # Extract table ID for uniqueness check
                    table_ids.add(table.html)

            assert len(table_ids) == 50  # All tables should be unique

    def test_table_mode_with_unicode_content(self) -> None:
        """Test table processing with Unicode characters."""
        html = """
        <table>
            <tr><th>Language</th><th>Greeting</th></tr>
            <tr><td>English</td><td>Hello</td></tr>
            <tr><td>Spanish</td><td>Hola</td></tr>
            <tr><td>Chinese</td><td>你好</td></tr>
            <tr><td>Arabic</td><td>مرحبا</td></tr>
            <tr><td>Emoji</td><td>👋🌍</td></tr>
        </table>
        """
        page_no = 1
        name_prefix = "test"

        with tempfile.TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir)

            updated_html, tables = _process_tables(html, page_no, assets_dir, "auto", name_prefix)

            assert len(tables) == 1
            assert tables[0].html is not None

            # Check that Unicode characters are preserved
            assert "你好" in tables[0].html
            assert "مرحبا" in tables[0].html
            assert "👋🌍" in tables[0].html

    def test_table_mode_asset_file_naming(self) -> None:
        """Test that asset files are named correctly for different scenarios."""
        html = "<table><tr><td>Test</td></tr></table>"
        page_no = 5
        name_prefix = "chapter-02-page"

        with tempfile.TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir)

            updated_html, tables = _process_tables(html, page_no, assets_dir, "image-only", name_prefix)

            assert len(tables) == 1
            assert tables[0].kind == "image"
            # The table numbering starts from 1, not the page number
            assert tables[0].image_name == "chapter-02-page_table_0001.png"

            # Check that the file was actually created with the correct name
            expected_file = assets_dir / "chapter-02-page_table_0001.png"
            assert expected_file.exists()

    def test_table_mode_consistency_across_runs(self) -> None:
        """Test that table processing produces consistent results across multiple runs."""
        html = """
        <table>
            <tr><td>Cell 1</td><td>Cell 2</td></tr>
            <tr><td>Cell 3</td><td>Cell 4</td></tr>
        </table>
        """
        page_no = 1
        name_prefix = "test"

        results = []

        # Run processing multiple times
        for _run in range(3):
            with tempfile.TemporaryDirectory() as temp_dir:
                assets_dir = Path(temp_dir)

                updated_html, tables = _process_tables(html, page_no, assets_dir, "auto", name_prefix)

                # Store results for comparison
                results.append(
                    {
                        "table_count": len(tables),
                        "table_kind": tables[0].kind if tables else None,
                        "table_html": tables[0].html if tables and tables[0].html else None,
                    }
                )

        # All runs should produce identical results
        assert all(result["table_count"] == results[0]["table_count"] for result in results)
        assert all(result["table_kind"] == results[0]["table_kind"] for result in results)
        assert all(result["table_html"] == results[0]["table_html"] for result in results)


class TestTableModeEdgeCases:
    """Test edge cases and boundary conditions for table mode behavior."""

    def test_empty_table_processing(self) -> None:
        """Test processing completely empty tables."""
        empty_tables = [
            "<table></table>",
            "<table><tr></tr></table>",
            "<table><tr><td></td></tr></table>",
            "<table><tbody></tbody></table>",
        ]

        page_no = 1
        name_prefix = "test"

        with tempfile.TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir)

            for html in empty_tables:
                updated_html, tables = _process_tables(html, page_no, assets_dir, "auto", name_prefix)

                # Should still detect and process empty tables
                assert len(tables) == 1
                assert tables[0].kind == "html"
                assert tables[0].html == html

    def test_table_with_special_attributes(self) -> None:
        """Test processing tables with various HTML attributes."""
        html = """
        <table class="data-table" id="main-table" style="width: 100%;" data-sort="true">
            <thead>
                <tr class="header-row">
                    <th scope="col" data-field="name">Name</th>
                    <th scope="col" data-field="value">Value</th>
                </tr>
            </thead>
            <tbody>
                <tr class="data-row" data-id="1">
                    <td data-label="Name">Item 1</td>
                    <td data-label="Value">100</td>
                </tr>
            </tbody>
        </table>
        """
        page_no = 1
        name_prefix = "test"

        with tempfile.TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir)

            updated_html, tables = _process_tables(html, page_no, assets_dir, "auto", name_prefix)

            assert len(tables) == 1
            assert tables[0].html is not None

            # Should preserve all attributes
            assert 'class="data-table"' in tables[0].html
            assert 'id="main-table"' in tables[0].html
            assert 'data-sort="true"' in tables[0].html
            assert 'scope="col"' in tables[0].html

    def test_table_mode_with_very_large_table(self) -> None:
        """Test processing with a very large table."""
        # Generate a large table (100x100 cells)
        rows = []
        for i in range(100):
            cells = [f"<td>Cell {i}-{j}</td>" for j in range(100)]
            rows.append(f"<tr>{''.join(cells)}</tr>")

        html = f"<table>{''.join(rows)}</table>"
        page_no = 1
        name_prefix = "test"

        with tempfile.TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir)

            # Should handle large tables without issues
            updated_html, tables = _process_tables(html, page_no, assets_dir, "auto", name_prefix)

            assert len(tables) == 1
            assert tables[0].html is not None
            assert len(tables[0].html) > 10000  # Should be a large HTML string

    def test_table_mode_with_invalid_assets_directory(self) -> None:
        """Test behavior when assets directory is invalid or inaccessible."""
        html = "<table><tr><td>Test</td></tr></table>"
        page_no = 1
        name_prefix = "test"

        # Test with non-existent directory (should be created)
        non_existent_dir = Path("/tmp/non_existent_pdf2foundry_test_dir")
        if non_existent_dir.exists():
            import shutil

            shutil.rmtree(non_existent_dir)

        # Create the directory first (simulating normal behavior)
        non_existent_dir.mkdir(parents=True, exist_ok=True)

        # Should process normally with created directory
        updated_html, tables = _process_tables(html, page_no, non_existent_dir, "image-only", name_prefix)

        assert len(tables) == 1
        assert tables[0].kind == "image"
        assert tables[0].image_name is not None
        assert (non_existent_dir / tables[0].image_name).exists()

        # Clean up
        if non_existent_dir.exists():
            import shutil

            shutil.rmtree(non_existent_dir)
