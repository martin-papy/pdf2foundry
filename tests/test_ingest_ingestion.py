from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pdf2foundry.ingest.docling_parser import parse_structure_from_doc
from pdf2foundry.ingest.ingestion import JsonOpts, ingest_docling


class _DummyDoc:
    def __init__(self, pages: int = 3, outline: list[Any] | None = None) -> None:
        self._pages = pages
        self._outline = outline or []

    def num_pages(self) -> int:
        return self._pages

    def export_to_html(self, **_: object) -> str:  # pragma: no cover - not used here
        return "<html></html>"

    # Outline-like attribute for parse_structure_from_doc tests
    @property
    def outline(self) -> list[Any]:
        return self._outline

    # Optional serializer for ingestion JSON write path
    def to_json(self) -> str:  # pragma: no cover - trivial
        return "{}"


def test_ingest_docling_converts_and_emits(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, dict[str, int | str]]] = []

    def on_progress(event: str, payload: dict[str, int | str]) -> None:
        events.append((event, payload))

    dummy = _DummyDoc(pages=4)

    def fake_convert(_: Path) -> _DummyDoc:
        return dummy

    # Patch the symbol resolved inside ingest_docling by its fully qualified import
    monkeypatch.setattr("pdf2foundry.ingest.docling_adapter.run_docling_conversion", fake_convert)

    doc = ingest_docling(Path("/tmp/x.pdf"), JsonOpts(), on_progress=on_progress)
    assert doc is dummy
    # Expect load start and success events
    assert any(e[0] == "load_pdf" for e in events)
    assert any(e[0] == "load_pdf:success" for e in events)


def test_ingest_docling_writes_json_when_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = _DummyDoc(pages=1)

    def fake_convert(_: Path) -> _DummyDoc:
        return dummy

    monkeypatch.setattr("pdf2foundry.ingest.docling_adapter.run_docling_conversion", fake_convert)

    json_path = tmp_path / "docling.json"
    events: list[tuple[str, dict[str, int | str]]] = []

    def on_progress(event: str, payload: dict[str, int | str]) -> None:
        events.append((event, payload))

    doc = ingest_docling(Path("/tmp/x.pdf"), JsonOpts(path=json_path), on_progress=on_progress)
    assert doc is dummy
    assert json_path.exists()
    assert json_path.read_text(encoding="utf-8").strip() != ""
    assert any(e[0] == "docling_json:saved" for e in events)


def test_parse_structure_from_doc_outline() -> None:
    # Build a minimal outline tree compatible with _outline_from_docling expectations
    class _Node:
        def __init__(self, title: str, page: int, children: list[_Node] | None = None) -> None:
            self.title = title
            self.page = page
            self.children = children or []

    outline: list[Any] = [
        _Node(
            "Chapter 1",
            1,
            [
                _Node("Section 1", 2),
                _Node("Section 2", 3),
            ],
        )
    ]

    doc = _DummyDoc(pages=5, outline=outline)
    parsed = parse_structure_from_doc(doc)
    assert parsed.page_count == 5
    assert parsed.outline and parsed.outline[0].title == "Chapter 1"
