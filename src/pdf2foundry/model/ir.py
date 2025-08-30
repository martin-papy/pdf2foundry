"""Intermediate representation (IR) for downstream processing.

This IR combines the structural outline with merged HTML content so later
stages (Foundry mapping, deterministic IDs) can operate on a clean model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class SectionIR:
    id_path: list[str]
    level: int
    title: str
    page_start: int
    page_end: int | None
    html: str


@dataclass(slots=True)
class ChapterIR:
    id_path: list[str]
    title: str
    sections: list[SectionIR] = field(default_factory=list)


@dataclass(slots=True)
class DocumentIR:
    mod_id: str
    title: str
    chapters: list[ChapterIR] = field(default_factory=list)
    assets_dir: Path | None = None
    pack_name: str | None = None
