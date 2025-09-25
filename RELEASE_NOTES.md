# Release Notes

## Version 0.1.0a1 - 2025-09-25

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

For detailed usage instructions, see the [README.md](README.md).
