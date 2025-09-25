# Development Guide

## Environment Setup

### Prerequisites

**System Requirements:**

- **Python 3.12+**: Core runtime environment
- **Node.js 24+**: Required for Foundry CLI pack compilation
- **Tesseract OCR**: Required for OCR functionality
- **Git**: Version control
- **Internet Connection**: For downloading ML models (~1GB on first use)

**Development Tools:**

- Virtual environment support
- Code editor with Python support (VSCode/Cursor recommended)

### System Dependencies Installation

#### Node.js 24+ and Foundry CLI

```bash
# Install Node.js 24+ (visit https://nodejs.org for installers)
# Then install Foundry CLI in your project directory:
npm install @foundryvtt/foundryvtt-cli
```

#### Tesseract OCR

```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# Windows
# Download from https://github.com/UB-Mannheim/tesseract/wiki
```

### Initial Setup

1. **Clone and setup virtual environment:**

   ```bash
   git clone https://github.com/martin-papy/pdf2foundry.git
   cd pdf2foundry
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

1. **Install pre-commit hooks:**

   ```bash
   pre-commit install
   ```

### Environment Validation

After setup, validate your development environment:

```bash
# Activate virtual environment
source .venv/bin/activate

# Check Python and Docling environment
pdf2foundry doctor

# Verify system dependencies
node --version    # Should be 24+
tesseract --version    # Should show Tesseract info
npx @foundryvtt/foundryvtt-cli --version    # Should show Foundry CLI

# Run a quick test to ensure everything works
pytest tests/unit/test_caps.py -v
```

**Expected Output:**

- ✅ Python 3.12+ detected
- ✅ Docling environment functional
- ✅ All system dependencies available
- ✅ Unit tests pass

## Development Workflow

### Code Quality Gates

This project uses strict quality gates that **must pass** before any commit:

- **Ruff**: Linting and formatting
- **Black**: Code formatting
- **MyPy**: Type checking (strict mode)
- **Pytest**: Test suite with 90% coverage requirement

### Running Quality Checks

```bash
# Activate virtual environment (REQUIRED)
source .venv/bin/activate

# Run all quality checks
pre-commit run --all-files

# Run tests with coverage
pytest tests/ -v

# Individual tools (for debugging)
ruff check src/
black --check src/
mypy src/
```

## Git Workflow

### Committing Code

**Important**: Our pre-commit hooks use `language: system`, which means they depend on your active virtual environment.

#### Option 1: Terminal Commits (Recommended)

```bash
# Ensure virtual environment is active
source .venv/bin/activate

# Stage your changes
git add .

# Commit (pre-commit hooks will run automatically)
git commit -m "Your commit message"
```

#### Option 2: GUI Commits (VSCode/Cursor)

For GUI commits to work properly:

1. **Launch your editor from terminal** where venv is active:

   ```bash
   source .venv/bin/activate
   cursor .  # or code .
   ```

1. **Or configure your editor's Git path** to use the same Git binary as your terminal.

### Troubleshooting Git Issues

If you encounter pre-commit failures that work in terminal but fail in GUI:

1. **Run the debug hook** to compare environments:

   ```bash
   # From terminal (working environment)
   source .venv/bin/activate
   pre-commit run debug-env --hook-stage manual

   # Then try GUI commit to generate comparison log
   # Check .git/precommit-debug.log for differences
   ```

1. **Common issues:**

   - Virtual environment not activated in GUI context
   - Different Python/Git paths between terminal and GUI
   - Line ending differences (should be resolved by .gitattributes)

1. **Quick fixes:**

   - Always launch editor from activated terminal
   - Ensure consistent Git configuration
   - Use `git add -A && git commit` from terminal as fallback

## MyPy Configuration

We use a **hybrid approach** for MyPy:

- **Pre-commit**: Uses `--no-incremental --cache-dir=/dev/null` for reliability
- **Local development**: Uses incremental mode for speed
- **CI**: Uses the same reliable settings as pre-commit

This eliminates SQLite lock issues while maintaining performance.

## Testing

### Running Tests

```bash
# Activate virtual environment (REQUIRED)
source .venv/bin/activate

# Run all tests with coverage
pytest tests/ -v

# Run only unit tests (fast)
pytest tests/unit/ -v

# Run E2E tests (requires system dependencies)
pytest tests/e2e/ -v

