"""Tests for validation, assertion, and performance utilities."""

import json
import sys
import time
from pathlib import Path

import pytest

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.assertions import (
    assert_files_exist,
    assert_json_structure,
    assert_no_broken_assets,
    assert_performance_within_threshold,
    assert_toc_resolves,
    assert_valid_compendium_structure,
    assert_valid_module_json,
)
from utils.performance import (
    PerformanceTimer,
    benchmark_function,
    check_performance_regression,
    format_duration,
    get_performance_baseline,
    perf_timer,
    performance_test,
    write_performance_metrics,
)
from utils.validation import (
    load_schema,
    validate_compendium_structure,
    validate_json_structure,
    validate_module_json,
)


class TestValidationUtils:
    """Test validation utilities."""

    def test_load_schema(self):
        """Test loading JSON schema."""
        schema = load_schema("module")

        assert isinstance(schema, dict)
        assert "$schema" in schema
        assert "properties" in schema
        assert "id" in schema["properties"]
        assert "title" in schema["properties"]

    def test_load_nonexistent_schema(self):
        """Test loading non-existent schema."""
        with pytest.raises(FileNotFoundError):
            load_schema("nonexistent")

    def test_validate_module_json_valid(self, tmp_path):
        """Test validation of a valid module.json."""
        module_data = {"id": "test-module", "title": "Test Module", "version": "1.0.0", "compatibility": {"minimum": "13"}}

        module_file = tmp_path / "module.json"
        with module_file.open("w") as f:
            json.dump(module_data, f)

        errors = validate_module_json(module_file)
        assert errors == []

    def test_validate_module_json_invalid(self, tmp_path):
        """Test validation of an invalid module.json."""
        module_data = {
            "title": "Test Module",  # Missing required 'id'
            "version": "1.0.0",
            # Missing required 'compatibility'
        }

        module_file = tmp_path / "module.json"
        with module_file.open("w") as f:
            json.dump(module_data, f)

        errors = validate_module_json(module_file)
        assert len(errors) > 0
        assert any("id" in error for error in errors)

    def test_validate_module_json_missing_file(self, tmp_path):
        """Test validation of missing module.json."""
        missing_file = tmp_path / "missing.json"
        errors = validate_module_json(missing_file)

        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_validate_compendium_structure_valid(self, tmp_path):
        """Test validation of valid compendium structure."""
        # Create valid module structure
        module_data = {
            "id": "test-module",
            "title": "Test Module",
            "version": "1.0.0",
            "compatibility": {"minimum": "13"},
            "packs": [{"name": "test-pack", "label": "Test Pack", "path": "packs/test-pack", "type": "JournalEntry"}],
        }

        # Create directories and files
        (tmp_path / "module.json").write_text(json.dumps(module_data))
        (tmp_path / "packs" / "test-pack").mkdir(parents=True)
        (tmp_path / "sources").mkdir()
        (tmp_path / "assets").mkdir()

        errors = validate_compendium_structure(tmp_path)
        assert errors == []

    def test_validate_compendium_structure_missing_pack(self, tmp_path):
        """Test validation with missing pack directory."""
        module_data = {
            "id": "test-module",
            "title": "Test Module",
            "version": "1.0.0",
            "compatibility": {"minimum": "13"},
            "packs": [
                {"name": "missing-pack", "label": "Missing Pack", "path": "packs/missing-pack", "type": "JournalEntry"}
            ],
        }

        (tmp_path / "module.json").write_text(json.dumps(module_data))

        errors = validate_compendium_structure(tmp_path)
        assert len(errors) > 0
        assert any("Pack directory not found" in error for error in errors)

    def test_validate_json_structure(self, tmp_path):
        """Test JSON structure validation."""
        test_data = {"name": "Test", "version": 1, "items": ["a", "b", "c"]}

        json_file = tmp_path / "test.json"
        with json_file.open("w") as f:
            json.dump(test_data, f)

        # Valid structure
        expected_keys = ["name", "version", "items"]
        errors = validate_json_structure(json_file, expected_keys)
        assert errors == []

        # Missing key
        expected_keys = ["name", "version", "missing_key"]
        errors = validate_json_structure(json_file, expected_keys)
        assert len(errors) == 1
        assert "missing_key" in errors[0]


