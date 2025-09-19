---
description: Docling capabilities vs current usage in PDF2Foundry and recommendations
globs: docs/docling_capabilities_gap_analysis.md
alwaysApply: false
---

# Docling Capabilities Gap Analysis

## Scope

Assess whether we leverage Docling effectively for visually rich PDFs (images, complex tables, multi-columns, nested sections) and propose targeted improvements. This complements the full-document workflow plan in `architecture_docling_full_document_plan.md`.

## What Docling Can Do (relevant highlights)

- Full-document parse to a unified DoclingDocument with layout, reading order, outline/bookmarks.
- HTML/Markdown export per page or whole-document; configurable content layers and image modes.
- Table structure recognition (TableFormer variants) producing structured tables beyond image placeholders.
- Image extraction; optional AI-generated picture descriptions via VLMs (picture description options).
- OCR for scanned PDFs/pages; backend flexibility; performance knobs (page ranges, parallelism).
- Lossless/structured JSON export of the document graph (version-dependent), enabling caching and reproducible downstream.

## Our Current Usage (observed in code)

- We already:

  - Build a Docling document and call `export_to_html(page_no=...)` with optional `ContentLayer`/`ImageRefMode` when `docling-core` is present (`ingest/content_extractor.py`).
  - Extract base64-embedded images and rewrite to `assets/` with deterministic naming.
  - Detect tables in HTML, but only with a binary strategy: keep as HTML or replace with image placeholders; no use of Docling structured tables.
  - Parse outline/bookmarks from the Docling doc for chapters/sections (`ingest/docling_parser.py`), with a heading heuristic fallback.
  - Duplicate Docling conversion in `cli.py` (outline path vs content path), which we plan to unify.

- We do not yet:

  - Enable/consume structured table outputs from Docling (e.g., TableFormer modes) to build semantic tables.
  - Leverage picture description VLMs to enrich figures/captions for better semantic linking.
  - Persist the DoclingDocument to JSON and reload it to avoid reprocessing.
  - Configure OCR path for scanned pages (we currently set `do_ocr=False` throughout).
  - Use performance knobs (page range, parallel options) for very large PDFs.

## Gaps and Recommendations

- Structured Tables

  - Gap: We only pattern-match `<table>` tags from HTML export; complex tables or ones reconstructed by Docling’s table model are not consumed.
  - Reco: Expose a `--tables structured|auto|image-only` option. When `structured`, configure `PdfPipelineOptions.table_structure_options` with an accurate mode (e.g., TableFormer accurate) and plumb captured logical tables into our `ParsedContent` (new data structure) and IR.

- Picture/Image Enrichment

  - Gap: Images are extracted but semantically unlabeled; captions/figure numbers are not linked.
  - Reco: Optionally enable `do_picture_description` with a small VLM (configurable). Store descriptions in `ParsedContent` next to `ImageAsset` and render as captions. Keep this off by default to avoid extra model deps.

- OCR for Scanned/Hybrid PDFs

  - Gap: OCR is disabled; scanned content will be missed.
  - Reco: Add `--ocr auto|on|off`. For `auto`, probe doc to detect text vs image-heavy pages and enable OCR only where needed.

- Full-Document Parse and Caching

  - Gap: Double conversion and no caching.
  - Reco: Implement single conversion with optional `--docling-json` load/save as per architecture plan; enable quick iteration and reproducibility.

- Performance Controls

  - Gap: No page-range or parallel controls.
  - Reco: Add `--pages` (e.g., `1-10,15,20-`) and `--workers N` to pass to Docling if supported by the backend; document trade-offs.

- Multi-Column Handling

  - Gap: We only warn and rely on Docling’s reading order; no reflow.
  - Reco: Keep default behavior but add an experimental `--reflow columns` mode that, when Docling exposes block geometry, can split and concatenate columns left-to-right during HTML merge. Start as opt-in.

## Proposed API/Model Adjustments

- `ParsedContent` additions:

  - `tables_structured: list[StructuredTable]` capturing table cells with row/col spans and page location.
  - `images` gains optional `caption: str | None` and `bbox: tuple[float,float,float,float] | None` when available.

- CLI options:

  - `--tables structured|auto|image-only` (default: auto)
  - `--ocr auto|on|off` (default: off)
  - `--docling-json PATH`, `--write-docling-json/--no-write-docling-json`
  - `--pages <spec>`, `--workers <int>`
  - `--picture-descriptions on|off` with a nested `--vlm-repo-id` for advanced users

## Acceptance Criteria for Feature Parity Upgrade

- Single-pass Docling conversion with optional JSON caching.
- Structured tables available in the pipeline when enabled; fallback paths preserved.
- Optional OCR and picture descriptions correctly toggled via CLI.
- No regressions in Foundry mappings; HTML content remains wrapped and images resolved to module paths.

## Next Steps (implementation-ready)

1. Implement full-document conversion and JSON caching (see architecture plan).
1. Add new CLI flags and plumb to `PdfPipelineOptions` (OCR, images, table mode, picture description).
1. Extend `ParsedContent` with `StructuredTable` and image captions; adapt IR builder to render HTML tables or images accordingly.
1. Add tests:
   - Verify `structured` table mode produces non-empty structured tables on synthetic inputs.
   - Verify `--ocr on` extracts text from image-only stubs.
   - Verify picture descriptions are attached when enabled (mock VLM call where needed).
1. Document all options in README and `--help`.
