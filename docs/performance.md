# Performance Optimization Guide

PDF2Foundry includes comprehensive performance optimization features to handle documents of all sizes efficiently. This guide covers processing options, caching strategies, parallel processing, and performance tuning for different use cases.

## Overview

PDF2Foundry's performance architecture includes:

- **Single-pass ingestion**: PDF converted to Docling document once per run
- **JSON caching**: Save/load processed documents for faster re-runs
- **Parallel processing**: Multi-worker CPU-bound operations
- **Intelligent caching**: OCR, image, and caption result caching
- **Selective processing**: Page selection and feature toggles
- **Memory optimization**: Configurable limits and efficient resource usage

## Caching System

### Docling JSON Caching

The most significant performance optimization is caching the Docling document conversion:

```bash
# Cache to specific file (load if exists, save if doesn't)
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" \
  --docling-json "cache/book-docling.json"

# Auto-cache to default location (dist/<mod-id>/sources/docling.json)
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" \
  --write-docling-json

# Load from cache with fallback on failure
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" \
  --docling-json "cache/book-docling.json" --fallback-on-json-failure
```

**Performance Impact:**

- **First run**: Full PDF processing + JSON cache creation
- **Subsequent runs**: ~10-50x faster (load from JSON cache)
- **Cache size**: Typically 10-30% of original PDF size

**Use Cases:**

- **Development**: Iterate on output formatting without re-processing PDF
- **Batch processing**: Process same PDF with different options
- **CI/CD**: Cache conversion results between pipeline stages

### Intelligent Sub-Caches

PDF2Foundry includes several automatic caches for expensive operations:

#### **OCR Cache**

- **Scope**: Per-image OCR results (LRU cache, 2000 entries)
- **Thread safety**: Single-threaded per pipeline
- **Performance**: Avoids re-OCR of identical image regions

#### **Image Caption Cache**

- **Scope**: VLM-generated image descriptions (LRU cache, 2000 entries)
- **Model dependency**: Cached per VLM model
- **Performance**: Significant for documents with repeated images

#### **Shared Image Cache**

- **Scope**: PIL images for page rasterization and region extraction
- **Thread safety**: Thread-safe with RLock protection
- **Performance**: Reduces memory usage and rasterization overhead

## Page Selection (`--pages`)

Process only specific pages from a PDF document:

```bash
# Process single pages
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" --pages "1,5,10"

# Process page ranges
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" --pages "1-5,10-15"

# Mix single pages and ranges
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" --pages "1,3,5-10,15"
```

**Use Cases:**

- Extract specific chapters or sections
- Test conversion on a subset before processing the full document
- Skip problematic pages during development

**Notes:**

- Page numbers are 1-based (first page is 1, not 0)
- Pages are processed in ascending order regardless of specification order
- Invalid page numbers (exceeding document length) will cause an error

## Parallel Processing (`--workers`)

Use multiple worker processes for CPU-bound page-level operations:

```bash
# Use 4 worker processes
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" --workers 4

# Combine with page selection and caching
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" \
  --pages "1-20" --workers 4 --write-docling-json
```

### Performance Guidelines

**Recommended Configuration:**

- **Small documents** (< 20 pages): `--workers 1-2`
- **Medium documents** (20-100 pages): `--workers 2-4`
- **Large documents** (100+ pages): `--workers 4-8`
- **CPU cores**: Generally use 1-2 workers per CPU core
- **Memory**: Each worker uses ~200-500MB additional memory

### Platform Considerations

**Process Start Methods:**

- **Linux**: Uses `fork` start method (most efficient, lowest overhead)
- **macOS/Windows**: Uses `spawn` start method (higher overhead, slower startup)
- **Automatic fallback**: System automatically reduces workers if backend doesn't support parallelism

**Performance Impact by Platform:**

- **Linux**: 2-4x speedup with 4 workers typical
- **macOS**: 1.5-3x speedup (spawn overhead reduces gains)
- **Windows**: 1.5-2.5x speedup (spawn overhead + platform limitations)

