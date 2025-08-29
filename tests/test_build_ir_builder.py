from __future__ import annotations

from typing import Any

from pdf2foundry.builder.ir_builder import build_document_ir
from pdf2foundry.model.content import HtmlPage, ParsedContent
from pdf2foundry.model.document import OutlineNode, ParsedDocument


def test_build_document_ir_basic() -> None:
    # Outline: Chapter (1..3) with two sections: 1..1 and 2..3
    section1 = OutlineNode(
        title="Intro", level=2, page_start=1, page_end=1, children=[], path=["chapter", "intro"]
    )
    section2 = OutlineNode(
        title="Usage", level=2, page_start=2, page_end=3, children=[], path=["chapter", "usage"]
    )
    chapter = OutlineNode(
        title="Chapter",
        level=1,
        page_start=1,
        page_end=3,
        children=[section1, section2],
        path=["chapter"],
    )
    parsed_doc = ParsedDocument(page_count=3, outline=[chapter])

    pages = [HtmlPage(html=f"<p>p{n}</p>", page_no=n) for n in range(1, 4)]
    parsed_content = ParsedContent(pages=pages)

    events: list[dict[str, Any]] = []

    def on_progress(event: str, payload: dict[str, Any]) -> None:
        events.append({"event": event, **payload})

    ir = build_document_ir(
        parsed_doc, parsed_content, mod_id="mod", doc_title="Doc", on_progress=on_progress
    )
    assert ir.mod_id == "mod"
    assert ir.title == "Doc"
    assert len(ir.chapters) == 1
    assert len(ir.chapters[0].sections) == 2
    # HTML merging
    assert ir.chapters[0].sections[0].html == "<p>p1</p>"
    assert ir.chapters[0].sections[1].html == "<p>p2</p>\n\n<p>p3</p>"
    # Progress events
    assert events[0]["event"] == "ir:start"
    assert events[-1]["event"] == "ir:finalized"


def test_build_document_ir_duplicate_section_titles() -> None:
    # Two sections with the same title at same level under one chapter
    s1 = OutlineNode(
        title="Intro", level=2, page_start=1, page_end=1, children=[], path=["chapter", "intro"]
    )
    s2 = OutlineNode(
        title="Intro", level=2, page_start=2, page_end=2, children=[], path=["chapter", "intro"]
    )
    ch = OutlineNode(
        title="Chapter", level=1, page_start=1, page_end=2, children=[s1, s2], path=["chapter"]
    )
    parsed_doc = ParsedDocument(page_count=2, outline=[ch])
    pages = [HtmlPage(html=f"<p>p{n}</p>", page_no=n) for n in range(1, 3)]
    ir = build_document_ir(parsed_doc, ParsedContent(pages=pages), mod_id="m", doc_title="D")
    ids = ["-".join(sec.id_path) for sec in ir.chapters[0].sections]
    assert ids[0] != ids[1]
