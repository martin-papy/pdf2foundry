# End-to-End Testing Strategy for PDF2Foundry

## Overview

This document outlines comprehensive end-to-end (E2E) test scenarios for PDF2Foundry, a tool that converts born-digital PDFs into Foundry VTT v13 modules. These tests validate the entire pipeline from PDF input to complete Foundry module output, ensuring all features work correctly in realistic scenarios.

## Testing Philosophy

As a **Senior Software Quality Assurance Engineer**, our E2E testing strategy follows these principles:

- **Real-world scenarios**: Test with actual PDF files representing different document types
- **Complete pipeline validation**: Test from CLI invocation to final module structure
- **Feature coverage**: Validate all major CLI options and processing modes
- **Output validation**: Verify both file structure and content correctness
- **Error handling**: Test graceful failure modes and edge cases
- **Performance validation**: Ensure acceptable processing times for various document sizes

## Test Environment Requirements

### Prerequisites

- Python 3.12+ with PDF2Foundry installed
- Node.js (for Foundry CLI pack compilation)
- Tesseract OCR (for OCR-enabled tests)
- Internet connection (for VLM model downloads)
- Sufficient disk space for test outputs (~500MB recommended)

### Test Data Requirements

We need a diverse set of PDF test files representing different document characteristics:

1. **Simple text-only PDF** (basic.pdf) - 5-10 pages, clear structure
1. **Image-rich PDF** (illustrated-guide.pdf) - Contains figures, diagrams, photos
1. **Table-heavy PDF** (data-manual.pdf) - Multiple table formats and structures
1. **Complex structured PDF** (academic-paper.pdf) - Multi-column, footnotes, references
1. **Large document PDF** (comprehensive-manual.pdf) - 100+ pages for performance testing
1. **Scanned/low-text PDF** (scanned-document.pdf) - For OCR testing
1. **Minimal PDF** (single-page.pdf) - Edge case testing

## Core Test Scenarios

### E2E-001: Basic PDF Conversion

**Objective**: Validate basic PDF to Foundry module conversion with default settings.

**Test Data**: `fixtures/basic.pdf` (simple text document with clear chapter structure)

**Command**:

```bash
pdf2foundry convert fixtures/basic.pdf \
  --mod-id "e2e-basic-test" \
  --mod-title "Basic E2E Test Module" \
  --out-dir "test-output/e2e-001"
```

**Expected Outputs**:

- Module directory: `test-output/e2e-001/e2e-basic-test/`
- Files present:
  - `module.json` (valid Foundry v13 format)
  - `styles/pdf2foundry.css`
  - `sources/journals/*.json` (one per chapter + TOC)
  - `assets/` (if images present)
- Content validation:
  - Journal entries have deterministic IDs
  - TOC contains `@UUID[...]` links to all chapters
  - HTML content wrapped in `<div class="pdf2foundry">`
  - Text content matches PDF structure

**Validation Criteria**:

- Exit code: 0
- Module.json schema validation
- Journal entry JSON schema validation
- TOC link integrity check
- Content fidelity spot-check

### E2E-002: Image Extraction and Processing

**Objective**: Validate image extraction, asset management, and HTML image references.

**Test Data**: `fixtures/illustrated-guide.pdf` (document with various image types)

**Command**:

```bash
pdf2foundry convert fixtures/illustrated-guide.pdf \
  --mod-id "e2e-image-test" \
  --mod-title "Image Processing Test" \
  --out-dir "test-output/e2e-002" \
  --verbose
```

**Expected Outputs**:

- Assets directory with extracted images
- Image files in original format/quality
- HTML content with correct image references
- Image paths: `modules/e2e-image-test/assets/image_*.{png,jpg,etc}`

**Validation Criteria**:

- All PDF images extracted to assets/
- HTML `<img>` tags reference correct module paths
- Images are accessible and not corrupted
- Image alt text present where available

### E2E-003: Table Processing Modes

**Objective**: Test different table processing modes (structured, auto, image-only).

**Test Data**: `fixtures/data-manual.pdf` (document with various table formats)

**Commands**:

