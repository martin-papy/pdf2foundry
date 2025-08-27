from __future__ import annotations

from typing import Any

from pdf2foundry.parser import (
    OutlineItem,
    detect_headings_heuristic,
    extract_image_bytes,
    extract_images,
    extract_outline,
    extract_page_content,
    save_images,
)


class DocWithToc:
    def __init__(self, toc: list[list[object]]):
        self._toc = toc

    def get_toc(self, simple: bool = True) -> list[list[object]]:  # pragma: no cover - trivial
        return self._toc


def test_extract_outline_normalizes_entries(caplog: Any) -> None:
    doc = DocWithToc(
        [
            [1, "Chapter 1 — Intro", 1],
            [2, "Overview", 2],
            [1, "Chapter 2 — Advanced", 5],
        ]
    )

    with caplog.at_level("WARNING"):
        items = extract_outline(doc)

    # No warnings expected because TOC exists
    assert not [r for r in caplog.records if r.levelname == "WARNING"]

    assert items == [
        OutlineItem(level=1, title="Chapter 1 — Intro", page_index=0),
        OutlineItem(level=2, title="Overview", page_index=1),
        OutlineItem(level=1, title="Chapter 2 — Advanced", page_index=4),
    ]


def test_extract_outline_warns_when_missing(caplog: Any) -> None:
    doc = DocWithToc([])
    with caplog.at_level("WARNING"):
        items = extract_outline(doc)

    assert items == []
    warnings = [r.message for r in caplog.records if r.levelname == "WARNING"]
    assert any("No bookmarks found" in str(msg) for msg in warnings)


class FakePage:
    def __init__(
        self,
        blocks: list[dict[str, Any]],
        links: list[dict[str, Any]] | None = None,
        images: list[object] | None = None,
    ):
        self._blocks = blocks
        self._links = links or []
        self._images = images or []

    def get_text(self, option: str) -> dict[str, Any]:  # pragma: no cover - trivial
        assert option == "dict"
        return {"blocks": self._blocks}

    def get_links(self) -> list[dict[str, Any]]:  # pragma: no cover - trivial
        return self._links

    def get_images(self, full: bool = True) -> list[object]:  # pragma: no cover - trivial
        return self._images


class FakeDoc:
    def __init__(self, pages: list[FakePage]):
        self._pages = pages

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._pages)

    def __getitem__(self, index: int) -> Any:  # pragma: no cover - trivial
        return self._pages[index]


class FakeDocWithImages(FakeDoc):
    def __init__(self, pages: list[FakePage], images_by_xref: dict[int, dict[str, Any]]):
        super().__init__(pages)
        self._images_by_xref = images_by_xref

    def extract_image(self, xref: int) -> dict[str, Any]:  # pragma: no cover - trivial
        return self._images_by_xref.get(int(xref), {"image": b"", "ext": "bin"})


def test_detect_headings_heuristic_picks_largest_titles_per_page() -> None:
    # Page 0 has two spans; only the larger font should be used
    page0 = FakePage(
        [
            {"lines": [{"spans": [{"text": "Intro", "size": 18.0}]}]},
            {"lines": [{"spans": [{"text": "overview", "size": 12.0}]}]},
        ]
    )
    # Page 1 one heading span
    page1 = FakePage([{"lines": [{"spans": [{"text": "Chapter 2", "size": 16.0}]}]}])

    doc = FakeDoc([page0, page1])
    items = detect_headings_heuristic(doc, max_levels=2)

    # Global sizes are 18.0 (level 1) and 16.0 (level 2); 12.0 ignored
    assert items == [
        OutlineItem(level=1, title="Intro", page_index=0),
        OutlineItem(level=2, title="Chapter 2", page_index=1),
    ]


def test_extract_page_content_flattens_blocks_and_collects_links() -> None:
    page = FakePage(
        [
            {
                "type": 0,
                "bbox": [10, 10, 100, 30],
                "lines": [{"spans": [{"text": "Hello", "size": 12.0}]}],
            },
            {
                "type": 0,
                "bbox": [10, 40, 100, 60],
                "lines": [{"spans": [{"text": "World", "size": 12.0}]}],
            },
        ],
        links=[
            {"from_": [10, 10, 20, 20], "uri": "https://example.com"},
            {"from_": [10, 40, 20, 50], "page": 3},
        ],
    )
    doc = FakeDoc([page])
    contents = extract_page_content(doc)
    assert len(contents) == 1
    pc = contents[0]
    assert pc.page_index == 0
    assert pc.text_lines == ["Hello", "World"]
    assert len(pc.links) == 2
    assert pc.links[0].uri == "https://example.com"
    assert pc.links[1].target_page_index == 3


def test_extract_images_collects_xrefs() -> None:
    img_tuple = (42, None, 640, 480, 8, None, None, "Im1")
    page = FakePage([], images=[img_tuple])
    doc = FakeDoc([page])
    imgs = extract_images(doc)
    assert len(imgs) == 1
    ref = imgs[0]
    assert ref.page_index == 0
    assert ref.xref == 42
    assert ref.width == 640 and ref.height == 480


def test_extract_image_bytes_returns_bytes_and_ext() -> None:
    doc = FakeDocWithImages([], {7: {"image": b"abc123", "ext": "png"}})
    data, ext = extract_image_bytes(doc, 7)
    assert data == b"abc123"
    assert ext == "png"


def test_save_images_writes_files_and_paths(tmp_path: Any) -> None:
    page = FakePage([], images=[(7, None, 10, 10, 8, None, None, "Im")])
    doc = FakeDocWithImages([page], {7: {"image": b"data", "ext": "jpg"}})
    refs = extract_images(doc)
    results = save_images(doc, refs, tmp_path, "mod-x")
    assert len(results) == 1
    _, dest, module_rel = results[0]
    assert dest.exists() and dest.read_bytes() == b"data"
    assert module_rel.startswith("modules/mod-x/assets/")
