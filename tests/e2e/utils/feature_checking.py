"""Feature availability checking utilities for tests.

This module provides utilities for checking feature availability in test
environments, enabling proper test skipping and conditional execution.
"""

import os
import shutil
import subprocess

import pytest


def check_ml_availability() -> tuple[bool, str | None]:
    """
    Check if ML features are available.

    Returns:
        Tuple of (is_available, reason_if_not)
    """
    # Check if ML is explicitly disabled
    if os.getenv("PDF2FOUNDRY_NO_ML") == "1":
        return False, "ML features disabled via --no-ml flag"

    # Check if in CI minimal environment
    if os.getenv("PDF2FOUNDRY_CI_MINIMAL") == "1":
        return False, "Running in CI minimal environment"

    # Check for required ML dependencies
    try:
        import transformers  # noqa: F401
    except ImportError:
        return False, "transformers library not available"

    try:
        import torch  # noqa: F401
    except ImportError:
        return False, "torch library not available"

    try:
        import huggingface_hub  # noqa: F401
    except ImportError:
        return False, "huggingface_hub library not available"

    return True, None


def check_ocr_availability() -> tuple[bool, str | None]:
    """
    Check if OCR features are available.

    Returns:
        Tuple of (is_available, reason_if_not)
    """
    # Check if tesseract binary is available
    if not shutil.which("tesseract"):
        return False, "tesseract binary not found in PATH"

    # Check if pytesseract is available
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False, "pytesseract library not available"

    return True, None


def check_models_cached() -> tuple[bool, str | None]:
    """
    Check if required ML models are cached.

    Returns:
        Tuple of (is_cached, reason_if_not)
    """
    try:
        from huggingface_hub import try_to_load_from_cache

        from pdf2foundry.models.registry import get_default_vlm_model

        model_id = get_default_vlm_model()
        cached_path = try_to_load_from_cache(repo_id=model_id, filename="config.json")

        if cached_path is None:
            return False, f"Model {model_id} not cached locally"

        return True, None

    except ImportError as e:
        return False, f"Model registry not available: {e}"
    except Exception as e:
        return False, f"Error checking model cache: {e}"


def check_cli_availability() -> tuple[bool, str | None]:
    """
    Check if PDF2Foundry CLI is available.

    Returns:
        Tuple of (is_available, reason_if_not)
    """
    cli_binary = os.getenv("PDF2FOUNDRY_CLI", "pdf2foundry")

    if not shutil.which(cli_binary):
        return False, f"CLI binary '{cli_binary}' not found in PATH"

    # Test that CLI responds to --version
    try:
        result = subprocess.run([cli_binary, "--version"], capture_output=True, text=True, timeout=10, check=False)

        if result.returncode != 0:
            return False, f"CLI version check failed with exit code {result.returncode}"

        return True, None

    except subprocess.TimeoutExpired:
        return False, "CLI version check timed out"
    except Exception as e:
        return False, f"CLI version check failed: {e}"


def check_test_fixtures() -> tuple[bool, list[str]]:
    """
    Check if required test fixtures are available.

    Returns:
        Tuple of (all_available, list_of_missing_fixtures)
    """
    from pathlib import Path

    fixtures_dir = Path(__file__).parent.parent / "fixtures"

    if not fixtures_dir.exists():
        return False, [f"Fixtures directory not found: {fixtures_dir}"]

    required_fixtures = [
        "basic.pdf",
        "comprehensive-manual.pdf",
        "illustrated-guide.pdf",
        "data-manual.pdf",
        "manifest.json",
    ]

    missing_fixtures = []
    for fixture in required_fixtures:
        if not (fixtures_dir / fixture).exists():
            missing_fixtures.append(fixture)

    return len(missing_fixtures) == 0, missing_fixtures


def get_feature_availability_summary() -> dict[str, dict[str, any]]:
    """
    Get a comprehensive summary of feature availability.

    Returns:
        Dictionary with feature availability status and reasons
    """
    summary = {}

    # Check ML availability
    ml_available, ml_reason = check_ml_availability()
    summary["ml"] = {
        "available": ml_available,
        "reason": ml_reason,
    }

    # Check OCR availability
    ocr_available, ocr_reason = check_ocr_availability()
    summary["ocr"] = {
        "available": ocr_available,
        "reason": ocr_reason,
    }

    # Check model caching
    models_cached, cache_reason = check_models_cached()
    summary["models_cached"] = {
        "available": models_cached,
        "reason": cache_reason,
    }

    # Check CLI availability
    cli_available, cli_reason = check_cli_availability()
    summary["cli"] = {
        "available": cli_available,
        "reason": cli_reason,
    }

    # Check test fixtures
    fixtures_available, missing_fixtures = check_test_fixtures()
    summary["fixtures"] = {
        "available": fixtures_available,
        "reason": f"Missing fixtures: {missing_fixtures}" if missing_fixtures else None,
    }

    return summary


