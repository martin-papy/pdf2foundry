"""Backend capability detection for PDF2Foundry.

This module provides utilities to detect backend capabilities and resolve
effective worker configurations based on platform constraints, Docling version,
and multiprocessing support.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import sys
from dataclasses import dataclass

from pdf2foundry.docling_env import probe_docling

logger = logging.getLogger(__name__)


@dataclass
class BackendCapabilities:
    """Backend capability information."""

    supports_parallel_extract: bool
    max_workers: int | None = None
    start_method: str | None = None
    platform: str | None = None
    docling_version: str | None = None
    notes: list[str] | None = None


def detect_backend_capabilities(
    docling_version: str | None = None,
    platform: str | None = None,
    safe_fork: bool | None = None,
) -> BackendCapabilities:
    """Detect backend capabilities for parallel processing.

    Args:
        docling_version: Docling version string (auto-detected if None)
        platform: Platform string (sys.platform if None)
        safe_fork: Whether fork is safe (auto-detected if None)

    Returns:
        BackendCapabilities with parallel processing support information
    """
    notes: list[str] = []

    # Auto-detect platform if not provided
    if platform is None:
        platform = sys.platform

    # Auto-detect docling version if not provided
    if docling_version is None:
        probe_result = probe_docling()
        docling_version = probe_result.docling_version
        if not probe_result.has_docling or not probe_result.can_construct_converter:
            notes.append("Docling not available or cannot construct converter")

    # Determine multiprocessing start method and fork safety
    try:
        start_method = multiprocessing.get_start_method()
    except RuntimeError:
        start_method = "unknown"
        notes.append("Could not determine multiprocessing start method")

    # Determine multiprocessing safety if not provided
    if safe_fork is None:
        # Support both fork and spawn on POSIX systems
        # fork: Fast, shares memory, traditional Unix approach
        # spawn: Safer, fresh interpreter, Python 3.8+ default on macOS
        safe_multiprocessing = platform.startswith(("linux", "darwin")) and start_method in ("fork", "spawn", "forkserver")

        # Allow override from environment for testing
        env_override = os.environ.get("PDF2FOUNDRY_SAFE_FORK")
        if env_override is not None:
            safe_multiprocessing = env_override.lower() in ("1", "true", "yes")
            notes.append(f"Multiprocessing safety overridden by environment: {safe_multiprocessing}")

        # For backward compatibility, keep the safe_fork variable name
        safe_fork = safe_multiprocessing

    # Determine parallel processing support
    supports_parallel_extract = False
    max_workers = None

    # Enable parallel processing if multiprocessing is safe and Docling is available
    if safe_fork and docling_version:
        # Docling supports parallel processing with both fork and spawn start methods
        supports_parallel_extract = True
        notes.append(f"Parallel processing enabled with {start_method} start method")

        # Set a reasonable default max workers based on CPU count
        try:
            cpu_count = os.cpu_count() or multiprocessing.cpu_count()
            max_workers = min(cpu_count, 8)  # Cap at 8 to avoid resource exhaustion
        except (OSError, NotImplementedError):
            max_workers = 1
            notes.append("Could not determine CPU count, limiting to 1 worker")
    else:
        if not safe_fork:
            notes.append(f"Multiprocessing not safe on platform {platform} with start method {start_method}")
        if not docling_version:
            notes.append("Docling version not available")

    return BackendCapabilities(
        supports_parallel_extract=supports_parallel_extract,
        max_workers=max_workers,
        start_method=start_method,
        platform=platform,
        docling_version=docling_version,
        notes=notes,
    )


def resolve_effective_workers(
    requested: int,
    capabilities: BackendCapabilities,
    total_pages: int | None = None,
) -> tuple[int, list[str]]:
    """Resolve the effective number of workers based on capabilities and constraints.

    Args:
        requested: Requested number of workers
        capabilities: Backend capabilities
        total_pages: Total number of pages to process (for clamping)

    Returns:
        Tuple of (effective_workers, reasons) where reasons explains any downgrades
    """
    reasons: list[str] = []
    effective = requested

    # If only 1 worker requested, no need to check capabilities
    if requested <= 1:
        return 1, reasons

    # Check if backend supports parallel processing
    if not capabilities.supports_parallel_extract:
        effective = 1
        reasons.append("Backend does not support parallel page extraction")
        return effective, reasons

    # Clamp to backend maximum if available
    if capabilities.max_workers is not None and effective > capabilities.max_workers:
        effective = capabilities.max_workers
        reasons.append(f"Clamped to backend maximum of {capabilities.max_workers} workers")

    # Clamp to number of pages if available
    if total_pages is not None and effective > total_pages:
        effective = total_pages
        reasons.append(f"Clamped to page count of {total_pages}")

    # Ensure we always return at least 1
    if effective < 1:
        effective = 1
        reasons.append("Forced minimum of 1 worker")

    return effective, reasons


def log_worker_resolution(
    requested: int,
    effective: int,
    reasons: list[str],
    capabilities: BackendCapabilities,
    pages_to_process: int | None = None,
) -> None:
    """Log worker resolution information.

    Args:
        requested: Originally requested number of workers
        effective: Effective number of workers after resolution
        reasons: List of reasons for any downgrades
        capabilities: Backend capabilities used for resolution
        pages_to_process: Number of pages to be processed
    """
    # Log basic resolution info
    if effective == requested:
        logger.info(
            "Worker resolution: using %d worker%s for page-level CPU-bound stages",
            effective,
            "s" if effective != 1 else "",
        )
    else:
        logger.info(
            "Worker resolution: requested %d, using %d worker%s for page-level CPU-bound stages",
            requested,
            effective,
            "s" if effective != 1 else "",
        )

    # Log reasons for downgrades
    for reason in reasons:
        if "does not support" in reason.lower():
            logger.warning("Worker downgrade: %s", reason)
        else:
            logger.info("Worker adjustment: %s", reason)

    # Log additional context
    context_items = []
    if capabilities.platform:
        context_items.append(f"platform={capabilities.platform}")
    if capabilities.start_method:
        context_items.append(f"start_method={capabilities.start_method}")
    if capabilities.docling_version:
        context_items.append(f"docling={capabilities.docling_version}")
    if pages_to_process is not None:
        context_items.append(f"pages={pages_to_process}")

    if context_items:
        logger.debug("Worker resolution context: %s", ", ".join(context_items))

    # Log any capability notes
    if capabilities.notes:
        for note in capabilities.notes:
            logger.debug("Backend capability note: %s", note)


__all__ = [
    "BackendCapabilities",
    "detect_backend_capabilities",
    "log_worker_resolution",
    "resolve_effective_workers",
]
