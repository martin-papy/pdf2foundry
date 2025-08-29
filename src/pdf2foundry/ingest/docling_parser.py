from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pdf2foundry.model.document import OutlineNode, ParsedDocument

ProgressCallback = Callable[[str, dict[str, int | str]], None] | None


def _safe_emit(on_progress: ProgressCallback, event: str, payload: dict[str, int | str]) -> None:
    if on_progress is None:
        return
    from contextlib import suppress

    # Never let UI callbacks break parsing
    with suppress(Exception):
        on_progress(event, payload)


def _slugify(text: str) -> str:
    import re

    # Simple slug: lowercase, replace non-alphanum with hyphens, collapse repeats
    s = re.sub(r"[^A-Za-z0-9]+", "-", text.lower()).strip("-")
    s = re.sub(r"-+", "-", s)
    return s or "untitled"


def _compute_path_chain(ancestors: list[OutlineNode], title: str) -> list[str]:
    return [*([seg for a in ancestors for seg in a.path[:1]]), _slugify(title)]


def _count_chapters_sections(nodes: list[OutlineNode]) -> tuple[int, int]:
    chapters = sum(1 for n in nodes if n.level == 1)
    sections = 0
    stack: list[OutlineNode] = nodes[:]
    while stack:
        n = stack.pop()
        if n.level >= 2:
            sections += 1
        stack.extend(n.children)
    return chapters, sections


def parse_pdf_structure(pdf: Path, on_progress: ProgressCallback = None) -> ParsedDocument:
    """Parse a born-digital PDF and return its logical outline.

    Strategy:
    - Try Docling bookmarks/outline first and normalize to OutlineNode tree
    - If empty/missing, fallback to heuristics (heading detection)
    - Emit progress events at key boundaries for CLI rendering
    """

    # Import lazily to avoid hard dependency at import time
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipe_opts = PdfPipelineOptions(
        do_ocr=False, generate_picture_images=False, generate_page_images=False
    )
    conv = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipe_opts)}
    )
    doc = conv.convert(str(pdf)).document

    # Determine page count (Docling API varies across versions)
    # num_pages may be untyped depending on docling version; guard with getattr
    try:
        num_pages_fn = getattr(doc, "num_pages", None)
        if callable(num_pages_fn):
            page_count = int(num_pages_fn())
        else:
            page_count = int(getattr(doc, "num_pages", 0) or 0)
    except Exception:
        page_count = int(getattr(doc, "num_pages", 0) or 0)

    _safe_emit(on_progress, "load_pdf", {"pdf": str(pdf), "page_count": page_count})

    _safe_emit(on_progress, "extract_bookmarks:start", {"page_count": page_count})

    outline_nodes: list[OutlineNode] = _outline_from_docling(doc, page_count)

    if outline_nodes:
        chapters, sections = _count_chapters_sections(outline_nodes)
        _safe_emit(
            on_progress,
            "extract_bookmarks:success",
            {"page_count": page_count, "chapters": chapters, "sections": sections},
        )
    else:
        _safe_emit(on_progress, "extract_bookmarks:empty", {"page_count": page_count})
        _safe_emit(on_progress, "heuristics:start", {"page_count": page_count})
        from pdf2foundry.ingest.heuristics import build_outline_from_headings

        outline_nodes = build_outline_from_headings(doc, page_count)
        chapters, sections = _count_chapters_sections(outline_nodes)
        _safe_emit(
            on_progress,
            "heuristics:detected",
            {"page_count": page_count, "chapters": chapters, "sections": sections},
        )

    _safe_emit(
        on_progress, "outline:finalized", {"page_count": page_count, "nodes": chapters + sections}
    )

    return ParsedDocument(page_count=page_count, outline=outline_nodes)


def _outline_from_docling(doc, page_count: int) -> list[OutlineNode]:  # type: ignore[no-untyped-def]
    """Attempt to extract outline/bookmarks from Docling document and normalize.

    This function intentionally stays liberal with Docling types because the API
    may vary by version; we access attributes defensively.
    """

    # Try a few commonly used attributes that may contain outline/bookmark info
    candidates = [
        getattr(doc, "outline", None),
        getattr(doc, "toc", None),
        getattr(doc, "bookmarks", None),
    ]

    outline_like = next((c for c in candidates if c), None)
    if not outline_like:
        return []

    # Expect a list of nodes with at least (title, page number, children)
    root_nodes: list[OutlineNode] = []

    def normalize(node_like, ancestors: list[OutlineNode]) -> OutlineNode | None:  # type: ignore[no-untyped-def]
        title = (
            getattr(node_like, "title", None) or getattr(node_like, "name", None) or str(node_like)
        )
        # Commonly, docling stores page numbers as 1-based
        page = getattr(node_like, "page", None) or getattr(node_like, "page_no", None) or 1
        try:
            page_start = max(1, int(page))
        except Exception:
            page_start = 1

        level = len(ancestors) + 1
        node = OutlineNode(
            title=title,
            level=level,
            page_start=page_start,
            page_end=None,
            children=[],
            path=_compute_path_chain(ancestors, title),
        )

        children_like = (
            getattr(node_like, "children", None) or getattr(node_like, "items", None) or []
        )
        for child_like in list(children_like or []):
            child = normalize(child_like, [*ancestors, node])
            if child is not None:
                node.children.append(child)

        return node

    for item in list(outline_like or []):
        norm = normalize(item, [])
        if norm is not None:
            root_nodes.append(norm)

    # Compute page_end for each node by looking ahead in a depth-first sequence
    def assign_page_ends(nodes: list[OutlineNode], parent_end: int | None) -> None:
        flat: list[OutlineNode] = []

        def dfs(n: OutlineNode) -> None:
            flat.append(n)
            for c in n.children:
                dfs(c)

        for n in nodes:
            dfs(n)

        for i, n in enumerate(flat):
            # Next node that is at the same or higher level determines the end
            end: int | None = parent_end
            for j in range(i + 1, len(flat)):
                m = flat[j]
                if m.level <= n.level:
                    end = max(1, m.page_start - 1)
                    break
            # Cap by page_count
            if end is not None:
                n.page_end = min(page_count, end)
            else:
                # Last span extends to document end
                n.page_end = page_count

    assign_page_ends(root_nodes, parent_end=None)
    return root_nodes
