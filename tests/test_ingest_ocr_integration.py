"""Integration tests for OCR functionality in content extraction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from pdf2foundry.ingest.content_extractor import extract_semantic_content
from pdf2foundry.ingest.ocr_engine import OcrResult
from pdf2foundry.ingest.ocr_processor import _merge_ocr_results, _rasterize_page, apply_ocr_to_page
from pdf2foundry.model.pipeline_options import OcrMode, PdfPipelineOptions


class TestApplyOcrToPage:
    """Test _apply_ocr_to_page function."""

    def test_ocr_not_needed_auto_mode_high_coverage(self) -> None:
        """Test that OCR is skipped in AUTO mode with high text coverage."""
        doc = Mock()
        # HTML with lots of text (high coverage)
        html = "<p>" + "This is a lot of text content. " * 100 + "</p>"
        options = PdfPipelineOptions(ocr_mode=OcrMode.AUTO, text_coverage_threshold=0.05)
        engine = Mock()
        cache = Mock()

        result = apply_ocr_to_page(doc, html, 1, options, engine, cache)

        assert result == html
        engine.is_available.assert_not_called()

    def test_ocr_needed_but_engine_unavailable_on_mode(self) -> None:
        """Test OCR needed but engine unavailable in ON mode."""
        doc = Mock()
        html = "<img src='test.png'>"
        options = PdfPipelineOptions(ocr_mode=OcrMode.ON)
        engine = Mock()
        engine.is_available.return_value = False
        cache = Mock()

        with patch("pdf2foundry.ingest.ocr_processor.logger") as mock_logger:
            result = apply_ocr_to_page(doc, html, 1, options, engine, cache)

            assert result == html
            engine.is_available.assert_called_once()
            # Should log error in ON mode
            mock_logger.error.assert_called()

    def test_ocr_needed_but_engine_unavailable_auto_mode(self) -> None:
        """Test OCR needed but engine unavailable in AUTO mode."""
        doc = Mock()
        html = "<img src='test.png'>"
        options = PdfPipelineOptions(ocr_mode=OcrMode.AUTO, text_coverage_threshold=0.05)
        engine = Mock()
        engine.is_available.return_value = False
        cache = Mock()

        with patch("pdf2foundry.ingest.ocr_processor.logger") as mock_logger:
            result = apply_ocr_to_page(doc, html, 1, options, engine, cache)

            assert result == html
            engine.is_available.assert_called_once()
            # Should log warning in AUTO mode
            mock_logger.warning.assert_called()

    def test_ocr_page_rasterization_fails(self) -> None:
        """Test OCR when page rasterization fails."""
        doc = Mock()
        html = "<img src='test.png'>"
        options = PdfPipelineOptions(ocr_mode=OcrMode.ON)
        engine = Mock()
        engine.is_available.return_value = True
        cache = Mock()

        with (
            patch("pdf2foundry.ingest.ocr_processor._rasterize_page", return_value=None),
            patch("pdf2foundry.ingest.ocr_processor.logger") as mock_logger,
        ):
            result = apply_ocr_to_page(doc, html, 1, options, engine, cache)

            assert result == html
            mock_logger.warning.assert_called()

    def test_ocr_success_with_cache_miss(self) -> None:
        """Test successful OCR processing with cache miss."""
        doc = Mock()
        html = "<img src='test.png'>"
        options = PdfPipelineOptions(ocr_mode=OcrMode.ON)
        engine = Mock()
        engine.is_available.return_value = True
        cache = Mock()
        cache.get.return_value = None  # Cache miss

        mock_image = Mock()
        ocr_results = [OcrResult("Extracted text", confidence=0.9)]
        engine.run.return_value = ocr_results

        with (
            patch("pdf2foundry.ingest.ocr_processor._rasterize_page", return_value=mock_image),
            patch("pdf2foundry.ingest.ocr_processor._merge_ocr_results") as mock_merge,
            patch("pdf2foundry.ingest.content_extractor.logging"),
        ):
            mock_merge.return_value = html + "\n<div>OCR content</div>"

            result = apply_ocr_to_page(doc, html, 1, options, engine, cache)

            # Verify OCR was run and cached
            engine.run.assert_called_once_with(mock_image)
            cache.set.assert_called_once_with(mock_image, None, ocr_results)
            mock_merge.assert_called_once_with(ocr_results, html)

            assert "OCR content" in result

    def test_ocr_success_with_cache_hit(self) -> None:
        """Test successful OCR processing with cache hit."""
        doc = Mock()
        html = "<img src='test.png'>"
        options = PdfPipelineOptions(ocr_mode=OcrMode.ON)
        engine = Mock()
        engine.is_available.return_value = True
        cache = Mock()

        # Cache hit
        cached_results = [OcrResult("Cached text", confidence=0.8)]
        cache.get.return_value = cached_results

        mock_image = Mock()

        with (
            patch("pdf2foundry.ingest.ocr_processor._rasterize_page", return_value=mock_image),
            patch("pdf2foundry.ingest.ocr_processor._merge_ocr_results") as mock_merge,
            patch("pdf2foundry.ingest.content_extractor.logging"),
        ):
            mock_merge.return_value = html + "\n<div>Cached OCR content</div>"

            result = apply_ocr_to_page(doc, html, 1, options, engine, cache)

            # Verify OCR was not run (cache hit)
            engine.run.assert_not_called()
            cache.set.assert_not_called()
            mock_merge.assert_called_once_with(cached_results, html)

            assert "Cached OCR content" in result

    def test_ocr_no_results_found(self) -> None:
        """Test OCR when no text is extracted."""
        doc = Mock()
        html = "<img src='test.png'>"
        options = PdfPipelineOptions(ocr_mode=OcrMode.ON)
        engine = Mock()
        engine.is_available.return_value = True
        cache = Mock()
        cache.get.return_value = None

        mock_image = Mock()
        engine.run.return_value = []  # No OCR results

        with (
            patch("pdf2foundry.ingest.ocr_processor._rasterize_page", return_value=mock_image),
            patch("pdf2foundry.ingest.ocr_processor.logger") as mock_logger,
        ):
            result = apply_ocr_to_page(doc, html, 1, options, engine, cache)

            assert result == html
            mock_logger.info.assert_called()

    def test_ocr_processing_exception_on_mode(self) -> None:
        """Test OCR processing exception in ON mode."""
        doc = Mock()
        html = "<img src='test.png'>"
        options = PdfPipelineOptions(ocr_mode=OcrMode.ON)
        engine = Mock()
        engine.is_available.return_value = True
        cache = Mock()

        mock_image = Mock()

        with (
            patch("pdf2foundry.ingest.ocr_processor._rasterize_page", return_value=mock_image),
            patch("pdf2foundry.ingest.ocr_processor.logger") as mock_logger,
        ):
            engine.run.side_effect = Exception("OCR failed")

            result = apply_ocr_to_page(doc, html, 1, options, engine, cache)

            assert result == html
            mock_logger.error.assert_called()

    def test_ocr_processing_exception_auto_mode(self) -> None:
        """Test OCR processing exception in AUTO mode."""
        doc = Mock()
        html = "<img src='test.png'>"
        options = PdfPipelineOptions(ocr_mode=OcrMode.AUTO, text_coverage_threshold=0.05)
        engine = Mock()
        engine.is_available.return_value = True
        cache = Mock()

        mock_image = Mock()

        with (
            patch("pdf2foundry.ingest.ocr_processor._rasterize_page", return_value=mock_image),
            patch("pdf2foundry.ingest.ocr_processor.logger") as mock_logger,
        ):
            engine.run.side_effect = Exception("OCR failed")

            result = apply_ocr_to_page(doc, html, 1, options, engine, cache)

            assert result == html
            mock_logger.warning.assert_called()


class TestRasterizePage:
    """Test _rasterize_page function."""

    def test_rasterize_with_docling_render_page(self) -> None:
        """Test page rasterization using Docling's render_page method."""
        doc = Mock()
        doc.pages = True  # Has pages attribute
        mock_image = Mock()
        doc.render_page.return_value = mock_image

        result = _rasterize_page(doc, 5)

        doc.render_page.assert_called_once_with(4)  # 0-based indexing
        assert result == mock_image

    def test_rasterize_without_docling_methods(self) -> None:
        """Test page rasterization fallback when Docling methods not available."""
        doc = Mock()
        # No pages attribute or render_page method
        del doc.pages

        result = _rasterize_page(doc, 1)

        assert result is None

    def test_rasterize_exception(self) -> None:
        """Test page rasterization when exception occurs."""
        doc = Mock()
        doc.pages = True
        doc.render_page.side_effect = Exception("Render failed")

        result = _rasterize_page(doc, 1)

        assert result is None


