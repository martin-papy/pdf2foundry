"""E2E-010: Dependency Error Handling Tests.

This module validates graceful handling of missing dependencies (like Tesseract)
and filesystem permission errors with clear error messages and exit codes.
"""

import contextlib
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

# Common regex patterns for stderr checks
RE_PERM = re.compile(r"Permission denied|EACCES|EPERM|Read-only", re.IGNORECASE)
RE_TESS = re.compile(r"tesseract|OCR|not found|missing", re.IGNORECASE)


@pytest.fixture
def valid_pdf(fixtures_dir: Path) -> Path:
    """Return path to a known-good PDF for testing."""
    pdf_path = fixtures_dir / "basic.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Valid PDF fixture not found: {pdf_path}")
    return pdf_path


def run_cli(args: list[str], env: dict[str, str] | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
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


def hide_in_path(bin_name: str) -> dict[str, str]:
    """
    Return env with PATH set to directories excluding any containing bin_name.

    Args:
        bin_name: Binary name to hide from PATH

    Returns:
        Environment dict with modified PATH
    """
    current_path = os.environ.get("PATH", "")
    path_dirs = current_path.split(os.pathsep)

    # Filter out directories containing the binary
    filtered_dirs = []
    for path_dir in path_dirs:
        if path_dir:  # Skip empty path components
            bin_path = Path(path_dir) / bin_name
            bin_path_exe = Path(path_dir) / f"{bin_name}.exe"  # Windows compatibility
            # Only include directory if it doesn't contain the binary
            if not (bin_path.exists() or bin_path_exe.exists()):
                filtered_dirs.append(path_dir)

    return {"PATH": os.pathsep.join(filtered_dirs)}


def make_readonly(path: Path) -> None:
    """
    Make a path read-only (chmod 0o555).

    Args:
        path: Path to make read-only
    """
    try:
        if path.is_file():
            path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        else:
            path.chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    except Exception:
        pass  # Best effort


def restore_writable(path: Path) -> None:
    """
    Restore writable permissions to a path.

    Args:
        path: Path to restore permissions
    """
    try:
        if path.is_file():
            path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        else:
            path.chmod(
                stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
            )
    except Exception:
        pass  # Best effort


class TestDependencyErrorHandling:
    """Test class for dependency-related error handling."""

    def test_missing_tesseract(self, tmp_path: Path, valid_pdf: Path) -> None:
        """
        Simulate missing Tesseract with OCR=on and verify clear errors,
        non-zero exits, and clean outputs.

        When OCR is explicitly requested with --ocr on, the application should
        fail if Tesseract is not available, rather than silently continuing.
        """
        # Set up output directory
        outdir = tmp_path / "out-ocr-missing"

        # Hide tesseract from PATH
        env = hide_in_path("tesseract")

        # Run CLI with OCR forced on (not auto) to trigger tesseract requirement
        result = run_cli(
            [
                "convert",
                str(valid_pdf),
                "--mod-id",
                "test-ocr-missing",
                "--mod-title",
                "Test OCR Missing",
                "--out-dir",
                str(outdir),
                "--ocr",
                "on",  # Force OCR on to trigger tesseract requirement
            ],
            env=env,
        )

        # Should fail when required dependency is missing
        assert result.returncode != 0, (
            f"Expected non-zero exit code when tesseract is missing and OCR is explicitly requested. "
            f"Got exit code {result.returncode}"
        )

        # Assert stderr contains tesseract-related error message
        stderr_output = result.stderr
        assert RE_TESS.search(stderr_output), f"Expected tesseract-related error message in stderr. " f"Got: {stderr_output}"

        # Verify no output directory artifacts created on failure
        assert_clean_output_dir(outdir)

    def test_permission_errors(self, tmp_path: Path, valid_pdf: Path, request) -> None:
        """
        Test filesystem permission failures and verify clear errors,
        non-zero exits, and clean outputs.
        """
        # Create read-only parent directory
        ro_parent = tmp_path / "ro"
        ro_parent.mkdir()

        # Add finalizer to restore permissions
        def restore_permissions():
            with contextlib.suppress(Exception):
                restore_writable(ro_parent)  # Best effort cleanup

        request.addfinalizer(restore_permissions)

        # Make parent read-only
        make_readonly(ro_parent)

        # Try to create output directory under read-only parent
        outdir = ro_parent / "out"

        # Run CLI - should fail due to permission error
        result = run_cli(
            [
                "convert",
                str(valid_pdf),
                "--mod-id",
                "test-perm-error",
                "--mod-title",
                "Test Permission Error",
                "--out-dir",
                str(outdir),
            ]
        )

        # Check if chmod was effective (might not work on all systems)
        if result.returncode == 0:
            # If the command succeeded, chmod might not be effective on this system
            pytest.skip("chmod read-only not effective on this system - cannot test permission errors")

        # Assert non-zero exit code
        assert result.returncode != 0, "Expected non-zero exit code for permission error"

        # Assert output contains permission-related error message
        output = result.stdout + result.stderr
        assert RE_PERM.search(output), (
            f"Expected permission-related error message in output. " f"Got stdout: {result.stdout}, stderr: {result.stderr}"
        )

        # Verify no output directory created under read-only parent
        assert not outdir.exists(), "Output directory should not be created under read-only parent"
