"""Tests for CLI --reflow-columns flag functionality."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pdf2foundry.cli import app


@pytest.fixture
def temp_pdf() -> Generator[str, None, None]:
    """Create a temporary minimal PDF file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"%PDF-1.4\n%EOF\n")
        yield tmp.name


class TestReflowColumnsFlag:
    """Test --reflow-columns flag functionality."""

    def test_cli_convert_with_reflow_disabled_default(self, temp_pdf: str) -> None:
        """Test CLI with reflow disabled by default."""
        runner = CliRunner()

        try:
            result = runner.invoke(
                app,
                [
                    "convert",
                    temp_pdf,
                    "--mod-id",
                    "test-mod",
                    "--mod-title",
                    "Test Title",
                ],
            )
            assert result.exit_code == 0
            # Reflow should be disabled by default

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    def test_cli_convert_with_reflow_enabled(self, temp_pdf: str) -> None:
        """Test CLI with reflow explicitly enabled."""
        runner = CliRunner()

        try:
            result = runner.invoke(
                app,
                [
                    "convert",
                    temp_pdf,
                    "--mod-id",
                    "test-mod",
                    "--mod-title",
                    "Test Title",
                    "--reflow-columns",
                ],
            )
            assert result.exit_code == 0

        finally:
            Path(temp_pdf).unlink(missing_ok=True)
