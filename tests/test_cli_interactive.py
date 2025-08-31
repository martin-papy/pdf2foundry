from __future__ import annotations

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from pdf2foundry.cli import app


def test_cli_convert_interactive_defaults() -> None:
    runner = CliRunner()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"%PDF-1.4\n%EOF\n")
        pdf_path = tmp.name

    try:
        # Provide newlines to accept defaults for all prompts
        user_input = "\n" * 11
        result = runner.invoke(app, ["convert", pdf_path], input=user_input)
        assert result.exit_code == 0
        # Echoes should include these lines
        assert "Module ID:" in result.stdout
        assert "Module Title:" in result.stdout
        assert "Output Directory:" in result.stdout
    finally:
        Path(pdf_path).unlink(missing_ok=True)
