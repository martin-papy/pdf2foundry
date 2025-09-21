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

from PIL import Image  # type: ignore[import-not-found]

from pdf2foundry.ingest.caption_engine import CaptionCache, HFCaptionEngine
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
    options: PdfPipelineOptions, on_progress: ProgressCallback = None
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
            logger.warning(
                "Picture descriptions enabled but no VLM repository ID provided. "
                "Image captions will be skipped."
            )
            _safe_emit(on_progress, "caption:no_model", {"reason": "no_vlm_repo_id"})
        else:
            try:
                caption_engine = HFCaptionEngine(options.vlm_repo_id)
                caption_cache = CaptionCache()
                if caption_engine.is_available():
                    _safe_emit(
                        on_progress,
                        "caption:initialized",
                        {"model_id": options.vlm_repo_id},
                    )
                else:
                    _safe_emit(
                        on_progress,
                        "caption:unavailable",
                        {"model_id": options.vlm_repo_id},
                    )
            except Exception as e:
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