# Run specific test tiers
pytest tests/e2e/ -m "tier1"  # Core functionality tests
pytest tests/e2e/ -m "tier2"  # Feature tests
pytest tests/e2e/ -m "tier3"  # ML/AI tests (requires models)
```

### Coverage Requirements

- **Minimum coverage**: 90%
- **Coverage is enforced** in pre-commit hooks and CI
- **Unit tests**: Focus on individual component testing
- **E2E tests**: Validate complete conversion pipeline
- Add tests for any new functionality

### Test Structure

```text
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests (70+ test files)
│   ├── test_*.py           # Test modules mirroring src/ structure
│   └── fixtures/           # Unit test data
└── e2e/                    # End-to-end tests
    ├── conftest.py         # E2E-specific fixtures
    ├── test_e2e_*.py      # E2E test suites by feature
    ├── utils/              # Testing utilities
    │   ├── fixtures.py     # PDF fixture management
    │   ├── validation.py   # Schema and structure validation
    │   ├── performance.py  # Performance testing utilities
    │   └── *.py           # Specialized test helpers
    ├── fixtures/           # Test PDF files and metadata
    │   ├── *.pdf          # Various test PDFs
    │   └── manifest.json   # Fixture checksums
    ├── schemas/            # JSON Schema definitions
    │   └── module.schema.json  # Foundry v13 module schema
    └── perf/              # Performance baselines and results
        ├── baseline.json   # Performance baselines
        └── latest.json     # Latest test results
```

### Test Categories

#### **Unit Tests** (`tests/unit/`)

- **Fast execution**: < 1 second per test
- **No external dependencies**: Pure Python logic testing
- **High coverage**: Target 95%+ for core modules
- **Isolated**: Mock external services and file I/O

#### **E2E Tests** (`tests/e2e/`)

Refer to [E2E testing Strategy](.e2e-testing-strategy.md)

- **Complete pipeline**: PDF → Foundry module conversion
- **Real dependencies**: Requires Tesseract, Node.js, etc.
- **Tiered execution**:
  - **Tier 1**: Core functionality (always run)
  - **Tier 2**: Advanced features (OCR, tables, images)
  - **Tier 3**: ML/AI features (conditional on model availability)

#### **Performance Tests**

- **Regression detection**: 20% threshold (configurable)
- **Baseline management**: Automated baseline updates
- **Multi-scenario**: Different PDF sizes and configurations
- **CI integration**: Performance summaries in PRs

### ML/AI Development Considerations

#### **Model Management**

- **Default VLM**: `Salesforce/blip-image-captioning-base` (~1GB)
- **Model Caching**: Models cached in `HF_HOME` directory
- **Offline Development**: Use `--no-ml` flag for faster iteration
- **CI Testing**: Conditional ML tests based on model availability

#### **Environment Variables for ML Testing**

```bash
# Hugging Face model cache (optional)
export HF_HOME=/path/to/model/cache

# Hugging Face API token (for rate-limited models)
export HF_TOKEN=your_token_here

# Skip ML features in development
export PDF2FOUNDRY_NO_ML=1
```

#### **Testing ML Features**

```bash
# Test with ML features enabled (requires models)
pytest tests/e2e/ -m "tier3"

# Test ML error handling
pytest tests/e2e/test_e2e_010_vlm_errors.py

# Test conditional ML execution
pytest tests/e2e/test_e2e_conditional_ml.py
```

#### **Performance Considerations**

- **Model Download**: First run downloads ~1GB of models
- **Memory Usage**: VLM processing requires additional RAM
- **Processing Time**: Image descriptions add significant processing time
- **CI Optimization**: Use model caching and conditional execution

## Performance Notes

- **Pre-commit runtime**: ~40-45 seconds (optimized for reliability)
- **MyPy caching**: Enabled locally, disabled in CI/pre-commit
- **Parallel execution**: Disabled to prevent SQLite lock issues

## Architecture Decisions

### Why `language: system` for Pre-commit?

- **Performance**: Uses your exact dependencies and mypy cache
- **Accuracy**: Tests against your actual environment
- **Trade-off**: Requires environment consistency between terminal and GUI

### Why Universal `# type: ignore`?

- **Compatibility**: Works across different mypy configurations
- **Reliability**: Prevents VSCode vs terminal mypy differences
- **Maintainability**: Simpler than managing specific error codes

## Troubleshooting

### Common Issues

#### **Environment Setup Issues**

1. **"Virtual environment not found"**

   - **Solution**: `source .venv/bin/activate` before any git operations
   - **Prevention**: Always launch editor from activated terminal

1. **"Node.js version too old"**

   - **Solution**: Install Node.js 24+ from <https://nodejs.org>
   - **Check**: `node --version` should show v24.x.x or higher

1. **"Tesseract not found"**

   - **Solution**: Install Tesseract OCR for your platform (see installation section)
   - **Check**: `tesseract --version` should show version info

