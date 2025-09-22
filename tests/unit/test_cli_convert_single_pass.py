from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pdf2foundry.cli import app


def test_cli_single_pass_uses_docling_json_default_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = CliRunner()

    # Minimal PDF placeholder content used by CLI to short-circuit heavy work
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
                "m",
                "--mod-title",
                "t",
                "--write-docling-json",
            ],
        )
        # Placeholder path returns early, but prints configuration lines
        assert result.exit_code == 0
        assert "Docling JSON cache: will write to default path" in result.stdout
    finally:
        Path(pdf_path).unlink(missing_ok=True)
