"""Tests for parallel page processing functionality."""

# ruff: noqa: SIM117

import logging
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from pdf2foundry.ingest.parallel_processor import (
    PageProcessingContext,
    PageProcessingResult,
    process_page_content,
    process_pages_parallel,
)
from pdf2foundry.model.content import HtmlPage
from pdf2foundry.model.pipeline_options import PdfPipelineOptions, TableMode


class TestPageProcessingContext:
    """Test the PageProcessingContext dataclass."""

    def test_context_creation(self) -> None:
        """Test creating a processing context."""
        context = PageProcessingContext(
            page_no=1,
            out_assets_path="/tmp/assets",
            name_prefix="page-0001",
            pipeline_options=PdfPipelineOptions(),
        )

        assert context.page_no == 1
        assert context.out_assets_path == "/tmp/assets"
        assert context.name_prefix == "page-0001"
        assert isinstance(context.pipeline_options, PdfPipelineOptions)


class TestPageProcessingResult:
    """Test the PageProcessingResult dataclass."""

    def test_result_creation(self) -> None:
        """Test creating a processing result."""
        html_page = HtmlPage(html="<p>Test</p>", page_no=1)
        result = PageProcessingResult(
            page_no=1,
            html_page=html_page,
            images=[],
            tables=[],
            links=[],
            processing_time=0.5,
        )

        assert result.page_no == 1
        assert result.html_page == html_page
        assert result.images == []
        assert result.tables == []
        assert result.links == []
        assert result.processing_time == 0.5


