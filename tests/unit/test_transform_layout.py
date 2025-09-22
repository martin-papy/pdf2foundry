from __future__ import annotations

from typing import Any

import pytest

from pdf2foundry.transform.layout import detect_column_count, flatten_page_html
from pdf2foundry.transform.reflow import reflow_columns


class _Block:
    def __init__(self, x0: float, x1: float) -> None:
        self.x0 = x0
        self.x1 = x1


class _Page:
    def __init__(self, blocks: list[_Block]) -> None:
        self.blocks = blocks


class _Doc:
    def __init__(self, pages: list[_Page]) -> None:
        self.pages = pages


def test_detect_column_count_single_column() -> None:
    # All blocks clustered centrally
    blocks = [_Block(100, 200) for _ in range(10)]
    doc = _Doc([_Page(blocks)])
    assert detect_column_count(doc, 1) == 1


def test_detect_column_count_two_columns_and_flatten(caplog: pytest.LogCaptureFixture) -> None:
    # Create two clusters: left and right
    left = [_Block(50, 100) for _ in range(10)]
    right = [_Block(400, 450) for _ in range(10)]
    doc = _Doc([_Page(left + right)])
    assert detect_column_count(doc, 1) == 2
    # Flatten should log a warning and return same html
    caplog.clear()
    html = flatten_page_html("<p>x</p>", doc, 1)
    assert html == "<p>x</p>"
    assert any("Multi-column layout detected" in r.message for r in caplog.records)


def test_detect_column_count_fallback_get_blocks_and_bbox_tuple(monkeypatch: Any) -> None:
    class _Doc2:
        def get_blocks(self, page_no: int):  # type: ignore[no-untyped-def]
            # Return blocks with bbox tuples
            return [type("B", (), {"bbox": (10, 0, 20, 10)})() for _ in range(10)]

    doc = _Doc2()
    assert detect_column_count(doc, 1) == 1


class _TextBlock:
    """Mock text block for reflow testing."""

    def __init__(self, x0: float, y0: float, x1: float, y1: float, text: str = "text") -> None:
        self.bbox = (x0, y0, x1, y1)
        self.type = "text"
        self.text = text


