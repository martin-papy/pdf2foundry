"""Timeout utilities for PDF2Foundry.

This module provides timeout context managers and utilities for handling
long-running operations like model loading in CI environments.
"""

from __future__ import annotations

import logging
import os
import signal
import threading
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)


@contextmanager
def timeout_context(seconds: int, operation_name: str = "operation") -> Generator[None, None, None]:
    """Context manager for operation timeouts using signals (Unix only).

    This timeout mechanism only works on Unix-like systems. On Windows or
    in environments where signals are not available, it will log a warning
    and proceed without timeout protection.

    Args:
        seconds: Timeout in seconds
        operation_name: Name of the operation for error messages

    Raises:
        TimeoutError: If the operation times out

    Example:
        with timeout_context(60, "model loading"):
            # Long-running operation here
            load_model()
    """

    def timeout_handler(signum: int, frame: Any) -> None:
        """Signal handler for timeout."""
        raise TimeoutError(f"{operation_name} timed out after {seconds} seconds")

    # Check if we're on a system that supports signals
    if not hasattr(signal, "SIGALRM") or os.name == "nt":
        logger.warning(f"Timeout protection not available on this platform for {operation_name}")
        yield
        return

    # Check if we're in the main thread (signals only work in main thread)
    if threading.current_thread() is not threading.main_thread():
        logger.warning(f"Timeout protection not available in non-main thread for {operation_name}")
        yield
        return

    # Set up the timeout
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)

    try:
        logger.debug(f"Starting {operation_name} with {seconds}s timeout")
        yield
        logger.debug(f"Completed {operation_name} within timeout")
    finally:
        # Always clean up the alarm and restore the old handler
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def get_environment_timeout(operation: str, default_local: int = 300, default_ci: int = 60) -> int:
    """Get timeout value based on environment and operation type.

    Args:
        operation: Operation name (e.g., "model_load", "ocr_process")
        default_local: Default timeout for local development (seconds)
        default_ci: Default timeout for CI environments (seconds)

    Returns:
        Timeout value in seconds
    """
    # Check for operation-specific environment variable
    env_var = f"PDF2FOUNDRY_{operation.upper()}_TIMEOUT"
    env_timeout = os.environ.get(env_var)

    if env_timeout is not None:
        try:
            return int(env_timeout)
        except ValueError:
            logger.warning(f"Invalid timeout value in {env_var}: {env_timeout}, using defaults")

    # Use CI-specific timeout if in CI environment
    if os.environ.get("CI") == "1":
        logger.debug(f"Using CI timeout for {operation}: {default_ci}s")
        return default_ci

    # Use local development timeout
    logger.debug(f"Using local timeout for {operation}: {default_local}s")
    return default_local


__all__ = [
    "timeout_context",
    "get_environment_timeout",
]
