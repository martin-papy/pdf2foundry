"""Advanced tests for caption engine functionality."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from PIL import Image

from pdf2foundry.ingest.caption_engine import HFCaptionEngine


class TestHFCaptionEngineAdvanced:
    """Advanced tests for HFCaptionEngine to improve coverage."""

    @pytest.fixture(autouse=True)
    def mock_logger(self, isolate_logging):
        """Mock the logger to prevent StreamHandler issues in CI."""
        with patch("pdf2foundry.ingest.caption_engine.logger") as mock_log:
            mock_log.warning = Mock()
            mock_log.error = Mock()
            mock_log.debug = Mock()
            mock_log.info = Mock()
            yield mock_log

    def test_is_available_ml_support_disabled(self) -> None:
        """Test availability check when ML support is disabled."""
        with patch("pdf2foundry.core.feature_detection.FeatureAvailability.has_ml_support", return_value=False):
            engine = HFCaptionEngine("microsoft/Florence-2-base")
            available = engine.is_available()
            assert available is False

    def test_is_available_transformers_not_found(self) -> None:
        """Test availability check when transformers module is not found."""
        with (
            patch("pdf2foundry.core.feature_detection.FeatureAvailability.has_ml_support", return_value=True),
            patch("importlib.util.find_spec", return_value=None),
        ):
            engine = HFCaptionEngine("microsoft/Florence-2-base")
            available = engine.is_available()
            assert available is False

    def test_load_pipeline_florence2_model(self) -> None:
        """Test loading Florence-2 model pipeline."""
        with (
            patch.object(HFCaptionEngine, "is_available", return_value=True),
            patch("pdf2foundry.core.timeout.get_environment_timeout", return_value=60),
            patch("pdf2foundry.core.timeout.timeout_context"),
        ):
            # Mock transformers components for Florence-2
            mock_processor = Mock()
            mock_model = Mock()

            # Mock the transformers module and its classes
            mock_transformers = Mock()
            mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
            mock_transformers.AutoModelForCausalLM.from_pretrained.return_value = mock_model

            with patch.dict("sys.modules", {"transformers": mock_transformers}):
                engine = HFCaptionEngine("microsoft/Florence-2-base")
                engine._load_pipeline()

                assert engine._pipeline is not None
                assert engine._pipeline["type"] == "florence2"
                assert engine._pipeline["model"] is mock_model
                assert engine._pipeline["processor"] is mock_processor

    def test_load_pipeline_blip_model(self) -> None:
        """Test loading BLIP model pipeline."""
        with (
            patch.object(HFCaptionEngine, "is_available", return_value=True),
            patch("pdf2foundry.core.timeout.get_environment_timeout", return_value=60),
            patch("pdf2foundry.core.timeout.timeout_context"),
        ):
            mock_pipeline = Mock()

            # Mock the transformers module
            mock_transformers = Mock()
            mock_transformers.pipeline.return_value = mock_pipeline

            with patch.dict("sys.modules", {"transformers": mock_transformers}):
                engine = HFCaptionEngine("salesforce/blip-image-captioning-base")
                engine._load_pipeline()

                assert engine._pipeline is mock_pipeline

    def test_load_pipeline_device_map_fallback(self) -> None:
        """Test pipeline loading with device_map fallback."""
        with (
            patch.object(HFCaptionEngine, "is_available", return_value=True),
            patch("pdf2foundry.core.timeout.get_environment_timeout", return_value=60),
            patch("pdf2foundry.core.timeout.timeout_context"),
        ):
            mock_pipeline = Mock()

            # Mock the transformers module
            mock_transformers = Mock()
            # First call with device_map fails, second succeeds
            mock_transformers.pipeline.side_effect = [ValueError("device_map not supported"), mock_pipeline]

            with patch.dict("sys.modules", {"transformers": mock_transformers}):
                engine = HFCaptionEngine("salesforce/blip-image-captioning-base")
                engine._load_pipeline()

                assert engine._pipeline is mock_pipeline
                # Should have been called twice (with and without device_map)
                assert mock_transformers.pipeline.call_count == 2

    def test_load_pipeline_timeout_error(self) -> None:
        """Test pipeline loading timeout."""
        from pdf2foundry.core.exceptions import ModelNotAvailableError

        with (
            patch.object(HFCaptionEngine, "is_available", return_value=True),
            patch("pdf2foundry.core.timeout.get_environment_timeout", return_value=60),
            patch("pdf2foundry.core.timeout.timeout_context", side_effect=TimeoutError("Model loading timed out")),
        ):
            # Mock the transformers module
            mock_transformers = Mock()

            with patch.dict("sys.modules", {"transformers": mock_transformers}):
                engine = HFCaptionEngine("microsoft/Florence-2-base")

                with pytest.raises(ModelNotAvailableError) as exc_info:
                    engine._load_pipeline()

                assert "timed out" in str(exc_info.value)
                assert engine._available is False

    def test_load_pipeline_florence2_error(self) -> None:
        """Test Florence-2 model loading error."""
        from pdf2foundry.core.exceptions import ModelNotAvailableError

        with (
            patch.object(HFCaptionEngine, "is_available", return_value=True),
            patch("pdf2foundry.core.timeout.get_environment_timeout", return_value=60),
            patch("pdf2foundry.core.timeout.timeout_context"),
        ):
            # Mock the transformers module with error
            mock_transformers = Mock()
            mock_transformers.AutoProcessor.from_pretrained.side_effect = RuntimeError("Model not found")

            with patch.dict("sys.modules", {"transformers": mock_transformers}):
                engine = HFCaptionEngine("microsoft/Florence-2-base")

                with pytest.raises(ModelNotAvailableError):
                    engine._load_pipeline()

    def test_generate_florence2_success(self) -> None:
        """Test successful caption generation with Florence-2."""
        with patch.object(HFCaptionEngine, "is_available", return_value=True):
            # Mock Florence-2 pipeline
            mock_model = Mock()
            mock_processor = Mock()
            mock_processor.return_value = {"input_ids": Mock(), "pixel_values": Mock()}
            mock_processor.batch_decode.return_value = ["<MORE_DETAILED_CAPTION>A detailed image description"]
            mock_model.generate.return_value = Mock()

            engine = HFCaptionEngine("microsoft/Florence-2-base")
            engine._pipeline = {"model": mock_model, "processor": mock_processor, "type": "florence2"}

            image = Image.new("RGB", (100, 100), color="red")
            result = engine.generate(image)

            assert result == "A detailed image description"

    def test_generate_result_formats(self) -> None:
        """Test different result format handling."""
        with (
            patch.object(HFCaptionEngine, "is_available", return_value=True),
            patch.object(HFCaptionEngine, "_load_pipeline"),
        ):
            engine = HFCaptionEngine("test/model")
            image = Image.new("RGB", (100, 100), color="red")

            # Test dict result with generated_text
            engine._pipeline = Mock(return_value={"generated_text": "Dict result"})
            result = engine.generate(image)
            assert result == "Dict result"

            # Test dict result with text
            engine._pipeline = Mock(return_value={"text": "Dict text result"})
            result = engine.generate(image)
            assert result == "Dict text result"

            # Test string result
            engine._pipeline = Mock(return_value="String result")
            result = engine.generate(image)
            assert result == "String result"

    def test_generate_prefix_removal_variations(self) -> None:
        """Test various prefix removal scenarios."""
        with (
            patch.object(HFCaptionEngine, "is_available", return_value=True),
            patch.object(HFCaptionEngine, "_load_pipeline"),
        ):
            engine = HFCaptionEngine("test/model")
            image = Image.new("RGB", (100, 100), color="red")

            # Test different prefixes
            test_cases = [
                ("an image of a cat", "A cat"),
                ("this is a dog", "A dog"),
                ("the image shows birds", "Birds"),
                ("image: flowers", "Flowers"),
                ("no prefix here", "No prefix here"),
            ]

            for input_text, expected in test_cases:
                engine._pipeline = Mock(return_value=[{"generated_text": input_text}])
                result = engine.generate(image)
                assert result == expected

    def test_generate_model_not_available_error(self) -> None:
        """Test generation with ModelNotAvailableError."""
        from pdf2foundry.core.exceptions import ModelNotAvailableError

        with (
            patch.object(HFCaptionEngine, "is_available", return_value=True),
            patch.object(HFCaptionEngine, "_load_pipeline"),
        ):
            engine = HFCaptionEngine("test/model")
            engine._pipeline = Mock(side_effect=ModelNotAvailableError("Model unavailable", "test/model"))

            image = Image.new("RGB", (100, 100), color="red")
            result = engine.generate(image)

            assert result is None
