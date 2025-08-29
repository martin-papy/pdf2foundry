"""Core document data structures used by the parsing pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class OutlineNode:
    """Represents a logical section in the document.

    - level is 1-based: 1 = chapter, 2 = section, etc.
    - page_start/page_end use 1-based page indices; page_end may be None for the
      last span.
    - path contains sanitized hierarchical segments (slugified titles) used for
      deterministic ID building.
    """

    title: str
    level: int
    page_start: int
    page_end: int | None
    children: list[OutlineNode] = field(default_factory=list)
    path: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ParsedDocument:
    """Top-level parsed structure returned by the ingestion stage."""

    page_count: int
    outline: list[OutlineNode]
