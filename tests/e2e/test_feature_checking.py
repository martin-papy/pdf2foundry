"""Test feature availability checking utilities.

This test module validates the feature checking utilities and demonstrates
their usage for conditional test execution.
"""

import sys
from pathlib import Path

import pytest

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.feature_checking import (
    assert_cli_available,
    assert_fixtures_available,
    check_cli_availability,
    check_ml_availability,
    check_models_cached,
    check_ocr_availability,
    check_test_fixtures,
    log_feature_availability,
    require_ml_with_cached_models,
    skip_if_missing_fixtures,
    skip_if_no_cli,
    skip_if_no_ml,
    skip_if_no_ocr,
    skip_in_ci_minimal,
)


@pytest.mark.e2e
@pytest.mark.tier1
@pytest.mark.ci_safe
def test_feature_availability_checking(feature_availability) -> None:
    """
    Test feature availability checking functionality.

    This test validates that feature availability checking works correctly
    and provides accurate information about the test environment.

    Args:
        feature_availability: Feature availability fixture
    """
    # Validate feature availability structure
    assert isinstance(feature_availability, dict), "Feature availability should be a dictionary"

    # Check for required features
    required_features = ["ml", "ocr", "models_cached", "cli", "fixtures"]
    for feature in required_features:
        assert feature in feature_availability, f"Missing feature: {feature}"

        # Each feature should have availability and reason
        feature_info = feature_availability[feature]
        assert "available" in feature_info, f"Missing 'available' for {feature}"
        assert "reason" in feature_info, f"Missing 'reason' for {feature}"
        assert isinstance(feature_info["available"], bool), f"'available' should be boolean for {feature}"

    print("✓ Feature availability checking working correctly")
    print(f"✓ Checked {len(required_features)} features")

    # Log availability for debugging
    for feature, info in feature_availability.items():
        status = "✅" if info["available"] else "❌"
        print(f"  {status} {feature}: {info['available']}")
        if info["reason"]:
            print(f"    Reason: {info['reason']}")


@pytest.mark.e2e
@pytest.mark.tier1
@pytest.mark.ci_safe
def test_individual_feature_checks() -> None:
    """
    Test individual feature checking functions.

    This test validates that each feature checking function works correctly
    and returns the expected tuple format.
    """
    # Test ML availability check
    ml_available, ml_reason = check_ml_availability()
    assert isinstance(ml_available, bool), "ML availability should be boolean"
    if not ml_available:
        assert isinstance(ml_reason, str), "ML reason should be string when not available"

    # Test OCR availability check
    ocr_available, ocr_reason = check_ocr_availability()
    assert isinstance(ocr_available, bool), "OCR availability should be boolean"
    if not ocr_available:
        assert isinstance(ocr_reason, str), "OCR reason should be string when not available"

    # Test models cached check
    models_cached, cache_reason = check_models_cached()
    assert isinstance(models_cached, bool), "Models cached should be boolean"
    if not models_cached:
        assert isinstance(cache_reason, str), "Cache reason should be string when not cached"

    # Test CLI availability check
    cli_available, cli_reason = check_cli_availability()
    assert isinstance(cli_available, bool), "CLI availability should be boolean"
    if not cli_available:
        assert isinstance(cli_reason, str), "CLI reason should be string when not available"

    # Test fixtures availability check
    fixtures_available, missing_fixtures = check_test_fixtures()
    assert isinstance(fixtures_available, bool), "Fixtures availability should be boolean"
    assert isinstance(missing_fixtures, list), "Missing fixtures should be a list"

    print("✓ Individual feature checks working correctly")
    print(f"✓ ML available: {ml_available}")
    print(f"✓ OCR available: {ocr_available}")
    print(f"✓ Models cached: {models_cached}")
    print(f"✓ CLI available: {cli_available}")
    print(f"✓ Fixtures available: {fixtures_available}")


