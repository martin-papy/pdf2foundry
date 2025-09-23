"""Model registry for PDF2Foundry VLM models.

This module provides a centralized registry for Vision-Language Models (VLM)
used in PDF2Foundry. It uses a single, well-tested model (BLIP) for all
environments to ensure compatibility and reduce complexity.
"""

from __future__ import annotations

from dataclasses import dataclass

# Single VLM model for all environments - BLIP for compatibility
# BLIP was chosen over Florence-2 due to better compatibility across
# local laptops and CI environments, avoiding complex setup requirements
DEFAULT_VLM_MODEL = "Salesforce/blip-image-captioning-base"


@dataclass
class ModelSpec:
    """Specification for the VLM model."""

    id: str
    size_mb: int
    task: str
    compatible_local: bool  # Works on local laptops
    compatible_ci: bool  # Works in CI environments


# Single model specification - BLIP chosen for broad compatibility
# BLIP provides good quality captions while being manageable in size
# and compatible across different environments
VLM_MODEL_SPEC = ModelSpec(
    id=DEFAULT_VLM_MODEL,
    size_mb=990,  # ~1GB - manageable size for CI caching
    task="image-to-text",
    compatible_local=True,  # Works well on local laptops
    compatible_ci=True,  # Works in CI environments with proper caching
)


def get_default_vlm_model() -> str:
    """Get the default VLM model for all environments.

    Returns:
        The default VLM model ID (BLIP)
    """
    return DEFAULT_VLM_MODEL


def get_model_spec() -> ModelSpec:
    """Get the model specification.

    Returns:
        ModelSpec containing details about the default VLM model
    """
    return VLM_MODEL_SPEC


__all__ = [
    "DEFAULT_VLM_MODEL",
    "ModelSpec",
    "VLM_MODEL_SPEC",
    "get_default_vlm_model",
    "get_model_spec",
]
