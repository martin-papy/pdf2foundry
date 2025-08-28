from __future__ import annotations

from pdf2foundry.parser import OutlineItem, build_structure_map


def test_build_structure_map_basic_ranges_and_paths() -> None:
    outline = [
        OutlineItem(level=1, title="Chap 1", page_index=0),
        OutlineItem(level=2, title="Sec A", page_index=1),
        OutlineItem(level=2, title="Sec B", page_index=3),
        OutlineItem(level=1, title="Chap 2", page_index=5),
    ]

    chapters = build_structure_map(outline)

    assert len(chapters) == 2

    c1 = chapters[0]
    assert c1.title == "Chap 1"
    assert c1.page_start == 0
    assert c1.page_end == 4
    assert c1.path.startswith("ch/01-")
    assert len(c1.sections) == 2
    s1, s2 = c1.sections
    assert s1.title == "Sec A" and s1.page_start == 1 and s1.page_end == 2
    assert "/sec/01-" in s1.path and s1.path.startswith(c1.path)
    assert s2.title == "Sec B" and s2.page_start == 3 and s2.page_end == 4
    assert "/sec/02-" in s2.path and s2.path.startswith(c1.path)

    c2 = chapters[1]
    assert c2.title == "Chap 2"
    assert c2.page_start == 5
    assert c2.page_end is None
    assert c2.path.startswith("ch/02-")
    assert not c2.sections


def test_build_structure_map_empty_outline() -> None:
    assert build_structure_map([]) == []


def test_build_structure_map_level_gaps_treated_as_sections() -> None:
    outline = [
        OutlineItem(level=1, title="C1", page_index=0),
        OutlineItem(level=3, title="Deep", page_index=2),
    ]
    chapters = build_structure_map(outline)
    assert len(chapters) == 1
    c1 = chapters[0]
    assert len(c1.sections) == 1
    s = c1.sections[0]
    assert s.title == "Deep" and s.page_start == 2 and s.page_end is None


def test_build_structure_map_duplicate_titles_unique_slugs() -> None:
    outline = [
        OutlineItem(level=1, title="Intro", page_index=0),
        OutlineItem(level=1, title="Intro", page_index=5),
    ]
    chs = build_structure_map(outline)
    assert len(chs) == 2
    assert chs[0].path != chs[1].path
