"""Tests for pipeline options module."""

import pytest

from pdf2foundry.model.pipeline_options import OcrMode, PdfPipelineOptions, TableMode


class TestTableMode:
    """Test TableMode enum."""

    def test_enum_values(self) -> None:
        """Test enum values match expected CLI strings."""
        assert TableMode.STRUCTURED.value == "structured"
        assert TableMode.AUTO.value == "auto"
        assert TableMode.IMAGE_ONLY.value == "image-only"

    def test_enum_from_string(self) -> None:
        """Test creating enum from string values."""
        assert TableMode("structured") == TableMode.STRUCTURED
        assert TableMode("auto") == TableMode.AUTO
        assert TableMode("image-only") == TableMode.IMAGE_ONLY

    def test_invalid_string_raises_error(self) -> None:
        """Test invalid string raises ValueError."""
        with pytest.raises(ValueError):
            TableMode("invalid")


class TestOcrMode:
    """Test OcrMode enum."""

    def test_enum_values(self) -> None:
        """Test enum values match expected CLI strings."""
        assert OcrMode.AUTO.value == "auto"
        assert OcrMode.ON.value == "on"
        assert OcrMode.OFF.value == "off"

    def test_enum_from_string(self) -> None:
        """Test creating enum from string values."""
        assert OcrMode("auto") == OcrMode.AUTO
        assert OcrMode("on") == OcrMode.ON
        assert OcrMode("off") == OcrMode.OFF

    def test_invalid_string_raises_error(self) -> None:
        """Test invalid string raises ValueError."""
        with pytest.raises(ValueError):
            OcrMode("invalid")


class TestPdfPipelineOptions:
    """Test PdfPipelineOptions dataclass."""

    def test_default_values(self) -> None:
        """Test default values preserve current behavior."""
        options = PdfPipelineOptions()

        # Defaults must preserve current behavior
        assert options.tables_mode == TableMode.AUTO
        assert options.ocr_mode == OcrMode.OFF
        assert options.picture_descriptions is False
        assert options.vlm_repo_id is None
        assert options.text_coverage_threshold == 0.05

    def test_from_cli_defaults(self) -> None:
        """Test from_cli with no arguments yields expected defaults."""
        options = PdfPipelineOptions.from_cli()

        assert options.tables_mode == TableMode.AUTO
        assert options.ocr_mode == OcrMode.OFF
        assert options.picture_descriptions is False
        assert options.vlm_repo_id is None
        assert options.text_coverage_threshold == 0.05

    def test_from_cli_all_values(self) -> None:
        """Test from_cli with all arguments specified."""
        options = PdfPipelineOptions.from_cli(
            tables="structured",
            ocr="on",
            picture_descriptions="on",
            vlm_repo_id="test-model",
            text_coverage_threshold=0.1,
        )

        assert options.tables_mode == TableMode.STRUCTURED
        assert options.ocr_mode == OcrMode.ON
        assert options.picture_descriptions is True
        assert options.vlm_repo_id == "test-model"
        assert options.text_coverage_threshold == 0.1

    def test_from_cli_invalid_tables(self) -> None:
        """Test from_cli with invalid tables value raises error."""
        with pytest.raises(ValueError, match="Invalid tables mode 'invalid'"):
            PdfPipelineOptions.from_cli(tables="invalid")

    def test_from_cli_invalid_ocr(self) -> None:
        """Test from_cli with invalid OCR value raises error."""
        with pytest.raises(ValueError, match="Invalid OCR mode 'invalid'"):
            PdfPipelineOptions.from_cli(ocr="invalid")

    def test_from_cli_invalid_picture_descriptions(self) -> None:
        """Test from_cli with invalid picture_descriptions value raises error."""
        with pytest.raises(ValueError, match="Invalid picture_descriptions 'invalid'"):
            PdfPipelineOptions.from_cli(picture_descriptions="invalid")

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        options = PdfPipelineOptions(
            tables_mode=TableMode.STRUCTURED,
            ocr_mode=OcrMode.ON,
            picture_descriptions=True,
            vlm_repo_id="test-model",
            text_coverage_threshold=0.1,
        )

        expected = {
            "tables_mode": "structured",
            "ocr_mode": "on",
            "picture_descriptions": True,
            "vlm_repo_id": "test-model",
            "text_coverage_threshold": 0.1,
        }

        assert options.to_dict() == expected

    def test_repr(self) -> None:
        """Test __repr__ method."""
        options = PdfPipelineOptions(
            tables_mode=TableMode.STRUCTURED,
            ocr_mode=OcrMode.ON,
            picture_descriptions=True,
            vlm_repo_id="test-model",
            text_coverage_threshold=0.1,
        )

        repr_str = repr(options)

        # Check that all key information is in the repr
        assert "PdfPipelineOptions(" in repr_str
        assert "tables_mode=structured" in repr_str
        assert "ocr_mode=on" in repr_str
        assert "picture_descriptions=True" in repr_str
        assert "vlm_repo_id='test-model'" in repr_str
        assert "text_coverage_threshold=0.1" in repr_str

    def test_backward_compatibility_snapshot(self) -> None:
        """Test that defaults match current behavior expectations."""
        # This test serves as a snapshot to ensure defaults don't change
        # and break backward compatibility
        options = PdfPipelineOptions()

        # These values must match current CLI defaults
        assert options.tables_mode.value == "auto"  # Current --tables default
        assert options.ocr_mode.value == "off"  # Current no-OCR behavior
        assert options.picture_descriptions is False  # Current no-captions behavior
        assert options.vlm_repo_id is None  # No VLM by default
        assert options.text_coverage_threshold == 0.05  # Reasonable default for AUTO OCR
