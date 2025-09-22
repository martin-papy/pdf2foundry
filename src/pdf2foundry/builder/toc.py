from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from pdf2foundry.builder.toc_template import render_toc_html
from pdf2foundry.model.foundry import (
    JournalEntry,
    JournalPageText,
    build_compendium_folder_flags,
    make_journal_entry,
    make_text_page,
)
from pdf2foundry.model.id_utils import make_entry_id, make_page_id


@dataclass(slots=True)
class TocPageRef:
    entry_id: str
    page_id: str
    label: str


@dataclass(slots=True)
class TocEntryRef:
    entry_id: str
    entry_name: str
    pages: list[TocPageRef]


def build_uuid_link(entry_id: str, page_id: str, label: str) -> str:
    """Build Foundry @UUID link string for a journal page.

    Format: @UUID[JournalEntry.<entryId>.JournalEntryPage.<pageId>]{<label>}
    """

    return f"@UUID[JournalEntry.{entry_id}.JournalEntryPage.{page_id}]{{{label}}}"


def collect_toc_metadata(entries: Iterable[JournalEntry]) -> list[TocEntryRef]:
    """Collect TOC metadata from mapped JournalEntry objects.

    - Preserves entry order from the iterable
    - Sorts pages by their `sort` value ascending (stable)
    - Captures deterministic IDs and human-readable labels
    """

    toc: list[TocEntryRef] = []
    for entry in entries:
        # Defensive sort: ensure stable page order by `sort`
        pages_sorted: list[JournalPageText] = sorted(entry.pages, key=lambda p: p.sort)
        page_refs: list[TocPageRef] = [TocPageRef(entry_id=entry._id, page_id=p._id, label=p.name) for p in pages_sorted]
        toc.append(TocEntryRef(entry_id=entry._id, entry_name=entry.name, pages=page_refs))
    return toc


def build_toc_entry_from_entries(
    mod_id: str,
    entries: list[JournalEntry],
    *,
    title: str = "Table of Contents",
    folder_path: list[str] | None = None,
) -> JournalEntry:
    """Build a TOC JournalEntry document from existing chapter entries.

    - Computes deterministic IDs using canonical path ["toc"] and the page name
    - Renders HTML with @UUID links using collected metadata
    """

    toc_meta = collect_toc_metadata(entries)
    html = render_toc_html(toc_meta, title=title)

    entry_canonical = ["toc"]
    entry_id = make_entry_id(mod_id, entry_canonical)
    page_id = make_page_id(mod_id, entry_canonical, title)
    page = make_text_page(page_id, title, level=1, text_html=html, sort=1000)

    # Flags: compendium folders at specified folder path (default root-level)
    entry_flags: dict[str, object] = {}
    if folder_path:
        entry_flags.update(build_compendium_folder_flags(folder_path))

    # Add canonical metadata under module namespace for deterministic paths
    entry_flags.setdefault(mod_id, {})
    mod_ns = entry_flags[mod_id]
    if isinstance(mod_ns, dict):
        mod_ns["canonicalPath"] = entry_canonical
        mod_ns["canonicalPathStr"] = "/".join(entry_canonical)
        mod_ns["nameSlug"] = entry_canonical[-1]

    # Mirror canonical info to page flags
    page.flags.setdefault(mod_id, {})
    page_ns = page.flags[mod_id]
    if isinstance(page_ns, dict):
        page_ns["canonicalPath"] = [*entry_canonical, title]
        page_ns["canonicalPathStr"] = "/".join([*entry_canonical, title])
        page_ns["sectionOrder"] = 0

    return make_journal_entry(_id=entry_id, name=title, pages=[page], flags=entry_flags)


_UUID_PATTERN = re.compile(
    r"@UUID\[JournalEntry\.(?P<entry>[A-Za-z0-9]+)\.JournalEntryPage\.(?P<page>[A-Za-z0-9]+)\]\{(?P<label>[\s\S]*?)\}",
    re.IGNORECASE,
)


def extract_uuid_targets_from_html(html: str) -> list[tuple[str, str, str]]:
    """Extract (entry_id, page_id, label) triples from @UUID links in HTML."""

    results: list[tuple[str, str, str]] = []
    for m in _UUID_PATTERN.finditer(html or ""):
        results.append((m.group("entry"), m.group("page"), m.group("label")))
    return results


def validate_toc_links(toc_entry: JournalEntry, entries: list[JournalEntry]) -> list[str]:
    """Validate that all @UUID links in the TOC page resolve to actual entries/pages.

    Returns a list of warning strings for any missing targets.
    """

    issues: list[str] = []
    if not toc_entry.pages:
        return issues
    content_val = toc_entry.pages[0].text.get("content", "")
    html = content_val if isinstance(content_val, str) else str(content_val)
    targets = extract_uuid_targets_from_html(html)
    entry_to_pages: dict[str, set[str]] = {e._id: {p._id for p in e.pages} for e in entries}
    for entry_id, page_id, label in targets:
        pages = entry_to_pages.get(entry_id)
        if pages is None:
            issues.append(f"'{label}' targets missing entry {entry_id}")
        elif page_id not in pages:
            issues.append(f"'{label}' targets missing page {page_id} in entry {entry_id}")
    return issues
