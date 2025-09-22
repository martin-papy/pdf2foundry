"""Content data structures for semantic extraction (HTML, images, tables, links)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass(slots=True)
class BBox:
    """Bounding box in page coordinates."""

    x: float  # Left coordinate
    y: float  # Top coordinate
    w: float  # Width
    h: float  # Height

    def __post_init__(self) -> None:
        """Validate bounding box dimensions."""
        if self.w < 0:
            raise ValueError(f"Width must be non-negative, got {self.w}")
        if self.h < 0:
            raise ValueError(f"Height must be non-negative, got {self.h}")

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary for serialization."""
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> BBox:
        """Create from dictionary."""
        return cls(x=data["x"], y=data["y"], w=data["w"], h=data["h"])


@dataclass(slots=True)
class TableCell:
    """A cell in a structured table."""

    text: str  # Cell text content
    bbox: BBox  # Cell bounding box
    row_span: int = 1  # Number of rows spanned
    col_span: int = 1  # Number of columns spanned
    is_header: bool = False  # Whether this is a header cell

    def __post_init__(self) -> None:
        """Validate cell spans."""
        if self.row_span < 1:
            raise ValueError(f"Row span must be >= 1, got {self.row_span}")
        if self.col_span < 1:
            raise ValueError(f"Column span must be >= 1, got {self.col_span}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "text": self.text,
            "bbox": self.bbox.to_dict(),
            "row_span": self.row_span,
            "col_span": self.col_span,
            "is_header": self.is_header,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TableCell:
        """Create from dictionary."""
        return cls(
            text=data["text"],
            bbox=BBox.from_dict(data["bbox"]),
            row_span=data.get("row_span", 1),
            col_span=data.get("col_span", 1),
            is_header=data.get("is_header", False),
        )


@dataclass(slots=True)
class StructuredTable:
    """A structured table with semantic cell information."""

    id: str  # Deterministic table ID
    bbox: BBox  # Table bounding box
    rows: list[list[TableCell]]  # 2D array of table cells
    caption: str | None = None  # Optional table caption
    meta: dict[str, Any] = field(default_factory=dict)  # Metadata (source_page, confidence, etc.)

    def __post_init__(self) -> None:
        """Validate table structure."""
        if not self.rows:
            raise ValueError("Table must have at least one row")

        # Validate that all rows have the same number of logical columns
        # (accounting for colspan)
        if len(self.rows) > 1:
            first_row_cols = sum(cell.col_span for cell in self.rows[0])
            for i, row in enumerate(self.rows[1:], 1):
                row_cols = sum(cell.col_span for cell in row)
                if row_cols != first_row_cols:
                    raise ValueError(f"Row {i} has {row_cols} logical columns, " f"but first row has {first_row_cols}")

    @classmethod
    def from_detector(
        cls,
        detector_output: Any,
        page_num: int,
        id_seed: str,
        caption: str | None = None,
        confidence: float = 1.0,
    ) -> StructuredTable:
        """Create StructuredTable from detector output.

        Args:
            detector_output: Raw output from table detection
            page_num: Source page number (1-based)
            id_seed: Seed for deterministic ID generation
            caption: Optional table caption
            confidence: Detection confidence (0.0-1.0)

        Returns:
            StructuredTable instance

        Note:
            Factory method for creating StructuredTable from detector output.
            Implementation depends on the specific table detector being used.
        """
        from pdf2foundry.model.id_utils import sha1_16_hex

        table_id = sha1_16_hex(f"{id_seed}|table|page_{page_num}")

        # Extract actual data from detector output
        # This will be implemented based on the specific detector format
        bbox = BBox(x=0, y=0, w=100, h=50)
        cell = TableCell(text="", bbox=BBox(x=0, y=0, w=100, h=25))
        rows = [[cell]]

        meta = {
            "source_page": page_num,
            "confidence": confidence,
            "detector": "docling",
        }

        return cls(
            id=table_id,
            bbox=bbox,
            rows=rows,
            caption=caption,
            meta=meta,
        )

    @classmethod
    def from_raster_fallback(
        cls,
        image_ref: str,
        page_num: int,
        bbox: BBox,
        id_seed: str,
        caption: str | None = None,
        confidence: float = 0.0,
    ) -> StructuredTable:
        """Create StructuredTable that references a rasterized image.

        Args:
            image_ref: Reference to rasterized table image
            page_num: Source page number (1-based)
            bbox: Table bounding box
            id_seed: Seed for deterministic ID generation
            caption: Optional table caption
            confidence: Detection confidence (0.0 for raster fallback)

        Returns:
            StructuredTable instance with raster fallback metadata
        """
        from pdf2foundry.model.id_utils import sha1_16_hex

        table_id = sha1_16_hex(f"{id_seed}|table_raster|page_{page_num}")

        # Create a single cell that spans the entire table area
        cell = TableCell(
            text=f"[Rasterized table: {image_ref}]",
            bbox=bbox,
        )
        rows = [[cell]]

        meta = {
            "source_page": page_num,
            "confidence": confidence,
            "raster_fallback": True,
            "image_ref": image_ref,
        }

        return cls(
            id=table_id,
            bbox=bbox,
            rows=rows,
            caption=caption,
            meta=meta,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "bbox": self.bbox.to_dict(),
            "rows": [[cell.to_dict() for cell in row] for row in self.rows],
            "caption": self.caption,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StructuredTable:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            bbox=BBox.from_dict(data["bbox"]),
            rows=[[TableCell.from_dict(cell_data) for cell_data in row_data] for row_data in data["rows"]],
            caption=data.get("caption"),
            meta=data.get("meta", {}),
        )


@dataclass(slots=True)
class HtmlPage:
    html: str
    page_no: int  # 1-based


@dataclass(slots=True)
class ImageAsset:
    """An image asset extracted from the PDF."""

    # Final resolved src in the page HTML (e.g., "assets/<file>")
    src: str
    page_no: int  # 1-based
    name: str

    # Enhanced metadata (optional, backward compatible)
    bbox: BBox | None = None  # Image bounding box
    caption: str | None = None  # Generated image caption
    meta: dict[str, Any] = field(default_factory=dict)  # Additional metadata

    @property
    def alt_text(self) -> str | None:
        """Get alt text for the image (alias for caption)."""
        return self.caption

    @alt_text.setter
    def alt_text(self, value: str | None) -> None:
        """Set alt text for the image (updates caption)."""
        self.caption = value

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "src": self.src,
            "page_no": self.page_no,
            "name": self.name,
        }

        # Only include optional fields if they have values
        if self.bbox is not None:
            result["bbox"] = self.bbox.to_dict()
        if self.caption is not None:
            result["caption"] = self.caption
        if self.meta:
            result["meta"] = self.meta

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImageAsset:
        """Create from dictionary."""
        bbox = None
        if "bbox" in data:
            bbox = BBox.from_dict(data["bbox"])

        return cls(
            src=data["src"],
            page_no=data["page_no"],
            name=data["name"],
            bbox=bbox,
            caption=data.get("caption"),
            meta=data.get("meta", {}),
        )


