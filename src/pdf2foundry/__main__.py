"""Main entry point for PDF2Foundry when run as a module."""

from pdf2foundry.cli import app

if __name__ == "__main__":  # pragma: no cover - executed only via `python -m`
    app()
