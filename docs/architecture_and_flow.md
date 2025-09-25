# PDF2Foundry Architecture & Flow

## System Requirements

PDF2Foundry requires the following system dependencies:

- **Python 3.12+**: Core runtime environment
- **Node.js 24+**: Required for Foundry CLI pack compilation
- **Tesseract OCR**: Required for OCR functionality
- **Internet Connection**: For downloading ML models on first use (~1GB)

## High-level System Design

### **Inputs**

- One PDF (born-digital, selectable text)
- CLI configuration options
- Optional cached Docling JSON for faster re-runs

### **Outputs**

- **Complete Foundry VTT v13 Module** containing:
  - `module.json` (v13-compatible module manifest)
  - `assets/` (extracted images at original quality)
  - `styles/pdf2foundry.css` (scoped, non-conflicting CSS)
  - `sources/journals/*.json` (Journal Entry source files)
  - `sources/docling.json` (optional cached document)
  - `packs/<pack-name>/` (compiled LevelDB pack)
- **Optional TOC**: Table of Contents Journal Entry with `@UUID[...]` navigation links

### **Core Foundry VTT Integration**

- **Journal Page HTML Format**: Supported in v13 via `JOURNAL_ENTRY_PAGE_FORMATS.HTML`
- **Document Model**: Journals & Pages are proper Documents with UUID linking (`@UUID[...]`) support
- **LevelDB Packs**: Since v11, compendium packs use LevelDB directories with official packaging flow
- **Native Folders**: v13 supports native folders inside packs (no external dependencies required)

______________________________________________________________________

## CLI Interface

The actual CLI follows a subcommand structure with `convert` as the primary command:

```bash
pdf2foundry convert "My Book.pdf" \
  --mod-id "my-book" \
  --mod-title "My Book (PDF Import)" \
  --author "ACME" \
  --license "OGL" \
  --pack-name "my-book-journals" \
  --toc \
  --tables auto \
  --ocr auto \
  --picture-descriptions off \
  --vlm-repo-id "Salesforce/blip-image-captioning-base" \
  --deterministic-ids \
  --out-dir dist \
  --compile-pack \
  --docling-json cache.json \
  --write-docling-json \
  --fallback-on-json-failure \
  --pages "1-50" \
  --workers 4 \
  --reflow-columns \
  --no-ml \
  --verbose
```

**Key CLI Features:**

- **Subcommand structure**: `pdf2foundry convert <pdf> [options]`
- **Required arguments**: PDF file path, `--mod-id`, `--mod-title`
- **Smart defaults**: TOC enabled, auto table processing, deterministic IDs
- **Advanced features**: OCR, ML-powered image descriptions, multi-worker processing
- **Caching system**: Single-pass ingestion with JSON caching for faster re-runs

______________________________________________________________________

## Processing Pipeline

The conversion follows a **single-pass architecture** with these main stages:

### 1. **PDF Ingestion & Caching**

- **Docling Integration**: Uses Docling's DocumentConverter for unified PDF processing
- **Caching System**: Optional JSON caching (`--docling-json`) for faster re-runs
- **Page Selection**: Support for processing specific pages (`--pages "1-50"`)
- **Multi-worker Processing**: Parallel processing for CPU-intensive operations

### 2. **Structure Parsing**

- **Bookmark Extraction**: Primary method for chapter/section detection
- **Heading Heuristics**: Fallback when bookmarks are missing or incomplete
- **Document Tree**: Build logical hierarchy: `Book → Chapters → Sections`

### 3. **Content Extraction** (Per Page, Parallelizable)

- **HTML Export**: Docling generates semantic HTML with proper structure
- **Layout Transformation**: Optional multi-column reflow (`--reflow-columns`)
- **Image Processing**: Extract images to `assets/` directory with original quality
- **Table Processing**: Three modes:
  - `structured`: Always extract semantic table structure
  - `auto`: Try structured, fallback to image if needed
  - `image-only`: Always rasterize tables as images
- **OCR Processing**: Tesseract integration with intelligent triggering:
  - `auto`: OCR pages with low text coverage
  - `on`: Always apply OCR
  - `off`: Disable OCR completely
