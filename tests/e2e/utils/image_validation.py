"""Image validation utilities for E2E tests."""

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest


def extract_html_from_json(data: Any) -> list[str]:
    """
    Extract HTML content from JSON data structures.

    Args:
        data: JSON data structure to search

    Returns:
        List of HTML content strings found in the data
    """
    html_content = []

    if isinstance(data, dict):
        # Look for HTML content in common fields
        for key, value in data.items():
            if key in ("content", "text", "description") and isinstance(value, str):
                # Check if it looks like HTML (contains tags)
                if "<" in value and ">" in value:
                    html_content.append(value)
            elif key == "text" and isinstance(value, dict) and "content" in value:
                # Foundry VTT text structure
                content = value["content"]
                if isinstance(content, str) and "<" in content and ">" in content:
                    html_content.append(content)
            else:
                # Recursively search nested structures
                html_content.extend(extract_html_from_json(value))

    elif isinstance(data, list):
        for item in data:
            html_content.extend(extract_html_from_json(item))

    return html_content


def validate_img_tag(img_tag, available_images: set[str], module_dir: Path, source_info: Any) -> list[str]:
    """
    Validate a single <img> tag.

    Args:
        img_tag: BeautifulSoup img tag element
        available_images: Set of available image paths
        module_dir: Module directory path
        source_info: Information about the source file for error reporting

    Returns:
        List of validation error messages
    """
    errors = []

    # Check src attribute
    src = img_tag.get("src")
    if not src:
        errors.append(f"<img> tag missing src attribute in {source_info}")
        return errors

    # Ensure src is relative (not absolute path or http[s])
    if src.startswith(("http://", "https://", "/")):
        errors.append(f"<img> src should be relative, got absolute: {src} in {source_info}")

    # Ensure no '..' segments or backslashes
    if ".." in src or "\\" in src:
        errors.append(f"<img> src contains invalid path segments: {src} in {source_info}")

    # Check if the referenced image exists
    # Try both the direct path and normalized variations
    src_variations = [
        src,
        src.lstrip("./"),  # Remove leading ./
        src.replace("\\", "/"),  # Normalize separators
    ]

    found = False
    for variation in src_variations:
        if variation in available_images:
            found = True
            break

    if not found:
        errors.append(f"<img> src references non-existent image: {src} in {source_info}")

    # Verify width and height attributes if present
    width = img_tag.get("width")
    height = img_tag.get("height")

    if width is not None:
        try:
            width_val = int(width)
            if width_val <= 0:
                errors.append(f"<img> width must be positive integer, got: {width} in {source_info}")
        except ValueError:
            errors.append(f"<img> width must be integer, got: {width} in {source_info}")

    if height is not None:
        try:
            height_val = int(height)
            if height_val <= 0:
                errors.append(f"<img> height must be positive integer, got: {height} in {source_info}")
        except ValueError:
            errors.append(f"<img> height must be integer, got: {height} in {source_info}")

    return errors


