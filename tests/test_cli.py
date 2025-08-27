from typer.testing import CliRunner

from pdf2foundry.cli import app


def test_cli_shows_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Convert a PDF into a Foundry VTT v12+ module" in result.stdout
