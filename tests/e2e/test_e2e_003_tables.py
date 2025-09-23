"""E2E-003: Table Processing Modes Test.

This test validates the different table processing modes (structured, auto, image-only)
using fixtures/data-manual.pdf and compares output quality and processing performance.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.fixtures import get_fixture
from utils.performance import performance_test
from utils.table_validation import (
    analyze_table_representations,
    assert_mode_specific_requirements,
    assert_representation_exclusivity,
)
from utils.validation import validate_assets, validate_compendium_structure, validate_module_json


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.tier2
@pytest.mark.ci_safe
@pytest.mark.parametrize("mode", ["structured", "auto", "image-only"])
def test_table_processing_modes(tmp_output_dir: Path, cli_runner, mode: str) -> None:
    """
    Test table processing modes with data-manual.pdf.

    This test performs comprehensive table processing validation:
    1. Converts fixtures/data-manual.pdf using pdf2foundry CLI with --tables <mode>
    2. Validates module structure and schema compliance
    3. Performs mode-specific table representation checks
    4. Records and validates performance metrics

    Args:
        tmp_output_dir: Temporary directory for test output (from conftest.py fixture)
        cli_runner: CLI runner function (from conftest.py fixture)
        mode: Table processing mode ('structured', 'auto', 'image-only')
    """
    # Environment checks - skip if prerequisites not met
    _check_prerequisites()

    # Get input fixture
    try:
        input_pdf = get_fixture("data-manual.pdf")
    except FileNotFoundError as e:
        pytest.skip(f"Required fixture not found: {e}")

    # Verify schema availability
    schema_path = Path(__file__).parent / "schemas" / "module.schema.json"
    if not schema_path.exists():
        pytest.skip(f"Schema file not found: {schema_path}")

    # Step 1: Execute CLI conversion with performance timing
    test_name = f"table_processing_{mode}"
    with performance_test(test_name, "conversion_time") as timer:
        module_dir = _run_table_conversion(tmp_output_dir, input_pdf, cli_runner, mode)

    # Step 2: Validate module structure and schema
    _validate_module_structure(module_dir, mode)

    # Step 3: Perform mode-specific table assertions
    table_analysis = analyze_table_representations(module_dir, mode)
    assert_mode_specific_requirements(table_analysis, mode)

    # Step 4: Cross-mode validation (ensure mutual exclusivity where required)
    if mode != "auto":
        assert_representation_exclusivity(table_analysis, mode)

    print(f"✓ CLI conversion completed successfully for mode: {mode}")
    print("✓ Module structure validation passed")
    print("✓ Mode-specific table assertions passed")
    print(f"✓ Found {table_analysis['structured_count']} structured tables")
    print(f"✓ Found {table_analysis['image_count']} image tables")
    print(f"✓ Conversion time: {timer.elapsed_seconds:.2f}s")
    print(f"✓ Output directory: {module_dir}")


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


def _run_table_conversion(tmp_output_dir: Path, input_pdf: Path, cli_runner, mode: str) -> Path:
    """
    Execute CLI conversion for data-manual.pdf with specified table mode.

    Args:
        tmp_output_dir: Temporary output directory
        input_pdf: Path to input PDF fixture
        cli_runner: CLI runner fixture
        mode: Table processing mode

    Returns:
        Path to the generated module directory

    Raises:
        pytest.fail: If conversion fails
    """
    # Create mode-specific output directory
    mode_output_dir = tmp_output_dir / mode
    if mode_output_dir.exists():
        shutil.rmtree(mode_output_dir)
    mode_output_dir.mkdir(parents=True, exist_ok=True)

    # Run pdf2foundry CLI with table mode
    cmd_args = [
        "convert",
        str(input_pdf),
        "--mod-id",
        f"test-tables-{mode}",
        "--mod-title",
        f"Test Tables {mode.title()} Mode",
        "--out-dir",
        str(mode_output_dir),
        "--tables",
        mode,
    ]

    try:
        # Run CLI with extended timeout for table processing
        # Use longer timeout for complex table processing in CI
        timeout = 420 if os.environ.get("CI") == "1" else 300  # 7 minutes in CI, 5 minutes locally
        result = cli_runner(cmd_args, timeout=timeout)
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"CLI conversion timed out after {timeout} seconds for mode {mode}. "
            f"This may indicate a hanging issue with table processing. "
            f"Command: pdf2foundry {' '.join(cmd_args)}"
        )
    except Exception as e:
        pytest.fail(f"CLI execution failed with exception for mode {mode}: {e}")

    # Assert successful exit code
    if result.returncode != 0:
        # Create debug log file for troubleshooting
        debug_log = mode_output_dir / "debug.log"
        debug_log.write_text(
            f"Command: pdf2foundry {' '.join(cmd_args)}\n"
            f"Mode: {mode}\n"
            f"Exit code: {result.returncode}\n"
            f"Output:\n{result.stdout}\n"
        )
        pytest.fail(
            f"CLI conversion failed for mode {mode} with exit code {result.returncode}. "
            f"Output: {result.stdout}. Debug log saved to: {debug_log}"
        )

    # Validate basic module structure exists
    module_dir = mode_output_dir / f"test-tables-{mode}"
    if not module_dir.exists():
        pytest.fail(f"Module directory not found at expected location for mode {mode}: {module_dir}")

    return module_dir


def _validate_module_structure(module_dir: Path, mode: str) -> None:
    """
    Validate module structure and schema compliance.

    Args:
        module_dir: Path to the generated module directory
        mode: Table processing mode

    Raises:
        pytest.fail: If validation fails
    """
    # Validate module.json against schema
    module_json_path = module_dir / "module.json"
    if not module_json_path.exists():
        pytest.fail(f"module.json not found at expected location: {module_json_path}")

    validation_errors = validate_module_json(module_json_path)
    if validation_errors:
        error_msg = "module.json validation failed:\n" + "\n".join(f"  - {error}" for error in validation_errors)
        pytest.fail(error_msg)

    # Validate compendium structure
    structure_errors = validate_compendium_structure(module_dir)
    if structure_errors:
        error_msg = "Compendium structure validation failed:\n" + "\n".join(f"  - {error}" for error in structure_errors)
        pytest.fail(error_msg)

    # Validate asset integrity
    asset_errors = validate_assets(module_dir)
    if asset_errors:
        error_msg = "Asset validation failed:\n" + "\n".join(f"  - {error}" for error in asset_errors)
        pytest.fail(error_msg)
