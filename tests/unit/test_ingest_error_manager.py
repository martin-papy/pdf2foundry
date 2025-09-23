"""Tests for ErrorManager class."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pdf2foundry.ingest.error_handling import ErrorContext, ErrorManager


class TestErrorManager:
    """Test the ErrorManager class."""

    def test_initialization_with_default_context(self) -> None:
        """Test ErrorManager initialization with default context."""
        manager = ErrorManager()

        assert manager.context is not None
        assert isinstance(manager.context, ErrorContext)
        assert manager.context.source_module is None

    def test_initialization_with_custom_context(self) -> None:
        """Test ErrorManager initialization with custom context."""
        context = ErrorContext(source_module="test_module", page=5)
        manager = ErrorManager(context)

        assert manager.context == context
        assert manager.context.source_module == "test_module"
        assert manager.context.page == 5

    def test_warn_basic(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test basic warning logging."""
        manager = ErrorManager()

        with caplog.at_level(logging.WARNING):
            manager.warn("TEST-001", "Test warning message")

        assert "TEST-001: Test warning message" in caplog.text

        # Check that log record has extra data
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert hasattr(record, "event_code")
        assert record.event_code == "TEST-001"

    def test_warn_with_extra_and_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test warning logging with extra data and exception."""
        context = ErrorContext(source_module="test_module", page=5)
        manager = ErrorManager(context)
        exception = ValueError("Test error")
        extra = {"detail": "extra info"}

        with caplog.at_level(logging.WARNING):
            manager.warn("TEST-002", "Test warning with extras", extra=extra, exception=exception)

        assert "TEST-002: Test warning with extras" in caplog.text

        record = caplog.records[0]
        assert record.event_code == "TEST-002"
        assert record.source_module == "test_module"
        assert record.page == 5
        assert record.detail == "extra info"
        assert record.exception_class == "ValueError"
        assert record.exception_message == "Test error"

    def test_error_basic(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test basic error logging."""
        manager = ErrorManager()

        with caplog.at_level(logging.ERROR):
            manager.error("ERR-001", "Test error message")

        assert "ERR-001: Test error message" in caplog.text

        record = caplog.records[0]
        assert record.levelno == logging.ERROR
        assert record.event_code == "ERR-001"

    def test_error_with_extra_and_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test error logging with extra data and exception."""
        context = ErrorContext(pdf_path=Path("/test.pdf"), doc_id="doc123")
        manager = ErrorManager(context)
        exception = RuntimeError("Critical error")
        extra = {"context": "processing"}

        with caplog.at_level(logging.ERROR):
            manager.error("ERR-002", "Critical error occurred", extra=extra, exception=exception)

        assert "ERR-002: Critical error occurred" in caplog.text

        record = caplog.records[0]
        assert record.event_code == "ERR-002"
        assert record.pdf_path == "/test.pdf"
        assert record.doc_id == "doc123"
        assert record.context == "processing"
        assert record.exception_class == "RuntimeError"
        assert record.exception_message == "Critical error"

    @patch("pdf2foundry.ingest.error_handling.log_feature_decision")
    def test_decision_logging(self, mock_log_decision: Mock, caplog: pytest.LogCaptureFixture) -> None:
        """Test decision logging."""
        context = ErrorContext(source_module="ocr_processor")
        manager = ErrorManager(context)
        extra = {"confidence": 0.8}

        with caplog.at_level(logging.INFO):
            manager.decision("DEC-001", "ocr.mode", "auto", extra=extra)

        # Check that existing feature logger was called
        mock_log_decision.assert_called_once_with("ocr.mode", "auto", extra)

        # Check our structured logging
        assert "DEC-001: ocr.mode=auto" in caplog.text

        record = caplog.records[0]
        assert record.event_code == "DEC-001"
        assert record.decision_key == "ocr.mode"
        assert record.decision_value == "auto"
        assert record.confidence == 0.8

    @patch("pdf2foundry.ingest.error_handling.log_error_policy")
    def test_error_policy_without_event_code(self, mock_log_policy: Mock) -> None:
        """Test error policy logging without event code."""
        manager = ErrorManager()

        manager.error_policy("OCR", "missing_dependency", "skip", details="Tesseract not found")

        # Should call existing feature logger
        mock_log_policy.assert_called_once_with("OCR", "missing_dependency", "skip", "Tesseract not found")

    @patch("pdf2foundry.ingest.error_handling.log_error_policy")
    def test_error_policy_with_event_code(self, mock_log_policy: Mock, caplog: pytest.LogCaptureFixture) -> None:
        """Test error policy logging with event code."""
        context = ErrorContext(source_module="ocr_processor", page=3)
        manager = ErrorManager(context)

        with caplog.at_level(logging.WARNING):
            manager.error_policy("OCR", "processing_failed", "continue", details="Engine error", event_code="OCR-ERR-001")

        # Should call existing feature logger
        mock_log_policy.assert_called_once_with("OCR", "processing_failed", "continue", "Engine error")

        # Should also log with structured format
        assert "OCR-ERR-001: OCR error policy: processing_failed -> continue" in caplog.text

        record = caplog.records[0]
        assert record.event_code == "OCR-ERR-001"
        assert record.feature == "OCR"
        assert record.error_type == "processing_failed"
        assert record.action == "continue"
        assert record.details == "Engine error"
        assert record.source_module == "ocr_processor"
        assert record.page == 3

    def test_build_log_data_with_docling_version(self) -> None:
        """Test _build_log_data includes docling version when available."""
        context = ErrorContext(pdf_path=Path("/test.pdf"))
        manager = ErrorManager(context)

        with patch.dict("sys.modules", {"docling": Mock(__version__="1.2.3")}):
            result = manager._build_log_data("TEST-001")

        assert result["docling_version"] == "1.2.3"
        assert result["event_code"] == "TEST-001"
        assert result["pdf_path"] == "/test.pdf"

    def test_build_log_data_without_docling(self) -> None:
        """Test _build_log_data when docling is not available."""
        context = ErrorContext(doc_id="doc123")
        manager = ErrorManager(context)

        with patch("builtins.__import__") as mock_import:

            def side_effect(name: str, *args, **kwargs):
                if name == "docling":
                    raise ImportError("No module named 'docling'")
                return Mock()

            mock_import.side_effect = side_effect

            result = manager._build_log_data("TEST-002")

        assert result["docling_version"] == "not_installed"
        assert result["event_code"] == "TEST-002"
        assert result["doc_id"] == "doc123"

    def test_build_log_data_docling_no_version(self) -> None:
        """Test _build_log_data when docling has no __version__ attribute."""
        context = ErrorContext()
        manager = ErrorManager(context)

        # Mock docling module without __version__ attribute
        mock_docling = Mock()
        if hasattr(mock_docling, "__version__"):
            delattr(mock_docling, "__version__")

        with patch.dict("sys.modules", {"docling": mock_docling}):
            result = manager._build_log_data("TEST-003")

        assert result["docling_version"] == "unknown"

    def test_build_log_data_with_extra_and_exception(self) -> None:
        """Test _build_log_data with extra data and exception."""
        context = ErrorContext(page=5, object_kind="table")
        manager = ErrorManager(context)

        extra = {"table_index": 2, "confidence": 0.7}
        exception = ValueError("Parse error")

        result = manager._build_log_data("TEST-004", extra=extra, exception=exception)

        assert result["event_code"] == "TEST-004"
        assert result["page"] == 5
        assert result["object_kind"] == "table"
        assert result["table_index"] == 2
        assert result["confidence"] == 0.7
        assert result["exception_class"] == "ValueError"
        assert result["exception_message"] == "Parse error"

    def test_logger_name_with_source_module(self) -> None:
        """Test that logger name includes source module."""
        context = ErrorContext(source_module="test_module")
        manager = ErrorManager(context)

        # Logger name should include the source module
        expected_name = "pdf2foundry.ingest.error_handling.test_module"
        assert manager._logger.name == expected_name

    def test_logger_name_without_source_module(self) -> None:
        """Test that logger name defaults when no source module."""
        context = ErrorContext()
        manager = ErrorManager(context)

        # Logger name should default to unknown
        expected_name = "pdf2foundry.ingest.error_handling.unknown"
        assert manager._logger.name == expected_name
