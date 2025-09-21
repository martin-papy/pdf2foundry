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


def log_pipeline_configuration(options: PdfPipelineOptions) -> None:
    """Log the pipeline configuration decisions for debugging.

    Args:
        options: Pipeline options to log
    """
    logger.info("Pipeline configuration:")
    logger.info("  Tables mode: %s", options.tables_mode.value)
    logger.info("  OCR mode: %s", options.ocr_mode.value)
    logger.info(
        "  Picture descriptions: %s", "enabled" if options.picture_descriptions else "disabled"
    )
    if options.picture_descriptions and options.vlm_repo_id:
        logger.info("  VLM model: %s", options.vlm_repo_id)
    logger.info("  Text coverage threshold: %.3f", options.text_coverage_threshold)


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


def log_feature_decision(
    feature: str, decision: str, context: dict[str, Any] | None = None
) -> None:
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


def log_error_policy(
    feature: str, error_type: str, action: str, details: str | None = None
) -> None:
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
    "log_pipeline_configuration",
    "log_feature_availability",
    "log_feature_decision",
    "log_error_policy",
]