class TestAssertionUtils:
    """Test assertion utilities."""

    def test_assert_valid_module_json_success(self, tmp_path):
        """Test successful module.json assertion."""
        module_data = {"id": "test-module", "title": "Test Module", "version": "1.0.0", "compatibility": {"minimum": "13"}}

        module_file = tmp_path / "module.json"
        with module_file.open("w") as f:
            json.dump(module_data, f)

        # Should not raise
        assert_valid_module_json(module_file)

    def test_assert_valid_module_json_failure(self, tmp_path):
        """Test failing module.json assertion."""
        module_data = {"title": "Invalid Module"}  # Missing required fields

        module_file = tmp_path / "module.json"
        with module_file.open("w") as f:
            json.dump(module_data, f)

        with pytest.raises(AssertionError):
            assert_valid_module_json(module_file)

    def test_assert_files_exist_success(self, tmp_path):
        """Test successful file existence assertion."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"

        file1.write_text("content1")
        file2.write_text("content2")

        # Should not raise
        assert_files_exist([file1, file2])

    def test_assert_files_exist_failure(self, tmp_path):
        """Test failing file existence assertion."""
        existing_file = tmp_path / "exists.txt"
        missing_file = tmp_path / "missing.txt"

        existing_file.write_text("content")

        with pytest.raises(AssertionError):
            assert_files_exist([existing_file, missing_file])

    def test_assert_json_structure_success(self, tmp_path):
        """Test successful JSON structure assertion."""
        test_data = {"name": "Test", "count": 42, "items": ["a", "b"]}

        json_file = tmp_path / "test.json"
        with json_file.open("w") as f:
            json.dump(test_data, f)

        expected_structure = {"name": str, "count": int, "items": [str]}

        # Should not raise
        assert_json_structure(json_file, expected_structure)

    def test_assert_performance_within_threshold_success(self):
        """Test successful performance assertion."""
        # Should not raise (within threshold)
        assert_performance_within_threshold(1.0, 1.0, 0.2)
        assert_performance_within_threshold(1.1, 1.0, 0.2)  # 10% slower, within 20% threshold

    def test_assert_performance_within_threshold_failure(self):
        """Test failing performance assertion."""
        with pytest.raises(AssertionError):
            assert_performance_within_threshold(1.5, 1.0, 0.2)  # 50% slower, exceeds 20% threshold


class TestPerformanceUtils:
    """Test performance utilities."""

    def test_performance_timer_basic(self):
        """Test basic performance timer functionality."""
        timer = PerformanceTimer()

        timer.start()
        time.sleep(0.01)  # 10ms
        elapsed = timer.stop()

        assert elapsed >= 0.01
        assert elapsed < 0.02  # Should be close to 10ms
        assert timer.elapsed_seconds == elapsed
        assert timer.elapsed_ms >= 10

    def test_perf_timer_context_manager(self):
        """Test performance timer context manager."""
        with perf_timer() as timer:
            time.sleep(0.01)

        assert timer.elapsed_seconds >= 0.01
        assert timer.elapsed_ms >= 10

    def test_write_and_read_performance_metrics(self, tmp_path):
        """Test writing and reading performance metrics."""
        perf_dir = tmp_path / "perf"

        # Write metrics
        metrics = {"execution_time": 1.5, "memory_usage": 100.0}
        write_performance_metrics("test_function", metrics, perf_dir)

        # Check file was created (with environment-specific naming)
        from utils.environment_detection import get_environment_key

        env_key = get_environment_key()
        test_file = perf_dir / f"test_function_{env_key}.json"
        assert test_file.exists()

        # Check content
        with test_file.open() as f:
            data = json.load(f)

        assert "runs" in data
        assert len(data["runs"]) == 1
        assert data["runs"][0]["metrics"] == metrics

        # Check aggregate file was created
        latest_file = perf_dir / "latest.json"
        assert latest_file.exists()

    def test_get_performance_baseline(self, tmp_path):
        """Test getting performance baseline."""
        perf_dir = tmp_path / "perf"

        # Write some metrics first
        metrics1 = {"execution_time": 1.0}
        metrics2 = {"execution_time": 1.2}
        write_performance_metrics("test_baseline", metrics1, perf_dir)
        write_performance_metrics("test_baseline", metrics2, perf_dir)

        # Get baseline (should be average)
        baseline = get_performance_baseline("test_baseline", "execution_time", perf_dir)
        assert baseline == 1.1  # Average of 1.0 and 1.2

    def test_check_performance_regression(self, tmp_path):
        """Test performance regression checking."""
        perf_dir = tmp_path / "perf"

        # Establish baseline
        metrics = {"execution_time": 1.0}
        write_performance_metrics("test_regression", metrics, perf_dir)

        # Test no regression
        result = check_performance_regression("test_regression", "execution_time", 1.1, 0.2, perf_dir)
        assert not result["is_regression"]
        assert result["status"] == "acceptable"

        # Test regression
        result = check_performance_regression("test_regression", "execution_time", 1.5, 0.2, perf_dir)
        assert result["is_regression"]
        assert result["status"] == "regression"

    @pytest.mark.perf
    def test_performance_test_context_manager(self, tmp_path):
        """Test performance test context manager."""
        # First run to establish baseline (should not check regression)
        with performance_test("test_context_mgr", check_regression=False) as timer:
            time.sleep(0.01)

        assert timer.elapsed_seconds >= 0.01

        # Second run should not raise (within reasonable bounds)
        # Use a high threshold to avoid flaky tests
        with performance_test("test_context_mgr", check_regression=True, threshold=2.0) as timer:
            time.sleep(0.01)

        assert timer.elapsed_seconds >= 0.01

    def test_benchmark_function(self):
        """Test function benchmarking."""

        def test_func(n):
            return sum(range(n))

        results = benchmark_function(test_func, 100, iterations=3, warmup=1)

        assert "min" in results
        assert "max" in results
        assert "avg" in results
        assert "iterations" in results
        assert "total" in results

        assert results["iterations"] == 3
        assert results["min"] <= results["avg"] <= results["max"]
        # Check total is approximately avg * iterations (allow for floating point precision)
        expected_total = results["avg"] * 3
        assert abs(results["total"] - expected_total) < 1e-10

    def test_format_duration(self):
        """Test duration formatting."""
        assert "μs" in format_duration(0.0001)  # microseconds
        assert "ms" in format_duration(0.1)  # milliseconds
        assert "s" in format_duration(1.5)  # seconds
        assert "m" in format_duration(65)  # minutes


@pytest.mark.slow
class TestIntegrationScenarios:
    """Integration tests for complete E2E scenarios."""

    def test_complete_module_validation_workflow(self, tmp_path):
        """Test a complete module validation workflow."""
        # Create a realistic module structure
        module_data = {
            "id": "integration-test-module",
            "title": "Integration Test Module",
            "version": "1.0.0",
            "compatibility": {"minimum": "13", "verified": "13"},
            "packs": [
                {"name": "test-journals", "label": "Test Journals", "path": "packs/test-journals", "type": "JournalEntry"}
            ],
            "styles": ["styles/module.css"],
        }

        # Create directory structure
        (tmp_path / "module.json").write_text(json.dumps(module_data, indent=2))
        (tmp_path / "packs" / "test-journals").mkdir(parents=True)
        (tmp_path / "sources" / "journals").mkdir(parents=True)
        (tmp_path / "assets").mkdir()
        (tmp_path / "styles").mkdir()
        (tmp_path / "styles" / "module.css").write_text("/* Test CSS */")

        # Create a sample journal entry
        journal_entry = {
            "_id": "1234567890abcdef",
            "name": "Test Entry",
            "pages": [
                {
                    "_id": "abcdef1234567890",
                    "name": "Test Page",
                    "type": "text",
                    "text": {"content": "<h1>Test Content</h1><p>This is a test.</p>", "format": 1},
                }
            ],
        }

        journal_file = tmp_path / "sources" / "journals" / "test-entry.json"
        with journal_file.open("w") as f:
            json.dump(journal_entry, f, indent=2)

        # Run complete validation workflow
        with perf_timer() as timer:
            # Validate module structure
            assert_valid_module_json(tmp_path / "module.json")
            assert_valid_compendium_structure(tmp_path)
            assert_no_broken_assets(tmp_path)
            assert_toc_resolves(tmp_path)

            # Validate required files exist
            required_files = [tmp_path / "module.json", tmp_path / "styles" / "module.css"]
            assert_files_exist(required_files)

        # Validation should complete quickly
        assert timer.elapsed_seconds < 1.0

        print(f"Complete validation workflow completed in {format_duration(timer.elapsed_seconds)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
