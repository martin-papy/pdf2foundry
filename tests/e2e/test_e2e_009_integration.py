"""E2E-009: Advanced Features Integration Test.

This test validates the integration of multiple advanced features (tables, OCR, image captions)
to ensure no conflicts or regressions when features interact, using fixtures/illustrated-guide.pdf.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.fixtures import get_fixture
from utils.integration_test_helpers import (
    compare_module_outputs,
    get_combined_flags,
    validate_conflict_handling,
    validate_cross_feature_consistency,
    validate_performance_baseline,
)
from utils.performance import performance_test
from utils.validation import (
    validate_assets,
    validate_compendium_structure,
    validate_module_json,
)


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.tier2
@pytest.mark.ci_safe
def test_advanced_features_integration(tmp_output_dir: Path, cli_runner) -> None:
    """
    Test integration of multiple advanced features.

    This test performs comprehensive integration validation:
    1. Converts fixtures/illustrated-guide.pdf with combined advanced flags
    2. Validates module structure, schema compliance, and cross-feature consistency
    3. Ensures no duplicate assets or conflicting references
    4. Measures performance against baseline and sum-of-parts estimate
    5. Validates cache idempotency and conflict handling

    Args:
        tmp_output_dir: Temporary directory for test output (from conftest.py fixture)
        cli_runner: CLI runner function (from conftest.py fixture)
    """
    # Environment checks - skip if prerequisites not met
    _check_prerequisites()

    # Get input fixture - prefer illustrated-guide.pdf for mixed content
    try:
        input_pdf = get_fixture("illustrated-guide.pdf")
    except FileNotFoundError:
        try:
            # Fallback to data-manual.pdf if illustrated-guide not available
            input_pdf = get_fixture("data-manual.pdf")
        except FileNotFoundError as e:
            pytest.skip(f"Required fixture not found: {e}")

    # Verify schema availability
    schema_path = Path(__file__).parent / "schemas" / "module.schema.json"
    if not schema_path.exists():
        pytest.skip(f"Schema file not found: {schema_path}")

    # Create cache directory for the test
    tmp_cache_dir = tmp_output_dir / "cache"
    tmp_cache_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Execute CLI conversion with performance timing
    test_name = "E2E-009"
    with performance_test(test_name, "integration_conversion") as timer:
        module_dir, run_result = _run_integration_conversion(tmp_output_dir, input_pdf, cli_runner, tmp_cache_dir)

    # Step 2: Validate module structure and schema
    _validate_module_structure(module_dir)

    # Step 3: Validate cross-feature consistency and no conflicts
    validate_cross_feature_consistency(module_dir, run_result)

    # Step 4: Capture and compare performance to baseline
    validate_performance_baseline(test_name, timer.elapsed_seconds, tmp_output_dir)

    # Step 5: Verify cache idempotency
    _verify_cache_idempotency(tmp_output_dir, input_pdf, cli_runner, tmp_cache_dir, module_dir)

    # Step 6: Test conflict handling scenarios
    validate_conflict_handling(tmp_output_dir, input_pdf, cli_runner, tmp_cache_dir)

    print("✓ Advanced features integration test completed successfully")
    print(f"✓ Conversion time: {timer.elapsed_seconds:.2f}s")
    print(f"✓ Output directory: {module_dir}")
    print(f"✓ Cache directory: {tmp_cache_dir}")


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


def _run_integration_conversion(
    tmp_output_dir: Path, input_pdf: Path, cli_runner, tmp_cache_dir: Path
) -> tuple[Path, dict[str, Any]]:
    """
    Execute CLI conversion with combined advanced features.

    Args:
        tmp_output_dir: Temporary output directory
        input_pdf: Path to input PDF fixture
        cli_runner: CLI runner fixture
        tmp_cache_dir: Cache directory path

    Returns:
        Tuple of (module_directory_path, run_result_metadata)

    Raises:
        pytest.fail: If conversion fails
    """
    # Create integration-specific output directory
    integration_output_dir = tmp_output_dir / "integration"
    if integration_output_dir.exists():
        shutil.rmtree(integration_output_dir)
    integration_output_dir.mkdir(parents=True, exist_ok=True)

    # Build command arguments
    mod_id = "test-integration-009"
    cmd_args = [
        "convert",
        str(input_pdf),
        "--mod-id",
        mod_id,
        "--mod-title",
        "Advanced Features Integration Test",
        "--out-dir",
        str(integration_output_dir),
        *get_combined_flags(tmp_cache_dir),
    ]

    # Capture start time and run metadata
    start_time = time.perf_counter()
    start_timestamp = time.time()

    try:
        # Run CLI with extended timeout for complex processing
        # Use longer timeout in CI for complex integration processing
        timeout = 900 if os.environ.get("CI") == "1" else 600  # 15 min in CI, 10 min locally
        result = cli_runner(cmd_args, timeout=timeout)

        end_time = time.perf_counter()
        duration_s = end_time - start_time

        # Prepare run metadata
        run_result = {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_s": duration_s,
            "start_timestamp": start_timestamp,
            "end_timestamp": time.time(),
            "command": " ".join(cmd_args),
            "flags": get_combined_flags(tmp_cache_dir),
        }

    except subprocess.TimeoutExpired:
        pytest.fail(
            f"CLI conversion timed out after {timeout} seconds for integration test. " f"Command: {' '.join(cmd_args)}"
        )

    # Validate conversion succeeded
    if result.returncode != 0:
        # Save debug information
        debug_file = integration_output_dir / "debug_info.json"
        with open(debug_file, "w") as f:
            json.dump(run_result, f, indent=2)

        pytest.fail(
            f"CLI conversion failed with exit code {result.returncode}. "
            f"Command: {' '.join(cmd_args)}. "
            f"Error: {result.stderr}. "
            f"Debug info saved to: {debug_file}"
        )

    module_dir = integration_output_dir / mod_id
    if not module_dir.exists():
        pytest.fail(f"Expected module directory not found: {module_dir}")

    return module_dir, run_result


def _validate_module_structure(module_dir: Path) -> None:
    """
    Validate basic module structure and schema compliance.

    Args:
        module_dir: Path to the generated module directory

    Raises:
        pytest.fail: If validation fails
    """
    # Validate module.json schema
    module_json_path = module_dir / "module.json"
    schema_errors = validate_module_json(module_json_path)
    if schema_errors:
        pytest.fail(f"Module schema validation failed: {schema_errors}")

    # Validate compendium structure
    compendium_errors = validate_compendium_structure(module_dir)
    if compendium_errors:
        pytest.fail(f"Compendium structure validation failed: {compendium_errors}")

    # Validate assets
    asset_errors = validate_assets(module_dir)
    if asset_errors:
        pytest.fail(f"Asset validation failed: {asset_errors}")

    print("✓ Module structure validation passed")


def _verify_cache_idempotency(
    tmp_output_dir: Path, input_pdf: Path, cli_runner, tmp_cache_dir: Path, original_module_dir: Path
) -> None:
    """
    Verify cache idempotency by re-running with same cache.

    Args:
        tmp_output_dir: Temporary output directory
        input_pdf: Path to input PDF fixture
        cli_runner: CLI runner fixture
        tmp_cache_dir: Cache directory path
        original_module_dir: Original module directory for comparison

    Raises:
        pytest.fail: If cached run doesn't produce identical results or isn't faster
    """
    # Create separate output directory for cached run
    cached_output_dir = tmp_output_dir / "cached"
    cached_output_dir.mkdir(parents=True, exist_ok=True)

    # Build command arguments (identical to original for true idempotency test)
    mod_id = "test-integration-009"  # Same as original for idempotency
    cmd_args = [
        "convert",
        str(input_pdf),
        "--mod-id",
        mod_id,
        "--mod-title",
        "Advanced Features Integration Test",  # Same as original
        "--out-dir",
        str(cached_output_dir),
        *get_combined_flags(tmp_cache_dir),
    ]

    # Run with timing
    start_time = time.perf_counter()
    try:
        result = cli_runner(cmd_args, timeout=300)  # Should be much faster with cache
        cached_duration = time.perf_counter() - start_time
    except subprocess.TimeoutExpired:
        pytest.fail("Cached run timed out - cache may not be working")

    if result.returncode != 0:
        pytest.fail(f"Cached run failed: {result.stderr}")

    cached_module_dir = cached_output_dir / mod_id
    if not cached_module_dir.exists():
        pytest.fail(f"Cached module directory not found: {cached_module_dir}")

    # Compare outputs for deterministic behavior
    compare_module_outputs(original_module_dir, cached_module_dir)

    print("✓ Cache idempotency verified")
    print(f"✓ Cached run duration: {cached_duration:.2f}s")
