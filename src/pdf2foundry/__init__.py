"""PDF2Foundry - Convert born-digital PDFs into Foundry VTT v13 module compendia."""

try:
    from importlib.metadata import version

    __version__ = version("pdf2foundry")
except ImportError:  # pragma: no cover - environment-specific fallback
    # Fallback for Python < 3.8 or if package not installed
    __version__ = "0.1.0"

__author__ = "Martin Papy"
__email__ = "martin.papy@gmail.com"
