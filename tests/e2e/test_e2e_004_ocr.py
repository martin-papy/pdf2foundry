"""E2E-004: OCR Processing Test.

This test validates OCR functionality with auto, on, and off modes using
fixtures/scanned-document.pdf, validating text extraction quality and timing impact.
"""

import shutil
import sys
from pathlib import Path

import pytest

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.fixtures import get_fixture
from utils.ocr_test_helpers import (
    MAX_CHARS_NO_OCR,
    MAX_OCR_SLOWDOWN_RATIO,
    MIN_CHARS_OCR,
    MIN_OCR_SLOWDOWN_RATIO,
    OCR_MODES,
    collect_artifacts,
    load_ground_truth_tokens,
    load_timing_data,
    run_conversion_with_timing,
    save_debug_info,
    store_timing_data,
    validate_content_by_mode,
    validate_timing_ratios,
)


@pytest.mark.e2e
@pytest.mark.ocr
@pytest.mark.tier2
@pytest.mark.parametrize("ocr_mode", OCR_MODES)
def test_ocr_processing(tmp_output_dir: Path, cli_runner, ocr_mode: str) -> None:
    """
    Test OCR functionality with different modes.

    This test performs OCR processing with auto, on, and off modes:
    1. Checks Tesseract availability (skips if missing)
    2. Converts fixtures/scanned-document.pdf with specified OCR mode
    3. Validates text extraction quality based on mode
    4. Measures timing impact of OCR processing

    Args:
        tmp_output_dir: Temporary directory for test output
        cli_runner: CLI runner function
        ocr_mode: OCR mode to test ('auto', 'on', 'off')
    """
    # Precondition: Check if Tesseract is available
    if shutil.which("tesseract") is None:
        pytest.skip("Tesseract not installed - OCR tests require tesseract binary")

    # Load ground truth tokens
    expected_tokens = load_ground_truth_tokens()

    # Log test configuration
    print("\n=== OCR Test Configuration ===")
    print(f"OCR Mode: {ocr_mode}")
    print(f"MIN_CHARS_OCR: {MIN_CHARS_OCR}")
    print(f"MAX_CHARS_NO_OCR: {MAX_CHARS_NO_OCR}")
    print(f"Expected tokens: {expected_tokens}")
    print(f"OCR slowdown ratio range: {MIN_OCR_SLOWDOWN_RATIO} - {MAX_OCR_SLOWDOWN_RATIO}")

    # Get input fixture
    try:
        input_pdf = get_fixture("scanned-document.pdf")
    except FileNotFoundError as e:
        pytest.skip(f"Required fixture not found: {e}")

    # Create mode-specific output directory
    mode_output_dir = tmp_output_dir / f"ocr-{ocr_mode}"
    mode_output_dir.mkdir(parents=True, exist_ok=True)

    # Run conversion with timing
    result = run_conversion_with_timing(cli_runner, input_pdf, mode_output_dir, ocr_mode)

    # Validate conversion succeeded
    if result["exit_code"] != 0:
        save_debug_info(mode_output_dir, result)
        pytest.fail(
            f"CLI conversion failed with exit code {result['exit_code']}. "
            f"Command: pdf2foundry convert {input_pdf} --ocr {ocr_mode}. "
            f"Error: {result['stderr']}"
        )

    # Collect artifacts and analyze content
    artifacts = collect_artifacts(mode_output_dir / f"test-scan-{ocr_mode}")

    # Validate content characteristics based on mode
    validate_content_by_mode(ocr_mode, artifacts, expected_tokens)

    # Store timing data for cross-mode comparison
    store_timing_data(tmp_output_dir, ocr_mode, result["duration_s"])

    print(f"✓ OCR mode '{ocr_mode}' test completed successfully")
    print(f"  - Text length: {artifacts['text_length']} chars")
    print(f"  - Image count: {artifacts['image_count']}")
    print(f"  - Duration: {result['duration_s']:.2f}s")


