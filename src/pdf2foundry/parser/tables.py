from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from html import escape
from pathlib import Path
from typing import Any, cast

from ..types import (
    ParsedTable,
    TableCandidate,
    TableExtractionMetrics,
    TableRender,
)
from .images import generate_deterministic_image_name

logger = logging.getLogger(__name__)


def detect_table_regions_with_camelot(
    pdf_path: Path,
    pages: str | None = None,
    *,
    flavor: str = "lattice",
    log: logging.Logger | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> list[TableCandidate]:
    active_logger = log or logger

    try:  # Local import to avoid hard dependency at runtime/tests
        import camelot as _camelot

        camelot = cast(Any, _camelot)
    except Exception:  # pragma: no cover - environment-dependent
        active_logger.info(
            "Camelot not installed; skipping table detection and deferring to image fallback."
        )
        return []

    def _tables_to_candidates(tables_obj: Any) -> list[TableCandidate]:
        out: list[TableCandidate] = []
        try:
            for t in tables_obj:
                page_raw = getattr(t, "page", None)
                page_index = int(page_raw) - 1 if isinstance(page_raw, str | int) else 0
                bbox = getattr(t, "_bbox", None)
                if (
                    isinstance(bbox, list | tuple)
                    and len(bbox) == 4
                    and all(isinstance(v, int | float) for v in bbox)
                ):
                    x1, y1, x2, y2 = (
                        float(bbox[0]),
                        float(bbox[1]),
                        float(bbox[2]),
                        float(bbox[3]),
                    )
                else:
                    continue
                out.append(TableCandidate(page_index=page_index, bbox=(x1, y1, x2, y2)))
        except Exception:  # pragma: no cover - defensive
            return []
        return out

    # Fast path when no progress tracking is needed
    if on_progress is None and (pages is None or pages.strip().lower() == "all"):
        try:
            tables = camelot.read_pdf(str(pdf_path), pages="all", flavor=flavor)
        except Exception as exc:  # pragma: no cover - depends on system libs
            active_logger.info("Camelot detection failed (%s); returning no tables.", exc)
            return []
        return _tables_to_candidates(tables)

    # Progress-aware path: iterate per page
    try:
        import fitz
    except Exception:  # pragma: no cover - environment-dependent
        try:
            tables = camelot.read_pdf(str(pdf_path), pages=pages or "all", flavor=flavor)
        except Exception as exc:  # pragma: no cover - depends on system libs
            active_logger.info("Camelot detection failed (%s); returning no tables.", exc)
            return []
        return _tables_to_candidates(tables)

    doc = fitz.open(str(pdf_path))
    total_pages = doc.page_count
    page_numbers = list(range(1, total_pages + 1))

    candidates: list[TableCandidate] = []
    processed = 0
    for page_no in page_numbers:
        try:
            try:
                tables = camelot.read_pdf(str(pdf_path), pages=str(page_no), flavor=flavor)
            except Exception:  # pragma: no cover - depends on system libs
                tables = []

            for t in tables:
                page_raw = getattr(t, "page", None)
                page_index = int(page_raw) - 1 if isinstance(page_raw, str | int) else (page_no - 1)
                bbox = getattr(t, "_bbox", None)
                if (
                    isinstance(bbox, list | tuple)
                    and len(bbox) == 4
                    and all(isinstance(v, int | float) for v in bbox)
                ):
                    x1, y1, x2, y2 = (
                        float(bbox[0]),
                        float(bbox[1]),
                        float(bbox[2]),
                        float(bbox[3]),
                    )
                else:
                    continue
                candidates.append(TableCandidate(page_index=page_index, bbox=(x1, y1, x2, y2)))
        finally:
            processed += 1
            if on_progress is not None:
                on_progress(processed)

    return candidates


def extract_tables_with_camelot(
    pdf_path: Path,
    candidates: Iterable[TableCandidate],
    *,
    flavor: str = "lattice",
    log: logging.Logger | None = None,
) -> list[ParsedTable]:
    """Attempt to extract structured table data for the given candidate regions using Camelot.

    - Keeps Camelot as an optional dependency via local import.
    - Uses candidate page index to scope parsing and passes the candidate bbox as table_areas.
    - Captures basic parsing metrics (when available) via info-level logs.
    - Returns one TableRender per candidate when HTML is produced; candidates that
      yield no tables are skipped.
    """
    active_logger = log or logger

    try:  # Local import to avoid hard dependency at runtime/tests
        import camelot as _camelot

        camelot = cast(Any, _camelot)
    except Exception:  # pragma: no cover - environment-dependent
        active_logger.info(
            "Camelot not installed; skipping table extraction and returning no tables."
        )
        return []

    results: list[ParsedTable] = []
    for cand in candidates:
        pages = str(cand.page_index + 1)
        # Camelot expects "x1,y1,x2,y2" in PDF coordinate space. We pass-through the
        # candidate bbox; for most born-digital PDFs this matches expectations.
        table_areas = [f"{cand.bbox[0]},{cand.bbox[1]},{cand.bbox[2]},{cand.bbox[3]}"]

        try:
            tables = camelot.read_pdf(
                str(pdf_path), pages=pages, flavor=flavor, table_areas=table_areas
            )
        except Exception as exc:  # pragma: no cover - system libs dependent
            active_logger.info(
                "Camelot extraction failed on page=%s bbox=%s (%s)",
                cand.page_index,
                cand.bbox,
                exc,
            )
            continue

        if not tables:
            continue

        # Take the first detected table for this region
        try:
            t = tables[0]
            df = getattr(t, "df", None)
            # Log available parsing metrics when present
            report = getattr(t, "parsing_report", None)
            metrics: TableExtractionMetrics | None = None

            def _to_float(value: Any) -> float | None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            if isinstance(report, dict):
                acc = _to_float(report.get("accuracy"))
                ws = _to_float(report.get("whitespace"))
                order = _to_float(report.get("order"))
                metrics = TableExtractionMetrics(accuracy=acc, whitespace=ws, order=order)

            rows: list[list[str]] = []
            nrows = 0
            ncols = 0
            if df is not None:
                try:
                    # Camelot uses pandas DataFrame; get values as strings
                    nrows, ncols = int(df.shape[0]), int(df.shape[1])
                    for r in range(nrows):
                        row: list[str] = []
                        for c in range(ncols):
                            val = df.iat[r, c]
                            row.append("" if val is None else str(val))
                        rows.append(row)
                except Exception:  # pragma: no cover - defensive
                    rows = []
                    nrows = 0
                    ncols = 0

            # Simple acceptance heuristic: at least 2x2 and decent accuracy when available
            ok = (
                nrows >= 2
                and ncols >= 2
                and (metrics is None or metrics.accuracy is None or metrics.accuracy >= 90.0)
            )

            results.append(
                ParsedTable(
                    page_index=cand.page_index,
                    bbox=cand.bbox,
                    rows=rows,
                    nrows=nrows,
                    ncols=ncols,
                    metrics=metrics,
                    ok=ok,
                )
            )
        except Exception:  # pragma: no cover - defensive
            continue

    return results


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
                import camelot as _camelot

                camelot = cast(Any, _camelot)

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


def convert_parsed_table_to_html(parsed: ParsedTable) -> str:
    """Convert a ParsedTable into an HTML <table> string.

    Generates minimal semantic HTML suitable for Foundry VTT Journal pages.
    """
    rows_html: list[str] = []
    for row in parsed.rows:
        cells = "".join(f"<td>{escape(cell)}</td>" for cell in row)
        rows_html.append(f"<tr>{cells}</tr>")
    tbody = "".join(rows_html)
    return f"<table><tbody>{tbody}</tbody></table>"


def parsed_tables_to_renders(tables: Iterable[ParsedTable]) -> list[TableRender]:
    """Convert ParsedTable objects into TableRender entries with HTML.

    Image fields are left None and fallback=False because HTML was produced.
    """
    renders: list[TableRender] = []
    for t in tables:
        html_str = convert_parsed_table_to_html(t)
        renders.append(
            TableRender(
                page_index=t.page_index,
                bbox=t.bbox,
                html=html_str,
                image_path=None,
                module_rel=None,
                fallback=False,
            )
        )
    return renders


def renders_to_html(renders: Iterable[TableRender]) -> str:
    """Join render fragments into a single HTML string."""
    return "\n".join(render_table_fragment(r) for r in renders)


def build_tables_html(
    pdf_path: Path,
    mod_id: str,
    assets_dir: Path,
    candidates: list[TableCandidate],
    *,
    parsed_tables: list[ParsedTable] | None = None,
    camelot_enabled: bool = True,
) -> str:
    """High-level helper to produce final HTML for all table candidates.

    Uses parsed tables when ok=True, otherwise falls back to Camelot/image.
    """
    renders = choose_table_renders(
        pdf_path,
        mod_id,
        assets_dir,
        candidates,
        parsed_tables=parsed_tables,
        camelot_enabled=camelot_enabled,
    )
    return renders_to_html(renders)


def choose_table_renders(
    pdf_path: Path,
    mod_id: str,
    assets_dir: Path,
    candidates: list[TableCandidate],
    *,
    parsed_tables: list[ParsedTable] | None = None,
    camelot_enabled: bool = True,
) -> list[TableRender]:
    """Prefer parsed tables with ok=True; otherwise fall back to Camelot/image.

    Always returns exactly one TableRender per candidate, preserving input order.
    """
    # Index parsed tables by (page_index, bbox) for quick lookup
    parsed_index: dict[tuple[int, tuple[float, float, float, float]], ParsedTable] = {}
    if parsed_tables:
        for p in parsed_tables:
            parsed_index[(p.page_index, p.bbox)] = p

    results: list[TableRender] = []
    for cand in candidates:
        parsed = parsed_index.get((cand.page_index, cand.bbox))
        if parsed is not None and parsed.ok:
            # Use pre-parsed structured HTML
            html_render = parsed_tables_to_renders([parsed])[0]
            results.append(html_render)
            continue

        # Fallback path: try Camelot HTML (if enabled) else rasterize
        renders = table_to_html_or_image(
            pdf_path,
            mod_id,
            assets_dir,
            [cand],
            camelot_enabled=camelot_enabled,
        )
        render = renders[0]
        if render.fallback:
            reason = "camelot_disabled" if not camelot_enabled else "no_html"
            logger.info(
                "tables.fallback image used | page=%s bbox=%s reason=%s",
                cand.page_index,
                cand.bbox,
                reason,
            )
        results.append(render)

    return results
