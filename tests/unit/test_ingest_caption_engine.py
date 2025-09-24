"""Tests for caption engine functionality."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch

import pytest
from PIL import Image

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

    @pytest.fixture(autouse=True)
    def mock_logger(self, isolate_logging):
        """Mock the logger to prevent StreamHandler issues in CI."""
        with patch("pdf2foundry.ingest.caption_engine.logger") as mock_log:
            mock_log.warning = Mock()
            mock_log.error = Mock()
            mock_log.debug = Mock()
            mock_log.info = Mock()
            yield mock_log

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

    def test_is_available_other_error(self) -> None:
        """Test availability check with other errors."""
        # Store original __import__ to avoid recursion
        original_import = __import__

        with patch("builtins.__import__") as mock_import:

            def side_effect(name: str, *args: Any, **kwargs: Any) -> Any:
                if name == "importlib.util":
                    raise RuntimeError("Some other error")
                else:
                    # Use the original import to avoid recursion
                    return original_import(name, *args, **kwargs)

            mock_import.side_effect = side_effect

            engine = HFCaptionEngine("microsoft/Florence-2-base")
            available = engine.is_available()
            assert available is False

    def test_generate_not_available(self) -> None:
        """Test caption generation when engine is not available."""
        with patch.object(HFCaptionEngine, "is_available", return_value=False):
            engine = HFCaptionEngine("microsoft/Florence-2-base")
            image = Image.new("RGB", (100, 100), color="red")
            result = engine.generate(image)
            assert result is None

    def test_generate_success(self) -> None:
        """Test successful caption generation."""
        with (
            patch.object(HFCaptionEngine, "is_available", return_value=True),
            patch.object(HFCaptionEngine, "_load_pipeline"),
        ):
            engine = HFCaptionEngine("microsoft/Florence-2-base")
            engine._pipeline = Mock(return_value=[{"generated_text": "A red square"}])

            image = Image.new("RGB", (100, 100), color="red")
            result = engine.generate(image)

            assert result == "A red square"

    def test_generate_with_error(self) -> None:
        """Test caption generation with error."""
        with (
            patch.object(HFCaptionEngine, "is_available", return_value=True),
            patch.object(HFCaptionEngine, "_load_pipeline"),
        ):
            engine = HFCaptionEngine("microsoft/Florence-2-base")
            engine._pipeline = Mock(side_effect=RuntimeError("Model error"))

            image = Image.new("RGB", (100, 100), color="red")
            result = engine.generate(image)

            assert result is None


class TestCaptionCache:
    """Test CaptionCache class."""

    def test_init(self) -> None:
        """Test CaptionCache initialization."""
        cache = CaptionCache(max_size=10)
        assert cache._max_size == 10
        assert len(cache._cache) == 0
        assert len(cache._access_order) == 0

    def test_get_miss(self) -> None:
        """Test cache miss."""
        cache = CaptionCache(max_size=10)
        image = Image.new("RGB", (100, 100), color="red")
        result = cache.get(image)
        # Should return a sentinel object (not found)
        assert result is not None
        assert not isinstance(result, str)

    def test_set_and_get(self) -> None:
        """Test setting and getting from cache."""
        cache = CaptionCache(max_size=10)
        image = Image.new("RGB", (100, 100), color="red")
        cache.set(image, "red square")

        result = cache.get(image)
        assert result == "red square"

    def test_lru_eviction(self) -> None:
        """Test LRU eviction when cache is full."""
        cache = CaptionCache(max_size=2)

        # Create different images
        image1 = Image.new("RGB", (100, 100), color="red")
        image2 = Image.new("RGB", (100, 100), color="green")
        image3 = Image.new("RGB", (100, 100), color="blue")

        # Fill cache
        cache.set(image1, "red")
        cache.set(image2, "green")

        # Add third item, should evict image1
        cache.set(image3, "blue")

        # Check eviction
        result1 = cache.get(image1)
        assert not isinstance(result1, str)  # Should be sentinel (evicted)
        assert cache.get(image2) == "green"
        assert cache.get(image3) == "blue"

    def test_access_order_update(self) -> None:
        """Test that accessing items updates their position in LRU order."""
        cache = CaptionCache(max_size=2)

        # Create different images
        image1 = Image.new("RGB", (100, 100), color="red")
        image2 = Image.new("RGB", (100, 100), color="green")
        image3 = Image.new("RGB", (100, 100), color="blue")

        cache.set(image1, "red")
        cache.set(image2, "green")

        # Access image1 to make it most recently used
        cache.get(image1)

        # Add image3, should evict image2 (least recently used)
        cache.set(image3, "blue")

        assert cache.get(image1) == "red"  # Still there
        result2 = cache.get(image2)
        assert not isinstance(result2, str)  # Evicted
        assert cache.get(image3) == "blue"

    def test_update_existing_key(self) -> None:
        """Test updating an existing key doesn't change cache size."""
        cache = CaptionCache(max_size=2)

        # Create different images
        image1 = Image.new("RGB", (100, 100), color="red")
        image2 = Image.new("RGB", (100, 100), color="green")

        cache.set(image1, "red")
        cache.set(image2, "green")

        # Update existing key
        cache.set(image1, "new_red")

        assert len(cache._cache) == 2
        assert cache.get(image1) == "new_red"
        assert cache.get(image2) == "green"

    def test_clear(self) -> None:
        """Test clearing the cache."""
        cache = CaptionCache(max_size=10)

        # Create different images
        image1 = Image.new("RGB", (100, 100), color="red")
        image2 = Image.new("RGB", (100, 100), color="green")

        cache.set(image1, "red")
        cache.set(image2, "green")

        cache.clear()

        assert len(cache._cache) == 0
        assert len(cache._access_order) == 0

        # Both should return sentinel objects (not found)
        result1 = cache.get(image1)
        result2 = cache.get(image2)
        assert not isinstance(result1, str)
        assert not isinstance(result2, str)

    def test_cache_size(self) -> None:
        """Test getting cache size."""
        cache = CaptionCache(max_size=10)
        assert len(cache._cache) == 0

        # Create different images
        image1 = Image.new("RGB", (100, 100), color="red")
        image2 = Image.new("RGB", (100, 100), color="green")

        cache.set(image1, "red")
        assert len(cache._cache) == 1

        cache.set(image2, "green")
        assert len(cache._cache) == 2

        cache.clear()
        assert len(cache._cache) == 0