@pytest.mark.e2e
@pytest.mark.ocr
@pytest.mark.tier2
def test_ocr_timing_comparison(tmp_output_dir: Path) -> None:
    """
    Compare timing across OCR modes after all parametrized tests complete.

    This test runs after the parametrized tests and validates that:
    - OCR-enabled modes are slower than 'off' mode
    - Timing ratios are within reasonable bounds

    Args:
        tmp_output_dir: Temporary directory containing timing data
    """
    # Load timing data from parametrized tests
    timing_data = load_timing_data(tmp_output_dir)

    if not timing_data:
        pytest.skip("No timing data available - parametrized tests may not have run")

    # Validate we have all required modes
    required_modes = {"off", "on", "auto"}
    available_modes = set(timing_data.keys())
    missing_modes = required_modes - available_modes

    if missing_modes:
        pytest.skip(f"Missing timing data for modes: {missing_modes}")

    base_off = timing_data["off"]
    on_duration = timing_data["on"]
    auto_duration = timing_data["auto"]

    # Compute ratios
    on_ratio = on_duration / base_off if base_off > 0 else float("inf")
    auto_ratio = auto_duration / base_off if base_off > 0 else float("inf")

    print("\n=== OCR Timing Analysis ===")
    print(f"Off mode: {base_off:.2f}s")
    print(f"On mode: {on_duration:.2f}s (ratio: {on_ratio:.2f}x)")
    print(f"Auto mode: {auto_duration:.2f}s (ratio: {auto_ratio:.2f}x)")

    # Validate timing constraints
    validate_timing_ratios(base_off, on_ratio, auto_ratio)

    print("✓ OCR timing validation passed")


@pytest.mark.e2e
@pytest.mark.ocr
@pytest.mark.tier2
def test_ocr_tesseract_unavailable(tmp_output_dir: Path, cli_runner, monkeypatch) -> None:
    """
    Test behavior when Tesseract is unavailable.

    This test simulates missing Tesseract by mocking shutil.which and validates:
    - --ocr on: fails with clear error message
    - --ocr auto: falls back gracefully with warning

    Args:
        tmp_output_dir: Temporary directory for test output
        cli_runner: CLI runner function
        monkeypatch: Pytest monkeypatch fixture
    """
    # Get input fixture
    try:
        input_pdf = get_fixture("scanned-document.pdf")
    except FileNotFoundError as e:
        pytest.skip(f"Required fixture not found: {e}")

    # Simulate missing Tesseract by mocking shutil.which for tesseract only
    original_which = shutil.which

    def mock_which(cmd):
        if cmd == "tesseract":
            return None
        return original_which(cmd)

    monkeypatch.setattr(shutil, "which", mock_which)

    # Test --ocr on (should succeed but with warnings about missing Tesseract)
    on_output_dir = tmp_output_dir / "ocr-on-no-tesseract"
    on_output_dir.mkdir(parents=True, exist_ok=True)

    result_on = run_conversion_with_timing(cli_runner, input_pdf, on_output_dir, "on")

    # Should succeed but with warnings about OCR being unavailable
    assert result_on["exit_code"] == 0, (
        f"Expected success with --ocr on when Tesseract unavailable (graceful degradation). "
        f"Exit code: {result_on['exit_code']}, Error: {result_on['stderr']}"
    )

    # Should mention OCR or Tesseract in output (warnings)
    stdout = result_on["stdout"] or ""
    stderr = result_on["stderr"] or ""
    output_text = (stdout + stderr).lower()
    assert any(
        keyword in output_text for keyword in ["tesseract", "ocr"]
    ), f"Output should mention Tesseract or OCR warnings. Got stdout: {stdout}, stderr: {stderr}"

    # Should behave like 'off' mode (low text, images present)
    artifacts_on = collect_artifacts(on_output_dir / "test-scan-on")
    assert (
        artifacts_on["text_length"] <= MAX_CHARS_NO_OCR
    ), f"Expected low text content when OCR unavailable. Got {artifacts_on['text_length']} chars"
    assert artifacts_on["image_count"] >= 1, "Expected images when OCR unavailable"

    # Test --ocr auto (should succeed with fallback)
    auto_output_dir = tmp_output_dir / "ocr-auto-no-tesseract"
    auto_output_dir.mkdir(parents=True, exist_ok=True)

    result_auto = run_conversion_with_timing(cli_runner, input_pdf, auto_output_dir, "auto")

    # Should succeed but with warning about OCR being disabled
    assert result_auto["exit_code"] == 0, (
        f"Expected success with --ocr auto when Tesseract unavailable. "
        f"Exit code: {result_auto['exit_code']}, Error: {result_auto['stderr']}"
    )

    # Should behave like 'off' mode (low text, images present)
    artifacts = collect_artifacts(auto_output_dir / "test-scan-auto")
    assert (
        artifacts["text_length"] <= MAX_CHARS_NO_OCR
    ), f"Expected low text content when OCR unavailable. Got {artifacts['text_length']} chars"
    assert artifacts["image_count"] >= 1, "Expected images when OCR unavailable"

    print("✓ Tesseract unavailable handling validated")
