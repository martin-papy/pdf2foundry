"""Centralized feature decision logging for PDF2Foundry pipeline.

This module provides utilities for logging feature decisions and error policies
without overlapping with ProgressReporter functionality. It focuses on informative
logging for debugging and troubleshooting rather than user progress updates.
"""

from __future__ import annotations

import logging
from typing import Any

from pdf2foundry.model.pipeline_options import PdfPipelineOptions

logger = logging.getLogger(__name__)


def _format_page_spec(pages: list[int]) -> str:
    """Format a list of page numbers into a compact string representation.

    Args:
        pages: List of page numbers (assumed to be sorted)

    Returns:
        Compact string representation (e.g., "1,3,5-7,10")
    """
    if not pages:
        return ""

    # Group consecutive pages into ranges
    ranges = []
    start = pages[0]
    end = pages[0]

    for page in pages[1:]:
        if page == end + 1:
            end = page
        else:
            # Add the current range
            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{end}")
            start = end = page

    # Add the final range
    if start == end:
        ranges.append(str(start))
    else:
        ranges.append(f"{start}-{end}")

    return ",".join(ranges)


def log_pipeline_configuration(options: PdfPipelineOptions) -> None:
    """Log the pipeline configuration decisions for debugging.

    Args:
        options: Pipeline options to log
    """
    logger.info("Pipeline configuration:")
    logger.info("  Tables mode: %s", options.tables_mode.value)
    logger.info("  OCR mode: %s", options.ocr_mode.value)
    logger.info("  Picture descriptions: %s", "enabled" if options.picture_descriptions else "disabled")
    if options.picture_descriptions and options.vlm_repo_id:
        logger.info("  VLM model: %s", options.vlm_repo_id)
    logger.info("  Text coverage threshold: %.3f", options.text_coverage_threshold)

    # Log worker configuration
    if options.pages:
        logger.info("  Pages: %s (%d selected)", _format_page_spec(options.pages), len(options.pages))
    else:
        logger.info("  Pages: all")

    if options.workers != options.workers_effective:
        logger.info("  Workers: %d requested, %d effective", options.workers, options.workers_effective)
    else:
        logger.info("  Workers: %d", options.workers_effective)

    logger.info(
        "  Multi-column reflow: %s",
        "enabled (experimental)" if options.reflow_columns else "disabled",
    )


def log_feature_availability(feature: str, available: bool, reason: str | None = None) -> None:
    """Log feature availability status.

    Args:
        feature: Name of the feature (e.g., "OCR", "Captions", "Structured Tables")
        available: Whether the feature is available
        reason: Optional reason for unavailability
    """
    if available:
        logger.info("%s: Available", feature)
    else:
        if reason:
            logger.warning("%s: Unavailable - %s", feature, reason)
        else:
            logger.warning("%s: Unavailable", feature)


def log_feature_decision(feature: str, decision: str, context: dict[str, Any] | None = None) -> None:
    """Log a feature processing decision.

    Args:
        feature: Name of the feature making the decision
        decision: The decision made (e.g., "enabled", "disabled", "fallback")
        context: Optional context information
    """
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        logger.info("%s: %s (%s)", feature, decision, context_str)
    else:
        logger.info("%s: %s", feature, decision)


def log_error_policy(feature: str, error_type: str, action: str, details: str | None = None) -> None:
    """Log error handling policy decisions.

    Args:
        feature: Name of the feature encountering the error
        error_type: Type of error (e.g., "missing_dependency", "model_load_failed")
        action: Action taken (e.g., "skip", "fallback", "continue", "exit")
        details: Optional additional details
    """
    if details:
        logger.warning("%s error policy: %s -> %s (%s)", feature, error_type, action, details)
    else:
        logger.warning("%s error policy: %s -> %s", feature, error_type, action)


__all__ = [
    "log_error_policy",
    "log_feature_availability",
    "log_feature_decision",
    "log_pipeline_configuration",
]
