"""Tests for caption engine functionality."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch

from PIL import Image  # type: ignore[import-not-found]

from pdf2foundry.ingest.caption_engine import CaptionCache, HFCaptionEngine


class MockCaptionEngine:
    """Mock caption engine for testing."""

    def __init__(self, available: bool = True, caption: str | None = "A test image"):
        self._available = available
        self._caption = caption

    def is_available(self) -> bool:
        """Mock availability check."""
        return self._available

    def generate(self, pil_image: Image.Image) -> str | None:
        """Mock caption generation."""
        if not self._available:
            return None
        return self._caption


class TestHFCaptionEngine:
    """Test HFCaptionEngine class."""

    def test_init(self) -> None:
        """Test HFCaptionEngine initialization."""
        engine = HFCaptionEngine("microsoft/Florence-2-base")
        assert engine.model_id == "microsoft/Florence-2-base"
        assert engine._pipeline is None
        assert engine._available is None

    @patch("builtins.__import__")
    def test_is_available_success(self, mock_import: Mock) -> None:
        """Test availability check when transformers is available."""
        # Mock successful import
        mock_transformers = Mock()
        mock_import.return_value = mock_transformers

        engine = HFCaptionEngine("microsoft/Florence-2-base")

        # First call should check availability
        available = engine.is_available()
        assert available is True

        # Second call should use cached result
        available = engine.is_available()
        assert available is True

    @patch("builtins.__import__")
    def test_is_available_import_error(self, mock_import: Mock) -> None:
        """Test availability check when transformers is not available."""
        mock_import.side_effect = ImportError("No module named 'transformers'")

        engine = HFCaptionEngine("microsoft/Florence-2-base")
        available = engine.is_available()
        assert available is False

    @patch("builtins.__import__")
    def test_is_available_other_error(self, mock_import: Mock) -> None:
        """Test availability check with other errors."""
        mock_import.side_effect = RuntimeError("Some other error")

        engine = HFCaptionEngine("microsoft/Florence-2-base")
        available = engine.is_available()
        assert available is False

    def test_generate_not_available(self) -> None:
        """Test caption generation when engine is not available."""
        with patch.object(HFCaptionEngine, "is_available", return_value=False):
            engine = HFCaptionEngine("microsoft/Florence-2-base")

            # Create a test image
            image = Image.new("RGB", (100, 100), color="red")

            result = engine.generate(image)
            assert result is None

    def test_generate_success_florence(self) -> None:
        """Test successful caption generation with Florence model."""
        with (
            patch.object(HFCaptionEngine, "is_available", return_value=True),
            patch.object(HFCaptionEngine, "_load_pipeline"),
        ):
            # Mock the pipeline
            mock_pipeline = Mock()
            mock_pipeline.return_value = [{"generated_text": "A red square image"}]

            engine = HFCaptionEngine("microsoft/Florence-2-base")
            engine._pipeline = mock_pipeline

            # Create a test image
            image = Image.new("RGB", (100, 100), color="red")

            result = engine.generate(image)
            assert result == "A red square image"

            # Verify pipeline was called
            mock_pipeline.assert_called_once_with(image)

    def test_generate_success_blip(self) -> None:
        """Test successful caption generation with BLIP model."""
        with (
            patch.object(HFCaptionEngine, "is_available", return_value=True),
            patch.object(HFCaptionEngine, "_load_pipeline"),
        ):
            # Mock the pipeline
            mock_pipeline = Mock()
            mock_pipeline.return_value = [{"text": "A colorful image"}]

            engine = HFCaptionEngine("salesforce/blip-image-captioning-base")
            engine._pipeline = mock_pipeline

            # Create a test image
            image = Image.new("RGB", (100, 100), color="blue")

            result = engine.generate(image)
            assert result == "A colorful image"

    def test_generate_with_prefix_removal(self) -> None:
        """Test caption generation with prefix removal."""
        with (
            patch.object(HFCaptionEngine, "is_available", return_value=True),
            patch.object(HFCaptionEngine, "_load_pipeline"),
        ):
            # Mock the pipeline
            mock_pipeline = Mock()
            mock_pipeline.return_value = [{"generated_text": "a photo of a red square"}]

            engine = HFCaptionEngine("microsoft/Florence-2-base")
            engine._pipeline = mock_pipeline

            # Create a test image
            image = Image.new("RGB", (100, 100), color="red")

            result = engine.generate(image)
            assert result == "A red square"  # Prefix removed and capitalized

    def test_generate_empty_result(self) -> None:
        """Test caption generation with empty result."""
        with (
            patch.object(HFCaptionEngine, "is_available", return_value=True),
            patch.object(HFCaptionEngine, "_load_pipeline"),
        ):
            # Mock the pipeline
            mock_pipeline = Mock()
            mock_pipeline.return_value = [{"generated_text": ""}]

            engine = HFCaptionEngine("microsoft/Florence-2-base")
            engine._pipeline = mock_pipeline

            # Create a test image
            image = Image.new("RGB", (100, 100), color="red")

            result = engine.generate(image)
            assert result is None

    def test_generate_pipeline_error(self) -> None:
        """Test caption generation with pipeline error."""
        with (
            patch.object(HFCaptionEngine, "is_available", return_value=True),
            patch.object(HFCaptionEngine, "_load_pipeline"),
        ):
            # Mock the pipeline to raise an error
            mock_pipeline = Mock()
            mock_pipeline.side_effect = RuntimeError("Model loading failed")

            engine = HFCaptionEngine("microsoft/Florence-2-base")
            engine._pipeline = mock_pipeline

            # Create a test image
            image = Image.new("RGB", (100, 100), color="red")

            result = engine.generate(image)
            assert result is None

    def test_load_pipeline_error(self) -> None:
        """Test pipeline loading error."""
        with patch.object(HFCaptionEngine, "is_available", return_value=True):
            # Create a test image first (before mocking import)
            image = Image.new("RGB", (100, 100), color="red")

            with patch("builtins.__import__") as mock_import:
                # Mock transformers import and pipeline creation to fail
                def side_effect(name: str, *args: Any, **kwargs: Any) -> Any:
                    if name == "transformers":
                        mock_transformers = Mock()
                        mock_transformers.pipeline.side_effect = RuntimeError("Model not found")
                        return mock_transformers
                    else:
                        # For other imports, use the real import
                        return __import__(name, *args, **kwargs)

                mock_import.side_effect = side_effect

                engine = HFCaptionEngine("nonexistent/model")

                # Should return None when model loading fails (error is logged, not raised)
                result = engine.generate(image)
                assert result is None


class TestCaptionCache:
    """Test CaptionCache class."""

    def test_init(self) -> None:
        """Test CaptionCache initialization."""
        cache = CaptionCache()
        assert cache._cache == {}

    def test_cache_miss(self) -> None:
        """Test cache miss returns sentinel object."""
        cache = CaptionCache()
        image = Image.new("RGB", (100, 100), color="red")

        result = cache.get(image)
        assert result is not None  # Should be sentinel object
        assert isinstance(result, object)

    def test_cache_hit_with_caption(self) -> None:
        """Test cache hit with caption."""
        cache = CaptionCache()
        image = Image.new("RGB", (100, 100), color="red")
        caption = "A red square"

        # Set caption
        cache.set(image, caption)

        # Get caption
        result = cache.get(image)
        assert result == caption

    def test_cache_hit_with_none(self) -> None:
        """Test cache hit with None caption."""
        cache = CaptionCache()
        image = Image.new("RGB", (100, 100), color="red")

        # Set None caption (no caption generated)
        cache.set(image, None)

        # Get caption
        result = cache.get(image)
        assert result is None

    def test_cache_different_images(self) -> None:
        """Test cache with different images."""
        cache = CaptionCache()
        image1 = Image.new("RGB", (100, 100), color="red")
        image2 = Image.new("RGB", (100, 100), color="blue")

        # Set different captions
        cache.set(image1, "Red image")
        cache.set(image2, "Blue image")

        # Get captions
        assert cache.get(image1) == "Red image"
        assert cache.get(image2) == "Blue image"

    def test_cache_same_content_different_objects(self) -> None:
        """Test cache with same content but different image objects."""
        cache = CaptionCache()

        # Create two identical images
        image1 = Image.new("RGB", (100, 100), color="red")
        image2 = Image.new("RGB", (100, 100), color="red")

        # Set caption for first image
        cache.set(image1, "Red square")

        # Second image should have same hash and return cached result
        result = cache.get(image2)
        assert result == "Red square"

    def test_clear(self) -> None:
        """Test cache clearing."""
        cache = CaptionCache()
        image = Image.new("RGB", (100, 100), color="red")

        # Set caption
        cache.set(image, "Red square")
        assert cache.get(image) == "Red square"

        # Clear cache
        cache.clear()

        # Should be cache miss now
        result = cache.get(image)
        assert isinstance(result, object)  # Sentinel object

    def test_image_hash_consistency(self) -> None:
        """Test that image hash is consistent."""
        cache = CaptionCache()
        image = Image.new("RGB", (100, 100), color="red")

        # Get hash multiple times
        hash1 = cache._get_image_hash(image)
        hash2 = cache._get_image_hash(image)

        assert hash1 == hash2
        assert len(hash1) == 16  # Truncated SHA256

    def test_image_hash_different_images(self) -> None:
        """Test that different images have different hashes."""
        cache = CaptionCache()
        image1 = Image.new("RGB", (100, 100), color="red")
        image2 = Image.new("RGB", (100, 100), color="blue")

        hash1 = cache._get_image_hash(image1)
        hash2 = cache._get_image_hash(image2)

        assert hash1 != hash2
