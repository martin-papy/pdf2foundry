#!/usr/bin/env python3
"""
Demonstration script for environment-aware performance testing.

This script shows how the new environment detection and performance
baseline system works, addressing the "424% slower" issue by comparing
appropriate baselines for each environment.
"""

import sys
from pathlib import Path

# Add the project root to the path so we can import our modules
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from tests.e2e.utils.environment_detection import (  # noqa: E402
    print_environment_info,
)
from tests.e2e.utils.performance import (  # noqa: E402
    check_performance_regression,
    get_performance_baseline,
    write_performance_metrics,
)


def demonstrate_environment_awareness():
    """Demonstrate the environment-aware performance system."""
    print("🚀 Environment-Aware Performance Testing Demo")
    print("=" * 60)

    # Show current environment
    print_environment_info()

    # Simulate performance data for different scenarios
    scenarios = [
        ("Local MacBook Pro", {"environment_type": "local", "performance_tier": "fast"}, 32.5),
        ("GitHub Actions", {"environment_type": "github_actions", "performance_tier": "slow"}, 135.2),
        ("Local Linux", {"environment_type": "local", "performance_tier": "medium"}, 48.7),
    ]

    print("📊 Performance Comparison Scenarios:")
    print("-" * 60)

    for scenario_name, env_info, time_value in scenarios:
        multiplier = 1.0
        if env_info["environment_type"] == "github_actions":
            multiplier = 3.0 * 1.2 * 1.1  # slow tier * CI overhead * GitHub Actions overhead
        elif env_info["performance_tier"] == "medium":
            multiplier = 1.5

        threshold = 0.2  # 20% base threshold
        if env_info["environment_type"] == "github_actions":
            threshold = 0.4  # 40% for GitHub Actions
        elif "ci" in env_info["environment_type"]:
            threshold = 0.3  # 30% for other CI

        print(f"🖥️  {scenario_name}:")
        print(f"   Environment: {env_info['environment_type']} ({env_info['performance_tier']})")
        print(f"   Execution Time: {time_value:.1f}s")
        print(f"   Expected Multiplier: {multiplier:.1f}x")
        print(f"   Regression Threshold: {threshold:.1%}")

        # Show what the old system would think
        if scenario_name != "Local MacBook Pro":
            old_regression = (time_value - 32.5) / 32.5
            print(f"   ❌ Old System: {old_regression:.1%} regression (WRONG!)")

        # Show what the new system thinks
        expected_time = 32.5 * multiplier
        new_regression = (time_value - expected_time) / expected_time
        if abs(new_regression) < threshold:
            print(f"   ✅ New System: {new_regression:+.1%} vs expected (ACCEPTABLE)")
        else:
            print(f"   ⚠️  New System: {new_regression:+.1%} vs expected (NEEDS INVESTIGATION)")

        print()

    print("🎯 Key Benefits:")
    print("- Environment-specific baselines prevent false regressions")
    print("- Appropriate thresholds for each environment type")
    print("- Backward compatibility with legacy baseline.json")
    print("- Clear separation of local vs CI performance expectations")
    print()

    print("📁 File Structure:")
    print("tests/e2e/perf/")
    print("├── baseline.json                    # Legacy baseline (local)")
    print("├── table_processing_local_fast.json    # Local environment baseline")
    print("├── table_processing_github_actions_slow.json  # CI environment baseline")
    print("└── latest.json                      # Current run results")
    print()


def simulate_performance_test():
    """Simulate a performance test with the new system."""
    print("🧪 Simulating Performance Test")
    print("=" * 40)

    # Create a temporary performance directory
    perf_dir = Path(__file__).parent.parent / "perf" / "demo"
    perf_dir.mkdir(parents=True, exist_ok=True)

    # Simulate writing performance metrics
    test_metrics = {"conversion_time": 45.2}
    write_performance_metrics("demo_table_processing", test_metrics, perf_dir)

    print(f"✅ Wrote performance metrics to {perf_dir}")

    # Try to get baseline (will be None for first run)
    baseline = get_performance_baseline("demo_table_processing", "conversion_time", perf_dir)
    print(f"📊 Current baseline: {baseline:.1f}s" if baseline else "📊 No baseline yet (first run)")

    # Check for regression
    result = check_performance_regression("demo_table_processing", "conversion_time", 45.2, perf_dir=perf_dir)

    print(f"🔍 Regression check: {result['status']}")
    if result["status"] != "no_baseline":
        print(f"   Regression ratio: {result['regression_ratio']:+.1%}")
        print(f"   Threshold: {result['threshold']:.1%}")

    print(f"🌍 Environment: {result['environment_key']}")
    print()


if __name__ == "__main__":
    demonstrate_environment_awareness()
    simulate_performance_test()

    print("🎉 Demo complete! The new system addresses the '424% slower' issue")
    print("   by comparing performance within the same environment type.")
