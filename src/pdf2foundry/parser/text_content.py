from __future__ import annotations

from collections.abc import Callable
from typing import cast

from ..types import BlockDict, LinkAnnotation, PageContent, PdfPagesLike


def _normalize_span_text(text: str) -> str:
    return " ".join(text.split()).strip()


def extract_page_content(
    document: PdfPagesLike,
    on_progress: Callable[[int], None] | None = None,
) -> list[PageContent]:
    results: list[PageContent] = []
    for page_index in range(len(document)):
        page = document[page_index]
        page_dict = page.get_text("dict")

        ordered_blocks: list[BlockDict] = []
        for block in page_dict.get("blocks", []):
            if block.get("type", 0) != 0:
                continue
            ordered_blocks.append(block)
        ordered_blocks.sort(
            key=lambda b: (
                float(b.get("bbox", [0.0, 0.0])[1]),
                float(b.get("bbox", [0.0, 0.0, 0.0, 0.0])[0]),
            )
        )

        text_lines: list[str] = []
        for block in ordered_blocks:
            lines = block.get("lines", [])
            for line in lines:
                spans = line.get("spans", [])
                merged = " ".join(
                    _normalize_span_text(span.get("text", ""))
                    for span in spans
                    if _normalize_span_text(span.get("text", ""))
                )
                if merged:
                    text_lines.append(merged)

        raw_links = page.get_links()
        links: list[LinkAnnotation] = []
        for link in raw_links:
            rect_seq = cast(list[float], link.get("from_") or link.get("from") or [])
            bbox = (
                float(rect_seq[0]) if len(rect_seq) > 0 else 0.0,
                float(rect_seq[1]) if len(rect_seq) > 1 else 0.0,
                float(rect_seq[2]) if len(rect_seq) > 2 else 0.0,
                float(rect_seq[3]) if len(rect_seq) > 3 else 0.0,
            )
            uri = link.get("uri") if isinstance(link.get("uri"), str) else None
            target_page = link.get("page") if isinstance(link.get("page"), int) else None
            links.append(
                LinkAnnotation(
                    page_index=page_index,
                    bbox=bbox,
                    uri=uri,
                    target_page_index=target_page,
                )
            )

        results.append(PageContent(page_index=page_index, text_lines=text_lines, links=links))
        if on_progress is not None:
            on_progress(page_index)

    return results
