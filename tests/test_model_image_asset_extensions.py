"""Tests for enhanced ImageAsset with new metadata fields."""

from pdf2foundry.model.content import BBox, ImageAsset


class TestImageAssetExtensions:
    """Test enhanced ImageAsset with new metadata fields."""

    def test_backward_compatible_image(self) -> None:
        """Test that existing ImageAsset usage still works."""
        image = ImageAsset(src="test.png", page_no=1, name="test")

        assert image.src == "test.png"
        assert image.page_no == 1
        assert image.name == "test"
        assert image.bbox is None
        assert image.caption is None
        assert image.alt_text is None
        assert image.meta == {}

    def test_enhanced_image_with_metadata(self) -> None:
        """Test ImageAsset with new metadata fields."""
        bbox = BBox(x=10, y=20, w=100, h=80)
        meta = {"source_page": 1, "extracted_at": "2023-01-01"}

        image = ImageAsset(
            src="enhanced.png",
            page_no=1,
            name="enhanced",
            bbox=bbox,
            caption="A sample image",
            meta=meta,
        )

        assert image.bbox == bbox
        assert image.caption == "A sample image"
        assert image.alt_text == "A sample image"  # Should alias caption
        assert image.meta == meta

    def test_alt_text_property_alias(self) -> None:
        """Test that alt_text property aliases caption."""
        image = ImageAsset(src="test.png", page_no=1, name="test")

        # Setting caption should update alt_text
        image.caption = "Test caption"
        assert image.alt_text == "Test caption"

        # Setting alt_text should update caption
        image.alt_text = "Updated caption"
        assert image.caption == "Updated caption"

        # Setting to None should work
        image.alt_text = None
        assert image.caption is None
        assert image.alt_text is None

    def test_to_dict_minimal(self) -> None:
        """Test to_dict with minimal ImageAsset (backward compatibility)."""
        image = ImageAsset(src="minimal.png", page_no=2, name="minimal")
        data = image.to_dict()

        expected = {
            "src": "minimal.png",
            "page_no": 2,
            "name": "minimal",
        }
        assert data == expected

    def test_to_dict_enhanced(self) -> None:
        """Test to_dict with enhanced ImageAsset."""
        bbox = BBox(x=5, y=10, w=50, h=40)
        image = ImageAsset(
            src="enhanced.png",
            page_no=3,
            name="enhanced",
            bbox=bbox,
            caption="Enhanced image",
            meta={"test": True},
        )

        data = image.to_dict()

        expected = {
            "src": "enhanced.png",
            "page_no": 3,
            "name": "enhanced",
            "bbox": {"x": 5.0, "y": 10.0, "w": 50.0, "h": 40.0},
            "caption": "Enhanced image",
            "meta": {"test": True},
        }
        assert data == expected

    def test_from_dict_minimal(self) -> None:
        """Test from_dict with minimal data (backward compatibility)."""
        data = {
            "src": "legacy.png",
            "page_no": 1,
            "name": "legacy",
        }

        image = ImageAsset.from_dict(data)

        assert image.src == "legacy.png"
        assert image.page_no == 1
        assert image.name == "legacy"
        assert image.bbox is None
        assert image.caption is None
        assert image.meta == {}

    def test_from_dict_enhanced(self) -> None:
        """Test from_dict with enhanced data."""
        data = {
            "src": "full.png",
            "page_no": 2,
            "name": "full",
            "bbox": {"x": 15.0, "y": 25.0, "w": 60.0, "h": 45.0},
            "caption": "Full image",
            "meta": {"enhanced": True},
        }

        image = ImageAsset.from_dict(data)

        assert image.src == "full.png"
        assert image.bbox == BBox(x=15.0, y=25.0, w=60.0, h=45.0)
        assert image.caption == "Full image"
        assert image.alt_text == "Full image"
        assert image.meta == {"enhanced": True}
