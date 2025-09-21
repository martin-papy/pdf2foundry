"""Tests for CLI pipeline options integration."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pdf2foundry.cli import app


@pytest.fixture  # type: ignore[misc]
def temp_pdf() -> Generator[str, None, None]:
    """Create a temporary minimal PDF file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"%PDF-1.4\n%EOF\n")
        yield tmp.name


def test_cli_convert_default_pipeline_options(temp_pdf: str) -> None:
    """Test CLI with default pipeline options."""
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

        # Check default values are displayed
        assert "Table Handling: auto" in result.stdout
        assert "OCR Mode: off" in result.stdout
        assert "Picture Descriptions: No" in result.stdout

    finally:
        Path(temp_pdf).unlink(missing_ok=True)


def test_cli_convert_structured_tables(temp_pdf: str) -> None:
    """Test CLI with structured tables option."""
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
                "--tables",
                "structured",
            ],
        )
        assert result.exit_code == 0
        assert "Table Handling: structured" in result.stdout

    finally:
        Path(temp_pdf).unlink(missing_ok=True)


def test_cli_convert_ocr_auto(temp_pdf: str) -> None:
    """Test CLI with OCR auto option."""
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
                "--ocr",
                "auto",
            ],
        )
        assert result.exit_code == 0
        assert "OCR Mode: auto" in result.stdout

    finally:
        Path(temp_pdf).unlink(missing_ok=True)


def test_cli_convert_picture_descriptions_on_with_vlm(temp_pdf: str) -> None:
    """Test CLI with picture descriptions enabled and VLM repo ID."""
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
                "--picture-descriptions",
                "on",
                "--vlm-repo-id",
                "microsoft/Florence-2-base",
            ],
        )
        assert result.exit_code == 0
        assert "Picture Descriptions: Yes" in result.stdout
        assert "VLM Repository: microsoft/Florence-2-base" in result.stdout

    finally:
        Path(temp_pdf).unlink(missing_ok=True)


def test_cli_convert_picture_descriptions_on_without_vlm_warns(temp_pdf: str) -> None:
    """Test CLI with picture descriptions enabled but no VLM repo ID shows warning."""
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
                "--picture-descriptions",
                "on",
            ],
        )
        assert result.exit_code == 0
        assert "Picture Descriptions: Yes" in result.stdout
        assert (
            "Warning: Picture descriptions enabled but no VLM repository ID provided"
            in result.stdout
        )

    finally:
        Path(temp_pdf).unlink(missing_ok=True)


def test_cli_convert_vlm_repo_id_without_picture_descriptions_warns(temp_pdf: str) -> None:
    """Test CLI with VLM repo ID but picture descriptions disabled shows warning."""
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
                "--vlm-repo-id",
                "microsoft/Florence-2-base",
            ],
        )
        assert result.exit_code == 0
        assert "Picture Descriptions: No" in result.stdout
        assert (
            "Warning: VLM repository ID provided but picture descriptions are disabled"
            in result.stdout
        )

    finally:
        Path(temp_pdf).unlink(missing_ok=True)


def test_cli_convert_invalid_tables_option(temp_pdf: str) -> None:
    """Test CLI with invalid tables option fails with error."""
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
                "--tables",
                "invalid",
            ],
        )
        assert result.exit_code == 1
        assert "Invalid tables mode 'invalid'" in result.stdout

    finally:
        Path(temp_pdf).unlink(missing_ok=True)


def test_cli_convert_invalid_ocr_option(temp_pdf: str) -> None:
    """Test CLI with invalid OCR option fails with error."""
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
                "--ocr",
                "invalid",
            ],
        )
        assert result.exit_code == 1
        assert "Invalid OCR mode 'invalid'" in result.stdout

    finally:
        Path(temp_pdf).unlink(missing_ok=True)


def test_cli_convert_invalid_picture_descriptions_option(temp_pdf: str) -> None:
    """Test CLI with invalid picture descriptions option fails with error."""
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
                "--picture-descriptions",
                "invalid",
            ],
        )
        assert result.exit_code == 1
        assert "Invalid picture_descriptions 'invalid'" in result.stdout

    finally:
        Path(temp_pdf).unlink(missing_ok=True)


@pytest.mark.parametrize("tables_mode", ["structured", "auto", "image-only"])  # type: ignore[misc]
def test_cli_convert_all_tables_modes(temp_pdf: str, tables_mode: str) -> None:
    """Test CLI with all valid tables modes."""
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
                "--tables",
                tables_mode,
            ],
        )
        assert result.exit_code == 0
        assert f"Table Handling: {tables_mode}" in result.stdout

    finally:
        Path(temp_pdf).unlink(missing_ok=True)


@pytest.mark.parametrize("ocr_mode", ["auto", "on", "off"])  # type: ignore[misc]
def test_cli_convert_all_ocr_modes(temp_pdf: str, ocr_mode: str) -> None:
    """Test CLI with all valid OCR modes."""
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
                "--ocr",
                ocr_mode,
            ],
        )
        assert result.exit_code == 0
        assert f"OCR Mode: {ocr_mode}" in result.stdout

    finally:
        Path(temp_pdf).unlink(missing_ok=True)
