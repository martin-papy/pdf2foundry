from __future__ import annotations

from collections.abc import Callable

from pdf2foundry.model.content import HtmlPage, ParsedContent
from pdf2foundry.model.document import OutlineNode, ParsedDocument
from pdf2foundry.model.ir import ChapterIR, DocumentIR, SectionIR

ProgressCallback = Callable[[str, dict[str, int | str]], None] | None


def _safe_emit(on_progress: ProgressCallback, event: str, payload: dict[str, int | str]) -> None:
    if on_progress is None:
        return
    from contextlib import suppress

    with suppress(Exception):
        on_progress(event, payload)


def _slugify(text: str) -> str:
    import re

    s = re.sub(r"[^A-Za-z0-9]+", "-", text.lower()).strip("-")
    s = re.sub(r"-+", "-", s)
    return s or "untitled"


def _unique_path(
    segments: list[str], seen_at_level: dict[int, dict[str, int]], level: int
) -> list[str]:
    # Ensure stable uniqueness per hierarchy level using ordinal suffixes
    base = segments[-1]
    level_seen = seen_at_level.setdefault(level, {})
    count = level_seen.get(base, 0)
    if count == 0:
        level_seen[base] = 1
        return segments
    new_last = f"{base}-{count+1}"
    level_seen[base] = count + 1
    return [*segments[:-1], new_last]


def _merge_html(pages: list[HtmlPage], start: int, end: int | None) -> str:
    end_page = end if end is not None else (pages[-1].page_no if pages else start)
    parts: list[str] = []
    for p in pages:
        if start <= p.page_no <= end_page:
            parts.append(p.html)
    return "\n\n".join(parts)


def build_document_ir(
    parsed_doc: ParsedDocument,
    parsed_content: ParsedContent,
    mod_id: str,
    doc_title: str,
    on_progress: ProgressCallback = None,
) -> DocumentIR:
    _safe_emit(on_progress, "ir:start", {"doc_title": doc_title})

    # Helper to gather all sections under a chapter node
    def sections_for(chapter_node: OutlineNode) -> list[OutlineNode]:
        result: list[OutlineNode] = []
        stack: list[OutlineNode] = chapter_node.children[:]
        while stack:
            n = stack.pop(0)
            if n.level >= 2:
                result.append(n)
            stack[0:0] = n.children
        return result

    chapters: list[ChapterIR] = []
    seen_at_level: dict[int, dict[str, int]] = {}

    # Root outline nodes are top-level candidates; we treat only level==1 as chapters.
    for node in parsed_doc.outline:
        if node.level != 1:
            continue
        chap_seg = [_slugify(seg) for seg in (node.path[:1] or [_slugify(node.title)])]
        chap_id_path = _unique_path(chap_seg, seen_at_level, level=1)

        chapter_ir = ChapterIR(id_path=chap_id_path, title=node.title, sections=[])
        _safe_emit(on_progress, "chapter:assembled", {"chapter": node.title})

        for sec in sections_for(node):
            sec_segs = [*chap_id_path, _slugify(sec.title)]
            sec_id_path = _unique_path(sec_segs, seen_at_level, level=sec.level)
            html = _merge_html(parsed_content.pages, sec.page_start, sec.page_end)
            section_ir = SectionIR(
                id_path=sec_id_path,
                level=sec.level,
                title=sec.title,
                page_start=sec.page_start,
                page_end=sec.page_end,
                html=html,
            )
            chapter_ir.sections.append(section_ir)
            _safe_emit(
                on_progress,
                "section:assembled",
                {"chapter": node.title, "section": sec.title},
            )

        chapters.append(chapter_ir)

    total_sections = sum(len(c.sections) for c in chapters)
    _safe_emit(on_progress, "ir:finalized", {"chapters": len(chapters), "sections": total_sections})

    return DocumentIR(
        mod_id=mod_id, title=doc_title, chapters=chapters, assets_dir=parsed_content.assets_dir
    )
