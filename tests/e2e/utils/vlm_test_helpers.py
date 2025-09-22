"""VLM test helper functions and utilities.

This module contains helper functions for VLM E2E testing, including
environment checks, caption validation, and performance comparison utilities.
"""

import json
import os
import re
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

import pytest


def assert_requirements() -> None:
    """
    Check that required dependencies are available with correct versions.

    Raises:
        pytest.skip: If transformers or torch are missing or versions too low
    """
    # Check transformers
    try:
        import transformers

        # Parse version - handle dev versions like "4.44.0.dev0"
        version_str = transformers.__version__.split(".dev")[0]
        major, minor = map(int, version_str.split(".")[:2])

        if major < 4 or (major == 4 and minor < 44):
            pytest.skip(f"transformers version {transformers.__version__} < 4.44 required")

    except ImportError:
        pytest.skip("transformers library not available (required for VLM captions)")

    # Check torch
    try:
        import torch

        # Parse version - handle dev versions like "2.3.1+cu121"
        version_str = torch.__version__.split("+")[0]
        major, minor = map(int, version_str.split(".")[:2])

        if major < 2 or (major == 2 and minor < 3):
            pytest.skip(f"torch version {torch.__version__} < 2.3 required")

    except ImportError:
        pytest.skip("torch library not available (required for VLM captions)")


def check_internet_connectivity() -> bool:
    """
    Check if internet is available for model downloads.

    Returns:
        True if internet is available, False otherwise
    """
    try:
        # Try to connect to Hugging Face
        with socket.create_connection(("huggingface.co", 443), timeout=5):
            return True
    except OSError:
        try:
            # Fallback: try HTTP request
            urllib.request.urlopen("https://huggingface.co", timeout=5)
            return True
        except Exception:
            return False


def choose_fixture(fixtures_dir: Path) -> Path:
    """
    Choose the best available fixture for VLM testing.

    Args:
        fixtures_dir: Path to fixtures directory

    Returns:
        Path to selected fixture

    Raises:
        pytest.skip: If no suitable fixture is found
    """
    # Preferred fixtures in order of preference
    preferred_fixtures = [
        "illustrated-guide.pdf",  # Best: likely has many images
        "data-manual.pdf",  # Good: technical manual with diagrams
        "comprehensive-manual.pdf",  # Fallback: comprehensive content
        "basic.pdf",  # Last resort: basic content
    ]

    for fixture_name in preferred_fixtures:
        fixture_path = fixtures_dir / fixture_name
        if fixture_path.exists():
            return fixture_path

    # If none of the preferred fixtures exist, try any PDF
    pdf_files = list(fixtures_dir.glob("*.pdf"))
    if pdf_files:
        return pdf_files[0]

    pytest.skip("No suitable PDF fixture found for VLM testing")


def run_cli(args: list[str], env: dict[str, str] | None = None, timeout: int = 600) -> dict[str, Any]:
    """
    Run pdf2foundry CLI with timing and robust error handling.

    Args:
        args: Command line arguments (excluding binary name)
        env: Additional environment variables
        timeout: Command timeout in seconds (default: 10 minutes for VLM)

    Returns:
        Dict with results including timing, exit code, and outputs
    """
    # Get CLI binary path
    cli_binary = os.getenv("PDF2FOUNDRY_CLI", "pdf2foundry")
    cmd = [cli_binary, *args]

    # Prepare environment
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    # Log command execution
    print(f"Running command: {' '.join(cmd)}")
    if env:
        print(f"Additional env vars: {env}")

    start_time = time.perf_counter()

    try:
        result = subprocess.run(
            cmd,
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            timeout=timeout,
            check=False,  # Don't raise on non-zero exit
        )

        duration = time.perf_counter() - start_time

        print(f"Command completed in {duration:.2f}s with exit code {result.returncode}")
        if result.stdout:
            print(f"Output:\n{result.stdout}")

        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": "",  # Merged into stdout
            "duration_s": duration,
        }

    except subprocess.TimeoutExpired:
        duration = time.perf_counter() - start_time
        print(f"Command timed out after {duration:.2f}s")
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "duration_s": duration,
        }
    except Exception as e:
        duration = time.perf_counter() - start_time
        print(f"Command failed after {duration:.2f}s: {e}")
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "duration_s": duration,
        }


def get_vlm_flags() -> list[str]:
    """Get standard VLM CLI flags for testing."""
    return ["--picture-descriptions", "on", "--vlm-repo-id", "Salesforce/blip-image-captioning-base"]


