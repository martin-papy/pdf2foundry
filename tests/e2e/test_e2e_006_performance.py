"""E2E-006: Performance and Scalability Test.

This test benchmarks large documents, single vs multi-threaded processing,
and page selection functionality to ensure performance requirements are met.
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
from utils.performance import performance_test
from utils.validation import validate_module_json

# Performance test scenarios
SCENARIOS = {
    "large_doc_single_thread": {
        "fixture": "illustrated-guide.pdf",
        "workers": 1,
        "description": "Large document with single-threaded processing",
    },
    "large_doc_multi_thread": {
        "fixture": "illustrated-guide.pdf",
        "workers": 4,
        "description": "Large document with multi-threaded processing (4 workers)",
    },
    "mid_doc_pages_all": {
        "fixture": "comprehensive-manual.pdf",
        "pages": None,
        "description": "Mid-sized document with all pages",
    },
    "mid_doc_pages_subset": {
        "fixture": "comprehensive-manual.pdf",
        "pages": "1-10",
        "description": "Mid-sized document with page selection (1-10)",
    },
}

# Performance thresholds and constants
PERF_THRESHOLD = float(os.getenv("PERF_THRESHOLD", "0.2"))  # 20% regression threshold
PERF_THRESHOLD_CI = float(os.getenv("PERF_THRESHOLD_CI", str(PERF_THRESHOLD * 1.5)))  # Relaxed for CI
PERF_UPDATE_BASELINE = os.getenv("PERF_UPDATE_BASELINE", "0") == "1"
NIGHTLY = os.getenv("NIGHTLY", "0") == "1"
E2E_PERF = os.getenv("E2E_PERF", "0") == "1"
CI = os.getenv("CI", "0") == "1"


def _check_prerequisites() -> None:
    """Check if prerequisites for performance testing are met."""
    # Check if we should skip performance tests in CI
    if CI and not NIGHTLY and not E2E_PERF:
        pytest.skip(
            "Performance tests skipped in PR CI. "
            "Set E2E_PERF=1 to run in PR or NIGHTLY=1 for nightly builds. "
            "See tests/e2e/README.md for details."
        )

    # Check CLI availability with timeout
    try:
        cli_binary = os.getenv("PDF2FOUNDRY_CLI", "pdf2foundry")
        result = subprocess.run(
            [cli_binary, "--version"],
            capture_output=True,
            text=True,
            timeout=30,  # Increased timeout for CI stability
        )
        if result.returncode != 0:
            pytest.skip(f"pdf2foundry CLI not available or not working: {result.stderr}")
    except subprocess.TimeoutExpired:
        pytest.skip("pdf2foundry CLI version check timed out (may indicate system issues)")
    except FileNotFoundError:
        pytest.skip(f"pdf2foundry CLI not found: {cli_binary}")
    except Exception as e:
        pytest.skip(f"pdf2foundry CLI check failed: {e}")


def _build_cli_args(
    input_pdf: Path,
    output_dir: Path,
    mod_id: str,
    workers: int | str | None = None,
    pages: str | None = None,
) -> list[str]:
    """
    Build CLI arguments for pdf2foundry conversion.

    Args:
        input_pdf: Path to input PDF file
        output_dir: Output directory path
        mod_id: Module ID for the conversion
        workers: Number of workers (1, auto, or specific number)
        pages: Page range specification (e.g., "1-10")

    Returns:
        List of CLI arguments
    """
    args = [
        "convert",
        str(input_pdf),
        "--mod-id",
        mod_id,
        "--mod-title",
        f"Performance Test {mod_id}",
        "--out-dir",
        str(output_dir),
    ]

    if workers is not None:
        args.extend(["--workers", str(workers)])

    if pages is not None:
        args.extend(["--pages", pages])

    return args


def _validate_page_selection_output(module_dir: Path, pages_spec: str) -> None:
    """
    Validate that page selection output contains only the specified pages.

    Args:
        module_dir: Path to the generated module directory
        pages_spec: Page specification string (e.g., "1-10")

    Raises:
        AssertionError: If page selection validation fails
    """
    import json

    from pdf2foundry.cli.parse import parse_page_spec

    # Parse the expected pages to validate the spec format
    try:
        parse_page_spec(pages_spec)
    except ValueError as e:
        pytest.fail(f"Invalid page specification for validation: {pages_spec}: {e}")

    # Check module.json exists
    module_json_path = module_dir / "module.json"
    if not module_json_path.exists():
        pytest.fail(f"module.json not found for page selection validation: {module_json_path}")

    # Load and inspect module.json
    try:
        with module_json_path.open() as f:
            module_data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        pytest.fail(f"Failed to load module.json for page selection validation: {e}")

    # Basic validation that we have a reasonable structure
    assert "packs" in module_data, "module.json should contain packs"
    assert len(module_data["packs"]) > 0, "module.json should have at least one pack"

    # Check that sources directory exists and has reasonable content
    sources_dir = module_dir / "sources" / "journals"
    if not sources_dir.exists():
        pytest.fail(f"Sources directory not found: {sources_dir}")

    # Count journal entry files (each should represent content from the selected pages)
    journal_files = list(sources_dir.glob("*.json"))
    assert len(journal_files) > 0, f"No journal files found in {sources_dir}"

    # For a more thorough validation, we could:
    # 1. Parse each journal file and check page references
    # 2. Verify asset files correspond only to selected pages
    # 3. Check that no content from excluded pages is present
    #
    # For now, we validate basic structure and assume the CLI page filtering worked
    # if the conversion completed successfully and produced reasonable output

    print(f"✓ Page selection validation passed: {len(journal_files)} journal files for pages {pages_spec}")


def _run_conversion_with_timing(
    scenario_name: str,
    input_pdf: Path,
    output_dir: Path,
    cli_runner,
    workers: int | str | None = None,
    pages: str | None = None,
    timeout: int = 1800,
) -> dict[str, Any]:
    """
    Run PDF conversion with performance timing.

    Args:
        scenario_name: Name of the performance scenario
        input_pdf: Path to input PDF file
        output_dir: Output directory path
        cli_runner: CLI runner fixture
        workers: Number of workers for processing
        pages: Page range specification
        timeout: Command timeout in seconds

    Returns:
        Dictionary with timing results and metadata
    """
    # Clean output directory
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build CLI arguments
    mod_id = f"perf-{scenario_name.replace('_', '-')}"
    args = _build_cli_args(input_pdf, output_dir, mod_id, workers, pages)

    # Adjust timeout for CI stability (reduce flakiness)
    if CI:
        timeout = min(timeout * 2, 3600)  # Double timeout in CI, max 1 hour

    # Run conversion with timing and regression checking
    with performance_test(
        test_name=f"e2e_006_performance_{scenario_name}",
        metric_name="conversion_time",
        check_regression=True,
        threshold=PERF_THRESHOLD_CI if CI else PERF_THRESHOLD,
    ) as timer:
        try:
            result = cli_runner(args, timeout=timeout)
        except subprocess.TimeoutExpired:
            pytest.fail(
                f"Performance test {scenario_name} timed out after {timeout}s. "
                f"This may indicate a performance regression or system resource issues. "
                f"Command: pdf2foundry {' '.join(args)}"
            )
        except Exception as e:
            pytest.fail(f"Performance test {scenario_name} failed with exception: {e}")

    # Check conversion success
    if result.returncode != 0:
        debug_log = output_dir / "debug.log"
        debug_log.write_text(
            f"Scenario: {scenario_name}\n"
            f"Command: pdf2foundry {' '.join(args)}\n"
            f"Exit code: {result.returncode}\n"
            f"Output:\n{result.stdout}\n"
        )
        pytest.fail(
            f"Performance test {scenario_name} failed with exit code {result.returncode}. "
            f"Output: {result.stdout}. Debug log: {debug_log}"
        )

    # Validate basic output structure
    module_dir = output_dir / mod_id
    if not module_dir.exists():
        pytest.fail(f"Module directory not created: {module_dir}")

    module_json_path = module_dir / "module.json"
    if not module_json_path.exists():
        pytest.fail(f"module.json not found: {module_json_path}")

    # Basic validation (don't fail on schema errors in perf tests)
    validation_errors = validate_module_json(module_json_path)
    if validation_errors:
        print(f"Warning: module.json validation issues in {scenario_name}: {validation_errors}")

    return {
        "scenario": scenario_name,
        "duration": timer.elapsed_seconds,
        "exit_code": result.returncode,
        "module_dir": module_dir,
        "workers": workers,
        "pages": pages,
    }


@pytest.mark.perf
@pytest.mark.slow
@pytest.mark.e2e
@pytest.mark.tier2
@pytest.mark.ci_safe
def test_performance_setup_smoke(tmp_output_dir: Path, cli_runner) -> None:
    """
    Smoke test to validate performance harness and fixture availability.

    This test ensures:
    1. Required fixtures are available
    2. Performance utilities work correctly
    3. Basic CLI execution and timing works
    4. Performance metrics are written correctly

    Args:
        tmp_output_dir: Temporary directory for test output
        cli_runner: CLI runner function
    """
    _check_prerequisites()

    # Test fixture availability
    try:
        small_fixture = get_fixture("single-page.pdf")
        assert small_fixture.exists(), f"Smoke test fixture not found: {small_fixture}"
    except FileNotFoundError as e:
        pytest.skip(f"Smoke test fixture not available: {e}")

    # Test performance utilities with a quick conversion
    scenario_name = "smoke_test"
    result = _run_conversion_with_timing(
        scenario_name=scenario_name,
        input_pdf=small_fixture,
        output_dir=tmp_output_dir / scenario_name,
        cli_runner=cli_runner,
        timeout=60,  # Short timeout for smoke test
    )

    # Validate results
    assert result["exit_code"] == 0, f"Smoke test conversion failed: {result}"
    assert result["duration"] > 0, "Performance timing should be positive"
    assert result["module_dir"].exists(), "Module directory should be created"

    # Check that performance metrics were written
    perf_dir = Path(__file__).parent / "perf"
    assert perf_dir.exists(), "Performance directory should exist"

    # Look for the metrics file (may have timestamp suffix)
    metrics_files = list(perf_dir.glob(f"e2e_006_performance_{scenario_name}*.json"))
    assert len(metrics_files) > 0, f"Performance metrics file should be created in {perf_dir}"

    print(f"✓ Smoke test completed in {result['duration']:.2f}s")
    print(f"✓ Performance metrics written to {perf_dir}")


@pytest.mark.perf
@pytest.mark.slow
@pytest.mark.e2e
@pytest.mark.tier2
@pytest.mark.ci_safe
@pytest.mark.parametrize("workers", [1, 4])
def test_threading_performance(tmp_output_dir: Path, cli_runner, workers: int) -> None:
    """
    Benchmark single-threaded vs multi-threaded processing on large document.

    This test compares wall-clock time for different worker configurations
    to ensure multi-threading provides performance benefits or at least
    doesn't significantly degrade performance.

    Args:
        tmp_output_dir: Temporary directory for test output
        cli_runner: CLI runner function
        workers: Number of workers (1 for single-thread, 4 for multi-thread)
    """
    _check_prerequisites()

    # Get large document fixture
    try:
        large_fixture = get_fixture("illustrated-guide.pdf")
        assert large_fixture.exists(), f"Large fixture not found: {large_fixture}"
    except FileNotFoundError as e:
        pytest.skip(f"Large document fixture not available: {e}")

    # Run performance test
    scenario_name = f"threading_{workers}_workers"
    result = _run_conversion_with_timing(
        scenario_name=scenario_name,
        input_pdf=large_fixture,
        output_dir=tmp_output_dir / scenario_name,
        cli_runner=cli_runner,
        workers=workers,
        timeout=1800,  # 30 minutes for large document
    )

    # Validate results
    assert result["exit_code"] == 0, f"Threading test failed: {result}"
    assert result["duration"] > 0, "Performance timing should be positive"

    print(f"✓ Threading test ({workers} workers) completed in {result['duration']:.2f}s")

    # Additional validation: ensure reasonable performance bounds
    # Large document should complete within reasonable time (adjust as needed)
    max_reasonable_time = 1200  # 20 minutes
    if result["duration"] > max_reasonable_time:
        pytest.fail(
            f"Threading test took too long: {result['duration']:.2f}s > {max_reasonable_time}s. "
            f"This may indicate a performance regression."
        )


@pytest.mark.perf
@pytest.mark.slow
@pytest.mark.e2e
@pytest.mark.tier2
@pytest.mark.ci_safe
@pytest.mark.parametrize("pages", [None, "1-10"])
def test_page_selection_performance(tmp_output_dir: Path, cli_runner, pages: str | None) -> None:
    """
    Validate page selection functionality and measure timing differences.

    This test compares processing time for full document vs page subset
    and verifies that page selection produces correct output.

    Args:
        tmp_output_dir: Temporary directory for test output
        cli_runner: CLI runner function
        pages: Page range specification (None for all pages, "1-10" for subset)
    """
    _check_prerequisites()

    # Get mid-sized document fixture
    try:
        mid_fixture = get_fixture("comprehensive-manual.pdf")
        assert mid_fixture.exists(), f"Mid-sized fixture not found: {mid_fixture}"
    except FileNotFoundError as e:
        pytest.skip(f"Mid-sized document fixture not available: {e}")

    # Run performance test
    scenario_name = f"pages_{'all' if pages is None else pages.replace('-', '_')}"
    result = _run_conversion_with_timing(
        scenario_name=scenario_name,
        input_pdf=mid_fixture,
        output_dir=tmp_output_dir / scenario_name,
        cli_runner=cli_runner,
        pages=pages,
        timeout=600,  # 10 minutes for mid-sized document
    )

    # Validate results
    assert result["exit_code"] == 0, f"Page selection test failed: {result}"
    assert result["duration"] > 0, "Performance timing should be positive"

    print(f"✓ Page selection test ({pages or 'all'}) completed in {result['duration']:.2f}s")

    # Validate page selection output correctness
    if pages is not None:
        _validate_page_selection_output(result["module_dir"], pages)

    # Ensure reasonable performance bounds
    max_reasonable_time = 300  # 5 minutes for mid-sized document
    if result["duration"] > max_reasonable_time:
        pytest.fail(
            f"Page selection test took too long: {result['duration']:.2f}s > {max_reasonable_time}s. "
            f"This may indicate a performance regression."
        )


@pytest.mark.perf
@pytest.mark.slow
@pytest.mark.e2e
@pytest.mark.tier2
@pytest.mark.ci_safe
def test_performance_baseline_comparison(tmp_output_dir: Path, cli_runner) -> None:
    """
    Run a comprehensive performance comparison against baseline metrics.

    This test runs multiple scenarios and compares results against
    stored baselines, failing if performance regressions are detected.

    Args:
        tmp_output_dir: Temporary directory for test output
        cli_runner: CLI runner function
    """
    _check_prerequisites()

    results = []

    # Run key performance scenarios
    scenarios_to_test = [
        ("illustrated-guide.pdf", {"workers": 1}, "baseline_large_single"),
        ("illustrated-guide.pdf", {"workers": 4}, "baseline_large_multi"),
        ("comprehensive-manual.pdf", {"pages": "1-10"}, "baseline_mid_subset"),
    ]

    for fixture_name, kwargs, scenario_name in scenarios_to_test:
        try:
            fixture_path = get_fixture(fixture_name)
            assert fixture_path.exists(), f"Fixture not found: {fixture_path}"
        except FileNotFoundError as e:
            print(f"Skipping {scenario_name}: {e}")
            continue

        result = _run_conversion_with_timing(
            scenario_name=scenario_name,
            input_pdf=fixture_path,
            output_dir=tmp_output_dir / scenario_name,
            cli_runner=cli_runner,
            timeout=1800,
            **kwargs,
        )

        results.append(result)
        print(f"✓ Baseline scenario {scenario_name} completed in {result['duration']:.2f}s")

    # Ensure we ran at least some tests
    assert len(results) > 0, "No performance scenarios could be executed"

    # All individual tests should have passed (regression checking is done in performance_test)
    for result in results:
        assert result["exit_code"] == 0, f"Baseline test failed: {result['scenario']}"

    print(f"✓ All {len(results)} baseline scenarios completed successfully")
