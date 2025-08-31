# PDF2Foundry

Convert born-digital PDFs into a Foundry VTT v12+ module compendium.

## Installation (dev)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev]
```

Enable pre-commit hooks:

```bash
pre-commit install
```

## Development

### Continuous Integration

The project uses GitHub Actions for CI/CD with the following checks:

- **Linting & Formatting**: Ruff, Black, and MyPy
- **Testing**: pytest with coverage reporting
- **Build**: Package building and installation testing
- **Cross-platform**: Testing on Ubuntu, Windows, and macOS

All checks must pass before merging. The CI runs on Python 3.12 and 3.13.

## CLI Usage

```bash
pdf2foundry --help
```

### Command

```bash
pdf2foundry convert \
  --pdf "My Book.pdf" \
  --mod-id "pdf2foundry-my-book" \
  --mod-title "My Book (PDF Import)" \
  --author "ACME" \
  --license "OGL" \
  --pack-name "my-book-journals" \
  --toc/--no-toc \
  --tables auto|image-only \
  --deterministic-ids/--no-deterministic-ids \
  --out-dir dist \
  --compile-pack/--no-compile-pack
```

- `--pdf` (required): Path to source PDF

- `--mod-id` (required): Module ID

- `--mod-title` (required): Module title

- `--author`: Author name

- `--license`: License string

- `--pack-name`: Pack name (default: `<mod-id>-journals`)

- `--toc`: Generate TOC entry (default: enabled)

- `--tables`: `auto` (default) or `image-only`

- `--deterministic-ids`: Use deterministic IDs (default: enabled)

  (compendium folders are native in v13)

- `--out-dir`: Output directory (default: `dist`)

- `--compile-pack`: Compile JSON sources to LevelDB pack using Foundry CLI (default: disabled)

## Output Layout

```text
<out-dir>/<mod-id>/
  module.json
  assets/
  styles/pdf2foundry.css
  sources/journals/*.json
  packs/<pack-name>/
```

See [docs/PRD.md](docs/PRD.md) and [docs/architecture_and_flow.md](docs/architecture_and_flow.md) for details.

## Pack Compilation (Foundry CLI)

- Requires Node.js (LTS) and the Foundry CLI as a devDependency (already configured in `package.json`).
- You can compile during `convert` with `--compile-pack`, or manually via npm:

```bash
npm run compile:pack --modid=<mod-id> --packname=<mod-id>-journals
```

Under the hood this runs:

```bash
npx @foundryvtt/foundryvtt-cli compilePack \
  --input dist/<mod-id>/sources/journals \
  --output dist/<mod-id>/packs/<mod-id>-journals
```
