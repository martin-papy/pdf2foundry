# Performance Features

PDF2Foundry includes several performance and processing options to optimize conversion for different use cases.

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

# Combine with page selection
pdf2foundry convert book.pdf --mod-id my-book --mod-title "My Book" --pages "1-20" --workers 4
```

**Performance Guidelines:**

- **Recommended workers**: 2-4 for most systems
- **CPU cores**: Generally use 1-2 workers per CPU core
- **Memory**: Each worker uses additional memory; monitor system resources
- **Diminishing returns**: More workers don't always mean faster processing

**Platform Considerations:**

- **Linux**: Uses `fork` start method (most efficient)
- **macOS/Windows**: Uses `spawn` start method (higher overhead)
- **Automatic fallback**: System automatically reduces workers if backend doesn't support parallelism

**What Gets Parallelized:**

- HTML content extraction and transformation
- Image processing and base64 encoding
- Table structure analysis and rendering
- Layout transformations (including multi-column reflow)

**What Stays Single-Threaded:**

- PDF parsing and Docling conversion (always single-pass)
- OCR processing (disabled when workers > 1 for cache safety)
- Picture descriptions (disabled when workers > 1 for cache safety)

**Logging:**
The tool logs the effective worker count and any downgrades:

```text
INFO: Using workers=4 for page-level CPU-bound stages
WARNING: Backend does not support parallel page extraction; forcing workers=1
```

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

## Performance Tips

### For Large Documents

- Use `--pages` to process in batches
- Enable `--workers` based on your CPU cores
- Use `--docling-json` to cache conversion results
- Consider `--tables image-only` for faster processing

### For Multi-Column PDFs

- Test `--reflow-columns` on a few pages first
- Combine with `--pages` for targeted reflow testing
- Validate output carefully, especially around figures and tables

### For Development/Testing

- Use `--pages "1-3"` to test on first few pages
- Set `--workers 1` for consistent debugging
- Disable `--reflow-columns` unless specifically testing layout

### Memory Optimization

- Reduce `--workers` if system runs out of memory
- Process large documents in page batches
- Use `--tables image-only` to reduce memory usage

## Troubleshooting

### Performance Issues

- **Slow processing**: Try increasing `--workers` (up to CPU core count)
- **High memory usage**: Reduce `--workers` or process fewer pages at once
- **Inconsistent results**: Disable `--reflow-columns` and use `--workers 1`

### Platform-Specific

- **Windows/macOS**: Expect higher overhead with multiple workers
- **Linux**: Generally best performance with parallel processing
- **Older systems**: Stick to `--workers 1-2` for stability

### Logging and Diagnostics

The tool provides detailed logging about performance decisions:

- Worker count resolution and any downgrades
- Page selection and processing counts
- Backend capability detection results
- Timing information for major processing stages

Use these logs to understand and optimize performance for your specific use case.
