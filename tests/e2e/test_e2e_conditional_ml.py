"""E2E: Conditional ML Tests with Proper Skipping.

This test module contains ML/VLM tests that run conditionally based on:
1. Model availability and caching status
2. Environment configuration (CI vs local)
3. Feature availability detection

These tests demonstrate proper skipping behavior for CI environments.
"""

import os
import sys
from pathlib import Path

import pytest

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.fixtures import get_fixture
from utils.validation import validate_module_json


def _models_cached() -> bool:
    """Check if BLIP model is cached locally."""
    try:
        from huggingface_hub import try_to_load_from_cache

        from pdf2foundry.models.registry import get_default_vlm_model

        model_id = get_default_vlm_model()
        cached_path = try_to_load_from_cache(repo_id=model_id, filename="config.json")
        return cached_path is not None
    except Exception:
        return False


@pytest.mark.e2e
@pytest.mark.tier3
@pytest.mark.requires_models
@pytest.mark.skipif(os.getenv("CI") == "1" and not _models_cached(), reason="Models not cached in CI")
def test_vlm_with_cached_models(tmp_output_dir: Path, cli_runner, models_cached: bool) -> None:
    """
    Test VLM functionality with pre-cached models.

    This test only runs if models are confirmed cached, demonstrating
    proper conditional execution for ML features in CI environments.

    Args:
        tmp_output_dir: Temporary output directory
        cli_runner: CLI runner function
        models_cached: Model caching status fixture
    """
    # Double-check that models are actually cached
    if not models_cached:
        pytest.skip("Models must be cached for this test")

    # Additional environment checks
    try:
        from pdf2foundry.core.feature_detection import FeatureAvailability

        if not FeatureAvailability.has_ml_support():
            pytest.skip("ML support not available in current environment")
    except ImportError:
        pytest.skip("Feature detection not available")

    # Get the default VLM model for testing
    try:
        from pdf2foundry.models.registry import get_default_vlm_model

        vlm_model = get_default_vlm_model()
    except ImportError:
        pytest.skip("Model registry not available")

    # Get input fixture
    try:
        input_pdf = get_fixture("basic.pdf")
    except FileNotFoundError as e:
        pytest.skip(f"Required fixture not found: {e}")

    # Execute CLI conversion with VLM enabled
    cmd_args = [
        "convert",
        str(input_pdf),
        "--mod-id",
        "test-vlm-cached",
        "--mod-title",
        "Test VLM with Cached Models",
        "--out-dir",
        str(tmp_output_dir),
        "--picture-descriptions",
        "on",
        "--vlm-repo-id",
        vlm_model,
    ]

    # Use longer timeout for ML operations but still reasonable for CI
    result = cli_runner(cmd_args, timeout=300)  # 5 minutes

    # Assert successful completion
    assert result.returncode == 0, f"VLM conversion failed: {result.stdout}"

    # Validate basic structure
    module_json_path = tmp_output_dir / "test-vlm-cached" / "module.json"
    assert module_json_path.exists(), f"module.json not found: {module_json_path}"

    validation_errors = validate_module_json(module_json_path)
    assert not validation_errors, f"module.json validation failed: {validation_errors}"

    print("✓ VLM test with cached models completed successfully")
    print(f"✓ Used model: {vlm_model}")
    print(f"✓ Models were cached: {models_cached}")


@pytest.mark.e2e
@pytest.mark.tier3
@pytest.mark.requires_models
@pytest.mark.skipif(os.getenv("PDF2FOUNDRY_CI_MINIMAL") == "1", reason="Skipped in CI minimal environment")
def test_ml_feature_detection(test_environment_info: dict) -> None:
    """
    Test ML feature detection and environment awareness.

    This test validates that the feature detection system correctly
    identifies ML capabilities and environment constraints.

    Args:
        test_environment_info: Environment information fixture
    """
    print(f"Environment info: {test_environment_info}")

    # Test feature availability detection
    try:
        from pdf2foundry.core.feature_detection import FeatureAvailability

        # Get feature status
        features = FeatureAvailability.get_available_features()

        # In a full environment, ML should be available
        if not test_environment_info.get("ci_minimal", False):
            assert features["ml"], "ML support should be available in full environment"

        # Log feature status for debugging
        FeatureAvailability.log_feature_status()

        print("✓ Feature detection working correctly")
        print(f"✓ ML support: {features['ml']}")
        print(f"✓ OCR support: {features['ocr']}")
        print(f"✓ CI minimal mode: {features['ci_minimal']}")

    except ImportError:
        pytest.skip("Feature detection module not available")