- **Link Detection**: Extract internal and external link references

### 4. **AI-Powered Enhancements** (Optional)

- **Image Descriptions**: Vision-Language Model captions (`--picture-descriptions on`)
- **Default VLM**: `Salesforce/blip-image-captioning-base` (~1GB)
- **ML Disable**: `--no-ml` flag for CI environments or faster processing

### 5. **Intermediate Representation (IR)**

- Build unified document model from parsed structure and extracted content
- Resolve cross-references and internal links
- Apply deterministic ID generation: `sha1(<mod-id>|<chapter-path>|<section-path>)[:16]`

### 6. **Foundry Mapping**

- **Journal Entries**: One per chapter
- **Journal Pages**: One per section (`type: "text"`, `text.format: 1` for HTML)
- **UUID Links**: Generate stable `@UUID[JournalEntry.<E>.JournalEntryPage.<P>]` references
- **Folder Structure**: Native v13 compendium folder support

### 7. **Output Generation**

- **Module Manifest**: Generate `module.json` with proper v13 compatibility
- **Source Files**: Write individual JSON files per Journal Entry
- **Assets**: Copy extracted images with proper references
- **Styles**: Generate scoped CSS (`pdf2foundry.css`)
- **TOC Generation**: Optional Table of Contents with clickable navigation

### 8. **Pack Compilation** (Optional)

- **Foundry CLI Integration**: Use official `@foundryvtt/foundryvtt-cli` for LevelDB compilation
- **Node.js Requirement**: Requires Node.js 24+ for Foundry CLI
- **Automatic Compilation**: `--compile-pack` flag for immediate pack generation

### **Architecture Principles**

- **Single-Pass Processing**: Each PDF processed exactly once with optional caching
- **Modular Design**: Clean separation between ingestion, processing, and output
- **Error Resilience**: Graceful degradation when features fail
- **Performance Optimization**: Multi-worker support and intelligent feature detection

______________________________________________________________________

## Output Directory Structure

PDF2Foundry generates a complete Foundry VTT module with the following structure:

```text
<out-dir>/<mod-id>/
├── module.json                 # Module manifest with v13 compatibility
├── assets/                     # Extracted images and media
│   ├── image_001.png          # Original quality images
│   ├── image_002.jpg
│   └── ...
├── styles/
│   └── pdf2foundry.css        # Scoped module styles
├── sources/
│   ├── journals/              # Journal Entry source files
│   │   ├── chapter_001.json   # One file per chapter
│   │   ├── chapter_002.json
│   │   ├── toc.json           # Table of Contents (optional)
│   │   └── ...
│   └── docling.json          # Cached Docling document (optional)
└── packs/
    └── <pack-name>/          # Compiled LevelDB pack (optional)
        ├── 000001.ldb        # LevelDB files
        ├── 000002.ldb
        └── MANIFEST-000001
```

### **Key Components:**

- **`module.json`**: Foundry v13 module manifest with proper compatibility declarations
- **`assets/`**: Original resolution images extracted from PDF
- **`sources/journals/`**: Individual JSON files for each Journal Entry (chapter)
- **`sources/docling.json`**: Optional cached Docling document for faster re-runs
- **`packs/<pack-name>/`**: Compiled LevelDB compendium (requires Node.js 24+ and Foundry CLI)
- **`styles/pdf2foundry.css`**: Scoped CSS to avoid conflicts with other modules

### **Module Structure:**

- **One Chapter** → **One Journal Entry** (with multiple pages)
- **One Section** → **One Journal Entry Page** (`type: "text"`, HTML format)
- **Deterministic IDs**: SHA1-based stable UUIDs for reliable cross-references
- **Native v13 Folders**: Built-in compendium folder support (no external dependencies)

______________________________________________________________________

## Error Handling & Resilience

PDF2Foundry implements comprehensive error handling with graceful degradation:

### **Structure Detection Fallbacks**

- **Missing bookmarks**: Automatically fall back to heading-based heuristics
- **Ambiguous structure**: Use intelligent section detection with logging
- **Empty documents**: Handle edge cases with appropriate user feedback

### **Content Processing Resilience**

