from __future__ import annotations

import base64
import re
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol

from pdf2foundry.model.content import HtmlPage, ImageAsset, LinkRef, ParsedContent, TableContent

ProgressCallback = Callable[[str, dict[str, int | str]], None] | None


def _safe_emit(on_progress: ProgressCallback, event: str, payload: dict[str, int | str]) -> None:
    if on_progress is None:
        return
    from contextlib import suppress

    with suppress(Exception):
        on_progress(event, payload)


class DocumentLike(Protocol):
    def num_pages(self) -> int: ...
    def export_to_html(self, **kwargs: object) -> str: ...


def _write_base64_image(data_b64: str, dest_dir: Path, filename: str) -> str:
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        data_bytes = base64.b64decode(data_b64)
    except Exception:
        data_bytes = b""
    (dest_dir / filename).write_bytes(data_bytes)
    return filename


def _extract_images_from_html(
    html: str, page_no: int, assets_dir: Path, name_prefix: str
) -> tuple[str, list[ImageAsset]]:
    pattern = re.compile(r'src="data:image/(?P<ext>[^;\"]+);base64,(?P<data>[^\"]+)"')
    images: list[ImageAsset] = []
    counter = {"n": 0}

    def repl(m: re.Match[str]) -> str:
        counter["n"] += 1
        raw_ext = m.group("ext").lower().strip()
        ext = "jpg" if raw_ext == "jpeg" else ("svg" if "svg" in raw_ext else raw_ext)
        fname = f"{name_prefix}_img_{counter['n']:04d}.{ext}"
        _write_base64_image(m.group("data"), assets_dir, fname)
        rel = f"assets/{fname}"
        images.append(ImageAsset(src=rel, page_no=page_no, name=fname))
        return f'src="{rel}"'

    updated = pattern.sub(repl, html)
    return updated, images


def _detect_links(html: str, page_no: int) -> list[LinkRef]:
    links: list[LinkRef] = []
    for m in re.finditer(r'<a\s+[^>]*href="(?P<href>[^"]+)"', html, re.IGNORECASE):
        href = m.group("href")
        kind: Literal["external", "internal"] = (
            "external" if href.startswith(("http://", "https://", "mailto:")) else "internal"
        )
        links.append(LinkRef(kind=kind, source_page=page_no, target=href))
    return links


def extract_semantic_content(
    doc: DocumentLike, out_assets: Path, table_mode: str, on_progress: ProgressCallback = None
) -> ParsedContent:
    """Extract per-page HTML, images, simple tables, and links from a Docling document.

    - For v1, tables are not reconstructed from structure; we leave placeholders
      for auto vs image-only handling and will expand in a later iteration.
    - Images embedded as base64 are extracted to files and srcs rewritten.
    - Links are collected from anchor tags.
    """

    # Determine page count
    try:
        page_count = int(doc.num_pages())
    except Exception:
        page_count = int(getattr(doc, "num_pages", 0) or 0)

    _safe_emit(on_progress, "content:start", {"page_count": page_count})

    try:
        from docling_core.types.doc.document import ContentLayer

        include_layers = {ContentLayer.BODY, ContentLayer.BACKGROUND, ContentLayer.FURNITURE}
    except Exception:  # pragma: no cover - optional dependency path
        include_layers = None

    pages: list[HtmlPage] = []
    images: list[ImageAsset] = []
    tables: list[TableContent] = []
    links: list[LinkRef] = []

    # Per-page export with images embedded for reliable extraction
    for p in range(page_count):
        page_no = p + 1
        try:
            if include_layers is not None:
                html = doc.export_to_html(
                    page_no=page_no,
                    split_page_view=False,
                    included_content_layers=include_layers,
                )
            else:
                html = doc.export_to_html(
                    page_no=page_no,
                    split_page_view=False,
                )
        except Exception:
            html = ""

        _safe_emit(on_progress, "page:exported", {"page_no": page_no})

        # Multi-column detection and flattening (no-op + warning in v1)
        try:
            from pdf2foundry.transform.layout import flatten_page_html

            html = flatten_page_html(html, doc, page_no)
        except Exception:
            # If transform fails for any reason, proceed with original HTML
            pass

        # Extract images
        html, page_images = _extract_images_from_html(
            html, page_no, out_assets, f"page-{page_no:04d}"
        )
        images.extend(page_images)
        if page_images:
            _safe_emit(
                on_progress, "images:extracted", {"page_no": page_no, "count": len(page_images)}
            )

        # Tables (v1: we do not transform; leave for later)
        if table_mode == "image-only":
            # Placeholder: record an intent; actual region rasterization to be added later
            pass
        else:
            # auto mode placeholder
            pass

        # Links
        page_links = _detect_links(html, page_no)
        links.extend(page_links)
        if page_links:
            _safe_emit(
                on_progress, "links:detected", {"page_no": page_no, "count": len(page_links)}
            )

        pages.append(HtmlPage(html=html, page_no=page_no))

    _safe_emit(
        on_progress,
        "content:finalized",
        {"pages": len(pages), "images": len(images), "tables": len(tables)},
    )

    return ParsedContent(
        pages=pages, images=images, tables=tables, links=links, assets_dir=out_assets
    )
