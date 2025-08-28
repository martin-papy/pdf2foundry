from __future__ import annotations

from collections.abc import Callable
from typing import cast

from ..types import (
    BlockDict,
    LineInfo,
    LinkAnnotation,
    PageContent,
    PdfPagesLike,
    SpanInfo,
)


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
        raw_lines: list[LineInfo] = []
        for block in ordered_blocks:
            lines = block.get("lines", [])
            for line in lines:
                spans = line.get("spans", [])
                normalized_spans = [_normalize_span_text(span.get("text", "")) for span in spans]
                merged = " ".join(s for s in normalized_spans if s)
                if merged:
                    text_lines.append(merged)
                    # Capture representative geometry/metrics for this line
                    bbox_list = line.get("bbox", [])
                    bbox = (
                        (
                            float(bbox_list[0]) if len(bbox_list) > 0 else 0.0,
                            float(bbox_list[1]) if len(bbox_list) > 1 else 0.0,
                            float(bbox_list[2]) if len(bbox_list) > 2 else 0.0,
                            float(bbox_list[3]) if len(bbox_list) > 3 else 0.0,
                        )
                        if bbox_list
                        else None
                    )

                    span_infos: list[SpanInfo] = []
                    size_candidates: list[float] = []
                    for i, span in enumerate(spans):
                        txt = (
                            normalized_spans[i]
                            if i < len(normalized_spans)
                            else _normalize_span_text(span.get("text", ""))
                        )
                        size_val = span.get("size")
                        size_f = float(size_val) if isinstance(size_val, int | float) else None
                        if isinstance(size_f, float):
                            size_candidates.append(size_f)
                        span_infos.append(SpanInfo(text=txt, size=size_f))

                    line_size = max(size_candidates) if size_candidates else None
                    raw_lines.append(
                        LineInfo(text=merged, bbox=bbox, size=line_size, spans=span_infos)
                    )

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

        results.append(
            PageContent(
                page_index=page_index,
                text_lines=text_lines,
                links=links,
                raw_lines=raw_lines or None,
            )
        )
        if on_progress is not None:
            on_progress(page_index)

    return results
