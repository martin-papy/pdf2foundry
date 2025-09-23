"""Tests for custom exception classes."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from pdf2foundry.ingest.error_handling import (
    CaptionAssociationWarning,
    CrossRefResolutionWarning,
    ErrorContext,
    ErrorManager,
    PdfParseError,
    TableExtractionError,
)


class TestCustomExceptions:
    """Test custom exception classes."""

    def test_pdf_parse_error_basic(self) -> None:
        """Test PdfParseError with basic parameters."""
        pdf_path = Path("/test/document.pdf")
        error = PdfParseError(pdf_path)

        assert error.pdf_path == pdf_path
        assert error.cause is None
        assert error.page is None
        assert str(error) == "Failed to parse PDF /test/document.pdf"

    def test_pdf_parse_error_with_page(self) -> None:
        """Test PdfParseError with page number."""
        pdf_path = Path("/test/document.pdf")
        error = PdfParseError(pdf_path, page=5)

        assert error.pdf_path == pdf_path
        assert error.page == 5
        assert str(error) == "Failed to parse PDF /test/document.pdf at page 5"

    def test_pdf_parse_error_with_cause(self) -> None:
        """Test PdfParseError with cause exception."""
        pdf_path = Path("/test/document.pdf")
        cause = ValueError("Invalid format")
        error = PdfParseError(pdf_path, cause=cause)

        assert error.pdf_path == pdf_path
        assert error.cause == cause
        assert str(error) == "Failed to parse PDF /test/document.pdf: Invalid format"

    def test_pdf_parse_error_with_page_and_cause(self) -> None:
        """Test PdfParseError with both page and cause."""
        pdf_path = Path("/test/document.pdf")
        cause = RuntimeError("Docling error")
        error = PdfParseError(pdf_path, cause=cause, page=3)

        assert error.pdf_path == pdf_path
        assert error.cause == cause
        assert error.page == 3
        assert str(error) == "Failed to parse PDF /test/document.pdf at page 3: Docling error"

    def test_table_extraction_error_basic(self) -> None:
        """Test TableExtractionError with basic parameters."""
        error = TableExtractionError(5)

        assert error.page == 5
        assert error.table_index is None
        assert error.cause is None
        assert str(error) == "Failed to extract table on page 5"

    def test_table_extraction_error_with_table_index(self) -> None:
        """Test TableExtractionError with table index."""
        error = TableExtractionError(3, table_index=2)

        assert error.page == 3
        assert error.table_index == 2
        assert str(error) == "Failed to extract table on page 3 (table 2)"

    def test_table_extraction_error_with_cause(self) -> None:
        """Test TableExtractionError with cause exception."""
        cause = ValueError("Invalid table structure")
        error = TableExtractionError(7, cause=cause)

        assert error.page == 7
        assert error.cause == cause
        assert str(error) == "Failed to extract table on page 7: Invalid table structure"

    def test_table_extraction_error_with_all_params(self) -> None:
        """Test TableExtractionError with all parameters."""
        cause = RuntimeError("Processing failed")
        error = TableExtractionError(4, table_index=1, cause=cause)

        assert error.page == 4
        assert error.table_index == 1
        assert error.cause == cause
        assert str(error) == "Failed to extract table on page 4 (table 1): Processing failed"

    def test_cross_ref_resolution_warning(self) -> None:
        """Test CrossRefResolutionWarning."""
        error = CrossRefResolutionWarning("See Chapter 5", 10, "chapter-5")

        assert error.link_text == "See Chapter 5"
        assert error.source_page == 10
        assert error.target_anchor == "chapter-5"
        assert str(error) == "Failed to resolve cross-reference 'See Chapter 5' on page 10 to anchor 'chapter-5'"

    def test_caption_association_warning_basic(self) -> None:
        """Test CaptionAssociationWarning with basic parameters."""
        error = CaptionAssociationWarning(8)

        assert error.page == 8
        assert error.figure_id is None
        assert error.caption_text is None
        assert str(error) == "Failed to associate caption on page 8"

    def test_caption_association_warning_with_figure_id(self) -> None:
        """Test CaptionAssociationWarning with figure ID."""
        error = CaptionAssociationWarning(6, figure_id="fig-3")

        assert error.page == 6
        assert error.figure_id == "fig-3"
        assert str(error) == "Failed to associate caption on page 6 for figure fig-3"

    def test_caption_association_warning_with_caption_text(self) -> None:
        """Test CaptionAssociationWarning with caption text."""
        caption = "This is a test caption for the figure"
        error = CaptionAssociationWarning(9, caption_text=caption)

        assert error.page == 9
        assert error.caption_text == caption
        assert str(error) == "Failed to associate caption on page 9: 'This is a test caption for the figure'"

    def test_caption_association_warning_with_long_caption_text(self) -> None:
        """Test CaptionAssociationWarning with long caption text (should be truncated)."""
        long_caption = "This is a very long caption text that should be truncated when displayed in the error message"
        error = CaptionAssociationWarning(12, caption_text=long_caption)

        assert error.page == 12
        assert error.caption_text == long_caption
        expected_str = "Failed to associate caption on page 12: " "'This is a very long caption text that should be tr...'"
        assert str(error) == expected_str

    def test_caption_association_warning_with_all_params(self) -> None:
        """Test CaptionAssociationWarning with all parameters."""
        caption = "Figure showing the results"
        error = CaptionAssociationWarning(15, figure_id="fig-7", caption_text=caption)

        assert error.page == 15
        assert error.figure_id == "fig-7"
        assert error.caption_text == caption
        assert str(error) == "Failed to associate caption on page 15 for figure fig-7: 'Figure showing the results'"


class TestIntegrationScenarios:
    """Test integration scenarios with ErrorManager and custom exceptions."""

    def test_error_manager_with_pdf_parse_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test ErrorManager handling PdfParseError."""
        pdf_path = Path("/test/document.pdf")
        context = ErrorContext(pdf_path=pdf_path, page=5)
        manager = ErrorManager(context)

        parse_error = PdfParseError(pdf_path, page=5, cause=ValueError("Invalid format"))

        with caplog.at_level(logging.ERROR):
            manager.error("PDF-001", "PDF parsing failed", exception=parse_error)

        assert "PDF-001: PDF parsing failed" in caplog.text

        record = caplog.records[0]
        assert record.exception_class == "PdfParseError"
        assert "Failed to parse PDF" in record.exception_message
        assert record.pdf_path == "/test/document.pdf"
        assert record.page == 5

    def test_error_manager_with_table_extraction_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test ErrorManager handling TableExtractionError."""
        context = ErrorContext(source_module="table_processor", page=3, object_kind="table")
        manager = ErrorManager(context)

        table_error = TableExtractionError(3, table_index=1, cause=RuntimeError("Processing failed"))

        with caplog.at_level(logging.WARNING):
            manager.warn("TABLE-001", "Table extraction failed", exception=table_error)

        assert "TABLE-001: Table extraction failed" in caplog.text

        record = caplog.records[0]
        assert record.exception_class == "TableExtractionError"
        assert "Failed to extract table" in record.exception_message
        assert record.source_module == "table_processor"
        assert record.page == 3
        assert record.object_kind == "table"

    def test_error_manager_with_cross_ref_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test ErrorManager handling CrossRefResolutionWarning."""
        context = ErrorContext(source_module="link_processor", page=10)
        manager = ErrorManager(context)

        cross_ref_error = CrossRefResolutionWarning("See Chapter 5", 10, "chapter-5")

        with caplog.at_level(logging.WARNING):
            manager.warn("LINK-001", "Cross-reference resolution failed", exception=cross_ref_error)

        assert "LINK-001: Cross-reference resolution failed" in caplog.text

        record = caplog.records[0]
        assert record.exception_class == "CrossRefResolutionWarning"
        assert "Failed to resolve cross-reference" in record.exception_message
        assert record.source_module == "link_processor"
        assert record.page == 10

    def test_error_manager_with_caption_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test ErrorManager handling CaptionAssociationWarning."""
        context = ErrorContext(source_module="caption_processor", page=8)
        manager = ErrorManager(context)

        caption_error = CaptionAssociationWarning(8, figure_id="fig-3", caption_text="Test caption")

        with caplog.at_level(logging.WARNING):
            manager.warn("CAPTION-001", "Caption association failed", exception=caption_error)

        assert "CAPTION-001: Caption association failed" in caplog.text

        record = caplog.records[0]
        assert record.exception_class == "CaptionAssociationWarning"
        assert "Failed to associate caption" in record.exception_message
        assert record.source_module == "caption_processor"
        assert record.page == 8