def validate_caption_quality(caption: str) -> tuple[bool, str]:
    """
    Validate caption quality using lightweight heuristics.

    Args:
        caption: Caption text to validate

    Returns:
        Tuple of (is_valid, reason) where is_valid indicates if caption passes quality checks
    """
    if not caption or not caption.strip():
        return False, "empty_caption"

    caption = caption.strip()

    # Length check: should be between 5 and 128 characters
    if len(caption) < 5:
        return False, f"too_short_{len(caption)}"
    if len(caption) > 128:
        return False, f"too_long_{len(caption)}"

    # Check for at least one noun-like token (lightweight heuristic)
    # Use regex fallback for basic noun detection

    # Pattern for common nouns and image-related terms
    noun_pattern = (
        r"\b([A-Za-z]+(tion|ness|ity|ship|ing)|image|photo|picture|diagram|chart|table|figure|car|tree|"
        r"person|building|text|document|page|book|paper|screen|window|door|room|house|street|road|sky|water|"
        r"food|animal|plant|flower|mountain|river|city|town|man|woman|child|people|group|object|item|thing|"
        r"area|place|location|scene|view|background|foreground|color|white|black|red|blue|green|yellow|"
        r"orange|purple|brown|gray|grey|dark|light|bright|small|large|big|little|old|new|young|open|closed|"
        r"empty|full|clean|dirty|beautiful|ugly|good|bad|happy|sad|smiling|standing|sitting|walking|running|"
        r"holding|wearing|looking|showing|containing|displaying|featuring)\b"
    )

    if re.search(noun_pattern, caption, re.IGNORECASE):
        return True, "valid"

    # Check for VLM_STRICT mode - if not strict, allow non-empty captions
    vlm_strict = os.getenv("VLM_STRICT", "0") == "1"

    if not vlm_strict:
        return True, "valid_non_strict"

    return False, "no_noun_detected"


def collect_captions_from_json(output_dir: Path) -> list[dict]:
    """
    Collect image captions from JSON artifacts in the output directory.

    Args:
        output_dir: Output directory containing module artifacts

    Returns:
        List of dicts with image information including captions
    """
    captions = []

    # Look for sources/journals/*.json files
    sources_dir = output_dir / "sources" / "journals"
    if sources_dir.exists():
        for json_file in sources_dir.glob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)

                # Look for images in the journal entry structure
                # Images might be in pages -> text -> content or similar structure
                if isinstance(data, dict):
                    _extract_images_from_journal_data(data, captions, str(json_file))

            except Exception as e:
                print(f"Warning: Failed to parse {json_file}: {e}")

    # Also check for any other JSON files that might contain image data
    for json_file in output_dir.rglob("*.json"):
        if "sources/journals" in str(json_file):
            continue  # Already processed above

        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict):
                _extract_images_from_generic_data(data, captions, str(json_file))

        except Exception as e:
            print(f"Warning: Failed to parse {json_file}: {e}")

    return captions


def _extract_images_from_journal_data(data: dict, captions: list, source_file: str) -> None:
    """Extract image data from Foundry journal entry JSON structure."""
    # Recursively search for image-like structures
    if isinstance(data, dict):
        # Check if this looks like an image asset
        if "src" in data and "name" in data:
            caption_info = {
                "src": data.get("src"),
                "name": data.get("name"),
                "caption": data.get("caption"),
                "alt_text": data.get("alt_text"),
                "page_no": data.get("page_no"),
                "source_file": source_file,
                "source_type": "journal_entry",
            }
            captions.append(caption_info)

        # Check if this is HTML content that might contain img tags with alt attributes
        if "content" in data and isinstance(data["content"], str) and "<img" in data["content"]:
            _extract_images_from_html_content(data["content"], captions, source_file)

        # Recursively search nested structures
        for value in data.values():
            if isinstance(value, dict):
                _extract_images_from_journal_data(value, captions, source_file)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        _extract_images_from_journal_data(item, captions, source_file)


