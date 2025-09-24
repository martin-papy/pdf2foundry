"""CLI interface for PDF2Foundry."""

from pathlib import Path
from typing import Annotated

import typer

from pdf2foundry import __version__
from pdf2foundry.cli.conversion import run_conversion_pipeline
from pdf2foundry.cli.display import (
    display_configuration,
    display_docling_cache_behavior,
    display_validation_warnings,
)
from pdf2foundry.cli.interactive import prompt_for_missing_args
from pdf2foundry.cli.parse import parse_page_spec

app = typer.Typer(
    name="pdf2foundry",
    help="Convert born-digital PDFs into Foundry VTT v13 module compendia.",
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
        str | None,
        typer.Option(
            "--mod-id",
            help="Module ID (required, must be unique). Use lowercase, hyphens, no spaces.",
        ),
    ] = None,
    mod_title: Annotated[
        str | None,
        typer.Option(
            "--mod-title",
            help="Module Title (required). Display name for the module.",
        ),
    ] = None,
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
            help=(
                "Table handling: 'structured' (always extract structure), "
                "'auto' (try structured, fallback to image), or 'image-only' (always rasterize)"
            ),
        ),
    ] = "auto",  # Default: intelligent table processing with fallback
    ocr: Annotated[
        str,
        typer.Option(
            "--ocr",
            help=("OCR mode: 'auto' (OCR pages with low text coverage, default), " "'on' (always OCR), 'off' (disable OCR)"),
        ),
    ] = "auto",  # Default: intelligent OCR only when needed
    picture_descriptions: Annotated[
        str,
        typer.Option(
            "--picture-descriptions",
            help="Generate image captions: 'on' (enable with VLM) or 'off' (disable, default)",
        ),
    ] = "off",  # Default: disabled (requires VLM model and additional processing time)
    vlm_repo_id: Annotated[
        str | None,
        typer.Option(
            "--vlm-repo-id",
            help=(
                "Hugging Face VLM repository ID for picture descriptions " "(e.g., 'Salesforce/blip-image-captioning-base')"
            ),
        ),
    ] = None,
    deterministic_ids: Annotated[
        bool,
        typer.Option(
            "--deterministic-ids/--no-deterministic-ids",
            help="Use deterministic SHA1-based IDs for stable UUIDs across runs (default: yes)",
        ),
    ] = True,
    # Foundry v13 has native compendium folders; dependency flag removed
    compile_pack_now: Annotated[
        bool,
        typer.Option(
            "--compile-pack/--no-compile-pack",
            help="Compile sources to LevelDB pack using Foundry CLI (default: no)",
        ),
    ] = False,
    # Docling JSON cache options (single-pass ingestion plan)
    docling_json: Annotated[
        Path | None,
        typer.Option(
            "--docling-json",
            help=(
                "Path to Docling JSON cache. If it exists and is valid, load from it; "
                "otherwise convert and save to this path."
            ),
        ),
    ] = None,
    write_docling_json: Annotated[
        bool,
        typer.Option(
            "--write-docling-json/--no-write-docling-json",
            help=(
                "When enabled without --docling-json, write the Docling JSON cache to the default "
                "path (dist/<mod-id>/sources/docling.json). "
                "Ignored when --docling-json is provided."
            ),
        ),
    ] = False,
    fallback_on_json_failure: Annotated[
        bool,
        typer.Option(
            "--fallback-on-json-failure/--no-fallback-on-json-failure",
            help=("If loading from JSON fails, fall back to conversion " "(and overwrite when applicable)."),
        ),
    ] = False,
    pages: Annotated[
        str | None,
        typer.Option(
            "--pages",
            help=("Comma-separated list of 1-based page indices and ranges " "(e.g., '1,3,5-10'). Default: all pages."),
        ),
    ] = None,
    workers: Annotated[
        int,
        typer.Option(
            "--workers",
            help="Number of worker processes for CPU-bound page-level steps. Default: 1.",
        ),
    ] = 1,  # Default: single-threaded (safe on all platforms)
    reflow_columns: Annotated[
        bool,
        typer.Option(
            "--reflow-columns",
            help=(
                "Experimental: enable multi-column reflow in layout transform. "
                "Off by default. Use with caution on multi-column PDFs."
            ),
        ),
    ] = False,  # Default: disabled (experimental feature, may affect text order)
    no_ml: Annotated[
        bool,
        typer.Option(
            "--no-ml",
            help=(
                "Disable ML features (VLM, advanced OCR). Primarily for CI testing. "
                "When enabled, picture descriptions are automatically disabled."
            ),
        ),
    ] = False,  # Default: ML features enabled
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose",
            "-v",
            count=True,
            help=(
                "Increase verbosity. Use -v for info messages (decisions, summaries), "
                "-vv for debug messages (detailed processing). Default: warnings and errors only."
            ),
        ),
    ] = 0,
) -> None:
    """
    Convert a born-digital PDF into a Foundry VTT v13 module.
    
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
            
        # Enable structured tables and OCR
        pdf2foundry convert "Manual.pdf" --mod-id "manual" --mod-title "Game Manual" \\
            --tables structured --ocr auto
            
        # Enable picture descriptions with VLM
        pdf2foundry convert "Bestiary.pdf" --mod-id "bestiary" --mod-title "Monster Manual" \\
            --picture-descriptions on --vlm-repo-id "microsoft/Florence-2-base"
            
        # Process specific pages with multiple workers
        pdf2foundry convert "Manual.pdf" --mod-id "manual" --mod-title "Game Manual" \\
            --pages "1,5-10,15" --workers 4
            
        # Enable experimental multi-column reflow
        pdf2foundry convert "Academic.pdf" --mod-id "paper" --mod-title "Research Paper" \\
            --reflow-columns
    """
    # Configure logging based on verbosity level
    from pdf2foundry.ingest.logging_config import configure_logging

    configure_logging(verbose)

    # Interactive prompts when minimal args are provided
    if mod_id is None or mod_title is None:
        (
            mod_id,
            mod_title,
            author,
            license,
            pack_name,
            toc,
            tables,
            ocr,
            picture_descriptions,
            vlm_repo_id,
            deterministic_ids,
            compile_pack_now,
            out_dir,
        ) = prompt_for_missing_args(
            pdf,
            mod_id,
            mod_title,
            author,
            license,
            pack_name,
            toc,
            tables,
            ocr,
            picture_descriptions,
            vlm_repo_id,
            deterministic_ids,
            compile_pack_now,
            out_dir,
        )
        # Note: Interactive prompts don't handle pages, workers, reflow_columns yet
        # These remain as CLI-only options for now

    # Set default pack name if not provided
    if pack_name is None:
        pack_name = f"{mod_id}-journals"

    # Parse pages specification if provided
    parsed_pages: list[int] | None = None
    if pages is not None:
        try:
            parsed_pages = parse_page_spec(pages)
        except ValueError as exc:
            typer.echo(f"Error: {exc}")
            raise typer.Exit(1) from exc

    # Validate workers parameter
    if workers < 1:
        typer.echo("Error: --workers must be >= 1")
        raise typer.Exit(1)

    # Handle --no-ml flag: disable ML features when requested
    if no_ml:
        # Force disable picture descriptions when ML is disabled
        if picture_descriptions == "on":
            typer.echo("Warning: --no-ml flag overrides --picture-descriptions=on, disabling ML features")
        picture_descriptions = "off"
        vlm_repo_id = None

        # Set environment variable to indicate ML should be disabled
        import os

        os.environ["PDF2FOUNDRY_NO_ML"] = "1"

    # Validate CLI options using PdfPipelineOptions
    try:
        from pdf2foundry.model.pipeline_options import PdfPipelineOptions

        pipeline_options = PdfPipelineOptions.from_cli(
            tables=tables,
            ocr=ocr,
            picture_descriptions=picture_descriptions,
            vlm_repo_id=vlm_repo_id,
            pages=parsed_pages,
            workers=workers,
            reflow_columns=reflow_columns,
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc

    # Early validation: Check dependencies and permissions
    from pdf2foundry.cli.validation import (
        validate_foundry_cli_availability,
        validate_ocr_availability,
        validate_output_directory_permissions,
    )

    validate_ocr_availability(ocr)
    validate_foundry_cli_availability(compile_pack_now)

    # Validation warnings for picture descriptions
    display_validation_warnings(pipeline_options, vlm_repo_id)

    validate_output_directory_permissions(out_dir)

    # Validate mod_id format (basic check)
    if not mod_id.replace("-", "").replace("_", "").isalnum():
        typer.echo(
            "Error: --mod-id should contain only alphanumeric characters, hyphens, and underscores",
        )
        raise typer.Exit(1)

    # Note: deprecated flags (--docling-json-load/--docling-json-save) were removed.

    # Display configuration
    display_configuration(
        pdf,
        mod_id,
        mod_title,
        out_dir,
        pack_name,
        author,
        license,
        toc,
        tables,
        ocr,
        pipeline_options,
        deterministic_ids,
    )

    # Summarize Docling JSON cache behavior
    display_docling_cache_behavior(docling_json, write_docling_json, fallback_on_json_failure, out_dir, mod_id)

    # Execute single-pass ingestion pipeline
    run_conversion_pipeline(
        pdf=pdf,
        mod_id=mod_id,
        mod_title=mod_title,
        out_dir=out_dir,
        pack_name=pack_name,
        author=author,
        license=license,
        toc=toc,
        tables=tables,
        deterministic_ids=deterministic_ids,
        compile_pack_now=compile_pack_now,
        docling_json=docling_json,
        write_docling_json=write_docling_json,
        fallback_on_json_failure=fallback_on_json_failure,
        ocr=ocr,
        picture_descriptions=picture_descriptions,
        vlm_repo_id=vlm_repo_id,
        pages=parsed_pages,
        workers=workers,
        reflow_columns=reflow_columns,
        verbose=verbose,
        no_ml=no_ml,
    )


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
    PDF2Foundry - Convert born-digital PDFs into Foundry VTT v13 module compendia.

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