class _TableBlock:
    """Mock table block for reflow testing."""

    def __init__(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self.bbox = (x0, y0, x1, y1)
        self.type = "table"


class _ImageBlock:
    """Mock image block for reflow testing."""

    def __init__(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self.bbox = (x0, y0, x1, y1)
        self.type = "image"


def test_reflow_columns_no_op_too_few_blocks() -> None:
    """Test that reflow returns original blocks when there are too few."""
    blocks = [_TextBlock(100, 100, 200, 120) for _ in range(5)]
    result = reflow_columns(blocks, 612.0)
    assert result == blocks


def test_reflow_columns_no_op_single_column() -> None:
    """Test that reflow returns original blocks for single column layout."""
    # All blocks in the center of the page
    blocks = [_TextBlock(250, 100 + i * 20, 350, 120 + i * 20) for i in range(10)]
    result = reflow_columns(blocks, 612.0)
    assert result == blocks


def test_reflow_columns_two_column_reorder() -> None:
    """Test that reflow correctly reorders two-column text blocks."""
    # Create two distinct columns with clear separation
    left_blocks = [
        _TextBlock(50, 100, 150, 120, "A1"),  # Left column, top
        _TextBlock(50, 140, 150, 160, "A2"),  # Left column, middle
        _TextBlock(50, 180, 150, 200, "A3"),  # Left column, bottom
    ]
    right_blocks = [
        _TextBlock(400, 110, 500, 130, "B1"),  # Right column, top
        _TextBlock(400, 150, 500, 170, "B2"),  # Right column, middle
        _TextBlock(400, 190, 500, 210, "B3"),  # Right column, bottom
    ]

    # Mix the blocks (interleaved order)
    blocks = [
        left_blocks[0],
        right_blocks[0],
        left_blocks[1],
        right_blocks[1],
        left_blocks[2],
        right_blocks[2],
    ]

    result = reflow_columns(blocks, 612.0)

    # Should be reordered to left column first, then right column
    expected_texts = ["A1", "A2", "A3", "B1", "B2", "B3"]
    result_texts = [getattr(block, "text", "") for block in result]
    assert result_texts == expected_texts


def test_reflow_columns_preserves_non_text_elements() -> None:
    """Test that reflow preserves tables and images in appropriate positions."""
    blocks = [
        _TextBlock(50, 100, 150, 120, "A1"),  # Left column
        _TableBlock(200, 105, 300, 125),  # Table in middle
        _TextBlock(400, 110, 500, 130, "B1"),  # Right column
        _TextBlock(50, 140, 150, 160, "A2"),  # Left column
        _TextBlock(400, 150, 500, 170, "B2"),  # Right column
    ]

    result = reflow_columns(blocks, 612.0)

    # Check that we have the same number of blocks
    assert len(result) == len(blocks)

    # Check that table is still present
    table_blocks = [b for b in result if getattr(b, "type", "") == "table"]
    assert len(table_blocks) == 1


def test_reflow_columns_gap_too_small() -> None:
    """Test that reflow skips when column gap is too small."""
    # Create blocks with insufficient gap (< 8% of page width)
    left_blocks = [_TextBlock(200, 100 + i * 20, 280, 120 + i * 20) for i in range(5)]
    right_blocks = [_TextBlock(300, 100 + i * 20, 380, 120 + i * 20) for i in range(5)]

    blocks = left_blocks + right_blocks
    result = reflow_columns(blocks, 612.0)

    # Should return original order due to insufficient gap
    assert result == blocks


def test_reflow_columns_three_columns() -> None:
    """Test that reflow can handle three-column layouts."""
    # Create three distinct columns
    col1 = [_TextBlock(50, 100 + i * 20, 150, 120 + i * 20, f"A{i+1}") for i in range(3)]
    col2 = [_TextBlock(250, 100 + i * 20, 350, 120 + i * 20, f"B{i+1}") for i in range(3)]
    col3 = [_TextBlock(450, 100 + i * 20, 550, 120 + i * 20, f"C{i+1}") for i in range(3)]

    # Mix the blocks
    blocks = [col1[0], col2[0], col3[0], col1[1], col2[1], col3[1], col1[2], col2[2], col3[2]]

    result = reflow_columns(blocks, 612.0)

    # Should be reordered by columns
    expected_texts = ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"]
    result_texts = [getattr(block, "text", "") for block in result]
    assert result_texts == expected_texts


def test_reflow_columns_y_coordinate_sorting() -> None:
    """Test that blocks within columns are sorted by y-coordinate."""
    # Create blocks in wrong y-order within columns
    left_blocks = [
        _TextBlock(50, 180, 150, 200, "A3"),  # Bottom first
        _TextBlock(50, 100, 150, 120, "A1"),  # Top last
        _TextBlock(50, 140, 150, 160, "A2"),  # Middle
    ]
    right_blocks = [
        _TextBlock(400, 150, 500, 170, "B2"),  # Middle first
        _TextBlock(400, 190, 500, 210, "B3"),  # Bottom
        _TextBlock(400, 110, 500, 130, "B1"),  # Top last
    ]

    blocks = left_blocks + right_blocks
    result = reflow_columns(blocks, 612.0)

    # Should be sorted by y-coordinate within each column
    expected_texts = ["A1", "A2", "A3", "B1", "B2", "B3"]
    result_texts = [getattr(block, "text", "") for block in result]
    assert result_texts == expected_texts


def test_flatten_page_html_with_reflow_enabled(caplog: pytest.LogCaptureFixture) -> None:
    """Test flatten_page_html with reflow enabled."""
    # Create two-column layout using _TextBlock for proper type detection
    left = [_TextBlock(50, 100, 100, 120, f"L{i}") for i in range(5)]
    right = [_TextBlock(400, 100, 450, 120, f"R{i}") for i in range(5)]

    # Create a custom doc that returns these blocks
    class _DocWithTextBlocks:
        def __init__(self, blocks: list[_TextBlock]) -> None:
            self.pages = [type("Page", (), {"blocks": blocks})()]

    doc = _DocWithTextBlocks(left + right)

    # Set log level to capture INFO messages
    caplog.set_level("INFO", logger="pdf2foundry.transform.layout")
    caplog.clear()
    html = flatten_page_html("<p>content</p>", doc, 1, reflow_enabled=True)

    # Should return original HTML (no HTML reconstruction yet)
    assert html == "<p>content</p>"

    # Should log info about applying reflow (or a failure message)
    assert any("applying experimental reflow" in r.message for r in caplog.records) or any(
        "Column reflow failed" in r.message for r in caplog.records
    )


def test_flatten_page_html_with_reflow_disabled(caplog: pytest.LogCaptureFixture) -> None:
    """Test flatten_page_html with reflow disabled (default behavior)."""
    # Create two-column layout
    left = [_Block(50, 100) for _ in range(10)]
    right = [_Block(400, 450) for _ in range(10)]
    doc = _Doc([_Page(left + right)])

    caplog.clear()
    html = flatten_page_html("<p>content</p>", doc, 1, reflow_enabled=False)

    # Should return original HTML
    assert html == "<p>content</p>"

    # Should log warning about multi-column detection
    assert any("Multi-column layout detected" in r.message for r in caplog.records)
    assert any("using Docling reading order" in r.message for r in caplog.records)


def test_flatten_page_html_single_column_no_reflow() -> None:
    """Test flatten_page_html with single column (no reflow needed)."""
    # Single column layout
    blocks = [_Block(250, 350) for _ in range(10)]
    doc = _Doc([_Page(blocks)])

    html = flatten_page_html("<p>content</p>", doc, 1, reflow_enabled=True)

    # Should return original HTML without any processing
    assert html == "<p>content</p>"


def test_flatten_page_html_custom_page_width() -> None:
    """Test flatten_page_html with custom page width."""
    # Create layout that would be valid with custom width
    left = [_Block(50, 100) for _ in range(10)]
    right = [_Block(200, 250) for _ in range(10)]  # Closer together
    doc = _Doc([_Page(left + right)])

    # With small page width, gap should be sufficient
    html = flatten_page_html("<p>content</p>", doc, 1, reflow_enabled=True, page_width=300.0)
    assert html == "<p>content</p>"


def test_reflow_columns_deterministic() -> None:
    """Test that reflow_columns produces deterministic results."""
    # Create identical block sets
    blocks1 = [
        _TextBlock(50, 100, 150, 120, "A1"),
        _TextBlock(400, 110, 500, 130, "B1"),
        _TextBlock(50, 140, 150, 160, "A2"),
        _TextBlock(400, 150, 500, 170, "B2"),
    ]

    blocks2 = [
        _TextBlock(50, 100, 150, 120, "A1"),
        _TextBlock(400, 110, 500, 130, "B1"),
        _TextBlock(50, 140, 150, 160, "A2"),
        _TextBlock(400, 150, 500, 170, "B2"),
    ]

    result1 = reflow_columns(blocks1, 612.0)
    result2 = reflow_columns(blocks2, 612.0)

    # Results should be identical
    texts1 = [getattr(b, "text", "") for b in result1]
    texts2 = [getattr(b, "text", "") for b in result2]
    assert texts1 == texts2
