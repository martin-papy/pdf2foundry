from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from pdf2foundry.ingest.content_extractor import extract_semantic_content
from pdf2foundry.model.pipeline_options import PdfPipelineOptions


class _Doc:
    def __init__(self, pages: int) -> None:
        self._pages = pages

    def num_pages(self) -> int:
        return self._pages

    def export_to_html(self, **_: Any) -> str:
        # include one embedded image, one table, and one link
        # Use a valid 1x1 pixel PNG in base64
        valid_png_b64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJ"
            "TYQAAAAASUVORK5CYII="
        )
        return (
            '<div class="p">Hello'
            f'<img src="data:image/png;base64,{valid_png_b64}">'
            "<table><tr><td>A</td></tr></table>"
            '<a href="https://example.com">link</a>'
            "</div>"
        )


def test_extract_semantic_content(tmp_path: Path) -> None:
    doc = _Doc(2)

    events: list[dict[str, Any]] = []

    def on_progress(event: str, payload: dict[str, Any]) -> None:
        events.append({"event": event, **payload})

    out = extract_semantic_content(
        doc, tmp_path / "assets", options="auto", on_progress=on_progress
    )
    # two pages created
    assert len(out.pages) == 2
    # at least one image extracted
    assert out.images
    # at least one table recorded (html mode)
    assert out.tables and out.tables[0].kind in ("html", "image")
    # links detected
    assert out.links
    # events contain extract_content:start and extract_content:success
    assert events[0]["event"] == "extract_content:start"
    assert events[-1]["event"] == "extract_content:success"


def test_extract_semantic_content_no_contentlayer(monkeypatch: Any, tmp_path: Path) -> None:
    # Force import failure for ContentLayer path
    import sys

    sys.modules.pop("docling_core.types.doc.document", None)
    doc = _Doc(1)
    out = extract_semantic_content(doc, tmp_path / "assets2", options="image-only")
    assert len(out.pages) == 1
    # in image-only mode, tables become images
    assert out.tables and out.tables[0].kind == "image"


