"""E2E-005: AI Image Descriptions (VLM) Test.

This test validates Vision-Language Model integration for image captions using
microsoft/Florence-2-base, validating description quality and performance.
"""

import os
import sys
from pathlib import Path

import pytest

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.vlm_test_helpers import (
    assert_requirements,
    check_internet_connectivity,
    collect_captions_from_html,
    collect_captions_from_json,
    get_vlm_flags,
    run_cli,
    validate_caption_quality,
)

# Import fixtures from separate module
pytest_plugins = ["utils.vlm_fixtures"]


@pytest.mark.e2e
@pytest.mark.vlm
@pytest.mark.slow
def test_vlm_cache_warmup(
    test_fixture: Path,
    tmp_output_dir: Path,
    vlm_env: dict[str, str],
    hf_cache_dir: Path,
    request: pytest.FixtureRequest,
) -> None:
    """
    Warm up VLM model cache and verify successful model loading.

    This test runs a minimal conversion with captions enabled to trigger
    model download/load and stabilize subsequent timings. It xfails cleanly
    on offline or resource-constrained environments.

    Args:
        test_fixture: Selected PDF fixture for testing
        tmp_output_dir: Temporary output directory
        vlm_env: Environment variables for VLM testing
        hf_cache_dir: Hugging Face cache directory
    """
    # Check prerequisites
    assert_requirements()

    # Check internet connectivity for first-time model download
    has_internet = check_internet_connectivity()

    # Check if model is already cached
    model_cache_path = hf_cache_dir / "hub" / "models--Salesforce--blip-image-captioning-base"
    model_already_cached = model_cache_path.exists() and any(model_cache_path.iterdir())

    if not has_internet and not model_already_cached:
        pytest.xfail("No internet connection and model not cached - cannot download microsoft/Florence-2-base")

    # Run minimal conversion with VLM captions enabled
    mod_id = "test-vlm-warmup"

    cmd_args = [
        "convert",
        str(test_fixture),
        "--mod-id",
        mod_id,
        "--mod-title",
        "VLM Cache Warmup Test",
        "--out-dir",
        str(tmp_output_dir),
        "--pages",
        "1-2",  # Limit to first 2 pages for speed
        "--workers",
        "1",  # Single worker for predictable behavior
        "--no-toc",  # Disable TOC for simpler testing
        *get_vlm_flags(),
    ]

    print(f"Running cache warmup with fixture: {test_fixture.name}")
    print(f"Model cache path: {model_cache_path}")
    print(f"Model already cached: {model_already_cached}")
    print(f"Internet available: {has_internet}")

    # Increase timeout for potential model download (first run)
    timeout = 1200 if not model_already_cached else 600  # 20 min vs 10 min

    result = run_cli(cmd_args, env=vlm_env, timeout=timeout)

    # Handle common failure scenarios with informative xfail messages
    if result["exit_code"] != 0:
        stderr_output = result["stderr"] + result["stdout"]

        # Check for common failure patterns
        if any(
            pattern in stderr_output.lower() for pattern in ["connection", "timeout", "network", "403", "404", "502", "503"]
        ):
            pytest.xfail(f"Network/connectivity issue during model download: {stderr_output[:200]}...")

        if any(
            pattern in stderr_output.lower()
            for pattern in ["out of memory", "oom", "killed", "memory", "cuda out of memory"]
        ):
            pytest.xfail(
                f"Insufficient memory for VLM model loading. "
                f"Try reducing model size or increasing RAM: {stderr_output[:200]}..."
            )

        if "huggingface_hub" in stderr_output.lower() and "token" in stderr_output.lower():
            pytest.xfail(f"Hugging Face authentication issue. Set HF_TOKEN environment variable: {stderr_output[:200]}...")

        # Generic failure
        pytest.fail(f"VLM conversion failed with exit code {result['exit_code']}: {stderr_output[:500]}...")

    # Verify successful completion
    assert result["exit_code"] == 0, f"Conversion failed: {result['stdout']}"

    # Verify output directory structure exists
    module_dir = tmp_output_dir / mod_id
    assert module_dir.exists(), f"Module directory not created: {module_dir}"

    module_json = module_dir / "module.json"
    assert module_json.exists(), f"module.json not created: {module_json}"

    # Verify HF cache contains model artifacts
    assert model_cache_path.exists(), f"Model cache directory not created: {model_cache_path}"

    # Check for key model files (at least some should exist)
    model_files = list(model_cache_path.rglob("*"))
    assert len(model_files) > 0, f"No model files found in cache: {model_cache_path}"

    # Look for common model file patterns
    has_model_files = any(
        f.name in ["config.json", "pytorch_model.bin", "model.safetensors", "tokenizer.json"] for f in model_files
    )
    assert has_model_files, f"Expected model files not found in cache. Files: {[f.name for f in model_files[:10]]}"

    print(f"✅ Cache warmup successful in {result['duration_s']:.2f}s")
    print(f"✅ Model cached at: {model_cache_path}")
    print(f"✅ Found {len(model_files)} model files in cache")

    # Log model information if available in stdout
    stdout = result["stdout"]
    if "florence" in stdout.lower():
        print("✅ Florence model detected in output")

    # Record metrics for future reference
    request.node.user_properties.append(("warmup_duration_s", result["duration_s"]))
    request.node.user_properties.append(("model_cache_files", len(model_files)))
    request.node.user_properties.append(("model_was_cached", model_already_cached))


