from __future__ import annotations

from typing import Any

import pytest

from pdf2foundry.transform.layout import detect_column_count, flatten_page_html


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
