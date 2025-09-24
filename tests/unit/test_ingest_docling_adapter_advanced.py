"""Advanced tests for docling_adapter functionality."""

from __future__ import annotations

import concurrent.futures
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pdf2foundry.ingest import docling_adapter as da


class _DummyDoc:
    def num_pages(self) -> int:
        return 1

    def export_to_html(self, **_: object) -> str:  # pragma: no cover - trivial
        return "<html></html>"


class TestDoclingAdapterAdvanced:
    """Advanced tests for docling_adapter to improve coverage."""

    def test_do_docling_convert_impl_ci_minimal_mode(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test conversion in CI minimal mode."""
        # Set CI minimal environment
        monkeypatch.setenv("PDF2FOUNDRY_CI_MINIMAL", "1")

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

        # Mock the imports
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
                ocr=True,
                tables_mode="auto",
                vlm=None,
                pages=None,
                workers=1,
            )

            assert isinstance(result, _DummyDoc)
            # Verify CI minimal options were used
            mock_pipeline_options.assert_called_with(
                generate_picture_images=False,
                generate_page_images=False,
                do_ocr=False,
                do_table_structure=False,
            )

    def test_do_docling_convert_impl_no_ml_mode(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test conversion in no-ML mode."""
        # Set no-ML environment
        monkeypatch.setenv("PDF2FOUNDRY_NO_ML", "1")

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
                images=True,
                ocr=True,
                tables_mode="auto",
                vlm=None,
                pages=None,
                workers=1,
            )

            assert isinstance(result, _DummyDoc)
            # Verify no-ML options were used
            mock_pipeline_options.assert_called_with(
                generate_picture_images=False,
                generate_page_images=False,
                do_ocr=False,
                do_table_structure=False,
            )

    def test_do_docling_convert_impl_normal_mode(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test conversion in normal mode."""
        # Ensure no special environment variables are set
        monkeypatch.delenv("PDF2FOUNDRY_CI_MINIMAL", raising=False)
        monkeypatch.delenv("PDF2FOUNDRY_NO_ML", raising=False)

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
                images=True,
                ocr=False,
                tables_mode="auto",
                vlm=None,
                pages=None,
                workers=1,
            )

            assert isinstance(result, _DummyDoc)
            # Verify normal options were used
            mock_pipeline_options.assert_called_with(
                generate_picture_images=True,
                generate_page_images=True,
                do_ocr=False,
            )

    def test_do_docling_convert_impl_timeout_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test conversion timeout handling."""
        from pdf2foundry.ingest.error_handling import PdfParseError

        # Mock docling components
        mock_converter = Mock()
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
            # Mock timeout scenario
            mock_executor_instance = Mock()
            mock_future = Mock()
            mock_future.result.side_effect = concurrent.futures.TimeoutError("Conversion timed out")
            mock_executor_instance.submit.return_value = mock_future
            mock_executor.return_value.__enter__.return_value = mock_executor_instance
            mock_executor.return_value.__exit__.return_value = None

            pdf_path = tmp_path / "test.pdf"
            pdf_path.write_text("dummy pdf content")

            with pytest.raises(PdfParseError) as exc_info:
                da._do_docling_convert_impl(
                    pdf_path,
                    images=True,
                    ocr=False,
                    tables_mode="auto",
                    vlm=None,
                    pages=None,
                    workers=1,
                )

            assert "timed out" in str(exc_info.value)
            # Verify future was cancelled
            mock_future.cancel.assert_called_once()

    def test_do_docling_convert_impl_timeout_ci_minimal(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test timeout handling in CI minimal mode with aggressive cleanup."""
        from pdf2foundry.ingest.error_handling import PdfParseError

        # Set CI minimal environment
        monkeypatch.setenv("PDF2FOUNDRY_CI_MINIMAL", "1")

        # Mock docling components
        mock_converter = Mock()
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
            # Mock timeout scenario
            mock_executor_instance = Mock()
            mock_future = Mock()
            mock_future.result.side_effect = concurrent.futures.TimeoutError("Conversion timed out")
            mock_executor_instance.submit.return_value = mock_future
            mock_executor_instance.shutdown = Mock()
            mock_executor.return_value.__enter__.return_value = mock_executor_instance
            mock_executor.return_value.__exit__.return_value = None

            pdf_path = tmp_path / "test.pdf"
            pdf_path.write_text("dummy pdf content")

            with pytest.raises(PdfParseError):
                da._do_docling_convert_impl(
                    pdf_path,
                    images=True,
                    ocr=False,
                    tables_mode="auto",
                    vlm=None,
                    pages=None,
                    workers=1,
                )

            # Verify aggressive cleanup was called
            mock_executor_instance.shutdown.assert_called_with(wait=False, cancel_futures=True)

    def test_do_docling_convert_impl_import_error(self, tmp_path: Path) -> None:
        """Test handling of docling import error."""
        from pdf2foundry.ingest.error_handling import PdfParseError

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_text("dummy pdf content")

        # Mock import error by making the docling modules unavailable
        with patch.dict(
            "sys.modules",
            {
                "docling.datamodel.base_models": None,
                "docling.datamodel.pipeline_options": None,
                "docling.document_converter": None,
            },
        ):
            # Mock the import to raise ImportError for docling modules
            original_import = __import__

            def mock_import(name, *args, **kwargs):
                if name.startswith("docling"):
                    raise ImportError(f"No module named '{name}'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises(PdfParseError) as exc_info:
                    da._do_docling_convert_impl(
                        pdf_path,
                        images=True,
                        ocr=False,
                        tables_mode="auto",
                        vlm=None,
                        pages=None,
                        workers=1,
                    )

                assert "docling" in str(exc_info.value).lower()

    def test_do_docling_convert_impl_conversion_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test handling of general conversion errors."""
        from pdf2foundry.ingest.error_handling import PdfParseError

        # Mock docling components that raise an error during conversion
        mock_converter = Mock()
        mock_converter.convert.side_effect = RuntimeError("Conversion failed")

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
            mock_future.result.side_effect = RuntimeError("Conversion failed")
            mock_executor_instance.submit.return_value = mock_future
            mock_executor.return_value.__enter__.return_value = mock_executor_instance
            mock_executor.return_value.__exit__.return_value = None

            pdf_path = tmp_path / "test.pdf"
            pdf_path.write_text("dummy pdf content")

            with pytest.raises(PdfParseError) as exc_info:
                da._do_docling_convert_impl(
                    pdf_path,
                    images=True,
                    ocr=False,
                    tables_mode="auto",
                    vlm=None,
                    pages=None,
                    workers=1,
                )

            assert "Conversion failed" in str(exc_info.value)

    def test_timeout_calculation_different_environments(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test timeout calculation for different environments."""
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

            # Test CI environment with structured tables
            monkeypatch.setenv("CI", "1")
            monkeypatch.delenv("PDF2FOUNDRY_CI_MINIMAL", raising=False)

            da._do_docling_convert_impl(
                pdf_path,
                images=True,
                ocr=False,
                tables_mode="structured",
                vlm=None,
                pages=None,
                workers=1,
            )

            # Verify future.result was called (indicating timeout was set)
            mock_future.result.assert_called()

            # Test with custom timeout environment variable
            monkeypatch.setenv("PDF2FOUNDRY_CONVERSION_TIMEOUT", "120")

            da._do_docling_convert_impl(
                pdf_path,
                images=True,
                ocr=False,
                tables_mode="auto",
                vlm=None,
                pages=None,
                workers=1,
            )

            # Should still work with custom timeout
            assert mock_future.result.call_count >= 2
