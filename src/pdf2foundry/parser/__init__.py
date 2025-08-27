from __future__ import annotations

from pathlib import Path

__all__ = [
    # types
    "BlockDict",
    "ImageReference",
    "LinkAnnotation",
    "OutlineItem",
    "PageContent",
    "PdfDocumentLike",
    "PdfDocumentWithImages",
    "PdfPagesLike",
    "RawLinkDict",
    "TableCandidate",
    # functions
    "extract_image_bytes",
    "extract_images",
    "generate_deterministic_image_name",
    "save_images",
    "detect_headings_heuristic",
    "extract_outline",
    "detect_table_regions_with_camelot",
    "extract_page_content",
    "open_pdf",
]

# Re-export types (explicit alias marks intent for linters)
from ..types import (
    BlockDict as BlockDict,
)
from ..types import (
    ImageReference as ImageReference,
)
from ..types import (
    LinkAnnotation as LinkAnnotation,
)
from ..types import (
    OutlineItem as OutlineItem,
)
from ..types import (
    PageContent as PageContent,
)
from ..types import (
    PdfDocumentLike as PdfDocumentLike,
)
from ..types import (
    PdfDocumentWithImages as PdfDocumentWithImages,
)
from ..types import (
    PdfPagesLike as PdfPagesLike,
)
from ..types import (
    RawLinkDict as RawLinkDict,
)
from ..types import (
    TableCandidate as TableCandidate,
)

# Re-export primary functions from modular submodules (explicit alias)
from .images import (
    extract_image_bytes as extract_image_bytes,
)
from .images import (
    extract_images as extract_images,
)
from .images import (
    generate_deterministic_image_name as generate_deterministic_image_name,
)
from .images import (
    save_images as save_images,
)
from .outline import (
    detect_headings_heuristic as detect_headings_heuristic,
)
from .outline import (
    extract_outline as extract_outline,
)
from .pdf_io import open_pdf as _open_pdf
from .tables import (
    detect_table_regions_with_camelot as detect_table_regions_with_camelot,
)
from .text_content import extract_page_content as extract_page_content


def open_pdf(path: Path) -> PdfDocumentLike:
    return _open_pdf(path)
