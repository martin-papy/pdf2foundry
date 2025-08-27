from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

from ..types import TableCandidate, TableRender
from .images import generate_deterministic_image_name

logger = logging.getLogger(__name__)


def detect_table_regions_with_camelot(
    pdf_path: Path,
    pages: str | None = None,
    *,
    flavor: str = "lattice",
    log: logging.Logger | None = None,
) -> list[TableCandidate]:
    active_logger = log or logger

    try:  # Local import to avoid hard dependency at runtime/tests
        import camelot
    except Exception:  # pragma: no cover - environment-dependent
        active_logger.info(
            "Camelot not installed; skipping table detection and deferring to image fallback."
        )
        return []

    try:
        tables = camelot.read_pdf(str(pdf_path), pages=pages or "all", flavor=flavor)
    except Exception as exc:  # pragma: no cover - depends on system libs
        active_logger.info("Camelot detection failed (%s); returning no tables.", exc)
        return []

    candidates: list[TableCandidate] = []
    try:
        for t in tables:
            page_raw = getattr(t, "page", None)
            page_index = int(page_raw) - 1 if isinstance(page_raw, str | int) else 0
            bbox = getattr(t, "_bbox", None)
            if (
                isinstance(bbox, list | tuple)
                and len(bbox) == 4
                and all(isinstance(v, int | float) for v in bbox)
            ):
                x1, y1, x2, y2 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
            else:
                continue

            candidates.append(TableCandidate(page_index=page_index, bbox=(x1, y1, x2, y2)))
    except Exception:  # pragma: no cover - defensive
        return []

    return candidates


def table_to_html_or_image(
    pdf_path: Path,
    mod_id: str,
    assets_dir: Path,
    candidates: Iterable[TableCandidate],
    *,
    camelot_enabled: bool = True,
) -> list[TableRender]:
    results: list[TableRender] = []

    import fitz

    doc = fitz.open(str(pdf_path))

    for idx, cand in enumerate(candidates):
        page = doc.load_page(cand.page_index)
        rect = fitz.Rect(*cand.bbox)

        html_str: str | None = None
        if camelot_enabled:
            try:
                import camelot

                tables = camelot.read_pdf(str(pdf_path), pages=str(cand.page_index + 1))
                if len(tables) > 0:
                    html_str = tables[0].to_html()
            except Exception:
                html_str = None

        if html_str:
            logger.info("Table HTML generated (page=%s, bbox=%s)", cand.page_index, cand.bbox)
            results.append(
                TableRender(
                    page_index=cand.page_index,
                    bbox=cand.bbox,
                    html=html_str,
                    image_path=None,
                    module_rel=None,
                    fallback=False,
                )
            )
            continue

        pix = page.get_pixmap(clip=rect, alpha=False)
        assets_dir.mkdir(parents=True, exist_ok=True)
        filename = generate_deterministic_image_name(mod_id, cand.page_index, idx + 1, "png")
        out_path = assets_dir / filename
        pix.save(str(out_path))
        logger.info(
            "Table rasterized to image (page=%s, bbox=%s, path=%s)",
            cand.page_index,
            cand.bbox,
            out_path,
        )
        results.append(
            TableRender(
                page_index=cand.page_index,
                bbox=cand.bbox,
                html=None,
                image_path=out_path,
                module_rel=f"modules/{mod_id}/assets/{filename}",
                fallback=True,
            )
        )

    return results


def render_table_fragment(render: TableRender) -> str:
    if render.html:
        return render.html
    assert render.module_rel is not None
    return f'<figure><img src="{render.module_rel}" alt="Table" /></figure>'
