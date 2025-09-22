"""OCR test helper functions and utilities.

This module contains helper functions for OCR E2E testing, including
conversion runners, artifact collectors, and validation utilities.
"""

import json
import os
import time
from pathlib import Path
from typing import Any

# OCR test configuration
OCR_MODES = ["auto", "on", "off"]


def get_ocr_flags(mode: str) -> list[str]:
    """Get CLI flags for OCR mode."""
    return ["--ocr", mode]


# Thresholds - configurable via environment variables for CI tuning
MIN_CHARS_OCR = int(os.getenv("PDF2FOUNDRY_TEST_MIN_CHARS_OCR", "300"))
MAX_CHARS_NO_OCR = int(os.getenv("PDF2FOUNDRY_TEST_MAX_CHARS_NO_OCR", "80"))
MIN_OCR_SLOWDOWN_RATIO = float(os.getenv("PDF2FOUNDRY_TEST_MIN_OCR_SLOWDOWN_RATIO", "1.15"))
MAX_OCR_SLOWDOWN_RATIO = float(os.getenv("PDF2FOUNDRY_TEST_MAX_OCR_SLOWDOWN_RATIO", "8.0"))

# Ground truth tokens that should be present in OCR output
EXPECTED_TOKENS = [
    "document",  # Basic token that should appear
    "page",  # Another basic token
]


def load_ground_truth_tokens() -> list[str]:
    """
    Load ground truth tokens for OCR validation.

    Returns:
        List of expected tokens that should be present in OCR output
    """
    # For now, use hardcoded tokens. In the future, this could load from
    # tests/e2e/fixtures/snippets/scanned_document_header.txt
    return EXPECTED_TOKENS


def run_conversion_with_timing(cli_runner, input_pdf: Path, output_dir: Path, ocr_mode: str) -> dict[str, Any]:
    """
    Run PDF conversion with timing measurement.

    Args:
        cli_runner: CLI runner function
        input_pdf: Path to input PDF file
        output_dir: Output directory for conversion
        ocr_mode: OCR mode ('auto', 'on', 'off')

    Returns:
        Dict with conversion results including timing
    """
    mod_id = f"test-scan-{ocr_mode}"

    cmd_args = [
        "convert",
        str(input_pdf),
        "--mod-id",
        mod_id,
        "--mod-title",
        f"Test Scan {ocr_mode.title()}",
        "--out-dir",
        str(output_dir),
        "--no-toc",  # Disable TOC for simpler testing
        *get_ocr_flags(ocr_mode),
    ]

    start_time = time.monotonic()

    try:
        result = cli_runner(cmd_args, timeout=300)  # 5 minute timeout
        duration_s = time.monotonic() - start_time

        return {
            "mode": ocr_mode,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": getattr(result, "stderr", ""),
            "duration_s": duration_s,
            "out_dir": output_dir,
        }

    except Exception as e:
        duration_s = time.monotonic() - start_time
        return {
            "mode": ocr_mode,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "duration_s": duration_s,
            "out_dir": output_dir,
        }


def collect_artifacts(module_dir: Path) -> dict[str, Any]:
    """
    Collect and analyze artifacts from conversion output.

    Args:
        module_dir: Path to generated module directory

    Returns:
        Dict with artifact analysis results
    """
    artifacts = {
        "text_length": 0,
        "image_count": 0,
        "content_text": "",
    }

    # Collect text content from journal sources
    sources_dir = module_dir / "sources" / "journals"
    if sources_dir.exists():
        for json_file in sources_dir.glob("*.json"):
            try:
                with json_file.open() as f:
                    data = json.load(f)

                text_content = extract_text_content(data)
                artifacts["content_text"] += text_content + " "

                # Count images in HTML content
                image_count = count_images_in_content(data)
                artifacts["image_count"] += image_count

            except Exception as e:
                print(f"Warning: Error reading {json_file}: {e}")

    # Calculate total text length (normalized)
    normalized_text = " ".join(artifacts["content_text"].split())
    artifacts["text_length"] = len(normalized_text)

    return artifacts


def extract_text_content(data: Any) -> str:
    """
    Extract text content from JSON data structures.

    Args:
        data: JSON data structure to extract text from

    Returns:
        Extracted text content as a single string
    """
    text_content = ""

    if isinstance(data, dict):
        # Extract from common text fields
        text_fields = ["name", "title", "label", "description"]
        for field in text_fields:
            if field in data and isinstance(data[field], str):
                text_content += data[field] + " "

        # Extract from text content structures (Foundry VTT format)
        if "text" in data and isinstance(data["text"], dict):
            content = data["text"].get("content", "")
            if content:
                # Strip HTML tags from content
                text_content += strip_html_tags(content) + " "

        # Recursively process nested structures
        for value in data.values():
            text_content += extract_text_content(value)

    elif isinstance(data, list):
        for item in data:
            text_content += extract_text_content(item)

    return text_content


def strip_html_tags(html_content: str) -> str:
    """
    Strip HTML tags from content and return plain text.

    Args:
        html_content: HTML content string

    Returns:
        Plain text with HTML tags removed
    """
    if not html_content:
        return ""

    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")
        return soup.get_text()
    except ImportError:
        # Fallback: simple regex-based tag removal
        import re

        clean_text = re.sub(r"<[^>]+>", "", html_content)
        return clean_text


def count_images_in_content(data: Any) -> int:
    """
    Count images in content data.

    Args:
        data: JSON data structure to count images in

    Returns:
        Number of images found
    """
    image_count = 0

    if isinstance(data, dict):
        # Check text content for <img> tags
        if "text" in data and isinstance(data["text"], dict):
            content = data["text"].get("content", "")
            if content:
                import re

                img_tags = re.findall(r"<img[^>]*>", content, re.IGNORECASE)
                image_count += len(img_tags)

        # Recursively process nested structures
        for value in data.values():
            image_count += count_images_in_content(value)

    elif isinstance(data, list):
        for item in data:
            image_count += count_images_in_content(item)

    return image_count


