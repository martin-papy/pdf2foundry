from __future__ import annotations

from pdf2foundry.model.document import OutlineNode


def build_outline_from_headings(doc, page_count: int) -> list[OutlineNode]:  # type: ignore[no-untyped-def]
    """Very simple heading-based outline builder.

    For v1 we implement a conservative fallback:
    - Treat the first page's top-most large title (if any) as a single Chapter
    - Otherwise create a single Chapter spanning the whole document

    This keeps logic minimal until we iterate on richer heuristics in later tasks.
    """

    # Attempt to access a plausible set of per-page blocks
    blocks = getattr(doc, "blocks", None)
    if not blocks:
        # Single chapter fallback
        return [
            OutlineNode(
                title="Document",
                level=1,
                page_start=1,
                page_end=page_count,
                children=[],
                path=["document"],
            )
        ]

    # If blocks exist, try to locate a strong title on the first page
    try:
        first_page_blocks = blocks[0]
    except Exception:
        first_page_blocks = []

    title_text = None
    for b in list(first_page_blocks or []):
        # Heuristic: block with attribute category == "title" or a large font size
        category = getattr(b, "category", None) or getattr(b, "type", None)
        text = getattr(b, "text", None)
        font_size = getattr(b, "font_size", None) or getattr(b, "size", None)
        if (category and str(category).lower() in {"title", "heading"}) and text:
            title_text = str(text).strip()
            break
        if isinstance(font_size, int | float) and font_size >= 16 and text:
            title_text = str(text).strip()
            break

    if not title_text:
        title_text = "Document"

    return [
        OutlineNode(
            title=title_text,
            level=1,
            page_start=1,
            page_end=page_count,
            children=[],
            path=[title_text.lower().replace(" ", "-")],
        )
    ]
