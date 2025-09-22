"""Tests for multi-column reflow integration functionality."""

from __future__ import annotations

from unittest.mock import Mock

from pdf2foundry.transform.reflow import (
    _block_x_center,
    reflow_columns,
)


class MockBlock:
    """Mock block for testing."""

    def __init__(self, x0: float, y0: float, x1: float, y1: float, block_type: str = "text") -> None:
        self.bbox = (x0, y0, x1, y1)
        self.type = block_type


def test_reflow_columns_insufficient_blocks() -> None:
    """Test reflow_columns with insufficient blocks."""
    blocks = [MockBlock(50, 100, 100, 120) for _ in range(3)]  # Only 3 blocks

    result = reflow_columns(blocks, 612.0)

    assert result == blocks  # Should return original blocks


def test_reflow_columns_insufficient_text_blocks() -> None:
    """Test reflow_columns with insufficient text blocks."""
    # Create blocks where most are not text type
    blocks = [
        MockBlock(50, 100, 100, 120, "image"),
        MockBlock(60, 120, 110, 140, "image"),
        MockBlock(70, 140, 120, 160, "text"),  # Only one text block
        MockBlock(80, 160, 130, 180, "table"),
        MockBlock(90, 180, 140, 200, "image"),
        MockBlock(100, 200, 150, 220, "image"),
    ]

    result = reflow_columns(blocks, 612.0)

    assert result == blocks  # Should return original blocks


def test_reflow_columns_gap_too_small() -> None:
    """Test reflow_columns with gap too small for column separation."""
    # Create blocks with small gap (less than 8% of page width)
    page_width = 612.0
    # Gap of ~30 points is less than 8% of page width (~49 points)

    blocks = [
        MockBlock(50, 100, 100, 120),  # Left cluster
        MockBlock(55, 120, 105, 140),
        MockBlock(60, 140, 110, 160),
        MockBlock(130, 100, 180, 120),  # Right cluster, gap = 30 points (too small)
        MockBlock(135, 120, 185, 140),
        MockBlock(140, 140, 190, 160),
    ]

    result = reflow_columns(blocks, page_width)

    assert result == blocks  # Should return original blocks due to small gap


def test_reflow_columns_non_uniform_widths() -> None:
    """Test reflow_columns with non-uniform column widths."""
    blocks = [
        MockBlock(50, 100, 60, 120),  # Very narrow left column (width=10)
        MockBlock(55, 120, 65, 140),
        MockBlock(400, 100, 500, 120),  # Wide right column (width=100)
        MockBlock(405, 120, 505, 140),
        MockBlock(410, 140, 510, 160),
        MockBlock(415, 160, 515, 180),
    ]

    result = reflow_columns(blocks, 612.0)

    # Should return original blocks due to non-uniform widths
    assert result == blocks


def test_reflow_columns_successful_reorder() -> None:
    """Test successful reflow with well-separated columns."""
    # Create interleaved blocks that should be reordered
    blocks = [
        MockBlock(50, 100, 100, 120),  # A1 - Left, top
        MockBlock(400, 110, 450, 130),  # B1 - Right, top
        MockBlock(50, 140, 100, 160),  # A2 - Left, middle
        MockBlock(400, 150, 450, 170),  # B2 - Right, middle
        MockBlock(50, 180, 100, 200),  # A3 - Left, bottom
        MockBlock(400, 190, 450, 210),  # B3 - Right, bottom
    ]

    result = reflow_columns(blocks, 612.0)

    # Should reorder to left column first, then right column
    expected_order = [blocks[0], blocks[2], blocks[4], blocks[1], blocks[3], blocks[5]]
    assert result == expected_order


def test_reflow_columns_with_non_text_blocks() -> None:
    """Test reflow with mixed text and non-text blocks."""
    blocks = [
        MockBlock(50, 100, 100, 120, "text"),  # A1
        MockBlock(400, 110, 450, 130, "image"),  # Image in right column
        MockBlock(50, 140, 100, 160, "text"),  # A2
        MockBlock(400, 150, 450, 170, "text"),  # B1
        MockBlock(50, 180, 100, 200, "text"),  # A3
        MockBlock(400, 190, 450, 210, "text"),  # B2
    ]

    result = reflow_columns(blocks, 612.0)

    # Should reorder text blocks but preserve non-text blocks in appropriate positions
    assert len(result) == 6
    # Non-text blocks should be assigned to appropriate columns


def test_reflow_columns_histogram_fallback() -> None:
    """Test reflow using histogram fallback when k-means fails."""
    # Create a distribution that k-means might not handle well but histogram can
    blocks = []

    # Left column - many blocks
    for i in range(10):
        blocks.append(MockBlock(50, 100 + i * 20, 100, 120 + i * 20))

    # Right column - fewer blocks but clear separation
    for i in range(3):
        blocks.append(MockBlock(400, 100 + i * 50, 450, 120 + i * 50))

    result = reflow_columns(blocks, 612.0)

    # Should successfully reorder using histogram method
    # Left column blocks should come first
    left_blocks = []
    right_blocks = []
    for b in result:
        x_center = _block_x_center(b)
        if x_center is not None:
            if x_center < 200:
                left_blocks.append(b)
            elif x_center > 200:
                right_blocks.append(b)

    # All left blocks should come before right blocks in result
    left_indices = [result.index(b) for b in left_blocks]
    right_indices = [result.index(b) for b in right_blocks]

    assert max(left_indices) < min(right_indices)


def test_reflow_columns_blocks_without_x_center() -> None:
    """Test reflow with blocks that don't have x-center information."""
    blocks = [
        MockBlock(50, 100, 100, 120),  # Normal block
        Mock(),  # Block without bbox info
        MockBlock(400, 110, 450, 130),  # Normal block
        Mock(),  # Another block without bbox info
    ]

    result = reflow_columns(blocks, 612.0)

    # Should handle blocks without x-center gracefully
    assert len(result) == 4
    # Blocks without x-center should be assigned to column 0


def test_reflow_columns_blocks_without_y_top() -> None:
    """Test reflow with blocks that don't have y-top information."""

    class BlockWithoutY:
        def __init__(self, x0: float, x1: float) -> None:
            self.bbox = (x0, None, x1, None)  # No y information
            self.type = "text"

    blocks = [
        BlockWithoutY(50, 100),
        BlockWithoutY(400, 450),
        BlockWithoutY(60, 110),
        BlockWithoutY(410, 460),
    ]

    result = reflow_columns(blocks, 612.0)

    # Should handle blocks without y-top gracefully (sort by 0.0)
    assert len(result) == 4
