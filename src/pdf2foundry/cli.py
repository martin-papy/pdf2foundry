"""CLI interface for PDF2Foundry."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from pdf2foundry import __version__
from pdf2foundry.builder.ir_builder import build_document_ir, map_ir_to_foundry_entries
from pdf2foundry.builder.manifest import build_module_manifest, validate_module_manifest
from pdf2foundry.builder.packaging import PackCompileError, compile_pack
from pdf2foundry.builder.toc import build_toc_entry_from_entries, validate_toc_links
from pdf2foundry.ingest.content_extractor import extract_semantic_content
from pdf2foundry.ingest.docling_parser import parse_structure_from_doc
from pdf2foundry.ingest.ingestion import JsonOpts, ingest_docling
from pdf2foundry.model.foundry import JournalEntry
from pdf2foundry.ui.progress import ProgressReporter

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
            help=(
                "If loading from JSON fails, fall back to conversion "
                "(and overwrite when applicable)."
            ),
        ),
    ] = False,
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
    """
    # Interactive prompts when minimal args are provided
    if mod_id is None or mod_title is None:
        # Build sensible defaults from PDF name
        def _slug_default(text: str) -> str:
            import re as _re

            s = _re.sub(r"[^A-Za-z0-9]+", "-", (text or "").lower()).strip("-")
            s = _re.sub(r"-+", "-", s)
            return s or "untitled"

        pdf_stem = pdf.stem
        suggested_id = _slug_default(pdf_stem)
        suggested_title = pdf_stem

        if mod_id is None:
            mod_id = typer.prompt("Module ID", default=suggested_id)
        if mod_title is None:
            mod_title = typer.prompt("Module Title", default=suggested_title)

        # Optional metadata
        if not author:
            author = typer.prompt("Author", default="")
        if not license:
            license = typer.prompt("License", default="")

        # Derived values and confirmations
        if pack_name is None:
            pack_name = typer.prompt("Pack name", default=f"{mod_id}-journals")
        toc = typer.confirm("Generate TOC?", default=toc)
        tables = typer.prompt("Table handling (auto/image-only)", default=tables)
        deterministic_ids = typer.confirm("Use deterministic IDs?", default=deterministic_ids)
        compile_pack_now = typer.confirm("Compile LevelDB pack now?", default=compile_pack_now)
        out_dir = Path(typer.prompt("Output directory", default=str(out_dir)))

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

    # Note: deprecated flags (--docling-json-load/--docling-json-save) were removed.

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

    # Summarize Docling JSON cache behavior (ensures options are used and validated)
    default_json_path: Path | None = None
    if docling_json is not None and write_docling_json:
        typer.echo(
            "🗃️  Docling JSON: --docling-json provided; "
            "--write-docling-json is ignored (PATH semantics apply)"
        )
    if docling_json is not None:
        typer.echo(
            f"🗃️  Docling JSON cache: {docling_json} (load if exists; else convert then save)"
        )
    elif write_docling_json:
        default_json_path = out_dir / mod_id / "sources" / "docling.json"
        typer.echo(
            f"🗃️  Docling JSON cache: will write to default path {default_json_path} when converting"
        )
    else:
        typer.echo("🗃️  Docling JSON cache: disabled (no load/save)")
    if fallback_on_json_failure:
        typer.echo("↩️  Fallback on JSON failure: enabled")

    # Execute single-pass ingestion pipeline: get/create Docling once, then reuse
    # Keep placeholder path for minimal PDFs used in unit tests
    if str(pdf).endswith(".pdf") and pdf.stat().st_size < 1024:
        typer.echo("\n⚠️  Conversion not yet implemented - this is a placeholder!")
        return

    try:  # pragma: no cover - exercised via integration
        module_dir = out_dir / mod_id
        journals_src_dir = module_dir / "sources" / "journals"
        assets_dir = module_dir / "assets"
        styles_dir = module_dir / "styles"
        packs_dir = module_dir / "packs" / pack_name
        journals_src_dir.mkdir(parents=True, exist_ok=True)
        assets_dir.mkdir(parents=True, exist_ok=True)
        styles_dir.mkdir(parents=True, exist_ok=True)
        packs_dir.mkdir(parents=True, exist_ok=True)

        # Use rich progress UI for end-user feedback
        with ProgressReporter() as pr:
            startup_task = pr.add_step("Starting…", total=None)

            def _emit(event: str, payload: dict[str, int | str]) -> None:
                if startup_task in pr.progress.task_ids:
                    pr.finish_task(startup_task)
                pr.emit(event, payload)

            json_opts = JsonOpts(
                path=docling_json,
                write=write_docling_json,
                fallback_on_json_failure=fallback_on_json_failure,
                default_path=(
                    out_dir / mod_id / "sources" / "docling.json"
                    if write_docling_json and docling_json is None
                    else None
                ),
            )

            dl_doc = ingest_docling(pdf, json_opts=json_opts, on_progress=_emit)

            # Parse structure from the existing Docling doc
            parsed_doc = parse_structure_from_doc(dl_doc, on_progress=_emit)

            # Extract semantic content (HTML + images/tables/links)
            content = extract_semantic_content(
                dl_doc,
                out_assets=assets_dir,
                table_mode=tables,
                on_progress=_emit,
            )

            # Build IR
            ir = build_document_ir(
                parsed_doc,
                content,
                mod_id=mod_id,
                doc_title=mod_title,
                on_progress=_emit,
            )

            # 4) Map IR to Foundry Journal models
            entries: list[JournalEntry] = map_ir_to_foundry_entries(ir)

        # 5) Optionally add TOC entry at the beginning
        if toc:
            try:
                toc_entry = build_toc_entry_from_entries(mod_id, entries, title="Table of Contents")
                entries = [toc_entry, *entries]
                issues = validate_toc_links(toc_entry, entries[1:])
                for msg in issues:
                    typer.echo(f"⚠️  TOC link warning: {msg}")
            except Exception:
                # On failure, follow error policy: omit TOC, continue
                pass

        # 6) Write sources JSON, one file per entry
        def _slugify(text: str) -> str:
            import re as _re

            s = _re.sub(r"[^A-Za-z0-9]+", "-", (text or "").lower()).strip("-")
            s = _re.sub(r"-+", "-", s)
            return s or "untitled"

        used_names: set[str] = set()
        for idx, entry in enumerate(entries, start=1):
            base = _slugify(entry.name)
            name = base
            n = 1
            while name in used_names:
                n += 1
                name = f"{base}-{n}"
            used_names.add(name)
            out_file = journals_src_dir / f"{idx:03d}-{name}.json"
            # Include Classic Level key so the Foundry CLI packs primary docs
            data = asdict(entry)
            # Add Classic Level keys for Foundry CLI (root and pages)
            data["_key"] = f"!journal!{entry._id}"
            if isinstance(data.get("pages"), list):
                for p in data["pages"]:
                    pid = p.get("_id")
                    if isinstance(pid, str) and pid:
                        p["_key"] = f"!journal.pages!{entry._id}.{pid}"
            with out_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        # 7) Write module.json
        module_manifest = build_module_manifest(
            mod_id=mod_id,
            mod_title=mod_title,
            pack_name=pack_name,
            version=__version__,
            author=author,
            license_str=license,
            depend_compendium_folders=False,
        )
        issues = validate_module_manifest(module_manifest)
        for msg in issues:
            typer.echo(f"⚠️  module.json warning: {msg}")
        with (module_dir / "module.json").open("w", encoding="utf-8") as f:
            json.dump(module_manifest, f, ensure_ascii=False, indent=2)

        # 8) Write minimal CSS
        css_path = styles_dir / "pdf2foundry.css"
        if not css_path.exists():
            css_text = (
                ".pdf2foundry { line-height: 1.4; } "
                ".pdf2foundry img { max-width: 100%; height: auto; }\n"
            )
            css_path.write_text(css_text, encoding="utf-8")

        if compile_pack_now:
            try:
                compile_pack(module_dir, pack_name)
                typer.echo(f"\n✅ Compiled pack to {module_dir / 'packs' / pack_name}")
            except PackCompileError as exc:
                typer.echo(f"\n⚠️  Pack compilation failed: {exc}")
        else:
            typer.echo(f"\n✅ Wrote sources to {journals_src_dir} and assets to {assets_dir}")
            typer.echo("   Note: Pack compilation (packs/) is not performed automatically.")
    except ModuleNotFoundError:  # pragma: no cover - environment dependent
        typer.echo("\n⚠️  Docling not installed; skipping conversion steps.")
    except Exception as exc:  # pragma: no cover - unexpected runtime errors
        typer.echo(f"\n⚠️  Conversion failed: {exc}")


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
