from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from ..ids import compute_deterministic_id
from ..types import ImageReference, PdfDocumentWithImages, PdfPagesLike


def extract_images(document: PdfPagesLike) -> list[ImageReference]:
    images: list[ImageReference] = []
    for page_index in range(len(document)):
        page = document[page_index]
        try:
            raw_list = page.get_images(full=True)
        except Exception:  # pragma: no cover - passthrough safety
            raw_list = []
        for item in raw_list:
            seq = cast(tuple[Any, ...], item)
            xref = int(seq[0]) if len(seq) > 0 else -1
            width = int(seq[2]) if len(seq) > 2 else None
            height = int(seq[3]) if len(seq) > 3 else None
            name = str(seq[7]) if len(seq) > 7 else None
            images.append(
                ImageReference(
                    page_index=page_index,
                    xref=xref,
                    width=width,
                    height=height,
                    name=name,
                    ext=None,
                )
            )

    return images


def extract_image_bytes(document: PdfDocumentWithImages, xref: int) -> tuple[bytes, str]:
    info = document.extract_image(int(xref))
    data = info.get("image", b"")
    if not isinstance(data, bytes | bytearray):
        data = b""
    ext = info.get("ext", "bin")
    if not isinstance(ext, str) or not ext:
        ext = "bin"
    return bytes(data), ext.lower()


def generate_deterministic_image_name(
    mod_id: str, page_index: int, image_seq: int, ext: str
) -> str:
    chapter_key = f"page-{page_index:04d}"
    section_key = f"image-{image_seq:04d}"
    suffix = compute_deterministic_id(mod_id, chapter_key, section_key)[:8]
    safe_ext = (ext or "bin").lower()
    return f"p{page_index:04d}_i{image_seq:04d}_{suffix}.{safe_ext}"


def save_images(
    document: PdfDocumentWithImages,
    image_refs: list[ImageReference],
    assets_dir: Path,
    mod_id: str,
) -> list[tuple[ImageReference, Path, str]]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    results: list[tuple[ImageReference, Path, str]] = []
    per_page_counts: dict[int, int] = {}

    for ref in image_refs:
        seq = per_page_counts.get(ref.page_index, 0) + 1
        per_page_counts[ref.page_index] = seq

        data, ext = extract_image_bytes(document, ref.xref)
        filename = generate_deterministic_image_name(mod_id, ref.page_index, seq, ext)
        dest = assets_dir / filename
        dest.write_bytes(data)
        module_rel = f"modules/{mod_id}/assets/{filename}"
        results.append((ref, dest, module_rel))

    return results
