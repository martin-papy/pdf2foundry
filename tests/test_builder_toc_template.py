from __future__ import annotations

from pdf2foundry.builder.toc import TocEntryRef, TocPageRef
from pdf2foundry.builder.toc_template import render_toc_html
from pdf2foundry.model.id_utils import make_entry_id, make_page_id


def test_render_toc_html_contains_uuid_links_and_order() -> None:
    mod_id = "mod"
    ch_path1 = ["book", "chapter-1"]
    ch1_id = make_entry_id(mod_id, ch_path1)
    p1_id = make_page_id(mod_id, ch_path1, "Overview")
    p2_id = make_page_id(mod_id, ch_path1, "Usage")

    ch1 = TocEntryRef(
        entry_id=ch1_id,
        entry_name="Chapter 1 — Introduction",
        pages=[
            TocPageRef(entry_id=ch1_id, page_id=p1_id, label="Overview"),
            TocPageRef(entry_id=ch1_id, page_id=p2_id, label="Usage"),
        ],
    )

    html = render_toc_html([ch1], title="Contents")
    assert '<div class="pdf2foundry toc">' in html
    assert "<h1>Contents</h1>" in html
    # Contains both UUID links in order
    idx1 = html.find(f"@UUID[JournalEntry.{ch1_id}.JournalEntryPage.{p1_id}]{'{'}Overview{'}'}")
    idx2 = html.find(f"@UUID[JournalEntry.{ch1_id}.JournalEntryPage.{p2_id}]{'{'}Usage{'}'}")
    assert idx1 != -1 and idx2 != -1 and idx1 < idx2


def test_render_toc_html_handles_empty_chapter_pages() -> None:
    ch = TocEntryRef(entry_id="deadbeefdeadbeef", entry_name="Empty", pages=[])
    html = render_toc_html([ch])
    assert "<h2>Empty</h2>" in html
    # No <ul> list is rendered for empty pages
    assert "<ul>" not in html.split("<h2>Empty</h2>")[1]
