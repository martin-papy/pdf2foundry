"""Tests for docling_adapter functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pdf2foundry.ingest import docling_adapter as da


class _DummyDoc:
    def num_pages(self) -> int:
        return 1

    def export_to_html(self, **_: object) -> str:  # pragma: no cover - trivial
        return "<html></html>"


class TestDoclingAdapter:
    """Test docling_adapter module."""

    def test_do_docling_convert_impl_basic(self, tmp_path: Path) -> None:
        """Test basic docling conversion."""
        # Mock docling imports and classes
        mock_converter = Mock()
        mock_result = Mock()
        mock_result.document = _DummyDoc()
        mock_converter.convert.return_value = mock_result

        mock_pipeline_options = Mock()
        mock_pdf_format_option = Mock()
        mock_document_converter = Mock(return_value=mock_converter)
        mock_input_format = Mock()
        mock_input_format.PDF = "pdf"

        # Mock the imports to prevent actual docling imports
        with (
            patch.dict(
                "sys.modules",
                {
                    "docling.datamodel.base_models": Mock(InputFormat=mock_input_format),
                    "docling.datamodel.pipeline_options": Mock(PdfPipelineOptions=mock_pipeline_options),
                    "docling.document_converter": Mock(
                        DocumentConverter=mock_document_converter, PdfFormatOption=mock_pdf_format_option
                    ),
                },
            ),
            patch("concurrent.futures.ThreadPoolExecutor") as mock_executor,
        ):
            # Mock executor context manager
            mock_executor_instance = Mock()
            mock_future = Mock()
            mock_future.result.return_value = mock_result
            mock_executor_instance.submit.return_value = mock_future
            mock_executor.return_value.__enter__.return_value = mock_executor_instance
            mock_executor.return_value.__exit__.return_value = None

            pdf_path = tmp_path / "test.pdf"
            pdf_path.write_text("dummy pdf content")

            result = da._do_docling_convert_impl(
                pdf_path,
                images=True,
                ocr=False,
                tables_mode="auto",
                vlm=None,
                pages=None,
                workers=1,
            )

            assert isinstance(result, _DummyDoc)

    def test_do_docling_convert_impl_with_pages(self, tmp_path: Path) -> None:
        """Test docling conversion with specific pages."""
        # Mock docling components
        mock_converter = Mock()
        mock_result = Mock()
        mock_result.document = _DummyDoc()
        mock_converter.convert.return_value = mock_result

        mock_pipeline_options = Mock()
        mock_pdf_format_option = Mock()
        mock_document_converter = Mock(return_value=mock_converter)
        mock_input_format = Mock()
        mock_input_format.PDF = "pdf"

        with (
            patch.dict(
                "sys.modules",
                {
                    "docling.datamodel.base_models": Mock(InputFormat=mock_input_format),
                    "docling.datamodel.pipeline_options": Mock(PdfPipelineOptions=mock_pipeline_options),
                    "docling.document_converter": Mock(
                        DocumentConverter=mock_document_converter, PdfFormatOption=mock_pdf_format_option
                    ),
                },
            ),
            patch("concurrent.futures.ThreadPoolExecutor") as mock_executor,
        ):
            mock_executor_instance = Mock()
            mock_future = Mock()
            mock_future.result.return_value = mock_result
            mock_executor_instance.submit.return_value = mock_future
            mock_executor.return_value.__enter__.return_value = mock_executor_instance
            mock_executor.return_value.__exit__.return_value = None

            pdf_path = tmp_path / "test.pdf"
            pdf_path.write_text("dummy pdf content")

            result = da._do_docling_convert_impl(
                pdf_path,
                images=False,
                ocr=True,
                tables_mode="structured",
                vlm="microsoft/Florence-2-base",
                pages=[1, 2, 3],
                workers=2,
            )

            assert isinstance(result, _DummyDoc)

    def test_do_docling_convert_impl_tables_mode_variations(self, tmp_path: Path) -> None:
        """Test different tables_mode values."""
        # Mock docling components
        mock_converter = Mock()
        mock_result = Mock()
        mock_result.document = _DummyDoc()
        mock_converter.convert.return_value = mock_result

        mock_pipeline_options = Mock()
        mock_pdf_format_option = Mock()
        mock_document_converter = Mock(return_value=mock_converter)
        mock_input_format = Mock()
        mock_input_format.PDF = "pdf"

        with (
            patch.dict(
                "sys.modules",
                {
                    "docling.datamodel.base_models": Mock(InputFormat=mock_input_format),
                    "docling.datamodel.pipeline_options": Mock(PdfPipelineOptions=mock_pipeline_options),
                    "docling.document_converter": Mock(
                        DocumentConverter=mock_document_converter, PdfFormatOption=mock_pdf_format_option
                    ),
                },
            ),
            patch("concurrent.futures.ThreadPoolExecutor") as mock_executor,
        ):
            mock_executor_instance = Mock()
            mock_future = Mock()
            mock_future.result.return_value = mock_result
            mock_executor_instance.submit.return_value = mock_future
            mock_executor.return_value.__enter__.return_value = mock_executor_instance
            mock_executor.return_value.__exit__.return_value = None

            pdf_path = tmp_path / "test.pdf"
            pdf_path.write_text("dummy pdf content")

            # Test different tables_mode values
            for tables_mode in ["auto", "structured", "off"]:
                result = da._do_docling_convert_impl(
                    pdf_path,
                    images=True,
                    ocr=False,
                    tables_mode=tables_mode,
                    vlm=None,
                    pages=None,
                    workers=1,
                )
                assert isinstance(result, _DummyDoc)

    def test_run_docling_conversion_basic(self, tmp_path: Path) -> None:
        """Test basic PDF conversion to docling."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_text("dummy pdf content")

        with patch("pdf2foundry.ingest.docling_adapter._do_docling_convert_impl") as mock_convert:
            mock_convert.return_value = _DummyDoc()

            result = da.run_docling_conversion(
                pdf_path,
                images=True,
                ocr=False,
                tables_mode="auto",
                vlm=None,
                pages=None,
                workers=1,
            )

            assert isinstance(result, _DummyDoc)
            # Note: _cached_convert is called, not _do_docling_convert_impl directly

    def test_run_docling_conversion_with_all_options(self, tmp_path: Path) -> None:
        """Test PDF conversion with all options specified."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_text("dummy pdf content")

        with patch("pdf2foundry.ingest.docling_adapter._do_docling_convert_impl") as mock_convert:
            mock_convert.return_value = _DummyDoc()

            result = da.run_docling_conversion(
                pdf_path,
                images=False,
                ocr=True,
                tables_mode="structured",
                vlm="microsoft/Florence-2-base",
                pages=[1, 2, 3],
                workers=4,
            )

            assert isinstance(result, _DummyDoc)
            # Note: _cached_convert is called, not _do_docling_convert_impl directly

    def test_run_docling_conversion_error_handling(self, tmp_path: Path) -> None:
        """Test error handling in PDF conversion."""
        from pdf2foundry.ingest.error_handling import PdfParseError

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_text("dummy pdf content")

        with patch("pdf2foundry.ingest.docling_adapter._do_docling_convert_impl") as mock_convert:
            mock_convert.side_effect = PdfParseError("Conversion failed", pdf_path)

            with pytest.raises(PdfParseError):
                da.run_docling_conversion(
                    pdf_path,
                    images=True,
                    ocr=False,
                    tables_mode="auto",
                    vlm=None,
                    pages=None,
                    workers=1,
                )
