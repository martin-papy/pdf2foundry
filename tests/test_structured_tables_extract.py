"""Tests for structured table extraction functionality."""

from __future__ import annotations

import logging
from unittest.mock import Mock

import pytest

from pdf2foundry.ingest.structured_tables import _extract_structured_tables
from pdf2foundry.model.content import BBox, StructuredTable


class TestExtractStructuredTables:
    """Test the _extract_structured_tables function."""

    def test_extract_empty_page(self) -> None:
        """Test extraction from empty page."""
        doc = Mock()
        doc.pages = [Mock()]
        doc.pages[0].items = []
        doc.table_store = None

        tables = _extract_structured_tables(doc, 1)
        assert tables == []

    def test_extract_table_with_cells(self) -> None:
        """Test extraction of table with cells."""
        # Create mock cells
        cell1 = Mock()
        cell1.row = 0
        cell1.col = 0
        cell1.rowspan = 1
        cell1.colspan = 1
        cell1.text = "A1"
        cell1.bbox = Mock(x0=10.0, y0=20.0, x1=30.0, y1=40.0)
        cell1.confidence = 0.9

        cell2 = Mock()
        cell2.row = 0
        cell2.col = 1
        cell2.rowspan = 1
        cell2.colspan = 1
        cell2.text = "B1"
        cell2.bbox = Mock(x0=30.0, y0=20.0, x1=50.0, y1=40.0)
        cell2.confidence = 0.8

        cell3 = Mock()
        cell3.row = 1
        cell3.col = 0
        cell3.rowspan = 1
        cell3.colspan = 1
        cell3.text = "A2"
        cell3.bbox = Mock(x0=10.0, y0=40.0, x1=30.0, y1=60.0)
        cell3.confidence = 0.85

        cell4 = Mock()
        cell4.row = 1
        cell4.col = 1
        cell4.rowspan = 1
        cell4.colspan = 1
        cell4.text = "B2"
        cell4.bbox = Mock(x0=30.0, y0=40.0, x1=50.0, y1=60.0)
        cell4.confidence = 0.85

        # Create mock table
        table = Mock()
        table.__class__.__name__ = "Table"
        table.id = "test_table"
        table.bbox = Mock(x0=10.0, y0=20.0, x1=50.0, y1=60.0)
        table.confidence = 0.8
        table.cells = [cell1, cell2, cell3, cell4]

        page = Mock()
        page.items = [table]

        doc = Mock()
        doc.pages = [page]
        doc.table_store = None

        tables = _extract_structured_tables(doc, 1)
        assert len(tables) == 1

        extracted_table = tables[0]
        assert isinstance(extracted_table, StructuredTable)
        assert extracted_table.bbox == BBox(x=10.0, y=20.0, w=40.0, h=40.0)
        assert len(extracted_table.rows) == 2
        assert len(extracted_table.rows[0]) == 2
        assert len(extracted_table.rows[1]) == 2
        assert extracted_table.rows[0][0].text == "A1"
        assert extracted_table.rows[0][1].text == "B1"
        assert extracted_table.rows[1][0].text == "A2"
        assert extracted_table.rows[1][1].text == "B2"

    def test_extract_table_with_region_filter(self) -> None:
        """Test extraction with region filter."""
        # Create table that overlaps with region
        table = Mock()
        table.__class__.__name__ = "Table"
        table.id = "test_table"
        table.bbox = Mock(x0=10.0, y0=20.0, x1=50.0, y1=60.0)
        table.confidence = 0.8
        table.cells = []

        page = Mock()
        page.items = [table]

        doc = Mock()
        doc.pages = [page]
        doc.table_store = None

        # Region that overlaps significantly
        region = BBox(x=5.0, y=15.0, w=50.0, h=50.0)
        tables = _extract_structured_tables(doc, 1, region)
        assert len(tables) == 1

        # Region that doesn't overlap enough
        region = BBox(x=100.0, y=100.0, w=50.0, h=50.0)
        tables = _extract_structured_tables(doc, 1, region)
        assert len(tables) == 0

    def test_extract_table_no_bbox(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test extraction of table without bbox."""
        table = Mock()
        table.__class__.__name__ = "Table"
        table.id = "test_table"
        table.bbox = None
        table.quad = None
        table.confidence = 0.8
        table.cells = []

        page = Mock()
        page.items = [table]

        doc = Mock()
        doc.pages = [page]
        doc.table_store = None

        with caplog.at_level(logging.WARNING):
            tables = _extract_structured_tables(doc, 1)

        assert tables == []
        assert "has no bounding box" in caplog.text

    def test_extract_handles_different_bbox_formats(self) -> None:
        """Test extraction handles different bbox formats."""
        # Test list format bbox
        table1 = Mock()
        table1.__class__.__name__ = "Table"
        table1.id = "table1"
        table1.bbox = [10.0, 20.0, 50.0, 60.0]  # [x0, y0, x1, y1]
        table1.confidence = 0.8
        table1.cells = []

        # Test object format bbox
        table2 = Mock()
        table2.__class__.__name__ = "Table"
        table2.id = "table2"
        table2.bbox = Mock(x0=10.0, y0=20.0, x1=50.0, y1=60.0)
        table2.confidence = 0.8
        table2.cells = []

        page = Mock()
        page.items = [table1, table2]

        doc = Mock()
        doc.pages = [page]
        doc.table_store = None

        tables = _extract_structured_tables(doc, 1)
        assert len(tables) == 2

        # Both should have same bbox
        expected_bbox = BBox(x=10.0, y=20.0, w=40.0, h=40.0)
        assert tables[0].bbox == expected_bbox
        assert tables[1].bbox == expected_bbox

    def test_extract_handles_exceptions(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that extraction handles exceptions gracefully."""
        doc = Mock()
        doc.pages = None  # This will cause an error

        with caplog.at_level(logging.WARNING):
            tables = _extract_structured_tables(doc, 1)

        assert tables == []
        assert "Failed to extract structured tables from Docling document" in caplog.text
