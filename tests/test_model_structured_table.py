"""Tests for StructuredTable dataclass."""

import pytest

from pdf2foundry.model.content import BBox, StructuredTable, TableCell


class TestStructuredTable:
    """Test StructuredTable dataclass."""

    def test_basic_table(self) -> None:
        """Test creating basic structured table."""
        bbox = BBox(x=0, y=0, w=100, h=50)
        cell_bbox = BBox(x=0, y=0, w=50, h=25)
        cell = TableCell(text="Cell", bbox=cell_bbox)

        table = StructuredTable(
            id="test-table",
            bbox=bbox,
            rows=[[cell]],
        )

        assert table.id == "test-table"
        assert table.bbox == bbox
        assert len(table.rows) == 1
        assert len(table.rows[0]) == 1
        assert table.rows[0][0] == cell
        assert table.caption is None
        assert table.meta == {}

    def test_table_with_caption_and_meta(self) -> None:
        """Test table with caption and metadata."""
        bbox = BBox(x=0, y=0, w=100, h=50)
        cell_bbox = BBox(x=0, y=0, w=50, h=25)
        cell = TableCell(text="Data", bbox=cell_bbox)

        meta = {"source_page": 1, "confidence": 0.95}
        table = StructuredTable(
            id="data-table",
            bbox=bbox,
            rows=[[cell]],
            caption="Sample Data",
            meta=meta,
        )

        assert table.caption == "Sample Data"
        assert table.meta == meta

    def test_empty_table_raises_error(self) -> None:
        """Test that empty table raises ValueError."""
        bbox = BBox(x=0, y=0, w=100, h=50)
        with pytest.raises(ValueError, match="Table must have at least one row"):
            StructuredTable(id="empty", bbox=bbox, rows=[])

    def test_inconsistent_column_count_raises_error(self) -> None:
        """Test that inconsistent column counts raise ValueError."""
        bbox = BBox(x=0, y=0, w=100, h=50)
        cell_bbox = BBox(x=0, y=0, w=25, h=25)

        # First row has 2 cells, second row has 1 cell
        row1 = [
            TableCell(text="A", bbox=cell_bbox),
            TableCell(text="B", bbox=cell_bbox),
        ]
        row2 = [TableCell(text="C", bbox=cell_bbox)]

        with pytest.raises(ValueError, match="Row 1 has 1 logical columns"):
            StructuredTable(id="inconsistent", bbox=bbox, rows=[row1, row2])

    def test_colspan_validation_passes(self) -> None:
        """Test that colspan is properly accounted for in validation."""
        bbox = BBox(x=0, y=0, w=100, h=50)
        cell_bbox = BBox(x=0, y=0, w=25, h=25)

        # First row: 2 cells (2 logical columns)
        # Second row: 1 cell with colspan=2 (2 logical columns)
        row1 = [
            TableCell(text="A", bbox=cell_bbox),
            TableCell(text="B", bbox=cell_bbox),
        ]
        row2 = [TableCell(text="C", bbox=cell_bbox, col_span=2)]

        # Should not raise error
        table = StructuredTable(id="valid-colspan", bbox=bbox, rows=[row1, row2])
        assert len(table.rows) == 2

    def test_from_detector_factory(self) -> None:
        """Test from_detector factory method."""
        table = StructuredTable.from_detector(
            detector_output=None,  # Placeholder
            page_num=1,
            id_seed="test-doc",
            caption="Detected Table",
            confidence=0.85,
        )

        assert len(table.id) == 16  # SHA1 hash truncated to 16 chars
        assert table.caption == "Detected Table"
        assert table.meta["source_page"] == 1
        assert table.meta["confidence"] == 0.85
        assert table.meta["detector"] == "docling"
        assert len(table.rows) == 1  # Placeholder implementation

    def test_from_raster_fallback_factory(self) -> None:
        """Test from_raster_fallback factory method."""
        bbox = BBox(x=10, y=20, w=200, h=100)
        table = StructuredTable.from_raster_fallback(
            image_ref="table_image.png",
            page_num=2,
            bbox=bbox,
            id_seed="test-doc",
            caption="Rasterized Table",
        )

        assert table.bbox == bbox
        assert table.caption == "Rasterized Table"
        assert table.meta["source_page"] == 2
        assert table.meta["confidence"] == 0.0
        assert table.meta["raster_fallback"] is True
        assert table.meta["image_ref"] == "table_image.png"
        assert "Rasterized table: table_image.png" in table.rows[0][0].text

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        bbox = BBox(x=0, y=0, w=100, h=50)
        cell_bbox = BBox(x=0, y=0, w=50, h=25)
        cell = TableCell(text="Test", bbox=cell_bbox)

        table = StructuredTable(
            id="serialize-test",
            bbox=bbox,
            rows=[[cell]],
            caption="Test Table",
            meta={"test": True},
        )

        data = table.to_dict()

        assert data["id"] == "serialize-test"
        assert data["bbox"] == bbox.to_dict()
        assert data["caption"] == "Test Table"
        assert data["meta"] == {"test": True}
        assert len(data["rows"]) == 1
        assert len(data["rows"][0]) == 1
        assert data["rows"][0][0] == cell.to_dict()

    def test_from_dict(self) -> None:
        """Test from_dict deserialization."""
        data = {
            "id": "deserialize-test",
            "bbox": {"x": 5.0, "y": 10.0, "w": 80.0, "h": 40.0},
            "rows": [
                [
                    {
                        "text": "Cell1",
                        "bbox": {"x": 5.0, "y": 10.0, "w": 40.0, "h": 20.0},
                        "row_span": 1,
                        "col_span": 1,
                        "is_header": False,
                    }
                ]
            ],
            "caption": "Deserialized Table",
            "meta": {"restored": True},
        }

        table = StructuredTable.from_dict(data)

        assert table.id == "deserialize-test"
        assert table.bbox == BBox(x=5.0, y=10.0, w=80.0, h=40.0)
        assert table.caption == "Deserialized Table"
        assert table.meta == {"restored": True}
        assert len(table.rows) == 1
        assert table.rows[0][0].text == "Cell1"
