"""Custom exceptions for PDF2Foundry.

This module defines custom exception classes used throughout PDF2Foundry
for better error handling and user experience.
"""

from __future__ import annotations


class ModelNotAvailableError(Exception):
    """Raised when a required ML model is not available.

    This exception is raised when:
    - ML dependencies are not installed (CI minimal mode)
    - Model loading fails due to network issues
    - Model loading times out
    - ML features are explicitly disabled
    """

    def __init__(self, message: str, model_id: str | None = None, timeout: bool = False) -> None:
        """Initialize ModelNotAvailableError.

        Args:
            message: Error message describing the issue
            model_id: Optional model ID that failed to load
            timeout: Whether the error was due to a timeout
        """
        super().__init__(message)
        self.model_id = model_id
        self.timeout = timeout


class FeatureNotAvailableError(Exception):
    """Raised when a required feature is not available.

    This exception is raised when:
    - Optional dependencies are not installed
    - Features are disabled in CI minimal mode
    - System requirements are not met
    """

    def __init__(self, message: str, feature: str | None = None) -> None:
        """Initialize FeatureNotAvailableError.

        Args:
            message: Error message describing the issue
            feature: Optional feature name that is not available
        """
        super().__init__(message)
        self.feature = feature


__all__ = [
    "ModelNotAvailableError",
    "FeatureNotAvailableError",
]