# Pytest skip decorators for common feature requirements
def skip_if_no_ml(reason: str | None = None):
    """Skip test if ML features are not available."""
    ml_available, ml_reason = check_ml_availability()
    skip_reason = reason or ml_reason or "ML features not available"
    return pytest.mark.skipif(not ml_available, reason=skip_reason)


def skip_if_no_ocr(reason: str | None = None):
    """Skip test if OCR features are not available."""
    ocr_available, ocr_reason = check_ocr_availability()
    skip_reason = reason or ocr_reason or "OCR features not available"
    return pytest.mark.skipif(not ocr_available, reason=skip_reason)


def skip_if_models_not_cached(reason: str | None = None):
    """Skip test if ML models are not cached."""
    models_cached, cache_reason = check_models_cached()
    skip_reason = reason or cache_reason or "ML models not cached"
    return pytest.mark.skipif(not models_cached, reason=skip_reason)


def skip_if_no_cli(reason: str | None = None):
    """Skip test if CLI is not available."""
    cli_available, cli_reason = check_cli_availability()
    skip_reason = reason or cli_reason or "CLI not available"
    return pytest.mark.skipif(not cli_available, reason=skip_reason)


def skip_if_missing_fixtures(reason: str | None = None):
    """Skip test if required fixtures are missing."""
    fixtures_available, missing_fixtures = check_test_fixtures()
    skip_reason = reason or f"Missing fixtures: {missing_fixtures}" if missing_fixtures else "Fixtures not available"
    return pytest.mark.skipif(not fixtures_available, reason=skip_reason)


# Conditional skip for CI environments
def skip_in_ci_minimal(reason: str | None = None):
    """Skip test in CI minimal environments."""
    is_ci_minimal = os.getenv("PDF2FOUNDRY_CI_MINIMAL") == "1"
    skip_reason = reason or "Skipped in CI minimal environment"
    return pytest.mark.skipif(is_ci_minimal, reason=skip_reason)


def skip_in_ci(reason: str | None = None):
    """Skip test in any CI environment."""
    is_ci = os.getenv("CI") == "1"
    skip_reason = reason or "Skipped in CI environment"
    return pytest.mark.skipif(is_ci, reason=skip_reason)


# Combination decorators for common patterns
def require_full_environment(reason: str | None = None):
    """Require full environment (ML + OCR + CLI + fixtures)."""

    def decorator(func):
        # Apply multiple skip conditions
        func = skip_if_no_ml(reason)(func)
        func = skip_if_no_ocr(reason)(func)
        func = skip_if_no_cli(reason)(func)
        func = skip_if_missing_fixtures(reason)(func)
        return func

    return decorator


def require_ml_with_cached_models(reason: str | None = None):
    """Require ML features with cached models."""

    def decorator(func):
        func = skip_if_no_ml(reason)(func)
        func = skip_if_models_not_cached(reason)(func)
        return func

    return decorator


# Pytest fixtures for feature availability
@pytest.fixture
def feature_availability():
    """Fixture providing feature availability summary."""
    return get_feature_availability_summary()


@pytest.fixture
def ml_available():
    """Fixture providing ML availability status."""
    available, _ = check_ml_availability()
    return available


@pytest.fixture
def ocr_available():
    """Fixture providing OCR availability status."""
    available, _ = check_ocr_availability()
    return available


@pytest.fixture
def cli_available():
    """Fixture providing CLI availability status."""
    available, _ = check_cli_availability()
    return available


@pytest.fixture
def fixtures_available():
    """Fixture providing fixtures availability status."""
    available, _ = check_test_fixtures()
    return available


# Helper functions for test assertions
def assert_ml_available():
    """Assert that ML features are available, with helpful error message."""
    available, reason = check_ml_availability()
    if not available:
        pytest.fail(f"ML features required but not available: {reason}")


def assert_ocr_available():
    """Assert that OCR features are available, with helpful error message."""
    available, reason = check_ocr_availability()
    if not available:
        pytest.fail(f"OCR features required but not available: {reason}")


def assert_models_cached():
    """Assert that ML models are cached, with helpful error message."""
    cached, reason = check_models_cached()
    if not cached:
        pytest.fail(f"ML models required but not cached: {reason}")


def assert_cli_available():
    """Assert that CLI is available, with helpful error message."""
    available, reason = check_cli_availability()
    if not available:
        pytest.fail(f"CLI required but not available: {reason}")


def assert_fixtures_available():
    """Assert that test fixtures are available, with helpful error message."""
    available, missing = check_test_fixtures()
    if not available:
        pytest.fail(f"Test fixtures required but missing: {missing}")


# Logging helper
def log_feature_availability():
    """Log feature availability status for debugging."""
    summary = get_feature_availability_summary()

    print("\n" + "=" * 50)
    print("FEATURE AVAILABILITY STATUS")
    print("=" * 50)

    for feature, status in summary.items():
        available = status["available"]
        reason = status["reason"]

        status_icon = "✅" if available else "❌"
        print(f"{status_icon} {feature.upper()}: {'Available' if available else 'Not Available'}")

        if reason:
            print(f"   Reason: {reason}")

    print("=" * 50 + "\n")