```bash
# Test structured table extraction
pdf2foundry convert fixtures/data-manual.pdf \
  --mod-id "e2e-tables-structured" \
  --mod-title "Structured Tables Test" \
  --tables structured \
  --out-dir "test-output/e2e-003a"

# Test auto mode (structured with fallback)
pdf2foundry convert fixtures/data-manual.pdf \
  --mod-id "e2e-tables-auto" \
  --mod-title "Auto Tables Test" \
  --tables auto \
  --out-dir "test-output/e2e-003b"

# Test image-only mode
pdf2foundry convert fixtures/data-manual.pdf \
  --mod-id "e2e-tables-image" \
  --mod-title "Image Tables Test" \
  --tables image-only \
  --out-dir "test-output/e2e-003c"
```

**Expected Outputs**:

- Structured mode: HTML `<table>` elements with proper structure
- Auto mode: Mix of HTML tables and image fallbacks
- Image-only mode: All tables as embedded images

**Validation Criteria**:

- Table content accuracy comparison
- HTML table structure validation (structured mode)
- Image quality assessment (image-only mode)
- Processing time comparison between modes

### E2E-004: OCR Processing

**Objective**: Validate OCR functionality for scanned or low-text documents.

**Test Data**: `fixtures/scanned-document.pdf` (document requiring OCR)

**Commands**:

```bash
# Test auto OCR (should trigger on low text coverage)
pdf2foundry convert fixtures/scanned-document.pdf \
  --mod-id "e2e-ocr-auto" \
  --mod-title "Auto OCR Test" \
  --ocr auto \
  --out-dir "test-output/e2e-004a"

# Test forced OCR
pdf2foundry convert fixtures/scanned-document.pdf \
  --mod-id "e2e-ocr-on" \
  --mod-title "Forced OCR Test" \
  --ocr on \
  --out-dir "test-output/e2e-004b"

# Test OCR disabled
pdf2foundry convert fixtures/scanned-document.pdf \
  --mod-id "e2e-ocr-off" \
  --mod-title "No OCR Test" \
  --ocr off \
  --out-dir "test-output/e2e-004c"
```

**Expected Outputs**:

- Auto mode: OCR applied only to low-text pages
- Forced mode: OCR applied to all pages
- Disabled mode: No OCR processing

**Validation Criteria**:

- Text extraction quality comparison
- Processing time impact assessment
- OCR accuracy spot-check on known text

### E2E-005: AI Image Descriptions

**Objective**: Test Vision-Language Model integration for image captions.

**Test Data**: `fixtures/illustrated-guide.pdf`

**Command**:

```bash
pdf2foundry convert fixtures/illustrated-guide.pdf \
  --mod-id "e2e-image-descriptions" \
  --mod-title "Image Descriptions Test" \
  --picture-descriptions on \
  --vlm-repo-id "microsoft/Florence-2-base" \
  --out-dir "test-output/e2e-005"
```

**Expected Outputs**:

- Images with AI-generated alt text and captions
- Enhanced accessibility in HTML output
- Reasonable processing time despite AI inference

**Validation Criteria**:

- All images have generated descriptions
- Description quality assessment (relevance, accuracy)
- No model download/loading failures
- Graceful handling of unsupported image formats

### E2E-006: Performance and Scalability

**Objective**: Test performance with large documents and parallel processing.

**Test Data**: `fixtures/comprehensive-manual.pdf` (100+ pages)

**Commands**:

```bash
# Single-threaded baseline
pdf2foundry convert fixtures/comprehensive-manual.pdf \
  --mod-id "e2e-perf-single" \
  --mod-title "Performance Test Single" \
  --workers 1 \
  --out-dir "test-output/e2e-006a"

# Multi-threaded processing
pdf2foundry convert fixtures/comprehensive-manual.pdf \
  --mod-id "e2e-perf-multi" \
  --mod-title "Performance Test Multi" \
  --workers 4 \
  --out-dir "test-output/e2e-006b"

# Page selection for chunked processing
pdf2foundry convert fixtures/comprehensive-manual.pdf \
  --mod-id "e2e-perf-pages" \
  --mod-title "Performance Test Pages" \
  --pages "1-20,50-70" \
  --workers 2 \
  --out-dir "test-output/e2e-006c"
```

**Expected Outputs**:

- Successful processing of large documents
- Performance improvement with multiple workers
- Correct page selection and processing

**Validation Criteria**:

