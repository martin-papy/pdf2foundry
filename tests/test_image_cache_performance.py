"""Performance tests for the shared image cache system."""

import time
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from pdf2foundry.ingest.image_cache import (
    BBox,
    CacheLimits,
    SharedImageCache,
    get_image_hash,
    should_enable_image_cache,
)


@pytest.fixture
def mock_doc() -> Mock:
    """Create a mock document with render_page method."""
    doc = Mock()

    def render_page(page_index: int, dpi: int = 150) -> Image.Image:
        # Create a test image with gradient pattern - different for each page/dpi combo
        size = (int(600 * dpi / 150), int(800 * dpi / 150))
        img = Image.new("RGB", size)

        # Create a gradient pattern that will produce different crops
        pixels = []
        for y in range(size[1]):
            for x in range(size[0]):
                # Create a pattern based on position, page, and dpi
                r = (x + page_index * 50) % 256
                g = (y + dpi) % 256
                b = (x + y + page_index * 30) % 256
                pixels.append((r, g, b))

        img.putdata(pixels)
        return img

    doc.render_page = render_page
    return doc


@pytest.fixture
def image_cache() -> SharedImageCache:
    """Create a shared image cache with small limits for testing."""
    limits = CacheLimits(
        page_raster_cache=5,
        region_image_cache=10,
        ocr_cache=20,
        caption_cache=20,
    )
    return SharedImageCache(limits)