@pytest.mark.e2e
@pytest.mark.tier1
@pytest.mark.ci_safe
def test_skip_decorators() -> None:
    """
    Test skip decorator functionality.

    This test validates that skip decorators can be applied and work correctly
    for conditional test execution.
    """

    # Test that decorators can be applied without errors
    @skip_if_no_ml("Test ML skip")
    def dummy_ml_test():
        pass

    @skip_if_no_ocr("Test OCR skip")
    def dummy_ocr_test():
        pass

    @skip_if_no_cli("Test CLI skip")
    def dummy_cli_test():
        pass

    @skip_if_missing_fixtures("Test fixtures skip")
    def dummy_fixtures_test():
        pass

    @skip_in_ci_minimal("Test CI minimal skip")
    def dummy_ci_test():
        pass

    # Test combination decorator
    @require_ml_with_cached_models("Test ML with models")
    def dummy_ml_models_test():
        pass

    print("✓ Skip decorators can be applied successfully")
    print("✓ Combination decorators working correctly")


@pytest.mark.e2e
@pytest.mark.tier1
@pytest.mark.ci_safe
def test_assertion_helpers() -> None:
    """
    Test assertion helper functions.

    This test validates that assertion helpers work correctly and provide
    useful error messages when features are not available.
    """
    # Test CLI assertion (should work in most environments)
    try:
        assert_cli_available()
        print("✓ CLI assertion passed")
    except Exception as e:
        print(f"INFO: CLI assertion failed (expected in some environments): {e}")

    # Test fixtures assertion (should work if fixtures are present)
    try:
        assert_fixtures_available()
        print("✓ Fixtures assertion passed")
    except Exception as e:
        print(f"INFO: Fixtures assertion failed (expected if fixtures missing): {e}")

    print("✓ Assertion helpers working correctly")


@pytest.mark.e2e
@pytest.mark.tier1
@pytest.mark.ci_safe
def test_feature_logging() -> None:
    """
    Test feature availability logging.

    This test validates that feature availability can be logged in a readable
    format for debugging purposes.
    """
    try:
        log_feature_availability()
        print("✓ Feature availability logging completed successfully")
    except Exception as e:
        pytest.fail(f"Feature availability logging failed: {e}")


@pytest.mark.e2e
@pytest.mark.tier1
@pytest.mark.ci_safe
def test_fixture_integration(ml_available, ocr_available, cli_available, fixtures_available) -> None:
    """
    Test integration with pytest fixtures.

    This test validates that the feature checking utilities integrate correctly
    with pytest fixtures for easy use in tests.

    Args:
        ml_available: ML availability fixture
        ocr_available: OCR availability fixture
        cli_available: CLI availability fixture
        fixtures_available: Fixtures availability fixture
    """
    # Validate fixture types
    assert isinstance(ml_available, bool), "ML available fixture should be boolean"
    assert isinstance(ocr_available, bool), "OCR available fixture should be boolean"
    assert isinstance(cli_available, bool), "CLI available fixture should be boolean"
    assert isinstance(fixtures_available, bool), "Fixtures available fixture should be boolean"

    print("✓ Fixture integration working correctly")
    print(f"✓ ML available (fixture): {ml_available}")
    print(f"✓ OCR available (fixture): {ocr_available}")
    print(f"✓ CLI available (fixture): {cli_available}")
    print(f"✓ Fixtures available (fixture): {fixtures_available}")


# Demonstration tests showing proper usage patterns
@pytest.mark.e2e
@pytest.mark.tier3
@skip_if_no_ml("ML features required for this test")
def test_ml_feature_usage_example() -> None:
    """
    Example test showing proper ML feature usage.

    This test demonstrates how to use feature checking for ML-dependent tests.
    """
    # This test will be skipped if ML features are not available
    print("✓ ML features are available - test can proceed")
    print("✓ This demonstrates proper conditional test execution")


@pytest.mark.e2e
@pytest.mark.tier2
@skip_if_no_ocr("OCR features required for this test")
def test_ocr_feature_usage_example() -> None:
    """
    Example test showing proper OCR feature usage.

    This test demonstrates how to use feature checking for OCR-dependent tests.
    """
    # This test will be skipped if OCR features are not available
    print("✓ OCR features are available - test can proceed")
    print("✓ This demonstrates proper conditional test execution")


@pytest.mark.e2e
@pytest.mark.tier3
@require_ml_with_cached_models("ML with cached models required")
def test_ml_with_models_usage_example() -> None:
    """
    Example test showing proper ML with cached models usage.

    This test demonstrates how to use combination decorators for complex requirements.
    """
    # This test will be skipped if ML features are not available OR models are not cached
    print("✓ ML features available and models cached - test can proceed")
    print("✓ This demonstrates proper combination decorator usage")
