"""Tests for ParsedContent with structured tables."""

from typing import Any

from pdf2foundry.model.content import BBox, ParsedContent, StructuredTable, TableCell


class TestParsedContentExtensions:
    """Test ParsedContent with structured tables."""

    def test_backward_compatible_parsed_content(self) -> None:
        """Test that existing ParsedContent usage still works."""
        content = ParsedContent()

        assert content.pages == []
        assert content.images == []
        assert content.tables == []
        assert content.links == []
        assert content.assets_dir is None
        assert content.structured_tables == []

    def test_parsed_content_with_structured_tables(self) -> None:
        """Test ParsedContent with structured tables."""
        bbox = BBox(x=0, y=0, w=100, h=50)
        cell_bbox = BBox(x=0, y=0, w=50, h=25)
        cell = TableCell(text="Data", bbox=cell_bbox)
        table = StructuredTable(id="test", bbox=bbox, rows=[[cell]])

        content = ParsedContent(structured_tables=[table])

        assert len(content.structured_tables) == 1
        assert content.structured_tables[0] == table

    def test_to_dict_minimal(self) -> None:
        """Test to_dict with minimal ParsedContent."""
        content = ParsedContent()
        data = content.to_dict()

        expected: dict[str, Any] = {
            "pages": [],
            "images": [],
            "tables": [],
            "links": [],
        }
        assert data == expected

    def test_to_dict_with_structured_tables(self) -> None:
        """Test to_dict with structured tables."""
        bbox = BBox(x=0, y=0, w=100, h=50)
        cell_bbox = BBox(x=0, y=0, w=50, h=25)
        cell = TableCell(text="Test", bbox=cell_bbox)
        table = StructuredTable(id="test", bbox=bbox, rows=[[cell]])

        content = ParsedContent(structured_tables=[table])
        data = content.to_dict()

        assert "structured_tables" in data
        assert len(data["structured_tables"]) == 1
        assert data["structured_tables"][0] == table.to_dict()

    def test_from_dict_minimal(self) -> None:
        """Test from_dict with minimal data."""
        data: dict[str, Any] = {
            "pages": [],
            "images": [],
            "tables": [],
            "links": [],
        }

        content = ParsedContent.from_dict(data)

        assert content.pages == []
        assert content.structured_tables == []

    def test_from_dict_with_structured_tables(self) -> None:
        """Test from_dict with structured tables."""
        table_data = {
            "id": "restored",
            "bbox": {"x": 0.0, "y": 0.0, "w": 100.0, "h": 50.0},
            "rows": [
                [
                    {
                        "text": "Restored",
                        "bbox": {"x": 0.0, "y": 0.0, "w": 50.0, "h": 25.0},
                        "row_span": 1,
                        "col_span": 1,
                        "is_header": False,
                    }
                ]
            ],
            "caption": None,
            "meta": {},
        }

        data = {
            "pages": [],
            "images": [],
            "tables": [],
            "links": [],
            "structured_tables": [table_data],
        }

        content = ParsedContent.from_dict(data)

        assert len(content.structured_tables) == 1
        assert content.structured_tables[0].id == "restored"
        assert content.structured_tables[0].rows[0][0].text == "Restored"

    def test_round_trip_serialization(self) -> None:
        """Test that serialization round-trip preserves all data."""
        # Create complex content with all features
        bbox = BBox(x=10, y=20, w=100, h=80)
        cell_bbox = BBox(x=10, y=20, w=50, h=40)
        cell = TableCell(text="Complex", bbox=cell_bbox, is_header=True)
        table = StructuredTable(
            id="complex",
            bbox=bbox,
            rows=[[cell]],
            caption="Complex Table",
            meta={"test": True},
        )

        from pdf2foundry.model.content import ImageAsset

        image = ImageAsset(
            src="test.png",
            page_no=1,
            name="test",
            bbox=bbox,
            caption="Test Image",
            meta={"image": True},
        )

        original = ParsedContent(
            images=[image],
            structured_tables=[table],
        )

        # Round-trip through serialization
        data = original.to_dict()
        restored = ParsedContent.from_dict(data)

        # Verify everything is preserved
        assert len(restored.structured_tables) == 1
        assert restored.structured_tables[0].id == "complex"
        assert restored.structured_tables[0].caption == "Complex Table"

        assert len(restored.images) == 1
        assert restored.images[0].caption == "Test Image"
        assert restored.images[0].alt_text == "Test Image"
