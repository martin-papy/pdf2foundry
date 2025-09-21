"""Tests for OCR engine functionality (fixed version)."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from PIL import Image  # type: ignore[import-not-found]

from pdf2foundry.ingest.ocr_engine import (
    OcrCache,
    OcrResult,
    TesseractOcrEngine,
    compute_text_coverage,
    needs_ocr,
)


class TestOcrResult:
    """Test OcrResult class."""

    def test_init_basic(self) -> None:
        """Test basic OcrResult initialization."""
        result = OcrResult("Hello world")
        assert result.text == "Hello world"
        assert result.confidence == 0.0
        assert result.language is None
        assert result.bbox is None

    def test_init_full(self) -> None:
        """Test OcrResult initialization with all parameters."""
        result = OcrResult(
            text="Hello world",
            confidence=0.95,
            language="eng",
            bbox=(10.0, 20.0, 100.0, 50.0),
        )
        assert result.text == "Hello world"
        assert result.confidence == 0.95
        assert result.language == "eng"
        assert result.bbox == (10.0, 20.0, 100.0, 50.0)

    def test_to_html_span_basic(self) -> None:
        """Test HTML span generation with basic result."""
        result = OcrResult("Hello world")
        html = result.to_html_span()
        assert 'data-ocr="true"' in html
        assert "Hello world" in html
        assert html.startswith("<span")
        assert html.endswith("</span>")

    def test_to_html_span_full(self) -> None:
        """Test HTML span generation with full metadata."""
        result = OcrResult(
            text="Hello world",
            confidence=0.95,
            language="eng",
            bbox=(10.0, 20.0, 100.0, 50.0),
        )
        html = result.to_html_span()
        assert 'data-ocr="true"' in html
        assert 'data-ocr-confidence="0.950"' in html
        assert 'data-ocr-language="eng"' in html
        assert 'data-bbox="10.0,20.0,100.0,50.0"' in html
        assert "Hello world" in html

    def test_html_escaping(self) -> None:
        """Test HTML special character escaping."""
        result = OcrResult('<script>alert("test")</script>')
        html = result.to_html_span()
        assert "&lt;script&gt;" in html
        assert "&quot;test&quot;" in html
        assert "<script>" not in html


class TestTesseractOcrEngine:
    """Test TesseractOcrEngine class."""

    def test_init(self) -> None:
        """Test engine initialization."""
        engine = TesseractOcrEngine()
        assert engine._pytesseract is None
        assert engine._available is None

    def test_is_available_success(self) -> None:
        """Test availability check when tesseract is available."""
        engine = TesseractOcrEngine()

        mock_pytesseract = Mock()
        mock_pytesseract.get_tesseract_version.return_value = "5.0.0"

        def mock_ensure() -> Mock:
            engine._available = True
            return mock_pytesseract

        with patch.object(engine, "_ensure_pytesseract", side_effect=mock_ensure):
            assert engine.is_available() is True
            assert engine._available is True

    def test_is_available_import_error(self) -> None:
        """Test availability check when pytesseract is not installed."""
        engine = TesseractOcrEngine()

        def mock_ensure_fail() -> None:
            engine._available = False
            raise ImportError("No module")

        with patch.object(engine, "_ensure_pytesseract", side_effect=mock_ensure_fail):
            assert engine.is_available() is False
            assert engine._available is False

    def test_is_available_tesseract_error(self) -> None:
        """Test availability check when tesseract binary is not available."""
        engine = TesseractOcrEngine()

        def mock_ensure_fail() -> None:
            engine._available = False
            raise ImportError("Tesseract not found")

        with patch.object(engine, "_ensure_pytesseract", side_effect=mock_ensure_fail):
            assert engine.is_available() is False
            assert engine._available is False

    def test_run_pil_image(self) -> None:
        """Test OCR with PIL Image input."""
        engine = TesseractOcrEngine()

        # Create a mock PIL image
        mock_image = Mock(spec=Image.Image)

        # Mock pytesseract
        mock_pytesseract = Mock()
        mock_pytesseract.image_to_string.return_value = "Hello world"
        mock_pytesseract.image_to_data.return_value = {"conf": ["95", "90", "85"]}
        mock_pytesseract.image_to_osd.return_value = {"script": "Latin"}
        mock_pytesseract.Output.DICT = "dict"

        with patch.object(engine, "_ensure_pytesseract", return_value=mock_pytesseract):
            results = engine.run(mock_image)

            assert len(results) == 1
            assert results[0].text == "Hello world"
            assert results[0].confidence == 0.9  # (95+90+85)/3/100
            assert results[0].language == "Latin"

    def test_run_empty_text(self) -> None:
        """Test OCR when no text is found."""
        engine = TesseractOcrEngine()

        mock_image = Mock(spec=Image.Image)

        # Mock pytesseract returning empty text
        mock_pytesseract = Mock()
        mock_pytesseract.image_to_string.return_value = ""
        mock_pytesseract.image_to_data.return_value = {"conf": []}
        mock_pytesseract.Output.DICT = "dict"

        with patch.object(engine, "_ensure_pytesseract", return_value=mock_pytesseract):
            results = engine.run(mock_image)
            assert len(results) == 0

    def test_run_ocr_error(self) -> None:
        """Test OCR when processing fails."""
        engine = TesseractOcrEngine()

        mock_image = Mock(spec=Image.Image)

        # Mock pytesseract raising an exception
        mock_pytesseract = Mock()
        mock_pytesseract.image_to_string.side_effect = Exception("OCR failed")
        mock_pytesseract.Output.DICT = "dict"

        with (
            patch.object(engine, "_ensure_pytesseract", return_value=mock_pytesseract),
            pytest.raises(Exception, match="OCR failed"),
        ):
            engine.run(mock_image)

    def test_run_unavailable_engine(self) -> None:
        """Test running OCR when engine is not available."""
        engine = TesseractOcrEngine()

        with (
            patch.object(
                engine,
                "_ensure_pytesseract",
                side_effect=ImportError("pytesseract not available: No module"),
            ),
            pytest.raises(ImportError, match="pytesseract not available"),
        ):
            engine.run(Mock())


class TestOcrCache:
    """Test OcrCache class."""

    def test_init(self) -> None:
        """Test cache initialization."""
        cache = OcrCache()
        assert cache._cache == {}

    def test_get_set_basic(self) -> None:
        """Test basic cache get/set functionality."""
        cache = OcrCache()

        # Create mock image and results
        mock_image = Mock(spec=Image.Image)
        results = [OcrResult("test")]

        # Mock the hash generation
        with patch.object(cache, "_get_image_hash", return_value="hash123"):
            # Initially empty
            assert cache.get(mock_image) is None

            # Set and get
            cache.set(mock_image, None, results)
            cached = cache.get(mock_image)

            assert cached == results

    def test_get_set_with_language(self) -> None:
        """Test cache with language parameter."""
        cache = OcrCache()

        mock_image = Mock(spec=Image.Image)
        results_eng = [OcrResult("hello")]
        results_fra = [OcrResult("bonjour")]

        with patch.object(cache, "_get_image_hash", return_value="hash123"):
            # Set different results for different languages
            cache.set(mock_image, "eng", results_eng)
            cache.set(mock_image, "fra", results_fra)

            # Get correct results for each language
            assert cache.get(mock_image, "eng") == results_eng
            assert cache.get(mock_image, "fra") == results_fra
            assert cache.get(mock_image, "deu") is None

    def test_clear(self) -> None:
        """Test cache clearing."""
        cache = OcrCache()

        mock_image = Mock(spec=Image.Image)
        results = [OcrResult("test")]

        with patch.object(cache, "_get_image_hash", return_value="hash123"):
            cache.set(mock_image, None, results)
            assert cache.get(mock_image) == results

            cache.clear()
            assert cache.get(mock_image) is None

    def test_get_image_hash_bytes(self) -> None:
        """Test image hashing with bytes."""
        cache = OcrCache()

        image_bytes = b"raw_image_data"

        # This should work without mocking since it's just bytes
        result = cache._get_image_hash(image_bytes)

        # Should return a 16-character hex string
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)


class TestTextCoverage:
    """Test text coverage calculation."""

    def test_compute_text_coverage_empty(self) -> None:
        """Test coverage with empty HTML."""
        coverage = compute_text_coverage("")
        assert coverage == 0.0

    def test_compute_text_coverage_minimal_text(self) -> None:
        """Test coverage with minimal text content."""
        html = "<div><img src='test.png'></div>"
        coverage = compute_text_coverage(html)
        # Should be very low but not necessarily 0 due to spaces/punctuation
        assert coverage < 0.01

    def test_compute_text_coverage_some_text(self) -> None:
        """Test coverage with some text content."""
        html = "<p>Hello world! This is a test.</p>"
        coverage = compute_text_coverage(html)
        assert coverage > 0.0
        assert coverage < 1.0

    def test_compute_text_coverage_lots_of_text(self) -> None:
        """Test coverage with lots of text content."""
        # Create HTML with more than estimated page capacity
        long_text = "This is a test sentence. " * 200  # ~5000 chars
        html = f"<div>{long_text}</div>"
        coverage = compute_text_coverage(html)
        assert coverage == 1.0  # Capped at 1.0

    def test_compute_text_coverage_html_tags_ignored(self) -> None:
        """Test that HTML tags are ignored in coverage calculation."""
        html_with_tags = "<p><strong>Hello</strong> <em>world</em>!</p>"
        html_plain = "Hello world!"

        coverage_tags = compute_text_coverage(html_with_tags)
        coverage_plain = compute_text_coverage(html_plain)

        # Should be approximately equal (tags removed)
        assert abs(coverage_tags - coverage_plain) < 0.01


class TestNeedsOcr:
    """Test OCR necessity determination."""

    def test_needs_ocr_off_mode(self) -> None:
        """Test that OCR is never needed in OFF mode."""
        assert needs_ocr("", "off") is False
        assert needs_ocr("<p>Some text</p>", "off") is False
        assert needs_ocr("<img src='test.png'>", "off") is False

    def test_needs_ocr_on_mode(self) -> None:
        """Test that OCR is always needed in ON mode."""
        assert needs_ocr("", "on") is True
        assert needs_ocr("<p>Lots of text content here</p>", "on") is True
        assert needs_ocr("<img src='test.png'>", "on") is True

    def test_needs_ocr_auto_mode_low_coverage(self) -> None:
        """Test AUTO mode with low text coverage."""
        # Empty or minimal content should trigger OCR
        assert needs_ocr("", "auto", threshold=0.05) is True
        assert needs_ocr("<img src='test.png'>", "auto", threshold=0.05) is True

    def test_needs_ocr_auto_mode_high_coverage(self) -> None:
        """Test AUTO mode with high text coverage."""
        # Lots of text should not trigger OCR
        long_text = "This is a test sentence with lots of content. " * 100
        html = f"<div>{long_text}</div>"
        assert needs_ocr(html, "auto", threshold=0.05) is False

    def test_needs_ocr_auto_mode_threshold(self) -> None:
        """Test AUTO mode threshold behavior."""
        html = "<p>Short text</p>"

        # With high threshold, should need OCR
        assert needs_ocr(html, "auto", threshold=0.5) is True

        # With low threshold, should not need OCR
        assert needs_ocr(html, "auto", threshold=0.001) is False

    def test_needs_ocr_invalid_mode(self) -> None:
        """Test with invalid OCR mode."""
        assert needs_ocr("test", "invalid") is False
