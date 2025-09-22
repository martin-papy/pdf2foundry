"""Docling environment probing utilities.

This module provides a lightweight probe to verify whether Docling and
Docling Core are available and minimally usable in the current Python
environment without performing heavy PDF processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DoclingProbeReport:
    """Structured result of the Docling environment probe."""

    has_docling: bool
    has_docling_core: bool
    docling_version: str | None
    docling_core_version: str | None
    can_construct_converter: bool
    has_core_types: bool
    notes: list[str] = field(default_factory=list)


def _get_package_version(pkg_name: str, module: object | None) -> str | None:
    """Best-effort retrieval of a package version.

    Tries importlib.metadata first, then falls back to module.__version__.
    """

    try:
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as pkg_version

        try:
            return pkg_version(pkg_name)
        except PackageNotFoundError:
            pass
    except Exception:
        # importlib.metadata not available or unexpected error
        pass

    if module is not None:
        # Fallback to module attribute if available
        return getattr(module, "__version__", None)
    return None


def probe_docling() -> DoclingProbeReport:
    """Probe the runtime for Docling and Docling Core availability.

    - Attempts to import `docling` and `docling_core`
    - Collects package versions
    - Tries to construct a minimal `DocumentConverter` with OCR disabled
    - Optionally imports a few core types from `docling_core`
    """

    notes: list[str] = []

    # Presence flags and versions
    has_docling = False
    has_docling_core = False
    docling_version: str | None = None
    docling_core_version: str | None = None

    try:
        import docling as _docling

        has_docling = True
        docling_version = _get_package_version("docling", _docling)
    except Exception as exc:  # pragma: no cover - purely environmental
        notes.append(f"docling import failed: {exc}")

    try:
        import docling_core as _docling_core

        has_docling_core = True
        # PyPI name uses hyphen, import uses underscore
        docling_core_version = _get_package_version("docling-core", _docling_core)
    except Exception as exc:  # pragma: no cover - purely environmental
        notes.append(f"docling-core import failed: {exc}")

    can_construct_converter = False
    if has_docling:
        try:
            # Light-weight construction without doing any conversion
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import (
                PdfPipelineOptions,
            )
            from docling.document_converter import (
                DocumentConverter,
                PdfFormatOption,
            )

            pipe_opts = PdfPipelineOptions(
                # Keep it light; do not trigger OCR or image generation
                do_ocr=False,
                generate_picture_images=False,
                generate_page_images=False,
            )
            _ = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipe_opts)})
            can_construct_converter = True
        except Exception as exc:  # pragma: no cover - environmental or version issues
            notes.append(f"Failed to construct DocumentConverter: {exc}")

    has_core_types = False
    if has_docling_core:
        try:
            # Import modules, then getattr to avoid mypy attr-defined issues
            import importlib

            _doc_types = importlib.import_module("docling_core.types.doc")
            _doc_doc = importlib.import_module("docling_core.types.doc.document")

            ImageRefMode = getattr(_doc_types, "ImageRefMode", None)
            ContentLayer = getattr(_doc_doc, "ContentLayer", None)

            if ImageRefMode is not None and ContentLayer is not None:
                has_core_types = True
            else:
                notes.append("docling-core types missing: ImageRefMode or ContentLayer not found")
        except Exception as exc:  # pragma: no cover - environmental or version issues
            notes.append(f"docling-core types import failed: {exc}")

    return DoclingProbeReport(
        has_docling=has_docling,
        has_docling_core=has_docling_core,
        docling_version=docling_version,
        docling_core_version=docling_core_version,
        can_construct_converter=can_construct_converter,
        has_core_types=has_core_types,
        notes=notes,
    )


def report_is_ok(report: DoclingProbeReport) -> bool:
    """Return True when the environment appears suitable for Docling usage."""

    return report.has_docling and report.has_docling_core and report.can_construct_converter and report.has_core_types


def format_report_lines(report: DoclingProbeReport) -> list[str]:
    """Format a human-friendly multi-line report."""

    def flag(ok: bool) -> str:
        return "✅" if ok else "❌"

    lines: list[str] = [
        "Docling Environment Check:",
        f"- Docling installed: {flag(report.has_docling)}"
        + (f" (version {report.docling_version})" if report.docling_version else ""),
        f"- Docling Core installed: {flag(report.has_docling_core)}"
        + (f" (version {report.docling_core_version})" if report.docling_core_version else ""),
        f"- Can construct DocumentConverter: {flag(report.can_construct_converter)}",
        f"- Core types available (ImageRefMode/ContentLayer): {flag(report.has_core_types)}",
    ]

    if report.notes:
        lines.append("- Notes:")
        lines.extend([f"  • {n}" for n in report.notes])

    return lines


__all__ = [
    "DoclingProbeReport",
    "format_report_lines",
    "probe_docling",
    "report_is_ok",
]
