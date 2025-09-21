from __future__ import annotations

from pathlib import Path
from typing import Any

from pdf2foundry.ingest.content_extractor import extract_semantic_content


class _Doc:
    def __init__(self, pages: int) -> None:
        self._pages = pages

    def num_pages(self) -> int:
        return self._pages

    def export_to_html(self, **_: Any) -> str:
        # include one embedded image, one table, and one link
        return (
            '<div class="p">Hello'
            '<img src="data:image/png;base64,iVBORw0KGgo=">'
            "<table><tr><td>A</td></tr></table>"
            '<a href="https://example.com">link</a>'
            "</div>"
        )


def test_extract_semantic_content(tmp_path: Path) -> None:
    doc = _Doc(2)

    events: list[dict[str, Any]] = []

    def on_progress(event: str, payload: dict[str, Any]) -> None:
        events.append({"event": event, **payload})

    out = extract_semantic_content(
        doc, tmp_path / "assets", options="auto", on_progress=on_progress
    )
    # two pages created
    assert len(out.pages) == 2
    # at least one image extracted
    assert out.images
    # at least one table recorded (html mode)
    assert out.tables and out.tables[0].kind in ("html", "image")
    # links detected
    assert out.links
    # events contain extract_content:start and extract_content:success
    assert events[0]["event"] == "extract_content:start"
    assert events[-1]["event"] == "extract_content:success"


def test_extract_semantic_content_no_contentlayer(monkeypatch: Any, tmp_path: Path) -> None:
    # Force import failure for ContentLayer path
    import sys

    sys.modules.pop("docling_core.types.doc.document", None)
    doc = _Doc(1)
    out = extract_semantic_content(doc, tmp_path / "assets2", options="image-only")
    assert len(out.pages) == 1
    # in image-only mode, tables become images
    assert out.tables and out.tables[0].kind == "image"
