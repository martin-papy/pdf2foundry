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

    # 2) Fallback: minimal deterministic structure
    num_pages = 0
    try:
        num_pages_fn = getattr(doc, "num_pages", None)
        num_pages = int(num_pages_fn()) if callable(num_pages_fn) else int(getattr(doc, "num_pages", 0) or 0)
    except Exception:
        num_pages = 0

    obj = {
        "schema_version": 1,
        "num_pages": num_pages,
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
        def __init__(self, pages: int) -> None:
            self._pages = pages

        def num_pages(self) -> int:  # pragma: no cover - trivial
            return self._pages

        def export_to_html(self, **_: object) -> str:  # pragma: no cover - placeholder
            return ""

    pages = 0
    try:
        if isinstance(data, dict):
            if "num_pages" in data and isinstance(data["num_pages"], int):
                pages = int(data["num_pages"])
            elif "pages" in data and isinstance(data["pages"], list):
                pages = len(data["pages"])
    except Exception:
        pages = 0

    return cast(_DocumentLikeForJson, _JsonDoc(pages))


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
