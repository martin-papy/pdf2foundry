"""E2E-001: Basic PDF Conversion Test.

This test validates the basic end-to-end conversion of fixtures/basic.pdf
with default settings, ensuring module structure, schema compliance, and content fidelity.
"""

import shutil
import sys
from pathlib import Path

import pytest

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.fixtures import get_fixture


@pytest.mark.e2e
@pytest.mark.integration
def test_basic(tmp_output_dir: Path, cli_runner) -> None:
    """
    Test basic PDF conversion with default settings.

    This test performs the complete E2E workflow:
    1. Converts fixtures/basic.pdf using pdf2foundry CLI
    2. Validates module.json against schema
    3. Validates compendium structure and assets
    4. Performs content fidelity checks

    Args:
        tmp_output_dir: Temporary directory for test output (from conftest.py fixture)
        cli_runner: CLI runner function (from conftest.py fixture)
    """
    # Environment checks - skip if prerequisites not met
    _check_prerequisites()

    # Get input fixture
    try:
        input_pdf = get_fixture("basic.pdf")
    except FileNotFoundError as e:
        pytest.skip(f"Required fixture not found: {e}")

    # Verify schema availability
    schema_path = Path(__file__).parent / "schemas" / "module.schema.json"
    if not schema_path.exists():
        pytest.skip(f"Schema file not found: {schema_path}")

    # Step 1: Execute CLI conversion
    # Ensure output directory is clean
    if tmp_output_dir.exists():
        shutil.rmtree(tmp_output_dir)
    tmp_output_dir.mkdir(parents=True, exist_ok=True)

    # Run pdf2foundry CLI with basic.pdf using the convert command
    cmd_args = [
        "convert",
        str(input_pdf),
        "--mod-id",
        "test-basic",
        "--mod-title",
        "Test Basic Module",
        "--out-dir",
        str(tmp_output_dir),
    ]

    try:
        result = cli_runner(cmd_args)
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

    # Subsequent validation steps will be implemented in following subtasks
    # For now, just verify the command executed successfully
    print("✓ CLI conversion completed successfully")
    print(f"✓ Output directory: {tmp_output_dir}")
    print(f"✓ Generated files: {list(tmp_output_dir.rglob('*'))}")


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

    This function will be implemented in subtask 18.5 to perform content fidelity checks.

    Args:
        module_dir: Path to the generated module directory
        expected_strings: List of strings that should be present in the content
    """
    # Implementation placeholder - will be completed in subtask 18.5
    pass
