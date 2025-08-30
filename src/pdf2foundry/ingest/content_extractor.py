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


def _rewrite_and_copy_referenced_images(
    html: str, page_no: int, assets_dir: Path, name_prefix: str
) -> tuple[str, list[ImageAsset]]:
    """Copy non-embedded image sources to assets and rewrite src to assets/.

    Handles local file paths, file:// URIs, and relative paths; leaves http(s) and
    data URIs untouched.
    """
    pattern = re.compile(r'src="(?P<src>(?!data:|https?://|mailto:|assets/)[^"]+)"', re.IGNORECASE)
    assets_dir.mkdir(parents=True, exist_ok=True)
    images: list[ImageAsset] = []
    counter = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal counter
        raw = m.group("src")
        src_path = raw
        if raw.lower().startswith("file://"):
            from urllib.parse import urlparse as _urlparse

            src_path = _urlparse(raw).path or ""
        p = Path(src_path)
        if not p.exists():
            return m.group(0)
        counter += 1
        fname = p.name if p.name else f"{name_prefix}_img_{counter:04d}.bin"
        dest = assets_dir / fname
        try:
            dest.write_bytes(p.read_bytes())
        except Exception:
            return m.group(0)
        rel = f"assets/{fname}"
        images.append(ImageAsset(src=rel, page_no=page_no, name=fname))
        return f'src="{rel}"'

    updated = pattern.sub(repl, html)
    return updated, images


def _rasterize_table_placeholder(dest_dir: Path, filename: str) -> str:
    """Write a tiny 1x1 PNG placeholder to dest_dir/filename and return filename.

    We avoid heavy dependencies during tests; real rasterization can replace this later.
    """

    # 1x1 transparent PNG (short constant split to satisfy line length)
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJ"
        "TYQAAAAASUVORK5CYII="
    )
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        data = base64.b64decode(png_b64)
    except Exception:
        data = b""
    (dest_dir / filename).write_bytes(data)
    return filename


def _process_tables(
    html: str, page_no: int, assets_dir: Path, table_mode: str, name_prefix: str
) -> tuple[str, list[TableContent]]:
    """Process <table> blocks.

    - auto: leave HTML tables intact; record TableContent(kind="html")
    - image-only: replace each table with an <img src="assets/..."> placeholder and
      write a tiny PNG file; record TableContent(kind="image")
    """

    tables: list[TableContent] = []
    # Simple, robust-enough pattern to capture table blocks
    pattern = re.compile(r"<table[\s\S]*?</table>", re.IGNORECASE)
    counter = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal counter
        counter += 1
        block = m.group(0)
        if table_mode == "image-only":
            fname = f"{name_prefix}_table_{counter:04d}.png"
            _rasterize_table_placeholder(assets_dir, fname)
            tables.append(TableContent(kind="image", page_no=page_no, html=None, image_name=fname))
            return f'<img src="assets/{fname}">'
        # auto mode: keep as HTML
        tables.append(TableContent(kind="html", page_no=page_no, html=block, image_name=None))
        return block

    updated = pattern.sub(repl, html)
    return updated, tables


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

    image_mode: object | None = None
    try:
        # Optional advanced options when docling-core is present
        from docling_core.types.doc import ImageRefMode
        from docling_core.types.doc.document import ContentLayer

        include_layers = {ContentLayer.BODY, ContentLayer.BACKGROUND, ContentLayer.FURNITURE}
        image_mode = ImageRefMode.EMBEDDED
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
                if image_mode is not None:
                    html = doc.export_to_html(
                        page_no=page_no,
                        split_page_view=False,
                        included_content_layers=include_layers,
                        image_mode=image_mode,
                    )
                else:
                    html = doc.export_to_html(
                        page_no=page_no,
                        split_page_view=False,
                        included_content_layers=include_layers,
                    )
            else:
                if image_mode is not None:
                    html = doc.export_to_html(
                        page_no=page_no,
                        split_page_view=False,
                        image_mode=image_mode,
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

        # Extract images (embedded base64)
        html, page_images = _extract_images_from_html(
            html, page_no, out_assets, f"page-{page_no:04d}"
        )
        images.extend(page_images)
        # Copy referenced images (local paths)
        html, ref_images = _rewrite_and_copy_referenced_images(
            html, page_no, out_assets, f"page-{page_no:04d}"
        )
        images.extend(ref_images)
        if ref_images:
            _safe_emit(on_progress, "images:copied", {"page_no": page_no, "count": len(ref_images)})
        if page_images:
            _safe_emit(
                on_progress, "images:extracted", {"page_no": page_no, "count": len(page_images)}
            )

        # Tables
        html, page_tables = _process_tables(
            html, page_no, out_assets, table_mode, f"page-{page_no:04d}"
        )
        tables.extend(page_tables)

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
