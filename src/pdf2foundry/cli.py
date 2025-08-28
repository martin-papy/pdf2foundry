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
    import tomllib
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as pkg_version

    ver: str | None = None
    # Prefer reading from pyproject.toml
    try:
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
        obj = data.get("project", {}).get("version")
        ver = obj if isinstance(obj, str) else None
    except Exception:
        ver = None

    # Fallback to installed package metadata, then to internal constant
    if ver is None:
        try:
            ver = pkg_version("pdf2foundry")
        except PackageNotFoundError:
            from . import __version__ as fallback_version

            ver = fallback_version

    typer.echo(ver)


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
    build: Annotated[
        bool,
        typer.Option(
            "--build/--no-build",
            help="Run the conversion pipeline to produce assembled HTML outputs",
        ),
    ] = False,
) -> int:
    """Entry point for the conversion pipeline."""

    # Basic validation for required strings
    if not mod_id.strip():
        typer.echo("Error: --mod-id cannot be empty", err=True)
        return 2
    if not mod_title.strip():
        typer.echo("Error: --mod-title cannot be empty", err=True)
        return 2

    effective_pack_name = pack_name or f"{mod_id}-journals"

    if not build:
        # Keep legacy behavior when not explicitly building, to satisfy existing tests
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

    # Build pipeline
    try:
        from .parser import (
            assemble_html_outputs,
            build_structure_map,
            choose_table_renders,
            create_environment,
            detect_headings_heuristic,
            detect_table_regions_with_camelot,
            extract_outline,
            extract_page_content,
            open_pdf,
            render_table_fragment,
            write_default_templates,
        )
    except Exception as exc:  # pragma: no cover - import resolution
        typer.echo(f"Error: failed to import pipeline modules: {exc}", err=True)
        return 1

    out_mod_dir = out_dir / mod_id
    templates_dir = out_mod_dir / "templates"
    sources_html_dir = out_mod_dir / "sources" / "html"
    assets_dir = out_mod_dir / images_dir
    templates_dir.mkdir(parents=True, exist_ok=True)
    sources_html_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Ensure default templates exist and env is ready
    write_default_templates(templates_dir)
    templates = create_environment(templates_dir)

    # Open PDF
    try:
        doc = open_pdf(pdf)
    except Exception as exc:  # pragma: no cover - depends on system libs
        typer.echo(f"Error: failed to open PDF: {exc}", err=True)
        return 1

    # Outline → structure map
    outline = extract_outline(doc)
    if not outline:
        # Fallback heuristic when bookmarks are missing
        # Cast to pages-like; our PdfDocumentLike supports __len__/__getitem__
        outline = detect_headings_heuristic(doc)  # type: ignore[arg-type]
    chapters = build_structure_map(outline)

    # Extract per-page content
    contents = extract_page_content(doc)  # type: ignore[arg-type]

    # Tables (optional) → per-page HTML fragments
    candidates = detect_table_regions_with_camelot(pdf)
    camelot_enabled = tables == TablesMode.AUTO
    per_page_table_html: dict[int, list[str]] = {}
    if candidates:
        renders = choose_table_renders(
            pdf, mod_id, assets_dir, candidates, parsed_tables=None, camelot_enabled=camelot_enabled
        )
        for r in renders:
            lst = per_page_table_html.setdefault(r.page_index, [])
            lst.append(render_table_fragment(r))
    tables_html_by_page: dict[int, str] = {k: "\n".join(v) for k, v in per_page_table_html.items()}

    # Assemble final HTML outputs
    chapters_html, sections_html = assemble_html_outputs(
        templates, chapters, contents, tables_html_by_page
    )

    # Write to disk under sources/html preserving logical paths
    def _write_html(rel_path: str, html: str) -> None:
        dest = sources_html_dir / f"{rel_path}.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")

    for ch in chapters:
        _write_html(ch.path, chapters_html[ch.path])
        for sec in ch.sections:
            _write_html(sec.path, sections_html[sec.path])

    msg = (
        "Built "
        f"{len(chapters_html)} chapters and {len(sections_html)} sections "
        f"→ {sources_html_dir}"
    )
    typer.echo(msg)
    return 0


def app_main() -> None:
    code = app()
    if isinstance(code, int):
        sys.exit(code)


if __name__ == "__main__":
    app_main()
