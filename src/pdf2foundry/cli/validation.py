"""CLI validation utilities for PDF2Foundry."""

import json
import subprocess
from pathlib import Path

import typer


def validate_ocr_availability(ocr_mode: str) -> None:
    """Validate OCR availability when explicitly requested.

    Args:
        ocr_mode: OCR mode string ("auto", "on", "off")

    Raises:
        typer.Exit: If OCR is required but not available
    """
    if ocr_mode != "on":
        return

    # Skip validation in test environments
    import os

    if os.getenv("PDF2FOUNDRY_SKIP_VALIDATION") == "1":
        return

    try:
        from pdf2foundry.ingest.ocr_engine import TesseractOcrEngine

        ocr_engine = TesseractOcrEngine()
        if not ocr_engine.is_available():
            typer.echo(
                "Error: OCR mode 'on' requires Tesseract but it is not available. "
                "Please install Tesseract or use '--ocr auto' to allow graceful degradation."
            )
            raise typer.Exit(1)
    except Exception as exc:
        typer.echo(f"Error: OCR availability check failed: {exc}")
        raise typer.Exit(1) from exc


def validate_foundry_cli_availability(compile_pack: bool) -> None:
    """Validate Foundry CLI availability when pack compilation is requested.

    Args:
        compile_pack: Whether pack compilation is requested

    Raises:
        typer.Exit: If pack compilation is required but CLI is not available
    """
    if not compile_pack:
        return

    # Skip validation in test environments
    import os

    if os.getenv("PDF2FOUNDRY_SKIP_VALIDATION") == "1":
        return

    try:
        from pdf2foundry.builder.packaging import _resolve_foundry_cli

        # Check if CLI can be resolved
        foundry_cli_path, working_directory = _resolve_foundry_cli()

        # Test if Node.js is available and CLI can be executed
        test_script = f'const cli = require({json.dumps(foundry_cli_path)}); console.log("OK");'
        subprocess.run(
            ["node", "-e", test_script],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
            cwd=working_directory,
        )
    except Exception as exc:
        typer.echo(
            f"Error: Pack compilation requires Foundry CLI but it is not available: {exc}. "
            "Please install Node.js and the Foundry CLI via 'npm install -g @foundryvtt/foundryvtt-cli' "
            "or remove the --compile-pack flag."
        )
        raise typer.Exit(1) from exc


def validate_output_directory_permissions(out_dir: Path) -> None:
    """Validate output directory permissions.

    Args:
        out_dir: Output directory path

    Raises:
        typer.Exit: If directory cannot be created or written to
    """
    try:
        # Check if we can create the output directory and write to it
        out_dir.mkdir(parents=True, exist_ok=True)

        # Test write permissions by creating a temporary file
        test_file = out_dir / ".pdf2foundry_permission_test"
        try:
            test_file.write_text("test")
            test_file.unlink()  # Clean up
        except (PermissionError, OSError) as exc:
            typer.echo(f"Error: Cannot write to output directory '{out_dir}': {exc}")
            raise typer.Exit(1) from exc

    except (PermissionError, OSError) as exc:
        typer.echo(f"Error: Cannot create output directory '{out_dir}': {exc}")
        raise typer.Exit(1) from exc
