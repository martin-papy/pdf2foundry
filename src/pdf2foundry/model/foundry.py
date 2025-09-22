"""Foundry VTT v13 Journal models (subset) used by pdf2foundry.

These dataclasses model the minimal JSON we need to emit for Journal Entries
and text Pages. We include helpers to enforce the required structure and to
build flags for Compendium Folders compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class JournalPageText:
    """Text page for a Journal Entry.

    Fields align with Foundry JSON shape for `type: "text"` pages where
    `text.format == 1` (HTML) and `title.show == True`.
    """

    _id: str
    name: str
    title: dict[str, int | bool]
    text: dict[str, int | str]
    type: str = field(init=False, default="text")
    sort: int = 0
    flags: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Enforce invariants for text pages
        if self.type != "text":
            raise ValueError("JournalPageText.type must be 'text'")
        fmt = self.text.get("format")
        if fmt != 1:
            raise ValueError("JournalPageText.text.format must be 1 (HTML)")
        show = self.title.get("show")
        if show is not True:
            raise ValueError("JournalPageText.title.show must be True")
        level = self.title.get("level")
        if not isinstance(level, int) or level < 1:
            raise ValueError("JournalPageText.title.level must be >= 1")


def make_text_page(_id: str, name: str, level: int, text_html: str, sort: int = 0) -> JournalPageText:
    """Factory for a text page with HTML content and visible title."""

    return JournalPageText(
        _id=_id,
        name=name,
        title={"show": True, "level": level},
        text={"format": 1, "content": text_html},
        sort=sort,
    )


@dataclass(slots=True)
class JournalEntry:
    """Minimal Journal Entry model with text pages."""

    _id: str
    name: str
    pages: list[JournalPageText]
    folder: str | None = None
    flags: dict[str, object] = field(default_factory=dict)
    ownership: dict[str, int] = field(default_factory=lambda: {"default": 0})


def validate_entry(entry: JournalEntry) -> None:
    """Basic shape validation for a JournalEntry and its pages.

    Ensures: required fields present, page type/text/title invariants, and HTML format.
    """

    assert isinstance(entry._id, str) and entry._id
    assert isinstance(entry.name, str) and entry.name
    assert isinstance(entry.pages, list)
    for p in entry.pages:
        assert p.type == "text"
        assert p.text.get("format") == 1
        assert p.title.get("show") is True
        lvl = p.title.get("level")
        assert isinstance(lvl, int) and 1 <= lvl <= 3


def make_journal_entry(
    _id: str,
    name: str,
    pages: list[JournalPageText],
    folder: str | None = None,
    flags: dict[str, object] | None = None,
    ownership: dict[str, int] | None = None,
) -> JournalEntry:
    """Factory for a JournalEntry with sensible defaults."""

    return JournalEntry(
        _id=_id,
        name=name,
        pages=pages,
        folder=folder,
        flags=flags or {},
        ownership=ownership or {"default": 0},
    )


def build_compendium_folder_flags(
    folder_path: list[str], *, color: str | None = None, ns: str = "compendium-folders"
) -> dict[str, object]:
    """Build flags payload for Compendium Folders to encode inner folder path.

    Example output shape (under flags):
    { "compendium-folders": { "folderPath": ["My Book", "Chapter 1"], "color": "#AABBCC" } }
    """

    payload: dict[str, object] = {"folderPath": list(folder_path)}
    if color:
        payload["color"] = color
    return {ns: payload}
