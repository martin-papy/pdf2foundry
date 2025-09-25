# Release Notes

## Version 0.1.0 - 2025-01-25

### Initial Release

This is the initial release of PDF2Foundry, a tool to convert born-digital PDFs into Foundry VTT v13 module compendia.

#### Features

- **Core Conversion**: Convert PDF chapters to Journal Entries and sections to Journal Pages
- **Rich Content Extraction**: Support for images, tables, links, and formatted text
- **Structure Preservation**: Maintain PDF outline/bookmark structure in Foundry
- **Structured Tables**: Extract semantic table structure when possible
- **OCR Support**: Optional OCR for scanned pages or low-text-coverage areas
- **Image Descriptions**: AI-powered image captions using Vision-Language Models
- **Performance Optimization**: Multi-worker processing and page selection for large documents
- **Caching System**: Single-pass ingestion with optional JSON caching for faster re-runs
- **Deterministic IDs**: Stable SHA1-based UUIDs for reliable cross-references across runs
- **Foundry Integration**: Native v13 compendium folders and pack compilation

#### Technical Details

- **Python Version**: Requires Python 3.12+
- **Architecture**: Single-pass processing powered by Docling
- **CLI Framework**: Built with Typer for robust command-line interface
- **Testing**: Comprehensive test suite with 90%+ coverage requirement
- **Quality Gates**: Strict linting (Ruff), formatting (Black), and type checking (MyPy)
- **CI/CD**: Full GitHub Actions pipeline with cross-platform testing

#### Dependencies

- Core: Typer, Jinja2, Pillow, Rich, Docling
- ML Features: Transformers, Hugging Face Hub, PyTorch
- OCR: PyTesseract (with system Tesseract requirement)
- Development: Ruff, Black, MyPy, pytest, pre-commit

#### Known Limitations

- OCR requires system Tesseract installation
- VLM features require internet connection for model downloads
- Pack compilation requires Node.js and Foundry CLI
- Large PDFs may require page selection for optimal performance

#### Installation

```bash
pip install pdf2foundry
```

#### Basic Usage

```bash
pdf2foundry convert "My Book.pdf" --mod-id "my-book" --mod-title "My Book"
```

For detailed usage instructions, see the [README.md](README.md).
