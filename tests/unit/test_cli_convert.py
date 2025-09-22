from __future__ import annotations

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from pdf2foundry.cli import app


def test_cli_convert_happy_path() -> None:
    runner = CliRunner()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"%PDF-1.4\n%EOF\n")
        pdf_path = tmp.name

    try:
        result = runner.invoke(
            app,
            [
                "convert",
                pdf_path,
                "--mod-id",
                "test-mod",
                "--mod-title",
                "Test Title",
            ],
        )
        assert result.exit_code == 0
        # key echoes
        assert "Converting PDF:" in result.stdout
        assert "Module ID: test-mod" in result.stdout
        assert "Module Title: Test Title" in result.stdout
    finally:
        Path(pdf_path).unlink(missing_ok=True)


def test_cli_convert_with_author_license() -> None:
    runner = CliRunner()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"%PDF-1.4\n%EOF\n")
        pdf_path = tmp.name

    try:
        result = runner.invoke(
            app,
            [
                "convert",
                pdf_path,
                "--mod-id",
                "test-mod",
                "--mod-title",
                "Test Title",
                "--author",
                "Alice",
                "--license",
                "MIT",
            ],
        )
        assert result.exit_code == 0
        assert "Author: Alice" in result.stdout
        assert "License: MIT" in result.stdout
    finally:
        Path(pdf_path).unlink(missing_ok=True)
