from __future__ import annotations

from pdf2foundry.model.id_utils import make_entry_id, make_page_id, sha1_16_hex


def test_sha1_16_hex_stability() -> None:
    v1 = sha1_16_hex("abc")
    v2 = sha1_16_hex("abc")
    assert v1 == v2
    assert len(v1) == 16
    assert all(c in "0123456789abcdef" for c in v1)


def test_make_entry_and_page_ids() -> None:
    entry_id = make_entry_id("mod", ["book", "chapter-1"])
    # Same inputs produce same id
    assert entry_id == make_entry_id("mod", ["book", "chapter-1"])

    page_id1 = make_page_id("mod", ["book", "chapter-1"], "Overview")
    page_id2 = make_page_id("mod", ["book", "chapter-1"], "Overview")
    assert page_id1 == page_id2
    # Different page names yield different ids
    assert page_id1 != make_page_id("mod", ["book", "chapter-1"], "Usage")
