"""Performance testing utilities for E2E tests."""

import json
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from tests.e2e.utils.environment_detection import (
    detect_environment,
    get_environment_key,
    get_environment_specific_threshold,
    get_performance_multiplier,
)


class PerformanceTimer:
    """High-precision performance timer using perf_counter_ns."""

    def __init__(self):
        self.start_time: int | None = None
        self.end_time: int | None = None

    def start(self) -> None:
        """Start the timer."""
        self.start_time = time.perf_counter_ns()
        self.end_time = None

    def stop(self) -> float:
        """
        Stop the timer and return elapsed time in seconds.

        Returns:
            Elapsed time in seconds
        """
        if self.start_time is None:
            raise RuntimeError("Timer not started")

        self.end_time = time.perf_counter_ns()
        return self.elapsed_seconds

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time is None:
            raise RuntimeError("Timer not started")

        end = self.end_time or time.perf_counter_ns()
        return (end - self.start_time) / 1_000_000_000

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return self.elapsed_seconds * 1000


@contextmanager
def perf_timer() -> Generator[PerformanceTimer, None, None]:
    """
    Context manager for performance timing.

    Usage:
        with perf_timer() as timer:
            # code to time
            pass
        print(f"Elapsed: {timer.elapsed_seconds:.3f}s")

    Yields:
        PerformanceTimer instance
    """
    timer = PerformanceTimer()
    timer.start()
    try:
        yield timer
    finally:
        timer.stop()


def write_performance_metrics(test_name: str, metrics: dict[str, float], perf_dir: Path | None = None) -> None:
    """
    Write performance metrics to environment-aware JSON files.

    Args:
        test_name: Name of the test
        metrics: Dictionary of metric names to values (in seconds)
        perf_dir: Directory to write metrics (default: tests/e2e/perf/)
    """
    if perf_dir is None:
        perf_dir = Path(__file__).parent.parent / "perf"

    perf_dir.mkdir(exist_ok=True)

    # Get environment information
    env_info = detect_environment()
    env_key = get_environment_key()

    # Write individual test metrics (environment-specific)
    test_file = perf_dir / f"{test_name}_{env_key}.json"

    # Load existing data if present
    if test_file.exists():
        try:
            with test_file.open() as f:
                existing_data = json.load(f)
        except (OSError, json.JSONDecodeError):
            existing_data = {"runs": [], "environment": env_info}
    else:
        existing_data = {"runs": [], "environment": env_info}

    # Add new run
    run_data = {"timestamp": time.time(), "metrics": metrics}
    existing_data["runs"].append(run_data)

    # Keep only last 10 runs to avoid file bloat
    existing_data["runs"] = existing_data["runs"][-10:]

    # Update environment info (in case it changed)
    existing_data["environment"] = env_info

    # Write updated data
    with test_file.open("w") as f:
        json.dump(existing_data, f, indent=2)

    # Update aggregate metrics
    update_aggregate_metrics(perf_dir)


