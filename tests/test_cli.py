from pathlib import Path

from typer.testing import CliRunner

from pdf2foundry.cli import app


def test_cli_shows_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Convert a PDF into a Foundry VTT v12+ module" in result.stdout


def test_cli_version_command() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()


def test_run_minimal_options(tmp_path: Path) -> None:
    # Create an empty file to satisfy exists=True validation; parsing logic not executed yet
    pdf_file = tmp_path / "sample.pdf"
    pdf_file.write_bytes(b"")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--pdf",
            str(pdf_file),
            "--mod-id",
            "pdf2foundry-my-book",
            "--mod-title",
            "My Book",
        ],
    )
    assert result.exit_code == 0
    assert "CLI skeleton ready" in result.stdout


def test_tables_mode_validation(tmp_path: Path) -> None:
    pdf_file = tmp_path / "sample.pdf"
    pdf_file.write_bytes(b"")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--pdf",
            str(pdf_file),
            "--mod-id",
            "x",
            "--mod-title",
            "y",
            "--tables",
            "image-only",
        ],
    )
    assert result.exit_code == 0
