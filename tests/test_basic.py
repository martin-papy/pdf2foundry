"""Basic tests for PDF2Foundry."""

from typer.testing import CliRunner

from pdf2foundry import __version__
from pdf2foundry.cli import app


def test_version() -> None:
    """Test that version is defined."""
    assert __version__ == "0.1.0"


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
    assert "Convert a PDF to a Foundry VTT module" in result.stdout


def test_cli_convert_placeholder() -> None:
    """Test that convert command runs with placeholder implementation."""
    runner = CliRunner()
    result = runner.invoke(
        app, ["convert", "test.pdf", "--mod-id", "test-module", "--mod-title", "Test Module"]
    )
    assert result.exit_code == 0
    assert "Converting test.pdf" in result.stdout
    assert "not yet implemented" in result.stdout
