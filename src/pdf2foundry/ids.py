from __future__ import annotations

import hashlib


def compute_deterministic_id(
    mod_id: str,
    chapter_path: str,
    section_path: str | None = None,
) -> str:
    """Compute a deterministic 16-hex id from the provided components.

    _id = sha1(<mod-id>|<chapter-path>|<section-path>)[:16]
    If section_path is None, omit the trailing separator and section.
    """

    parts = [mod_id, chapter_path]
    if section_path is not None:
        parts.append(section_path)
    seed = "|".join(parts)
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return digest[:16]