def update_aggregate_metrics(perf_dir: Path) -> None:
    """
    Update the aggregate performance metrics file.

    Args:
        perf_dir: Directory containing performance files
    """
    latest_file = perf_dir / "latest.json"
    aggregate_data = {}

    # Process all test metric files
    for metric_file in perf_dir.glob("*.json"):
        if metric_file.name == "latest.json":
            continue

        try:
            with metric_file.open() as f:
                test_data = json.load(f)

            test_name = metric_file.stem
            runs = test_data.get("runs", [])

            if runs:
                # Get latest run
                latest_run = runs[-1]
                metrics = latest_run.get("metrics", {})

                # Calculate statistics from all runs
                all_metrics = {}
                for run in runs:
                    for metric_name, value in run.get("metrics", {}).items():
                        if metric_name not in all_metrics:
                            all_metrics[metric_name] = []
                        all_metrics[metric_name].append(value)

                # Compute statistics
                test_stats = {}
                for metric_name, values in all_metrics.items():
                    test_stats[metric_name] = {
                        "latest": metrics.get(metric_name, 0),
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                        "runs": len(values),
                    }

                aggregate_data[test_name] = {"timestamp": latest_run["timestamp"], "metrics": test_stats}

        except (OSError, json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not process {metric_file}: {e}")

    # Write aggregate data
    with latest_file.open("w") as f:
        json.dump(aggregate_data, f, indent=2)


def get_performance_baseline(test_name: str, metric_name: str, perf_dir: Path | None = None) -> float | None:
    """
    Get the environment-specific performance baseline for a test metric.

    Args:
        test_name: Name of the test
        metric_name: Name of the metric
        perf_dir: Directory containing performance files

    Returns:
        Baseline value in seconds, or None if not found
    """
    if perf_dir is None:
        perf_dir = Path(__file__).parent.parent / "perf"

    env_key = get_environment_key()

    # Try environment-specific file first
    env_specific_file = perf_dir / f"{test_name}_{env_key}.json"

    if env_specific_file.exists():
        try:
            with env_specific_file.open() as f:
                data = json.load(f)

            runs = data.get("runs", [])
            if runs:
                # Calculate average from recent runs
                recent_runs = runs[-5:]  # Use last 5 runs for baseline
                values = []
                for run in recent_runs:
                    metrics = run.get("metrics", {})
                    if metric_name in metrics:
                        values.append(metrics[metric_name])

                if values:
                    return sum(values) / len(values)
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    # Fallback to legacy baseline.json for backward compatibility
    legacy_baseline = perf_dir / "baseline.json"
    if legacy_baseline.exists():
        try:
            with legacy_baseline.open() as f:
                data = json.load(f)

            test_data = data.get(test_name, {})
            metrics = test_data.get("metrics", {})
            metric_data = metrics.get(metric_name, {})

            # Use average as baseline, but adjust for environment differences
            baseline_value = metric_data.get("avg")
            if baseline_value is not None:
                # Apply environment multiplier to legacy baseline
                multiplier = get_performance_multiplier()
                return baseline_value * multiplier

        except (OSError, json.JSONDecodeError, KeyError):
            pass

    return None


def check_performance_regression(
    test_name: str, metric_name: str, current_value: float, threshold: float | None = None, perf_dir: Path | None = None
) -> dict[str, Any]:
    """
    Check if current performance represents a regression using environment-aware baselines.

    Args:
        test_name: Name of the test
        metric_name: Name of the metric
        current_value: Current performance value in seconds
        threshold: Regression threshold (default: environment-specific)
        perf_dir: Directory containing performance files

    Returns:
        Dictionary with regression analysis results
    """
    # Use environment-specific threshold if not provided
    if threshold is None:
        threshold = get_environment_specific_threshold()

    # Get environment-aware baseline
    baseline = get_performance_baseline(test_name, metric_name, perf_dir)
    env_info = detect_environment()
    env_key = get_environment_key()

    result = {
        "test_name": test_name,
        "metric_name": metric_name,
        "current_value": current_value,
        "baseline": baseline,
        "threshold": threshold,
        "environment": env_info,
        "environment_key": env_key,
        "is_regression": False,
        "regression_ratio": 0.0,
        "status": "unknown",
    }

    if baseline is None:
        result["status"] = "no_baseline"
        return result

    if current_value <= baseline:
        result["status"] = "improved"
        result["regression_ratio"] = (baseline - current_value) / baseline
        return result

    regression_ratio = (current_value - baseline) / baseline
    result["regression_ratio"] = regression_ratio

    if regression_ratio > threshold:
        result["is_regression"] = True
        result["status"] = "regression"
    else:
        result["status"] = "acceptable"

    return result


@contextmanager
def performance_test(
    test_name: str, metric_name: str = "execution_time", check_regression: bool = True, threshold: float | None = None
) -> Generator[PerformanceTimer, None, None]:
    """
    Context manager for performance testing with automatic regression checking.

    Args:
        test_name: Name of the test
        metric_name: Name of the performance metric
        check_regression: Whether to check for performance regression
        threshold: Regression threshold (default from PERF_THRESHOLD env var)

    Yields:
        PerformanceTimer instance

    Raises:
        AssertionError: If performance regression is detected
    """
    timer = PerformanceTimer()
    timer.start()

    try:
        yield timer
    finally:
        elapsed = timer.stop()

        # Write metrics
        metrics = {metric_name: elapsed}
        write_performance_metrics(test_name, metrics)

        # Check for regression if requested
        if check_regression:
            result = check_performance_regression(test_name, metric_name, elapsed, threshold)

            if result["is_regression"]:
                raise AssertionError(
                    f"Performance regression detected in {test_name}.{metric_name}: "
                    f"{result['regression_ratio']:.1%} slower than baseline "
                    f"(threshold: {result['threshold']:.1%})"
                )


def benchmark_function(func, *args, iterations: int = 5, warmup: int = 1, **kwargs) -> dict[str, float]:
    """
    Benchmark a function with multiple iterations.

    Args:
        func: Function to benchmark
        *args: Positional arguments for the function
        iterations: Number of iterations to run
        warmup: Number of warmup iterations (not counted)
        **kwargs: Keyword arguments for the function

    Returns:
        Dictionary with timing statistics
    """
    times = []

    # Warmup runs
    for _ in range(warmup):
        func(*args, **kwargs)

    # Actual benchmark runs
    for _ in range(iterations):
        with perf_timer() as timer:
            func(*args, **kwargs)
        times.append(timer.elapsed_seconds)

    return {
        "min": min(times),
        "max": max(times),
        "avg": sum(times) / len(times),
        "iterations": iterations,
        "total": sum(times),
    }


def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds to a human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.1f}μs"
    elif seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    else:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.1f}s"
