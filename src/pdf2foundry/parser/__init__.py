from __future__ import annotations

from pathlib import Path

__all__ = [
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
    "build_tables_html",
    "choose_table_renders",
    "convert_parsed_table_to_html",
    "detect_headings_heuristic",
    "detect_table_regions_with_camelot",
    "extract_image_bytes",
    "extract_images",
    "extract_outline",
    "extract_page_content",
    "extract_tables_with_camelot",
    "generate_deterministic_image_name",
    "open_pdf",
    "parsed_tables_to_renders",
    "renders_to_html",
    "save_images",
]

# Re-export types (explicit alias marks intent for linters)
from ..types import BlockDict as BlockDict
from ..types import ImageReference as ImageReference
from ..types import LinkAnnotation as LinkAnnotation
from ..types import OutlineItem as OutlineItem
from ..types import PageContent as PageContent
from ..types import PdfDocumentLike as PdfDocumentLike
from ..types import PdfDocumentWithImages as PdfDocumentWithImages
from ..types import PdfPagesLike as PdfPagesLike
from ..types import RawLinkDict as RawLinkDict
from ..types import TableCandidate as TableCandidate

# Re-export primary functions from modular submodules (explicit alias)
from .images import extract_image_bytes as extract_image_bytes
from .images import extract_images as extract_images
from .images import generate_deterministic_image_name as generate_deterministic_image_name
from .images import save_images as save_images
from .outline import detect_headings_heuristic as detect_headings_heuristic
from .outline import extract_outline as extract_outline
from .pdf_io import open_pdf as _open_pdf
from .tables import build_tables_html as build_tables_html
from .tables import choose_table_renders as choose_table_renders
from .tables import convert_parsed_table_to_html as convert_parsed_table_to_html
from .tables import detect_table_regions_with_camelot as detect_table_regions_with_camelot
from .tables import extract_tables_with_camelot as extract_tables_with_camelot
from .tables import parsed_tables_to_renders as parsed_tables_to_renders
from .tables import renders_to_html as renders_to_html
from .text_content import extract_page_content as extract_page_content


def open_pdf(path: Path) -> PdfDocumentLike:
    return _open_pdf(path)
