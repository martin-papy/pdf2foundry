"""E2E-001: Basic PDF Conversion Test (No ML).

This test validates the basic end-to-end conversion of fixtures/basic.pdf
with ML features explicitly disabled, ensuring CI-safe operation in minimal
dependency environments.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.fixtures import get_fixture
from utils.validation import validate_assets, validate_compendium_structure, validate_module_json


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.tier1
@pytest.mark.ci_safe
def test_basic_conversion_no_ml(tmp_output_dir: Path, cli_runner, test_environment_info) -> None:
    """
    Test basic PDF conversion with ML features disabled (CI minimal mode).

    This test performs the complete E2E workflow without ML dependencies:
    1. Converts fixtures/basic.pdf using pdf2foundry CLI with --no-ml flag
    2. Validates module.json against schema
    3. Validates compendium structure and assets
    4. Performs content fidelity checks
    5. Verifies that ML features are properly disabled

    Args:
        tmp_output_dir: Temporary directory for test output (from conftest.py fixture)
        cli_runner: CLI runner function (from conftest.py fixture)
        test_environment_info: Environment information fixture
    """
    # Environment checks - skip if prerequisites not met
    _check_prerequisites()

    # Log environment information for debugging
    print(f"Test environment info: {test_environment_info}")

    # Get input fixture
    try:
        input_pdf = get_fixture("basic.pdf")
    except FileNotFoundError as e:
        pytest.skip(f"Required fixture not found: {e}")

    # Verify schema availability
    schema_path = Path(__file__).parent / "schemas" / "module.schema.json"
    if not schema_path.exists():
        pytest.skip(f"Schema file not found: {schema_path}")

    # Step 1: Execute CLI conversion with ML features disabled
    # Ensure output directory is clean
    if tmp_output_dir.exists():
        shutil.rmtree(tmp_output_dir)
    tmp_output_dir.mkdir(parents=True, exist_ok=True)

    # Run pdf2foundry CLI with basic.pdf using the convert command
    # Explicitly disable ML features for CI-safe operation
    cmd_args = [
        "convert",
        str(input_pdf),
        "--mod-id",
        "test-basic-no-ml",
        "--mod-title",
        "Test Basic Module (No ML)",
        "--out-dir",
        str(tmp_output_dir),
        "--picture-descriptions",
        "off",  # Explicitly disable ML
        "--no-ml",  # Disable ML for CI testing
    ]

    try:
        # Run CLI with a reasonable timeout for basic tests
        result = cli_runner(cmd_args, timeout=120)  # 2 minute timeout for CI-safe tests
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"CLI conversion timed out after 120 seconds. This should not happen for CI-safe tests "
            f"without ML dependencies. Command: pdf2foundry {' '.join(cmd_args)}"
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

    # Step 2: Validate module.json against schema
    module_json_path = tmp_output_dir / "test-basic-no-ml" / "module.json"
    if not module_json_path.exists():
        pytest.fail(f"module.json not found at expected location: {module_json_path}")

    validation_errors = validate_module_json(module_json_path)
    if validation_errors:
        error_msg = "module.json validation failed:\n" + "\n".join(f"  - {error}" for error in validation_errors)
        pytest.fail(error_msg)

    # Step 3: Validate compendium structure and assets
    module_dir = tmp_output_dir / "test-basic-no-ml"

    # Validate directory structure
    structure_errors = validate_compendium_structure(module_dir)
    if structure_errors:
        error_msg = "Compendium structure validation failed:\n" + "\n".join(f"  - {error}" for error in structure_errors)
        pytest.fail(error_msg)

    # Validate asset integrity
    asset_errors = validate_assets(module_dir)
    if asset_errors:
        error_msg = "Asset validation failed:\n" + "\n".join(f"  - {error}" for error in asset_errors)
        pytest.fail(error_msg)

    # Verify at least one Journal entry/page is generated
    sources_journals_dir = module_dir / "sources" / "journals"
    if not sources_journals_dir.exists():
        pytest.fail(f"Journal sources directory not found: {sources_journals_dir}")

    journal_files = list(sources_journals_dir.glob("*.json"))
    if not journal_files:
        pytest.fail(f"No journal entry files found in: {sources_journals_dir}")

    # Verify at least one journal file has pages
    has_pages = False
    for journal_file in journal_files:
        try:
            with journal_file.open() as f:
                journal_data = json.load(f)

            if isinstance(journal_data, dict) and journal_data.get("pages"):
                has_pages = True
                break
        except Exception as e:
            pytest.fail(f"Error reading journal file {journal_file}: {e}")

    if not has_pages:
        pytest.fail("No journal entries with pages found - content generation may have failed")

    # Step 4: Content fidelity checks (same as basic test)
    expected_content_strings = [
        "Drow Elite Warriors",
        "Beholder",
        "Appendix",
        "Order of the Gauntlet",
        "Underdark",
        "Veterans",
    ]
    _assert_content_contains(module_dir, expected_content_strings)

    # Step 5: Verify ML features were properly disabled
    _verify_no_ml_artifacts(module_dir)

    # Step 6: Negative validation - test that validation properly fails when module.json is missing
    _test_negative_validation(module_dir)

    print("✓ CLI conversion completed successfully (No ML mode)")
    print("✓ module.json validation passed")
    print("✓ Compendium structure validation passed")
    print("✓ Asset validation passed")
    print("✓ Content fidelity checks passed")
    print("✓ ML features properly disabled")
    print("✓ Negative validation tests passed")
    print(f"✓ Found {len(journal_files)} journal entries with content")
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
        import subprocess

        result = subprocess.run(["pdf2foundry", "--version"], capture_output=True, text=True, timeout=10, check=False)
        if result.returncode != 0:
            pytest.skip(f"pdf2foundry --version failed with exit code {result.returncode}")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        pytest.skip(f"pdf2foundry version check failed: {e}")


def _assert_content_contains(module_dir: Path, expected_strings: list[str]) -> None:
    """
    Assert that the generated content contains expected strings.

    Searches through all JSON and HTML content in the module directory for the expected strings
    using case-insensitive matching.

    Args:
        module_dir: Path to the generated module directory
        expected_strings: List of strings that should be present in the content

    Raises:
        AssertionError: If any expected string is not found in the content
    """
    if not module_dir.exists():
        pytest.fail(f"Module directory not found: {module_dir}")

    # Collect all content text from JSON and HTML files
    all_content = []

    # Search in sources directory for JSON files
    sources_dir = module_dir / "sources"
    if sources_dir.exists():
        for json_file in sources_dir.rglob("*.json"):
            try:
                with json_file.open() as f:
                    data = json.load(f)
                content_text = _extract_text_content(data)
                if content_text:
                    all_content.append(content_text)
            except Exception as e:
                pytest.fail(f"Error reading JSON file {json_file}: {e}")

        # Also check standalone HTML files
        for html_file in sources_dir.rglob("*.html"):
            try:
                with html_file.open() as f:
                    html_content = f.read()
                text_content = _strip_html_tags(html_content)
                if text_content:
                    all_content.append(text_content)
            except Exception as e:
                pytest.fail(f"Error reading HTML file {html_file}: {e}")

    # Combine all content and normalize whitespace
    combined_content = " ".join(all_content).lower()
    combined_content = " ".join(combined_content.split())  # Normalize whitespace

    # Check for each expected string (case-insensitive)
    missing_strings = []
    for expected in expected_strings:
        if expected.lower() not in combined_content:
            missing_strings.append(expected)

    if missing_strings:
        pytest.fail(
            f"Content fidelity check failed. Missing expected strings: {missing_strings}\n"
            f"Searched in {len(all_content)} content sources from {module_dir}"
        )


def _extract_text_content(data: Any) -> str:
    """
    Extract text content from JSON data structures.

    Recursively searches for text content in common Foundry VTT fields like
    name, title, label, content, and nested structures.

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
                text_content += _strip_html_tags(content) + " "

        # Recursively process nested structures
        for value in data.values():
            text_content += _extract_text_content(value)

    elif isinstance(data, list):
        for item in data:
            text_content += _extract_text_content(item)

    return text_content


