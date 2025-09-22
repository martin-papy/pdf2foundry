"""Tests for apply_captions_to_images function."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from PIL import Image

from pdf2foundry.ingest.caption_processor import apply_captions_to_images
from pdf2foundry.model.content import ImageAsset
from pdf2foundry.model.pipeline_options import PdfPipelineOptions


class MockCaptionEngine:
    """Mock caption engine for testing."""

    def __init__(self, available: bool = True, caption: str | None = "A test image"):
        self._available = available
        self._caption = caption
        self.generate_calls: list[Image.Image] = []

    def is_available(self) -> bool:
        """Mock availability check."""
        return self._available

    def generate(self, pil_image: Image.Image) -> str | None:
        """Mock caption generation."""
        self.generate_calls.append(pil_image)
        if not self._available:
            return None
        return self._caption


class MockCaptionCache:
    """Mock caption cache for testing."""

    def __init__(self):
        self._cache: dict[str, str | None] = {}
        self.get_calls: list[Image.Image] = []
        self.set_calls: list[tuple[Image.Image, str | None]] = []

    def get(self, image: Image.Image) -> str | None | object:
        """Mock cache get."""
        self.get_calls.append(image)
        # Return sentinel object for cache miss
        return object()

    def set(self, image: Image.Image, caption: str | None) -> None:
        """Mock cache set."""
        self.set_calls.append((image, caption))


class TestApplyCaptionsToImages:
    """Test apply_captions_to_images function."""

    @pytest.fixture
    def temp_assets_dir(self) -> Path:
        """Create temporary assets directory with test images."""
        with tempfile.TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir)

            # Create test images
            test_image1 = Image.new("RGB", (100, 100), color="red")
            test_image2 = Image.new("RGB", (150, 150), color="blue")

            test_image1.save(assets_dir / "test1.png")
            test_image2.save(assets_dir / "test2.png")

            yield assets_dir

    @pytest.fixture
    def sample_images(self) -> list[ImageAsset]:
        """Create sample ImageAsset objects for testing."""
        return [
            ImageAsset(
                src="assets/test1.png",
                name="test1.png",
                page_no=1,
                bbox=None,
                caption=None,
            ),
            ImageAsset(
                src="assets/test2.png",
                name="test2.png",
                page_no=1,
                bbox=None,
                caption=None,
            ),
        ]

    def test_apply_captions_disabled(self, temp_assets_dir: Path, sample_images: list[ImageAsset]) -> None:
        """Test that captions are not applied when picture descriptions are disabled."""
        options = PdfPipelineOptions(picture_descriptions=False)
        mock_engine = MockCaptionEngine()
        mock_cache = MockCaptionCache()

        # Track progress events
        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        apply_captions_to_images(sample_images, temp_assets_dir, options, mock_engine, mock_cache, on_progress)

        # No captions should be applied
        for image in sample_images:
            assert image.caption is None
            assert image.alt_text is None

        # No engine calls should be made
        assert len(mock_engine.generate_calls) == 0
        assert len(mock_cache.get_calls) == 0
        assert len(mock_cache.set_calls) == 0

        # No progress events should be emitted
        assert len(events) == 0

    def test_apply_captions_no_engine(self, temp_assets_dir: Path, sample_images: list[ImageAsset]) -> None:
        """Test that captions are not applied when caption engine is None."""
        options = PdfPipelineOptions(picture_descriptions=True)

        # Track progress events
        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        apply_captions_to_images(sample_images, temp_assets_dir, options, None, None, on_progress)

        # No captions should be applied
        for image in sample_images:
            assert image.caption is None
            assert image.alt_text is None

        # No progress events should be emitted
        assert len(events) == 0

    def test_apply_captions_no_cache(self, temp_assets_dir: Path, sample_images: list[ImageAsset]) -> None:
        """Test that captions are not applied when caption cache is None."""
        options = PdfPipelineOptions(picture_descriptions=True)
        mock_engine = MockCaptionEngine()

        # Track progress events
        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        apply_captions_to_images(sample_images, temp_assets_dir, options, mock_engine, None, on_progress)

        # No captions should be applied
        for image in sample_images:
            assert image.caption is None
            assert image.alt_text is None

        # No engine calls should be made
        assert len(mock_engine.generate_calls) == 0

        # No progress events should be emitted
        assert len(events) == 0

    def test_apply_captions_engine_unavailable(self, temp_assets_dir: Path, sample_images: list[ImageAsset]) -> None:
        """Test that captions are not applied when caption engine is unavailable."""
        options = PdfPipelineOptions(picture_descriptions=True)
        mock_engine = MockCaptionEngine(available=False)
        mock_cache = MockCaptionCache()

        # Track progress events
        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        apply_captions_to_images(sample_images, temp_assets_dir, options, mock_engine, mock_cache, on_progress)

        # No captions should be applied
        for image in sample_images:
            assert image.caption is None
            assert image.alt_text is None

        # No engine calls should be made
        assert len(mock_engine.generate_calls) == 0
        assert len(mock_cache.get_calls) == 0
        assert len(mock_cache.set_calls) == 0

        # No progress events should be emitted
        assert len(events) == 0

    def test_apply_captions_success(self, temp_assets_dir: Path, sample_images: list[ImageAsset]) -> None:
        """Test successful caption application."""
        options = PdfPipelineOptions(picture_descriptions=True)
        mock_engine = MockCaptionEngine(available=True, caption="A colorful test image")
        mock_cache = MockCaptionCache()

        # Track progress events
        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        apply_captions_to_images(sample_images, temp_assets_dir, options, mock_engine, mock_cache, on_progress)

        # Captions should be applied to all images
        for image in sample_images:
            assert image.caption == "A colorful test image"
            assert image.alt_text == "A colorful test image"  # alt_text is set via property

        # Engine should be called for each image
        assert len(mock_engine.generate_calls) == 2
        assert len(mock_cache.get_calls) == 2
        assert len(mock_cache.set_calls) == 2

        # Progress events should be emitted
        assert len(events) == 3  # 2 image_processed + 1 batch_completed

        # Check image_processed events
        image_events = [e for e in events if e["event"] == "caption:image_processed"]
        assert len(image_events) == 2
        assert image_events[0]["image_name"] == "test1.png"
        assert image_events[0]["has_caption"] is True
        assert image_events[1]["image_name"] == "test2.png"
        assert image_events[1]["has_caption"] is True

        # Check batch_completed event
        batch_events = [e for e in events if e["event"] == "caption:batch_completed"]
        assert len(batch_events) == 1
        assert batch_events[0]["total_images"] == 2
        assert batch_events[0]["captioned_count"] == 2

    def test_apply_captions_no_caption_generated(self, temp_assets_dir: Path, sample_images: list[ImageAsset]) -> None:
        """Test behavior when no caption is generated."""
        options = PdfPipelineOptions(picture_descriptions=True)
        mock_engine = MockCaptionEngine(available=True, caption=None)  # No caption generated
        mock_cache = MockCaptionCache()

        # Track progress events
        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        apply_captions_to_images(sample_images, temp_assets_dir, options, mock_engine, mock_cache, on_progress)

        # No captions should be applied
        for image in sample_images:
            assert image.caption is None
            assert image.alt_text is None

        # Engine should still be called for each image
        assert len(mock_engine.generate_calls) == 2
        assert len(mock_cache.get_calls) == 2
        assert len(mock_cache.set_calls) == 2

        # Progress events should be emitted
        assert len(events) == 3  # 2 image_processed + 1 batch_completed

        # Check image_processed events
        image_events = [e for e in events if e["event"] == "caption:image_processed"]
        assert len(image_events) == 2
        assert image_events[0]["has_caption"] is False
        assert image_events[1]["has_caption"] is False

        # Check batch_completed event
        batch_events = [e for e in events if e["event"] == "caption:batch_completed"]
        assert len(batch_events) == 1
        assert batch_events[0]["total_images"] == 2
        assert batch_events[0]["captioned_count"] == 0  # No captions applied

    def test_apply_captions_missing_image_file(self, temp_assets_dir: Path) -> None:
        """Test behavior when image file is missing."""
        options = PdfPipelineOptions(picture_descriptions=True)
        mock_engine = MockCaptionEngine(available=True, caption="A test image")
        mock_cache = MockCaptionCache()

        # Create image asset for non-existent file
        missing_image = ImageAsset(
            src="assets/missing.png",
            name="missing.png",
            page_no=1,
            bbox=None,
            caption=None,
        )

        # Track progress events
        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        apply_captions_to_images([missing_image], temp_assets_dir, options, mock_engine, mock_cache, on_progress)

        # No captions should be applied
        assert missing_image.caption is None
        assert missing_image.alt_text is None

        # No engine calls should be made (file doesn't exist)
        assert len(mock_engine.generate_calls) == 0
        assert len(mock_cache.get_calls) == 0
        assert len(mock_cache.set_calls) == 0

        # Only batch_completed event should be emitted
        assert len(events) == 1
        batch_events = [e for e in events if e["event"] == "caption:batch_completed"]
        assert len(batch_events) == 1
        assert batch_events[0]["total_images"] == 1
        assert batch_events[0]["captioned_count"] == 0

    def test_apply_captions_with_cache_hit(self, temp_assets_dir: Path, sample_images: list[ImageAsset]) -> None:
        """Test caption application with cache hit."""
        options = PdfPipelineOptions(picture_descriptions=True)
        mock_engine = MockCaptionEngine(available=True, caption="Fresh caption")

        # Mock cache that returns cached captions
        mock_cache = Mock()
        mock_cache.get.return_value = "Cached caption"  # Cache hit

        # Track progress events
        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        apply_captions_to_images(sample_images, temp_assets_dir, options, mock_engine, mock_cache, on_progress)

        # Cached captions should be applied
        for image in sample_images:
            assert image.caption == "Cached caption"
            assert image.alt_text == "Cached caption"

        # Engine should not be called (cache hit)
        assert len(mock_engine.generate_calls) == 0

        # Cache should be called for each image
        assert mock_cache.get.call_count == 2
        assert mock_cache.set.call_count == 0  # No new captions to cache

        # Only batch_completed event should be emitted (no image_processed for cache hits)
        assert len(events) == 1
        batch_events = [e for e in events if e["event"] == "caption:batch_completed"]
        assert len(batch_events) == 1
        assert batch_events[0]["total_images"] == 2
        assert batch_events[0]["captioned_count"] == 2

    def test_apply_captions_with_cache_hit_none(self, temp_assets_dir: Path, sample_images: list[ImageAsset]) -> None:
        """Test caption application with cache hit returning None."""
        options = PdfPipelineOptions(picture_descriptions=True)
        mock_engine = MockCaptionEngine(available=True, caption="Fresh caption")

        # Mock cache that returns None (cached "no caption")
        mock_cache = Mock()
        mock_cache.get.return_value = None  # Cache hit with None

        # Track progress events
        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        apply_captions_to_images(sample_images, temp_assets_dir, options, mock_engine, mock_cache, on_progress)

        # No captions should be applied (cached None)
        for image in sample_images:
            assert image.caption is None
            assert image.alt_text is None

        # Engine should not be called (cache hit)
        assert len(mock_engine.generate_calls) == 0

        # Cache should be called for each image
        assert mock_cache.get.call_count == 2
        assert mock_cache.set.call_count == 0  # No new captions to cache

        # Only batch_completed event should be emitted
        assert len(events) == 1
        batch_events = [e for e in events if e["event"] == "caption:batch_completed"]
        assert len(batch_events) == 1
        assert batch_events[0]["total_images"] == 2
        assert batch_events[0]["captioned_count"] == 0
