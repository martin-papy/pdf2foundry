"""Tests for TableCell dataclass."""

import pytest

from pdf2foundry.model.content import BBox, TableCell


class TestTableCell:
    """Test TableCell dataclass."""

    def test_basic_cell(self) -> None:
        """Test creating basic table cell."""
        bbox = BBox(x=0, y=0, w=50, h=25)
        cell = TableCell(text="Hello", bbox=bbox)

        assert cell.text == "Hello"
        assert cell.bbox == bbox
        assert cell.row_span == 1
        assert cell.col_span == 1
        assert cell.is_header is False

    def test_header_cell_with_spans(self) -> None:
        """Test creating header cell with spans."""
        bbox = BBox(x=0, y=0, w=100, h=25)
        cell = TableCell(
            text="Header",
            bbox=bbox,
            row_span=2,
            col_span=3,
            is_header=True,
        )

        assert cell.text == "Header"
        assert cell.row_span == 2
        assert cell.col_span == 3
        assert cell.is_header is True

    def test_invalid_row_span_raises_error(self) -> None:
        """Test that row_span < 1 raises ValueError."""
        bbox = BBox(x=0, y=0, w=50, h=25)
        with pytest.raises(ValueError, match="Row span must be >= 1"):
            TableCell(text="Test", bbox=bbox, row_span=0)

    def test_invalid_col_span_raises_error(self) -> None:
        """Test that col_span < 1 raises ValueError."""
        bbox = BBox(x=0, y=0, w=50, h=25)
        with pytest.raises(ValueError, match="Column span must be >= 1"):
            TableCell(text="Test", bbox=bbox, col_span=0)

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        bbox = BBox(x=10, y=20, w=50, h=25)
        cell = TableCell(text="Test", bbox=bbox, row_span=2, is_header=True)

        expected = {
            "text": "Test",
            "bbox": {"x": 10.0, "y": 20.0, "w": 50.0, "h": 25.0},
            "row_span": 2,
            "col_span": 1,
            "is_header": True,
        }
        assert cell.to_dict() == expected

    def test_from_dict(self) -> None:
        """Test from_dict deserialization."""
        data = {
            "text": "Cell",
            "bbox": {"x": 5.0, "y": 10.0, "w": 30.0, "h": 15.0},
            "row_span": 1,
            "col_span": 2,
            "is_header": False,
        }
        cell = TableCell.from_dict(data)

        assert cell.text == "Cell"
        assert cell.bbox == BBox(x=5.0, y=10.0, w=30.0, h=15.0)
        assert cell.row_span == 1
        assert cell.col_span == 2
        assert cell.is_header is False

    def test_from_dict_with_defaults(self) -> None:
        """Test from_dict with missing optional fields uses defaults."""
        data = {
            "text": "Minimal",
            "bbox": {"x": 0.0, "y": 0.0, "w": 10.0, "h": 10.0},
        }
        cell = TableCell.from_dict(data)

        assert cell.row_span == 1
        assert cell.col_span == 1
        assert cell.is_header is False
