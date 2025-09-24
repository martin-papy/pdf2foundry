"""JSON serialization and deserialization for Docling documents.

This module provides utilities for converting Docling documents to/from JSON
format for caching purposes. It handles both native Docling serialization
(when available) and fallback serialization for compatibility.

Key features:
- Deterministic JSON serialization with sorted keys
- Native Docling serialization support when available
- Fallback serialization for minimal document structure
- Atomic file writing to prevent corruption
- Document reconstruction from JSON with validation

The serialization strategy prioritizes native Docling methods but provides
robust fallbacks to ensure caching works across different Docling versions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol, cast


class _DocumentLikeForJson(Protocol):  # pragma: no cover - interface
    def num_pages(self) -> int: ...
    def export_to_html(self, **kwargs: object) -> str: ...


def doc_to_json(doc: object, *, pretty: bool = True) -> str:
    """Serialize a Docling-like document to deterministic JSON.

    Strategy:
    - Prefer native to_json() if available
    - Normalize to a Python object, then dump with sorted keys
    - Fallback: serialize minimal shape if native unavailable
    """
    # 1) Native path if available
    to_json = getattr(doc, "to_json", None)
    if callable(to_json):
        try:
            native = to_json()
            if isinstance(native, str):
                try:
                    obj = json.loads(native)
                except Exception:
                    # Already a string; best-effort normalization by wrapping
                    obj = {"_native": native}
            else:
                obj = native
            return json.dumps(
                obj,
                ensure_ascii=False,
                sort_keys=True,
                indent=2 if pretty else None,
            )
        except Exception:
            # Fall through to fallback serializer
            pass

    # 2) Fallback: comprehensive structure with per-page HTML content
    num_pages = 0
    try:
        num_pages_fn = getattr(doc, "num_pages", None)
        num_pages = int(num_pages_fn()) if callable(num_pages_fn) else int(getattr(doc, "num_pages", 0) or 0)
    except Exception:
        num_pages = 0

    # Extract HTML content for each page to preserve in cache
    pages_html = []
    export_to_html = getattr(doc, "export_to_html", None)
    if callable(export_to_html) and num_pages > 0:
        for page_no in range(num_pages):
            try:
                html = export_to_html(page_no=page_no, split_page_view=False)
                pages_html.append(html)
            except Exception:
                # If individual page export fails, store empty content for that page
                pages_html.append("")

    obj = {
        "schema_version": 1,
        "num_pages": num_pages,
        "pages_html": pages_html,  # Store per-page HTML content
    }
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        indent=2 if pretty else None,
    )


def doc_from_json(text: str) -> _DocumentLikeForJson:
    """Deserialize a Docling-like document from JSON.

    - Prefer Docling's native from_json() when importable
    - Fallback to a minimal lightweight implementation
    """
    try:
        # Try native Docling API if available
        from docling.document import Document as _DoclingDocument

        from_json = getattr(_DoclingDocument, "from_json", None)
        if callable(from_json):
            return cast(_DocumentLikeForJson, from_json(text))
    except Exception:
        # Native path not available; continue to fallback
        pass

    data: Any
    try:
        data = json.loads(text)
    except Exception:
        data = {"num_pages": 0}

    class _JsonDoc:
        def __init__(self, pages: int, pages_html: list[str] | None = None) -> None:
            self._pages = pages
            self._pages_html = pages_html or []

        def num_pages(self) -> int:  # pragma: no cover - trivial
            return self._pages

        def export_to_html(self, page_no: int = 0, **_: object) -> str:
            """Export cached HTML content for the specified page."""
            if 0 <= page_no < len(self._pages_html):
                return self._pages_html[page_no]
            return ""  # Return empty string for invalid page numbers

    pages = 0
    pages_html: list[str] = []
    try:
        if isinstance(data, dict):
            if "num_pages" in data and isinstance(data["num_pages"], int):
                pages = int(data["num_pages"])
            elif "pages" in data and isinstance(data["pages"], list):
                pages = len(data["pages"])

            # Load cached HTML content if available
            if "pages_html" in data and isinstance(data["pages_html"], list):
                pages_html = [str(html) for html in data["pages_html"]]
    except Exception:
        pages = 0
        pages_html = []

    return cast(_DocumentLikeForJson, _JsonDoc(pages, pages_html))


def atomic_write_text(path: Path, data: str, *, encoding: str = "utf-8") -> None:
    """Atomically write text to a file by writing to a temp file then replacing.

    Ensures parent directories exist and minimizes risk of partial writes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding=encoding, dir=str(path.parent), delete=False) as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


__all__ = [
    "atomic_write_text",
    "doc_from_json",
    "doc_to_json",
]
