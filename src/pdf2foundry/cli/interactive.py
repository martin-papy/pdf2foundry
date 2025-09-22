"""Interactive prompting utilities for CLI."""

from pathlib import Path

import typer


def slug_default(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    import re as _re

    s = _re.sub(r"[^A-Za-z0-9]+", "-", (text or "").lower()).strip("-")
    s = _re.sub(r"-+", "-", s)
    return s or "untitled"


def prompt_for_missing_args(
    pdf: Path,
    mod_id: str | None,
    mod_title: str | None,
    author: str,
    license: str,
    pack_name: str | None,
    toc: bool,
    tables: str,
    ocr: str,
    picture_descriptions: str,
    vlm_repo_id: str | None,
    deterministic_ids: bool,
    compile_pack_now: bool,
    out_dir: Path,
) -> tuple[str, str, str, str, str, bool, str, str, str, str | None, bool, bool, Path]:
    """Prompt for missing CLI arguments interactively.

    Returns:
        Tuple of all the arguments with user-provided values
    """
    # Build sensible defaults from PDF name
    pdf_stem = pdf.stem
    suggested_id = slug_default(pdf_stem)
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
    tables = typer.prompt("Table handling (structured/auto/image-only)", default=tables)
    ocr = typer.prompt("OCR mode (auto/on/off)", default=ocr)
    picture_descriptions = typer.prompt("Picture descriptions (on/off)", default=picture_descriptions)
    if picture_descriptions == "on":
        vlm_repo_id = typer.prompt("VLM repository ID (optional)", default=vlm_repo_id or "")
        vlm_repo_id = vlm_repo_id or None
    deterministic_ids = typer.confirm("Use deterministic IDs?", default=deterministic_ids)
    compile_pack_now = typer.confirm("Compile LevelDB pack now?", default=compile_pack_now)
    out_dir = Path(typer.prompt("Output directory", default=str(out_dir)))

    return (
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
