"""Caption processing functionality for PDF2Foundry.

This module handles the application of captions to extracted images when picture
descriptions are enabled in the pipeline.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PIL import Image

from pdf2foundry.ingest.caption_engine import CaptionCache, HFCaptionEngine
from pdf2foundry.ingest.feature_logger import log_error_policy, log_feature_availability
from pdf2foundry.model.content import ImageAsset
from pdf2foundry.model.pipeline_options import PdfPipelineOptions

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, dict[str, Any]], None] | None


def _safe_emit(callback: ProgressCallback, event: str, payload: dict[str, Any]) -> None:
    """Safely emit a progress event."""
    if callback:
        with contextlib.suppress(Exception):
            callback(event, payload)


def apply_captions_to_images(
    images: list[ImageAsset],
    assets_dir: Path,
    options: PdfPipelineOptions,
    caption_engine: HFCaptionEngine | None,
    caption_cache: CaptionCache | None,
    on_progress: ProgressCallback = None,
) -> None:
    """Apply captions to extracted images when picture descriptions are enabled.

    Args:
        images: List of ImageAsset objects to caption
        assets_dir: Directory containing the image assets
        options: Pipeline options containing picture description settings
        caption_engine: Caption engine instance (None if not available)
        caption_cache: Caption cache instance (None if not available)
        on_progress: Optional progress callback
    """
    if not options.picture_descriptions:
        logger.debug("Picture descriptions disabled, skipping captioning")
        return

    if caption_engine is None:
        logger.warning("Caption engine not available, skipping image captioning")
        return

    if caption_cache is None:
        logger.warning("Caption cache not available, skipping image captioning")
        return

    if not caption_engine.is_available():
        logger.warning("Caption engine not available, skipping image captioning")
        return

    logger.info(f"Generating captions for {len(images)} images")

    captioned_count = 0
    for image in images:
        try:
            # Load the image file
            image_path = assets_dir / image.name
            if not image_path.exists():
                logger.warning(f"Image file not found: {image_path}")
                continue

            # Load as PIL Image
            pil_image = Image.open(image_path)

            # Check cache first
            cached_caption = caption_cache.get(pil_image)
            if isinstance(cached_caption, str | type(None)):
                # Cache hit: either a string caption or None (no caption was generated)
                caption = cached_caption
                logger.debug(f"Using cached caption for {image.name}")
            else:
                # Generate caption
                logger.debug(f"Generating caption for {image.name}")
                caption = caption_engine.generate(pil_image)
                caption_cache.set(pil_image, caption)

                _safe_emit(
                    on_progress,
                    "caption:image_processed",
                    {"image_name": image.name, "has_caption": caption is not None},
                )

            # Apply caption to image
            if caption:
                image.caption = caption
                # alt_text is automatically set via the property
                captioned_count += 1
                logger.debug(f"Applied caption to {image.name}: {caption}")
            else:
                logger.debug(f"No caption generated for {image.name}")

        except Exception as e:
            logger.warning(f"Failed to caption image {image.name}: {e}")
            continue

    logger.info(f"Successfully captioned {captioned_count}/{len(images)} images")

    _safe_emit(
        on_progress,
        "caption:batch_completed",
        {"total_images": len(images), "captioned_count": captioned_count},
    )


def initialize_caption_components(
    options: PdfPipelineOptions,
    on_progress: ProgressCallback = None,
    shared_image_cache: Any = None,
) -> tuple[HFCaptionEngine | None, CaptionCache | None]:
    """Initialize caption engine and cache components.

    Args:
        options: Pipeline options containing caption settings
        on_progress: Optional progress callback

    Returns:
        Tuple of (caption_engine, caption_cache) or (None, None) if not available
    """
    caption_engine = None
    caption_cache = None

    if options.picture_descriptions:
        if options.vlm_repo_id is None:
            log_error_policy(
                "Captions",
                "no_vlm_repo_id",
                "skip",
                "Picture descriptions enabled but no VLM repository ID provided",
            )
            logger.warning(
                "Picture descriptions enabled but no VLM repository ID provided. " "Image captions will be skipped."
            )
            _safe_emit(on_progress, "caption:no_model", {"reason": "no_vlm_repo_id"})
        else:
            try:
                caption_engine = HFCaptionEngine(options.vlm_repo_id)
                # Use cache limits from shared cache if available
                if shared_image_cache and hasattr(shared_image_cache, "_limits"):
                    cache_size = shared_image_cache._limits.caption_cache
                else:
                    cache_size = 2000
                caption_cache = CaptionCache(max_size=cache_size)
                if caption_engine.is_available():
                    log_feature_availability("Captions", True)
                    _safe_emit(
                        on_progress,
                        "caption:initialized",
                        {"model_id": options.vlm_repo_id},
                    )
                else:
                    log_feature_availability("Captions", False, "VLM model not available")
                    _safe_emit(
                        on_progress,
                        "caption:unavailable",
                        {"model_id": options.vlm_repo_id},
                    )
            except (TimeoutError, ConnectionError, OSError) as e:
                # Network/timeout errors should be handled gracefully
                log_error_policy(
                    "Captions",
                    "model_load_timeout",
                    "continue",
                    f"VLM model '{options.vlm_repo_id}' failed to load due to network/timeout: {e}",
                )
                logger.warning(
                    f"Caption engine initialization failed due to network/timeout, continuing without captions: {e}"
                )
                _safe_emit(
                    on_progress,
                    "caption:timeout",
                    {"model_id": options.vlm_repo_id, "error": str(e)},
                )
                caption_engine = None
                caption_cache = None
            except Exception as e:
                # Import here to avoid circular imports
                from pdf2foundry.core.exceptions import ModelNotAvailableError

                # Handle ModelNotAvailableError specifically for better logging
                if isinstance(e, ModelNotAvailableError):
                    log_error_policy(
                        "Captions",
                        "model_not_available",
                        "continue",
                        f"VLM model '{options.vlm_repo_id}' not available: {e}",
                    )
                    logger.warning(f"VLM model not available, continuing without captions: {e}")
                    _safe_emit(
                        on_progress,
                        "caption:model_not_available",
                        {"model_id": options.vlm_repo_id, "error": str(e)},
                    )
                else:
                    log_error_policy(
                        "Captions",
                        "model_load_failed",
                        "continue",
                        f"VLM model '{options.vlm_repo_id}' failed to load: {e}",
                    )
                logger.error(f"Caption engine initialization failed: {e}")
                _safe_emit(
                    on_progress,
                    "caption:init_failed",
                    {"model_id": options.vlm_repo_id, "error": str(e)},
                )
                caption_engine = None
                caption_cache = None

    return caption_engine, caption_cache


__all__ = [
    "apply_captions_to_images",
    "initialize_caption_components",
]
