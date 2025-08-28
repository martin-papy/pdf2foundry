from __future__ import annotations

from pathlib import Path

from pdf2foundry.parser import LinkAnnotation, PageContent, create_environment
from pdf2foundry.parser.html_convert import (
    build_chapter_html,
    build_section_html,
    slice_content_by_range,
)
from pdf2foundry.parser.structure import ChapterNode, SectionNode
from pdf2foundry.parser.templating import write_default_templates


def _mk_pc(idx: int, *lines: str) -> PageContent:
    return PageContent(page_index=idx, text_lines=list(lines), links=[])


def test_slice_content_by_range_filters_pages() -> None:
    contents = [_mk_pc(0, "a"), _mk_pc(1, "b"), _mk_pc(3, "c")]
    out = slice_content_by_range(contents, 1, 2)
    assert [c.page_index for c in out] == [1]


def test_build_section_and_chapter_html(tmp_path: Path) -> None:
    write_default_templates(tmp_path)
    templates = create_environment(tmp_path)

    contents = [
        PageContent(
            page_index=0,
            text_lines=["Intro"],
            links=[LinkAnnotation(page_index=0, bbox=(0, 0, 0, 0), uri=None, target_page_index=2)],
        ),
        _mk_pc(1, "A1", "A2"),
        _mk_pc(2, "B1"),
    ]

    section_a = SectionNode(title="Sec A", path="ch/01-x/sec/01-a", page_start=1, page_end=1)
    section_b = SectionNode(title="Sec B", path="ch/01-x/sec/02-b", page_start=2, page_end=None)
    chapter = ChapterNode(
        title="Chap 1",
        path="ch/01-x",
        page_start=0,
        page_end=None,
        sections=[section_a, section_b],
    )

    sec_a_html = build_section_html(templates, section_a, contents, {})
    assert '<div class="pdf2foundry">' in sec_a_html
    assert "<p>A1</p>" in sec_a_html and "<p>A2</p>" in sec_a_html

    chap_html = build_chapter_html(templates, chapter, contents, {})
    # Container is present due to entry template
    assert '<div class="pdf2foundry">' in chap_html
    # Both section bodies present in order
    a_pos = chap_html.find("<p>A1</p>")
    b_pos = chap_html.find("<p>B1</p>")
    assert 0 <= a_pos < b_pos
    # Internal link marker targeting page 2 should be present
    assert 'data-p2f-link="page:2"' in chap_html
