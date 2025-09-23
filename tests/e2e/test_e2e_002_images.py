"""E2E-002: Image Extraction and Processing Test.

This test validates image extraction, asset management, and HTML references
using fixtures/illustrated-guide.pdf with comprehensive image validation.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.fixtures import get_fixture
from utils.image_validation import (
    test_accessibility_features,
    validate_html_image_references,
    validate_image_integrity_and_formats,
)
from utils.validation import validate_module_json


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.tier2
@pytest.mark.ci_safe
def test_images(tmp_output_dir: Path, cli_runner) -> None:
    """
    Test image extraction and processing with illustrated-guide.pdf.

    This test performs comprehensive image validation:
    1. Converts fixtures/illustrated-guide.pdf using pdf2foundry CLI
    2. Validates extracted image assets and counts
    3. Validates HTML <img> references and attributes
    4. Validates image integrity, formats, and dimensions with Pillow
    5. Tests accessibility features (alt text) under different settings

    Args:
        tmp_output_dir: Temporary directory for test output (from conftest.py fixture)
        cli_runner: CLI runner function (from conftest.py fixture)
    """
    # Environment checks - skip if prerequisites not met
    _check_prerequisites()

    # Get input fixture
    try:
        input_pdf = get_fixture("illustrated-guide.pdf")
    except FileNotFoundError as e:
        pytest.skip(f"Required fixture not found: {e}")

    # Verify schema availability
    schema_path = Path(__file__).parent / "schemas" / "module.schema.json"
    if not schema_path.exists():
        pytest.skip(f"Schema file not found: {schema_path}")

    # Step 1: Execute CLI conversion (subtask 19.1)
    module_dir = _run_default_conversion(tmp_output_dir, input_pdf, cli_runner)

    # Step 2: Enumerate extracted image assets (subtask 19.2)
    extracted_images = _enumerate_and_validate_images(module_dir)

    # Step 3: Validate HTML <img> references (subtask 19.3)
    validate_html_image_references(module_dir, extracted_images)

    # Step 4: Image integrity and format validation (subtask 19.4)
    validate_image_integrity_and_formats(extracted_images)

    # Step 5: Accessibility checks for alt text (subtask 19.5)
    test_accessibility_features(tmp_output_dir, cli_runner)

    print("✓ CLI conversion completed successfully")
    print(f"✓ Found and validated {len(extracted_images)} extracted images")
    print("✓ HTML image references validation passed")
    print("✓ Image integrity and format validation passed")
    print("✓ Accessibility features validation passed")
    print(f"✓ Output directory: {tmp_output_dir}")


def _check_prerequisites() -> None:
    """
    Check that all prerequisites for running the test are available.

    Raises:
        pytest.skip: If any prerequisite is missing
    """
    # Check if pdf2foundry binary is available
    if not shutil.which("pdf2foundry"):
        pytest.skip("pdf2foundry binary not found in PATH")

    # Verify pdf2foundry responds to --version
    try:
        result = subprocess.run(["pdf2foundry", "--version"], capture_output=True, text=True, timeout=10, check=False)
        if result.returncode != 0:
            pytest.skip(f"pdf2foundry --version failed with exit code {result.returncode}")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        pytest.skip(f"pdf2foundry version check failed: {e}")

    # Check if Pillow is available for image validation
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        pytest.skip("Pillow (PIL) not available for image validation")


def _run_default_conversion(tmp_output_dir: Path, input_pdf: Path, cli_runner) -> Path:
    """
    Execute CLI conversion for illustrated-guide.pdf (subtask 19.1).

    Args:
        tmp_output_dir: Temporary output directory
        input_pdf: Path to input PDF fixture
        cli_runner: CLI runner fixture

    Returns:
        Path to the generated module directory

    Raises:
        pytest.fail: If conversion fails
    """
    # Ensure output directory is clean
    if tmp_output_dir.exists():
        shutil.rmtree(tmp_output_dir)
    tmp_output_dir.mkdir(parents=True, exist_ok=True)

    # Run pdf2foundry CLI with illustrated-guide.pdf
    cmd_args = [
        "convert",
        str(input_pdf),
        "--mod-id",
        "test-images",
        "--mod-title",
        "Test Images Module",
        "--out-dir",
        str(tmp_output_dir),
    ]

    try:
        # Run CLI with a reasonable timeout to prevent hanging
        # Use longer timeout for complex image processing in CI
        timeout = 480 if os.environ.get("CI") == "1" else 180  # 8 minutes in CI, 3 minutes locally
        result = cli_runner(cmd_args, timeout=timeout)
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"CLI conversion timed out after {timeout} seconds. This may indicate a hanging issue "
            f"with image processing or PDF conversion. Command: pdf2foundry {' '.join(cmd_args)}"
        )
    except Exception as e:
        pytest.fail(f"CLI execution failed with exception: {e}")

    # Assert successful exit code
    if result.returncode != 0:
        # Create debug log file for troubleshooting
        debug_log = tmp_output_dir / "debug.log"
        debug_log.write_text(
            f"Command: pdf2foundry {' '.join(cmd_args)}\n" f"Exit code: {result.returncode}\n" f"Output:\n{result.stdout}\n"
        )
        pytest.fail(
            f"CLI conversion failed with exit code {result.returncode}. "
            f"Output: {result.stdout}. Debug log saved to: {debug_log}"
        )

    # Validate basic module structure
    module_dir = tmp_output_dir / "test-images"
    if not module_dir.exists():
        pytest.fail(f"Module directory not found at expected location: {module_dir}")

    # Basic schema validation
    module_json_path = module_dir / "module.json"
    if not module_json_path.exists():
        pytest.fail(f"module.json not found at expected location: {module_json_path}")

    validation_errors = validate_module_json(module_json_path)
    if validation_errors:
        error_msg = "module.json validation failed:\n" + "\n".join(f"  - {error}" for error in validation_errors)
        pytest.fail(error_msg)

    return module_dir


def _enumerate_and_validate_images(module_dir: Path) -> list[dict[str, Any]]:
    """
    Enumerate extracted image assets and validate base invariants (subtask 19.2).

    Args:
        module_dir: Path to the generated module directory

    Returns:
        List of image metadata dictionaries with keys: path, rel, ext, size_bytes

    Raises:
        pytest.fail: If image validation fails
    """
    # Candidate asset roots
    asset_candidates = [
        module_dir / "assets",
        module_dir / "assets" / "images",
        module_dir / "images",
    ]

    # Find the first existing asset directory
    assets_dir = None
    for candidate in asset_candidates:
        if candidate.exists():
            assets_dir = candidate
            break

    if assets_dir is None:
        # Fall back to globbing under module_dir
        assets_dir = module_dir

    # Collect images with common extensions (case-insensitive)
    image_extensions = {".png", ".jpg", ".jpeg", ".webp"}
    extracted_images = []

    for file_path in assets_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in image_extensions:
            # Ensure file is within module_dir (no symlink escape)
            try:
                real_file = file_path.resolve()
                real_module = module_dir.resolve()
                if not str(real_file).startswith(str(real_module)):
                    pytest.fail(f"Image file outside module directory (symlink escape): {file_path}")
            except Exception as e:
                pytest.fail(f"Error resolving path for {file_path}: {e}")

            # Ensure relative, normalized paths
            try:
                rel_path = file_path.relative_to(module_dir)
                rel_str = str(rel_path)
                if rel_str.startswith("..") or "//" in rel_str or "\\\\" in rel_str:
                    pytest.fail(f"Invalid relative path for image: {rel_str}")
            except ValueError as e:
                pytest.fail(f"Error computing relative path for {file_path}: {e}")

            # Build image metadata
            extracted_images.append(
                {
                    "path": file_path,
                    "rel": rel_path,
                    "ext": file_path.suffix.lower(),
                    "size_bytes": file_path.stat().st_size,
                }
            )

    # Assert minimum expected count (>= 5 for illustrated-guide.pdf)
    expected_min = 5
    if len(extracted_images) < expected_min:
        pytest.fail(
            f"Expected at least {expected_min} extracted images, but found {len(extracted_images)}. "
            f"Images found: {[img['rel'] for img in extracted_images]}"
        )

    print(f"✓ Found {len(extracted_images)} extracted images meeting validation criteria")
    return extracted_images
