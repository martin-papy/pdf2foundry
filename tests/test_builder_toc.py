from __future__ import annotations

from pdf2foundry.builder.toc import (
    build_toc_entry_from_entries,
    build_uuid_link,
    collect_toc_metadata,
    extract_uuid_targets_from_html,
    validate_toc_links,
)
from pdf2foundry.model.foundry import make_journal_entry, make_text_page
from pdf2foundry.model.id_utils import make_entry_id, make_page_id


def test_collect_toc_metadata_orders_pages_and_preserves_ids() -> None:
    mod_id = "mod"
    entry_path = ["book", "chapter-1"]
    entry_id = make_entry_id(mod_id, entry_path)
    page1_id = make_page_id(mod_id, entry_path, "Overview")
    page2_id = make_page_id(mod_id, entry_path, "Usage")

    p2 = make_text_page(page2_id, "Usage", level=1, text_html="<div>Usage</div>", sort=200)
    p1 = make_text_page(page1_id, "Overview", level=1, text_html="<div>Overview</div>", sort=100)
    entry = make_journal_entry(_id=entry_id, name="Chapter 1 — Introduction", pages=[p2, p1])

    toc = collect_toc_metadata([entry])
    assert len(toc) == 1
    e = toc[0]
    assert e.entry_id == entry_id
    assert e.entry_name == "Chapter 1 — Introduction"

    # Sorted by `sort` ascending
    assert [p.page_id for p in e.pages] == [page1_id, page2_id]
    assert [p.label for p in e.pages] == ["Overview", "Usage"]


def test_build_uuid_link_formatting() -> None:
    mod_id = "mod"
    entry_path = ["book", "chapter-1"]
    entry_id = make_entry_id(mod_id, entry_path)
    page_id = make_page_id(mod_id, entry_path, "Overview")

    link = build_uuid_link(entry_id, page_id, "Overview")
    assert link == f"@UUID[JournalEntry.{entry_id}.JournalEntryPage.{page_id}]{{Overview}}"


def test_collect_toc_metadata_handles_entry_without_pages() -> None:
    entry = make_journal_entry(_id="deadbeefdeadbeef", name="Empty", pages=[])
    toc = collect_toc_metadata([entry])
    assert len(toc) == 1
    assert toc[0].entry_id == "deadbeefdeadbeef"
    assert toc[0].entry_name == "Empty"
    assert toc[0].pages == []


def test_build_toc_entry_from_entries_sets_flags_and_renders_links() -> None:
    mod_id = "mod"
    ch_path = ["book", "chapter-1"]
    ch_id = make_entry_id(mod_id, ch_path)
    p1_id = make_page_id(mod_id, ch_path, "Overview")
    p2_id = make_page_id(mod_id, ch_path, "Usage")

    p1 = make_text_page(p1_id, "Overview", level=1, text_html="<div>Overview</div>", sort=100)
    p2 = make_text_page(p2_id, "Usage", level=1, text_html="<div>Usage</div>", sort=200)
    ch = make_journal_entry(_id=ch_id, name="Chapter 1 — Introduction", pages=[p2, p1])

    toc_entry = build_toc_entry_from_entries(
        mod_id, [ch], title="Table of Contents", folder_path=["My Book"]
    )

    # Deterministic IDs for TOC entry and its page
    expected_entry_id = make_entry_id(mod_id, ["toc"])
    expected_page_id = make_page_id(mod_id, ["toc"], "Table of Contents")
    assert toc_entry._id == expected_entry_id
    assert len(toc_entry.pages) == 1
    assert toc_entry.pages[0]._id == expected_page_id

    # Canonical metadata present (v13 doesn't require compendium-folders dependency)
    mod_ns = toc_entry.flags.get(mod_id)
    assert isinstance(mod_ns, dict)
    assert mod_ns.get("canonicalPath") == ["toc"]
    assert mod_ns.get("canonicalPathStr") == "toc"
    assert mod_ns.get("nameSlug") == "toc"

    # Page flags contain canonical path info
    p_ns = toc_entry.pages[0].flags.get(mod_id)
    assert isinstance(p_ns, dict)
    assert p_ns.get("canonicalPath") == ["toc", "Table of Contents"]
    assert p_ns.get("canonicalPathStr") == "toc/Table of Contents"
    assert p_ns.get("sectionOrder") == 0

    # Rendered content contains @UUID links for underlying chapter pages
    content_val = toc_entry.pages[0].text["content"]
    html = str(content_val)
    pat1 = f"@UUID[JournalEntry.{ch_id}.JournalEntryPage.{p1_id}]{{Overview}}"
    pat2 = f"@UUID[JournalEntry.{ch_id}.JournalEntryPage.{p2_id}]{{Usage}}"
    assert pat1 in html
    assert pat2 in html


def test_extract_uuid_targets_from_html() -> None:
    html = (
        "<div>"
        "@UUID[JournalEntry.aaaa1111bbbb2222.JournalEntryPage.cccc3333dddd4444]{One}"
        " and "
        "@UUID[JournalEntry.eeee5555ffff6666.JournalEntryPage.7777aaaa8888bbbb]{Two}"
        "</div>"
    )
    targets = extract_uuid_targets_from_html(html)
    assert targets == [
        ("aaaa1111bbbb2222", "cccc3333dddd4444", "One"),
        ("eeee5555ffff6666", "7777aaaa8888bbbb", "Two"),
    ]


def test_validate_toc_links_reports_missing_targets() -> None:
    # Build TOC for an entry with a single valid page
    mod_id = "mod"
    ch_path = ["book", "chapter-1"]
    ch_id = make_entry_id(mod_id, ch_path)
    p_id = make_page_id(mod_id, ch_path, "Overview")
    p = make_text_page(p_id, "Overview", level=1, text_html="<div>Overview</div>", sort=100)
    ch = make_journal_entry(_id=ch_id, name="Ch", pages=[p])

    toc_entry = build_toc_entry_from_entries(mod_id, [ch])
    # Corrupt the HTML to include a bad entry and bad page
    bad_html = str(toc_entry.pages[0].text["content"]) + " "
    bad_html += f"@UUID[JournalEntry.BADENTRY.JournalEntryPage.{p_id}]{{Bad Entry}}"
    bad_html += " "
    bad_html += f"@UUID[JournalEntry.{ch_id}.JournalEntryPage.BADPAGE]{{Bad Page}}"
    toc_entry.pages[0].text["content"] = bad_html

    issues = validate_toc_links(toc_entry, [ch])
    assert any("missing entry" in msg for msg in issues)
    assert any("missing page" in msg for msg in issues)
