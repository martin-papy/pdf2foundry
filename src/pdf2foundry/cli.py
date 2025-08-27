from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(add_completion=False, help="Convert a PDF into a Foundry VTT v12+ module.")


class TablesMode(str, Enum):
    AUTO = "auto"
    IMAGE_ONLY = "image-only"


@app.callback()
def main_callback() -> None:
    """Top-level CLI callback for shared setup if needed later."""


@app.command()
def version() -> None:
    """Print version and exit."""
    from . import __version__

    typer.echo(__version__)


@app.command()
def run(
    pdf: Annotated[
        Path,
        typer.Option("--pdf", exists=True, dir_okay=False, help="Path to source PDF"),
    ],
    mod_id: Annotated[str, typer.Option("--mod-id", help="Module ID")],
    mod_title: Annotated[str, typer.Option("--mod-title", help="Module title")],
    author: Annotated[str | None, typer.Option("--author", help="Author name")] = None,
    license: Annotated[str | None, typer.Option("--license", help="License string")] = None,
    pack_name: Annotated[
        str | None, typer.Option("--pack-name", help="Pack name; default <mod-id>-journals")
    ] = None,
    toc: Annotated[
        bool,
        typer.Option("--toc/--no-toc", help="Generate TOC entry"),
    ] = True,
    tables: Annotated[
        TablesMode,
        typer.Option(
            "--tables",
            case_sensitive=False,
            help="Tables mode",
        ),
    ] = TablesMode.AUTO,
    deterministic_ids: Annotated[
        bool,
        typer.Option("--deterministic-ids/--no-deterministic-ids", help="Use deterministic IDs"),
    ] = True,
    depend_compendium_folders: Annotated[
        bool,
        typer.Option(
            "--depend-compendium-folders/--no-depend-compendium-folders",
            help="Depend on Compendium Folders",
        ),
    ] = True,
    images_dir: Annotated[Path, typer.Option("--images-dir", help="Images directory name")] = Path(
        "assets"
    ),
    out_dir: Annotated[Path, typer.Option("--out-dir", help="Output directory")] = Path("dist"),
) -> int:
    """Entry point for the conversion pipeline (skeleton for now)."""

    # Defer implementation per architecture doc; return success for now.
    # Basic validation for required strings
    if not mod_id.strip():
        typer.echo("Error: --mod-id cannot be empty", err=True)
        return 2
    if not mod_title.strip():
        typer.echo("Error: --mod-title cannot be empty", err=True)
        return 2

    effective_pack_name = pack_name or f"{mod_id}-journals"

    _ = (
        pdf,
        mod_id,
        mod_title,
        author,
        license,
        effective_pack_name,
        toc,
        tables,
        deterministic_ids,
        depend_compendium_folders,
        images_dir,
        out_dir,
    )
    typer.echo("pdf2foundry: CLI skeleton ready.")
    return 0


def app_main() -> None:
    code = app()
    if isinstance(code, int):
        sys.exit(code)


if __name__ == "__main__":
    app_main()
