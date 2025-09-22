# End-to-End Testing for PDF2Foundry

This directory contains end-to-end tests for the PDF2Foundry CLI tool, designed to validate the complete conversion pipeline from PDF input to Foundry VTT module output.

## Test Structure

```text
tests/e2e/
├── README.md                    # This file
├── conftest.py                  # Pytest configuration and fixtures
├── test_smoke.py               # Basic smoke tests
├── utils/                      # Shared testing utilities
│   ├── __init__.py
│   ├── fixtures.py             # Fixture management and PDF generation
│   ├── validation.py           # JSON Schema and asset validation
│   ├── assertions.py           # Rich assertion helpers
│   └── performance.py          # Performance testing utilities
├── schemas/                    # JSON Schema definitions
│   └── module.schema.json      # Foundry v13 module.json schema
├── fixtures/                   # Test fixture metadata
│   └── manifest.json           # Fixture checksums and metadata
└── perf/                      # Performance test results
    └── latest.json             # Latest performance metrics
```

## Environment Variables

Configure these environment variables for testing:

### Required

- `PDF2FOUNDRY_CLI`: Path to the pdf2foundry CLI binary (default: `pdf2foundry` if on PATH)

### Optional

- `HF_HOME`: Hugging Face model cache directory (for VLM tests)
- `HF_TOKEN`: Hugging Face API token (for rate-limited models)
- `FOUNDRY_CLI_CMD`: Foundry CLI command (e.g., `fvtt` or `npx @foundryvtt/foundry-cli`)

### Performance Environment Variables

- `PERF_THRESHOLD`: Performance regression threshold (default: 0.2 = 20%)
- `PERF_THRESHOLD_CI`: Relaxed threshold for CI environments (default: 1.5 × PERF_THRESHOLD)
- `PERF_UPDATE_BASELINE`: Set to "1" to update performance baselines (default: "0")
- `E2E_PERF`: Set to "1" to run performance tests in PR CI (default: "0", skipped)
- `NIGHTLY`: Set to "1" to run performance tests in nightly builds (default: "0")
- `CI`: Set to "1" to enable CI-specific behaviors (timeouts, thresholds) (default: "0")

## Test Markers

Use pytest markers to run specific test categories:

```bash
# Run all E2E tests
pytest tests/e2e/

# Run only fast tests (exclude slow ones)
pytest tests/e2e/ -m "not slow"

# Run performance tests (normally skipped in PR CI)
E2E_PERF=1 pytest tests/e2e/ -m "perf"

# Run tests that require OCR
pytest tests/e2e/ -m "ocr"

# Run tests that require Vision Language Models
pytest tests/e2e/ -m "vlm"

# Run integration tests
pytest tests/e2e/ -m "integration"

# Run error handling tests
pytest tests/e2e/ -m "errors"

# Run tests that use caching
pytest tests/e2e/ -m "cache"

# Run tests that involve pack compilation
pytest tests/e2e/ -m "pack"
```

## Marker Definitions

- `slow`: Tests that take significant time to complete
- `perf`: Performance benchmarking tests
- `cache`: Tests that verify caching functionality
- `ocr`: Tests requiring OCR capabilities (Tesseract)
- `vlm`: Tests requiring Vision Language Models
- `pack`: Tests involving Foundry pack compilation
- `integration`: Integration tests with external tools
- `errors`: Error handling and edge case tests

## Performance Testing

Performance tests (`test_e2e_006_performance.py`) benchmark conversion speed and validate functionality:

### Test Scenarios

- **Threading Performance**: Compare single-threaded vs multi-threaded processing
- **Page Selection**: Validate `--pages` functionality and measure timing differences
- **Baseline Comparison**: Track performance over time and detect regressions

### CI Integration

Performance tests are **skipped by default in PR CI** to avoid flakiness and long runtimes:

```bash
# Run performance tests locally
E2E_PERF=1 pytest tests/e2e/test_e2e_006_performance.py -v

# Run in nightly builds (CI)
NIGHTLY=1 pytest tests/e2e/ -m "perf"

# Update performance baselines (use with caution)
PERF_UPDATE_BASELINE=1 pytest tests/e2e/ -m "perf"
```

### Performance Data

- **Metrics**: Stored in `tests/e2e/perf/` as JSON files with timestamps
- **Baselines**: Computed from historical averages for regression detection
- **Thresholds**: Default 20% regression threshold, configurable via `PERF_THRESHOLD`

## Local Setup

1. **Install E2E dependencies:**

   ```bash
   pip install -e ".[e2e]"
   ```

1. **Set environment variables:**

   ```bash
   export PDF2FOUNDRY_CLI="pdf2foundry"  # or path to binary
   export HF_HOME="$HOME/.cache/huggingface"  # optional
   ```

1. **Run smoke tests:**

   ```bash
   pytest tests/e2e/test_smoke.py -v
   ```

1. **Run all E2E tests:**

   ```bash
   pytest tests/e2e/ -v
   ```

## Parallel Execution

E2E tests support parallel execution using pytest-xdist:

```bash
# Run tests in parallel (auto-detect CPU count)
pytest tests/e2e/ -n auto

# Run with specific number of workers
pytest tests/e2e/ -n 4

# Disable parallel execution
pytest tests/e2e/ -n 0
```

## Fixture Management

Test fixtures are managed through:

- `fixtures/manifest.json`: Metadata and checksums for all test PDFs
- `utils/fixtures.py`: Utilities for accessing and verifying fixtures
- Automatic checksum verification to ensure test data integrity
- Synthetic PDF generation for controlled test scenarios

## Validation and Assertions

The test suite includes comprehensive validation:

- **JSON Schema validation**: Foundry module.json structure
- **Asset validation**: Referenced images and files exist and are accessible
- **TOC validation**: Table of contents links resolve correctly
- **Rich assertions**: Detailed diff output for failures using the Rich library

## Troubleshooting

### Common Issues

1. **CLI not found**: Set `PDF2FOUNDRY_CLI` environment variable
1. **Missing dependencies**: Run `pip install -e ".[e2e]"`
1. **Fixture checksum failures**: Fixtures may have been modified
1. **Performance test failures**: Check `PERF_THRESHOLD` setting
1. **Parallel test conflicts**: Use unique temp directories per test

### Debug Mode

Run tests with verbose output and logging:

```bash
pytest tests/e2e/ -v -s --log-cli-level=DEBUG
```

### Skip Missing Dependencies

Tests automatically skip when required tools are unavailable:

- Tesseract (for OCR tests)
- Node.js (for Foundry CLI tests)
- Foundry CLI (for pack compilation tests)

## Contributing

When adding new E2E tests:

1. Use appropriate markers for categorization
1. Follow the AAA pattern (Arrange, Act, Assert)
1. Use descriptive test names explaining the scenario
1. Add fixtures to `manifest.json` with checksums
1. Use the provided utilities for validation and assertions
1. Consider performance implications for slow tests