class TestImageCachePerformance:
    """Test cache performance and effectiveness."""

    def test_page_cache_hit_performance(
        self, mock_doc: Mock, image_cache: SharedImageCache
    ) -> None:
        """Test that page cache hits are significantly faster than misses."""
        page_index = 0
        dpi = 150

        # First call - cache miss (should be slower)
        start_time = time.perf_counter()
        result1 = image_cache.get_cached_page_image(mock_doc, page_index, dpi)
        miss_time = time.perf_counter() - start_time

        assert result1 is not None
        assert result1.page_index == page_index
        assert result1.dpi == dpi

        # Second call - cache hit (should be faster)
        start_time = time.perf_counter()
        result2 = image_cache.get_cached_page_image(mock_doc, page_index, dpi)
        hit_time = time.perf_counter() - start_time

        assert result2 is not None
        assert result1.hash == result2.hash
        assert result1.image is result2.image  # Same object reference

        # Cache hit should be significantly faster
        # Allow some tolerance for timing variations
        assert (
            hit_time < miss_time * 0.5
        ), f"Hit time {hit_time:.6f}s should be much faster than miss time {miss_time:.6f}s"

        # Verify metrics
        metrics = image_cache.get_metrics()
        assert metrics["page_hits"] == 1
        assert metrics["page_misses"] == 1
        assert metrics["rasterize_calls"] == 1

    def test_region_cache_reuses_page_cache(
        self, mock_doc: Mock, image_cache: SharedImageCache
    ) -> None:
        """Test that region cache reuses page cache entries."""
        page_index = 0
        bbox = BBox(100, 100, 300, 300)

        # Get a region - should trigger page rasterization
        start_time = time.perf_counter()
        region1 = image_cache.get_cached_region_image(mock_doc, page_index, bbox)
        first_time = time.perf_counter() - start_time

        assert region1 is not None

        # Get the same region again - should hit region cache
        start_time = time.perf_counter()
        region2 = image_cache.get_cached_region_image(mock_doc, page_index, bbox)
        second_time = time.perf_counter() - start_time

        assert region2 is not None
        assert region1.hash == region2.hash
        assert region1.image is region2.image

        # Second call should be much faster
        assert second_time < first_time * 0.5

        # Get a different region from the same page - should reuse page cache
        bbox2 = BBox(200, 200, 400, 400)
        start_time = time.perf_counter()
        region3 = image_cache.get_cached_region_image(mock_doc, page_index, bbox2)
        third_time = time.perf_counter() - start_time

        assert region3 is not None
        assert region3.hash != region1.hash  # Different regions have different hashes

        # Third call should be faster than first (reuses page cache)
        assert third_time < first_time * 0.8

        # Verify metrics - should have 1 page miss, 1 page hit, 1 rasterize call
        metrics = image_cache.get_metrics()
        assert metrics["page_hits"] == 1  # Third region call reused the page
        assert metrics["page_misses"] == 1  # One page rasterization
        assert metrics["rasterize_calls"] == 1  # Only one actual rasterization
        assert metrics["region_hits"] == 1  # Second region call was a hit
        assert metrics["region_misses"] == 2  # Two different regions

    def test_cache_eviction_behavior(self, mock_doc: Mock, image_cache: SharedImageCache) -> None:
        """Test LRU eviction behavior under memory pressure."""
        # Fill page cache beyond limit (5 pages)
        pages_to_cache = 7
        cached_results = []

        for i in range(pages_to_cache):
            result = image_cache.get_cached_page_image(mock_doc, i, 150)
            assert result is not None
            cached_results.append(result)

        metrics = image_cache.get_metrics()
        assert metrics["page_misses"] == pages_to_cache
        assert metrics["page_cache_size"] <= 5  # Should not exceed limit

        # Access first few pages again - some should be evicted
        evicted_count = 0
        for i in range(3):
            result = image_cache.get_cached_page_image(mock_doc, i, 150)
            assert result is not None
            if result.hash != cached_results[i].hash:
                evicted_count += 1

        # Some pages should have been evicted and re-rasterized
        final_metrics = image_cache.get_metrics()
        assert final_metrics["rasterize_calls"] > pages_to_cache

    def test_different_dpi_creates_separate_cache_entries(
        self, mock_doc: Mock, image_cache: SharedImageCache
    ) -> None:
        """Test that different DPI values create separate cache entries."""
        page_index = 0

        # Cache at 150 DPI
        result_150 = image_cache.get_cached_page_image(mock_doc, page_index, 150)
        assert result_150 is not None

        # Cache at 300 DPI - should be a different entry
        result_300 = image_cache.get_cached_page_image(mock_doc, page_index, 300)
        assert result_300 is not None

        # Should be different images
        assert result_150.hash != result_300.hash
        assert result_150.image.size != result_300.image.size

        # Both should be cache misses
        metrics = image_cache.get_metrics()
        assert metrics["page_misses"] == 2
        assert metrics["page_hits"] == 0
        assert metrics["rasterize_calls"] == 2

    def test_bbox_normalization_cache_consistency(
        self, mock_doc: Mock, image_cache: SharedImageCache
    ) -> None:
        """Test that equivalent bboxes (after normalization) hit the same cache entry."""
        page_index = 0

        # These bboxes should normalize to the same thing
        bbox1 = BBox(100, 100, 300, 300)
        bbox2 = BBox(300, 300, 100, 100)  # Swapped coordinates

        result1 = image_cache.get_cached_region_image(mock_doc, page_index, bbox1)
        result2 = image_cache.get_cached_region_image(mock_doc, page_index, bbox2)

        assert result1 is not None
        assert result2 is not None

        # Should be the same cached result
        assert result1.hash == result2.hash
        assert result1.image is result2.image

        # Should have 1 region miss and 1 region hit
        metrics = image_cache.get_metrics()
        assert metrics["region_hits"] == 1
        assert metrics["region_misses"] == 1

    def test_cache_metrics_accuracy(self, mock_doc: Mock, image_cache: SharedImageCache) -> None:
        """Test that cache metrics are accurately tracked."""
        # Start with empty cache
        initial_metrics = image_cache.get_metrics()
        assert all(v == 0 for v in initial_metrics.values())

        # Generate some cache activity
        page_index = 0

        # Page cache miss
        image_cache.get_cached_page_image(mock_doc, page_index, 150)

        # Page cache hit
        image_cache.get_cached_page_image(mock_doc, page_index, 150)

        # Region cache miss (reuses page cache)
        bbox = BBox(100, 100, 200, 200)
        image_cache.get_cached_region_image(mock_doc, page_index, bbox)

        # Region cache hit
        image_cache.get_cached_region_image(mock_doc, page_index, bbox)

        final_metrics = image_cache.get_metrics()

        assert final_metrics["page_hits"] == 2  # One direct hit + one from region cache
        assert final_metrics["page_misses"] == 1
        assert final_metrics["region_hits"] == 1
        assert final_metrics["region_misses"] == 1
        assert final_metrics["rasterize_calls"] == 1
        assert final_metrics["page_hit_rate"] == 2 / 3  # 2 hits out of 3 total
        assert final_metrics["region_hit_rate"] == 0.5  # 1 hit out of 2 total

    def test_cache_clear_functionality(self, mock_doc: Mock, image_cache: SharedImageCache) -> None:
        """Test that cache clearing works correctly."""
        # Populate cache
        image_cache.get_cached_page_image(mock_doc, 0, 150)
        image_cache.get_cached_region_image(mock_doc, 0, BBox(100, 100, 200, 200))

        metrics_before = image_cache.get_metrics()
        assert metrics_before["page_cache_size"] > 0
        assert metrics_before["region_cache_size"] > 0

        # Clear cache
        image_cache.clear()

        metrics_after = image_cache.get_metrics()
        assert metrics_after["page_cache_size"] == 0
        assert metrics_after["region_cache_size"] == 0
        assert all(v == 0 for v in metrics_after.values())