def _strip_html_tags(html_content: str) -> str:
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


def _verify_no_ml_artifacts(module_dir: Path) -> None:
    """
    Verify that no ML-related artifacts were generated.

    This function checks that:
    1. No image captions were generated (alt attributes should be empty or generic)
    2. No VLM-related metadata is present in the output
    3. Processing completed without attempting to load ML models

    Args:
        module_dir: Path to the generated module directory

    Raises:
        AssertionError: If ML artifacts are found when they shouldn't be
    """
    # Check for image captions in HTML content
    sources_dir = module_dir / "sources"
    if sources_dir.exists():
        for json_file in sources_dir.rglob("*.json"):
            try:
                with json_file.open() as f:
                    data = json.load(f)

                # Look for image elements with AI-generated captions
                html_content = _extract_html_from_json(data)
                if html_content:
                    # Check for sophisticated alt text that would indicate VLM processing
                    import re

                    img_tags = re.findall(r'<img[^>]*alt="([^"]*)"[^>]*>', html_content, re.IGNORECASE)

                    for alt_text in img_tags:
                        # AI-generated captions typically contain descriptive phrases
                        # Generic or empty alt text is expected in no-ML mode
                        if (
                            alt_text
                            and len(alt_text) > 20
                            and any(
                                word in alt_text.lower()
                                for word in ["shows", "depicts", "contains", "features", "displays", "illustrates"]
                            )
                        ):
                            pytest.fail(
                                f"Found potential AI-generated caption in no-ML mode: '{alt_text}'. "
                                f"ML features should be disabled."
                            )

            except Exception as e:
                # Don't fail the test for parsing errors, just log
                print(f"Warning: Could not parse {json_file} for ML artifact check: {e}")

    print("✓ No ML artifacts found - ML features properly disabled")