@pytest.mark.e2e
@pytest.mark.vlm
@pytest.mark.slow
def test_vlm_caption_validation(
    test_fixture: Path,
    tmp_output_dir: Path,
    vlm_env: dict[str, str],
    hf_cache_dir: Path,
    request: pytest.FixtureRequest,
) -> None:
    """
    Validate caption presence and quality after VLM processing.

    This test runs a conversion with captions enabled and validates:
    1. Images receive non-empty captions
    2. Caption quality meets basic heuristics (length, content)
    3. Captions are present in JSON and/or HTML output

    Args:
        test_fixture: Selected PDF fixture for testing
        tmp_output_dir: Temporary output directory
        vlm_env: Environment variables for VLM testing
        hf_cache_dir: Hugging Face cache directory
    """
    # Check prerequisites
    assert_requirements()

    # Check if model is cached (should be after warmup test)
    model_cache_path = hf_cache_dir / "hub" / "models--Salesforce--blip-image-captioning-base"
    model_cached = model_cache_path.exists() and any(model_cache_path.iterdir())

    if not model_cached and not check_internet_connectivity():
        pytest.xfail("Model not cached and no internet - cannot run caption validation")

    # Run conversion with VLM captions enabled
    mod_id = "test-vlm-validation"

    cmd_args = [
        "convert",
        str(test_fixture),
        "--mod-id",
        mod_id,
        "--mod-title",
        "VLM Caption Validation Test",
        "--out-dir",
        str(tmp_output_dir),
        "--pages",
        "1-3",  # Process a few pages for better coverage
        "--workers",
        "1",  # Single worker for predictable behavior
        "--no-toc",  # Disable TOC for simpler testing
        *get_vlm_flags(),
    ]

    print(f"Running caption validation with fixture: {test_fixture.name}")

    result = run_cli(cmd_args, env=vlm_env, timeout=600)

    # Handle VLM-specific failures gracefully
    if result["exit_code"] != 0:
        error_output = result["stdout"] + result.get("stderr", "")

        # Check for common VLM failure patterns
        if any(
            pattern in error_output.lower()
            for pattern in [
                "cannot find the requested files in the local cache",
                "connection error",
                "authentication",
                "access denied",
                "rate limit",
                "model not found",
            ]
        ):
            pytest.skip(f"VLM model access failed (likely auth/network issue): {error_output[:200]}...")

        # For other failures, still fail the test
        pytest.fail(f"VLM conversion failed with exit code {result['exit_code']}: {error_output[:500]}...")

    module_dir = tmp_output_dir / mod_id
    assert module_dir.exists(), f"Module directory not created: {module_dir}"

    # Collect captions from JSON artifacts
    json_captions = collect_captions_from_json(module_dir)
    print(f"Found {len(json_captions)} images in JSON artifacts")

    # Collect captions from HTML files
    html_captions = collect_captions_from_html(module_dir)
    print(f"Found {len(html_captions)} images in HTML files")

    # Combine all caption sources
    all_captions = json_captions + html_captions

    if not all_captions:
        pytest.skip("No images found in output - cannot validate captions")

    # Validate caption presence and quality
    captioned_images = []
    quality_results = []

    for img_info in all_captions:
        caption = img_info.get("caption") or img_info.get("alt_text")

        if caption and caption.strip():
            captioned_images.append(img_info)

            # Validate caption quality
            is_valid, reason = validate_caption_quality(caption)
            quality_results.append(
                {
                    "image": img_info["name"] or img_info["src"],
                    "caption": caption,
                    "is_valid": is_valid,
                    "reason": reason,
                    "length": len(caption.strip()),
                    "source": img_info["source_type"],
                }
            )

            print(f"Caption for {img_info['name']}: '{caption[:50]}...' (valid: {is_valid}, reason: {reason})")

    # Aggregate validation results
    total_images = len(all_captions)
    captioned_count = len(captioned_images)
    valid_captions = [r for r in quality_results if r["is_valid"]]

    print("\n=== Caption Validation Results ===")
    print(f"Total images found: {total_images}")
    print(f"Images with captions: {captioned_count}")
    print(f"Valid captions: {len(valid_captions)}")

    # Assertions based on task requirements

    # 1. At least 1 image should have a non-empty caption
    assert captioned_count > 0, f"No images have captions. Found {total_images} images total."

    # 2. If multiple images, require >=80% to have non-empty captions
    if total_images > 1:
        caption_rate = captioned_count / total_images
        assert caption_rate >= 0.8, (
            f"Caption rate {caption_rate:.1%} < 80%. " f"Only {captioned_count}/{total_images} images have captions."
        )

    # 3. Quality validation: all captions should pass basic heuristics
    failed_quality = [r for r in quality_results if not r["is_valid"]]
    if failed_quality:
        print("\n=== Quality Failures ===")
        for failure in failed_quality[:5]:  # Show first 5 failures
            print(f"  {failure['image']}: {failure['reason']} ('{failure['caption'][:30]}...')")

    # Allow some quality failures in non-strict mode
    vlm_strict = os.getenv("VLM_STRICT", "0") == "1"
    if vlm_strict:
        assert len(failed_quality) == 0, f"{len(failed_quality)} captions failed quality checks in strict mode"
    else:
        # In non-strict mode, allow up to 20% quality failures
        if quality_results:
            failure_rate = len(failed_quality) / len(quality_results)
            assert failure_rate <= 0.2, (
                f"Quality failure rate {failure_rate:.1%} > 20%. "
                f"{len(failed_quality)}/{len(quality_results)} captions failed quality checks."
            )

    # Record metrics for analysis
    request.node.user_properties.append(("total_images", total_images))
    request.node.user_properties.append(("captioned_images", captioned_count))
    request.node.user_properties.append(("caption_rate", captioned_count / total_images if total_images > 0 else 0))
    request.node.user_properties.append(("valid_captions", len(valid_captions)))
    request.node.user_properties.append(
        ("quality_rate", len(valid_captions) / len(quality_results) if quality_results else 0)
    )
    request.node.user_properties.append(("vlm_strict_mode", vlm_strict))

    # Log sample captions for debugging
    if valid_captions:
        print("\n=== Sample Valid Captions ===")
        for i, result in enumerate(valid_captions[:3]):
            print(f"  {i+1}. {result['image']}: '{result['caption']}'")

    print(
        f"✅ Caption validation successful: {captioned_count}/{total_images} images captioned, "
        f"{len(valid_captions)} valid"
    )


