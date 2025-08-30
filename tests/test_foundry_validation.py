from __future__ import annotations

from pdf2foundry.builder.ir_builder import build_document_ir, map_ir_to_foundry_entries
from pdf2foundry.model.content import HtmlPage, ParsedContent
from pdf2foundry.model.document import OutlineNode, ParsedDocument
from pdf2foundry.model.foundry import validate_entry


def test_validate_entry_basic() -> None:
    section = OutlineNode(
        title="Overview", level=2, page_start=1, page_end=1, children=[], path=["ch", "ov"]
    )
    chapter = OutlineNode(
        title="Chapter", level=1, page_start=1, page_end=1, children=[section], path=["ch"]
    )
    parsed_doc = ParsedDocument(page_count=1, outline=[chapter])
    pages = [HtmlPage(html="<p>x</p>", page_no=1)]
    ir = build_document_ir(parsed_doc, ParsedContent(pages=pages), mod_id="m", doc_title="D")
    entries = map_ir_to_foundry_entries(ir)
    assert entries
    validate_entry(entries[0])
