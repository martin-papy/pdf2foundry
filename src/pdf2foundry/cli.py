from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(add_completion=False, help="Convert a PDF into a Foundry VTT v12+ module.")


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
        typer.Option(exists=True, dir_okay=False, help="Path to source PDF"),
    ],
    mod_id: Annotated[str, typer.Option(help="Module ID")],
    mod_title: Annotated[str, typer.Option(help="Module title")],
    author: Annotated[str | None, typer.Option(help="Author name")] = None,
    license: Annotated[str | None, typer.Option(help="License string")] = None,
    pack_name: Annotated[
        str | None, typer.Option(help="Pack name; default <mod-id>-journals")
    ] = None,
    toc: Annotated[bool, typer.Option(help="Generate TOC entry")] = True,
    tables: Annotated[str, typer.Option(help="Tables mode: auto|image-only")] = "auto",
    deterministic_ids: Annotated[bool, typer.Option(help="Use deterministic IDs")] = True,
    depend_compendium_folders: Annotated[
        bool, typer.Option(help="Depend on Compendium Folders")
    ] = True,
    images_dir: Annotated[Path, typer.Option(help="Images directory name")] = Path("assets"),
    out_dir: Annotated[Path, typer.Option(help="Output directory")] = Path("dist"),
) -> int:
    """Entry point for the conversion pipeline (skeleton for now)."""

    # Defer implementation per architecture doc; return success for now.
    _ = (
        pdf,
        mod_id,
        mod_title,
        author,
        license,
        pack_name,
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
