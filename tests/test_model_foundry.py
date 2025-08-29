from __future__ import annotations

import pytest

from pdf2foundry.model.foundry import (
    JournalPageText,
    build_compendium_folder_flags,
    make_journal_entry,
    make_text_page,
)


def test_make_text_page_and_entry() -> None:
    page = make_text_page(_id="p1", name="Overview", level=1, text_html="<p>Hi</p>")
    assert page.type == "text"
    assert page.text["format"] == 1
    assert page.title["show"] is True
    entry = make_journal_entry(_id="e1", name="Chapter 1", pages=[page])
    assert entry._id == "e1"
    assert entry.pages[0].name == "Overview"
    assert entry.ownership.get("default") == 0


def test_page_invariants_violations() -> None:
    with pytest.raises(ValueError):
        JournalPageText(
            _id="p2",
            name="Bad",
            title={"show": False, "level": 1},
            text={"format": 1, "content": ""},
        )
    with pytest.raises(ValueError):
        JournalPageText(
            _id="p3",
            name="BadFmt",
            title={"show": True, "level": 1},
            text={"format": 2, "content": ""},
        )
    with pytest.raises(ValueError):
        JournalPageText(
            _id="p4",
            name="BadLevel",
            title={"show": True, "level": 0},
            text={"format": 1, "content": ""},
        )


def test_build_compendium_folder_flags() -> None:
    flags = build_compendium_folder_flags(["Book", "Chapter 1"], color="#AABBCC")
    assert "compendium-folders" in flags
    cf = flags["compendium-folders"]
    assert isinstance(cf, dict)
    assert cf["folderPath"] == ["Book", "Chapter 1"]
    assert cf["color"] == "#AABBCC"