1. **"Foundry CLI not available"**

   - **Solution**: `npm install @foundryvtt/foundryvtt-cli` in project root
   - **Check**: `npx @foundryvtt/foundryvtt-cli --version`

#### **Development Issues**

1. **"MyPy SQLite database locked"**

   - **Solution**: Already resolved with `--no-incremental --cache-dir=/dev/null`
   - **Alternative**: Delete `.mypy_cache` directory

1. **"Tests fail in pre-commit but pass manually"**

   - **Solution**: Ensure you're running tests in the same environment
   - **Check**: Compare `python --version` in terminal vs pre-commit

1. **"E2E tests skipped or failing"**

   - **Solution**: Verify system dependencies with `pdf2foundry doctor`
   - **Check**: Ensure test fixtures are available in `tests/e2e/fixtures/`

1. **"ML tests failing or skipped"**

   - **Solution**: Models not cached - run with internet connection first
   - **Alternative**: Use `--no-ml` flag or `PDF2FOUNDRY_NO_ML=1`

#### **Performance Issues**

1. **"Pre-commit hooks too slow"**

   - **Expected**: ~40-45 seconds is normal for reliability
   - **Alternative**: Use `git commit --no-verify` for quick commits (not recommended)

1. **"Tests taking too long"**

   - **Solution**: Run unit tests only: `pytest tests/unit/`
   - **Alternative**: Use specific test markers: `pytest -m "not tier3"`

### Getting Help

#### **Diagnostic Commands**

```bash
# Environment diagnostics
pdf2foundry doctor

# Pre-commit debug information
pre-commit run debug-env --hook-stage manual

# Test environment check
pytest tests/e2e/test_conftest.py -v

# Feature availability check
python -c "from pdf2foundry.core.feature_detection import FeatureAvailability; print(FeatureAvailability.get_available_features())"
```

#### **Debug Logs**

1. **Pre-commit issues**: Check `.git/precommit-debug.log`
1. **Test failures**: Use `pytest -v -s` for detailed output
1. **CLI issues**: Use `pdf2foundry convert --verbose --verbose` for debug output
1. **Environment differences**: Compare terminal vs GUI environments

#### **Support Checklist**

1. ✅ Virtual environment activated
1. ✅ System dependencies installed (Node.js 24+, Tesseract)
1. ✅ `pdf2foundry doctor` passes
1. ✅ Unit tests pass: `pytest tests/unit/ -v`
1. ✅ Pre-commit hooks installed: `pre-commit install`

## Best Practices

### **Development Workflow**

- **Always activate venv** before development: `source .venv/bin/activate`
- **Launch editor from terminal** for GUI consistency: `cursor .` or `code .`
- **Run quality checks locally** before pushing: `pre-commit run --all-files`
- **Validate environment** regularly: `pdf2foundry doctor`

### **Testing Strategy**

- **Write tests first** for new functionality (TDD approach)
- **Run unit tests frequently**: `pytest tests/unit/ -v` (fast feedback)
- **Run E2E tests before PR**: `pytest tests/e2e/ -m "tier1"` (core validation)
- **Test ML features conditionally**: Use `--no-ml` for faster iteration

### **Code Quality**

- **Follow type hints**: All functions should have proper type annotations
- **Maintain coverage**: Aim for 95%+ coverage on new code
- **Document public APIs**: Use docstrings for all public functions/classes
- **Keep modules focused**: Avoid files larger than ~500 lines

### **Performance Optimization**

- **Profile before optimizing**: Use performance tests to identify bottlenecks
- **Cache expensive operations**: Leverage Docling JSON caching
- **Use multi-worker processing**: Test with different worker counts
- **Monitor memory usage**: Especially for ML features

### **Dependency Management**

- **Keep dependencies updated** regularly: `pip list --outdated`
- **Pin versions in pyproject.toml**: Ensure reproducible builds
- **Test with minimal dependencies**: Use `ci-minimal` extra for core testing
- **Document system requirements**: Update docs when adding new dependencies

### **Git Workflow**

- **Use conventional commits**: `feat:`, `fix:`, `docs:`, etc.
- **Document breaking changes** in commit messages and RELEASE_NOTES.md
- **Keep commits atomic**: One logical change per commit
- **Test before committing**: Pre-commit hooks enforce this

### **ML/AI Development**

- **Use model caching**: Set `HF_HOME` to avoid repeated downloads
- **Test offline scenarios**: Ensure graceful degradation with `--no-ml`
- **Validate model outputs**: Check image descriptions for quality
- **Monitor resource usage**: ML features are memory and time intensive
