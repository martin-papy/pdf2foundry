"""CLI interface for PDF2Foundry."""

from pathlib import Path
from typing import Annotated

import typer

from pdf2foundry import __version__

app = typer.Typer(
    name="pdf2foundry",
    help="Convert born-digital PDFs into Foundry VTT v12+ module compendia.",
    no_args_is_help=True,
)


@app.command()
def convert(
    pdf: Annotated[
        Path,
        typer.Argument(
            help="Path to source PDF file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    mod_id: Annotated[
        str,
        typer.Option(
            "--mod-id",
            help="Module ID (required, must be unique). Use lowercase, hyphens, no spaces.",
        ),
    ],
    mod_title: Annotated[
        str,
        typer.Option(
            "--mod-title",
            help="Module Title (required). Display name for the module.",
        ),
    ],
    out_dir: Annotated[
        Path,
        typer.Option(
            "--out-dir",
            help="Output directory for generated module (default: dist)",
        ),
    ] = Path("dist"),
    author: Annotated[
        str,
        typer.Option("--author", help="Author name for module metadata"),
    ] = "",
    license: Annotated[
        str,
        typer.Option("--license", help="License string for module metadata"),
    ] = "",
    pack_name: Annotated[
        str | None,
        typer.Option(
            "--pack-name",
            help="Compendium pack name (default: <mod-id>-journals)",
        ),
    ] = None,
    toc: Annotated[
        bool,
        typer.Option(
            "--toc/--no-toc",
            help="Generate Table of Contents Journal Entry (default: yes)",
        ),
    ] = True,
    tables: Annotated[
        str,
        typer.Option(
            "--tables",
            help="Table handling: 'auto' (HTML when possible) or 'image-only'",
        ),
    ] = "auto",
    deterministic_ids: Annotated[
        bool,
        typer.Option(
            "--deterministic-ids/--no-deterministic-ids",
            help="Use deterministic SHA1-based IDs for stable UUIDs across runs (default: yes)",
        ),
    ] = True,
    depend_compendium_folders: Annotated[
        bool,
        typer.Option(
            "--depend-compendium-folders/--no-depend-compendium-folders",
            help="Add Compendium Folders module as dependency for folder structure (default: yes)",
        ),
    ] = True,
) -> None:
    """
    Convert a born-digital PDF into a Foundry VTT v12+ module.
    
    This command processes a PDF file and generates a complete Foundry VTT module
    containing a Journal Entry compendium with chapters and sections from the PDF.
    
    Examples:
    
        # Basic conversion
        pdf2foundry convert "My Book.pdf" --mod-id "my-book" --mod-title "My Book"
        
        # With custom output directory and author
        pdf2foundry convert "Manual.pdf" --mod-id "game-manual" --mod-title "Game Manual" \\
            --out-dir "modules" --author "John Doe"
            
        # Disable TOC and use image-only tables
        pdf2foundry convert "Guide.pdf" --mod-id "guide" --mod-title "Player Guide" \\
            --no-toc --tables image-only
    """
    # Set default pack name if not provided
    if pack_name is None:
        pack_name = f"{mod_id}-journals"

    # Validate table handling option
    if tables not in ["auto", "image-only"]:
        typer.echo(
            f"Error: --tables must be 'auto' or 'image-only', got '{tables}'",
        )
        raise typer.Exit(1)

    # Validate mod_id format (basic check)
    if not mod_id.replace("-", "").replace("_", "").isalnum():
        typer.echo(
            "Error: --mod-id should contain only alphanumeric characters, hyphens, and underscores",
        )
        raise typer.Exit(1)

    # Display configuration
    typer.echo(f"📄 Converting PDF: {pdf}")
    typer.echo(f"🆔 Module ID: {mod_id}")
    typer.echo(f"📖 Module Title: {mod_title}")
    typer.echo(f"📁 Output Directory: {out_dir}")
    typer.echo(f"📦 Pack Name: {pack_name}")

    if author:
        typer.echo(f"👤 Author: {author}")
    if license:
        typer.echo(f"⚖️  License: {license}")

    typer.echo(f"📋 Generate TOC: {'Yes' if toc else 'No'}")
    typer.echo(f"📊 Table Handling: {tables}")
    typer.echo(f"🔗 Deterministic IDs: {'Yes' if deterministic_ids else 'No'}")
    typer.echo(f"📂 Compendium Folders Dependency: {'Yes' if depend_compendium_folders else 'No'}")

    typer.echo("\n⚠️  Conversion not yet implemented - this is a placeholder!")

    # TODO: Implement the actual conversion logic
    # This will be implemented in subsequent tasks


@app.command()
def version() -> None:
    """Show version information."""
    typer.echo(f"pdf2foundry version {__version__}")


def version_callback(value: bool) -> None:
    """Version callback for --version flag."""
    if value:
        typer.echo(f"pdf2foundry version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit",
        ),
    ] = None,
) -> None:
    """
    PDF2Foundry - Convert born-digital PDFs into Foundry VTT v12+ module compendia.

    This tool converts born-digital PDF documents into installable Foundry VTT modules
    containing Journal Entry compendia with proper structure, images, tables, and navigation.

    Features:
    - Preserves PDF structure (chapters → Journal Entries, sections → Journal Pages)
    - Extracts images and tables with fallback handling
    - Generates deterministic UUIDs for stable cross-references
    - Creates Table of Contents with navigation links
    - Supports Compendium Folders for organization

    For detailed usage, run: pdf2foundry convert --help
    """
    pass


@app.command()
def doctor() -> None:
    """Check environment for Docling and docling-core availability.

    This command performs a lightweight probe without processing any PDFs.
    It reports installed versions and whether a minimal DocumentConverter
    can be constructed.
    """
    # Import inside the function to avoid hard dependency at CLI import time
    try:
        from pdf2foundry.docling_env import (
            format_report_lines,
            probe_docling,
            report_is_ok,
        )
    except Exception as exc:  # pragma: no cover - extremely unlikely
        typer.echo(f"Error: failed to load environment probe: {exc}", err=True)
        raise typer.Exit(1) from exc

    report = probe_docling()
    for line in format_report_lines(report):
        typer.echo(line)

    if not report_is_ok(report):
        raise typer.Exit(1)


if __name__ == "__main__":  # pragma: no cover - executed only via `python -m`
    app()
