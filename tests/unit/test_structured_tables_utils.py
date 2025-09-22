"""Tests for structured table utility functions."""

from __future__ import annotations

from unittest.mock import Mock

from pdf2foundry.ingest.structured_tables import _calculate_bbox_overlap, try_structured_table
from pdf2foundry.model.content import BBox, StructuredTable
from pdf2foundry.model.pipeline_options import PdfPipelineOptions, TableMode


class TestCalculateBboxOverlap:
    """Test the _calculate_bbox_overlap function."""

    def test_no_overlap(self) -> None:
        """Test bboxes with no overlap."""
        bbox1 = BBox(x=0.0, y=0.0, w=10.0, h=10.0)
        bbox2 = BBox(x=20.0, y=20.0, w=10.0, h=10.0)

        overlap = _calculate_bbox_overlap(bbox1, bbox2)
        assert overlap == 0.0

    def test_complete_overlap(self) -> None:
        """Test bboxes with complete overlap."""
        bbox1 = BBox(x=0.0, y=0.0, w=10.0, h=10.0)
        bbox2 = BBox(x=0.0, y=0.0, w=10.0, h=10.0)

        overlap = _calculate_bbox_overlap(bbox1, bbox2)
        assert overlap == 1.0

    def test_partial_overlap(self) -> None:
        """Test bboxes with partial overlap."""
        bbox1 = BBox(x=0.0, y=0.0, w=10.0, h=10.0)
        bbox2 = BBox(x=5.0, y=5.0, w=10.0, h=10.0)

        overlap = _calculate_bbox_overlap(bbox1, bbox2)
        # Intersection is 5x5 = 25, bbox1 area is 10x10 = 100
        # So overlap should be 25/100 = 0.25
        assert overlap == 0.25

    def test_zero_area_bbox(self) -> None:
        """Test bbox with zero area."""
        bbox1 = BBox(x=0.0, y=0.0, w=0.0, h=10.0)  # Zero width
        bbox2 = BBox(x=0.0, y=0.0, w=10.0, h=10.0)

        overlap = _calculate_bbox_overlap(bbox1, bbox2)
        assert overlap == 0.0

    def test_touching_edges(self) -> None:
        """Test bboxes that only touch at edges."""
        bbox1 = BBox(x=0.0, y=0.0, w=10.0, h=10.0)
        bbox2 = BBox(x=10.0, y=0.0, w=10.0, h=10.0)  # Touching right edge

        overlap = _calculate_bbox_overlap(bbox1, bbox2)
        assert overlap == 0.0


class TestTryStructuredTable:
    """Test the try_structured_table function."""

    def test_no_tables_found(self) -> None:
        """Test when no tables are found."""
        doc = Mock()
        doc.pages = [Mock()]
        doc.pages[0].items = []
        doc.table_store = None

        options = PdfPipelineOptions(tables_mode=TableMode.STRUCTURED)

        table, confidence = try_structured_table(doc, 1, None, options)
        assert table is None
        assert confidence == 0.0

    def test_single_table_found(self) -> None:
        """Test when single table is found."""
        # Create mock table
        table_mock = Mock()
        table_mock.__class__.__name__ = "Table"
        table_mock.id = "test_table"
        table_mock.bbox = Mock(x0=10.0, y0=20.0, x1=50.0, y1=60.0)
        table_mock.confidence = 0.8
        table_mock.cells = []

        page = Mock()
        page.items = [table_mock]

        doc = Mock()
        doc.pages = [page]
        doc.table_store = None

        options = PdfPipelineOptions(tables_mode=TableMode.STRUCTURED)

        table, confidence = try_structured_table(doc, 1, None, options)
        assert table is not None
        assert isinstance(table, StructuredTable)
        assert confidence > 0.0

    def test_multiple_tables_best_confidence(self) -> None:
        """Test selection of best table when multiple are found."""
        # Create two mock tables with different confidences
        table1 = Mock()
        table1.__class__.__name__ = "Table"
        table1.id = "table1"
        table1.bbox = Mock(x0=10.0, y0=20.0, x1=50.0, y1=60.0)
        table1.confidence = 0.6
        table1.cells = []

        table2 = Mock()
        table2.__class__.__name__ = "Table"
        table2.id = "table2"
        table2.bbox = Mock(x0=60.0, y0=20.0, x1=100.0, y1=60.0)
        table2.confidence = 0.9
        table2.cells = []

        page = Mock()
        page.items = [table1, table2]

        doc = Mock()
        doc.pages = [page]
        doc.table_store = None

        options = PdfPipelineOptions(tables_mode=TableMode.STRUCTURED)

        table, confidence = try_structured_table(doc, 1, None, options)
        assert table is not None
        # Should select the table with higher confidence
        assert table.meta["docling_table_id"] == "table2"

    def test_with_region_overlap_scoring(self) -> None:
        """Test confidence scoring with region overlap."""
        # Create table
        table_mock = Mock()
        table_mock.__class__.__name__ = "Table"
        table_mock.id = "test_table"
        table_mock.bbox = Mock(x0=10.0, y0=20.0, x1=50.0, y1=60.0)
        table_mock.confidence = 0.8
        table_mock.cells = []

        page = Mock()
        page.items = [table_mock]

        doc = Mock()
        doc.pages = [page]
        doc.table_store = None

        options = PdfPipelineOptions(tables_mode=TableMode.STRUCTURED)

        # Region that partially overlaps
        region = BBox(x=30.0, y=40.0, w=40.0, h=40.0)
        table, confidence = try_structured_table(doc, 1, region, options)

        assert table is not None
        # Confidence should be reduced due to partial overlap
        assert 0.0 < confidence < 0.8

    def test_confidence_clamping(self) -> None:
        """Test that confidence is clamped to [0, 1] range."""
        # Create table with very high confidence
        table_mock = Mock()
        table_mock.__class__.__name__ = "Table"
        table_mock.id = "test_table"
        table_mock.bbox = Mock(x0=10.0, y0=20.0, x1=50.0, y1=60.0)
        table_mock.confidence = 1.5  # > 1.0
        table_mock.cells = []

        page = Mock()
        page.items = [table_mock]

        doc = Mock()
        doc.pages = [page]
        doc.table_store = None

        options = PdfPipelineOptions(tables_mode=TableMode.STRUCTURED)

        table, confidence = try_structured_table(doc, 1, None, options)
        assert table is not None
        assert confidence <= 1.0

    def test_handles_none_confidence(self) -> None:
        """Test handling of None confidence values."""
        # Create table with None confidence
        table_mock = Mock()
        table_mock.__class__.__name__ = "Table"
        table_mock.id = "test_table"
        table_mock.bbox = Mock(x0=10.0, y0=20.0, x1=50.0, y1=60.0)
        table_mock.confidence = None
        table_mock.cells = []

        page = Mock()
        page.items = [table_mock]

        doc = Mock()
        doc.pages = [page]
        doc.table_store = None

        options = PdfPipelineOptions(tables_mode=TableMode.STRUCTURED)

        table, confidence = try_structured_table(doc, 1, None, options)
        assert table is not None
        # Should use default confidence of 0.5
        assert confidence > 0.0