class TestCaptionIntegration:
    """Test caption functionality integration with content extraction."""

    def test_extract_content_with_captions_disabled(self, tmp_path: Path) -> None:
        """Test content extraction with picture descriptions disabled."""
        doc = _Doc(1)
        options = PdfPipelineOptions(picture_descriptions=False)

        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        out = extract_semantic_content(doc, tmp_path / "assets", options, on_progress)

        # Images should be extracted but not captioned
        assert len(out.images) > 0
        for image in out.images:
            assert image.caption is None
            assert image.alt_text is None

        # No caption events should be emitted
        caption_events = [e for e in events if e["event"].startswith("caption:")]
        assert len(caption_events) == 0

    def test_extract_content_with_captions_no_vlm_repo_id(self, tmp_path: Path) -> None:
        """Test content extraction with picture descriptions enabled but no VLM repo ID."""
        doc = _Doc(1)
        options = PdfPipelineOptions(picture_descriptions=True, vlm_repo_id=None)

        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        out = extract_semantic_content(doc, tmp_path / "assets", options, on_progress)

        # Images should be extracted but not captioned
        assert len(out.images) > 0
        for image in out.images:
            assert image.caption is None
            assert image.alt_text is None

        # Should have caption:no_model event
        caption_events = [e for e in events if e["event"].startswith("caption:")]
        assert len(caption_events) == 1
        assert caption_events[0]["event"] == "caption:no_model"
        assert caption_events[0]["reason"] == "no_vlm_repo_id"

    @patch("pdf2foundry.ingest.caption_processor.HFCaptionEngine")
    def test_extract_content_with_captions_engine_unavailable(
        self, mock_engine_class: Mock, tmp_path: Path
    ) -> None:
        """Test content extraction when caption engine is unavailable."""
        # Mock engine to be unavailable
        mock_engine = Mock()
        mock_engine.is_available.return_value = False
        mock_engine_class.return_value = mock_engine

        doc = _Doc(1)
        options = PdfPipelineOptions(
            picture_descriptions=True, vlm_repo_id="microsoft/Florence-2-base"
        )

        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        out = extract_semantic_content(doc, tmp_path / "assets", options, on_progress)

        # Images should be extracted but not captioned
        assert len(out.images) > 0
        for image in out.images:
            assert image.caption is None
            assert image.alt_text is None

        # Should have caption:unavailable event
        caption_events = [e for e in events if e["event"].startswith("caption:")]
        assert len(caption_events) == 1
        assert caption_events[0]["event"] == "caption:unavailable"
        assert caption_events[0]["model_id"] == "microsoft/Florence-2-base"

    @patch("pdf2foundry.ingest.caption_processor.HFCaptionEngine")
    def test_extract_content_with_captions_init_failure(
        self, mock_engine_class: Mock, tmp_path: Path
    ) -> None:
        """Test content extraction when caption engine initialization fails."""
        # Mock engine initialization to fail
        mock_engine_class.side_effect = RuntimeError("Model not found")

        doc = _Doc(1)
        options = PdfPipelineOptions(picture_descriptions=True, vlm_repo_id="nonexistent/model")

        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        out = extract_semantic_content(doc, tmp_path / "assets", options, on_progress)

        # Images should be extracted but not captioned
        assert len(out.images) > 0
        for image in out.images:
            assert image.caption is None
            assert image.alt_text is None

        # Should have caption:init_failed event
        caption_events = [e for e in events if e["event"].startswith("caption:")]
        assert len(caption_events) == 1
        assert caption_events[0]["event"] == "caption:init_failed"
        assert caption_events[0]["model_id"] == "nonexistent/model"
        assert "Model not found" in caption_events[0]["error"]

    @patch("pdf2foundry.ingest.caption_processor.HFCaptionEngine")
    @patch("pdf2foundry.ingest.caption_processor.CaptionCache")
    def test_extract_content_with_captions_success(
        self, mock_cache_class: Mock, mock_engine_class: Mock, tmp_path: Path
    ) -> None:
        """Test successful content extraction with captions."""
        # Mock successful caption engine
        mock_engine = Mock()
        mock_engine.is_available.return_value = True
        mock_engine.generate.return_value = "A test image caption"
        mock_engine_class.return_value = mock_engine

        # Mock cache
        mock_cache = Mock()
        mock_cache.get.return_value = object()  # Cache miss (sentinel object)
        mock_cache_class.return_value = mock_cache

        doc = _Doc(1)
        options = PdfPipelineOptions(
            picture_descriptions=True, vlm_repo_id="microsoft/Florence-2-base"
        )

        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        out = extract_semantic_content(doc, tmp_path / "assets", options, on_progress)

        # Images should be extracted and captioned
        assert len(out.images) > 0
        for image in out.images:
            assert image.caption == "A test image caption"
            assert image.alt_text == "A test image caption"

        # Should have caption events
        caption_events = [e for e in events if e["event"].startswith("caption:")]
        assert len(caption_events) >= 2  # initialized + batch_completed

        # Check for initialization event
        init_events = [e for e in caption_events if e["event"] == "caption:initialized"]
        assert len(init_events) == 1
        assert init_events[0]["model_id"] == "microsoft/Florence-2-base"

        # Check for completion event
        completion_events = [e for e in caption_events if e["event"] == "caption:batch_completed"]
        assert len(completion_events) == 1
        assert completion_events[0]["total_images"] == len(out.images)
        assert completion_events[0]["captioned_count"] == len(out.images)

    @patch("pdf2foundry.ingest.caption_processor.HFCaptionEngine")
    @patch("pdf2foundry.ingest.caption_processor.CaptionCache")
    def test_extract_content_with_captions_cache_hit(
        self, mock_cache_class: Mock, mock_engine_class: Mock, tmp_path: Path
    ) -> None:
        """Test content extraction with caption cache hit."""
        # Mock successful caption engine
        mock_engine = Mock()
        mock_engine.is_available.return_value = True
        mock_engine_class.return_value = mock_engine

        # Mock cache with hit
        mock_cache = Mock()
        mock_cache.get.return_value = "Cached caption"
        mock_cache_class.return_value = mock_cache

        doc = _Doc(1)
        options = PdfPipelineOptions(
            picture_descriptions=True, vlm_repo_id="microsoft/Florence-2-base"
        )

        out = extract_semantic_content(doc, tmp_path / "assets", options)

        # Images should be captioned with cached caption
        assert len(out.images) > 0
        for image in out.images:
            assert image.caption == "Cached caption"
            assert image.alt_text == "Cached caption"

        # Engine generate should not be called due to cache hit
        mock_engine.generate.assert_not_called()

    @patch("pdf2foundry.ingest.caption_processor.HFCaptionEngine")
    @patch("pdf2foundry.ingest.caption_processor.CaptionCache")
    def test_extract_content_with_captions_no_caption_generated(
        self, mock_cache_class: Mock, mock_engine_class: Mock, tmp_path: Path
    ) -> None:
        """Test content extraction when no caption is generated."""
        # Mock caption engine that returns None
        mock_engine = Mock()
        mock_engine.is_available.return_value = True
        mock_engine.generate.return_value = None
        mock_engine_class.return_value = mock_engine

        # Mock cache miss
        mock_cache = Mock()
        mock_cache.get.return_value = object()  # Cache miss (sentinel object)
        mock_cache_class.return_value = mock_cache

        doc = _Doc(1)
        options = PdfPipelineOptions(
            picture_descriptions=True, vlm_repo_id="microsoft/Florence-2-base"
        )

        out = extract_semantic_content(doc, tmp_path / "assets", options)

        # Images should be extracted but not captioned
        assert len(out.images) > 0
        for image in out.images:
            assert image.caption is None
            assert image.alt_text is None