### What Gets Parallelized

**Per-Page Operations:**

- HTML content extraction and transformation
- Image processing and base64 encoding
- Table structure analysis and rendering
- Layout transformations (including multi-column reflow)
- Link detection and processing

### What Stays Single-Threaded

**Global Operations:**

- PDF parsing and Docling conversion (always single-pass)
- Document structure analysis and TOC generation
- Final module assembly and pack compilation

**Cache-Dependent Features:**

- OCR processing (disabled when workers > 1 for cache safety)
- Picture descriptions (disabled when workers > 1 for cache safety)
- These features automatically fall back to sequential mode

### Worker Resolution Logic

The system automatically determines the effective worker count:

```text
INFO: Using workers=4 for page-level CPU-bound stages
INFO: OCR disabled in parallel mode for cache safety
WARNING: Backend does not support parallel page extraction; forcing workers=1
```

**Automatic Downgrades:**

- Backend doesn't support parallelism → `workers=1`
- OCR or VLM enabled → `workers=1` (cache safety)
- Insufficient pages → Reduced worker count
- Platform limitations → Fallback to sequential mode

## Multi-Column Reflow (`--reflow-columns`)

⚠️ **EXPERIMENTAL FEATURE**

Reorder multi-column text content into natural reading order:

```bash
# Enable experimental multi-column reflow
pdf2foundry convert academic-paper.pdf --mod-id paper --mod-title "Research Paper" --reflow-columns
```

**When to Use:**

- **Academic papers** with 2-3 column layouts
- **Journals** and **magazines** with column-based text
- **Technical documents** where reading order matters

**Risks and Limitations:**

- **Captions**: May be misplaced relative to figures
- **Sidebars**: Could be moved out of context
- **Footnotes**: May appear in wrong positions
- **Tables**: Complex layouts might be disrupted
- **Mixed layouts**: Pages with varying column counts may not reflow correctly

**How It Works:**

1. Analyzes text block positions to detect 2-3 column layouts
1. Verifies column separation (minimum 8% of page width gap)
1. Reorders text blocks within each column by vertical position
1. Concatenates columns left-to-right for natural reading flow
1. Preserves non-text elements (images, tables) in their relative positions

**Validation:**

