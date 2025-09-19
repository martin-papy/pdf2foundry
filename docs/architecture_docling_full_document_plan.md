---
description: Migration plan to a full-document Docling workflow (parse once, reuse)
globs: docs/architecture_docling_full_document_plan.md
alwaysApply: false
---

# Full-Document Docling Workflow Plan

## Rationale

- Current pipeline converts the PDF with Docling twice: once in `ingest/docling_parser.parse_pdf_structure` (for outline) and again in `cli.convert` before `extract_semantic_content` (for per-page HTML/images). This duplicates work and makes extension harder.
- Proposed approach: treat the PDF as a single Docling Document built once; persist it to disk (JSON) for reproducibility and reuse. Then drive outline, content extraction, and downstream IR/Foundry mapping from that single source of truth.

## Desired End State (High Level)

- Single Docling conversion: `DocumentConverter(...).convert(pdf).document` executed once per run.
- Persist Docling Document to `dist/<mod-id>/sources/docling.json` (or similar), with an accompanying schema/version note.
- All subsequent steps (`parse_pdf_structure`, `extract_semantic_content`) accept a `DocumentLike` rather than re-converting. Outline detection (bookmarks/heuristics) operates on that in-memory document; content extraction uses the same instance.
- Optionally, support `--docling-json <path>` to skip PDF read entirely and operate from a saved Docling Document (enables faster iteration and later features).

## Impacted Modules and Changes

- `src/pdf2foundry/cli.py`

  - Remove the second Docling conversion block (currently lines around the `# 2) Extract semantic content` section).
  - Move Docling conversion earlier, immediately after path/args validation, and pass the resulting `dl_doc` down to both structure parsing and content extraction functions.
  - New optional flags:
    - `--docling-json PATH` (mutually exclusive with `pdf` input) or complementary: if provided, load Docling document from JSON instead of reading the PDF.
    - `--write-docling-json/--no-write-docling-json` (default: yes) to persist the in-memory Docling doc.
  - Persist: write the Docling Document JSON to `sources/docling.json` (consider a gzipped variant later if size warrants).

- `src/pdf2foundry/ingest/docling_parser.py`

  - Refactor `parse_pdf_structure` to accept a `DocumentLike` object directly (instead of a `Path` to the PDF). Expose a thin helper `load_docling_document(pdf_path)` for callers who do need to load from PDF.
  - Remove its internal converter creation and `conv.convert(...)` call; rely on injected `doc`.
  - Keep heuristics and bookmarks extraction unchanged, operating on `doc`.

- `src/pdf2foundry/ingest/content_extractor.py`

  - Already accepts a `DocumentLike` with `num_pages()` and `export_to_html(...)`; no change required other than ensuring the same `doc` instance is reused.

- `src/pdf2foundry/transform/*`

  - No structural changes required. `layout.flatten_page_html` optionally benefits from richer `doc.pages[*].blocks` if present (already supported).

- `src/pdf2foundry/builder/ir_builder.py`

  - No interface change; continues to consume `ParsedDocument` and `ParsedContent` regardless of how those are produced.

- `src/pdf2foundry/docling_env.py`

  - No change required. Consider adding a small utility in a later iteration to report serialization capabilities.

## Serialization Strategy (Docling Document → JSON)

- Prefer Docling's native serialization if available (e.g., `document.to_json()` / `document.dump()`); otherwise implement a safe subset serializer focusing on fields we use: `num_pages`, `pages[*].blocks` (bbox/text/attrs), outline/bookmarks structures.
- When saving, include metadata: `{ "pdf2foundryDoclingSchema": 1, "doclingVersion": "x.y.z" }`.
- When loading from JSON, reconstruct a lightweight `DocumentLike` that provides `num_pages()`, `export_to_html(page_no=...)`, and minimal structural access needed by layout heuristics. If HTML export isn’t reconstructible, fallback to storing per-page HTML alongside.

## CLI Flow (New)

1. Resolve inputs and output directories; ensure `assets/`, `sources/journals/`, `styles/` exist.
1. Build or load Docling document:
   - If `--docling-json` provided: load from JSON.
   - Else: run a single `DocumentConverter` with `generate_picture_images=True`, `generate_page_images=True`, `do_ocr=False` (same as current second conversion), capture `dl_doc`.
   - If `--write-docling-json`: persist to `sources/docling.json`.
1. Parse structure: `parsed_doc = parse_pdf_structure(doc=dl_doc, on_progress=...)` (signature changed).
1. Extract content: `content = extract_semantic_content(doc=dl_doc, out_assets=assets_dir, table_mode=tables, ...)`.
1. Build IR and map to Foundry entries, optionally prepend TOC, write sources and `module.json`, as today.

## API Signatures (Proposed)

```python
# ingest/docling_parser.py
def load_docling_document(pdf: Path, *, images: bool = True, ocr: bool = False) -> DocumentLike: ...

def parse_pdf_structure(doc: DocumentLike, on_progress: ProgressCallback = None) -> ParsedDocument: ...

# cli.py (convert)
dl_doc = load_docling_document(pdf)  # or load from --docling-json
parsed_doc = parse_pdf_structure(dl_doc, on_progress=_emit)
content = extract_semantic_content(dl_doc, assets_dir, tables, on_progress=_emit)
```

## Tests Impact

- `tests/test_ingest_docling_parser.py`

  - Update to call `parse_pdf_structure(doc=...)` instead of passing a temp PDF path with monkeypatched modules. The existing `_Doc` stub remains valid.

- `tests/test_cli_convert.py`

  - Adjust to reflect single conversion path if tests currently rely on double-conversion behavior. Introduce a test for `--docling-json` input path.

- Other tests (content extraction, IR, mapping) remain unchanged.

## Migration Steps

1. Implement `load_docling_document(pdf: Path, ...)` in `ingest/docling_parser.py` (or a sibling `loader.py`).
1. Change `parse_pdf_structure` signature to take `doc` instead of `pdf: Path`; adapt code to use provided `doc` only.
1. Update `cli.convert`:
   - Create/load a single `dl_doc`.
   - Pass `dl_doc` to `parse_pdf_structure` and `extract_semantic_content`.
   - Remove the second converter creation.
   - Add `--docling-json` and `--write-docling-json` options; implement JSON persistence/loading.
1. Add a minimal serializer/loader for Docling Document JSON if Docling lacks a stable one in our version. Otherwise, use Docling’s native.
1. Update tests for the new signatures & flags; add a roundtrip test that loads from `docling.json` and produces identical output.
1. Document the new flow in README and CLI help.

## Risks & Mitigations

- Docling API variability: use defensive getattr access (current code already does this) and version-gate optional features in serializer.
- JSON size: keep as optional (`--write-docling-json` default on can be revisited) and consider gzip (`docling.json.gz`).
- HTML export from JSON: if not trivially reconstructible, store per-page HTML snapshots alongside or rely on Docling’s native JSON which may support regeneration.

## Acceptance Criteria

- One Docling conversion per run when starting from PDF.
- Ability to run from a saved `docling.json` without opening the PDF.
- No regressions in outline parsing, content extraction, IR building, and Foundry output tests.
- New CLI options documented and covered by tests.
