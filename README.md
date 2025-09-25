# PDF2Foundry

Convert born-digital PDFs into a Foundry VTT v13 module compendium with rich content extraction, structured tables, OCR support, and AI-powered image descriptions.

## Quick Start

```bash
# Install and convert a PDF
pip install pdf2foundry
pdf2foundry convert "My Book.pdf" --mod-id "my-book" --mod-title "My Book"
```

## Developer Setup

For development setup, testing, and contribution guidelines, see [docs/development.md](docs/development.md).

## Features

- **Structure Preservation**: PDF chapters → Journal Entries, sections → Journal Pages
- **Rich Content**: Images, tables, links, and text with proper formatting
- **Structured Tables**: Extract semantic table structure when possible
- **OCR Support**: Optional OCR for scanned pages or low-text-coverage areas
- **Image Descriptions**: AI-powered image captions using Vision-Language Models
- **Performance**: Multi-worker processing and page selection for large documents
- **Caching**: Single-pass ingestion with optional JSON caching for faster re-runs
- **Deterministic IDs**: Stable UUIDs for reliable cross-references across runs
- **Foundry Integration**: Native v13 compendium folders and pack compilation

## Installation

### System Requirements

PDF2Foundry requires the following system dependencies:

- **Python 3.12+**
- **Node.js 24+** (for Foundry CLI pack compilation)
- **Tesseract OCR** (for OCR features)

### System Dependencies

#### Node.js 24+ and Foundry CLI

Required for pack compilation features:

```bash
# Install Node.js 24+ (visit https://nodejs.org for installers)
# Then install Foundry CLI in your project directory:
npm install @foundryvtt/foundryvtt-cli
```

#### Tesseract OCR

Required for OCR functionality:

```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# Windows
# Download from https://github.com/UB-Mannheim/tesseract/wiki
```

### Python Installation

#### Production Install

```bash
pip install pdf2foundry
```

#### Development Install

```bash
git clone https://github.com/martin-papy/pdf2foundry.git
cd pdf2foundry
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python -m pip install -U pip
python -m pip install -e .[dev]
```

Enable pre-commit hooks for development:

```bash
pre-commit install
```

### Included Features

PDF2Foundry includes all advanced features by default:

- **OCR Support**: Tesseract integration for scanned documents
- **AI Image Descriptions**: Vision-Language Models via transformers
- **ML Processing**: PyTorch and related libraries

**Note**: ML models are downloaded automatically from Hugging Face on first use (~1GB for default BLIP model).

## Development

### Architecture

