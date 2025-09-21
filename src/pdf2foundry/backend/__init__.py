"""Backend capability detection and configuration utilities."""

from .caps import (
    BackendCapabilities,
    detect_backend_capabilities,
    log_worker_resolution,
    resolve_effective_workers,
)

__all__ = [
    "BackendCapabilities",
    "detect_backend_capabilities",
    "log_worker_resolution",
    "resolve_effective_workers",
]
