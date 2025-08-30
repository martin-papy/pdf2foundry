from __future__ import annotations

from typing import Any

from pdf2foundry.builder.ir_builder import build_document_ir, map_ir_to_foundry_entries
from pdf2foundry.model.content import HtmlPage, ParsedContent
from pdf2foundry.model.document import OutlineNode, ParsedDocument


def _sample_ir() -> tuple[Any, Any]:
    # Outline: Chapter (1..3) with two sections: 1..1 and 2..3
    section1 = OutlineNode(
        title="Overview",
        level=2,
        page_start=1,
        page_end=1,
        children=[],
        path=["chapter", "overview"],
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
    ir = build_document_ir(parsed_doc, parsed_content, mod_id="mod", doc_title="Doc")
    return ir, chapter


def test_map_ir_to_foundry_entries_basic() -> None:
    ir, chapter = _sample_ir()
    entries = map_ir_to_foundry_entries(ir)

    # One entry per chapter
    assert len(entries) == 1
    entry = entries[0]
    assert entry.name == chapter.title
    assert entry.ownership.get("default") == 0
    assert isinstance(entry.flags, dict)
    # Compendium Folders flags encoded at entry level
    assert "compendium-folders" in entry.flags
    cf = entry.flags["compendium-folders"]
    assert isinstance(cf, dict)
    assert cf.get("folderPath") == [ir.title, chapter.title]

    # Two pages mapped from sections
    assert len(entry.pages) == 2
    p1, p2 = entry.pages

    # Page invariants (type/text.format/title.show enforced by model)
    assert p1.type == "text"
    assert p1.text.get("format") == 1
    assert p1.title.get("show") is True

    # Title levels derived from section levels (sec.level=2 → title.level=1)
    assert p1.title.get("level") == 1
    assert p2.title.get("level") == 1

    # Sort ordering leaves gaps for future inserts
    assert p1.sort == 1000
    assert p2.sort == 2000


def test_map_ir_name_fallbacks_and_dedup_levels() -> None:
    # Build outline with empty chapter title and duplicate/empty section titles
    s1 = OutlineNode(
        title="Intro", level=2, page_start=1, page_end=1, children=[], path=["c", "intro"]
    )
    s2 = OutlineNode(
        title="Intro", level=3, page_start=2, page_end=2, children=[], path=["c", "intro-2"]
    )
    s3 = OutlineNode(
        title="  ", level=5, page_start=3, page_end=3, children=[], path=["c", "untitled"]
    )
    ch = OutlineNode(title="", level=1, page_start=1, page_end=3, children=[s1, s2, s3], path=["c"])
    parsed_doc = ParsedDocument(page_count=3, outline=[ch])
    pages = [HtmlPage(html=f"<p>p{n}</p>", page_no=n) for n in range(1, 4)]
    ir = build_document_ir(parsed_doc, ParsedContent(pages=pages), mod_id="m", doc_title="Book")

    entries = map_ir_to_foundry_entries(ir)
    assert len(entries) == 1
    e = entries[0]
    # Chapter name fallback
    assert e.name == "Untitled Chapter 1"
    # Page names: dedup and fallback
    assert e.pages[0].name == "Intro"
    assert e.pages[1].name == "Intro (2)"
    assert e.pages[2].name == "Untitled Section 3"
    # Title level clamped to 1..3 (levels were 2 -> 1, 3 -> 2, 5 -> 3)
    assert [p.title.get("level") for p in e.pages] == [1, 2, 3]

    # Canonical flags present on pages and entry (module namespace)
    ns = ir.mod_id
    for idx, p in enumerate(e.pages):
        assert ns in p.flags
        m = p.flags[ns]
        assert isinstance(m, dict)
        assert m.get("sectionOrder") == idx
        assert isinstance(m.get("canonicalPath"), list)
        assert isinstance(m.get("canonicalPathStr"), str)
    assert ns in e.flags
    em = e.flags[ns]
    assert isinstance(em, dict)
    assert isinstance(em.get("canonicalPath"), list)
    assert isinstance(em.get("canonicalPathStr"), str)