- Processing time benchmarks
- Memory usage monitoring
- Output quality consistency across modes
- No performance regressions

### E2E-007: Caching and Re-runs

**Objective**: Validate Docling JSON caching for improved re-run performance.

**Test Data**: `fixtures/basic.pdf`

**Commands**:

```bash
# Initial run with cache writing
pdf2foundry convert fixtures/basic.pdf \
  --mod-id "e2e-cache-test" \
  --mod-title "Cache Test Module" \
  --write-docling-json \
  --out-dir "test-output/e2e-007"

# Re-run using cache (should be faster)
pdf2foundry convert fixtures/basic.pdf \
  --mod-id "e2e-cache-test-rerun" \
  --mod-title "Cache Test Rerun" \
  --docling-json "test-output/e2e-007/e2e-cache-test/sources/docling.json" \
  --out-dir "test-output/e2e-007-rerun"

# Test cache fallback
pdf2foundry convert fixtures/basic.pdf \
  --mod-id "e2e-cache-fallback" \
  --mod-title "Cache Fallback Test" \
  --docling-json "nonexistent-cache.json" \
  --fallback-on-json-failure \
  --out-dir "test-output/e2e-007-fallback"
```

**Expected Outputs**:

- Cache file created in first run
- Significant speed improvement in cached run
- Graceful fallback when cache is invalid

**Validation Criteria**:

- Cache file format validation
- Performance improvement measurement
- Output consistency between cached and non-cached runs
- Proper fallback behavior

### E2E-008: Pack Compilation

**Objective**: Test Foundry CLI integration for LevelDB pack compilation.

**Test Data**: `fixtures/basic.pdf`

**Command**:

```bash
pdf2foundry convert fixtures/basic.pdf \
  --mod-id "e2e-pack-compile" \
  --mod-title "Pack Compilation Test" \
  --compile-pack \
  --out-dir "test-output/e2e-008"
```

**Expected Outputs**:

- Complete module with compiled LevelDB pack
- Packs directory with proper LevelDB structure
- Successful Foundry CLI execution

**Validation Criteria**:

- LevelDB pack structure validation
- Pack content integrity check
- Foundry CLI exit code verification
- Module installability in Foundry VTT

### E2E-009: Advanced Features Integration

**Objective**: Test combination of multiple advanced features.

**Test Data**: `fixtures/comprehensive-manual.pdf`

**Command**:

```bash
pdf2foundry convert fixtures/comprehensive-manual.pdf \
  --mod-id "e2e-advanced-combo" \
  --mod-title "Advanced Features Test" \
  --tables structured \
  --ocr auto \
  --picture-descriptions on \
  --vlm-repo-id "microsoft/Florence-2-base" \
  --workers 2 \
  --reflow-columns \
  --compile-pack \
  --write-docling-json \
  --verbose \
  --out-dir "test-output/e2e-009"
```

**Expected Outputs**:

- Fully featured module with all enhancements
- Successful integration of all features
- Reasonable processing time despite complexity

**Validation Criteria**:

- All features working correctly together
- No feature conflicts or interference
- Output quality meets all individual feature standards
- Performance within acceptable bounds

### E2E-010: Error Handling and Edge Cases

**Objective**: Test graceful handling of problematic inputs and edge cases.

**Test Cases**:

#### E2E-010a: Corrupted PDF

```bash
# Test with invalid PDF file
echo "Not a PDF" > test-output/corrupted.pdf
pdf2foundry convert test-output/corrupted.pdf \
  --mod-id "e2e-error-corrupt" \
  --mod-title "Corrupted PDF Test" \
  --out-dir "test-output/e2e-010a"
```

#### E2E-010b: Empty PDF

```bash
# Test with minimal/empty PDF
pdf2foundry convert fixtures/empty.pdf \
  --mod-id "e2e-error-empty" \
  --mod-title "Empty PDF Test" \
  --out-dir "test-output/e2e-010b"
```

#### E2E-010c: Invalid CLI Arguments

```bash
# Test with invalid table mode
pdf2foundry convert fixtures/basic.pdf \
  --mod-id "e2e-error-args" \
  --mod-title "Invalid Args Test" \
  --tables invalid-mode \
  --out-dir "test-output/e2e-010c"
```

