from __future__ import annotations

from pathlib import Path

from pdf2foundry.parser import (
    PageContent,
    assemble_html_outputs,
    create_environment,
    validate_scoped_html,
)
from pdf2foundry.parser.structure import ChapterNode, SectionNode
from pdf2foundry.parser.templating import write_default_templates


def test_assemble_html_outputs_scoped(tmp_path: Path) -> None:
    write_default_templates(tmp_path)
    templates = create_environment(tmp_path)

    contents = [
        PageContent(page_index=0, text_lines=["Intro"], links=[]),
        PageContent(page_index=1, text_lines=["A"], links=[]),
        PageContent(page_index=2, text_lines=["B"], links=[]),
    ]

    s1 = SectionNode(title="A", path="ch/01-x/sec/01-a", page_start=1, page_end=1)
    s2 = SectionNode(title="B", path="ch/01-x/sec/02-b", page_start=2, page_end=None)
    ch = ChapterNode(title="Chap 1", path="ch/01-x", page_start=0, page_end=None, sections=[s1, s2])

    ch_map, sec_map = assemble_html_outputs(templates, [ch], contents, {})

    assert ch.path in ch_map and s1.path in sec_map and s2.path in sec_map
    assert validate_scoped_html(ch_map[ch.path])
    assert validate_scoped_html(sec_map[s1.path])
    assert validate_scoped_html(sec_map[s2.path])