class TestMergeOcrResults:
    """Test _merge_ocr_results function."""

    def test_merge_empty_results(self) -> None:
        """Test merging with empty OCR results."""
        html = "<p>Original content</p>"
        result = _merge_ocr_results([], html)
        assert result == html

    def test_merge_with_body_tag(self) -> None:
        """Test merging OCR results with HTML containing body tag."""
        html = "<html><body><p>Original</p></body></html>"
        ocr_results = [OcrResult("OCR text")]

        result = _merge_ocr_results(ocr_results, html)

        assert '<div class="ocr-content" data-source="ocr">' in result
        assert 'data-ocr="true"' in result
        assert "OCR text" in result
        assert result.endswith("</body></html>")

    def test_merge_with_html_tag_no_body(self) -> None:
        """Test merging OCR results with HTML tag but no body."""
        html = "<html><p>Original</p></html>"
        ocr_results = [OcrResult("OCR text")]

        result = _merge_ocr_results(ocr_results, html)

        assert '<div class="ocr-content" data-source="ocr">' in result
        assert "OCR text" in result
        assert result.endswith("</html>")

    def test_merge_without_html_tags(self) -> None:
        """Test merging OCR results with plain HTML content."""
        html = "<p>Original content</p>"
        ocr_results = [OcrResult("OCR text")]

        result = _merge_ocr_results(ocr_results, html)

        assert result.startswith("<p>Original content</p>")
        assert '<div class="ocr-content" data-source="ocr">' in result
        assert "OCR text" in result

    def test_merge_multiple_results(self) -> None:
        """Test merging multiple OCR results."""
        html = "<p>Original</p>"
        ocr_results = [
            OcrResult("First text"),
            OcrResult("Second text"),
            OcrResult(""),  # Empty text should be skipped
            OcrResult("   "),  # Whitespace-only should be skipped
            OcrResult("Third text"),
        ]

        result = _merge_ocr_results(ocr_results, html)

        assert "First text" in result
        assert "Second text" in result
        assert "Third text" in result
        # Should have 4 <p> tags total (1 original + 3 OCR results)
        # Count both <p> and <p with attributes
        p_count = result.count("<p>") + result.count("<p ")
        assert p_count == 4

    def test_merge_with_metadata(self) -> None:
        """Test merging OCR results with full metadata."""
        html = "<p>Original</p>"
        ocr_results = [
            OcrResult(
                text="Test text", confidence=0.95, language="eng", bbox=(10.0, 20.0, 100.0, 50.0)
            )
        ]

        result = _merge_ocr_results(ocr_results, html)

        assert 'data-ocr="true"' in result
        assert 'data-ocr-confidence="0.950"' in result
        assert 'data-ocr-language="eng"' in result
        assert 'data-bbox="10.0,20.0,100.0,50.0"' in result


