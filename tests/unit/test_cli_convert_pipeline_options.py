"""Tests for CLI pipeline options integration."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pdf2foundry.cli import app


@pytest.fixture(autouse=True)
def skip_validation() -> Generator[None, None, None]:
    """Skip CLI validation for unit tests."""
    original_value = os.environ.get("PDF2FOUNDRY_SKIP_VALIDATION")
    os.environ["PDF2FOUNDRY_SKIP_VALIDATION"] = "1"
    try:
        yield
    finally:
        if original_value is None:
            os.environ.pop("PDF2FOUNDRY_SKIP_VALIDATION", None)
        else:
            os.environ["PDF2FOUNDRY_SKIP_VALIDATION"] = original_value


@pytest.fixture
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
        assert "OCR Mode: auto" in result.stdout
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


def test_cli_convert_ocr_on(temp_pdf: str) -> None:
    """Test CLI with OCR on option."""
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
                "on",
            ],
        )
        assert result.exit_code == 0
        assert "OCR Mode: on" in result.stdout

    finally:
        Path(temp_pdf).unlink(missing_ok=True)


def test_cli_convert_ocr_off(temp_pdf: str) -> None:
    """Test CLI with OCR off option."""
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
                "off",
            ],
        )
        assert result.exit_code == 0
        assert "OCR Mode: off" in result.stdout

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


def test_cli_convert_picture_descriptions_on_without_vlm_uses_default(temp_pdf: str) -> None:
    """Test CLI with picture descriptions enabled but no VLM repo ID uses default model."""
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
        # Should automatically use default VLM model (no warning needed)
        assert "VLM Repository: Salesforce/blip-image-captioning-base" in result.stdout

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
        assert "Warning: VLM repository ID provided but picture descriptions are disabled" in result.stdout

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


@pytest.mark.parametrize("tables_mode", ["structured", "auto", "image-only"])
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


@pytest.mark.parametrize("ocr_mode", ["auto", "on"])
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
