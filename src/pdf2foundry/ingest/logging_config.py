"""Logging configuration for PDF2Foundry.

This module provides centralized logging configuration with support for
configurable verbosity levels that integrate with the CLI and error handling system.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any


def configure_logging(verbosity: int = 0, *, disable_progress_interference: bool = True) -> None:
    """Configure logging for PDF2Foundry with the specified verbosity level.

    Args:
        verbosity: Verbosity level (0=WARNING, 1=INFO, 2=DEBUG)
        disable_progress_interference: If True, configure logging to avoid
                                     interfering with ProgressReporter output
    """
    # Map verbosity levels to logging levels
    level_map = {
        0: logging.WARNING,  # Default: only warnings and errors
        1: logging.INFO,  # -v: include info messages (decisions, summaries)
        2: logging.DEBUG,  # -vv: include debug messages (detailed processing)
    }

    # Clamp verbosity to valid range
    verbosity = max(0, min(2, verbosity))
    log_level = level_map[verbosity]

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    handler = logging.StreamHandler(sys.stderr) if disable_progress_interference else logging.StreamHandler(sys.stdout)

    handler.setLevel(log_level)

    # Create formatter based on verbosity level
    if verbosity >= 2:
        # Debug level: include module name, line number, and correlation ID
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
            datefmt="%H:%M:%S",
        )
    elif verbosity >= 1:
        # Info level: include module name and structured event codes
        formatter = logging.Formatter(fmt="[%(levelname)s] %(name)s - %(message)s")
    else:
        # Warning level: minimal format for user-facing messages
        formatter = logging.Formatter(fmt="%(levelname)s: %(message)s")

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Configure specific loggers for better control
    _configure_module_loggers(verbosity)

    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info("Logging configured: verbosity=%d, level=%s", verbosity, logging.getLevelName(log_level))


def _configure_module_loggers(verbosity: int) -> None:
    """Configure specific module loggers based on verbosity level."""

    # PDF2Foundry modules - always respect the global level
    # (inherits from root logger level automatically)

    # Third-party libraries - keep them quieter unless high verbosity
    if verbosity < 2:
        # Suppress debug messages from third-party libraries
        logging.getLogger("docling").setLevel(logging.WARNING)
        logging.getLogger("transformers").setLevel(logging.WARNING)
        logging.getLogger("torch").setLevel(logging.WARNING)
        logging.getLogger("PIL").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)

    # Special handling for multiprocessing logs
    if verbosity < 1:
        logging.getLogger("pdf2foundry.ingest.parallel_processor").setLevel(logging.ERROR)


def get_effective_log_level() -> int:
    """Get the current effective logging level.

    Returns:
        Current logging level (logging.DEBUG, logging.INFO, etc.)
    """
    return logging.getLogger().getEffectiveLevel()


def is_debug_enabled() -> bool:
    """Check if debug logging is enabled.

    Returns:
        True if debug logging is enabled
    """
    return get_effective_log_level() <= logging.DEBUG


def is_info_enabled() -> bool:
    """Check if info logging is enabled.

    Returns:
        True if info logging is enabled
    """
    return get_effective_log_level() <= logging.INFO


class StructuredLoggerAdapter(logging.LoggerAdapter[logging.Logger]):
    """Logger adapter that adds structured context to log messages.

    This adapter automatically includes structured context from ErrorContext
    in log messages, making them more actionable and searchable.
    """

    def __init__(self, logger: logging.Logger, extra: dict[str, Any] | None = None) -> None:
        super().__init__(logger, extra or {})

    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> tuple[Any, MutableMapping[str, Any]]:
        """Process log message and add structured context."""
        # Add structured context to extra
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        # Merge adapter extra with message extra
        kwargs["extra"].update(self.extra)

        return msg, kwargs


def get_structured_logger(name: str, context: dict[str, Any] | None = None) -> StructuredLoggerAdapter:
    """Get a structured logger with optional context.

    Args:
        name: Logger name (typically __name__)
        context: Optional context to include in all log messages

    Returns:
        StructuredLoggerAdapter instance
    """
    base_logger = logging.getLogger(name)
    return StructuredLoggerAdapter(base_logger, context)


__all__ = [
    "configure_logging",
    "get_effective_log_level",
    "is_debug_enabled",
    "is_info_enabled",
    "StructuredLoggerAdapter",
    "get_structured_logger",
]
