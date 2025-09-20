from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pdf2foundry.ingest.docling_adapter import DoclingDocumentLike
from pdf2foundry.ingest.json_io import atomic_write_text, doc_to_json


@dataclass
class JsonOpts:
    """Options controlling DoclingDocument JSON cache behavior.

    Fields:
    - path: When provided via --docling-json PATH. If exists and is valid, load;
      if missing, convert then save to this path.
    - write: When True (from --write-docling-json), save after conversion when
      no explicit path is provided.
    - fallback_on_json_failure: When True, if JSON loading fails, fall back to
      conversion and (if applicable) overwrite cache.
    - pretty: Pretty-print JSON when writing.
    - default_path: Default destination path computed by CLI when write is True
      and no explicit path is set (typically dist/<mod-id>/sources/docling.json).
    """

    path: Path | None = None
    write: bool = False
    fallback_on_json_failure: bool = False
    pretty: bool = True
    default_path: Path | None = None


ProgressCallback = Callable[[str, dict[str, int | str]], None] | None


def _safe_emit(on_progress: ProgressCallback, event: str, payload: dict[str, int | str]) -> None:
    if on_progress is None:
        return
    from contextlib import suppress

    with suppress(Exception):
        on_progress(event, payload)


def ingest_docling(
    pdf_path: Path,
    json_opts: JsonOpts,
    on_progress: ProgressCallback = None,
) -> DoclingDocumentLike:
    """Load or convert a Docling document once, optionally saving JSON.

    Notes:
    - JSON load-from-cache is deferred until deterministic serializers (Task 13.3).
      For now, we always convert and optionally write JSON if supported by Docling.
    """
    from pdf2foundry.ingest.docling_adapter import run_docling_conversion

    _safe_emit(on_progress, "load_pdf", {"pdf": str(pdf_path)})
    doc = run_docling_conversion(pdf_path)

    # Emit success with page_count if available
    page_count = 0
    try:
        num_pages_fn = getattr(doc, "num_pages", None)
        if callable(num_pages_fn):
            page_count = int(num_pages_fn())
        else:
            page_count = int(getattr(doc, "num_pages", 0) or 0)
    except Exception:
        page_count = int(getattr(doc, "num_pages", 0) or 0)
    _safe_emit(on_progress, "load_pdf:success", {"pdf": str(pdf_path), "page_count": page_count})

    # Determine save path, if any
    json_path: Path | None = None
    if json_opts.path is not None:
        json_path = json_opts.path
    elif json_opts.write and json_opts.default_path is not None:
        json_path = json_opts.default_path

    if json_path is not None:
        try:
            json_text = doc_to_json(doc, pretty=json_opts.pretty)
            atomic_write_text(json_path, json_text)
            _safe_emit(on_progress, "docling_json:saved", {"path": str(json_path)})
        except Exception:
            # Ignore write failures for now; detailed handling in Task 13.4/13.8
            pass

    return doc


__all__ = ["JsonOpts", "ingest_docling"]
