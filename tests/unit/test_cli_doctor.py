from __future__ import annotations

import sys
import types

from typer.testing import CliRunner

from pdf2foundry.cli import app


def _shim_docling_success() -> None:
    # Minimal shim to satisfy doctor() imports
    class _DoclingMod(types.ModuleType):
        __version__: str

    mod_docling = _DoclingMod("docling")
    mod_docling.__version__ = "2.0.0"
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
            pass

    mod_conv.PdfFormatOption = _Pfo  # type: ignore[attr-defined]
    mod_conv.DocumentConverter = _DC  # type: ignore[attr-defined]

    class _CoreMod(types.ModuleType):
        __version__: str

    mod_core = _CoreMod("docling_core")
    mod_core.__version__ = "2.0.0"
    mod_core_types_doc = types.ModuleType("docling_core.types.doc")

    class ImageRefMode:
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


def test_cli_doctor_success() -> None:
    _shim_docling_success()
    runner = CliRunner()
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Docling Environment Check:" in result.stdout


def test_cli_doctor_failure() -> None:
    # Shim with failing converter
    _shim_docling_success()
    import sys

    mod_conv = sys.modules["docling.document_converter"]

    class _FailDC:
        def __init__(self, **_: object) -> None:
            raise RuntimeError("boom")

    mod_conv.DocumentConverter = _FailDC  # type: ignore[attr-defined]

    runner = CliRunner()
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
