"""CLI interface for PDF2Foundry."""

from typing import Annotated

import typer

app = typer.Typer(
    name="pdf2foundry",
    help="Convert born-digital PDFs into Foundry VTT v12+ module compendia.",
    no_args_is_help=True,
)


@app.command()
def convert(
    pdf: Annotated[str, typer.Argument(help="Path to source PDF file")],
    mod_id: Annotated[str, typer.Option("--mod-id", help="Module ID (required, must be unique)")],
    mod_title: Annotated[str, typer.Option("--mod-title", help="Module Title (required)")],
    out_dir: Annotated[
        str, typer.Option("--out-dir", help="Output directory for generated module")
    ] = "dist",
    author: Annotated[str, typer.Option("--author", help="Author name")] = "",
    license: Annotated[str, typer.Option("--license", help="License string")] = "",
    pack_name: Annotated[str, typer.Option("--pack-name", help="Compendium pack name")] = "",
    toc: Annotated[bool, typer.Option("--toc/--no-toc", help="Generate TOC")] = True,
    tables: Annotated[
        str, typer.Option("--tables", help="Table handling: auto or image-only")
    ] = "auto",
    deterministic_ids: Annotated[
        bool,
        typer.Option("--deterministic-ids/--no-deterministic-ids", help="Use deterministic IDs"),
    ] = True,
    depend_compendium_folders: Annotated[
        bool,
        typer.Option(
            "--depend-compendium-folders/--no-depend-compendium-folders",
            help="Add Compendium Folders dependency",
        ),
    ] = True,
) -> None:
    """Convert a PDF to a Foundry VTT module."""
    # TODO: Implement the actual conversion logic
    typer.echo(f"Converting {pdf} to Foundry module...")
    typer.echo(f"Module ID: {mod_id}")
    typer.echo(f"Module Title: {mod_title}")
    typer.echo(f"Output Directory: {out_dir}")
    typer.echo("Conversion not yet implemented - this is a placeholder!")


@app.callback()
def main() -> None:
    """PDF2Foundry - Convert born-digital PDFs into Foundry VTT v12+ module compendia."""
    pass


if __name__ == "__main__":
    app()
