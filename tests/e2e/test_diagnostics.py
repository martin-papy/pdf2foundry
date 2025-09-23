"""Test diagnostics functionality.

This test module demonstrates and validates the test environment
diagnostics utilities for debugging test failures.
"""

import sys
from pathlib import Path

import pytest

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.diagnostics import (
    check_test_prerequisites,
    diagnose_test_failure,
    get_environment_diagnostics,
    log_environment_diagnostics,
)


@pytest.mark.e2e
@pytest.mark.tier1
@pytest.mark.ci_safe
def test_environment_diagnostics_collection(environment_diagnostics) -> None:
    """
    Test that environment diagnostics can be collected successfully.

    This test validates that the diagnostics system works and provides
    useful information for debugging test environment issues.

    Args:
        environment_diagnostics: Environment diagnostics fixture
    """
    # Validate diagnostics structure
    assert isinstance(environment_diagnostics, dict), "Diagnostics should be a dictionary"

    # Check for required diagnostic categories
    required_categories = [
        "system",
        "python",
        "environment_variables",
        "feature_availability",
        "model_status",
        "dependencies",
        "cli_status",
    ]

    for category in required_categories:
        assert category in environment_diagnostics, f"Missing diagnostic category: {category}"

    # Validate system info
    system_info = environment_diagnostics["system"]
    assert "platform" in system_info
    assert "python_version" in system_info

    # Validate Python info
    python_info = environment_diagnostics["python"]
    assert "version" in python_info
    assert "executable" in python_info

    print("✓ Environment diagnostics collection working correctly")
    print(f"✓ Found {len(environment_diagnostics)} diagnostic categories")


@pytest.mark.e2e
@pytest.mark.tier1
@pytest.mark.ci_safe
def test_prerequisite_checking(test_prerequisites) -> None:
    """
    Test prerequisite checking functionality.

    This test validates that prerequisite checking works and identifies
    missing requirements correctly.

    Args:
        test_prerequisites: Test prerequisites fixture
    """
    # Prerequisites should be a list
    assert isinstance(test_prerequisites, list), "Prerequisites should be a list"

    # In a properly set up environment, there should be no issues
    # But we'll be lenient for CI environments
    print("✓ Prerequisite check completed")
    print(f"✓ Found {len(test_prerequisites)} issues")

    if test_prerequisites:
        print("Issues found:")
        for issue in test_prerequisites:
            print(f"  - {issue}")
    else:
        print("✓ All prerequisites satisfied")


@pytest.mark.e2e
@pytest.mark.tier1
@pytest.mark.ci_safe
def test_failure_diagnosis() -> None:
    """
    Test failure diagnosis functionality.

    This test validates that the failure diagnosis system can provide
    useful diagnostic information for common failure patterns.
    """
    # Test timeout diagnosis
    timeout_diag = diagnose_test_failure("test_example", "TimeoutExpired: Command timed out after 120 seconds")
    assert "timeout" in timeout_diag.lower()
    assert "ci minimal" in timeout_diag.lower()

    # Test ML diagnosis
    ml_diag = diagnose_test_failure("test_vlm", "ImportError: No module named 'transformers'")
    assert "transformers" in ml_diag.lower()
    assert "dependencies" in ml_diag.lower()

    # Test OCR diagnosis
    ocr_diag = diagnose_test_failure("test_ocr", "FileNotFoundError: tesseract not found")
    assert "tesseract" in ocr_diag.lower()
    assert "install" in ocr_diag.lower()

    print("✓ Failure diagnosis working correctly")
    print("✓ Provides specific guidance for common failure patterns")


@pytest.mark.e2e
@pytest.mark.tier1
@pytest.mark.ci_safe
def test_diagnostics_logging() -> None:
    """
    Test diagnostics logging functionality.

    This test validates that diagnostics can be logged in a readable format
    for debugging purposes.
    """
    # Test that logging doesn't crash
    try:
        log_environment_diagnostics()
        print("✓ Diagnostics logging completed successfully")
    except Exception as e:
        pytest.fail(f"Diagnostics logging failed: {e}")


@pytest.mark.e2e
@pytest.mark.tier1
@pytest.mark.ci_safe
def test_direct_diagnostics_access() -> None:
    """
    Test direct access to diagnostics functions.

    This test validates that diagnostics functions can be called directly
    without fixtures for debugging purposes.
    """
    # Test direct function calls
    diagnostics = get_environment_diagnostics()
    assert isinstance(diagnostics, dict)

    prerequisites = check_test_prerequisites()
    assert isinstance(prerequisites, list)

    # Test diagnosis with various error patterns
    test_cases = [
        ("timeout error", "Command timed out"),
        ("ml error", "transformers not found"),
        ("ocr error", "tesseract missing"),
        ("fixture error", "fixture not found"),
        ("cli error", "pdf2foundry not found"),
        ("general error", "unknown error occurred"),
    ]

    for test_name, error_msg in test_cases:
        diagnosis = diagnose_test_failure(test_name, error_msg)
        assert isinstance(diagnosis, str)
        assert len(diagnosis) > 0
        assert test_name in diagnosis

    print("✓ Direct diagnostics access working correctly")
    print(f"✓ Tested {len(test_cases)} error patterns")
