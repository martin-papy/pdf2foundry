"""Single-pass PDF ingestion with JSON caching support.

This module implements the unified single-pass ingestion design for PDF2Foundry,
where each PDF is converted to a Docling document exactly once per run, with
optional JSON caching to avoid re-conversion on subsequent runs.

Key features:
- Single-pass conversion: PDF → DoclingDocument (once per run)
- JSON caching: Save/load DoclingDocument to/from JSON for faster re-runs
- Fallback handling: Graceful fallback to conversion if JSON loading fails
- Validation: Ensure loaded documents have required methods and reasonable data
- Progress reporting: Emit events during conversion and loading

The main entry point is `ingest_docling()` which handles the complete workflow
of loading from cache (if available) or converting from PDF, with optional
cache writing for future runs.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pdf2foundry.ingest.docling_adapter import DoclingDocumentLike
from pdf2foundry.ingest.json_io import atomic_write_text, doc_to_json

logger = logging.getLogger(__name__)


class JsonLoadError(Exception):
    """Raised when JSON file cannot be loaded or parsed."""

    def __init__(self, path: Path, cause: Exception | None = None) -> None:
        self.path = path
        self.cause = cause
        msg = f"Failed to load JSON from {path}"
        if cause:
            msg += f": {cause}"
        msg += ". Consider deleting the cache file and re-running."
        super().__init__(msg)


class JsonValidationError(Exception):
    """Raised when loaded JSON doesn't represent a valid DoclingDocument."""

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        msg = f"Invalid DoclingDocument JSON at {path}: {reason}. " "Consider deleting the cache file and re-running."
        super().__init__(msg)


class ConversionError(Exception):
    """Raised when PDF to DoclingDocument conversion fails."""

    def __init__(self, pdf_path: Path, cause: Exception | None = None) -> None:
        self.pdf_path = pdf_path
        self.cause = cause
        msg = f"Failed to convert PDF {pdf_path}"
        if cause:
            msg += f": {cause}"
        super().__init__(msg)


def validate_doc(doc: DoclingDocumentLike) -> None:
    """Validate that a DoclingDocument has required fields and reasonable values.

    Args:
        doc: The document to validate

    Raises:
        JsonValidationError: If the document fails validation checks
    """
    # Check that we have a non-zero page count
    try:
        num_pages_fn = getattr(doc, "num_pages", None)
        page_count = int(num_pages_fn()) if callable(num_pages_fn) else int(getattr(doc, "num_pages", 0) or 0)
    except Exception as e:
        raise JsonValidationError(Path("<unknown>"), f"Cannot determine page count: {e}") from e

    if page_count <= 0:
        raise JsonValidationError(Path("<unknown>"), f"Invalid page count: {page_count}")

    # Check that export_to_html method exists and is callable
    if not hasattr(doc, "export_to_html") or not callable(doc.export_to_html):
        raise JsonValidationError(Path("<unknown>"), "Missing or invalid 'export_to_html' method")

    # Basic smoke test - try to call export_to_html to ensure it doesn't immediately fail
    try:
        html_output = doc.export_to_html()
        if not isinstance(html_output, str):
            raise JsonValidationError(Path("<unknown>"), "export_to_html() must return a string")
    except Exception as e:
        raise JsonValidationError(Path("<unknown>"), f"export_to_html() method failed: {e}") from e


def load_json_file(path: Path) -> str:
    """Load and parse JSON file, validating basic JSON syntax.

    Args:
        path: Path to the JSON file

    Returns:
        The raw JSON text as a string

    Raises:
        JsonLoadError: If the file cannot be read or parsed as JSON
    """
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        raise JsonLoadError(path, e) from e

    # Validate that it's parseable JSON
    try:
        json.loads(text)
    except json.JSONDecodeError as e:
        raise JsonLoadError(path, e) from e

    return text


