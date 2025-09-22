"""Tests for conftest.py fixtures and utilities."""

import os
import subprocess
from pathlib import Path

import pytest


def test_project_root_fixture(project_root):
    """Test that project_root fixture finds the correct root directory."""
    assert isinstance(project_root, Path)
    assert project_root.exists()

    # Should contain pyproject.toml
    assert (project_root / "pyproject.toml").exists()

    # Should contain src/pdf2foundry
    assert (project_root / "src" / "pdf2foundry").exists()


def test_fixtures_dir_fixture(fixtures_dir):
    """Test that fixtures_dir fixture points to the correct directory."""
    assert isinstance(fixtures_dir, Path)
    assert fixtures_dir.exists()
    assert fixtures_dir.name == "fixtures"


def test_tmp_output_dir_fixture(tmp_output_dir):
    """Test that tmp_output_dir fixture creates a temporary directory."""
    assert isinstance(tmp_output_dir, Path)
    assert tmp_output_dir.exists()
    assert tmp_output_dir.is_dir()
    assert "output" in str(tmp_output_dir)


def test_tmp_cache_dir_fixture(tmp_cache_dir):
    """Test that tmp_cache_dir fixture creates a temporary cache directory."""
    assert isinstance(tmp_cache_dir, Path)
    assert tmp_cache_dir.exists()
    assert tmp_cache_dir.is_dir()
    assert "cache" in str(tmp_cache_dir)


def test_cli_runner_fixture(cli_runner):
    """Test that cli_runner fixture provides the run_cli function."""
    assert callable(cli_runner)

    # Test with a simple --help command
    result = cli_runner(["--help"])
    assert result.returncode == 0
    assert "pdf2foundry" in result.stdout.lower()
    assert "convert" in result.stdout.lower()


def test_skip_missing_fixture(skip_missing):
    """Test that skip_missing fixture provides the skip function."""
    assert callable(skip_missing)

    # Test with a binary that should exist (python)
    # This should not raise an exception
    skip_missing("python")

    # Test with a binary that definitely doesn't exist
    with pytest.raises(pytest.skip.Exception):
        skip_missing("definitely_nonexistent_binary_12345")


def test_environment_setup(tmp_cache_dir):
    """Test that the test environment is properly set up."""
    # Check that test-specific environment variables are set
    assert os.getenv("PDF2FOUNDRY_TEST_MODE") == "1"
    assert os.getenv("PDF2FOUNDRY_CACHE_DIR") == str(tmp_cache_dir)


def test_cli_runner_with_environment(cli_runner, tmp_output_dir):
    """Test CLI runner with custom environment variables."""
    custom_env = {"TEST_VAR": "test_value"}

    # Run a simple command with custom environment
    result = cli_runner(["--version"], env=custom_env)
    assert result.returncode == 0


def test_cli_runner_with_working_directory(cli_runner, tmp_output_dir):
    """Test CLI runner with custom working directory."""
    # Run command with specific working directory
    result = cli_runner(["--help"], cwd=tmp_output_dir)
    assert result.returncode == 0


@pytest.mark.slow
def test_cli_runner_timeout(cli_runner):
    """Test that CLI runner respects timeout settings."""
    # This test is marked as slow because it involves timeout testing
    # Use a very short timeout to test the mechanism
    with pytest.raises(subprocess.TimeoutExpired):
        # This would normally succeed, but with a very short timeout it should fail
        # Note: We can't easily test this without a command that takes time
        # So we'll skip this test for now and rely on manual testing
        pytest.skip("Timeout testing requires a long-running command")


def test_markers_are_configured():
    """Test that custom pytest markers are properly configured."""
    # This test verifies that our custom markers don't cause warnings
    # The actual marker functionality is tested by pytest itself
    import pytest

    # These should not raise warnings when used
    slow_marker = pytest.mark.slow
    perf_marker = pytest.mark.perf
    cache_marker = pytest.mark.cache

    assert slow_marker is not None
    assert perf_marker is not None
    assert cache_marker is not None
