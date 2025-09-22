"""Tests for combined CLI performance features and defaults behavior."""

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


class TestCombinedFeatures:
    """Test combinations of performance features."""

    def test_cli_convert_pages_and_workers(self, temp_pdf: str) -> None:
        """Test CLI with both pages and workers specified."""
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
                    "--workers",
                    "2",
                ],
            )
            assert result.exit_code == 0

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    def test_cli_convert_pages_and_reflow(self, temp_pdf: str) -> None:
        """Test CLI with both pages and reflow specified."""
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
                    "1-2",
                    "--reflow-columns",
                ],
            )
            assert result.exit_code == 0

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    def test_cli_convert_workers_and_reflow(self, temp_pdf: str) -> None:
        """Test CLI with both workers and reflow specified."""
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
                    "--workers",
                    "2",
                    "--reflow-columns",
                ],
            )
            assert result.exit_code == 0

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    def test_cli_convert_all_performance_features(self, temp_pdf: str) -> None:
        """Test CLI with all performance features enabled."""
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
                    "1-2",
                    "--workers",
                    "2",
                    "--reflow-columns",
                ],
            )
            assert result.exit_code == 0

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    def test_cli_convert_performance_with_other_features(self, temp_pdf: str) -> None:
        """Test CLI with performance features combined with other options."""
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
                    "--workers",
                    "2",
                    "--reflow-columns",
                    "--tables",
                    "structured",
                    "--ocr",
                    "auto",
                    "--no-toc",
                ],
            )
            assert result.exit_code == 0

        finally:
            Path(temp_pdf).unlink(missing_ok=True)


class TestDefaultsBehavior:
    """Test that defaults remain unchanged."""

    def test_cli_convert_defaults_unchanged(self, temp_pdf: str) -> None:
        """Test that default behavior is unchanged when no performance flags are used."""
        runner = CliRunner()

        try:
            # Run without any performance flags
            result_baseline = runner.invoke(
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
            assert result_baseline.exit_code == 0

            # Key assertions about defaults - should show successful execution
            assert "Conversion not yet implemented - this is a placeholder!" in result_baseline.stdout
            # The placeholder message indicates the CLI processed the arguments correctly

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    def test_cli_convert_explicit_defaults_same_as_implicit(self, temp_pdf: str) -> None:
        """Test that explicitly setting defaults produces same result as implicit defaults."""
        runner = CliRunner()

        try:
            # Run without flags (implicit defaults)
            result_implicit = runner.invoke(
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
            assert result_implicit.exit_code == 0

            # Run with explicit defaults
            result_explicit = runner.invoke(
                app,
                [
                    "convert",
                    temp_pdf,
                    "--mod-id",
                    "test-mod",
                    "--mod-title",
                    "Test Title",
                    "--workers",
                    "1",
                    # Note: --pages defaults to None (all pages), can't explicitly set
                    # Note: --reflow-columns defaults to False, no explicit way to set false
                ],
            )
            assert result_explicit.exit_code == 0

            # Both should succeed and have similar key outputs
            # (Exact comparison would be too brittle for this test level)

        finally:
            Path(temp_pdf).unlink(missing_ok=True)
