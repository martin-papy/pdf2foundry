from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ..types import OutlineItem


@dataclass(frozen=True)
class SectionNode:
    title: str
    path: str
    page_start: int
    page_end: int | None


@dataclass(frozen=True)
class ChapterNode:
    title: str
    path: str
    page_start: int
    page_end: int | None
    sections: list[SectionNode]


def _slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    lowered = normalized.lower()
    replaced = re.sub(r"[^a-z0-9]+", "-", lowered)
    collapsed = re.sub(r"-+", "-", replaced).strip("-")
    return collapsed or "item"


def build_structure_map(
    outline: list[OutlineItem], *, chapter_level: int = 1, section_level: int = 2
) -> list[ChapterNode]:
    if not outline:
        return []

    chapters: list[ChapterNode] = []
    current_sections: list[SectionNode] = []
    chapter_index = 0
    section_index = 0

    # Track previous nodes for computing page_end
    prev_chapter: ChapterNode | None = None
    prev_section: SectionNode | None = None

    # Helper to finalize a section when a new sibling begins
    def close_prev_section(new_start: int) -> None:
        nonlocal prev_section
        if prev_section is None:
            return
        # Replace last section with updated page_end
        updated = SectionNode(
            title=prev_section.title,
            path=prev_section.path,
            page_start=prev_section.page_start,
            page_end=max(prev_section.page_start, new_start - 1),
        )
        current_sections[-1] = updated
        prev_section = updated

    # Helper to finalize a chapter when a new sibling begins
    def close_prev_chapter(new_start: int) -> None:
        nonlocal prev_chapter, current_sections
        if prev_chapter is None:
            return
        # Close any open section first relative to new chapter start
        close_prev_section(new_start)
        updated_chapter = ChapterNode(
            title=prev_chapter.title,
            path=prev_chapter.path,
            page_start=prev_chapter.page_start,
            page_end=max(prev_chapter.page_start, new_start - 1),
            sections=current_sections,
        )
        chapters[-1] = updated_chapter
        prev_chapter = updated_chapter

    # Per-parent slug counters to ensure unique slugs
    chapter_slug_counts: dict[str, int] = {}
    section_slug_counts: dict[str, int] = {}

    for item in outline:
        level = int(item.level)
        title = item.title.strip()
        start = int(item.page_index)
        if start < 0:
            continue

        # Normalize levels: anything below chapter_level starts a chapter;
        # anything >= section_level starts a section
        if level <= chapter_level:
            # New chapter
            # Finalize previous chapter range with this start
            close_prev_chapter(start)

            # Reset section state
            current_sections = []
            section_index = 0
            section_slug_counts = {}

            chapter_index += 1
            base_slug = _slugify(title)
            count = chapter_slug_counts.get(base_slug, 0)
            chapter_slug_counts[base_slug] = count + 1
            slug = base_slug if count == 0 else f"{base_slug}-{count+1}"
            chapter_path = f"ch/{chapter_index:02d}-{slug}"

            chapter = ChapterNode(
                title=title,
                path=chapter_path,
                page_start=start,
                page_end=None,
                sections=current_sections,
            )
            chapters.append(chapter)
            prev_chapter = chapter
            prev_section = None
        else:
            # Treat as section under current chapter
            if not chapters:
                # No chapter yet; implicitly create one for the first item
                chapter_index = 1
                implicit_title = title if title else "Chapter"
                base_slug = _slugify(implicit_title)
                chapter_slug_counts[base_slug] = 1
                chapter_path = f"ch/{chapter_index:02d}-{base_slug}"
                chapter = ChapterNode(
                    title=implicit_title,
                    path=chapter_path,
                    page_start=start,
                    page_end=None,
                    sections=current_sections,
                )
                chapters.append(chapter)
                prev_chapter = chapter

            # Close previous section with this start
            close_prev_section(start)

            section_index += 1
            base_slug = _slugify(title)
            count = section_slug_counts.get(base_slug, 0)
            section_slug_counts[base_slug] = count + 1
            slug = base_slug if count == 0 else f"{base_slug}-{count+1}"
            section_path = f"{chapters[-1].path}/sec/{section_index:02d}-{slug}"

            section = SectionNode(
                title=title,
                path=section_path,
                page_start=start,
                page_end=None,
            )
            current_sections.append(section)
            prev_section = section

    # Close trailing open nodes: leave page_end=None for the last section and chapter
    # Chapter end remains None for the last one by spec (until rendering/slicing)

    return chapters
