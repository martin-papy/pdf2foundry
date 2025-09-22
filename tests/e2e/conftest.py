"""Pytest configuration and fixtures for E2E tests."""

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Locate the project root directory (git root or pyproject.toml parent)."""
    current = Path(__file__).parent

    # Look for git root first
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent

    # Fall back to pyproject.toml parent
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent

    # Last resort: assume tests/e2e is two levels down from root
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def fixtures_dir(project_root: Path) -> Path:
    """Get the fixtures directory path."""
    fixtures_path = project_root / "fixtures"
    assert fixtures_path.exists(), f"Fixtures directory not found: {fixtures_path}"
    return fixtures_path


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory for each test."""
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)
    return output_dir


@pytest.fixture(scope="function")
def tmp_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary cache directory for each test."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


@pytest.fixture(scope="session")
def session_cache_dir(tmp_path_factory) -> Path:
    """Create a session-scoped cache directory for expensive operations."""
    cache_dir = tmp_path_factory.mktemp("session_cache")
    return cache_dir


def run_cli(
    args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None, timeout: int = 1800
) -> subprocess.CompletedProcess:
    """
    Run the PDF2Foundry CLI with robust logging and environment handling.

    Args:
        args: Command line arguments (excluding the binary name)
        cwd: Working directory for the command
        env: Additional environment variables
        timeout: Command timeout in seconds (default: 30 minutes)

    Returns:
        CompletedProcess with stdout/stderr merged
    """
    # Get CLI binary path from environment or use default
    cli_binary = os.getenv("PDF2FOUNDRY_CLI", "pdf2foundry")
    cmd = [cli_binary, *args]

    # Prepare environment
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    # Add common environment variables for testing
    full_env.setdefault("HF_HOME", str(Path.home() / ".cache" / "huggingface"))

    # Log command execution
    print(f"Running command: {' '.join(cmd)}")
    if cwd:
        print(f"Working directory: {cwd}")

    start_time = time.perf_counter()

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            timeout=timeout,
            check=False,  # Don't raise on non-zero exit
        )

        duration = time.perf_counter() - start_time
        print(f"Command completed in {duration:.2f}s with exit code {result.returncode}")

        if result.stdout:
            print(f"Output:\n{result.stdout}")

        return result

    except subprocess.TimeoutExpired:
        duration = time.perf_counter() - start_time
        print(f"Command timed out after {duration:.2f}s")
        raise
    except Exception as e:
        duration = time.perf_counter() - start_time
        print(f"Command failed after {duration:.2f}s: {e}")
        raise


def skip_if_missing_binary(name: str) -> None:
    """
    Skip the current test if the specified binary is not available.

    Args:
        name: Name of the binary to check for

    Raises:
        pytest.skip: If the binary is not found
    """
    if shutil.which(name) is None:
        pytest.skip(f"Required binary '{name}' not found in PATH")


@pytest.fixture
def cli_runner():
    """Fixture that provides the run_cli function for tests."""
    return run_cli


@pytest.fixture
def skip_missing():
    """Fixture that provides the skip_if_missing_binary function for tests."""
    return skip_if_missing_binary


@pytest.fixture(autouse=True)
def setup_test_environment(tmp_output_dir: Path, tmp_cache_dir: Path):
    """
    Automatically set up test environment for each test.

    This fixture runs automatically for every test and ensures:
    - Clean temporary directories
    - Proper environment variable setup
    """
    # Set test-specific environment variables
    original_env = {}
    test_env = {
        "PDF2FOUNDRY_TEST_MODE": "1",
        "PDF2FOUNDRY_CACHE_DIR": str(tmp_cache_dir),
    }

    # Save original values and set test values
    for key, value in test_env.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    yield

    # Restore original environment
    for key, original_value in original_env.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


# Pytest configuration hooks
def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "perf: marks tests as performance tests")
    config.addinivalue_line("markers", "cache: marks tests that use caching functionality")
    config.addinivalue_line("markers", "ocr: marks tests that require OCR functionality")
    config.addinivalue_line("markers", "vlm: marks tests that require Vision Language Models")
    config.addinivalue_line("markers", "pack: marks tests that involve Foundry pack compilation")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "errors: marks tests that test error handling")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names and paths."""
    for item in items:
        # Add slow marker to tests that are likely to be slow
        if any(keyword in item.name.lower() for keyword in ["full", "complete", "large", "comprehensive"]):
            item.add_marker(pytest.mark.slow)

        # Add integration marker to tests in integration directories or with integration in name
        if "integration" in str(item.fspath).lower() or "integration" in item.name.lower():
            item.add_marker(pytest.mark.integration)

        # Add performance marker to benchmark tests
        if "perf" in item.name.lower() or "benchmark" in item.name.lower():
            item.add_marker(pytest.mark.perf)

        # Add OCR marker to tests that likely use OCR
        if any(keyword in item.name.lower() for keyword in ["ocr", "tesseract", "scanned"]):
            item.add_marker(pytest.mark.ocr)

        # Add VLM marker to tests that likely use vision models
        if any(keyword in item.name.lower() for keyword in ["vlm", "vision", "multimodal"]):
            item.add_marker(pytest.mark.vlm)


def pytest_runtest_setup(item):
    """Set up individual test runs with dependency checking."""
    # Skip OCR tests if Tesseract is not available
    if item.get_closest_marker("ocr"):
        skip_if_missing_binary("tesseract")

    # Skip pack tests if Node.js is not available
    if item.get_closest_marker("pack"):
        skip_if_missing_binary("node")

    # Check for PDF2Foundry CLI availability for integration tests
    if item.get_closest_marker("integration"):
        cli_binary = os.getenv("PDF2FOUNDRY_CLI", "pdf2foundry")
        if shutil.which(cli_binary) is None:
            pytest.skip(f"PDF2Foundry CLI not found: {cli_binary}")


# Additional utility fixtures for common test patterns
@pytest.fixture
def sample_pdf_path(fixtures_dir: Path) -> Path:
    """Get path to a simple sample PDF for testing."""
    pdf_path = fixtures_dir / "basic.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Sample PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def complex_pdf_path(fixtures_dir: Path) -> Path:
    """Get path to a complex PDF for comprehensive testing."""
    pdf_path = fixtures_dir / "comprehensive-manual.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Complex PDF not found: {pdf_path}")
    return pdf_path
