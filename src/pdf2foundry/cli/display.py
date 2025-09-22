"""Configuration display utilities for CLI."""

from pathlib import Path

import typer

from pdf2foundry.model.pipeline_options import PdfPipelineOptions


def display_configuration(
    pdf: Path,
    mod_id: str,
    mod_title: str,
    out_dir: Path,
    pack_name: str,
    author: str,
    license: str,
    toc: bool,
    tables: str,
    ocr: str,
    pipeline_options: PdfPipelineOptions,
    deterministic_ids: bool,
) -> None:
    """Display the current configuration to the user."""
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
    typer.echo(f"👁️  OCR Mode: {ocr}")
    typer.echo(f"🖼️  Picture Descriptions: {'Yes' if pipeline_options.picture_descriptions else 'No'}")
    if pipeline_options.picture_descriptions and pipeline_options.vlm_repo_id:
        typer.echo(f"🤖 VLM Repository: {pipeline_options.vlm_repo_id}")
    typer.echo(f"🔗 Deterministic IDs: {'Yes' if deterministic_ids else 'No'}")


def display_docling_cache_behavior(
    docling_json: Path | None,
    write_docling_json: bool,
    fallback_on_json_failure: bool,
    out_dir: Path,
    mod_id: str,
) -> None:
    """Display Docling JSON cache behavior summary."""
    if docling_json is not None and write_docling_json:
        typer.echo("🗃️  Docling JSON: --docling-json provided; " "--write-docling-json is ignored (PATH semantics apply)")
    if docling_json is not None:
        typer.echo(f"🗃️  Docling JSON cache: {docling_json} (load if exists; else convert then save)")
    elif write_docling_json:
        default_json_path = out_dir / mod_id / "sources" / "docling.json"
        typer.echo(f"🗃️  Docling JSON cache: will write to default path {default_json_path} when converting")
    else:
        typer.echo("🗃️  Docling JSON cache: disabled (no load/save)")
    if fallback_on_json_failure:
        typer.echo("↩️  Fallback on JSON failure: enabled")


def display_validation_warnings(
    pipeline_options: PdfPipelineOptions,
    vlm_repo_id: str | None,
) -> None:
    """Display validation warnings for pipeline options."""
    if pipeline_options.picture_descriptions and pipeline_options.vlm_repo_id is None:
        typer.echo(
            "⚠️  Warning: Picture descriptions enabled but no VLM repository ID provided. "
            "Image captions will be skipped unless a default model is configured."
        )
    elif not pipeline_options.picture_descriptions and vlm_repo_id is not None:
        typer.echo(
            "⚠️  Warning: VLM repository ID provided but picture descriptions are disabled. "
            "The VLM repository ID will be ignored."
        )
