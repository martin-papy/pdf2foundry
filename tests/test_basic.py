"""Basic tests for PDF2Foundry."""

from typer.testing import CliRunner

from pdf2foundry import __version__
from pdf2foundry.cli import app


def test_version() -> None:
    """Test that version is defined and follows semantic versioning."""
    import re

    # Version should be defined and follow semantic versioning pattern
    assert __version__ is not None
    assert isinstance(__version__, str)
    # Check it follows semantic versioning (e.g., "0.1.0", "1.2.3", etc.)
    version_pattern = r"^\d+\.\d+\.\d+$"
    assert re.match(
        version_pattern, __version__
    ), f"Version '{__version__}' doesn't follow semantic versioning"


def test_cli_help() -> None:
    """Test that CLI help works."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Convert born-digital PDFs" in result.stdout


def test_cli_convert_help() -> None:
    """Test that convert command help works."""
    runner = CliRunner()
    result = runner.invoke(app, ["convert", "--help"])
    assert result.exit_code == 0
    assert "Convert a born-digital PDF into a Foundry VTT v12+ module" in result.stdout


def test_cli_convert_placeholder() -> None:
    """Test that convert command runs with placeholder implementation."""
    runner = CliRunner()
    # Create a temporary PDF file for testing
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"%PDF-1.4\n%EOF\n")  # Minimal valid PDF
        tmp_path = tmp.name

    try:
        result = runner.invoke(
            app, ["convert", tmp_path, "--mod-id", "test-module", "--mod-title", "Test Module"]
        )
        assert result.exit_code == 0
        assert "Converting" in result.stdout
        assert "test-module" in result.stdout
        assert "not yet implemented" in result.stdout
    finally:
        # Clean up
        import os

        os.unlink(tmp_path)


def test_cli_version_command() -> None:
    """Test that version command works."""
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "pdf2foundry version" in result.stdout
    assert __version__ in result.stdout


def test_cli_version_flag() -> None:
    """Test that --version flag works."""
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "pdf2foundry version" in result.stdout
    assert __version__ in result.stdout


def test_cli_convert_validation() -> None:
    """Test CLI argument validation."""
    runner = CliRunner()

    # Test invalid mod-id
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"%PDF-1.4\n%EOF\n")
        tmp_path = tmp.name

    try:
        result = runner.invoke(
            app, ["convert", tmp_path, "--mod-id", "invalid mod id", "--mod-title", "Test"]
        )
        assert result.exit_code == 1
        assert "should contain only alphanumeric characters" in result.stdout

        # Test invalid tables option
        result = runner.invoke(
            app,
            ["convert", tmp_path, "--mod-id", "test", "--mod-title", "Test", "--tables", "invalid"],
        )
        assert result.exit_code == 1
        assert "must be 'auto' or 'image-only'" in result.stdout
    finally:
        import os

        os.unlink(tmp_path)


def test_cli_convert_defaults() -> None:
    """Test CLI default values."""
    runner = CliRunner()
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"%PDF-1.4\n%EOF\n")
        tmp_path = tmp.name

    try:
        result = runner.invoke(
            app, ["convert", tmp_path, "--mod-id", "test-mod", "--mod-title", "Test Module"]
        )
        assert result.exit_code == 0
        assert "test-mod-journals" in result.stdout  # Default pack name
        assert "Generate TOC: Yes" in result.stdout  # Default TOC
        assert "Table Handling: auto" in result.stdout  # Default tables
        assert "Deterministic IDs: Yes" in result.stdout  # Default deterministic IDs
    finally:
        import os

        os.unlink(tmp_path)
