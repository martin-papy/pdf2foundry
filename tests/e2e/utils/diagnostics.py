"""Test environment diagnostics utilities.

This module provides utilities for diagnosing test environment issues,
feature availability, and providing clear failure reasons for CI environments.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


def get_environment_diagnostics() -> dict[str, Any]:
    """
    Get comprehensive environment diagnostics for debugging test failures.

    Returns:
        Dictionary containing detailed environment information
    """
    diagnostics = {
        "system": _get_system_info(),
        "python": _get_python_info(),
        "environment_variables": _get_relevant_env_vars(),
        "feature_availability": _get_feature_availability(),
        "model_status": _get_model_status(),
        "dependencies": _get_dependency_status(),
        "cli_status": _get_cli_status(),
    }

    return diagnostics


def log_environment_diagnostics() -> None:
    """Log comprehensive environment diagnostics for debugging."""
    diagnostics = get_environment_diagnostics()

    print("\n" + "=" * 60)
    print("TEST ENVIRONMENT DIAGNOSTICS")
    print("=" * 60)

    for category, info in diagnostics.items():
        print(f"\n{category.upper().replace('_', ' ')}:")
        if isinstance(info, dict):
            for key, value in info.items():
                print(f"  {key}: {value}")
        elif isinstance(info, list):
            for item in info:
                print(f"  - {item}")
        else:
            print(f"  {info}")

    print("=" * 60 + "\n")


def diagnose_test_failure(test_name: str, error_message: str) -> str:
    """
    Provide diagnostic information for test failures.

    Args:
        test_name: Name of the failed test
        error_message: Error message from the test failure

    Returns:
        Diagnostic message with potential solutions
    """
    diagnostics = []

    # Check for common failure patterns
    if "timeout" in error_message.lower():
        diagnostics.extend(_diagnose_timeout_issues())

    if "model" in error_message.lower() or "transformers" in error_message.lower():
        diagnostics.extend(_diagnose_ml_issues())

    if "tesseract" in error_message.lower() or "ocr" in error_message.lower():
        diagnostics.extend(_diagnose_ocr_issues())

    if "fixture" in error_message.lower() or "not found" in error_message.lower():
        diagnostics.extend(_diagnose_fixture_issues())

    if "cli" in error_message.lower() or "pdf2foundry" in error_message.lower():
        diagnostics.extend(_diagnose_cli_issues())

    # General diagnostics if no specific pattern found
    if not diagnostics:
        diagnostics.extend(_diagnose_general_issues())

    diagnostic_text = f"\n🔍 DIAGNOSTIC INFORMATION FOR: {test_name}\n"
    diagnostic_text += f"Error: {error_message}\n\n"
    diagnostic_text += "Potential causes and solutions:\n"

    for i, diag in enumerate(diagnostics, 1):
        diagnostic_text += f"{i}. {diag}\n"

    return diagnostic_text


def check_test_prerequisites() -> list[str]:
    """
    Check test prerequisites and return list of issues found.

    Returns:
        List of prerequisite issues (empty if all good)
    """
    issues = []

    # Check CLI availability
    if not shutil.which("pdf2foundry"):
        issues.append("pdf2foundry CLI not found in PATH")

    # Check Python version
    if sys.version_info < (3, 12):  # noqa: UP036
        issues.append(f"Python 3.12+ required, found {sys.version_info.major}.{sys.version_info.minor}")

    # Check essential dependencies
    try:
        import typer  # noqa: F401
    except ImportError:
        issues.append("typer dependency not available")

    try:
        import pillow  # noqa: F401
    except ImportError:
        issues.append("pillow dependency not available")

    # Check test fixtures
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    if not fixtures_dir.exists():
        issues.append(f"Fixtures directory not found: {fixtures_dir}")
    else:
        required_fixtures = ["basic.pdf", "comprehensive-manual.pdf"]
        for fixture in required_fixtures:
            if not (fixtures_dir / fixture).exists():
                issues.append(f"Required fixture not found: {fixture}")

    return issues


def _get_system_info() -> dict[str, Any]:
    """Get system information."""
    import platform

    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }


def _get_python_info() -> dict[str, Any]:
    """Get Python environment information."""
    return {
        "version": sys.version,
        "executable": sys.executable,
        "path": sys.path[:3],  # First 3 entries
        "prefix": sys.prefix,
    }


def _get_relevant_env_vars() -> dict[str, str | None]:
    """Get relevant environment variables."""
    relevant_vars = [
        "CI",
        "PDF2FOUNDRY_CI_MINIMAL",
        "PDF2FOUNDRY_NO_ML",
        "PDF2FOUNDRY_TEST_MODE",
        "PDF2FOUNDRY_CACHE_DIR",
        "HF_HOME",
        "TRANSFORMERS_CACHE",
        "PATH",
    ]

    return {var: os.getenv(var) for var in relevant_vars}


def _get_feature_availability() -> dict[str, Any]:
    """Get feature availability information."""
    features = {}

    try:
        from pdf2foundry.core.feature_detection import FeatureAvailability

        features = FeatureAvailability.get_available_features()
    except ImportError:
        features["error"] = "Feature detection module not available"

    return features


def _get_model_status() -> dict[str, Any]:
    """Get ML model status information."""
    status = {}

    try:
        from pdf2foundry.models.registry import get_default_vlm_model, get_model_spec
        from tests.e2e.conftest import _models_cached

        model_id = get_default_vlm_model()
        model_spec = get_model_spec()
        models_cached = _models_cached()

        status.update(
            {
                "default_model": model_id,
                "model_size_mb": model_spec.size_mb,
                "models_cached": models_cached,
            }
        )

    except ImportError as e:
        status["error"] = f"Model registry not available: {e}"

    return status


def _get_dependency_status() -> dict[str, str]:
    """Get dependency availability status."""
    dependencies = {
        "transformers": "not_checked",
        "torch": "not_checked",
        "huggingface_hub": "not_checked",
        "pytesseract": "not_checked",
        "docling": "not_checked",
    }

    for dep in dependencies:
        try:
            __import__(dep)
            dependencies[dep] = "available"
        except ImportError:
            dependencies[dep] = "missing"

    return dependencies


def _get_cli_status() -> dict[str, Any]:
    """Get CLI status information."""
    status = {}

    cli_binary = shutil.which("pdf2foundry")
    status["binary_path"] = cli_binary
    status["binary_available"] = cli_binary is not None

    if cli_binary:
        try:
            result = subprocess.run([cli_binary, "--version"], capture_output=True, text=True, timeout=10)
            status["version_check"] = "success" if result.returncode == 0 else "failed"
            status["version_output"] = result.stdout.strip() if result.stdout else result.stderr.strip()
        except Exception as e:
            status["version_check"] = f"error: {e}"

    return status


def _diagnose_timeout_issues() -> list[str]:
    """Diagnose timeout-related issues."""
    return [
        "Check if running in CI minimal environment - use shorter timeouts",
        "Verify ML models are cached if test requires them",
        "Check if --no-ml flag should be used for CI-safe tests",
        "Ensure test is marked with appropriate tier (tier1 for fast tests)",
    ]


def _diagnose_ml_issues() -> list[str]:
    """Diagnose ML-related issues."""
    return [
        "Check if transformers and torch dependencies are installed",
        "Verify models are cached using 'models_cached' fixture",
        "Use @pytest.mark.skipif for conditional ML tests",
        "Consider using --no-ml flag for CI environments",
        "Check PDF2FOUNDRY_NO_ML environment variable",
    ]


def _diagnose_ocr_issues() -> list[str]:
    """Diagnose OCR-related issues."""
    return [
        "Check if tesseract is installed: 'sudo apt-get install tesseract-ocr'",
        "Verify pytesseract Python package is available",
        "Use skip_if_missing_binary('tesseract') in test setup",
        "Consider marking test with @pytest.mark.ocr",
    ]


def _diagnose_fixture_issues() -> list[str]:
    """Diagnose fixture-related issues."""
    return [
        "Check if test fixtures exist in tests/e2e/fixtures/",
        "Verify fixture manifest.json is present and valid",
        "Use get_fixture() helper function for fixture access",
        "Check if fixture paths are correct in test code",
    ]


def _diagnose_cli_issues() -> list[str]:
    """Diagnose CLI-related issues."""
    return [
        "Check if pdf2foundry is installed: 'pip install -e .'",
        "Verify CLI is in PATH or use PDF2FOUNDRY_CLI env var",
        "Check if virtual environment is activated",
        "Try running 'pdf2foundry --version' manually",
    ]


def _diagnose_general_issues() -> list[str]:
    """Diagnose general issues."""
    return [
        "Check test prerequisites using check_test_prerequisites()",
        "Review test environment diagnostics",
        "Verify all required dependencies are installed",
        "Check if test is marked with correct tier and markers",
        "Review test logs for more specific error information",
    ]


# Pytest plugin hooks for automatic diagnostics
def pytest_runtest_logreport(report):
    """Automatically log diagnostics for failed tests."""
    if report.when == "call" and report.outcome == "failed" and os.getenv("PDF2FOUNDRY_TEST_DIAGNOSTICS") == "1":
        diagnostic_info = diagnose_test_failure(report.nodeid, str(report.longrepr))
        print(diagnostic_info)


def pytest_configure(config):
    """Configure pytest with diagnostic markers."""
    config.addinivalue_line("markers", "diagnostics: enable automatic diagnostics for this test")


# Fixture for easy access to diagnostics in tests
@pytest.fixture
def environment_diagnostics():
    """Fixture providing environment diagnostics."""
    return get_environment_diagnostics()


@pytest.fixture
def test_prerequisites():
    """Fixture providing test prerequisite check results."""
    return check_test_prerequisites()