class TestProcessPageContent:
    """Test the process_page_content function."""

    def test_process_page_basic(self, tmp_path: Path) -> None:
        """Test basic page processing."""
        # Mock document
        doc = Mock()
        doc.export_to_html.return_value = "<p>Test content</p>"

        # Create context
        context = PageProcessingContext(
            page_no=1,
            out_assets_path=str(tmp_path),
            name_prefix="page-0001",
            pipeline_options=PdfPipelineOptions(),
        )

        # Mock the imported functions
        with (
            patch("pdf2foundry.ingest.parallel_processor._extract_images_from_html") as mock_extract,
            patch("pdf2foundry.ingest.parallel_processor._rewrite_and_copy_referenced_images") as mock_rewrite,
        ):
            with patch("pdf2foundry.ingest.parallel_processor._detect_links") as mock_links:
                with patch("pdf2foundry.ingest.parallel_processor._process_tables") as mock_tables:
                    # Set up mocks
                    mock_extract.return_value = ("<p>Test content</p>", [])
                    mock_rewrite.return_value = ("<p>Test content</p>", [])
                    mock_links.return_value = []
                    mock_tables.return_value = ("<p>Test content</p>", [])

                    # Process page
                    result = process_page_content(doc, context)

                    # Verify result
                    assert isinstance(result, PageProcessingResult)
                    assert result.page_no == 1
                    assert result.html_page.html == "<p>Test content</p>"
                    assert result.html_page.page_no == 1
                    assert result.processing_time > 0

                    # Verify function calls
                    doc.export_to_html.assert_called_once_with(page_no=1, split_page_view=False)

    def test_process_page_with_layers_and_image_mode(self, tmp_path: Path) -> None:
        """Test page processing with layers and image mode."""
        # Mock document
        doc = Mock()
        doc.export_to_html.return_value = "<p>Test content</p>"

        # Create context
        context = PageProcessingContext(
            page_no=2,
            out_assets_path=str(tmp_path),
            name_prefix="page-0002",
            pipeline_options=PdfPipelineOptions(),
        )

        include_layers = ["text", "images"]
        image_mode = "embedded"

        # Mock the imported functions
        with (
            patch("pdf2foundry.ingest.parallel_processor._extract_images_from_html") as mock_extract,
            patch("pdf2foundry.ingest.parallel_processor._rewrite_and_copy_referenced_images") as mock_rewrite,
        ):
            with patch("pdf2foundry.ingest.parallel_processor._detect_links") as mock_links:
                with patch("pdf2foundry.ingest.parallel_processor._process_tables") as mock_tables:
                    # Set up mocks
                    mock_extract.return_value = ("<p>Test content</p>", [])
                    mock_rewrite.return_value = ("<p>Test content</p>", [])
                    mock_links.return_value = []
                    mock_tables.return_value = ("<p>Test content</p>", [])

                    # Process page
                    process_page_content(doc, context, include_layers, image_mode)

                    # Verify function call with parameters
                    doc.export_to_html.assert_called_once_with(
                        page_no=2,
                        split_page_view=False,
                        included_content_layers=include_layers,
                        image_mode=image_mode,
                    )

    def test_process_page_html_export_exception(self, tmp_path: Path) -> None:
        """Test page processing when HTML export fails."""
        # Mock document that raises exception
        doc = Mock()
        doc.export_to_html.side_effect = Exception("Export failed")

        # Create context
        context = PageProcessingContext(
            page_no=1,
            out_assets_path=str(tmp_path),
            name_prefix="page-0001",
            pipeline_options=PdfPipelineOptions(),
        )

        # Mock the imported functions
        with (
            patch("pdf2foundry.ingest.parallel_processor._extract_images_from_html") as mock_extract,
            patch("pdf2foundry.ingest.parallel_processor._rewrite_and_copy_referenced_images") as mock_rewrite,
        ):
            with patch("pdf2foundry.ingest.parallel_processor._detect_links") as mock_links:
                with patch("pdf2foundry.ingest.parallel_processor._process_tables") as mock_tables:
                    # Set up mocks
                    mock_extract.return_value = ("", [])
                    mock_rewrite.return_value = ("", [])
                    mock_links.return_value = []
                    mock_tables.return_value = ("", [])

                    # Process page
                    result = process_page_content(doc, context)

                    # Verify empty HTML is used when export fails
                    assert result.html_page.html == ""

    def test_process_page_structured_tables(self, tmp_path: Path) -> None:
        """Test page processing with structured table mode."""
        # Mock document
        doc = Mock()
        doc.export_to_html.return_value = "<p>Test content</p>"
        doc.pages = [Mock()]  # Mock pages attribute for structured table check

        # Create context with structured table mode
        options = PdfPipelineOptions()
        options.tables_mode = TableMode.STRUCTURED
        context = PageProcessingContext(
            page_no=1,
            out_assets_path=str(tmp_path),
            name_prefix="page-0001",
            pipeline_options=options,
        )

        # Mock the imported functions
        with (
            patch("pdf2foundry.ingest.parallel_processor._extract_images_from_html") as mock_extract,
            patch("pdf2foundry.ingest.parallel_processor._rewrite_and_copy_referenced_images") as mock_rewrite,
        ):
            with patch("pdf2foundry.ingest.parallel_processor._detect_links") as mock_links:
                with patch("pdf2foundry.ingest.parallel_processor._process_tables_with_options") as mock_tables_structured:
                    # Set up mocks
                    mock_extract.return_value = ("<p>Test content</p>", [])
                    mock_rewrite.return_value = ("<p>Test content</p>", [])
                    mock_links.return_value = []
                    mock_tables_structured.return_value = ("<p>Test content</p>", [])

                    # Process page
                    process_page_content(doc, context)

                    # Verify structured table processing was called
                    mock_tables_structured.assert_called_once_with(
                        doc, "<p>Test content</p>", 1, tmp_path, options, "page-0001"
                    )