PDF2Foundry uses a unified single-pass architecture powered by [Docling](https://github.com/DS4SD/docling):

1. **Single Conversion**: Each PDF is processed exactly once using Docling's DocumentConverter
1. **Structure Extraction**: Parse PDF bookmarks/outline with heuristic fallbacks
1. **Content Extraction**: Extract semantic content (HTML, images, tables) from the same document
1. **Foundry Mapping**: Build Intermediate Representation and map to Journal Entries/Pages
1. **Output Generation**: Write module.json, sources, assets, and optionally compile packs

### Continuous Integration

The project uses GitHub Actions for CI/CD with the following checks:

- **Linting & Formatting**: Ruff, Black, and MyPy (strict mode)
- **Testing**: pytest with 90%+ coverage requirement
- **Build**: Package building and installation testing
- **Cross-platform**: Testing on Ubuntu, Windows, and macOS

#### E2E & Performance Testing

- **E2E Tests**: Comprehensive end-to-end testing on pull requests and main branch
- **Performance Monitoring**: Automated performance regression detection with configurable thresholds (default: 20%)
- **Artifact Collection**: Test reports, performance metrics, and cache data preserved
- **PR Integration**: Automated performance summaries posted to pull requests

#### Performance Baseline Management

To update the performance baseline after improvements:

```bash
# Copy current results as new baseline
cp tests/e2e/perf/latest.json tests/e2e/perf/baseline.json
git add tests/e2e/perf/baseline.json
git commit -m "Update performance baseline"
```

#### Manual Workflow Triggers

You can manually trigger the E2E workflow using GitHub's workflow_dispatch feature in the Actions tab.

All checks must pass before merging. The CI runs on Python 3.12+.

## CLI Usage

### Basic Command

```bash
pdf2foundry convert <PDF_FILE> --mod-id <MODULE_ID> --mod-title <MODULE_TITLE> [OPTIONS]
```

### Full Command Reference

```bash
pdf2foundry convert \
  "My Book.pdf" \
  --mod-id "my-book" \
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
  --fallback-on-json-failure/--no-fallback-on-json-failure \
  --pages "1,5-10,15" \
  --workers 4 \
  --reflow-columns \
  --no-ml \
  --verbose/-v
```

### Command Options

#### Required Options

- `<PDF_FILE>`: Path to source PDF file
- `--mod-id`: Unique module identifier (lowercase, hyphens, no spaces)
- `--mod-title`: Display name for the module

#### Content Processing Options

- `--tables auto|structured|image-only`: Table handling mode (default: `auto`)

  - `auto`: Try structured extraction, fallback to image if needed
  - `structured`: Always extract semantic table structure
  - `image-only`: Always rasterize tables as images

- `--ocr auto|on|off`: OCR processing mode (default: `auto`)

  - `auto`: OCR pages with low text coverage
  - `on`: Always apply OCR to all pages
  - `off`: Disable OCR completely

- `--picture-descriptions on|off`: Generate AI image captions (default: `off`)

- `--vlm-repo-id <model>`: Hugging Face VLM model ID (required with `--picture-descriptions on`)

#### Performance Options

- `--pages "<spec>"`: Process specific pages (e.g., `"1,5-10,15"`, default: all pages)
- `--workers <n>`: Number of worker processes for CPU-bound operations (default: 1)
- `--reflow-columns`: Experimental multi-column text reflow (default: disabled)
- `--no-ml`: Disable ML features (VLM, advanced OCR) for faster processing or CI environments

#### Caching Options (Single-Pass Ingestion)

- `--docling-json <path>`: JSON cache file path. Load if exists, otherwise save after conversion
- `--write-docling-json`: Save to default cache location (`dist/<mod-id>/sources/docling.json`)
- `--fallback-on-json-failure`: Fall back to conversion if JSON loading fails

#### Module Options

- `--author <name>`: Author name for module metadata
- `--license <license>`: License string for module metadata
- `--pack-name <name>`: Compendium pack name (default: `<mod-id>-journals`)
- `--toc/--no-toc`: Generate Table of Contents entry (default: enabled)
- `--deterministic-ids/--no-deterministic-ids`: Use SHA1-based stable IDs (default: enabled)

#### Output Options

- `--out-dir <path>`: Output directory (default: `dist`)
- `--compile-pack/--no-compile-pack`: Compile to LevelDB using Foundry CLI (default: disabled)
- `--verbose`, `-v`: Increase verbosity (use `-v` for info, `-vv` for debug output)

### Usage Examples

#### Basic Conversion

```bash
# Minimal command - uses all defaults
pdf2foundry convert "My Book.pdf" --mod-id "my-book" --mod-title "My Book"

# With author and license metadata
pdf2foundry convert "Game Manual.pdf" --mod-id "game-manual" --mod-title "Game Manual" \
  --author "John Doe" --license "OGL"
```

#### Content Processing Features

```bash
# Structured table extraction (best for data-heavy PDFs)
pdf2foundry convert "Rulebook.pdf" --mod-id "rulebook" --mod-title "Player Rulebook" \
  --tables structured

# Force OCR on all pages (for scanned PDFs)
pdf2foundry convert "Scanned Book.pdf" --mod-id "scanned-book" --mod-title "Scanned Book" \
  --ocr on

# AI-powered image descriptions
pdf2foundry convert "Bestiary.pdf" --mod-id "bestiary" --mod-title "Monster Manual" \
  --picture-descriptions on --vlm-repo-id "Salesforce/blip-image-captioning-base"

# Disable TOC generation
pdf2foundry convert "Simple Guide.pdf" --mod-id "guide" --mod-title "Quick Guide" \
  --no-toc
```

#### Performance Optimization

```bash
# Process specific pages with multiple workers
pdf2foundry convert "Large Manual.pdf" --mod-id "manual" --mod-title "Game Manual" \
  --pages "1-10,50-60" --workers 4

# Experimental multi-column reflow for academic papers
pdf2foundry convert "Research Paper.pdf" --mod-id "paper" --mod-title "Research Paper" \
  --reflow-columns

# High-performance conversion with all optimizations
pdf2foundry convert "Journal.pdf" --mod-id "journal" --mod-title "Academic Journal" \
  --pages "5-25" --workers 3 --reflow-columns --verbose
```

#### Caching and Re-runs

```bash
# Convert and cache for future runs
pdf2foundry convert "Book.pdf" --mod-id "my-book" --mod-title "My Book" \
  --docling-json "book-cache.json"

# Subsequent runs load from cache (much faster)
pdf2foundry convert "Book.pdf" --mod-id "my-book" --mod-title "My Book" \
  --docling-json "book-cache.json"

# Auto-save to default cache location
pdf2foundry convert "Book.pdf" --mod-id "my-book" --mod-title "My Book" \
  --write-docling-json

# Robust caching with fallback
pdf2foundry convert "Book.pdf" --mod-id "my-book" --mod-title "My Book" \
  --docling-json "cache.json" --fallback-on-json-failure
```

#### Advanced Workflows

```bash
# All features enabled for maximum quality
pdf2foundry convert "Complete Manual.pdf" --mod-id "complete-manual" --mod-title "Complete Manual" \
  --tables structured --ocr auto --picture-descriptions on \
  --vlm-repo-id "Salesforce/blip-image-captioning-base" --workers 2 --verbose

# Production workflow with pack compilation
pdf2foundry convert "Module.pdf" --mod-id "my-module" --mod-title "My Module" \
  --author "Publisher" --license "OGL" --compile-pack --write-docling-json

# Debug workflow with maximum verbosity
pdf2foundry convert "Problem.pdf" --mod-id "debug" --mod-title "Debug Module" \
  --verbose --verbose --no-compile-pack
```

## Output Structure

PDF2Foundry generates a complete Foundry VTT module with the following structure:

```text
<out-dir>/<mod-id>/
├── module.json                 # Module manifest
├── assets/                     # Extracted images and media
│   ├── image_001.png
│   └── ...
├── styles/
│   └── pdf2foundry.css        # Module-specific styles
├── sources/
│   ├── journals/              # Journal Entry source files
│   │   ├── chapter_001.json
│   │   ├── chapter_002.json
│   │   └── ...
│   └── docling.json          # Cached Docling document (optional)
└── packs/
    └── <pack-name>/          # Compiled LevelDB pack (optional)
        ├── 000001.ldb
        └── ...
```

### Module Structure

- **Journal Entries**: Each PDF chapter becomes a Journal Entry
- **Journal Pages**: Each chapter section becomes a Journal Entry Page
- **Table of Contents**: Optional TOC entry with navigation links
- **Compendium Folders**: Native v13 folder organization
- **Deterministic IDs**: Stable SHA1-based UUIDs for reliable cross-references

## Technical Documentation

For developers and advanced users:

- **[Performance Guide](docs/performance.md)**: Optimization strategies and benchmarks
- **[Product Requirements](docs/PRD.md)**: Complete feature specification
- **[Development Guidelines](docs/development.md)**: Development Guidelines
- **[Architecture and Flow](docs/architecture_and_flow.md)**: General Architecture documentation
- **[E2E testing Strategy](docs/e2e-testing-strategy.md)**: E2e Strategy documentation

## Pack Compilation

PDF2Foundry can compile JSON sources into LevelDB packs for Foundry VTT using the official Foundry CLI.

### Requirements

- Node.js (LTS version recommended)
- Foundry CLI (included as devDependency in `package.json`)

### Compilation Options

```bash
# Compile during conversion
pdf2foundry convert "Book.pdf" --mod-id "my-book" --mod-title "My Book" --compile-pack

# Manual compilation via npm
npm run compile:pack --modid=my-book --packname=my-book-journals

# Direct Foundry CLI usage
npx @foundryvtt/foundryvtt-cli compilePack \
  --input dist/my-book/sources/journals \
  --output dist/my-book/packs/my-book-journals
```

## Troubleshooting

### Common Issues

**OCR not working**: Ensure Tesseract is installed and available in PATH

```bash
tesseract --version  # Should show version info
```

**Image descriptions failing**: Check VLM model ID and internet connection

```bash
# Test with a well-known model
pdf2foundry convert test.pdf --mod-id test --mod-title Test \
  --picture-descriptions on --vlm-repo-id "Salesforce/blip-image-captioning-base"
```

**Large files timing out**: Use page selection and multiple workers

```bash
pdf2foundry convert large.pdf --mod-id large --mod-title Large \
  --pages "1-50" --workers 4
```

**JSON cache corruption**: Delete cache and regenerate

```bash
rm dist/my-book/sources/docling.json
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" --write-docling-json
```

### Performance Tips

- Use `--pages` to process documents in chunks
- Enable `--workers` for CPU-intensive operations
- Cache Docling JSON for repeated runs with different settings
- Use `--tables image-only` for faster processing if table structure isn't needed
- Enable `--verbose` to monitor progress and identify bottlenecks

### System Requirements Check

```bash
# Check Python and Docling environment
pdf2foundry doctor

# Verify system dependencies
node --version    # Should be 24+
tesseract --version    # Should show Tesseract info
npx @foundryvtt/foundryvtt-cli --version    # Should show Foundry CLI

# Get detailed help
pdf2foundry convert --help

# Enable debug output
pdf2foundry convert book.pdf --mod-id test --mod-title Test -vv
```

## Contributing

We welcome contributions! Please see our development setup above and:

1. Fork the repository
1. Create a feature branch
1. Make your changes with tests
1. Ensure all CI checks pass (`pytest`, `pre-commit run --all-files`)
1. Submit a pull request

## License

This project is licensed under the GNU GPLv3 - see the [LICENSE](LICENSE) file for details.