**Expected Outputs**:

- Graceful error messages
- Non-zero exit codes for failures
- No partial/corrupted output files
- Helpful troubleshooting information

**Validation Criteria**:

- Clear error messages for each failure type
- Proper exit codes
- No crashes or stack traces in normal error conditions
- Cleanup of partial outputs on failure

## Test Data Management

### Required Test PDFs

Create or obtain the following test files:

1. **`fixtures/basic.pdf`** - Simple 5-page document with:

   - Clear chapter structure (3 chapters)
   - Basic text formatting (headings, paragraphs, lists)
   - No images or complex tables
   - Bookmarks/outline present

1. **`fixtures/illustrated-guide.pdf`** - 10-15 page document with:

   - Mixed text and images
   - Various image formats (PNG, JPEG)
   - Figure captions
   - Image-text integration

1. **`fixtures/data-manual.pdf`** - Document focused on tables:

   - Simple tables (2-3 columns)
   - Complex tables (merged cells, headers)
   - Mixed table and text content
   - Various table formatting styles

1. **`fixtures/academic-paper.pdf`** - Research paper format:

   - Multi-column layout
   - Footnotes and references
   - Mathematical notation
   - Bibliography

1. **`fixtures/comprehensive-manual.pdf`** - Large document (100+ pages):

   - Complete book structure
   - All content types (text, images, tables)
   - Complex navigation structure
   - Performance testing target

1. **`fixtures/scanned-document.pdf`** - OCR test target:

   - Low text coverage (scanned images)
   - Mixed scanned and digital content
   - Various text qualities

1. **`fixtures/single-page.pdf`** - Minimal edge case:

   - Single page document
   - Minimal content
   - Edge case testing

### Test Data Generation

For test files that don't exist, create them using:

1. **LibreOffice/Word**: Create structured documents and export to PDF
1. **LaTeX**: Generate academic-style documents with complex formatting
1. **Scanning simulation**: Create low-quality scanned-style PDFs
1. **Programmatic generation**: Use Python libraries to create specific test cases

## Validation Framework

### Automated Validation Scripts

Create validation scripts for each test scenario:

```python
# Example validation script structure
def validate_e2e_001_basic_conversion(output_dir: Path) -> ValidationResult:
    """Validate basic conversion test outputs."""
    results = ValidationResult()
    
    # Check file structure
    results.add_check("module_json_exists", 
                     (output_dir / "module.json").exists())
    
    # Validate module.json content
    module_json = load_json(output_dir / "module.json")
    results.add_check("module_id_correct", 
                     module_json.get("id") == "e2e-basic-test")
    
    # Check journal entries
    sources_dir = output_dir / "sources" / "journals"
    journal_files = list(sources_dir.glob("*.json"))
    results.add_check("journal_files_present", len(journal_files) > 0)
    
    # Validate content structure
    for journal_file in journal_files:
        journal_data = load_json(journal_file)
        results.add_check(f"journal_{journal_file.stem}_valid",
                         validate_journal_schema(journal_data))
    
    return results
```

### Content Validation Criteria

#### Module Structure Validation

- [ ] `module.json` present and valid
- [ ] Required directories exist (`assets/`, `sources/`, `styles/`)
- [ ] File permissions correct
- [ ] No unexpected files or directories

#### Module.json Validation

- [ ] Valid JSON format
- [ ] Required fields present (`id`, `title`, `version`, `compatibility`)
- [ ] Foundry v13 compatibility declared
- [ ] Pack configuration correct
- [ ] Author and license information (when provided)

#### Journal Entry Validation

- [ ] Valid JSON format for all journal files
- [ ] Required fields present (`_id`, `name`, `pages`)
- [ ] Deterministic ID format (16-character hex)
- [ ] Page structure correct (`type: "text"`, `text.format: 1`)
- [ ] HTML content wrapped in `<div class="pdf2foundry">`

#### Content Fidelity Validation

- [ ] Text content matches PDF source
- [ ] Heading structure preserved
- [ ] List formatting maintained
- [ ] Image references correct
- [ ] Table structure appropriate for mode
- [ ] Internal links functional

#### Asset Validation

- [ ] All images extracted to `assets/`
- [ ] Image files not corrupted
- [ ] Image paths in HTML correct
- [ ] No missing asset references