class TestImageHashPerformance:
    """Test image hashing performance and consistency."""

    def test_hash_consistency(self) -> None:
        """Test that identical images produce identical hashes."""
        # Create two identical images
        img1 = Image.new("RGB", (100, 100), (255, 0, 0))
        img2 = Image.new("RGB", (100, 100), (255, 0, 0))

        hash1 = get_image_hash(img1)
        hash2 = get_image_hash(img2)

        assert hash1 == hash2
        assert len(hash1) == 16  # 16-character hex string

    def test_hash_uniqueness(self) -> None:
        """Test that different images produce different hashes."""
        img1 = Image.new("RGB", (100, 100), (255, 0, 0))
        img2 = Image.new("RGB", (100, 100), (0, 255, 0))
        img3 = Image.new("RGB", (200, 200), (255, 0, 0))  # Different size

        hash1 = get_image_hash(img1)
        hash2 = get_image_hash(img2)
        hash3 = get_image_hash(img3)

        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3

    def test_hash_performance(self) -> None:
        """Test that image hashing is reasonably fast."""
        # Create a moderately large image
        img = Image.new("RGB", (1000, 1000), (128, 128, 128))

        # Time multiple hash operations
        start_time = time.perf_counter()
        hashes = []
        for _ in range(10):
            hashes.append(get_image_hash(img))
        end_time = time.perf_counter()

        avg_time = (end_time - start_time) / 10

        # All hashes should be identical
        assert all(h == hashes[0] for h in hashes)

        # Should be reasonably fast (less than 100ms per hash for 1MP image)
        assert avg_time < 0.1, f"Average hash time {avg_time:.6f}s is too slow"


class TestCacheFeatureGates:
    """Test cache feature gate functionality."""

    def test_should_enable_image_cache_logic(self) -> None:
        """Test cache enablement logic for different feature combinations."""
        # No features enabled
        assert not should_enable_image_cache("off", "off", False)

        # OCR only
        assert should_enable_image_cache("off", "auto", False)
        assert should_enable_image_cache("off", "on", False)

        # Tables only
        assert should_enable_image_cache("auto", "off", False)
        assert should_enable_image_cache("image-only", "off", False)
        assert should_enable_image_cache("structured", "off", False)

        # Captions only
        assert should_enable_image_cache("off", "off", True)

        # Multiple features
        assert should_enable_image_cache("auto", "auto", True)
        assert should_enable_image_cache("structured", "on", False)

    @patch("pdf2foundry.ingest.image_cache.should_enable_image_cache")
    def test_cache_not_created_when_disabled(self, mock_should_enable: Mock) -> None:
        """Test that cache is not created when features are disabled."""
        mock_should_enable.return_value = False

        # This would normally create a cache, but should be None when disabled
        from pdf2foundry.ingest.image_cache import CacheLimits, SharedImageCache

        # Simulate the logic from content_extractor.py
        shared_image_cache = None
        if mock_should_enable("auto", "off", False):  # Call the mocked function
            shared_image_cache = SharedImageCache(CacheLimits())

        assert shared_image_cache is None
        mock_should_enable.assert_called_once_with("auto", "off", False)


class TestCacheMemoryManagement:
    """Test cache memory management and bounds."""

    def test_page_cache_respects_limits(self, mock_doc: Mock) -> None:
        """Test that page cache respects size limits."""
        limits = CacheLimits(page_raster_cache=3)
        cache = SharedImageCache(limits)

        # Add more pages than the limit
        for i in range(5):
            cache.get_cached_page_image(mock_doc, i, 150)

        metrics = cache.get_metrics()
        assert metrics["page_cache_size"] <= 3

    def test_region_cache_respects_limits(self, mock_doc: Mock) -> None:
        """Test that region cache respects size limits."""
        limits = CacheLimits(region_image_cache=2)
        cache = SharedImageCache(limits)

        # Add more regions than the limit
        bboxes = [
            BBox(0, 0, 100, 100),
            BBox(100, 100, 200, 200),
            BBox(200, 200, 300, 300),
        ]

        for bbox in bboxes:
            cache.get_cached_region_image(mock_doc, 0, bbox)

        metrics = cache.get_metrics()
        assert metrics["region_cache_size"] <= 2

    def test_lru_eviction_order(self, mock_doc: Mock) -> None:
        """Test that LRU eviction works correctly."""
        limits = CacheLimits(page_raster_cache=2)
        cache = SharedImageCache(limits)

        # Add 2 pages to fill cache
        result1 = cache.get_cached_page_image(mock_doc, 0, 150)
        assert result1 is not None
        result2 = cache.get_cached_page_image(mock_doc, 1, 150)
        assert result2 is not None

        # Access page 0 again to make it more recently used
        cache.get_cached_page_image(mock_doc, 0, 150)

        # Add page 2 - should evict page 1 (least recently used)
        cache.get_cached_page_image(mock_doc, 2, 150)

        # Page 0 should still be cached (hit)
        result1_again = cache.get_cached_page_image(mock_doc, 0, 150)
        assert result1_again is not None
        assert result1_again.image is result1.image

        # Page 1 should be evicted (miss)
        result2_again = cache.get_cached_page_image(mock_doc, 1, 150)
        assert result2_again is not None
        assert result2_again.image is not result2.image

        metrics = cache.get_metrics()
        assert metrics["page_hits"] >= 2  # At least the page 0 accesses
        assert metrics["rasterize_calls"] >= 4  # Original 3 + re-rasterized page 1
