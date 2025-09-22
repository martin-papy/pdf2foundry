"""Tests for page selection functionality."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from pdf2foundry.ingest.content_extractor import _resolve_selected_pages, yield_pages
from pdf2foundry.model.pipeline_options import PdfPipelineOptions


class MockDocument:
    """Mock document for testing page selection."""

    def __init__(self, num_pages: int):
        self._num_pages = num_pages

    def num_pages(self) -> int:
        """Return the number of pages in the document."""
        return self._num_pages

    def export_to_html(self, **kwargs: Any) -> str:
        """Mock HTML export."""
        page_no = kwargs.get("page_no", 1)
        return f"<html>Page {page_no} content</html>"


class TestResolveSelectedPages:
    """Test _resolve_selected_pages function."""

    def test_resolve_all_pages_when_none_specified(self) -> None:
        """Test that all pages are selected when pages_option is None."""
        result = _resolve_selected_pages(total_pages=5, pages_option=None)
        assert result == [1, 2, 3, 4, 5]

    def test_resolve_all_pages_single_page_document(self) -> None:
        """Test that single page is selected for single-page document."""
        result = _resolve_selected_pages(total_pages=1, pages_option=None)
        assert result == [1]

    def test_resolve_empty_document(self) -> None:
        """Test that empty list is returned for zero-page document."""
        result = _resolve_selected_pages(total_pages=0, pages_option=None)
        assert result == []

    def test_resolve_single_page_selection(self) -> None:
        """Test selection of a single page."""
        result = _resolve_selected_pages(total_pages=10, pages_option=[5])
        assert result == [5]

    def test_resolve_multiple_pages_selection(self) -> None:
        """Test selection of multiple specific pages."""
        result = _resolve_selected_pages(total_pages=10, pages_option=[1, 3, 5, 7])
        assert result == [1, 3, 5, 7]

    def test_resolve_pages_with_duplicates(self) -> None:
        """Test that duplicate pages are deduplicated."""
        result = _resolve_selected_pages(total_pages=10, pages_option=[1, 3, 1, 5, 3])
        assert result == [1, 3, 5]

    def test_resolve_pages_unsorted_input(self) -> None:
        """Test that pages are sorted in ascending order."""
        result = _resolve_selected_pages(total_pages=10, pages_option=[7, 1, 5, 3])
        assert result == [1, 3, 5, 7]

    def test_resolve_pages_all_pages_selected(self) -> None:
        """Test selecting all pages explicitly."""
        result = _resolve_selected_pages(total_pages=3, pages_option=[1, 2, 3])
        assert result == [1, 2, 3]

    def test_resolve_pages_empty_selection(self) -> None:
        """Test that empty selection returns empty list."""
        result = _resolve_selected_pages(total_pages=10, pages_option=[])
        assert result == []

    def test_resolve_pages_exceeds_document_length(self) -> None:
        """Test that requesting pages beyond document length raises ValueError."""
        with pytest.raises(ValueError, match="Requested page 15 exceeds document length 10"):
            _resolve_selected_pages(total_pages=10, pages_option=[1, 5, 15])

    def test_resolve_pages_max_page_exactly_at_limit(self) -> None:
        """Test that requesting the last page exactly works."""
        result = _resolve_selected_pages(total_pages=10, pages_option=[1, 5, 10])
        assert result == [1, 5, 10]

    def test_resolve_pages_single_page_exceeds_limit(self) -> None:
        """Test that requesting a single page beyond limit raises ValueError."""
        with pytest.raises(ValueError, match="Requested page 5 exceeds document length 3"):
            _resolve_selected_pages(total_pages=3, pages_option=[5])

    def test_resolve_pages_multiple_exceed_limit(self) -> None:
        """Test that the highest exceeding page is reported in error."""
        with pytest.raises(ValueError, match="Requested page 20 exceeds document length 10"):
            _resolve_selected_pages(total_pages=10, pages_option=[5, 15, 20])


class TestYieldPages:
    """Test yield_pages function."""

    def test_yield_single_page(self) -> None:
        """Test yielding a single page."""
        doc = MockDocument(num_pages=10)
        selected_pages = [5]

        result = list(yield_pages(doc, selected_pages))
        assert result == [(5, 4)]  # (page_no, zero_based_index)

    def test_yield_multiple_pages(self) -> None:
        """Test yielding multiple pages."""
        doc = MockDocument(num_pages=10)
        selected_pages = [1, 3, 5, 7]

        result = list(yield_pages(doc, selected_pages))
        expected = [(1, 0), (3, 2), (5, 4), (7, 6)]
        assert result == expected

    def test_yield_pages_in_order(self) -> None:
        """Test that pages are yielded in the order specified."""
        doc = MockDocument(num_pages=10)
        selected_pages = [7, 2, 9, 1]  # Unsorted input

        result = list(yield_pages(doc, selected_pages))
        expected = [(7, 6), (2, 1), (9, 8), (1, 0)]  # Same order as input
        assert result == expected

    def test_yield_empty_selection(self) -> None:
        """Test yielding with empty page selection."""
        doc = MockDocument(num_pages=10)
        selected_pages: list[int] = []

        result = list(yield_pages(doc, selected_pages))
        assert result == []

    def test_yield_pages_returns_iterator(self) -> None:
        """Test that yield_pages returns an iterator."""
        doc = MockDocument(num_pages=10)
        selected_pages = [1, 2, 3]

        result = yield_pages(doc, selected_pages)
        assert isinstance(result, Iterator)

    def test_yield_pages_with_duplicates(self) -> None:
        """Test yielding pages with duplicates (should yield each occurrence)."""
        doc = MockDocument(num_pages=10)
        selected_pages = [1, 3, 1, 5]  # Contains duplicate

        result = list(yield_pages(doc, selected_pages))
        expected = [(1, 0), (3, 2), (1, 0), (5, 4)]  # Yields duplicate
        assert result == expected

    def test_yield_all_pages(self) -> None:
        """Test yielding all pages in a document."""
        doc = MockDocument(num_pages=5)
        selected_pages = [1, 2, 3, 4, 5]

        result = list(yield_pages(doc, selected_pages))
        expected = [(1, 0), (2, 1), (3, 2), (4, 3), (5, 4)]
        assert result == expected


class TestPageSelectionIntegration:
    """Test integration of page selection with pipeline options."""

    def test_pipeline_options_with_pages(self) -> None:
        """Test that PdfPipelineOptions correctly stores page selection."""
        pages = [1, 3, 5, 7]
        options = PdfPipelineOptions(pages=pages)

        assert options.pages == pages

    def test_pipeline_options_without_pages(self) -> None:
        """Test that PdfPipelineOptions defaults to None for pages."""
        options = PdfPipelineOptions()

        assert options.pages is None

    def test_resolve_pages_with_pipeline_options(self) -> None:
        """Test resolving pages using PdfPipelineOptions."""
        options = PdfPipelineOptions(pages=[2, 4, 6])

        result = _resolve_selected_pages(total_pages=10, pages_option=options.pages)
        assert result == [2, 4, 6]

    def test_resolve_pages_with_none_from_pipeline_options(self) -> None:
        """Test resolving pages when PdfPipelineOptions has None for pages."""
        options = PdfPipelineOptions(pages=None)

        result = _resolve_selected_pages(total_pages=5, pages_option=options.pages)
        assert result == [1, 2, 3, 4, 5]


class TestPageSelectionEdgeCases:
    """Test edge cases for page selection functionality."""

    def test_resolve_pages_large_document(self) -> None:
        """Test page selection with a large document."""
        total_pages = 1000
        selected_pages = [1, 100, 500, 999, 1000]

        result = _resolve_selected_pages(total_pages, selected_pages)
        assert result == [1, 100, 500, 999, 1000]

    def test_resolve_pages_sparse_selection(self) -> None:
        """Test sparse page selection across a large document."""
        total_pages = 100
        selected_pages = [1, 25, 50, 75, 100]

        result = _resolve_selected_pages(total_pages, selected_pages)
        assert result == [1, 25, 50, 75, 100]

    def test_yield_pages_large_selection(self) -> None:
        """Test yielding a large number of pages."""
        doc = MockDocument(num_pages=100)
        selected_pages = list(range(1, 101))  # All pages 1-100

        result = list(yield_pages(doc, selected_pages))

        # Verify first few and last few entries
        assert result[0] == (1, 0)
        assert result[1] == (2, 1)
        assert result[-2] == (99, 98)
        assert result[-1] == (100, 99)
        assert len(result) == 100

    def test_resolve_pages_boundary_conditions(self) -> None:
        """Test boundary conditions for page resolution."""
        # Test with page 1 only
        result = _resolve_selected_pages(total_pages=1, pages_option=[1])
        assert result == [1]

        # Test with last page only
        result = _resolve_selected_pages(total_pages=50, pages_option=[50])
        assert result == [50]

    def test_yield_pages_boundary_conditions(self) -> None:
        """Test boundary conditions for page yielding."""
        doc = MockDocument(num_pages=1)

        # Test single page document
        result = list(yield_pages(doc, [1]))
        assert result == [(1, 0)]

    def test_resolve_pages_with_complex_duplicates(self) -> None:
        """Test complex duplicate scenarios."""
        # Multiple duplicates of different pages
        selected_pages = [1, 5, 1, 3, 5, 1, 7, 3]
        result = _resolve_selected_pages(total_pages=10, pages_option=selected_pages)
        assert result == [1, 3, 5, 7]  # Deduplicated and sorted

    def test_error_message_accuracy(self) -> None:
        """Test that error messages are accurate and helpful."""
        # Test specific error message format
        with pytest.raises(ValueError) as exc_info:
            _resolve_selected_pages(total_pages=5, pages_option=[1, 3, 8])

        error_msg = str(exc_info.value)
        assert "Requested page 8 exceeds document length 5" in error_msg

    def test_resolve_pages_preserves_input_type(self) -> None:
        """Test that function works with different input types."""
        # Test with list
        result1 = _resolve_selected_pages(total_pages=10, pages_option=[1, 3, 5])
        assert result1 == [1, 3, 5]

        # Test with None
        result2 = _resolve_selected_pages(total_pages=3, pages_option=None)
        assert result2 == [1, 2, 3]


class TestPageSelectionPerformance:
    """Test performance characteristics of page selection functions."""

    def test_resolve_pages_performance_with_large_input(self) -> None:
        """Test that page resolution is efficient with large inputs."""
        # Large document with many selected pages
        total_pages = 10000
        selected_pages = list(range(1, 1001))  # First 1000 pages

        # This should complete quickly without issues
        result = _resolve_selected_pages(total_pages, selected_pages)
        assert len(result) == 1000
        assert result[0] == 1
        assert result[-1] == 1000

    def test_yield_pages_memory_efficiency(self) -> None:
        """Test that yield_pages is memory efficient (uses iterator)."""
        doc = MockDocument(num_pages=1000)
        selected_pages = list(range(1, 1001))

        # Get iterator but don't consume it
        page_iterator = yield_pages(doc, selected_pages)

        # Should be able to get first item without loading all into memory
        first_item = next(page_iterator)
        assert first_item == (1, 0)

        # Should be able to get second item
        second_item = next(page_iterator)
        assert second_item == (2, 1)
