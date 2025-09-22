from __future__ import annotations

import re


def _slugify(text: str) -> str:
    import re as _re

    s = _re.sub(r"[^A-Za-z0-9]+", "-", (text or "").lower()).strip("-")
    s = _re.sub(r"-+", "-", s)
    return s or "untitled"


def build_anchor_lookup(pages: list[tuple[str, str]]) -> dict[str, str]:
    """Build mapping from anchor token -> pageId.

    pages: list of (page_name, page_id)
    Tokens include slug(page_name) and page_name lower() without spaces.
    """

    mapping: dict[str, str] = {}
    for name, pid in pages:
        slug = _slugify(name)
        mapping.setdefault(slug, pid)
        mapping.setdefault((name or "").lower().replace(" ", "-"), pid)
    return mapping


def rewrite_internal_anchors_to_uuid(html: str, entry_id: str, token_to_pageid: dict[str, str]) -> str:
    """Replace <a href="#token">label</a> with @UUID link notation.

    Only transforms anchors with href starting with "#" and resolvable tokens.
    Leaves other anchors unchanged.
    """

    def _repl(m: re.Match[str]) -> str:
        href = m.group("href")
        label = m.group("label")
        if not href.startswith("#"):
            return m.group(0)
        token = href[1:]
        page_id = token_to_pageid.get(_slugify(token)) or token_to_pageid.get(token.lower())
        if not page_id:
            return label  # drop unresolved link, keep label
        uuid = f"@UUID[JournalEntry.{entry_id}.JournalEntryPage.{page_id}]{{{label}}}"
        return uuid

    pattern = re.compile(
        r"<a\s+[^>]*href\s*=\s*['\"](?P<href>[^'\"]+)['\"][^>]*>(?P<label>[\s\S]*?)</a>",
        re.IGNORECASE,
    )
    return pattern.sub(_repl, html)
