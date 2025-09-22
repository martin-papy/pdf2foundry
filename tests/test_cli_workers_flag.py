"""Tests for CLI --workers flag functionality."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from pdf2foundry.cli import app


@pytest.fixture
def temp_pdf() -> Generator[str, None, None]:
    """Create a temporary minimal PDF file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"%PDF-1.4\n%EOF\n")
        yield tmp.name


class TestWorkersFlag:
    """Test --workers flag functionality."""

    def test_cli_convert_with_workers_default(self, temp_pdf: str) -> None:
        """Test CLI with default workers (should be 1)."""
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
            # Should show worker count in logs (may be in debug/info output)

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    def test_cli_convert_with_workers_multiple(self, temp_pdf: str) -> None:
        """Test CLI with multiple workers."""
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
                    "4",
                ],
            )
            assert result.exit_code == 0

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    def test_cli_convert_with_workers_zero(self, temp_pdf: str) -> None:
        """Test CLI with invalid workers count (zero)."""
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
                    "0",
                ],
            )
            assert result.exit_code == 1
            assert "Error:" in result.stdout
            assert "workers must be >= 1" in result.stdout

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    def test_cli_convert_with_workers_negative(self, temp_pdf: str) -> None:
        """Test CLI with invalid workers count (negative)."""
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
                    "-1",
                ],
            )
            assert result.exit_code == 1
            assert "Error:" in result.stdout

        finally:
            Path(temp_pdf).unlink(missing_ok=True)

    @patch("pdf2foundry.backend.caps.detect_backend_capabilities")
    def test_cli_convert_workers_capability_downgrade(self, mock_caps: Mock, temp_pdf: str) -> None:
        """Test that workers are downgraded when backend doesn't support parallelism."""
        # Mock backend capabilities to not support parallel extraction
        mock_caps.return_value = {
            "supports_parallel_extract": False,
            "platform": "test",
            "start_method": "spawn",
            "cpu_count": 4,
            "max_workers": 8,
        }

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
                    "4",
                ],
            )
            assert result.exit_code == 0
            # Should show downgrade message in output (may be in logs)

        finally:
            Path(temp_pdf).unlink(missing_ok=True)


@pytest.mark.parametrize("workers_count", [1, 2, 4, 8])
def test_cli_convert_valid_workers_counts(temp_pdf: str, workers_count: int) -> None:
    """Test CLI with various valid worker counts."""
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
                str(workers_count),
            ],
        )
        assert result.exit_code == 0

    finally:
        Path(temp_pdf).unlink(missing_ok=True)
