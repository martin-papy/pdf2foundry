"""Pipeline options for PDF2Foundry processing.

This module defines our own pipeline configuration options that extend beyond
the basic Docling PdfPipelineOptions to support advanced features like
structured tables, OCR, and picture descriptions.
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
    OFF = "off"  # Never run OCR


@dataclass
class PdfPipelineOptions:
    """Pipeline configuration options for PDF2Foundry processing."""

    # Table processing mode
    tables_mode: TableMode = TableMode.AUTO

    # OCR processing mode (default: AUTO for intelligent OCR)
    ocr_mode: OcrMode = OcrMode.AUTO

    # Enable picture descriptions/captions
    picture_descriptions: bool = False

    # VLM repository ID for picture descriptions (required when picture_descriptions=True)
    vlm_repo_id: str | None = None

    # Text coverage threshold for AUTO OCR mode (5% default)
    text_coverage_threshold: float = 0.05

    # Page selection (None means all pages)
    pages: list[int] | None = None

    # Number of worker processes for CPU-bound page-level steps
    workers: int = 1

    # Effective number of workers after capability resolution (set during pipeline setup)
    workers_effective: int = 1

    # Enable experimental multi-column reflow in layout transform
    reflow_columns: bool = False

    @classmethod
    def from_cli(
        cls,
        *,
        tables: str = "auto",
        ocr: str = "auto",
        picture_descriptions: str = "off",
        vlm_repo_id: str | None = None,
        text_coverage_threshold: float = 0.05,
        pages: list[int] | None = None,
        workers: int = 1,
        reflow_columns: bool = False,
    ) -> PdfPipelineOptions:
        """Build PdfPipelineOptions from CLI argument values.

        Args:
            tables: Table handling mode ("structured", "auto", "image-only")
            ocr: OCR mode ("auto", "on", "off")
            picture_descriptions: Picture descriptions ("on", "off")
            vlm_repo_id: VLM repository ID for picture descriptions
            text_coverage_threshold: Text coverage threshold for AUTO OCR
            pages: List of 1-based page indices to process (None for all pages)
            workers: Number of worker processes for CPU-bound page-level steps
            reflow_columns: Enable experimental multi-column reflow

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
            raise ValueError(f"Invalid tables mode '{tables}'. Valid values: {valid_values}") from exc

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
            raise ValueError(f"Invalid picture_descriptions '{picture_descriptions}'. " f"Valid values: ['on', 'off']")

        # Use default VLM model if picture descriptions are enabled but no model specified
        if picture_descriptions_bool and vlm_repo_id is None:
            # Import here to avoid circular imports
            try:
                from pdf2foundry.models.registry import get_default_vlm_model

                vlm_repo_id = get_default_vlm_model()
            except ImportError:
                # Fallback if models module not available (shouldn't happen in normal usage)
                vlm_repo_id = "Salesforce/blip-image-captioning-base"

        # Validate workers parameter
        if workers < 1:
            raise ValueError(f"Workers must be >= 1, got {workers}")

        return cls(
            tables_mode=tables_mode,
            ocr_mode=ocr_mode,
            picture_descriptions=picture_descriptions_bool,
            vlm_repo_id=vlm_repo_id,
            text_coverage_threshold=text_coverage_threshold,
            pages=pages,
            workers=workers,
            reflow_columns=reflow_columns,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization/logging."""
        return {
            "tables_mode": self.tables_mode.value,
            "ocr_mode": self.ocr_mode.value,
            "picture_descriptions": self.picture_descriptions,
            "vlm_repo_id": self.vlm_repo_id,
            "text_coverage_threshold": self.text_coverage_threshold,
            "pages": self.pages,
            "workers": self.workers,
            "workers_effective": self.workers_effective,
            "reflow_columns": self.reflow_columns,
        }

    def __repr__(self) -> str:
        """String representation for debugging/logging."""
        return (
            f"PdfPipelineOptions("
            f"tables_mode={self.tables_mode.value}, "
            f"ocr_mode={self.ocr_mode.value}, "
            f"picture_descriptions={self.picture_descriptions}, "
            f"vlm_repo_id={self.vlm_repo_id!r}, "
            f"text_coverage_threshold={self.text_coverage_threshold}, "
            f"pages={self.pages}, "
            f"workers={self.workers}, "
            f"workers_effective={self.workers_effective}, "
            f"reflow_columns={self.reflow_columns}"
            f")"
        )


__all__ = [
    "OcrMode",
    "PdfPipelineOptions",
    "TableMode",
]