def _extract_images_from_html_content(html_content: str, captions: list, source_file: str) -> None:
    """Extract image data from HTML content within JSON."""
    import re

    # Find all img tags with alt attributes
    img_pattern = r'<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"[^>]*>'
    matches = re.findall(img_pattern, html_content, re.IGNORECASE)

    for src, alt_text in matches:
        # Extract filename from src
        filename = src.split("/")[-1] if src else ""

        caption_info = {
            "src": src,
            "name": filename,
            "caption": alt_text,
            "alt_text": alt_text,
            "page_no": None,  # Not available from HTML context
            "source_file": source_file,
            "source_type": "html_content",
        }
        captions.append(caption_info)

    # Also find img tags without alt attributes (for completeness)
    img_no_alt_pattern = r'<img[^>]*src="([^"]*)"[^>]*(?!alt=)[^>]*>'
    no_alt_matches = re.findall(img_no_alt_pattern, html_content, re.IGNORECASE)

    for src in no_alt_matches:
        # Skip if we already found this image with an alt attribute
        if any(caption["src"] == src for caption in captions):
            continue

        filename = src.split("/")[-1] if src else ""

        caption_info = {
            "src": src,
            "name": filename,
            "caption": None,
            "alt_text": None,
            "page_no": None,
            "source_file": source_file,
            "source_type": "html_content",
        }
        captions.append(caption_info)


def _extract_images_from_generic_data(data: dict, captions: list, source_file: str) -> None:
    """Extract image data from generic JSON structure."""
    if isinstance(data, dict) and "images" in data and isinstance(data["images"], list):
        for img in data["images"]:
            if isinstance(img, dict):
                caption_info = {
                    "src": img.get("src"),
                    "name": img.get("name"),
                    "caption": img.get("caption"),
                    "alt_text": img.get("alt_text"),
                    "page_no": img.get("page_no"),
                    "source_file": source_file,
                    "source_type": "generic_json",
                }
                captions.append(caption_info)


def collect_captions_from_html(output_dir: Path) -> list[dict]:
    """
    Collect image captions from HTML files in the output directory.

    Args:
        output_dir: Output directory containing module artifacts

    Returns:
        List of dicts with image information from HTML
    """
    captions = []

    # Try to import BeautifulSoup for better HTML parsing
    try:
        import importlib.util

        use_bs4 = importlib.util.find_spec("bs4") is not None
    except ImportError:
        use_bs4 = False
        print("BeautifulSoup not available, using regex fallback for HTML parsing")

    # Find HTML files in the output
    for html_file in output_dir.rglob("*.html"):
        try:
            with open(html_file, encoding="utf-8") as f:
                html_content = f.read()

            if use_bs4:
                _extract_images_from_html_bs4(html_content, captions, str(html_file))
            else:
                _extract_images_from_html_regex(html_content, captions, str(html_file))

        except Exception as e:
            print(f"Warning: Failed to parse HTML {html_file}: {e}")

    return captions


def _extract_images_from_html_bs4(html_content: str, captions: list, source_file: str) -> None:
    """Extract image data from HTML using BeautifulSoup."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, "html.parser")

    for img in soup.find_all("img"):
        src = img.get("src", "")
        alt = img.get("alt", "")
        aria_label = img.get("aria-label", "")
        title = img.get("title", "")

        # Extract filename from src
        name = src.split("/")[-1] if src else ""

        caption_info = {
            "src": src,
            "name": name,
            "caption": alt or aria_label or title or None,
            "alt_text": alt,
            "aria_label": aria_label,
            "title": title,
            "source_file": source_file,
            "source_type": "html_bs4",
        }
        captions.append(caption_info)


def _extract_images_from_html_regex(html_content: str, captions: list, source_file: str) -> None:
    """Extract image data from HTML using regex fallback."""
    # Pattern to match img tags with various attributes
    img_pattern = re.compile(r'<img\s+[^>]*?src\s*=\s*["\']([^"\']+)["\'][^>]*?>', re.IGNORECASE | re.DOTALL)

    for match in img_pattern.finditer(html_content):
        src = match.group(1)
        img_tag = match.group(0)

        # Extract alt attribute
        alt_match = re.search(r'alt\s*=\s*["\']([^"\']*)["\']', img_tag, re.IGNORECASE)
        alt = alt_match.group(1) if alt_match else ""

        # Extract aria-label attribute
        aria_match = re.search(r'aria-label\s*=\s*["\']([^"\']*)["\']', img_tag, re.IGNORECASE)
        aria_label = aria_match.group(1) if aria_match else ""

        # Extract title attribute
        title_match = re.search(r'title\s*=\s*["\']([^"\']*)["\']', img_tag, re.IGNORECASE)
        title = title_match.group(1) if title_match else ""

        # Extract filename from src
        name = src.split("/")[-1] if src else ""

        caption_info = {
            "src": src,
            "name": name,
            "caption": alt or aria_label or title or None,
            "alt_text": alt,
            "aria_label": aria_label,
            "title": title,
            "source_file": source_file,
            "source_type": "html_regex",
        }
        captions.append(caption_info)
