"""Core functionality for PDF2Foundry."""

__all__ = [
    "FeatureAvailability",
    "ModelNotAvailableError",
    "FeatureNotAvailableError",
    "timeout_context",
    "get_environment_timeout",
]

from .exceptions import FeatureNotAvailableError, ModelNotAvailableError
from .feature_detection import FeatureAvailability
from .timeout import get_environment_timeout, timeout_context