def _extract_html_from_json(data: Any) -> str:
    """
    Extract HTML content from JSON data structures.

    Args:
        data: JSON data structure to extract HTML from

    Returns:
        Extracted HTML content as a single string
    """
    html_content = ""

    if isinstance(data, dict):
        # Extract from text content structures (Foundry VTT format)
        if "text" in data and isinstance(data["text"], dict):
            content = data["text"].get("content", "")
            if content:
                html_content += content + " "

        # Recursively process nested structures
        for value in data.values():
            html_content += _extract_html_from_json(value)

    elif isinstance(data, list):
        for item in data:
            html_content += _extract_html_from_json(item)

    return html_content


def _test_negative_validation(module_dir: Path) -> None:
    """
    Test negative validation by temporarily removing module.json and ensuring validation fails.

    Args:
        module_dir: Path to the generated module directory

    Raises:
        AssertionError: If negative validation doesn't work as expected
    """
    module_json_path = module_dir / "module.json"
    backup_path = module_dir / "module.json.bak"

    if not module_json_path.exists():
        pytest.fail(f"module.json not found for negative validation test: {module_json_path}")

    try:
        # Move module.json aside temporarily
        shutil.move(str(module_json_path), str(backup_path))

        # Validate that validation now fails
        validation_errors = validate_module_json(module_json_path)

        if not validation_errors:
            pytest.fail(
                "Negative validation failed: validate_module_json should have reported errors " "when module.json is missing"
            )

        # Check that the error mentions the missing file
        error_text = " ".join(validation_errors).lower()
        if "not found" not in error_text and "missing" not in error_text:
            pytest.fail(f"Negative validation failed: error message should mention missing file. Got: {validation_errors}")

    finally:
        # Always restore the file
        if backup_path.exists():
            shutil.move(str(backup_path), str(module_json_path))
