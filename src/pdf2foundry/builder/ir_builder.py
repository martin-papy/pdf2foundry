from __future__ import annotations

from collections.abc import Callable

from pdf2foundry.model.content import HtmlPage, ParsedContent
from pdf2foundry.model.document import OutlineNode, ParsedDocument
from pdf2foundry.model.foundry import (
    JournalEntry,
    JournalPageText,
    build_compendium_folder_flags,
    make_journal_entry,
    make_text_page,
)
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


# --- Foundry mapping (Task 4.2): Map IR to Foundry Journal models ---


def map_ir_to_foundry_entries(
    ir: DocumentIR,
    *,
    deterministic_ids: bool = True,
) -> list[JournalEntry]:
    """Map a DocumentIR into Foundry JournalEntry objects with text pages.

    Notes
    - ID assignment is left deterministic and stable in later tasks; for now we
      pass through placeholder IDs derived from id_path joined (caller can
      replace with SHA1s). Keeping shape stable unblocks subsequent tasks.
    - Folder flags will be set in a later subtask (4.3). This function focuses
      on hierarchy mapping (Entry -> Pages) and page sorting.
    """

    entries: list[JournalEntry] = []

    for chapter_index, chapter in enumerate(ir.chapters, start=1):
        if deterministic_ids:
            entry_id = "|".join([ir.mod_id, *chapter.id_path])
        else:
            entry_id = "-".join(chapter.id_path)
        pages: list[JournalPageText] = []

        # Derive deterministic display name for chapter
        ch_name_raw = (chapter.title or "").strip()
        ch_name = ch_name_raw or f"Untitled Chapter {chapter_index}"

        # Assign sort in large gaps to allow later inserts
        sort_base = 1000
        seen_page_names: dict[str, int] = {}
        entry_canonical: list[str] = [*chapter.id_path]
        for i, sec in enumerate(chapter.sections):
            page_id = (
                "|".join([ir.mod_id, *sec.id_path]) if deterministic_ids else "-".join(sec.id_path)
            )
            sort = sort_base * (i + 1)
            # Deterministic page display name with sibling de-duplication
            raw_name = (sec.title or "").strip() or f"Untitled Section {i + 1}"
            count = seen_page_names.get(raw_name, 0)
            seen_page_names[raw_name] = count + 1
            page_name = raw_name if count == 0 else f"{raw_name} ({count + 1})"

            page = make_text_page(
                _id=page_id,
                name=page_name,
                level=min(3, max(1, sec.level - 1)),  # clamp to 1..3
                text_html=sec.html,
                sort=sort,
            )
            # Add canonical path flags for deterministic ID assignment
            canonical_path = [*entry_canonical, page_name]
            page.flags.setdefault(ir.mod_id, {})
            mod_ns = page.flags[ir.mod_id]
            if isinstance(mod_ns, dict):
                mod_ns["canonicalPath"] = canonical_path
                mod_ns["canonicalPathStr"] = "/".join(canonical_path)
                mod_ns["sectionOrder"] = i
            pages.append(page)

        # Encode folder path for Compendium Folders: [Book Title, Chapter Title]
        entry_flags = build_compendium_folder_flags([ir.title, ch_name])
        # Extend with module namespace for canonical paths
        entry_flags.setdefault(ir.mod_id, {})
        mod_flags = entry_flags[ir.mod_id]
        if isinstance(mod_flags, dict):
            mod_flags["canonicalPath"] = entry_canonical
            mod_flags["canonicalPathStr"] = "/".join(entry_canonical)
            mod_flags["nameSlug"] = entry_canonical[-1] if entry_canonical else ""

        entry = make_journal_entry(
            _id=entry_id,
            name=ch_name,
            pages=pages,
            folder=None,
            flags=entry_flags,
            ownership={"default": 0},
        )
        entries.append(entry)

    return entries