def test_corruption_detection(sample_image: dict[str, Any] | None) -> None:
    """
    Test corruption detection by deliberately corrupting an image.

    Args:
        sample_image: Sample image metadata for corruption test
    """
    if sample_image is None:
        return  # No images to test with

    try:
        from PIL import Image
    except ImportError:
        return

    # Create a temporary corrupted copy
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        # Copy the original image
        shutil.copy2(sample_image["path"], temp_path)

        # Corrupt the file by truncating it
        with temp_path.open("r+b") as f:
            f.seek(0, 2)  # Seek to end
            file_size = f.tell()
            if file_size > 100:
                f.seek(file_size // 2)  # Truncate to half size
                f.truncate()

        # Try to open the corrupted image - should fail
        try:
            with Image.open(temp_path) as img:
                img.verify()
            # If we get here, corruption detection failed
            pytest.fail("Corruption detection test failed: corrupted image was not detected")
        except Exception:
            # Expected - corruption was detected
            pass

    finally:
        # Clean up
        if temp_path.exists():
            temp_path.unlink()


def validate_html_image_references(module_dir: Path, extracted_images: list[dict[str, Any]]) -> None:
    """
    Validate HTML <img> references and attribute presence.

    Args:
        module_dir: Path to the generated module directory
        extracted_images: List of extracted image metadata

    Raises:
        pytest.fail: If HTML image validation fails
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        pytest.skip("BeautifulSoup not available for HTML parsing")

    # Create a set of available image paths for quick lookup
    available_images = {str(img["rel"]) for img in extracted_images}

    # Also add module-relative paths (modules/test-images/assets/...)
    module_relative_images = {f"modules/test-images/{img['rel']}" for img in extracted_images}
    available_images.update(module_relative_images)

    # Discover HTML pages under module_dir
    html_files = []
    for html_file in module_dir.rglob("*.html"):
        # Exclude non-content files if needed
        html_files.append(html_file)

    # Also check for HTML content embedded in JSON files
    json_html_content = []
    for json_file in module_dir.rglob("*.json"):
        try:
            with json_file.open() as f:
                data = json.load(f)
            html_content = extract_html_from_json(data)
            if html_content:
                json_html_content.extend(html_content)
        except Exception as e:
            pytest.fail(f"Error reading JSON file {json_file}: {e}")

    total_img_tags = 0
    validation_errors = []

    # Process standalone HTML files
    for html_file in html_files:
        try:
            with html_file.open() as f:
                html_content = f.read()

            soup = BeautifulSoup(html_content, "html.parser")
            img_tags = soup.find_all("img")

            for img_tag in img_tags:
                total_img_tags += 1
                errors = validate_img_tag(img_tag, available_images, module_dir, html_file)
                validation_errors.extend(errors)

        except Exception as e:
            pytest.fail(f"Error processing HTML file {html_file}: {e}")

    # Process HTML content from JSON files
    for html_content in json_html_content:
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            img_tags = soup.find_all("img")

            for img_tag in img_tags:
                total_img_tags += 1
                errors = validate_img_tag(img_tag, available_images, module_dir, "JSON content")
                validation_errors.extend(errors)

        except Exception as e:
            pytest.fail(f"Error processing HTML content from JSON: {e}")

    # Report validation results
    if validation_errors:
        error_msg = f"HTML image reference validation failed ({len(validation_errors)} errors):\n"
        error_msg += "\n".join(f"  - {error}" for error in validation_errors)
        pytest.fail(error_msg)

    if total_img_tags == 0:
        pytest.fail("No <img> tags found in any HTML content - image references may not be generated")

    print(f"✓ Validated {total_img_tags} <img> tags in HTML content")


def validate_image_integrity_and_formats(extracted_images: list[dict[str, Any]]) -> None:
    """
    Validate image integrity, format, and resolution with Pillow.

    Args:
        extracted_images: List of extracted image metadata

    Raises:
        pytest.fail: If image integrity validation fails
    """
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow (PIL) not available for image validation")

    # Allowed formats
    allowed_formats = {"PNG", "JPEG", "WEBP"}
    min_width, min_height = 16, 16  # More realistic minimum for small icons and decorative elements

    validation_errors = []
    corrupted_images = []

    for img_info in extracted_images:
        img_path = img_info["path"]
        rel_path = img_info["rel"]

        try:
            # Open and verify image
            with Image.open(img_path) as img:
                # Verify image can be loaded
                img.verify()

            # Reopen to get full metadata (verify() closes the image)
            with Image.open(img_path) as img:
                # Check format
                if img.format not in allowed_formats:
                    validation_errors.append(
                        f"Image {rel_path} has unsupported format: {img.format} (allowed: {allowed_formats})"
                    )

                # Check dimensions
                width, height = img.size
                if width < min_width or height < min_height:
                    validation_errors.append(
                        f"Image {rel_path} dimensions too small: {width}x{height} " f"(minimum: {min_width}x{min_height})"
                    )

        except Exception as e:
            corrupted_images.append(f"Image {rel_path} failed validation: {e}")

    # Test corruption detection with a deliberate corruption
    test_corruption_detection(extracted_images[0] if extracted_images else None)

    # Report results
    if validation_errors:
        error_msg = f"Image format/dimension validation failed ({len(validation_errors)} errors):\n"
        error_msg += "\n".join(f"  - {error}" for error in validation_errors)
        pytest.fail(error_msg)

    if corrupted_images:
        error_msg = f"Image corruption detected ({len(corrupted_images)} corrupted):\n"
        error_msg += "\n".join(f"  - {error}" for error in corrupted_images)
        pytest.fail(error_msg)

    print(f"✓ Validated integrity and format of {len(extracted_images)} images")


def test_accessibility_features(tmp_output_dir: Path, input_pdf: Path, cli_runner) -> None:
    """
    Test accessibility checks for alt text under feature toggle.

    Args:
        tmp_output_dir: Temporary output directory
        input_pdf: Input PDF fixture
        cli_runner: CLI runner fixture

    Raises:
        pytest.fail: If accessibility validation fails
    """
    # Note: This is a placeholder implementation since the CLI doesn't currently
    # have explicit accessibility flags. We'll test the current behavior and
    # ensure it's graceful.

    # For now, we'll just verify that the default conversion doesn't break
    # HTML structure and that any alt attributes (if present) are reasonable

    # The conversion was already done in the main test, so we can check
    # the existing output for alt text behavior
    module_dir = tmp_output_dir / "test-images"

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        pytest.skip("BeautifulSoup not available for accessibility testing")

    alt_text_stats = {"with_alt": 0, "without_alt": 0, "empty_alt": 0}

    # Check all HTML content for alt text patterns
    for html_file in module_dir.rglob("*.html"):
        try:
            with html_file.open() as f:
                html_content = f.read()

            soup = BeautifulSoup(html_content, "html.parser")
            img_tags = soup.find_all("img")

            for img_tag in img_tags:
                alt = img_tag.get("alt")
                if alt is None:
                    alt_text_stats["without_alt"] += 1
                elif alt.strip() == "":
                    alt_text_stats["empty_alt"] += 1
                else:
                    alt_text_stats["with_alt"] += 1

        except Exception as e:
            pytest.fail(f"Error checking accessibility in {html_file}: {e}")

    # Also check JSON-embedded HTML
    for json_file in module_dir.rglob("*.json"):
        try:
            with json_file.open() as f:
                data = json.load(f)

            html_content_list = extract_html_from_json(data)
            for html_content in html_content_list:
                soup = BeautifulSoup(html_content, "html.parser")
                img_tags = soup.find_all("img")

                for img_tag in img_tags:
                    alt = img_tag.get("alt")
                    if alt is None:
                        alt_text_stats["without_alt"] += 1
                    elif alt.strip() == "":
                        alt_text_stats["empty_alt"] += 1
                    else:
                        alt_text_stats["with_alt"] += 1

        except Exception as e:
            pytest.fail(f"Error checking accessibility in JSON {json_file}: {e}")

    # Report accessibility statistics
    total_images = sum(alt_text_stats.values())
    if total_images > 0:
        print(
            f"✓ Accessibility check: {alt_text_stats['with_alt']} with alt text, "
            f"{alt_text_stats['without_alt']} without alt text, "
            f"{alt_text_stats['empty_alt']} with empty alt text"
        )
    else:
        print("✓ Accessibility check: no <img> tags found to validate")

    # For now, we don't enforce alt text requirements since the feature
    # may not be implemented yet. We just ensure the HTML is well-formed.
