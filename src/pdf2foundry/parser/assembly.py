from __future__ import annotations

from ..types import PageContent
from .html_convert import build_chapter_html, build_section_html
from .structure import ChapterNode
from .templating import Templates


def validate_scoped_html(html: str) -> bool:
    return '<div class="pdf2foundry">' in html or "<div class='pdf2foundry'>" in html


def assemble_html_outputs(
    templates: Templates,
    chapters: list[ChapterNode],
    contents: list[PageContent],
    tables_html_by_page: dict[int, str] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    chapters_html: dict[str, str] = {}
    sections_html: dict[str, str] = {}

    for chapter in chapters:
        ch_html = build_chapter_html(templates, chapter, contents, tables_html_by_page)
        if not validate_scoped_html(ch_html):
            raise ValueError(f"Chapter HTML missing scoped wrapper for path={chapter.path}")
        chapters_html[chapter.path] = ch_html

        for section in chapter.sections:
            sec_html = build_section_html(templates, section, contents, tables_html_by_page)
            if not validate_scoped_html(sec_html):
                raise ValueError(f"Section HTML missing scoped wrapper for path={section.path}")
            sections_html[section.path] = sec_html

    return chapters_html, sections_html
