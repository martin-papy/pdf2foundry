from __future__ import annotations

import hashlib


def sha1_16_hex(value: str) -> str:
    """Return first 16 lowercase hex chars of SHA1(value).

    This yields a stable 64-bit identifier encoded as 16 hex chars.
    """

    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def make_entry_id(mod_id: str, canonical_path: list[str]) -> str:
    seed = f"{mod_id}|{'/'.join(canonical_path)}|entry"
    return sha1_16_hex(seed)


def make_page_id(mod_id: str, entry_canonical_path: list[str], page_name: str) -> str:
    seed = f"{mod_id}|{'/'.join(entry_canonical_path)}|page|{page_name}"
    return sha1_16_hex(seed)