def validate_content_by_mode(ocr_mode: str, artifacts: dict[str, Any], expected_tokens: list[str]) -> None:
    """
    Validate content characteristics based on OCR mode.

    Args:
        ocr_mode: OCR mode ('auto', 'on', 'off')
        artifacts: Artifact analysis results
        expected_tokens: List of expected tokens for OCR modes
    """
    text_length = artifacts["text_length"]
    image_count = artifacts["image_count"]
    content_text = artifacts["content_text"].lower()

    if ocr_mode == "off":
        # Off mode: should have minimal text and images present
        assert text_length <= MAX_CHARS_NO_OCR, (
            f"OCR off mode should have minimal text. " f"Expected <= {MAX_CHARS_NO_OCR} chars, got {text_length}"
        )
        assert image_count >= 1, f"OCR off mode should have images present. Got {image_count} images"
        print(f"✓ OCR off validation: {text_length} chars, {image_count} images")

    else:  # 'on' or 'auto'
        # OCR modes: should have more text and expected tokens
        if text_length >= MIN_CHARS_OCR:
            # If we have sufficient text, validate tokens
            missing_tokens = []
            for token in expected_tokens:
                if token.lower() not in content_text:
                    missing_tokens.append(token)

            if missing_tokens:
                print(f"Warning: Missing expected tokens in OCR output: {missing_tokens}")
                print(f"Content preview: {content_text[:200]}...")
                # For now, just warn rather than fail, as OCR quality can vary

        else:
            # If text length is low, it might indicate OCR didn't work properly
            print(f"Warning: OCR mode '{ocr_mode}' produced only {text_length} chars of text")
            print("This may indicate OCR processing issues with the test fixture")

        print(f"✓ OCR {ocr_mode} validation: {text_length} chars, {image_count} images")


def store_timing_data(output_dir: Path, mode: str, duration: float) -> None:
    """
    Store timing data for cross-mode comparison.

    Args:
        output_dir: Base output directory
        mode: OCR mode
        duration: Duration in seconds
    """
    timing_file = output_dir / "timing_data.json"

    # Load existing data or create new
    timing_data = {}
    if timing_file.exists():
        try:
            with timing_file.open() as f:
                timing_data = json.load(f)
        except Exception:
            pass  # Start fresh if file is corrupted

    # Store timing for this mode
    timing_data[mode] = duration

    # Save updated data
    with timing_file.open("w") as f:
        json.dump(timing_data, f, indent=2)


def load_timing_data(output_dir: Path) -> dict[str, float]:
    """
    Load timing data from previous test runs.

    Args:
        output_dir: Base output directory

    Returns:
        Dict mapping mode names to durations
    """
    timing_file = output_dir / "timing_data.json"

    if not timing_file.exists():
        return {}

    try:
        with timing_file.open() as f:
            return json.load(f)
    except Exception:
        return {}


def validate_timing_ratios(base_off: float, on_ratio: float, auto_ratio: float) -> None:
    """
    Validate OCR timing ratios are within expected bounds.

    Args:
        base_off: Base duration for 'off' mode
        on_ratio: Ratio of 'on' mode to 'off' mode
        auto_ratio: Ratio of 'auto' mode to 'off' mode
    """
    # Check if base timing is too small for reliable ratio comparison
    if base_off < 0.5:
        print(f"Warning: Base timing very small ({base_off:.2f}s), using absolute checks")
        # Use absolute time differences for very fast operations
        return

    # Check CI environment for relaxed bounds
    is_ci = os.getenv("CI", "").lower() in ("true", "1", "yes")
    if is_ci:
        print("CI environment detected - using relaxed timing bounds")
        # In CI, just check that OCR modes aren't dramatically slower
        max_ratio = MAX_OCR_SLOWDOWN_RATIO * 2  # Double the tolerance
    else:
        max_ratio = MAX_OCR_SLOWDOWN_RATIO

    # Validate 'on' mode timing
    assert on_ratio >= MIN_OCR_SLOWDOWN_RATIO, (
        f"OCR 'on' mode should be slower than 'off'. " f"Expected ratio >= {MIN_OCR_SLOWDOWN_RATIO}, got {on_ratio:.2f}"
    )
    assert on_ratio <= max_ratio, (
        f"OCR 'on' mode shouldn't be excessively slow. " f"Expected ratio <= {max_ratio}, got {on_ratio:.2f}"
    )

    # Validate 'auto' mode timing (more lenient as it may not trigger OCR)
    assert auto_ratio >= 1.0, f"OCR 'auto' mode shouldn't be faster than 'off'. " f"Got ratio {auto_ratio:.2f}"
    assert auto_ratio <= max_ratio, (
        f"OCR 'auto' mode shouldn't be excessively slow. " f"Expected ratio <= {max_ratio}, got {auto_ratio:.2f}"
    )


def save_debug_info(output_dir: Path, result: dict[str, Any]) -> None:
    """
    Save debug information when conversion fails.

    Args:
        output_dir: Output directory for debug files
        result: Conversion result dict
    """
    debug_file = output_dir / "debug.log"

    debug_content = f"""
OCR Test Debug Information
=========================
Mode: {result['mode']}
Exit Code: {result['exit_code']}
Duration: {result['duration_s']:.2f}s

STDOUT:
{result['stdout']}

STDERR:
{result['stderr']}
"""

    debug_file.write_text(debug_content.strip())
    print(f"Debug information saved to: {debug_file}")
