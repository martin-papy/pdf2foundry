from __future__ import annotations

import sys
import types
from typing import Any

from pdf2foundry.docling_env import format_report_lines, probe_docling, report_is_ok


def _shim_docling(success: bool = True) -> None:
    # Base packages
    class _DoclingMod(types.ModuleType):
        __version__: str

    mod_docling = _DoclingMod("docling")
    mod_docling.__version__ = "2.0.0"  # fallback version path

    mod_base = types.ModuleType("docling.datamodel.base_models")

    class _IF:
        PDF = object()

    mod_base.InputFormat = _IF  # type: ignore[attr-defined]

    mod_opts = types.ModuleType("docling.datamodel.pipeline_options")

    class _Ppo:
        def __init__(self, **_: object) -> None:
            pass

    mod_opts.PdfPipelineOptions = _Ppo  # type: ignore[attr-defined]

    mod_conv = types.ModuleType("docling.document_converter")

    class _Pfo:
        def __init__(self, **_: object) -> None:
            pass

    class _DC:
        def __init__(self, **_: object) -> None:
            if not success:
                raise RuntimeError("boom")

    mod_conv.PdfFormatOption = _Pfo  # type: ignore[attr-defined]
    mod_conv.DocumentConverter = _DC  # type: ignore[attr-defined]

    # docling_core and types
    class _CoreMod(types.ModuleType):
        __version__: str

    mod_core = _CoreMod("docling_core")
    mod_core.__version__ = "2.0.0"
    mod_core_types_doc = types.ModuleType("docling_core.types.doc")

    class ImageRefMode:  # - mimic external
        EMBEDDED = 1

    mod_core_types_doc.ImageRefMode = ImageRefMode  # type: ignore[attr-defined]
    mod_core_types_doc_document = types.ModuleType("docling_core.types.doc.document")

    class ContentLayer:
        BODY = 1
        BACKGROUND = 2
        FURNITURE = 3

    mod_core_types_doc_document.ContentLayer = ContentLayer  # type: ignore[attr-defined]

    sys.modules["docling"] = mod_docling
    sys.modules["docling.datamodel.base_models"] = mod_base
    sys.modules["docling.datamodel.pipeline_options"] = mod_opts
    sys.modules["docling.document_converter"] = mod_conv
    sys.modules["docling_core"] = mod_core
    sys.modules["docling_core.types.doc"] = mod_core_types_doc
    sys.modules["docling_core.types.doc.document"] = mod_core_types_doc_document


def test_probe_docling_success() -> None:
    _shim_docling(success=True)
    report = probe_docling()
    assert report.has_docling
    assert report.has_docling_core
    assert report.can_construct_converter
    assert report.has_core_types
    assert report_is_ok(report)
    lines = format_report_lines(report)
    assert any("Docling installed" in s for s in lines)
    # Ensure version strings presence or None tolerated
    assert isinstance(report.docling_version, str | type(None))
    assert isinstance(report.docling_core_version, str | type(None))


def test_probe_docling_partial_failure(monkeypatch: Any) -> None:
    _shim_docling(success=False)
    # Force importlib.metadata path to be exercised as well
    monkeypatch.setenv("PYTHONPATH", "")
    report = probe_docling()
    assert report.has_docling
    assert not report.can_construct_converter
    assert not report_is_ok(report)
