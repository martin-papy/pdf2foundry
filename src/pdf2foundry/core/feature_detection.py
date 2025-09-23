"""Runtime feature detection for PDF2Foundry.

This module provides runtime detection for CI environment compatibility and
feature availability. It's designed to enable graceful degradation in CI
environments while maintaining full functionality for end users.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class FeatureAvailability:
    """Runtime detection for CI environment compatibility."""

    @staticmethod
    def has_ml_support() -> bool:
        """Check if ML features are available (mainly for CI environments).

        In normal user installations, this should always return True since
        ML dependencies are included by default. This only returns False
        in CI environments with minimal dependencies or when explicitly disabled.

        Returns:
            True if transformers and torch are available and not disabled, False otherwise
        """
        # Check if ML features are explicitly disabled via CLI flag
        if os.getenv("PDF2FOUNDRY_NO_ML") == "1":
            logger.debug("ML support disabled via --no-ml flag")
            return False

        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401

            return True
        except ImportError:
            # In normal user installations, this should never happen
            # Only occurs in CI with minimal dependencies
            logger.debug("ML support not available - transformers or torch not found")
            return False

    @staticmethod
    def has_ocr_support() -> bool:
        """Check if OCR features are available (mainly for CI environments).

        In normal user installations, this should always return True since
        OCR dependencies are included by default. This only returns False
        in CI environments with minimal dependencies.

        Returns:
            True if pytesseract is available, False otherwise
        """
        try:
            import pytesseract  # noqa: F401

            return True
        except ImportError:
            # In normal user installations, this should never happen
            # Only occurs in CI with minimal dependencies
            logger.debug("OCR support not available - pytesseract not found")
            return False

    @staticmethod
    def is_ci_minimal_environment() -> bool:
        """Check if running in CI with minimal dependencies.

        This is determined by the presence of both CI=1 and
        PDF2FOUNDRY_CI_MINIMAL=1 environment variables.

        Returns:
            True if running in CI minimal mode, False otherwise
        """
        return os.getenv("CI") == "1" and os.getenv("PDF2FOUNDRY_CI_MINIMAL") == "1"

    @staticmethod
    def get_available_features() -> dict[str, Any]:
        """Get all available features and environment information.

        Returns:
            Dictionary containing feature availability and environment info
        """
        return {
            "ml": FeatureAvailability.has_ml_support(),
            "ocr": FeatureAvailability.has_ocr_support(),
            "ci_minimal": FeatureAvailability.is_ci_minimal_environment(),
            "environment": {
                "ci": os.getenv("CI", "0") == "1",
                "ci_minimal": os.getenv("PDF2FOUNDRY_CI_MINIMAL", "0") == "1",
            },
        }

    @staticmethod
    def log_feature_status() -> None:
        """Log the current feature availability status for debugging."""
        features = FeatureAvailability.get_available_features()

        logger.info("Feature availability status:")
        logger.info(f"  ML support: {features['ml']}")
        logger.info(f"  OCR support: {features['ocr']}")
        logger.info(f"  CI minimal mode: {features['ci_minimal']}")
        logger.info(f"  Environment - CI: {features['environment']['ci']}")
        logger.info(f"  Environment - CI minimal: {features['environment']['ci_minimal']}")


__all__ = [
    "FeatureAvailability",
]
