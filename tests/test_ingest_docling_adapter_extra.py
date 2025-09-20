from __future__ import annotations

import types
from pathlib import Path
from typing import Any

import pytest

from pdf2foundry.ingest.docling_adapter import _do_docling_convert_impl


class _Doc:
    def num_pages(self) -> int:  # pragma: no cover - trivial
        return 1

    def export_to_html(self, **_: object) -> str:  # pragma: no cover - trivial
        return "<html/>"


class _Conv:
    def convert(self, _: str) -> Any:
        class _Obj:
            def __init__(self) -> None:
                self.document = _Doc()

        return _Obj()


def _monkey_docling_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    # Create fake docling modules used inside _do_docling_convert_impl
    mod_base = types.ModuleType("docling.datamodel.base_models")

    class _IF:
        PDF = object()

    mod_base.InputFormat = _IF  # type: ignore[attr-defined]

    mod_opts = types.ModuleType("docling.datamodel.pipeline_options")

    class _Ppo:
        def __init__(self, **_: Any) -> None:
            pass

    mod_opts.PdfPipelineOptions = _Ppo  # type: ignore[attr-defined]

    mod_conv = types.ModuleType("docling.document_converter")

    class _Pfo:
        def __init__(self, **_: Any) -> None:
            pass

    mod_conv.PdfFormatOption = _Pfo  # type: ignore[attr-defined]
    mod_conv.DocumentConverter = lambda format_options: _Conv()  # type: ignore[attr-defined]

    import sys

    sys.modules["docling.datamodel.base_models"] = mod_base
    sys.modules["docling.datamodel.pipeline_options"] = mod_opts
    sys.modules["docling.document_converter"] = mod_conv


def test_do_docling_convert_impl_smoke(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _monkey_docling_modules(monkeypatch)
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%EOF\n")
    doc = _do_docling_convert_impl(
        pdf,
        images=True,
        ocr=False,
        tables_mode="auto",
        vlm=None,
        pages=None,
        workers=0,
    )
    assert hasattr(doc, "export_to_html")
    assert callable(doc.export_to_html)
