"""E2E-010: Basic Error Handling Tests.

This module validates graceful handling of corrupted PDFs, invalid arguments,
and basic error scenarios with clear error messages and exit codes.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

# Common regex patterns for stderr checks
RE_CORRUPT = re.compile(r"corrupt|invalid|EOF|xref|trailer", re.IGNORECASE)
RE_USAGE = re.compile(r"usage|Usage:", re.IGNORECASE)


@pytest.fixture
def valid_pdf(fixtures_dir: Path) -> Path:
    """Return path to a known-good PDF for testing."""
    pdf_path = fixtures_dir / "basic.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Valid PDF fixture not found: {pdf_path}")
    return pdf_path


def make_corrupt_pdf(src: Path, dst: Path, truncate_bytes: int = 1024) -> None:
    """
    Create a corrupted PDF by copying and truncating.

    Args:
        src: Source PDF file path
        dst: Destination corrupted PDF file path
        truncate_bytes: Number of bytes to truncate from the end
    """
    # Ensure destination directory exists
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Copy the file
    shutil.copy2(src, dst)

    # Truncate the file to corrupt it
    original_size = dst.stat().st_size
    if truncate_bytes >= original_size:
        # If truncate_bytes is too large, just make it very small
        truncate_bytes = original_size - 100

    with dst.open("r+b") as f:
        f.truncate(original_size - truncate_bytes)


def run_cli(args: list[str], env: dict[str, str] | None = None, timeout: int | None = None) -> subprocess.CompletedProcess:
    """
    Execute the pdf2foundry CLI with capture_output=True, text=True.

    Args:
        args: Command line arguments (excluding the binary name)
        env: Environment variables to override/add
        timeout: Command timeout in seconds

    Returns:
        CompletedProcess with stdout/stderr captured
    """
    # Get CLI binary path from environment or use default
    cli_binary = os.getenv("PDF2FOUNDRY_CLI", "pdf2foundry")
    cmd = [cli_binary, *args]

    # Use environment timeout if not specified
    if timeout is None:
        timeout = int(os.getenv("PDF2FOUNDRY_TEST_TIMEOUT", "300"))

    # Prepare environment
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    try:
        result = subprocess.run(
            cmd,
            env=full_env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,  # Don't raise on non-zero exit
        )
        return result
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, stdout="", stderr=f"Command timed out after {timeout}s")
    except Exception as e:
        # Create a mock result for consistency
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=f"Command execution failed: {e}")


def assert_clean_output_dir(path: Path) -> None:
    """
    Verify path does not exist or is empty (no files/dirs).

    Args:
        path: Directory path to check

    Raises:
        AssertionError: If path exists and contains files/directories
    """
    if not path.exists():
        return

    # Check if directory is empty
    contents = list(path.iterdir())
    if contents:
        content_list = [str(item) for item in contents]
        raise AssertionError(f"Output directory {path} should be empty but contains: {content_list}")


@pytest.mark.e2e
@pytest.mark.tier1
@pytest.mark.ci_safe
def test_harness_smoke(tmp_path: Path) -> None:
    """
    Smoke test to verify test harness utilities work correctly.
    """
    # Test help command
    result = run_cli(["--help"])
    assert result.returncode == 0
    assert "usage" in result.stdout.lower() or "usage" in result.stderr.lower()

    # Test assert_clean_output_dir on a fresh tmp dir
    clean_dir = tmp_path / "clean_test"
    assert_clean_output_dir(clean_dir)  # Should not raise

    # Test make_corrupt_pdf (need a source PDF first)
    try:
        from tests.e2e.utils.fixtures import generate_minimal_pdf

        source_pdf = tmp_path / "source.pdf"
        corrupt_pdf = tmp_path / "corrupt.pdf"

        generate_minimal_pdf(source_pdf, "Test", "Content")
        original_size = source_pdf.stat().st_size

        make_corrupt_pdf(source_pdf, corrupt_pdf, truncate_bytes=100)
        corrupt_size = corrupt_pdf.stat().st_size

        # Verify corruption (smaller file)
        assert corrupt_size < original_size

    except ImportError:
        # If fixtures utility not available, skip this part
        pass


class TestBasicErrorHandling:
    """Test class for basic error handling scenarios."""

    def test_help_command(self) -> None:
        """Test that --help works and shows usage information."""
        result = run_cli(["--help"])
        assert result.returncode == 0

        # Check that help output contains expected content
        output = result.stdout + result.stderr
        assert RE_USAGE.search(output), "Help output should contain usage information"
        assert "pdf2foundry" in output.lower(), "Help should mention the command name"

    @pytest.mark.parametrize("truncate_bytes", [256, 2048, 8192])
    def test_corrupted_pdf(self, tmp_path: Path, valid_pdf: Path, truncate_bytes: int) -> None:
        """
        Validate that corrupted PDFs result in a non-zero exit, meaningful error message,
        and no residual outputs.
        """
        # Create corrupted PDF
        corrupt_pdf = tmp_path / "corrupt.pdf"
        make_corrupt_pdf(valid_pdf, corrupt_pdf, truncate_bytes=truncate_bytes)

        # Set up output directory
        outdir = tmp_path / "out-corrupt"

        # Run CLI with corrupted PDF
        result = run_cli(
            [
                "convert",
                str(corrupt_pdf),
                "--mod-id",
                "test-corrupt",
                "--mod-title",
                "Test Corrupt",
                "--out-dir",
                str(outdir),
            ]
        )

        # Assert non-zero exit code
        assert result.returncode != 0, f"Expected non-zero exit code for corrupted PDF (truncated by {truncate_bytes} bytes)"

        # Assert stderr contains corruption-related message
        stderr_output = result.stderr
        assert RE_CORRUPT.search(stderr_output), (
            f"Expected corruption-related error message in stderr. " f"Got: {stderr_output}"
        )

        # Assert no output directory created or it's empty
        assert_clean_output_dir(outdir)

        # Verify that the original valid PDF still works to the same output directory
        result_valid = run_cli(
            ["convert", str(valid_pdf), "--mod-id", "test-valid", "--mod-title", "Test Valid", "--out-dir", str(outdir)]
        )

        # Should succeed
        assert result_valid.returncode == 0, (
            f"Valid PDF should work after corrupt PDF failure. " f"stderr: {result_valid.stderr}"
        )

        # Should have created module.json in the module directory
        assert (outdir / "test-valid" / "module.json").exists(), "Valid PDF should create module.json"

    @pytest.mark.parametrize(
        "invalid_args,expected_token,expected_exit_code",
        [
            (["--bogus-flag"], "bogus-flag", 2),  # Unknown flag -> argument parsing error
            (["--ocr", "banana"], "banana", 1),  # Invalid enum value -> application error
            (["--tables", "nonsense"], "nonsense", 1),  # Invalid enum value -> application error
        ],
    )
    def test_invalid_args(
        self,
        tmp_path: Path,
        valid_pdf: Path,
        invalid_args: list[str],
        expected_token: str,
        expected_exit_code: int,
    ) -> None:
        """
        Ensure unknown flags and bad enum values produce appropriate error messages and exit codes.
        Unknown flags should return exit code 2 (argument parsing error).
        Invalid enum values should return exit code 1 (application error).
        """
        # Set up output directory
        outdir = tmp_path / "out-invalid"

        # Build command with invalid arguments
        cmd_args = [
            "convert",
            str(valid_pdf),
            "--mod-id",
            "test-invalid",
            "--mod-title",
            "Test Invalid",
            "--out-dir",
            str(outdir),
            *invalid_args,
        ]

        # Run CLI with invalid arguments
        result = run_cli(cmd_args)

        # Assert expected exit code
        assert result.returncode == expected_exit_code, (
            f"Expected exit code {expected_exit_code} for invalid arguments {invalid_args}. "
            f"Got exit code {result.returncode}"
        )

        # For unknown flags (exit code 2), expect usage message
        if expected_exit_code == 2:
            output = result.stdout + result.stderr
            assert RE_USAGE.search(output), (
                f"Expected usage message in output for unknown flag {invalid_args}. " f"Got: {output}"
            )
            # For unknown flags, the token should be in stderr (strip ANSI color codes)
            import re

            clean_stderr = re.sub(r"\x1b\[[0-9;]*m", "", result.stderr)
            assert expected_token in clean_stderr, (
                f"Expected token '{expected_token}' in stderr for unknown flag {invalid_args}. "
                f"Got stderr: {result.stderr}"
            )
        else:
            # For invalid enum values (exit code 1), expect error message
            output = result.stdout + result.stderr
            assert expected_token in output, (
                f"Expected token '{expected_token}' in output for invalid enum {invalid_args}. " f"Got output: {output}"
            )
            assert "Invalid" in output, (
                f"Expected 'Invalid' to be mentioned in output for invalid enum {invalid_args}. " f"Got output: {output}"
            )

        # Verify no output directory artifacts created
        assert_clean_output_dir(outdir)
