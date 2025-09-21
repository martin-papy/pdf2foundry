"""Caption engine abstraction for PDF2Foundry.

This module provides an abstraction layer for image captioning engines, with a
Hugging Face transformers-based implementation. Captions are generated for figure-like
images when picture descriptions are enabled.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from PIL import Image  # type: ignore[import-not-found]

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
        """Lazily load the transformers pipeline."""
        if self._pipeline is None:
            try:
                import transformers  # type: ignore[import-not-found]

                logger.info(f"Loading VLM model: {self.model_id}")

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

                self._pipeline = transformers.pipeline(
                    task=task,
                    model=self.model_id,
                    device_map="auto",  # Use GPU if available
                )
                logger.info(f"Successfully loaded VLM model: {self.model_id}")
            except Exception as e:
                logger.error(f"Failed to load VLM model {self.model_id}: {e}")
                raise

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

            # Generate caption
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
