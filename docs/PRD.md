# Product Requirements Document

**Project Name:** PDF2Foundry
**Version:** 1.0 (Initial Release)
**Prepared For:** Development Team
**Foundry VTT Compatibility:** v12+
**Scope:** Convert a born-digital PDF into an installable Foundry VTT module containing a compendium of Journal Entries and Pages with images, HTML formatting, and internal navigation.

______________________________________________________________________

## 1. Project Overview

PDF2Foundry is a Python CLI tool that ingests a **born-digital PDF** and outputs a **Foundry VTT v12+ module**. The module will contain a **compendium pack** (`JournalEntry` type) where:

- Each **Chapter** in the PDF becomes a **Journal Entry**.
- Each **Section** within a chapter becomes a **Journal Page** (format: HTML).
- **Images** are extracted and saved as module assets, referenced by HTML `<img>` tags.
- **Tables** are converted to HTML `<table>` when possible; otherwise embedded as images.
- **Internal links** are converted into Foundry-native `@UUID[...]` links.
- A **TOC Journal Entry** is generated for navigation.
- Structure (root folder, chapter folders) is preserved using **Compendium Folders** (dependency).

______________________________________________________________________

## 2. Goals & Non-Goals

### Goals

- Automate conversion of a PDF into a Foundry-ready compendium.
- Preserve **structure** (book → chapters → sections).
- Preserve **content fidelity** (text, headings, lists, images, tables, links).
- Produce **deterministic IDs** for UUID stability across re-runs.
- Generate a **module folder** with everything needed for installation.
- Support **internal cross-references** and **external hyperlinks**.
- Provide a **TOC Journal Entry** for quick navigation.

### Non-Goals

- OCR for scanned PDFs (out of scope in v1).
- Full WYSIWYG fidelity of PDF layout (focus is on readable HTML structure).
- Advanced table styling beyond standard `<table>`.
- Compression or optimization of images.

______________________________________________________________________

## 3. Target Users

- **GMs and content creators** who legally own PDF content and want to bring it into Foundry VTT.
- Developers who may later extend the tool (multi-column layouts, OCR, etc.).

______________________________________________________________________

## 4. Functional Requirements

### 4.1 CLI Tool

- Command: `pdf2foundry [OPTIONS]`

- Input:

  - `--pdf <path>`: Path to source PDF.
  - `--out-dir <path>`: Output directory for generated module.

- Metadata:

  - `--mod-id <string>`: Module ID (required, must be unique).
  - `--mod-title <string>`: Module Title (required).
  - `--author <string>`: Author name.
  - `--license <string>`: License string.
  - `--pack-name <string>`: Compendium pack name (default: `<mod-id>-journals`).

- Behavior flags:

  - `--toc yes|no` (default: yes).
  - `--tables auto|image-only` (default: auto).
  - `--deterministic-ids yes|no` (default: yes).
  - `--depend-compendium-folders yes|no` (default: yes).

### 4.2 PDF Parsing

- Extract **outline/bookmarks** for chapters/sections when available.
- Fallback: detect headings using font size/weight.
- Flatten multi-column layouts to linear order.
- Extract text, lists, headings, inline styles.
- Extract images in original format/resolution.
- Extract link annotations.

### 4.3 Structure Mapping

- **Root folder** in compendium = PDF title.
- **Chapter → Journal Entry**.
- **Section → Journal Page** within entry.
- **TOC Entry**: contains UUID links to all chapters/sections.
- **Compendium Folders** integration: encode folder structure in flags.

### 4.4 Content Conversion

- Journal Page `type`: `"text"`.
- Journal Page `text.format`: `1` (HTML).
- Wrap content in `<div class="pdf2foundry">` for safe CSS scoping.
- Insert `<img src="modules/<mod-id>/assets/...">` for images.
- Convert tables to `<table>` if parsing successful; else rasterize.
- Replace internal references with `@UUID[...]`.

### 4.5 IDs & UUIDs

- Generate deterministic `_id` via `sha1(<mod-id>|<chapter-path>|<section-path>)[:16]`.
- Ensure stable UUIDs across runs.

### 4.6 Packaging

- Generate the following module structure:

  ```test
  <out-dir>/<mod-id>/
    module.json
    assets/...
    styles/pdf2foundry.css
    sources/journals/*.json
    packs/<pack-name>/  (LevelDB after compile)
  ```

- `module.json` must include:

  - `id`, `title`, `version`, `compatibility` (v12+).
  - `packs`: type `JournalEntry`.
  - `dependencies`: include `Compendium Folders` if `--depend-compendium-folders=yes`.

- Use **Foundry official CLI** (Node-based) to compile JSON into LevelDB pack.

______________________________________________________________________

## 5. Non-Functional Requirements

- **Compatibility:** Foundry v12+.
- **Performance:** Should handle PDFs up to 500 pages without crashing.
- **Extensibility:** Clear architecture to support OCR, compression, GUI in future versions.
- **Reliability:** Deterministic ID generation ensures UUID stability.
- **Maintainability:** Code organized with modules for parsing, HTML conversion, packaging.

______________________________________________________________________

## 6. Dependencies

- **Python libraries:**

  - `PyMuPDF (fitz)` → text, layout, images, bookmarks.
  - `Camelot` → table detection.
  - `Pillow` → rasterization of vector art/tables.
  - `Jinja2` → HTML templating.

- **Node tooling:**

  - `@foundryvtt/foundryvtt-cli` → compile JSON sources to LevelDB packs.

- **Foundry add-on:**

  - **Compendium Folders** → required dependency if `--depend-compendium-folders=yes`.

______________________________________________________________________

## 7. Error Handling

- **No bookmarks found:** fallback to heading heuristic; log warning.
- **Table parsing fails:** fallback to image snapshot; log info.
- **Broken cross-ref:** leave plain text; log warning.
- **PDF parse errors:** stop gracefully with error message.

______________________________________________________________________

## 8. Deliverables

- Python CLI (`pdf2foundry`) installable via `pip`.
- Developer documentation (README with setup, usage, examples).
- Sample output module for verification.
- Unit tests for ID generation, TOC linking, and compendium JSON schema validation.

______________________________________________________________________

## 9. Success Criteria

- GM can install the generated module into a v12 Foundry world.

- Journal compendium appears with correct name and contents.

- Importing entries preserves:

  - Chapters → Journal Entries.
  - Sections → Journal Pages.
  - Images loaded correctly.
  - TOC links navigate correctly via `@UUID[...]`.

- With Compendium Folders installed, entries are correctly nested into folder hierarchy.

______________________________________________________________________

## 10. Future Enhancements (not in v1)

- OCR for scanned PDFs.
- Multi-column preservation.
- Configurable image compression.
- Advanced cross-reference resolution.
- GUI front-end (Electron/Tauri).

______________________________________________________________________

## 11. Related Documents

- **Technical Feasibility**: [technical_feasibility.md](mdc:docs/technical_feasibility.md)
- **Architecture & Flow (High-level design and pipeline)**: [architecture_and_flow.md](mdc:docs/architecture_and_flow.md)
- **Templates Overview**: [sample.md](mdc:docs/sample.md)
- **Sample module manifest**: [sample.module.json](mdc:docs/sample.module.json)
- **Sample Journal Entry source**: [sample.journal_entry.json](mdc:docs/sample.journal_entry.json)
