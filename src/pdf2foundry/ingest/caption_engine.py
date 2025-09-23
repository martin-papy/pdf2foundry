"""Caption engine abstraction for PDF2Foundry.

This module provides an abstraction layer for image captioning engines, with a
Hugging Face transformers-based implementation. Captions are generated for figure-like
images when picture descriptions are enabled.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from PIL import Image

logger = logging.getLogger(__name__)


class CaptionEngine(Protocol):
    """Protocol for image captioning engines."""

    def generate(self, pil_image: Image.Image) -> str | None:
        """Generate a caption for the given PIL image.

        Args:
            pil_image: PIL Image to caption

        Returns:
            Generated caption text, or None if captioning fails
        """
        ...

    def is_available(self) -> bool:
        """Check if the caption engine is available and functional."""
        ...


class HFCaptionEngine:
    """Hugging Face transformers-based caption engine implementation."""

    def __init__(self, model_id: str) -> None:
        """Initialize HF caption engine with a specific model.

        Args:
            model_id: Hugging Face model repository ID (e.g., 'microsoft/Florence-2-base')
        """
        self.model_id = model_id
        self._pipeline: Any = None
        self._available: bool | None = None

    def is_available(self) -> bool:
        """Check if transformers and the model are available."""
        if self._available is None:
            try:
                # Check if ML features are available using our feature detection system
                from pdf2foundry.core.feature_detection import FeatureAvailability

                if not FeatureAvailability.has_ml_support():
                    logger.debug("ML features disabled or not available")
                    self._available = False
                    return self._available

                # Try to check if transformers is available using importlib
                import importlib.util

                if importlib.util.find_spec("transformers") is None:
                    raise ImportError("transformers module not found")

                # Test if we can create the pipeline (but don't actually load it yet)
                # This is a lightweight check - actual model loading happens lazily
                self._available = True
                logger.debug(f"HF Caption engine available for model: {self.model_id}")
            except ImportError as e:
                logger.warning(f"Transformers not available for captioning: {e}")
                self._available = False
            except Exception as e:
                logger.warning(f"HF Caption engine not available: {e}")
                self._available = False
        return self._available

    def _load_pipeline(self) -> None:
        """Lazily load the transformers pipeline with robust error handling and timeout."""
        if self._pipeline is None:
            from pdf2foundry.core.exceptions import ModelNotAvailableError
            from pdf2foundry.core.timeout import get_environment_timeout, timeout_context

            try:
                import transformers

                logger.info(f"Loading VLM model: {self.model_id}")

                # Get environment-appropriate timeout
                model_load_timeout = get_environment_timeout("model_load", default_local=300, default_ci=60)

                def _load_model() -> Any:
                    """Load the model with proper error handling."""
                    # Try to determine the task type based on model name
                    # Common VLM models and their tasks
                    if (
                        "florence" in self.model_id.lower()
                        or "blip" in self.model_id.lower()
                        or "llava" in self.model_id.lower()
                    ):
                        task = "image-to-text"
                    else:
                        # Default to image-to-text for most VLM models
                        task = "image-to-text"

                    # Special handling for Florence-2 models due to API differences
                    if "florence" in self.model_id.lower():
                        # Florence-2 requires direct model/processor usage, not pipeline
                        try:
                            from transformers import AutoModelForCausalLM, AutoProcessor

                            logger.info("Loading Florence-2 model and processor directly")
                            processor = AutoProcessor.from_pretrained(  # type: ignore[no-untyped-call]
                                self.model_id, trust_remote_code=True
                            )
                            model = AutoModelForCausalLM.from_pretrained(
                                self.model_id,
                                trust_remote_code=True,
                                torch_dtype="auto",
                                attn_implementation="eager",  # Avoid flash_attn requirement
                            )
                            # Store as a custom object instead of pipeline
                            return {"model": model, "processor": processor, "type": "florence2"}
                        except Exception as florence_error:
                            logger.error(f"Failed to load Florence-2 model directly: {florence_error}")
                            raise ModelNotAvailableError(
                                f"Florence-2 model loading failed: {florence_error}", model_id=self.model_id
                            ) from florence_error
                    else:
                        # Standard pipeline creation for other models (BLIP, etc.)
                        # Try with device_map first, fallback without it
                        try:
                            return transformers.pipeline(  # type: ignore[call-overload]
                                task,
                                model=self.model_id,
                                device_map="auto",  # Use GPU if available
                            )
                        except ValueError as device_map_error:
                            if "device_map" in str(device_map_error):
                                logger.warning(f"Model doesn't support device_map, trying without: {device_map_error}")
                                return transformers.pipeline(  # type: ignore[call-overload]
                                    task,
                                    model=self.model_id,
                                )
                            else:
                                raise ModelNotAvailableError(
                                    f"Pipeline creation failed: {device_map_error}", model_id=self.model_id
                                ) from device_map_error

                # Use timeout context for model loading
                try:
                    with timeout_context(model_load_timeout, f"VLM model loading ({self.model_id})"):
                        self._pipeline = _load_model()
                        logger.info(f"Successfully loaded VLM model: {self.model_id}")

                except TimeoutError as timeout_error:
                    timeout_msg = (
                        f"VLM model loading timed out after {model_load_timeout} seconds. "
                        f"This may indicate network issues or missing model cache. "
                        f"Model: {self.model_id}"
                    )
                    logger.error(timeout_msg)
                    # Mark as unavailable so future calls don't retry
                    self._available = False
                    raise ModelNotAvailableError(timeout_msg, model_id=self.model_id, timeout=True) from timeout_error

            except ModelNotAvailableError:
                # Re-raise our custom exceptions as-is
                self._available = False
                raise
            except Exception as e:
                logger.error(f"Failed to load VLM model {self.model_id}: {e}")
                # Mark as unavailable so future calls don't retry
                self._available = False
                raise ModelNotAvailableError(f"VLM model loading failed: {e}", model_id=self.model_id) from e

    def generate(self, pil_image: Image.Image) -> str | None:
        """Generate a caption for the given PIL image.

        Args:
            pil_image: PIL Image to caption

        Returns:
            Generated caption text, or None if captioning fails
        """
        if not self.is_available():
            logger.warning("HF Caption engine not available")
            return None

        try:
            # Lazy load the pipeline
            if self._pipeline is None:
                self._load_pipeline()

            # Generate caption - handle Florence-2 vs standard pipeline
            if isinstance(self._pipeline, dict) and self._pipeline.get("type") == "florence2":
                # Florence-2 specific generation
                model = self._pipeline["model"]
                processor = self._pipeline["processor"]

                # Florence-2 uses a specific prompt format for captioning
                prompt = "<MORE_DETAILED_CAPTION>"
                inputs = processor(text=prompt, images=pil_image, return_tensors="pt")

                # Generate with Florence-2
                generated_ids = model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=1024,
                    num_beams=3,
                    do_sample=False,
                )

                # Decode the result
                generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]

                # Extract the caption from Florence-2's response format
                # Florence-2 returns: "<MORE_DETAILED_CAPTION>actual caption text"
                result = generated_text.replace(prompt, "").strip() if prompt in generated_text else generated_text.strip()

                # Convert to expected format for downstream processing
                result = [{"generated_text": result}]
            else:
                # Standard pipeline generation
                result = self._pipeline(pil_image)

            # Extract text from result - format varies by model
            if isinstance(result, list) and len(result) > 0:
                if isinstance(result[0], dict) and "generated_text" in result[0]:
                    caption = result[0]["generated_text"]
                elif isinstance(result[0], dict) and "text" in result[0]:
                    caption = result[0]["text"]
                else:
                    # Fallback: convert to string
                    caption = str(result[0])
            elif isinstance(result, dict):
                if "generated_text" in result:
                    caption = result["generated_text"]
                elif "text" in result:
                    caption = result["text"]
                else:
                    caption = str(result)
            else:
                caption = str(result)

            # Clean up the caption
            caption = caption.strip()

            # Remove common prefixes that some models add
            prefixes_to_remove = [
                "a photo of ",
                "an image of ",
                "this is ",
                "the image shows ",
                "image: ",
            ]

            caption_lower = caption.lower()
            for prefix in prefixes_to_remove:
                if caption_lower.startswith(prefix):
                    caption = caption[len(prefix) :]
                    break

            # Capitalize first letter
            if caption:
                caption = caption[0].upper() + caption[1:]

            logger.debug(f"Generated caption: {caption}")
            return caption if caption else None

        except Exception as e:
            # Import here to avoid circular imports
            from pdf2foundry.core.exceptions import ModelNotAvailableError

            if isinstance(e, ModelNotAvailableError):
                # Model loading failed - this is expected in CI minimal environments
                logger.info(f"Caption generation skipped - model not available: {e}")
            else:
                # Other errors during caption generation
                logger.error(f"Caption generation failed: {e}")
            return None


class CaptionCache:
    """LRU cache for caption results to avoid reprocessing.

    Thread Safety:
    - This cache is NOT thread-safe by design for performance reasons
    - It's intended to be used within a single pipeline execution thread
    - If multi-threading is needed, each thread should have its own cache instance
    - The current PDF2Foundry pipeline is single-threaded per document
    """

    def __init__(self, max_size: int = 2000) -> None:
        """Initialize caption cache with LRU eviction.

        Args:
            max_size: Maximum number of entries to cache
        """
        self._cache: dict[str, str | None] = {}
        self._access_order: list[str] = []
        self._max_size = max_size

    def _get_image_hash(self, image: Image.Image) -> str:
        """Generate a hash key for an image."""
        # Use shared image hashing utility for consistency
        from pdf2foundry.ingest.image_cache import get_image_hash

        return get_image_hash(image)

    def get(self, image: Image.Image) -> str | None | object:
        """Get cached caption result if available.

        Returns:
            Cached caption string, None if no caption was generated,
            or a sentinel object if not in cache
        """
        key = self._get_image_hash(image)

        if key in self._cache:
            # Update access order (move to end)
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]

        return object()  # Sentinel for "not found"

    def set(self, image: Image.Image, caption: str | None) -> None:
        """Cache caption result with LRU eviction."""
        key = self._get_image_hash(image)

        # If already exists, update access order
        if key in self._cache:
            self._access_order.remove(key)

        self._cache[key] = caption
        self._access_order.append(key)

        # Evict oldest if over limit
        while len(self._cache) > self._max_size:
            oldest_key = self._access_order.pop(0)
            self._cache.pop(oldest_key, None)

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._access_order.clear()


__all__ = [
    "CaptionCache",
    "CaptionEngine",
    "HFCaptionEngine",
]
