"""Tests for structured table iteration functionality."""

from __future__ import annotations

import logging
from unittest.mock import Mock

import pytest

from pdf2foundry.ingest.structured_tables import _iter_structured_tables


class TestIterStructuredTables:
    """Test the _iter_structured_tables function."""

    def test_iter_empty_document(self) -> None:
        """Test iteration over empty document."""
        doc = Mock()
        doc.pages = []
        doc.table_store = None
        doc.tables = None

        tables = list(_iter_structured_tables(doc))
        assert tables == []

    def test_iter_document_no_tables(self) -> None:
        """Test iteration over document with no tables."""
        page = Mock()
        page.items = []
        page.elements = []

        doc = Mock()
        doc.pages = [page]
        doc.table_store = None
        doc.tables = None

        tables = list(_iter_structured_tables(doc))
        assert tables == []

    def test_iter_document_with_table(self) -> None:
        """Test iteration over document with a table."""
        # Create mock table
        cell1 = Mock()
        cell1.row = 0
        cell1.col = 0
        cell1.rowspan = 1
        cell1.colspan = 1
        cell1.text = "Header 1"
        cell1.bbox = Mock(x0=10.0, y0=20.0, x1=50.0, y1=40.0)
        cell1.quad = None
        cell1.confidence = 0.9

        cell2 = Mock()
        cell2.row = 0
        cell2.col = 1
        cell2.rowspan = 1
        cell2.colspan = 1
        cell2.text = "Header 2"
        cell2.bbox = Mock(x0=50.0, y0=20.0, x1=90.0, y1=40.0)
        cell2.quad = None
        cell2.confidence = 0.8

        table = Mock()
        table.__class__.__name__ = "Table"
        table.type = "table"
        table.id = "table_1"
        table.bbox = Mock(x0=10.0, y0=20.0, x1=90.0, y1=60.0)
        table.quad = None
        table.confidence = 0.85
        table.cells = [cell1, cell2]

        page = Mock()
        page.items = [table]
        page.elements = []

        doc = Mock()
        doc.pages = [page]
        doc.table_store = None
        doc.tables = None

        tables = list(_iter_structured_tables(doc))
        assert len(tables) == 1

        table_data = tables[0]
        assert table_data["page_no"] == 1
        assert table_data["table_id"] == "table_1"
        assert table_data["confidence"] == 0.85
        assert len(table_data["cells"]) == 2
        assert table_data["cells"][0]["text"] == "Header 1"
        assert table_data["cells"][1]["text"] == "Header 2"

    def test_iter_with_page_filter(self) -> None:
        """Test iteration with page filter."""
        # Create two pages with tables
        table1 = Mock()
        table1.__class__.__name__ = "Table"
        table1.id = "table_1"
        table1.bbox = Mock(x0=10.0, y0=20.0, x1=90.0, y1=60.0)
        table1.confidence = 0.8
        table1.cells = []

        table2 = Mock()
        table2.__class__.__name__ = "Table"
        table2.id = "table_2"
        table2.bbox = Mock(x0=10.0, y0=20.0, x1=90.0, y1=60.0)
        table2.confidence = 0.9
        table2.cells = []

        page1 = Mock()
        page1.items = [table1]
        page2 = Mock()
        page2.items = [table2]

        doc = Mock()
        doc.pages = [page1, page2]
        doc.table_store = None

        # Test filtering for page 2 only
        tables = list(_iter_structured_tables(doc, page_index=2))
        assert len(tables) == 1
        assert tables[0]["table_id"] == "table_2"
        assert tables[0]["page_no"] == 2

    def test_iter_with_table_ref(self) -> None:
        """Test iteration with table reference."""
        # Create table in table store
        table = Mock()
        table.id = "stored_table"
        table.bbox = Mock(x0=10.0, y0=20.0, x1=90.0, y1=60.0)
        table.confidence = 0.7
        table.cells = []

        # Create table reference
        table_ref = Mock()
        table_ref.__class__.__name__ = "TableRef"
        table_ref.id = "stored_table"
        table_ref.ref_id = "stored_table"

        page = Mock()
        page.items = [table_ref]

        doc = Mock()
        doc.pages = [page]
        doc.table_store = {"stored_table": table}

        tables = list(_iter_structured_tables(doc))
        assert len(tables) == 1
        assert tables[0]["table_id"] == "stored_table"

    def test_iter_handles_exceptions(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that iteration handles exceptions gracefully."""
        # Create a document that will raise an exception
        doc = Mock()
        doc.pages = None  # This will cause an error when iterating

        with caplog.at_level(logging.WARNING):
            tables = list(_iter_structured_tables(doc))

        assert tables == []
        assert "Failed to extract structured tables" in caplog.text
