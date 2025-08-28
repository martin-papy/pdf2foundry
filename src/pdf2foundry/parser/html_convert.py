from __future__ import annotations

import html
from collections.abc import Iterable

from ..types import LinkAnnotation, PageContent
from .structure import ChapterNode, SectionNode
from .templating import Templates


def slice_content_by_range(
    contents: list[PageContent], start: int, end: int | None
) -> list[PageContent]:
    if start < 0:
        raise ValueError("start must be non-negative")
    if end is not None and end < start:
        raise ValueError("end must be >= start")
    return [c for c in contents if c.page_index >= start and (end is None or c.page_index <= end)]


def lines_to_html(lines: Iterable[str]) -> str:
    return "\n".join(f"<p>{html.escape(line)}</p>" for line in lines)


def annotate_internal_links(
    html: str, links: list[LinkAnnotation] | None, page_offset: int = 0
) -> str:
    # Insert a leading marker for each internal link target on this page
    if not links:
        return html
    seen: set[int] = set()
    prefix = ""
    for link in links:
        # Skip external links
        if link.uri:
            continue
        if link.target_page_index is None:
            continue
        resolved = int(link.target_page_index)
        if resolved in seen:
            continue
        seen.add(resolved)
        prefix += f'<sup data-p2f-link="page:{resolved}"></sup>'
    if not prefix:
        return html
    # Insert before the first paragraph if possible
    idx = html.find("<p>")
    if idx == -1:
        return prefix + html
    return html[:idx] + prefix + html[idx:]


def _build_section_body(
    section: SectionNode,
    contents: list[PageContent],
    tables_html_by_page: dict[int, str] | None = None,
) -> str:
    per_page = slice_content_by_range(contents, section.page_start, section.page_end)
    fragments: list[str] = []
    for pc in per_page:
        body_html = lines_to_html(pc.text_lines)
        if tables_html_by_page and pc.page_index in tables_html_by_page:
            body_html += "\n" + tables_html_by_page[pc.page_index]
        body_html = annotate_internal_links(body_html, pc.links, page_offset=pc.page_index)
        fragments.append(body_html)
    return "\n".join(fragments)


def build_section_html(
    templates: Templates,
    section: SectionNode,
    contents: list[PageContent],
    tables_html_by_page: dict[int, str] | None = None,
) -> str:
    body = _build_section_body(section, contents, tables_html_by_page)
    return templates.render_page({"title": section.title, "body": body, "description": None})


def build_chapter_html(
    templates: Templates,
    chapter: ChapterNode,
    contents: list[PageContent],
    tables_html_by_page: dict[int, str] | None = None,
) -> str:
    parts: list[str] = []
    for section in chapter.sections:
        parts.append(_build_section_body(section, contents, tables_html_by_page))
    body = "\n".join(parts)

    # Prepend internal link markers found on chapter pages not covered by any section range
    covered_pages: set[int] = set()
    for s in chapter.sections:
        for pc in slice_content_by_range(contents, s.page_start, s.page_end):
            covered_pages.add(pc.page_index)

    chapter_pages = [
        pc
        for pc in contents
        if pc.page_index >= chapter.page_start
        and (chapter.page_end is None or pc.page_index <= chapter.page_end)
    ]
    non_section_pages = [pc for pc in chapter_pages if pc.page_index not in covered_pages]

    markers: list[str] = []
    seen_targets: set[int] = set()
    for pc in non_section_pages:
        for link in pc.links:
            if link.uri:
                continue
            if link.target_page_index is None:
                continue
            tgt = int(link.target_page_index)
            if tgt in seen_targets:
                continue
            seen_targets.add(tgt)
            markers.append(f'<sup data-p2f-link="page:{tgt}"></sup>')

    if markers:
        body = "".join(markers) + body

    return templates.render_page({"title": chapter.title, "body": body, "description": None})
