"""Model management for PDF2Foundry."""

__all__ = [
    "DEFAULT_VLM_MODEL",
    "ModelSpec",
    "VLM_MODEL_SPEC",
    "get_default_vlm_model",
    "get_model_spec",
]

from .registry import (
    DEFAULT_VLM_MODEL,
    VLM_MODEL_SPEC,
    ModelSpec,
    get_default_vlm_model,
    get_model_spec,
)
