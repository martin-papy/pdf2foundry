"""Tests for initialize_caption_components function."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch

from pdf2foundry.ingest.caption_processor import initialize_caption_components
from pdf2foundry.model.pipeline_options import PdfPipelineOptions


class TestInitializeCaptionComponents:
    """Test initialize_caption_components function."""

    def test_initialize_disabled(self) -> None:
        """Test initialization when picture descriptions are disabled."""
        options = PdfPipelineOptions(picture_descriptions=False)

        # Track progress events
        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        engine, cache = initialize_caption_components(options, on_progress)

        assert engine is None
        assert cache is None
        assert len(events) == 0

    def test_initialize_no_vlm_repo_id(self) -> None:
        """Test initialization when no VLM repo ID is provided."""
        options = PdfPipelineOptions(picture_descriptions=True, vlm_repo_id=None)

        # Track progress events
        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        engine, cache = initialize_caption_components(options, on_progress)

        assert engine is None
        assert cache is None

        # Should emit no_model event
        assert len(events) == 1
        assert events[0]["event"] == "caption:no_model"
        assert events[0]["reason"] == "no_vlm_repo_id"

    @patch("pdf2foundry.ingest.caption_processor.HFCaptionEngine")
    @patch("pdf2foundry.ingest.caption_processor.CaptionCache")
    def test_initialize_success(self, mock_cache_class: Mock, mock_engine_class: Mock) -> None:
        """Test successful initialization."""
        options = PdfPipelineOptions(picture_descriptions=True, vlm_repo_id="microsoft/Florence-2-base")

        # Mock successful engine creation
        mock_engine = Mock()
        mock_engine.is_available.return_value = True
        mock_engine_class.return_value = mock_engine

        mock_cache = Mock()
        mock_cache_class.return_value = mock_cache

        # Track progress events
        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        engine, cache = initialize_caption_components(options, on_progress)

        assert engine is mock_engine
        assert cache is mock_cache

        # Should create engine with correct model ID
        mock_engine_class.assert_called_once_with("microsoft/Florence-2-base")
        mock_cache_class.assert_called_once_with(max_size=2000)

        # Should emit initialized event
        assert len(events) == 1
        assert events[0]["event"] == "caption:initialized"
        assert events[0]["model_id"] == "microsoft/Florence-2-base"

    @patch("pdf2foundry.ingest.caption_processor.HFCaptionEngine")
    @patch("pdf2foundry.ingest.caption_processor.CaptionCache")
    def test_initialize_engine_unavailable(self, mock_cache_class: Mock, mock_engine_class: Mock) -> None:
        """Test initialization when engine is unavailable."""
        options = PdfPipelineOptions(picture_descriptions=True, vlm_repo_id="microsoft/Florence-2-base")

        # Mock engine that's unavailable
        mock_engine = Mock()
        mock_engine.is_available.return_value = False
        mock_engine_class.return_value = mock_engine

        mock_cache = Mock()
        mock_cache_class.return_value = mock_cache

        # Track progress events
        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        engine, cache = initialize_caption_components(options, on_progress)

        assert engine is mock_engine  # Engine is returned even if unavailable
        assert cache is mock_cache

        # Should emit unavailable event
        assert len(events) == 1
        assert events[0]["event"] == "caption:unavailable"
        assert events[0]["model_id"] == "microsoft/Florence-2-base"

    @patch("pdf2foundry.ingest.caption_processor.HFCaptionEngine")
    def test_initialize_engine_creation_error(self, mock_engine_class: Mock) -> None:
        """Test initialization when engine creation fails."""
        options = PdfPipelineOptions(picture_descriptions=True, vlm_repo_id="nonexistent/model")

        # Mock engine creation failure
        mock_engine_class.side_effect = Exception("Model not found")

        # Track progress events
        events: list[dict[str, Any]] = []

        def on_progress(event: str, payload: dict[str, Any]) -> None:
            events.append({"event": event, **payload})

        engine, cache = initialize_caption_components(options, on_progress)

        assert engine is None
        assert cache is None

        # Should emit init_failed event
        assert len(events) == 1
        assert events[0]["event"] == "caption:init_failed"
        assert events[0]["model_id"] == "nonexistent/model"
        assert events[0]["error"] == "Model not found"

    @patch("pdf2foundry.ingest.caption_processor.HFCaptionEngine")
    @patch("pdf2foundry.ingest.caption_processor.CaptionCache")
    def test_initialize_with_shared_cache_limits(self, mock_cache_class: Mock, mock_engine_class: Mock) -> None:
        """Test initialization with shared image cache limits."""
        options = PdfPipelineOptions(picture_descriptions=True, vlm_repo_id="microsoft/Florence-2-base")

        # Mock successful engine creation
        mock_engine = Mock()
        mock_engine.is_available.return_value = True
        mock_engine_class.return_value = mock_engine

        mock_cache = Mock()
        mock_cache_class.return_value = mock_cache

        # Mock shared image cache with limits
        shared_cache = Mock()
        shared_cache._limits = Mock()
        shared_cache._limits.caption_cache = 5000

        engine, cache = initialize_caption_components(options, shared_image_cache=shared_cache)

        assert engine is mock_engine
        assert cache is mock_cache

        # Should use cache size from shared cache
        mock_cache_class.assert_called_once_with(max_size=5000)
