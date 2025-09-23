"""Environment detection utilities for performance testing."""

import os
import platform
from typing import Any

import psutil


def detect_environment() -> dict[str, Any]:
    """
    Detect the current execution environment and return characteristics.

    Returns:
        Dictionary with environment information including:
        - environment_type: 'ci', 'local', 'unknown'
        - cpu_count: Number of CPU cores
        - memory_gb: Total memory in GB
        - platform_info: Platform details
        - is_github_actions: Whether running in GitHub Actions
        - performance_tier: 'fast', 'medium', 'slow' based on hardware
    """
    # Detect if running in CI
    is_ci = os.getenv("CI") == "1"
    is_github_actions = os.getenv("GITHUB_ACTIONS") == "true"

    # Get hardware info
    cpu_count = psutil.cpu_count(logical=True)
    memory_bytes = psutil.virtual_memory().total
    memory_gb = memory_bytes / (1024**3)

    # Determine environment type
    if is_github_actions:
        environment_type = "github_actions"
    elif is_ci:
        environment_type = "ci_other"
    else:
        environment_type = "local"

    # Determine performance tier based on hardware
    if cpu_count >= 8 and memory_gb >= 16:
        performance_tier = "fast"
    elif cpu_count >= 4 and memory_gb >= 8:
        performance_tier = "medium"
    else:
        performance_tier = "slow"

    # Override for known CI environments (they're typically slower due to shared resources)
    if is_ci:
        performance_tier = "slow" if cpu_count <= 2 else "medium"

    return {
        "environment_type": environment_type,
        "cpu_count": cpu_count,
        "memory_gb": round(memory_gb, 1),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "is_ci": is_ci,
        "is_github_actions": is_github_actions,
        "performance_tier": performance_tier,
        "runner_os": os.getenv("RUNNER_OS", "unknown"),
        "runner_arch": os.getenv("RUNNER_ARCH", "unknown"),
    }


def get_environment_key() -> str:
    """
    Get a unique key for the current environment for baseline storage.

    Returns:
        Environment key like 'github_actions_slow' or 'local_fast'
    """
    env = detect_environment()
    return f"{env['environment_type']}_{env['performance_tier']}"


def get_performance_multiplier() -> float:
    """
    Get expected performance multiplier compared to a baseline fast local environment.

    Returns:
        Multiplier where 1.0 = baseline, 2.0 = 2x slower, 0.5 = 2x faster
    """
    env = detect_environment()

    # Base multipliers by performance tier
    tier_multipliers = {
        "fast": 1.0,  # Baseline (8+ cores, 16+ GB RAM)
        "medium": 1.5,  # 50% slower (4-7 cores, 8-15 GB RAM)
        "slow": 3.0,  # 3x slower (≤4 cores, <8 GB RAM)
    }

    base_multiplier = tier_multipliers.get(env["performance_tier"], 2.0)

    # Additional CI overhead (shared resources, network latency, etc.)
    if env["is_ci"]:
        base_multiplier *= 1.2  # 20% additional overhead for CI

    # GitHub Actions specific adjustments
    if env["is_github_actions"]:
        base_multiplier *= 1.1  # Additional 10% for GitHub Actions overhead

    return base_multiplier


def get_environment_specific_threshold(base_threshold: float = 0.2) -> float:
    """
    Get environment-specific performance regression threshold.

    Args:
        base_threshold: Base threshold (e.g., 0.2 for 20%)

    Returns:
        Adjusted threshold for current environment
    """
    env = detect_environment()

    # CI environments have more variable performance, so use higher thresholds
    if env["is_ci"]:
        # GitHub Actions can be quite variable
        if env["is_github_actions"]:
            return base_threshold * 2.0  # 40% threshold instead of 20%
        else:
            return base_threshold * 1.5  # 30% threshold for other CI

    # Local environments should be more stable
    return base_threshold


def print_environment_info() -> None:
    """Print detailed environment information for debugging."""
    env = detect_environment()

    print("🔍 Environment Detection Results:")
    print(f"  Environment Type: {env['environment_type']}")
    print(f"  Performance Tier: {env['performance_tier']}")
    print(f"  CPU Cores: {env['cpu_count']}")
    print(f"  Memory: {env['memory_gb']} GB")
    print(f"  Platform: {env['platform']}")
    print(f"  Python: {env['python_version']}")
    print(f"  Is CI: {env['is_ci']}")
    print(f"  Is GitHub Actions: {env['is_github_actions']}")
    print(f"  Performance Multiplier: {get_performance_multiplier():.1f}x")
    print(f"  Regression Threshold: {get_environment_specific_threshold():.1%}")
    print()


if __name__ == "__main__":
    print_environment_info()