@dataclass(slots=True)
class TableContent:
    kind: Literal["html", "image", "structured"]
    page_no: int  # 1-based
    html: str | None = None
    image_name: str | None = None
    structured_table: StructuredTable | None = None


@dataclass(slots=True)
class LinkRef:
    kind: Literal["internal", "external"]
    source_page: int  # 1-based
    target: str


@dataclass(slots=True)
class ParsedContent:
    """Parsed content from a PDF document."""

    pages: list[HtmlPage] = field(default_factory=list)
    images: list[ImageAsset] = field(default_factory=list)
    tables: list[TableContent] = field(default_factory=list)
    links: list[LinkRef] = field(default_factory=list)
    assets_dir: Path | None = None

    # Enhanced structured content (optional, backward compatible)
    structured_tables: list[StructuredTable] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: dict[str, Any] = {
            "pages": [{"html": page.html, "page_no": page.page_no} for page in self.pages],
            "images": [img.to_dict() for img in self.images],
            "tables": [
                {
                    "kind": table.kind,
                    "page_no": table.page_no,
                    "html": table.html,
                    "image_name": table.image_name,
                }
                for table in self.tables
            ],
            "links": [
                {
                    "kind": link.kind,
                    "source_page": link.source_page,
                    "target": link.target,
                }
                for link in self.links
            ],
        }

        # Only include optional fields if they have values
        if self.assets_dir is not None:
            result["assets_dir"] = str(self.assets_dir)
        if self.structured_tables:
            result["structured_tables"] = [table.to_dict() for table in self.structured_tables]

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParsedContent:
        """Create from dictionary."""
        pages = [HtmlPage(html=p["html"], page_no=p["page_no"]) for p in data.get("pages", [])]
        images = [ImageAsset.from_dict(img_data) for img_data in data.get("images", [])]

        tables = []
        for table_data in data.get("tables", []):
            tables.append(
                TableContent(
                    kind=table_data["kind"],
                    page_no=table_data["page_no"],
                    html=table_data.get("html"),
                    image_name=table_data.get("image_name"),
                )
            )

        links = []
        for link_data in data.get("links", []):
            links.append(
                LinkRef(
                    kind=link_data["kind"],
                    source_page=link_data["source_page"],
                    target=link_data["target"],
                )
            )

        structured_tables = []
        if "structured_tables" in data:
            structured_tables = [StructuredTable.from_dict(table_data) for table_data in data["structured_tables"]]

        assets_dir = None
        if "assets_dir" in data:
            assets_dir = Path(data["assets_dir"])

        return cls(
            pages=pages,
            images=images,
            tables=tables,
            links=links,
            assets_dir=assets_dir,
            structured_tables=structured_tables,
        )


__all__ = [
    "BBox",
    "HtmlPage",
    "ImageAsset",
    "LinkRef",
    "ParsedContent",
    "StructuredTable",
    "TableCell",
    "TableContent",
]
