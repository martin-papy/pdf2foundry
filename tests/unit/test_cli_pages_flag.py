"""Tests for CLI --pages flag functionality."""

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


class TestPagesFlag:
    """Test --pages flag functionality."""

    def test_cli_convert_with_pages_single(self, temp_pdf: str) -> None:
        """Test CLI with single page specification."""
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
                    "--pages",
                    "1",
                ],
            )
            assert result.exit_code == 0
            # Should show successful execution (placeholder message for minimal PDFs)
            assert "Conversion not yet implemented - this is a placeholder!" in result.stdout

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    def test_cli_convert_with_pages_range(self, temp_pdf: str) -> None:
        """Test CLI with page range specification."""
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
                    "--pages",
                    "1-3",
                ],
            )
            assert result.exit_code == 0

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    def test_cli_convert_with_pages_mixed(self, temp_pdf: str) -> None:
        """Test CLI with mixed pages and ranges."""
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
                    "--pages",
                    "1,3,5-7",
                ],
            )
            assert result.exit_code == 0

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    def test_cli_convert_with_invalid_pages_zero(self, temp_pdf: str) -> None:
        """Test CLI with invalid page specification (zero)."""
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
                    "--pages",
                    "0",
                ],
            )
            assert result.exit_code == 1
            assert "Error:" in result.stdout

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    def test_cli_convert_with_invalid_pages_negative(self, temp_pdf: str) -> None:
        """Test CLI with invalid page specification (negative)."""
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
                    "--pages",
                    "-1",
                ],
            )
            assert result.exit_code == 1
            assert "Error:" in result.stdout

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    def test_cli_convert_with_invalid_pages_range(self, temp_pdf: str) -> None:
        """Test CLI with invalid page range (start > end)."""
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
                    "--pages",
                    "10-3",
                ],
            )
            assert result.exit_code == 1
            assert "Error:" in result.stdout

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    def test_cli_convert_with_malformed_pages(self, temp_pdf: str) -> None:
        """Test CLI with malformed page specification."""
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
                    "--pages",
                    "1,,3",
                ],
            )
            assert result.exit_code == 1
            assert "Error:" in result.stdout

        finally:
            Path(temp_pdf).unlink(missing_ok=True)


@pytest.mark.parametrize("pages_spec", ["1", "1,3", "1-3", "1,3,5-7"])
def test_cli_convert_valid_pages_specs(temp_pdf: str, pages_spec: str) -> None:
    """Test CLI with various valid page specifications."""
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
                "--pages",
                pages_spec,
            ],
        )
        assert result.exit_code == 0

    finally:
        Path(temp_pdf).unlink(missing_ok=True)