- **Always validate output** when using reflow
- **Test on sample pages** before processing full documents
- **Compare with original** to ensure content integrity
- **Disable if results are unsatisfactory** (it's off by default for a reason)

**Fallback Behavior:**

- If column detection fails, original order is preserved
- No reflow occurs on single-column or ambiguous layouts
- Deterministic output ensures consistent results across runs

## ML/AI Performance Features

### Disabling ML Features (`--no-ml`)

For faster processing when AI features aren't needed:

```bash
# Disable all ML features for maximum speed
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" --no-ml

# Combine with parallel processing for fastest conversion
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" \
  --no-ml --workers 4 --write-docling-json
```

**Performance Impact:**

- **OCR**: Disabled (no Tesseract processing)
- **Image Descriptions**: Disabled (no VLM model loading/inference)
- **Processing Speed**: 2-5x faster for image-heavy documents
- **Memory Usage**: Significantly reduced (no model loading)
- **Parallel Processing**: Enabled (no cache conflicts)

### VLM Model Optimization

When using image descriptions (`--picture-descriptions on`):

```bash
# Use lightweight BLIP model (default, ~1GB)
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" \
  --picture-descriptions on

# Use specific VLM model
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" \
  --picture-descriptions on --vlm-repo-id "Salesforce/blip-image-captioning-base"
```

**Model Performance Characteristics:**

- **Salesforce/blip-image-captioning-base**: ~1GB, fast inference, good quality
- **First run**: Downloads model (~1GB), caches locally
- **Subsequent runs**: Uses cached model, faster startup
- **Memory usage**: Additional 2-4GB RAM during processing
- **Processing time**: +30-200% depending on image count

### OCR Performance Tuning

OCR mode affects both speed and quality:

```bash
# Intelligent OCR (default) - only when needed
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" --ocr auto

# Always OCR (slower but comprehensive)
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" --ocr on

# Disable OCR (fastest)
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" --ocr off
```

**OCR Performance Impact:**

- **Auto mode**: OCR only pages with low text coverage (< 50%)
- **On mode**: OCR all pages (2-10x slower)
- **Off mode**: No OCR processing (fastest)
- **Cache benefit**: Repeated OCR operations are cached

## Combining Features

All performance features can be used together:

```bash
# Process specific pages with multiple workers and reflow
pdf2foundry convert academic-journal.pdf \
  --mod-id journal --mod-title "Academic Journal" \
  --pages "10-25" \
  --workers 3 \
  --reflow-columns \
  --tables structured
```

## Performance Optimization Strategies

### For Large Documents (100+ pages)

**Recommended Approach:**

```bash
# First run: Create cache with minimal features
pdf2foundry convert large-book.pdf --mod-id large-book --mod-title "Large Book" \
  --no-ml --workers 4 --write-docling-json

# Subsequent runs: Use cache with desired features
pdf2foundry convert large-book.pdf --mod-id large-book --mod-title "Large Book" \
  --docling-json "dist/large-book/sources/docling.json" \
  --picture-descriptions on --workers 1
```

**Optimization Techniques:**

- **Batch processing**: Use `--pages` to process in chunks
- **Cache first**: Create Docling JSON cache before adding expensive features
- **Parallel processing**: Use `--workers 4-8` for CPU-bound operations
- **Selective features**: Add OCR/VLM only where needed

### For Development and Testing

**Fast Iteration Workflow:**

```bash
# Initial cache creation (once)
pdf2foundry convert test.pdf --mod-id test --mod-title "Test" \
  --write-docling-json --no-ml

# Fast iterations with cache
pdf2foundry convert test.pdf --mod-id test --mod-title "Test" \
  --docling-json "dist/test/sources/docling.json" \
  --pages "1-3" --workers 1
```

**Development Best Practices:**

- **Use page selection**: `--pages "1-3"` for quick testing
- **Single worker**: `--workers 1` for consistent debugging
- **Disable experimental features**: Skip `--reflow-columns` unless testing
- **Cache everything**: Always use `--write-docling-json` or `--docling-json`

### For Multi-Column PDFs

**Testing Strategy:**

```bash
# Test reflow on sample pages first
pdf2foundry convert academic.pdf --mod-id academic --mod-title "Academic Paper" \
  --pages "1-5" --reflow-columns --write-docling-json

# Full processing after validation
pdf2foundry convert academic.pdf --mod-id academic --mod-title "Academic Paper" \
  --docling-json "dist/academic/sources/docling.json" --reflow-columns
```

**Validation Steps:**

- Test on representative pages first
- Compare output with original layout
- Check figure and table positioning
- Validate reading order and flow

### Memory Optimization

**Memory-Constrained Systems:**

```bash
# Minimal memory usage
pdf2foundry convert book.pdf --mod-id book --mod-title "Book" \
  --no-ml --workers 1 --tables image-only

# Batch processing for large documents
pdf2foundry convert book.pdf --mod-id book --mod-title "Book" \
  --pages "1-50" --workers 2 --write-docling-json
```

**Memory Management Strategies:**

- **Reduce workers**: Lower `--workers` count if system runs out of memory
- **Batch processing**: Process large documents in page chunks
- **Disable ML**: Use `--no-ml` to avoid model loading
- **Image-only tables**: Use `--tables image-only` to reduce processing overhead

### Performance Monitoring

**Built-in Diagnostics:**

```bash
# Verbose output for performance analysis
pdf2foundry convert book.pdf --mod-id book --mod-title "Book" \
  --verbose --verbose --workers 4
```

**Key Metrics to Monitor:**

- **Cache hit rates**: OCR and image caption cache effectiveness
- **Worker utilization**: Parallel processing efficiency
- **Memory usage**: Peak memory consumption during processing
- **Processing time**: Per-page and total conversion time

## Troubleshooting

### Performance Issues

#### **Slow Processing**

```bash
# Diagnose with verbose logging
pdf2foundry convert book.pdf --mod-id book --mod-title "Book" -vv

# Try parallel processing
pdf2foundry convert book.pdf --mod-id book --mod-title "Book" --workers 4

# Use caching for repeated runs
pdf2foundry convert book.pdf --mod-id book --mod-title "Book" --write-docling-json
```

**Common Causes:**

- No caching enabled (use `--write-docling-json`)
- Single-threaded processing (increase `--workers`)
- ML features enabled unnecessarily (use `--no-ml`)
- Processing all pages (use `--pages` for testing)

#### **High Memory Usage**

```bash
# Reduce memory consumption
pdf2foundry convert book.pdf --mod-id book --mod-title "Book" \
  --workers 1 --no-ml --tables image-only
```

**Memory Optimization:**

- Reduce `--workers` count (each worker uses 200-500MB)
- Use `--no-ml` to avoid model loading (saves 2-4GB)
- Process in batches with `--pages`
- Use `--tables image-only` to reduce processing overhead

#### **Inconsistent Results**

```bash
# Ensure deterministic processing
pdf2foundry convert book.pdf --mod-id book --mod-title "Book" \
  --workers 1 --deterministic-ids
```

**Consistency Factors:**

- Use `--workers 1` for debugging
- Disable `--reflow-columns` (experimental feature)
- Ensure `--deterministic-ids` is enabled (default)
- Use same caching strategy across runs

### Platform-Specific Issues

#### **Windows/macOS Performance**

- **Expected**: 20-40% overhead compared to Linux
- **Cause**: `spawn` process start method vs `fork`
- **Mitigation**: Use fewer workers (2-3 instead of 4-8)
- **Alternative**: Use WSL on Windows for better performance

#### **Linux Optimization**

- **Best performance**: Can efficiently use 4-8 workers
- **Memory efficiency**: `fork` method shares memory better
- **Recommendation**: Optimal platform for large document processing

#### **Memory-Constrained Systems**

```bash
# Minimal resource usage
pdf2foundry convert book.pdf --mod-id book --mod-title "Book" \
  --workers 1 --no-ml --pages "1-10"
```

### Diagnostic Tools

#### **Built-in Diagnostics**

```bash
# Environment check
pdf2foundry doctor

# Verbose processing logs
pdf2foundry convert book.pdf --mod-id book --mod-title "Book" -vv

# Worker resolution logging
pdf2foundry convert book.pdf --mod-id book --mod-title "Book" --workers 4 -v
```

#### **Performance Logging**

The tool provides detailed logging about performance decisions:

**Worker Resolution:**

```text
INFO: Using workers=4 for page-level CPU-bound stages
INFO: OCR disabled in parallel mode for cache safety
WARNING: Backend does not support parallel page extraction; forcing workers=1
```

**Cache Performance:**

```text
INFO: Loaded cached document from dist/book/sources/docling.json (150 pages)
INFO: OCR cache hit rate: 85% (170/200 requests)
INFO: Image caption cache hit rate: 92% (45/49 requests)
```

**Processing Metrics:**

```text
INFO: Page processing completed in 45.2s (4 workers, 150 pages)
INFO: Average per-page time: 0.30s
INFO: Peak memory usage: 2.1GB
```

#### **Performance Analysis**

**Key Metrics to Track:**

- **Cache hit rates**: Higher is better (> 80% ideal)
- **Worker utilization**: Should scale linearly with worker count
- **Memory usage**: Monitor peak consumption
- **Per-page timing**: Identify bottlenecks

**Optimization Workflow:**

1. **Baseline**: Run with `--workers 1 --no-ml -vv`
1. **Cache**: Add `--write-docling-json` and re-run
1. **Parallel**: Increase `--workers` and measure speedup
1. **Features**: Add ML features only when needed
1. **Monitor**: Use verbose logging to identify bottlenecks
