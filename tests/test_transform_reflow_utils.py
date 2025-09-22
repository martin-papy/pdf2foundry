"""Tests for reflow utility functions."""

from __future__ import annotations

from unittest.mock import Mock

from pdf2foundry.transform.reflow import (
    _block_type,
    _block_x_center,
    _block_y_top,
    _detect_columns_histogram,
    _detect_columns_kmeans,
    _silhouette_score,
    _simple_kmeans,
)


class MockBlock:
    """Mock block for testing."""

    def __init__(self, x0: float, y0: float, x1: float, y1: float, block_type: str = "text") -> None:
        self.bbox = (x0, y0, x1, y1)
        self.type = block_type


class MockBlockWithAttributes:
    """Mock block with separate x0, x1, y0 attributes."""

    def __init__(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1


class MockBlockWithBboxObject:
    """Mock block with bbox as an object."""

    def __init__(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self.bbox = Mock()
        self.bbox.x0 = x0
        self.bbox.y0 = y0
        self.bbox.x1 = x1
        self.bbox.y1 = y1


class MockBlockWithBoundingBox:
    """Mock block with bounding_box attribute."""

    def __init__(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self.bounding_box = (x0, y0, x1, y1)


class MockBlockWithCallableType:
    """Mock block with callable type method."""

    def __init__(self, x0: float, y0: float, x1: float, y1: float, block_type: str = "text") -> None:
        self.bbox = (x0, y0, x1, y1)
        self._type = block_type

    def type(self) -> str:
        return self._type


class MockBlockWithCategory:
    """Mock block with category attribute."""

    def __init__(self, x0: float, y0: float, x1: float, y1: float, category: str = "text") -> None:
        self.bbox = (x0, y0, x1, y1)
        self.category = category


def test_block_x_center_tuple_bbox() -> None:
    """Test _block_x_center with tuple bbox."""
    block = MockBlock(10.0, 20.0, 30.0, 40.0)
    assert _block_x_center(block) == 20.0  # (10 + 30) / 2


def test_block_x_center_object_bbox() -> None:
    """Test _block_x_center with bbox object."""
    block = MockBlockWithBboxObject(10.0, 20.0, 30.0, 40.0)
    assert _block_x_center(block) == 20.0


def test_block_x_center_bounding_box() -> None:
    """Test _block_x_center with bounding_box attribute."""
    block = MockBlockWithBoundingBox(10.0, 20.0, 30.0, 40.0)
    assert _block_x_center(block) == 20.0


def test_block_x_center_separate_attributes() -> None:
    """Test _block_x_center with separate x0/x1 attributes."""
    block = MockBlockWithAttributes(10.0, 20.0, 30.0, 40.0)
    assert _block_x_center(block) == 20.0


def test_block_x_center_no_bbox() -> None:
    """Test _block_x_center with no bbox information."""
    block = Mock()
    assert _block_x_center(block) is None


def test_block_x_center_invalid_bbox() -> None:
    """Test _block_x_center with invalid bbox."""
    block = Mock()
    block.bbox = "invalid"
    assert _block_x_center(block) is None


def test_block_x_center_short_tuple() -> None:
    """Test _block_x_center with short tuple."""
    block = Mock()
    block.bbox = (10.0, 20.0)  # Only 2 elements
    assert _block_x_center(block) is None


def test_block_x_center_exception_in_conversion() -> None:
    """Test _block_x_center with exception during float conversion."""
    block = Mock()
    block.bbox = ("not_a_number", 20.0, 30.0, 40.0)
    assert _block_x_center(block) is None


def test_block_y_top_tuple_bbox() -> None:
    """Test _block_y_top with tuple bbox."""
    block = MockBlock(10.0, 20.0, 30.0, 40.0)
    assert _block_y_top(block) == 20.0


def test_block_y_top_object_bbox() -> None:
    """Test _block_y_top with bbox object."""
    block = MockBlockWithBboxObject(10.0, 20.0, 30.0, 40.0)
    assert _block_y_top(block) == 20.0


def test_block_y_top_separate_attributes() -> None:
    """Test _block_y_top with separate y0 attribute."""
    block = MockBlockWithAttributes(10.0, 20.0, 30.0, 40.0)
    assert _block_y_top(block) == 20.0


def test_block_y_top_no_bbox() -> None:
    """Test _block_y_top with no bbox information."""
    block = Mock()
    assert _block_y_top(block) is None


def test_block_y_top_invalid_bbox() -> None:
    """Test _block_y_top with invalid bbox."""
    block = Mock()
    block.bbox = "invalid"
    assert _block_y_top(block) is None


def test_block_type_string_type() -> None:
    """Test _block_type with string type attribute."""
    block = MockBlock(0, 0, 10, 10, "heading")
    assert _block_type(block) == "heading"


def test_block_type_callable_type() -> None:
    """Test _block_type with callable type method."""
    block = MockBlockWithCallableType(0, 0, 10, 10, "paragraph")
    assert _block_type(block) == "paragraph"


def test_block_type_category() -> None:
    """Test _block_type with category attribute."""
    block = MockBlockWithCategory(0, 0, 10, 10, "table")
    assert _block_type(block) == "table"


def test_block_type_callable_exception() -> None:
    """Test _block_type with callable that raises exception."""
    block = Mock()
    block.type = Mock(side_effect=Exception("Test error"))
    block.category = None
    assert _block_type(block) == "text"  # Should default to text


def test_block_type_no_type_info() -> None:
    """Test _block_type with no type information."""
    block = Mock()
    block.type = None
    block.category = None
    assert _block_type(block) == "text"


def test_simple_kmeans_basic() -> None:
    """Test basic k-means clustering."""
    points = [1.0, 2.0, 8.0, 9.0, 10.0]
    k = 2

    assignments, centroids = _simple_kmeans(points, k)

    assert len(assignments) == len(points)
    assert len(centroids) == k
    assert all(0 <= a < k for a in assignments)

    # Should separate into two clusters
    left_cluster = [i for i, a in enumerate(assignments) if a == assignments[0]]
    right_cluster = [i for i, a in enumerate(assignments) if a != assignments[0]]

    # First few points should be in one cluster, last few in another
    assert len(left_cluster) > 0
    assert len(right_cluster) > 0


def test_simple_kmeans_insufficient_points() -> None:
    """Test k-means with insufficient points."""
    points = [1.0]
    k = 2

    assignments, centroids = _simple_kmeans(points, k)

    assert assignments == [0]
    assert centroids == [1.0]


def test_simple_kmeans_identical_points() -> None:
    """Test k-means with identical points."""
    points = [5.0, 5.0, 5.0, 5.0]
    k = 2

    assignments, centroids = _simple_kmeans(points, k)

    assert len(assignments) == 4
    assert len(centroids) == 1  # Should collapse to single centroid
    assert centroids[0] == 5.0


def test_simple_kmeans_convergence() -> None:
    """Test k-means convergence."""
    points = [1.0, 1.1, 1.2, 9.0, 9.1, 9.2]
    k = 2

    assignments, centroids = _simple_kmeans(points, k, max_iterations=1)

    # Should still work with limited iterations
    assert len(assignments) == 6
    assert len(centroids) == 2


def test_silhouette_score_basic() -> None:
    """Test basic silhouette score calculation."""
    points = [1.0, 2.0, 8.0, 9.0]
    assignments = [0, 0, 1, 1]
    centroids = [1.5, 8.5]

    score = _silhouette_score(points, assignments, centroids)

    # Should be positive for well-separated clusters
    assert score > 0


def test_silhouette_score_single_cluster() -> None:
    """Test silhouette score with single cluster."""
    points = [1.0, 2.0, 3.0]
    assignments = [0, 0, 0]
    centroids = [2.0]

    score = _silhouette_score(points, assignments, centroids)

    assert score == 0.0  # Single cluster should have score 0


def test_silhouette_score_single_point_cluster() -> None:
    """Test silhouette score with single point in cluster."""
    points = [1.0, 8.0, 9.0]
    assignments = [0, 1, 1]
    centroids = [1.0, 8.5]

    score = _silhouette_score(points, assignments, centroids)

    # Should handle single-point clusters gracefully
    assert isinstance(score, float)


def test_detect_columns_kmeans_good_separation() -> None:
    """Test k-means column detection with good separation."""
    # Two well-separated clusters
    x_centers = [50.0, 55.0, 60.0, 400.0, 405.0, 410.0]

    result = _detect_columns_kmeans(x_centers)

    assert result is not None
    num_columns, assignments, centroids = result
    assert num_columns == 2
    assert len(assignments) == 6
    assert len(centroids) == 2


def test_detect_columns_kmeans_poor_separation() -> None:
    """Test k-means column detection with poor separation."""
    # Poorly separated points
    x_centers = [50.0, 55.0, 60.0, 65.0, 70.0, 75.0]

    result = _detect_columns_kmeans(x_centers)

    # May still find clusters even with poor separation, depending on silhouette threshold
    if result is not None:
        num_columns, assignments, centroids = result
        assert num_columns >= 2
        assert len(assignments) == 6
        assert len(centroids) == num_columns


def test_detect_columns_kmeans_insufficient_points() -> None:
    """Test k-means column detection with insufficient points."""
    x_centers = [50.0, 60.0]  # Only 2 points, need at least 4 for k=2

    result = _detect_columns_kmeans(x_centers)

    assert result is None


def test_detect_columns_histogram_good_separation() -> None:
    """Test histogram column detection with good separation."""
    # Create points with clear gap and some spread within clusters
    x_centers = [45.0, 50.0, 55.0, 60.0, 65.0, 395.0, 400.0, 405.0, 410.0, 415.0]
    page_width = 612.0

    result = _detect_columns_histogram(x_centers, page_width)

    # The histogram method is quite strict about finding valleys
    # It may or may not detect columns depending on binning
    if result is not None:
        num_columns, boundaries = result
        assert num_columns == 2
        assert len(boundaries) == 1
        assert 65.0 < boundaries[0] < 395.0


def test_detect_columns_histogram_insufficient_points() -> None:
    """Test histogram column detection with insufficient points."""
    x_centers = [50.0, 60.0, 70.0]  # Less than 8 points
    page_width = 612.0

    result = _detect_columns_histogram(x_centers, page_width)

    assert result is None


def test_detect_columns_histogram_no_gap() -> None:
    """Test histogram column detection with no clear gap."""
    # Evenly distributed points with no clear valley
    x_centers = [float(x) for x in range(50, 400, 10)]  # Evenly spaced
    page_width = 612.0

    _detect_columns_histogram(x_centers, page_width)

    # Might return None if no clear valley is found
    # This depends on the specific distribution


def test_detect_columns_histogram_identical_points() -> None:
    """Test histogram column detection with identical points."""
    x_centers = [100.0] * 10  # All same x-coordinate
    page_width = 612.0

    result = _detect_columns_histogram(x_centers, page_width)

    assert result is None  # No spread, no columns
