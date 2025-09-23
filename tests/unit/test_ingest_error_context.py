"""Tests for ErrorContext dataclass."""

from __future__ import annotations

from pathlib import Path

from pdf2foundry.ingest.error_handling import ErrorContext


class TestErrorContext:
    """Test the ErrorContext dataclass."""

    def test_default_initialization(self) -> None:
        """Test ErrorContext with default values."""
        context = ErrorContext()

        assert context.pdf_path is None
        assert context.doc_id is None
        assert context.source_module is None
        assert context.page is None
        assert context.object_kind is None
        assert context.object_id is None
        assert context.flags == {}
        assert len(context.correlation_id) == 8  # UUID truncated to 8 chars
        assert context.cli_verbosity == 0

    def test_full_initialization(self) -> None:
        """Test ErrorContext with all values provided."""
        pdf_path = Path("/test/document.pdf")
        flags = {"test": True, "mode": "auto"}

        context = ErrorContext(
            pdf_path=pdf_path,
            doc_id="doc123",
            source_module="test_module",
            page=5,
            object_kind="table",
            object_id="table_1",
            flags=flags,
            cli_verbosity=2,
        )

        assert context.pdf_path == pdf_path
        assert context.doc_id == "doc123"
        assert context.source_module == "test_module"
        assert context.page == 5
        assert context.object_kind == "table"
        assert context.object_id == "table_1"
        assert context.flags == flags
        assert len(context.correlation_id) == 8
        assert context.cli_verbosity == 2

    def test_to_dict_with_none_values(self) -> None:
        """Test to_dict method with None values."""
        context = ErrorContext()
        result = context.to_dict()

        expected = {
            "pdf_path": None,
            "doc_id": None,
            "source_module": None,
            "page": None,
            "object_kind": None,
            "object_id": None,
            "flags": {},
            "correlation_id": context.correlation_id,
            "cli_verbosity": 0,
        }

        assert result == expected

    def test_to_dict_with_all_values(self) -> None:
        """Test to_dict method with all values provided."""
        pdf_path = Path("/test/document.pdf")
        flags = {"test": True}

        context = ErrorContext(
            pdf_path=pdf_path,
            doc_id="doc123",
            source_module="test_module",
            page=5,
            object_kind="table",
            object_id="table_1",
            flags=flags,
            cli_verbosity=2,
        )

        result = context.to_dict()

        expected = {
            "pdf_path": str(pdf_path),
            "doc_id": "doc123",
            "source_module": "test_module",
            "page": 5,
            "object_kind": "table",
            "object_id": "table_1",
            "flags": flags,
            "correlation_id": context.correlation_id,
            "cli_verbosity": 2,
        }

        assert result == expected

    def test_correlation_id_uniqueness(self) -> None:
        """Test that correlation IDs are unique across instances."""
        context1 = ErrorContext()
        context2 = ErrorContext()

        assert context1.correlation_id != context2.correlation_id
        assert len(context1.correlation_id) == 8
        assert len(context2.correlation_id) == 8

    def test_correlation_id_format(self) -> None:
        """Test that correlation ID is a valid UUID prefix."""
        context = ErrorContext()

        # Should be 8 characters long and contain only hex characters
        assert len(context.correlation_id) == 8
        assert all(c in "0123456789abcdef" for c in context.correlation_id.lower())

    def test_correlation_id_consistency_across_managers(self) -> None:
        """Test that correlation ID is preserved when context is shared."""
        context = ErrorContext(doc_id="doc123")

        # Same context instance should have same correlation ID
        assert context.correlation_id == context.correlation_id

        # Different contexts should have different correlation IDs
        context2 = ErrorContext(doc_id="doc456")
        assert context.correlation_id != context2.correlation_id