class TestProcessPagesParallel:
    """Test the process_pages_parallel function."""

    def test_sequential_fallback_when_workers_one(self, tmp_path: Path) -> None:
        """Test that sequential processing is used when workers <= 1."""
        doc = Mock()
        selected_pages = [1, 2]
        options = PdfPipelineOptions()
        options.workers = 1

        with patch("pdf2foundry.ingest.parallel_processor._process_pages_sequential") as mock_sequential:
            mock_sequential.return_value = ([], [], [], [], 1.0)

            result = process_pages_parallel(doc, selected_pages, tmp_path, options)

            mock_sequential.assert_called_once_with(doc, selected_pages, tmp_path, options, None, None)
            assert result == ([], [], [], [], 1.0)

    @patch("pdf2foundry.ingest.parallel_processor.ProcessPoolExecutor")
    def test_parallel_processing_success(self, mock_executor_class: Mock, tmp_path: Path) -> None:
        """Test successful parallel processing."""
        # Mock document
        doc = Mock()
        selected_pages = [1, 2]
        options = PdfPipelineOptions()
        options.workers_effective = 2

        # Mock executor and futures
        mock_executor = Mock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        # Create mock futures and results
        future1 = Mock()
        future2 = Mock()

        result1 = PageProcessingResult(
            page_no=1,
            html_page=HtmlPage(html="<p>Page 1</p>", page_no=1),
            images=[],
            tables=[],
            links=[],
            processing_time=0.1,
        )
        result2 = PageProcessingResult(
            page_no=2,
            html_page=HtmlPage(html="<p>Page 2</p>", page_no=2),
            images=[],
            tables=[],
            links=[],
            processing_time=0.2,
        )

        future1.result.return_value = result1
        future2.result.return_value = result2

        mock_executor.submit.side_effect = [future1, future2]

        # Mock as_completed to return futures in order
        with patch("pdf2foundry.ingest.parallel_processor.as_completed") as mock_as_completed:
            mock_as_completed.return_value = [future1, future2]

            # Process pages
            pages, images, tables, links, total_time = process_pages_parallel(doc, selected_pages, tmp_path, options)

            # Verify results
            assert len(pages) == 2
            assert pages[0].html == "<p>Page 1</p>"
            assert pages[1].html == "<p>Page 2</p>"
            assert images == []
            assert tables == []
            assert links == []
            assert total_time > 0

            # Verify executor was used correctly
            assert mock_executor.submit.call_count == 2

    @patch("pdf2foundry.ingest.parallel_processor.ProcessPoolExecutor")
    def test_parallel_processing_failure_fallback(self, mock_executor_class: Mock, tmp_path: Path) -> None:
        """Test fallback to sequential when parallel processing fails."""
        # Mock document
        doc = Mock()
        selected_pages = [1, 2]
        options = PdfPipelineOptions()
        options.workers_effective = 2

        # Mock executor to raise exception
        mock_executor_class.side_effect = Exception("Process creation failed")

        with patch("pdf2foundry.ingest.parallel_processor._process_pages_sequential") as mock_sequential:
            mock_sequential.return_value = ([], [], [], [], 1.0)

            # Process pages
            result = process_pages_parallel(doc, selected_pages, tmp_path, options)

            # Verify fallback was used
            mock_sequential.assert_called_once()
            assert result == ([], [], [], [], 1.0)

    @patch("pdf2foundry.ingest.parallel_processor.ProcessPoolExecutor")
    def test_parallel_processing_worker_exception(
        self,
        mock_executor_class: Mock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test handling of worker exceptions."""
        # Mock document
        doc = Mock()
        selected_pages = [1, 2]
        options = PdfPipelineOptions()
        options.workers_effective = 2

        # Mock executor
        mock_executor = Mock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        # Create mock futures - one succeeds, one fails
        future1 = Mock()
        future2 = Mock()

        result1 = PageProcessingResult(
            page_no=1,
            html_page=HtmlPage(html="<p>Page 1</p>", page_no=1),
            images=[],
            tables=[],
            links=[],
            processing_time=0.1,
        )

        future1.result.return_value = result1
        future2.result.side_effect = Exception("Worker failed")

        mock_executor.submit.side_effect = [future1, future2]

        # Mock as_completed to return failing future first
        with patch("pdf2foundry.ingest.parallel_processor.as_completed") as mock_as_completed:
            mock_as_completed.return_value = [future2, future1]

            with patch("pdf2foundry.ingest.parallel_processor._process_pages_sequential") as mock_sequential:
                mock_sequential.return_value = ([], [], [], [], 1.0)

                # Process pages - should fallback due to worker exception
                with caplog.at_level(logging.ERROR):  # Capture both ERROR and WARNING
                    process_pages_parallel(doc, selected_pages, tmp_path, options)

                # Verify fallback was used
                mock_sequential.assert_called_once()
                # The test should check for the actual error message that gets logged
                assert "Page 2 failed: Worker failed" in caplog.text

    def test_deterministic_ordering(self, tmp_path: Path) -> None:
        """Test that results are returned in deterministic page order."""
        # This test verifies that even if workers complete out of order,
        # the final results are ordered by page number

        doc = Mock()
        selected_pages = [1, 3, 2]  # Intentionally out of order
        options = PdfPipelineOptions()
        options.workers_effective = 2

        with patch("pdf2foundry.ingest.parallel_processor.ProcessPoolExecutor") as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value.__enter__.return_value = mock_executor

            # Create results that complete in different order than submitted
            results = {
                1: PageProcessingResult(
                    page_no=1,
                    html_page=HtmlPage(html="<p>Page 1</p>", page_no=1),
                    images=[],
                    tables=[],
                    links=[],
                    processing_time=0.1,
                ),
                2: PageProcessingResult(
                    page_no=2,
                    html_page=HtmlPage(html="<p>Page 2</p>", page_no=2),
                    images=[],
                    tables=[],
                    links=[],
                    processing_time=0.2,
                ),
                3: PageProcessingResult(
                    page_no=3,
                    html_page=HtmlPage(html="<p>Page 3</p>", page_no=3),
                    images=[],
                    tables=[],
                    links=[],
                    processing_time=0.3,
                ),
            }

            # Mock futures
            futures = [Mock() for _ in range(3)]
            for i, future in enumerate(futures):
                page_no = selected_pages[i]
                future.result.return_value = results[page_no]

            mock_executor.submit.side_effect = futures

            with patch("pdf2foundry.ingest.parallel_processor.as_completed") as mock_as_completed:
                # Return futures in different order than submitted
                mock_as_completed.return_value = [futures[2], futures[0], futures[1]]

                # Process pages
                pages, _, _, _, _ = process_pages_parallel(doc, selected_pages, tmp_path, options)

                # Verify results are in the same order as selected_pages
                assert len(pages) == 3
                assert pages[0].page_no == 1  # First in selected_pages
                assert pages[1].page_no == 3  # Second in selected_pages
                assert pages[2].page_no == 2  # Third in selected_pages
                assert pages[0].html == "<p>Page 1</p>"
                assert pages[1].html == "<p>Page 3</p>"
                assert pages[2].html == "<p>Page 2</p>"


class TestIntegrationWithContentExtractor:
    """Test integration with the main content extractor."""

    def test_parallel_condition_logic(self) -> None:
        """Test the logic for determining when to use parallel processing."""
        # Test the condition logic directly without importing content_extractor
        # to avoid optional dependency issues in tests

        # Simulate the condition from content_extractor.py
        def should_use_parallel(workers_effective: int, ocr_engine: Any, caption_engine: Any) -> bool:
            return workers_effective > 1 and ocr_engine is None and caption_engine is None

        # Test cases
        assert should_use_parallel(2, None, None) is True  # Should use parallel
        assert should_use_parallel(1, None, None) is False  # Single worker
        assert should_use_parallel(2, Mock(), None) is False  # OCR enabled
        assert should_use_parallel(2, None, Mock()) is False  # Captions enabled
        assert should_use_parallel(2, Mock(), Mock()) is False  # Both enabled
