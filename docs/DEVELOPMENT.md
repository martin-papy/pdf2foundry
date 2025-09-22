# Development Guide

## Environment Setup

### Prerequisites

- Python 3.12+
- Git
- Virtual environment activated

### Initial Setup

1. **Clone and setup virtual environment:**

   ```bash
   git clone <repository-url>
   cd pdf2foundry
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

1. **Install pre-commit hooks:**

   ```bash
   pre-commit install
   ```

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
source .venv/bin/activate
pytest tests/ -v
```

### Coverage Requirements

- **Minimum coverage**: 90%
- **Coverage is enforced** in pre-commit hooks
- Add tests for any new functionality

### Test Structure

```text
tests/
├── conftest.py          # Shared fixtures
├── test_*.py           # Test modules mirroring src/ structure
└── fixtures/           # Test data files
```

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

1. **"Virtual environment not found"**

   - Solution: `source .venv/bin/activate` before any git operations

1. **"MyPy SQLite database locked"**

   - Solution: Already resolved with `--no-incremental --cache-dir=/dev/null`

1. **"Tests fail in pre-commit but pass manually"**

   - Solution: Ensure you're running tests in the same environment

1. **"Line ending issues"**

   - Solution: `.gitattributes` should handle this automatically

### Getting Help

1. Check the debug log: `.git/precommit-debug.log`
1. Compare terminal vs GUI environments
1. Ensure consistent Python/Git versions
1. Verify virtual environment activation

## Best Practices

- **Always activate venv** before development
- **Launch editor from terminal** for GUI consistency
- **Run quality checks locally** before pushing
- **Keep dependencies updated** regularly
- **Write tests** for new functionality
- **Document breaking changes** in commit messages