@pytest.mark.e2e
@pytest.mark.tier3
@pytest.mark.requires_models
@pytest.mark.skipif(
    condition=lambda: (os.getenv("CI") == "1" and os.getenv("PDF2FOUNDRY_CI_MINIMAL") == "1"),
    reason="Skipped in CI minimal environment",
)
def test_ml_graceful_degradation(tmp_output_dir: Path, cli_runner, monkeypatch) -> None:
    """
    Test graceful degradation when ML features are disabled.

    This test simulates ML unavailability and verifies that the system
    degrades gracefully without crashing.

    Args:
        tmp_output_dir: Temporary output directory
        cli_runner: CLI runner function
        monkeypatch: Pytest monkeypatch fixture for mocking
    """
    # Get input fixture
    try:
        input_pdf = get_fixture("basic.pdf")
    except FileNotFoundError as e:
        pytest.skip(f"Required fixture not found: {e}")

    # Mock ML unavailability by setting the no-ML environment variable
    monkeypatch.setenv("PDF2FOUNDRY_NO_ML", "1")

    # Execute CLI conversion - should work without ML
    cmd_args = [
        "convert",
        str(input_pdf),
        "--mod-id",
        "test-ml-degradation",
        "--mod-title",
        "Test ML Graceful Degradation",
        "--out-dir",
        str(tmp_output_dir),
        "--picture-descriptions",
        "auto",  # Should auto-disable due to no ML
    ]

    result = cli_runner(cmd_args, timeout=120)  # Should be fast without ML

    # Should succeed even without ML
    assert result.returncode == 0, f"Conversion should succeed without ML: {result.stdout}"

    # Validate basic structure
    module_json_path = tmp_output_dir / "test-ml-degradation" / "module.json"
    assert module_json_path.exists(), f"module.json not found: {module_json_path}"

    validation_errors = validate_module_json(module_json_path)
    assert not validation_errors, f"module.json validation failed: {validation_errors}"

    print("✓ Graceful degradation test completed successfully")
    print("✓ System handled ML unavailability gracefully")


@pytest.mark.e2e
@pytest.mark.tier2  # This is tier2 because it doesn't require actual ML models
@pytest.mark.ci_safe
def test_environment_detection_utilities(test_environment_info: dict) -> None:
    """
    Test environment detection utilities work correctly.

    This test validates that environment detection works in all environments
    and provides accurate information about feature availability.

    Args:
        test_environment_info: Environment information fixture
    """
    # Validate that we get expected environment information
    assert isinstance(test_environment_info, dict), "Environment info should be a dictionary"

    # Check required keys
    required_keys = ["ml", "ocr", "ci_minimal", "environment"]
    for key in required_keys:
        assert key in test_environment_info, f"Missing required key: {key}"

    # Validate environment sub-dictionary
    env_info = test_environment_info["environment"]
    assert isinstance(env_info, dict), "Environment sub-info should be a dictionary"
    assert "ci" in env_info, "Missing 'ci' in environment info"
    assert "ci_minimal" in env_info, "Missing 'ci_minimal' in environment info"

    # Log environment for debugging
    print("✓ Environment detection utilities working correctly")
    print(f"✓ Environment info: {test_environment_info}")

    # Test CI detection logic
    is_ci = os.getenv("CI") == "1"
    is_ci_minimal = os.getenv("PDF2FOUNDRY_CI_MINIMAL") == "1"

    assert env_info["ci"] == is_ci, f"CI detection mismatch: expected {is_ci}, got {env_info['ci']}"
    assert (
        env_info["ci_minimal"] == is_ci_minimal
    ), f"CI minimal detection mismatch: expected {is_ci_minimal}, got {env_info['ci_minimal']}"

    print(f"✓ CI environment: {is_ci}")
    print(f"✓ CI minimal environment: {is_ci_minimal}")


@pytest.mark.e2e
@pytest.mark.tier1  # This is tier1 because it's a basic diagnostic test
@pytest.mark.ci_safe
def test_model_caching_detection(models_cached: bool) -> None:
    """
    Test model caching detection works correctly.

    This test validates that the model caching detection utility
    correctly identifies whether models are cached locally.

    Args:
        models_cached: Model caching status fixture
    """
    # Test the fixture
    assert isinstance(models_cached, bool), "models_cached should be a boolean"

    # Test the underlying function directly
    from conftest import _models_cached

    direct_result = _models_cached()

    assert direct_result == models_cached, "Fixture and direct function should return same result"

    print("✓ Model caching detection working correctly")
    print(f"✓ Models cached: {models_cached}")

    # In CI environments, models might not be cached initially
    if os.getenv("CI") == "1":
        print("✓ Running in CI environment - model caching status may vary")
    else:
        print("✓ Running in local environment")