@pytest.mark.e2e
@pytest.mark.vlm
@pytest.mark.perf
@pytest.mark.slow
def test_vlm_performance_comparison(
    test_fixture: Path,
    tmp_output_dir: Path,
    vlm_env: dict[str, str],
    hf_cache_dir: Path,
    request: pytest.FixtureRequest,
) -> None:
    """Compare performance of conversions with captions enabled vs disabled."""
    # Check prerequisites
    assert_requirements()

    # Check if model is cached (should be after warmup test)
    model_cache_path = hf_cache_dir / "hub" / "models--Salesforce--blip-image-captioning-base"
    model_cached = model_cache_path.exists() and any(model_cache_path.iterdir())

    if not model_cached and not check_internet_connectivity():
        pytest.xfail("Model not cached and no internet - cannot run performance comparison")

    # Get performance threshold from environment
    perf_threshold = float(os.getenv("PERF_THRESHOLD", "4.0"))

    print(f"Running performance comparison with fixture: {test_fixture.name}")
    print(f"Performance threshold: {perf_threshold}x")

    # Common command arguments (same pages, workers, etc.)
    base_args = [
        "convert",
        str(test_fixture),
        "--mod-title",
        "VLM Performance Test",
        "--out-dir",
        str(tmp_output_dir),
        "--pages",
        "1-2",  # Use same pages as warmup for consistency
        "--workers",
        "1",  # Single worker for predictable behavior
        "--no-toc",  # Disable TOC for simpler testing
    ]

    # Test A: Baseline without captions
    print("\n=== Running baseline conversion (no captions) ===")
    baseline_mod_id = "test-vlm-perf-baseline"
    baseline_args = [
        *base_args,
        "--mod-id",
        baseline_mod_id,
        "--picture-descriptions",
        "off",  # Explicitly disable captions
    ]

    baseline_result = run_cli(baseline_args, env=vlm_env, timeout=300)

    if baseline_result["exit_code"] != 0:
        pytest.fail(
            f"Baseline conversion failed with exit code {baseline_result['exit_code']}: "
            f"{baseline_result['stdout'][:500]}..."
        )

    duration_disabled = baseline_result["duration_s"]
    print(f"✅ Baseline conversion completed in {duration_disabled:.2f}s")

    # Test B: With captions enabled (cache should be warm)
    print("\n=== Running caption-enabled conversion ===")
    captions_mod_id = "test-vlm-perf-captions"
    captions_args = [
        *base_args,
        "--mod-id",
        captions_mod_id,
        *get_vlm_flags(),
    ]

    captions_result = run_cli(captions_args, env=vlm_env, timeout=600)

    if captions_result["exit_code"] != 0:
        pytest.fail(
            f"Captions conversion failed with exit code {captions_result['exit_code']}: "
            f"{captions_result['stdout'][:500]}..."
        )

    duration_enabled = captions_result["duration_s"]
    print(f"✅ Captions conversion completed in {duration_enabled:.2f}s")

    # Calculate performance metrics
    slowdown_ratio = duration_enabled / duration_disabled if duration_disabled > 0 else float("inf")

    print("\n=== Performance Comparison Results ===")
    print(f"Baseline (no captions): {duration_disabled:.2f}s")
    print(f"With captions: {duration_enabled:.2f}s")
    print(f"Slowdown ratio: {slowdown_ratio:.2f}x")
    print(f"Threshold: {perf_threshold:.2f}x")

    # Performance assertions

    # 1. Captions should be slower than baseline (sanity check)
    assert duration_enabled > duration_disabled, (
        f"Captions conversion ({duration_enabled:.2f}s) should be slower than "
        f"baseline ({duration_disabled:.2f}s). This suggests captions are not actually being processed."
    )

    # 2. Slowdown should be within acceptable bounds
    assert slowdown_ratio < perf_threshold, (
        f"Captions slowdown ratio {slowdown_ratio:.2f}x exceeds threshold {perf_threshold:.2f}x. "
        f"Caption processing may be too slow or inefficient."
    )

    # 3. Sanity check: slowdown should be at least 1.1x (10% slower)
    min_slowdown = 1.1
    assert slowdown_ratio >= min_slowdown, (
        f"Captions slowdown ratio {slowdown_ratio:.2f}x is suspiciously low (< {min_slowdown:.1f}x). "
        f"This suggests captions may not be actually processed."
    )

    # Verify both conversions produced valid output
    baseline_dir = tmp_output_dir / baseline_mod_id
    captions_dir = tmp_output_dir / captions_mod_id

    assert baseline_dir.exists(), f"Baseline output directory not created: {baseline_dir}"
    assert captions_dir.exists(), f"Captions output directory not created: {captions_dir}"

    baseline_module_json = baseline_dir / "module.json"
    captions_module_json = captions_dir / "module.json"

    assert baseline_module_json.exists(), f"Baseline module.json not created: {baseline_module_json}"
    assert captions_module_json.exists(), f"Captions module.json not created: {captions_module_json}"

    # Record detailed metrics for analysis
    request.node.user_properties.append(("duration_disabled_s", duration_disabled))
    request.node.user_properties.append(("duration_enabled_s", duration_enabled))
    request.node.user_properties.append(("slowdown_ratio", slowdown_ratio))
    request.node.user_properties.append(("perf_threshold", perf_threshold))
    request.node.user_properties.append(("model_was_cached", model_cached))
    request.node.user_properties.append(("fixture_used", test_fixture.name))

    # Additional diagnostics
    if slowdown_ratio > perf_threshold * 0.8:  # Warn if close to threshold
        print(f"⚠️  Performance warning: slowdown ratio {slowdown_ratio:.2f}x is close to threshold {perf_threshold:.2f}x")

    if slowdown_ratio < 1.5:  # Warn if suspiciously fast
        print(
            f"⚠️  Performance note: slowdown ratio {slowdown_ratio:.2f}x is quite low - "
            f"verify captions are being processed"
        )

    print(f"✅ Performance comparison successful: {slowdown_ratio:.2f}x slowdown within {perf_threshold:.2f}x threshold")
