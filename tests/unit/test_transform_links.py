from __future__ import annotations

from pdf2foundry.transform.links import build_anchor_lookup, rewrite_internal_anchors_to_uuid


def test_rewrite_internal_anchors_to_uuid() -> None:
    pages = [("Overview", "p1"), ("Key Concepts", "p2")]
    lookup = build_anchor_lookup(pages)
    entry_id = "e1"
    html = (
        '<p>See <a href="#overview">Overview</a> and '
        '<a href="#key-concepts">the next</a>. Also <a href="#missing">x</a>.</p>'
    )
    out = rewrite_internal_anchors_to_uuid(html, entry_id, lookup)
    assert "@UUID[JournalEntry.e1.JournalEntryPage.p1]{Overview}" in out
    assert "@UUID[JournalEntry.e1.JournalEntryPage.p2]{the next}" in out
    # unresolved becomes just label
    assert ">x</a>" not in out
