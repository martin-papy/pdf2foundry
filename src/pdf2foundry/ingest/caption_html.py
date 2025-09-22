"""HTML caption utilities for VLM integration."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdf2foundry.model.content import HtmlPage, ImageAsset


def update_html_with_captions(pages: list["HtmlPage"], images: list["ImageAsset"]) -> None:
    """Update HTML img tags with alt attributes from ImageAsset captions.

    This function updates the HTML content in pages to add alt attributes to img tags
    based on the captions stored in ImageAsset objects.

    Args:
        pages: List of HtmlPage objects to update
        images: List of ImageAsset objects containing captions
    """
    # Create a mapping from image filename to caption
    caption_map = {}
    for image in images:
        if image.caption:
            caption_map[image.name] = image.caption

    if not caption_map:
        return

    # Update HTML in each page
    for page in pages:
        original_html = page.html
        updated_html = original_html

        # Find and update img tags
        def replace_img_tag(match: re.Match[str]) -> str:
            full_tag = match.group(0)
            src_match = re.search(r'src="[^"]*?([^/]+\.(?:png|jpg|jpeg|gif|svg))"', full_tag, re.IGNORECASE)
            if src_match:
                filename = src_match.group(1)
                if filename in caption_map:
                    caption = caption_map[filename]
                    # Check if alt attribute already exists
                    if "alt=" in full_tag:
                        # Replace existing alt attribute
                        updated_tag = re.sub(r'alt="[^"]*"', f'alt="{caption}"', full_tag)
                    else:
                        # Add alt attribute before the closing >
                        updated_tag = full_tag[:-1] + f' alt="{caption}">'
                    return updated_tag
            return full_tag

        updated_html = re.sub(r"<img[^>]*>", replace_img_tag, updated_html)

        if updated_html != original_html:
            page.html = updated_html
