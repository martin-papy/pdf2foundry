"""Pipeline options for PDF2Foundry processing.

This module defines our own pipeline configuration options that extend beyond
the basic Docling PdfPipelineOptions to support advanced features like
structured tables, OCR, and picture descriptions.

Note: Defaults must not change observable output versus pre-feature release.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TableMode(Enum):
    """Table extraction mode options."""

    STRUCTURED = "structured"  # Always attempt structural extraction
    AUTO = "auto"  # Try structured, fallback to raster (current default)
    IMAGE_ONLY = "image-only"  # Always rasterize tables to images


class OcrMode(Enum):
    """OCR processing mode options."""

    AUTO = "auto"  # Run OCR only on pages with insufficient text coverage
    ON = "on"  # Always run OCR for all pages/images
    OFF = "off"  # Never run OCR (current default)


@dataclass
class PdfPipelineOptions:
    """Pipeline configuration options for PDF2Foundry processing.

    Defaults preserve current behavior to ensure backward compatibility.
    When all defaults are used, output should be identical to current pipeline
    (modulo metadata fields that are purely additive and not rendered).
    """

    # Table processing mode (default: AUTO preserves current behavior)
    tables_mode: TableMode = TableMode.AUTO

    # OCR processing mode (default: OFF preserves current no-OCR behavior)
    ocr_mode: OcrMode = OcrMode.OFF

    # Enable picture descriptions/captions (default: False preserves current behavior)
    picture_descriptions: bool = False

    # VLM repository ID for picture descriptions (required when picture_descriptions=True)
    vlm_repo_id: str | None = None

    # Text coverage threshold for AUTO OCR mode (5% default)
    text_coverage_threshold: float = 0.05

    @classmethod
    def from_cli(
        cls,
        *,
        tables: str = "auto",
        ocr: str = "off",
        picture_descriptions: str = "off",
        vlm_repo_id: str | None = None,
        text_coverage_threshold: float = 0.05,
    ) -> PdfPipelineOptions:
        """Build PdfPipelineOptions from CLI argument values.

        Args:
            tables: Table handling mode ("structured", "auto", "image-only")
            ocr: OCR mode ("auto", "on", "off")
            picture_descriptions: Picture descriptions ("on", "off")
            vlm_repo_id: VLM repository ID for picture descriptions
            text_coverage_threshold: Text coverage threshold for AUTO OCR

        Returns:
            PdfPipelineOptions instance with mapped enum values

        Raises:
            ValueError: If any argument has an invalid value
        """
        # Map tables string to enum
        try:
            tables_mode = TableMode(tables)
        except ValueError as exc:
            valid_values = [mode.value for mode in TableMode]
            raise ValueError(
                f"Invalid tables mode '{tables}'. Valid values: {valid_values}"
            ) from exc

        # Map OCR string to enum
        try:
            ocr_mode = OcrMode(ocr)
        except ValueError as exc:
            valid_values = [mode.value for mode in OcrMode]
            raise ValueError(f"Invalid OCR mode '{ocr}'. Valid values: {valid_values}") from exc

        # Map picture descriptions string to boolean
        if picture_descriptions == "on":
            picture_descriptions_bool = True
        elif picture_descriptions == "off":
            picture_descriptions_bool = False
        else:
            raise ValueError(
                f"Invalid picture_descriptions '{picture_descriptions}'. "
                f"Valid values: ['on', 'off']"
            )

        return cls(
            tables_mode=tables_mode,
            ocr_mode=ocr_mode,
            picture_descriptions=picture_descriptions_bool,
            vlm_repo_id=vlm_repo_id,
            text_coverage_threshold=text_coverage_threshold,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization/logging."""
        return {
            "tables_mode": self.tables_mode.value,
            "ocr_mode": self.ocr_mode.value,
            "picture_descriptions": self.picture_descriptions,
            "vlm_repo_id": self.vlm_repo_id,
            "text_coverage_threshold": self.text_coverage_threshold,
        }

    def __repr__(self) -> str:
        """String representation for debugging/logging."""
        return (
            f"PdfPipelineOptions("
            f"tables_mode={self.tables_mode.value}, "
            f"ocr_mode={self.ocr_mode.value}, "
            f"picture_descriptions={self.picture_descriptions}, "
            f"vlm_repo_id={self.vlm_repo_id!r}, "
            f"text_coverage_threshold={self.text_coverage_threshold}"
            f")"
        )


__all__ = [
    "TableMode",
    "OcrMode",
    "PdfPipelineOptions",
]
