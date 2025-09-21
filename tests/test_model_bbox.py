"""Tests for BBox dataclass."""

import pytest

from pdf2foundry.model.content import BBox


class TestBBox:
    """Test BBox dataclass."""

    def test_valid_bbox(self) -> None:
        """Test creating valid bounding box."""
        bbox = BBox(x=10.0, y=20.0, w=100.0, h=50.0)
        assert bbox.x == 10.0
        assert bbox.y == 20.0
        assert bbox.w == 100.0
        assert bbox.h == 50.0

    def test_zero_dimensions_allowed(self) -> None:
        """Test that zero width/height is allowed."""
        bbox = BBox(x=0.0, y=0.0, w=0.0, h=0.0)
        assert bbox.w == 0.0
        assert bbox.h == 0.0

    def test_negative_width_raises_error(self) -> None:
        """Test that negative width raises ValueError."""
        with pytest.raises(ValueError, match="Width must be non-negative"):
            BBox(x=0.0, y=0.0, w=-10.0, h=50.0)

    def test_negative_height_raises_error(self) -> None:
        """Test that negative height raises ValueError."""
        with pytest.raises(ValueError, match="Height must be non-negative"):
            BBox(x=0.0, y=0.0, w=100.0, h=-20.0)

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        bbox = BBox(x=10.5, y=20.5, w=100.5, h=50.5)
        expected = {"x": 10.5, "y": 20.5, "w": 100.5, "h": 50.5}
        assert bbox.to_dict() == expected

    def test_from_dict(self) -> None:
        """Test from_dict deserialization."""
        data = {"x": 15.0, "y": 25.0, "w": 80.0, "h": 40.0}
        bbox = BBox.from_dict(data)
        assert bbox.x == 15.0
        assert bbox.y == 25.0
        assert bbox.w == 80.0
        assert bbox.h == 40.0

    def test_round_trip_serialization(self) -> None:
        """Test that serialization round-trip preserves data."""
        original = BBox(x=12.34, y=56.78, w=90.12, h=34.56)
        data = original.to_dict()
        restored = BBox.from_dict(data)
        assert restored == original