def try_load_doc_from_json(path: Path, fallback_on_failure: bool) -> tuple[DoclingDocumentLike | None, list[str]]:
    """Attempt to load a DoclingDocument from JSON with optional fallback.

    Args:
        path: Path to the JSON file
        fallback_on_failure: If True, return None and warnings on failure;
                           if False, raise exceptions on failure

    Returns:
        Tuple of (document or None, list of warning messages)

    Raises:
        JsonLoadError: If fallback_on_failure is False and loading fails
        JsonValidationError: If fallback_on_failure is False and validation fails
    """
    warnings: list[str] = []

    try:
        # Load and parse the JSON file
        json_text = load_json_file(path)

        # Convert JSON to DoclingDocument
        from pdf2foundry.ingest.json_io import doc_from_json

        doc = doc_from_json(json_text)

        # Validate the document
        validate_doc(doc)

        logger.info("Successfully loaded DoclingDocument from cache: %s", path)
        return doc, warnings

    except (JsonLoadError, JsonValidationError) as e:
        if fallback_on_failure:
            warning_msg = f"Failed to load DoclingDocument from {path}: {e}. Will fall back to conversion."
            warnings.append(warning_msg)
            logger.warning(warning_msg)
            return None, warnings
        else:
            # Re-raise with path context for validation errors
            if isinstance(e, JsonValidationError) and e.path == Path("<unknown>"):
                raise JsonValidationError(path, e.reason) from e
            raise


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

    Behavior:
    - If json_opts.path is provided and exists: try to load from JSON. On failure,
      fall back to conversion regardless of json_opts.fallback_on_json_failure
      (convenience semantics).
    - If json_opts.path is provided and does not exist: convert and then save to
      that path.
    - Else if json_opts.write and default_path provided: convert and save to the
      default path.
    - Else: convert only.
    """
    from pdf2foundry.ingest.docling_adapter import run_docling_conversion

    # Convenience load path handling when explicit --docling-json PATH is provided
    if json_opts.path is not None and json_opts.path.exists():
        # Always allow fallback for convenience mode
        doc, warnings = try_load_doc_from_json(json_opts.path, fallback_on_failure=True)
        if doc is not None:
            # Emit loaded event with page count
            try:
                num_pages_fn = getattr(doc, "num_pages", None)
                page_count = int(num_pages_fn()) if callable(num_pages_fn) else int(getattr(doc, "num_pages", 0) or 0)
            except Exception:
                page_count = int(getattr(doc, "num_pages", 0) or 0)
            _safe_emit(
                on_progress,
                "ingest:loaded_from_cache",
                {"path": str(json_opts.path), "page_count": page_count},
            )
            return doc
        # If load failed with fallback, emit a warning event and continue to convert
        _safe_emit(
            on_progress,
            "ingest:cache_load_failed",
            {"path": str(json_opts.path)},
        )

    # Conversion branch
    _safe_emit(on_progress, "ingest:converting", {"pdf": str(pdf_path)})

    try:
        doc = run_docling_conversion(pdf_path)
    except Exception as e:
        # Emit conversion failure event
        _safe_emit(on_progress, "ingest:conversion_failed", {"pdf": str(pdf_path), "error": str(e)})
        raise

    # Emit success with page_count if available
    page_count = 0
    try:
        num_pages_fn = getattr(doc, "num_pages", None)
        page_count = int(num_pages_fn()) if callable(num_pages_fn) else int(getattr(doc, "num_pages", 0) or 0)
    except Exception:
        page_count = int(getattr(doc, "num_pages", 0) or 0)
    _safe_emit(on_progress, "ingest:converted", {"pdf": str(pdf_path), "page_count": page_count})

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
            _safe_emit(on_progress, "ingest:saved_to_cache", {"path": str(json_path)})
        except Exception:
            # Ignore write failures for now; detailed handling in Task 13.4
            pass

    return doc


__all__ = [
    "ConversionError",
    "JsonLoadError",
    "JsonOpts",
    "JsonValidationError",
    "ingest_docling",
    "load_json_file",
    "try_load_doc_from_json",
    "validate_doc",
]
