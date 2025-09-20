from __future__ import annotations

from pathlib import Path

import pytest

from pdf2foundry.ingest import docling_adapter as da


class _DummyDoc:
    def num_pages(self) -> int:
        return 1

    def export_to_html(self, **_: object) -> str:  # pragma: no cover - trivial
        return "<html></html>"


def test_run_docling_conversion_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Path, bool, bool, str, str | None, tuple[int, ...], int]] = []

    def fake_impl(
        pdf_path: Path,
        *,
        images: bool,
        ocr: bool,
        tables_mode: str,
        vlm: str | None,
        pages: list[int] | None,
        workers: int,
    ) -> da.DoclingDocumentLike:
        calls.append((pdf_path, images, ocr, tables_mode, vlm, tuple(pages or []), workers))
        return _DummyDoc()

    # Patch the actual converter implementation and clear cache
    monkeypatch.setattr(da, "_do_docling_convert_impl", fake_impl)
    da._cached_convert.cache_clear()

    pdf = Path("/tmp/example.pdf")

    # First call should trigger underlying impl
    d1 = da.run_docling_conversion(pdf)
    # Second call with same params should hit cache
    d2 = da.run_docling_conversion(pdf)

    assert isinstance(d1, _DummyDoc)
    assert d1 is d2
    assert len(calls) == 1


def test_run_docling_conversion_cache_key_changes_with_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Path, bool, bool, str, str | None, tuple[int, ...], int]] = []

    def fake_impl(
        pdf_path: Path,
        *,
        images: bool,
        ocr: bool,
        tables_mode: str,
        vlm: str | None,
        pages: list[int] | None,
        workers: int,
    ) -> da.DoclingDocumentLike:
        calls.append((pdf_path, images, ocr, tables_mode, vlm, tuple(pages or []), workers))
        return _DummyDoc()

    monkeypatch.setattr(da, "_do_docling_convert_impl", fake_impl)
    da._cached_convert.cache_clear()

    pdf = Path("/tmp/example.pdf")

    da.run_docling_conversion(pdf, images=True)
    da.run_docling_conversion(pdf, images=False)  # different arg -> different cache entry

    assert len(calls) == 2


def test_run_docling_conversion_type_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BadDoc:
        def num_pages(self) -> int:
            return 1

    def fake_impl(
        pdf_path: Path,
        *,
        images: bool,
        ocr: bool,
        tables_mode: str,
        vlm: str | None,
        pages: list[int] | None,
        workers: int,
    ) -> object:
        return _BadDoc()  # lacks export_to_html

    monkeypatch.setattr(da, "_do_docling_convert_impl", fake_impl)
    da._cached_convert.cache_clear()

    with pytest.raises(TypeError):
        da.run_docling_conversion(Path("/tmp/x.pdf"))


def test_load_docling_document_calls_run_docling_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Path, bool, bool, str, str | None, tuple[int, ...], int]] = []

    class _DummyDoc2(_DummyDoc):
        pass

    def fake_impl(
        pdf_path: Path,
        *,
        images: bool,
        ocr: bool,
        tables_mode: str,
        vlm: str | None,
        pages: list[int] | None,
        workers: int,
    ) -> da.DoclingDocumentLike:
        calls.append((pdf_path, images, ocr, tables_mode, vlm, tuple(pages or []), workers))
        return _DummyDoc2()

    monkeypatch.setattr(da, "_do_docling_convert_impl", fake_impl)
    da._cached_convert.cache_clear()

    d = da.load_docling_document(Path("/tmp/y.pdf"), images=False, ocr=True)
    assert isinstance(d, _DummyDoc2)
    assert len(calls) == 1
    assert calls[0][1] is False and calls[0][2] is True
