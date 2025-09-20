from __future__ import annotations

from typing import Any

from pdf2foundry.ingest.docling_parser import parse_structure_from_doc


class _Node:
    def __init__(self, title: str, page: int, children: list[_Node] | None = None) -> None:
        self.title = title
        self.page = page
        self.children = children or []


class _Doc:
    def __init__(self) -> None:
        self._outline = [
            _Node(
                "Chapter A",
                1,
                [
                    _Node("Section A1", 2),
                    _Node("Section A2", 3),
                ],
            )
        ]

    def num_pages(self) -> int:
        return 5

    @property
    def outline(self) -> list[_Node]:
        return self._outline

    def export_to_html(self, **_: Any) -> str:  # pragma: no cover - unused path here
        return ""


class _Conv:
    def __init__(self, doc: _Doc) -> None:
        self._doc = doc

    def convert(self, _: str) -> Any:
        class _Obj:
            def __init__(self, doc: _Doc) -> None:
                self.document = doc

        return _Obj(self._doc)


def _monkey_docling(monkeypatch: Any, doc: _Doc) -> None:
    import sys
    import types

    # Create fake docling submodules that parse_pdf_structure imports
    mod_base = types.ModuleType("docling.datamodel.base_models")

    class _IF:
        PDF = object()

    mod_base.InputFormat = _IF  # type: ignore[attr-defined]

    mod_opts = types.ModuleType("docling.datamodel.pipeline_options")

    class _Ppo:
        def __init__(self, **_: Any) -> None:
            pass

    mod_opts.PdfPipelineOptions = _Ppo  # type: ignore[attr-defined]

    mod_conv = types.ModuleType("docling.document_converter")

    class _Pfo:
        def __init__(self, **_: Any) -> None:
            pass

    mod_conv.PdfFormatOption = _Pfo  # type: ignore[attr-defined]
    mod_conv.DocumentConverter = lambda format_options: _Conv(doc)  # type: ignore[attr-defined]

    sys.modules["docling.datamodel.base_models"] = mod_base
    sys.modules["docling.datamodel.pipeline_options"] = mod_opts
    sys.modules["docling.document_converter"] = mod_conv


def test_parse_structure_from_doc_bookmarks(monkeypatch: Any) -> None:
    doc = _Doc()

    events: list[dict[str, Any]] = []

    def on_progress(event: str, payload: dict[str, Any]) -> None:
        events.append({"event": event, **payload})

    parsed = parse_structure_from_doc(doc, on_progress=on_progress)
    assert parsed.page_count == 5
    assert parsed.outline[0].title == "Chapter A"
    # First event in doc-based path is parse_structure:start
    assert events[0]["event"] == "parse_structure:start"
    assert any(e["event"].startswith("parse_structure:") for e in events)