#### TOC Validation

- [ ] TOC entry present (when enabled)
- [ ] UUID links to all chapters/sections
- [ ] Link format correct: `@UUID[JournalEntry.<id>.JournalEntryPage.<id>]`
- [ ] Link targets exist and are valid

## Performance Benchmarks

### Target Performance Metrics

| Document Size           | Expected Processing Time | Memory Usage |
| ----------------------- | ------------------------ | ------------ |
| Small (1-10 pages)      | < 30 seconds             | < 500MB      |
| Medium (11-50 pages)    | < 2 minutes              | < 1GB        |
| Large (51-100 pages)    | < 5 minutes              | < 2GB        |
| Very Large (100+ pages) | < 10 minutes             | < 4GB        |

### Performance Test Scenarios

1. **Baseline Performance**: Single-threaded, minimal features
1. **Multi-threading Impact**: Compare 1, 2, 4 worker performance
1. **Feature Impact**: Measure overhead of OCR, VLM, structured tables
1. **Cache Performance**: Compare initial vs. cached run times
1. **Memory Efficiency**: Monitor peak memory usage during processing

## Test Execution Framework

### Test Runner Script

```bash
#!/bin/bash
# run-e2e-tests.sh - Execute all E2E test scenarios

set -e

TEST_OUTPUT_DIR="test-output"
RESULTS_FILE="e2e-test-results.json"

# Clean previous test outputs
rm -rf "$TEST_OUTPUT_DIR"
mkdir -p "$TEST_OUTPUT_DIR"

# Initialize results
echo '{"tests": [], "summary": {}}' > "$RESULTS_FILE"

# Execute test scenarios
for test_scenario in e2e-{001..010}*; do
    echo "Running $test_scenario..."
    
    start_time=$(date +%s)
    
    if run_test_scenario "$test_scenario"; then
        status="PASS"
    else
        status="FAIL"
    fi
    
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    # Record results
    record_test_result "$test_scenario" "$status" "$duration"
done

# Generate summary report
generate_test_report "$RESULTS_FILE"
```

### Continuous Integration Integration

```yaml
# .github/workflows/e2e-tests.yml
name: End-to-End Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        pip install -e .[dev]
        sudo apt-get install tesseract-ocr
    
    - name: Set up Node.js for Foundry CLI
      uses: actions/setup-node@v4
      with:
        node-version: '18'
    
    - name: Install Foundry CLI
      run: npm install
    
    - name: Run E2E tests
      run: |
        chmod +x scripts/run-e2e-tests.sh
        ./scripts/run-e2e-tests.sh
    
    - name: Upload test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: e2e-test-results
        path: |
          test-output/
          e2e-test-results.json
```

## Test Maintenance

### Regular Test Updates

1. **Monthly**: Review test data for relevance and coverage
1. **Per Release**: Update expected outputs for format changes
1. **Feature Addition**: Add new test scenarios for new features
1. **Performance Regression**: Update benchmarks and thresholds

### Test Data Refresh

1. **Quarterly**: Review and update test PDF files
1. **Version Updates**: Ensure compatibility with new Foundry versions
1. **Library Updates**: Test with updated Docling/dependency versions

### Failure Investigation Process

1. **Immediate**: Determine if failure is test issue or product issue
1. **Analysis**: Compare actual vs. expected outputs in detail
1. **Root Cause**: Identify specific component or integration failure
1. **Resolution**: Fix product issue or update test expectations
1. **Prevention**: Add regression test if needed

## Success Criteria

### Test Suite Success Metrics

- **Coverage**: All major CLI options and feature combinations tested
- **Reliability**: < 5% false positive rate on test failures
- **Performance**: Test suite completes in < 30 minutes
- **Maintainability**: Tests remain stable across minor product updates

### Quality Gates

Before any release, the E2E test suite must:

- [ ] Pass all test scenarios (100% pass rate)
- [ ] Meet all performance benchmarks
- [ ] Validate output compatibility with Foundry VTT v13
- [ ] Demonstrate graceful error handling
- [ ] Confirm feature integration stability

This comprehensive E2E testing strategy ensures PDF2Foundry delivers reliable, high-quality PDF to Foundry VTT module conversion across all supported features and use cases.
