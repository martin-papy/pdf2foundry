from __future__ import annotations

from pathlib import Path

from pdf2foundry.ingest.content_extractor import extract_semantic_content
from pdf2foundry.model.pipeline_options import PdfPipelineOptions


class _FakeDocEmbedded:
    def num_pages(self) -> int:  # pragma: no cover - trivial
        return 1

    def export_to_html(self, **kwargs: object) -> str:
        # Minimal HTML with an embedded base64 PNG image
        png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJ" "TYQAAAAASUVORK5CYII="
        return f'<div><img src="data:image/png;base64,{png_b64}"></div>'


class _FakeDocReferenced:
    def __init__(self, img_path: Path) -> None:
        self._img_path = img_path

    def num_pages(self) -> int:  # pragma: no cover - trivial
        return 1

    def export_to_html(self, **kwargs: object) -> str:
        return f'<div><img src="{self._img_path}"></div>'


def test_extract_embedded_base64_image(tmp_path: Path) -> None:
    from pdf2foundry.model.pipeline_options import PdfPipelineOptions

    out = extract_semantic_content(_FakeDocEmbedded(), tmp_path, PdfPipelineOptions())
    # One page, one image extracted
    assert len(out.images) == 1
    # File exists on disk in assets dir
    img_rel = out.images[0].src
    assert img_rel.startswith("assets/")
    assert (tmp_path / Path(img_rel).name).exists() or (tmp_path / img_rel).exists()
    # HTML was rewritten to point at assets/
    assert "assets/" in out.pages[0].html


def test_copy_referenced_local_image(tmp_path: Path) -> None:
    # Create a small binary to represent an image
    src_img = tmp_path / "orig.png"
    src_img.write_bytes(b"\x89PNG\r\n\x1a\n")
    out = extract_semantic_content(_FakeDocReferenced(src_img), tmp_path, PdfPipelineOptions())
    # Should have at least one referenced image copied
    assert any(img.name == src_img.name for img in out.images)
    # Copied file exists under assets/
    assert (tmp_path / src_img.name).exists() or (tmp_path / "assets" / src_img.name).exists()
    # HTML rewritten
    assert "assets/" in out.pages[0].html
