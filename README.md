# PDF2Foundry

Convert born-digital PDFs into a Foundry VTT v13 module compendium.

## Installation (dev)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev]
```

Enable pre-commit hooks:

```bash
pre-commit install
```

## Development

### Continuous Integration

The project uses GitHub Actions for CI/CD with the following checks:

- **Linting & Formatting**: Ruff, Black, and MyPy
- **Testing**: pytest with coverage reporting
- **Build**: Package building and installation testing
- **Cross-platform**: Testing on Ubuntu, Windows, and macOS

All checks must pass before merging. The CI runs on Python 3.12 and 3.13.

## CLI Usage

```bash
pdf2foundry --help
```

### Command

```bash
pdf2foundry convert \
  --pdf "My Book.pdf" \
  --mod-id "pdf2foundry-my-book" \
  --mod-title "My Book (PDF Import)" \
  --author "ACME" \
  --license "OGL" \
  --pack-name "my-book-journals" \
  --toc/--no-toc \
  --tables auto|structured|image-only \
  --ocr auto|on|off \
  --picture-descriptions on|off \
  --vlm-repo-id <huggingface-model-id> \
  --deterministic-ids/--no-deterministic-ids \
  --out-dir dist \
  --compile-pack/--no-compile-pack \
  --docling-json cache.json \
  --write-docling-json/--no-write-docling-json \
  --fallback-on-json-failure/--no-fallback-on-json-failure
```

- `--pdf` (required): Path to source PDF

- `--mod-id` (required): Module ID

- `--mod-title` (required): Module title

- `--author`: Author name

- `--license`: License string

- `--pack-name`: Pack name (default: `<mod-id>-journals`)

- `--toc`: Generate TOC entry (default: enabled)

- `--tables`: Table processing mode - `auto` (default), `structured`, or `image-only`

- `--ocr`: OCR processing mode - `auto` (default), `on`, or `off`

- `--picture-descriptions`: Enable image captions - `on` or `off` (default)

- `--vlm-repo-id`: Hugging Face model ID for image captions (required when `--picture-descriptions=on`)

- `--deterministic-ids`: Use deterministic IDs (default: enabled)

  (compendium folders are native in v13)

- `--out-dir`: Output directory (default: `dist`)

- `--compile-pack`: Compile JSON sources to LevelDB pack using Foundry CLI (default: disabled)

- `--docling-json`: Path to JSON cache file. If exists and valid, load; otherwise convert and save to this path

- `--write-docling-json`: Save Docling JSON to default cache location (default: disabled)

- `--fallback-on-json-failure`: If JSON loading fails, fall back to conversion (default: disabled)

### Feature Examples

**Basic conversion (default behavior):**

```bash
pdf2foundry convert --pdf "book.pdf" --mod-id "my-book" --mod-title "My Book"
```

**With structured table extraction:**

```bash
pdf2foundry convert --pdf "book.pdf" --mod-id "my-book" --mod-title "My Book" \
  --tables structured
```

**With OCR for scanned pages:**

```bash
pdf2foundry convert --pdf "book.pdf" --mod-id "my-book" --mod-title "My Book" \
  --ocr on
```

**With image captions:**

```bash
pdf2foundry convert --pdf "book.pdf" --mod-id "my-book" --mod-title "My Book" \
  --picture-descriptions on --vlm-repo-id "Salesforce/blip-image-captioning-base"
```

**All features enabled:**

```bash
pdf2foundry convert --pdf "book.pdf" --mod-id "my-book" --mod-title "My Book" \
  --tables structured --ocr auto --picture-descriptions on \
  --vlm-repo-id "Salesforce/blip-image-captioning-base"
```

### Optional Dependencies

Some features require additional system dependencies:

- **OCR features** (`--ocr on|auto`): Requires Tesseract OCR

  ```bash
  # macOS
  brew install tesseract

  # Ubuntu/Debian
  sudo apt-get install tesseract-ocr

  # Windows
  # Download from https://github.com/UB-Mannheim/tesseract/wiki
  ```

- **Image captions** (`--picture-descriptions on`): Requires transformers library and a VLM model

  - Models are downloaded automatically from Hugging Face
  - Popular models: `Salesforce/blip-image-captioning-base`, `microsoft/DialoGPT-medium`
  - First run may take time to download models

## Output Layout

```text
<out-dir>/<mod-id>/
  module.json
  assets/
  styles/pdf2foundry.css
  sources/
    journals/*.json
    docling.json        # when JSON cache is written
  packs/<pack-name>/
```

## Single-Pass Ingestion

PDF2Foundry uses a single-pass ingestion design for efficiency:

1. **One Conversion**: Each PDF is converted to a Docling document exactly once per run
1. **JSON Caching**: Optionally cache the Docling document as JSON to avoid re-conversion
1. **Reuse**: The same Docling document instance is used for both structure parsing and content extraction

### Caching Examples

```bash
# Convert and cache for future runs
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" \
  --docling-json book-cache.json

# Subsequent runs load from cache (much faster)
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" \
  --docling-json book-cache.json

# Auto-save to default location
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" \
  --write-docling-json
```

See [docs/PRD.md](docs/PRD.md) and [docs/architecture_and_flow.md](docs/architecture_and_flow.md) for details.

## Pack Compilation (Foundry CLI)

- Requires Node.js (LTS) and the Foundry CLI as a devDependency (already configured in `package.json`).
- You can compile during `convert` with `--compile-pack`, or manually via npm:

```bash
npm run compile:pack --modid=<mod-id> --packname=<mod-id>-journals
```

Under the hood this runs:

```bash
npx @foundryvtt/foundryvtt-cli compilePack \
  --input dist/<mod-id>/sources/journals \
  --output dist/<mod-id>/packs/<mod-id>-journals
```
