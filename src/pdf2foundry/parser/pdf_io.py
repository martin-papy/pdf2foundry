from __future__ import annotations

from pathlib import Path
from typing import cast

from ..types import PdfDocumentLike


def open_pdf(path: Path) -> PdfDocumentLike:
    import fitz

    return cast(PdfDocumentLike, fitz.open(str(path)))
