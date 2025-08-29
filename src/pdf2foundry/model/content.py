"""Content data structures for semantic extraction (HTML, images, tables, links)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(slots=True)
class HtmlPage:
    html: str
    page_no: int  # 1-based


@dataclass(slots=True)
class ImageAsset:
    # Final resolved src in the page HTML (e.g., "assets/<file>")
    src: str
    page_no: int  # 1-based
    name: str


@dataclass(slots=True)
class TableContent:
    kind: Literal["html", "image"]
    page_no: int  # 1-based
    html: str | None = None
    image_name: str | None = None


@dataclass(slots=True)
class LinkRef:
    kind: Literal["internal", "external"]
    source_page: int  # 1-based
    target: str


@dataclass(slots=True)
class ParsedContent:
    pages: list[HtmlPage] = field(default_factory=list)
    images: list[ImageAsset] = field(default_factory=list)
    tables: list[TableContent] = field(default_factory=list)
    links: list[LinkRef] = field(default_factory=list)
    assets_dir: Path | None = None
