from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypedDict


class PdfDocumentLike(Protocol):
    """Minimal protocol for the PyMuPDF document object we rely on."""

    def get_toc(self, simple: bool = ...) -> list[list[object]]:  # pragma: no cover - typing
        ...


class PdfDocumentWithImages(Protocol):
    def extract_image(self, xref: int) -> dict[str, Any]:  # pragma: no cover - typing
        ...


class PdfPageLike(Protocol):
    def get_text(self, option: str) -> PageTextDict:  # pragma: no cover - typing
        ...

    def get_links(self) -> list[RawLinkDict]:  # pragma: no cover - typing
        ...

    def get_images(self, full: bool = ...) -> list[object]:  # pragma: no cover - typing
        ...


class PdfPagesLike(Protocol):
    def __len__(self) -> int:  # pragma: no cover - typing
        ...

    def __getitem__(self, index: int) -> PdfPageLike:  # pragma: no cover - typing
        ...


class SpanDict(TypedDict):
    text: str
    size: float


class LineDict(TypedDict):
    spans: list[SpanDict]


class BlockDict(TypedDict, total=False):
    lines: list[LineDict]
    type: int
    bbox: list[float]


class PageTextDict(TypedDict):
    blocks: list[BlockDict]


class RawLinkDict(TypedDict, total=False):
    # As returned by PyMuPDF page.get_links(): may contain 'uri' for external links
    # or 'page' for internal links; 'from' is the source rectangle
    uri: str
    page: int
    from_: list[float]


@dataclass(frozen=True)
class OutlineItem:
    """Represents a single outline/bookmark entry.

    - level: 1-based hierarchical level
    - title: text label of the entry
    - page_index: 0-based page index within the document
    """

    level: int
    title: str
    page_index: int


@dataclass(frozen=True)
class LinkAnnotation:
    page_index: int
    bbox: tuple[float, float, float, float]
    uri: str | None
    target_page_index: int | None


@dataclass(frozen=True)
class PageContent:
    page_index: int
    text_lines: list[str]
    links: list[LinkAnnotation]


@dataclass(frozen=True)
class ImageReference:
    page_index: int
    xref: int
    width: int | None
    height: int | None
    name: str | None
    ext: str | None


@dataclass(frozen=True)
class TableCandidate:
    page_index: int
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class TableRender:
    page_index: int
    bbox: tuple[float, float, float, float]
    html: str | None
    image_path: Path | None
    module_rel: str | None
    fallback: bool
