"""Centralized error handling and logging for PDF2Foundry pipeline.

This module provides a unified error handling system that integrates with the existing
feature_logger while adding structured error context and consistent event codes.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pdf2foundry.ingest.feature_logger import log_error_policy, log_feature_decision

logger = logging.getLogger(__name__)


@dataclass
class ErrorContext:
    """Context information for error handling and logging.

    Provides structured context that can be included in error messages
    and log entries to make them more actionable for users and developers.
    """

    pdf_path: Path | None = None
    doc_id: str | None = None
    source_module: str | None = None
    page: int | None = None
    object_kind: str | None = None  # e.g., "table", "image", "bookmark", "anchor"
    object_id: str | None = None
    flags: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    cli_verbosity: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for logging."""
        return {
            "pdf_path": str(self.pdf_path) if self.pdf_path else None,
            "doc_id": self.doc_id,
            "source_module": self.source_module,
            "page": self.page,
            "object_kind": self.object_kind,
            "object_id": self.object_id,
            "flags": self.flags,
            "correlation_id": self.correlation_id,
            "cli_verbosity": self.cli_verbosity,
        }


class ErrorManager:
    """Centralized error handling manager.

    Provides consistent error handling, logging, and decision tracking
    across the PDF processing pipeline. Integrates with existing
    feature_logger functionality while adding structured context.
    """

    def __init__(self, context: ErrorContext | None = None) -> None:
        self.context = context or ErrorContext()
        self._logger = logging.getLogger(f"{__name__}.{self.context.source_module or 'unknown'}")

    def warn(
        self,
        event_code: str,
        message: str,
        *,
        extra: dict[str, Any] | None = None,
        exception: Exception | None = None,
    ) -> None:
        """Log a warning with structured context.

        Args:
            event_code: Unique event code (e.g., "DL-MB001")
            message: Human-readable warning message
            extra: Additional context fields
            exception: Optional exception that triggered the warning
        """
        log_data = self._build_log_data(event_code, extra, exception)
        self._logger.warning("%s: %s", event_code, message, extra=log_data)

    def error(
        self,
        event_code: str,
        message: str,
        *,
        extra: dict[str, Any] | None = None,
        exception: Exception | None = None,
    ) -> None:
        """Log an error with structured context.

        Args:
            event_code: Unique event code (e.g., "DL-PDF001")
            message: Human-readable error message
            extra: Additional context fields
            exception: Optional exception that triggered the error
        """
        log_data = self._build_log_data(event_code, extra, exception)
        self._logger.error("%s: %s", event_code, message, extra=log_data)

    def decision(
        self,
        event_code: str,
        decision_key: str,
        decision_value: str,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log a feature decision with structured context.

        Args:
            event_code: Unique event code (e.g., "DL-OCR-DEC")
            decision_key: Key identifying the decision (e.g., "ocr.auto")
            decision_value: The decision made (e.g., "enabled")
            extra: Additional context fields
        """
        log_data = self._build_log_data(event_code, extra)
        log_data["decision_key"] = decision_key
        log_data["decision_value"] = decision_value

        # Use existing feature_logger for consistency
        log_feature_decision(decision_key, decision_value, extra)

        # Also log with our structured format
        self._logger.info("%s: %s=%s", event_code, decision_key, decision_value, extra=log_data)

    def error_policy(
        self,
        feature: str,
        error_type: str,
        action: str,
        *,
        details: str | None = None,
        event_code: str | None = None,
    ) -> None:
        """Log an error handling policy decision.

        Args:
            feature: Name of the feature encountering the error
            error_type: Type of error
            action: Action taken (e.g., "skip", "fallback", "continue", "exit")
            details: Optional additional details
            event_code: Optional event code for structured logging
        """
        # Use existing feature_logger for consistency
        log_error_policy(feature, error_type, action, details)

        # Also log with our structured format if event code provided
        if event_code:
            log_data = self._build_log_data(event_code)
            log_data.update(
                {
                    "feature": feature,
                    "error_type": error_type,
                    "action": action,
                    "details": details,
                }
            )
            self._logger.warning(
                "%s: %s error policy: %s -> %s",
                event_code,
                feature,
                error_type,
                action,
                extra=log_data,
            )

    def _build_log_data(
        self,
        event_code: str,
        extra: dict[str, Any] | None = None,
        exception: Exception | None = None,
    ) -> dict[str, Any]:
        """Build structured log data with context."""
        log_data = {
            "event_code": event_code,
            **self.context.to_dict(),
        }

        if extra:
            log_data.update(extra)

        if exception:
            log_data.update(
                {
                    "exception_class": exception.__class__.__name__,
                    "exception_message": str(exception),
                }
            )

        # Add docling version if available
        try:
            import docling

            log_data["docling_version"] = getattr(docling, "__version__", "unknown")
        except ImportError:
            log_data["docling_version"] = "not_installed"

        return log_data


# Custom exception classes for different failure modes
class PdfParseError(Exception):
    """Fatal PDF parsing error that should cause graceful exit."""

    def __init__(self, pdf_path: Path, cause: Exception | None = None, page: int | None = None) -> None:
        self.pdf_path = pdf_path
        self.cause = cause
        self.page = page

        msg = f"Failed to parse PDF {pdf_path}"
        if page is not None:
            msg += f" at page {page}"
        if cause:
            msg += f": {cause}"

        super().__init__(msg)


class TableExtractionError(Exception):
    """Non-fatal table extraction error - fallback should be used."""

    def __init__(self, page: int, table_index: int | None = None, cause: Exception | None = None) -> None:
        self.page = page
        self.table_index = table_index
        self.cause = cause

        msg = f"Failed to extract table on page {page}"
        if table_index is not None:
            msg += f" (table {table_index})"
        if cause:
            msg += f": {cause}"

        super().__init__(msg)


class CrossRefResolutionWarning(Exception):
    """Non-fatal cross-reference resolution warning."""

    def __init__(self, link_text: str, source_page: int, target_anchor: str) -> None:
        self.link_text = link_text
        self.source_page = source_page
        self.target_anchor = target_anchor

        super().__init__(
            f"Failed to resolve cross-reference '{link_text}' on page {source_page} " f"to anchor '{target_anchor}'"
        )


class CaptionAssociationWarning(Exception):
    """Non-fatal caption association warning."""

    def __init__(self, page: int, figure_id: str | None = None, caption_text: str | None = None) -> None:
        self.page = page
        self.figure_id = figure_id
        self.caption_text = caption_text

        msg = f"Failed to associate caption on page {page}"
        if figure_id:
            msg += f" for figure {figure_id}"
        if caption_text:
            snippet = caption_text[:50] + "..." if len(caption_text) > 50 else caption_text
            msg += f": '{snippet}'"

        super().__init__(msg)


__all__ = [
    "CaptionAssociationWarning",
    "CrossRefResolutionWarning",
    "ErrorContext",
    "ErrorManager",
    "PdfParseError",
    "TableExtractionError",
]
