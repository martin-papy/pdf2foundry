# PDF2Foundry

Convert born-digital PDFs into a Foundry VTT v12+ module compendium.

## Installation (dev)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .[full,dev]
```

Enable pre-commit hooks:

```bash
pre-commit install
```

## CLI Usage

```bash
pdf2foundry --help
```

### Command

```bash
pdf2foundry run \
  --pdf "My Book.pdf" \
  --mod-id "pdf2foundry-my-book" \
  --mod-title "My Book (PDF Import)" \
  --author "ACME" \
  --license "OGL" \
  --pack-name "my-book-journals" \
  --toc/--no-toc \
  --tables auto|image-only \
  --deterministic-ids/--no-deterministic-ids \
  --depend-compendium-folders/--no-depend-compendium-folders \
  --images-dir assets \
  --out-dir dist
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
- `--depend-compendium-folders`: Depend on Compendium Folders (default: enabled)
- `--images-dir`: Images directory name (default: `assets`)
- `--out-dir`: Output directory (default: `dist`)

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