class TestExtractSemanticContentOcrIntegration:
    """Test OCR integration in extract_semantic_content function."""

    def test_ocr_initialization_auto_mode(self) -> None:
        """Test that OCR components are initialized in AUTO mode."""
        doc = Mock()
        doc.num_pages.return_value = 1
        doc.export_to_html.return_value = "<p>Test content</p>"

        options = PdfPipelineOptions(ocr_mode=OcrMode.AUTO)

        with (
            patch("pdf2foundry.ingest.content_extractor.TesseractOcrEngine") as mock_engine_class,
            patch("pdf2foundry.ingest.content_extractor.OcrCache") as mock_cache_class,
        ):
            mock_engine = Mock()
            mock_engine.is_available.return_value = True
            mock_engine_class.return_value = mock_engine

            extract_semantic_content(doc, Path("/tmp"), options)

            # OCR components should be initialized
            mock_engine_class.assert_called_once()
            mock_cache_class.assert_called_once()

    def test_ocr_initialization_on_mode(self) -> None:
        """Test OCR components initialization in ON mode."""
        doc = Mock()
        doc.num_pages.return_value = 1
        doc.export_to_html.return_value = "<p>Test content</p>"
        doc.pages = []  # Make it iterable
        doc.render_page = Mock(return_value=None)  # Mock render_page method

        options = PdfPipelineOptions(ocr_mode=OcrMode.ON)

        mock_engine = Mock()
        mock_engine.is_available.return_value = True
        mock_cache = Mock()

        with (
            patch(
                "pdf2foundry.ingest.content_extractor.TesseractOcrEngine", return_value=mock_engine
            ),
            patch("pdf2foundry.ingest.content_extractor.OcrCache", return_value=mock_cache),
            patch("pdf2foundry.ingest.content_extractor.apply_ocr_to_page") as mock_apply_ocr,
        ):
            mock_apply_ocr.return_value = "<p>Test content</p>"

            extract_semantic_content(doc, Path("/tmp"), options)

            # OCR components should be initialized and used
            mock_engine.is_available.assert_called()
            mock_apply_ocr.assert_called()

    def test_ocr_initialization_failure(self) -> None:
        """Test graceful handling of OCR initialization failure."""
        doc = Mock()
        doc.num_pages.return_value = 1
        doc.export_to_html.return_value = "<p>Test content</p>"

        options = PdfPipelineOptions(ocr_mode=OcrMode.ON)

        with (
            patch(
                "pdf2foundry.ingest.content_extractor.TesseractOcrEngine",
                side_effect=Exception("Init failed"),
            ),
            patch("pdf2foundry.ingest.content_extractor.logger") as mock_logger,
        ):
            # Should not raise exception
            result = extract_semantic_content(doc, Path("/tmp"), options)

            # Should log warning and continue
            mock_logger.warning.assert_called()
            assert len(result.pages) == 1

    def test_ocr_progress_callbacks(self) -> None:
        """Test OCR progress callback emissions."""
        doc = Mock()
        doc.num_pages.return_value = 1
        doc.export_to_html.return_value = "<p>Test content</p>"
        doc.pages = []  # Make it iterable
        doc.render_page = Mock(return_value=None)  # Mock render_page method

        options = PdfPipelineOptions(ocr_mode=OcrMode.ON)
        progress_callback = Mock()

        mock_engine = Mock()
        mock_engine.is_available.return_value = True
        mock_cache = Mock()

        with (
            patch(
                "pdf2foundry.ingest.content_extractor.TesseractOcrEngine", return_value=mock_engine
            ),
            patch("pdf2foundry.ingest.content_extractor.OcrCache", return_value=mock_cache),
            patch("pdf2foundry.ingest.content_extractor.apply_ocr_to_page") as mock_apply_ocr,
        ):
            mock_apply_ocr.return_value = "<p>Test content</p>"

            extract_semantic_content(doc, Path("/tmp"), options, progress_callback)

            # Check that OCR initialization progress was emitted
            progress_calls = progress_callback.call_args_list
            ocr_events = [call for call in progress_calls if "ocr:" in call[0][0]]
            assert len(ocr_events) > 0
