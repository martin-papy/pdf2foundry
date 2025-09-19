---
description: Unified plan — full-document Docling workflow + capability upgrades
globs: docs/docling_refactor_unified_plan.md
alwaysApply: true
---

# Unified Docling Refactor Plan

## Goals

- Single-pass, full-document Docling ingestion (no duplicate conversions) with optional JSON caching.
- Maximize Docling capabilities for rich PDFs: structured tables, optional OCR, optional picture descriptions, performance knobs, and better multi-column handling.
- Preserve and expose logical structure for robust Foundry mapping while keeping deterministic IDs.

## Architecture Overview (target)

1. Build or load one DoclingDocument (`dl_doc`).
1. Parse outline/bookmarks from `dl_doc` (with heuristics fallback).
1. Extract semantic content from `dl_doc` (HTML per page, images, links, tables) with optional structured tables and enrichments.
1. Build IR and map to Foundry Journal Entries/Pages; write sources and `module.json`.
1. Optionally compile packs via Foundry CLI.

## CLI Flow (new)

1. Resolve inputs/outputs; ensure `dist/<mod-id>/{assets,styles,sources/journals}`.
1. Load/create `dl_doc`:
   - If `--docling-json PATH` provided: load doc from JSON.
   - Else: run a single DocumentConverter using configured `PdfPipelineOptions`.
   - If `--write-docling-json`: persist to `sources/docling.json`.
1. Structure: `parsed_doc = parse_pdf_structure(doc=dl_doc, on_progress=...)`.
1. Content: `content = extract_semantic_content(doc=dl_doc, out_assets=assets_dir, table_mode=tables, ...)`.
1. IR + Foundry: `ir -> entries`, prepend TOC (optional), write sources and `module.json`, optionally compile pack.

## Module Changes

- `src/pdf2foundry/cli.py`

  - Move Docling conversion to a single place; pass `dl_doc` to both structure and content steps.
  - Add flags:
    - `--docling-json PATH`
    - `--write-docling-json/--no-write-docling-json` (default: on)
    - `--tables structured|auto|image-only` (extend existing)
    - `--ocr auto|on|off` (default: off)
    - `--picture-descriptions on|off` (default: off), `--vlm-repo-id <repo>` (advanced)
    - `--pages <spec>` (e.g., `1-10,15,20-`), `--workers <int>` (if backend supports)

- `src/pdf2foundry/ingest/docling_parser.py`

  - New helper: `load_docling_document(pdf: Path, *, images: bool, ocr: bool, tables_mode: str, vlm: bool, pages: str | None, workers: int | None) -> DocumentLike` to centralize converter setup.
  - Change `parse_pdf_structure` to accept `doc: DocumentLike` instead of `pdf: Path`. Keep bookmarks + heuristic fallback.
  - Optional serializer: if Docling has native JSON dump/load, use it. Else provide a minimal subset serializer with schema/version header.

- `src/pdf2foundry/ingest/content_extractor.py`

  - Already accepts `DocumentLike`; extend to optionally capture structured tables and picture descriptions when available from `dl_doc`.
  - Extend `ParsedContent` to include `tables_structured` and optional `caption`/`bbox` on `ImageAsset` (backward compatible defaults).

- `src/pdf2foundry/transform/layout.py`

  - Keep detection; add optional experimental reflow when `--reflow columns` is enabled and geometry is present.

- `src/pdf2foundry/builder/ir_builder.py`

  - No breaking changes. If `tables_structured` exists, allow future enhancement to render semantic HTML tables for sections that contain them.

## Docling Options (wiring)

- Images: `generate_picture_images=True`, `generate_page_images=True`.
- Tables: when `--tables structured`, configure `table_structure_options` for accurate mode.
- OCR: respect `--ocr` value; for `auto`, detect image-dominant pages and enable OCR only there if supported.
- Picture descriptions: when enabled, set `do_picture_description=True` with `picture_description_options`.
- Performance: honor `--pages` and `--workers` when backend supports.

## Data Model Adjustments

- `ParsedContent` additions:
  - `tables_structured: list[StructuredTable]` (new type with cells, spans, and page anchors).
  - `ImageAsset.caption: str | None`, `ImageAsset.bbox: tuple[float,float,float,float] | None`.
  - Defaults keep all fields optional to avoid breaking existing code/tests.

## Tests

- Update `tests/test_ingest_docling_parser.py` to pass `doc` to `parse_pdf_structure`.
- Add CLI tests for:
  - `--docling-json` roundtrip (load saved JSON produces same output)
  - `--tables structured` path
  - `--ocr on` and `--ocr auto` paths
  - `--picture-descriptions on` (mock VLM)
  - `--pages` selection on small fixtures

## Migration Steps

1. Implement `load_docling_document` and refactor `parse_pdf_structure(doc=...)`.
1. Update `cli.convert` to single-pass Docling with JSON cache support and new flags.
1. Extend `ParsedContent` and extraction to support structured tables and captions (feature-gated by flags).
1. Introduce experimental multi-column reflow flag (no-op default).
1. Add tests and update docs/README and `--help`.

## Risks & Mitigations

- Docling API variability: continue defensive getattr; gate advanced features behind flags.
- JSON size: optional save, consider gzip later.
- Performance: expose page/workers flags; document trade-offs.
- Determinism: keep deterministic IDs and canonical paths unchanged.

## Acceptance Criteria

- One Docling conversion per run (when starting from PDF).
- Optional `docling.json` cache path supported.
- Structured tables/ocr/picture descriptions work when enabled; defaults preserve current behavior.
- No regressions in existing tests; new tests cover added flags/paths.