- **Table extraction failures**: Automatic fallback to image rasterization
- **Image extraction errors**: Graceful handling with placeholder generation
- **OCR failures**: Continue processing without OCR when Tesseract unavailable
- **ML model failures**: Disable AI features gracefully with `--no-ml` fallback

### **System Dependency Handling**

- **Missing Tesseract**: OCR features automatically disabled with warnings
- **Missing Node.js/Foundry CLI**: Pack compilation skipped with clear messaging
- **Insufficient memory**: Multi-worker processing scales down automatically

### **Validation & Recovery**

- **JSON cache corruption**: Automatic fallback to fresh conversion
- **Invalid PDF files**: Early detection with clear error messages
- **Permission errors**: Directory creation failures handled gracefully
- **Network issues**: ML model downloads with retry logic and offline fallbacks

### **Logging & Diagnostics**

- **Verbose modes**: `-v` for info, `-vv` for debug output
- **Progress reporting**: Real-time feedback during long operations
- **Doctor command**: `pdf2foundry doctor` for environment diagnostics
- **Feature detection**: Automatic capability detection and reporting

______________________________________________________________________

## Testing & Validation

PDF2Foundry includes comprehensive testing infrastructure:

### **Automated Testing**

- **Unit Tests**: Core functionality with 90%+ coverage requirement
- **E2E Tests**: End-to-end conversion testing with real PDFs
- **Performance Tests**: Regression detection with configurable thresholds
- **ML Tests**: Conditional testing for AI features when models are cached

### **Quality Gates**

- **Pre-commit Hooks**: Ruff, Black, MyPy (strict mode), pytest
- **CI/CD Pipeline**: Cross-platform testing (Ubuntu, Windows, macOS)
- **Tier-based Testing**: Core, feature, and ML test separation
- **Performance Monitoring**: Automated baseline management

### **Manual Validation Checklist**

1. **Module Installation**: Verify module appears in Foundry and imports correctly
1. **Content Rendering**: Confirm HTML rendering and asset loading in Journal pages
1. **Navigation**: Test TOC links and UUID-based page navigation
1. **Folder Structure**: Verify v13 native compendium folder organization
1. **Cross-references**: Validate internal links and deterministic ID stability

### **System Requirements Validation**

- **Python 3.12+**: Version compatibility testing
- **Node.js 24+**: Foundry CLI integration testing
- **Tesseract OCR**: OCR functionality validation
- **System Dependencies**: Comprehensive environment checking via `pdf2foundry doctor`

______________________________________________________________________

## Current Implementation Status

**✅ Completed Features:**

- Complete CLI interface with all documented options
- Single-pass Docling integration with caching
- Multi-worker parallel processing
- OCR integration with Tesseract
- AI-powered image descriptions with VLM support
- Deterministic ID generation for stable cross-references
- Foundry v13 module generation with native folder support
- LevelDB pack compilation via Foundry CLI
- Comprehensive error handling and graceful degradation
- Full test suite with E2E validation

**🔧 Architecture Highlights:**

- **Modular Design**: Clean separation between ingestion, processing, and output
- **Performance Optimized**: Intelligent caching and parallel processing
- **Production Ready**: Comprehensive testing and CI/CD pipeline
- **User Friendly**: Rich progress reporting and interactive prompts

______________________________________________________________________

## Additional Resources

For detailed implementation examples and schemas, see:

- **[Product Requirements](docs/PRD.md)**: Complete feature specification
- **[Development Guidelines](docs/development.md)**: Development setup and workflow
- **[Performance Guide](docs/performance.md)**: Optimization strategies and benchmarks

## Foundry VTT References

- [Foundry Virtual Tabletop](https://foundryvtt.com/) - Official Foundry VTT website
- [Foundry VTT Community Wiki](https://foundryvtt.wiki/) - Community documentation
- [Journal Entries Guide](https://foundryvtt.com/article/journal/) - Official journal documentation
- [Compendium Packs Guide](https://foundryvtt.com/article/compendium/) - Official compendium documentation
- [Content Packaging Guide](https://foundryvtt.com/article/packaging-guide/) - Official packaging documentation
