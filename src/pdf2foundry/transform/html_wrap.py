from __future__ import annotations

import re

_WRAP_RE = re.compile(
    r"^\s*<div[^>]*\bclass\s*=\s*(['\"])"  # class attribute start (single or double quote)
    r"[^'\"]*\bpdf2foundry\b[^'\"]*\1[^>]*>",
    re.IGNORECASE,
)


def wrap_html(content: str) -> str:
    """Ensure content is wrapped in a single div.pdf2foundry.

    Idempotent: if already wrapped at the root, returns content unchanged.
    """

    if _WRAP_RE.search(content or ""):
        return content
    return f"<div class='pdf2foundry'>{content}</div>"


def rewrite_img_srcs(html: str, mod_id: str) -> str:
    """Rewrite <img src="assets/..."> to module-relative path.

    - assets/foo.png -> modules/<mod-id>/assets/foo.png
    - Leave data:, http(s):, and modules/<...>/assets paths unchanged
    - Handle single/double quotes; avoid double-prefixing
    """

    def _repl(m: re.Match[str]) -> str:
        quote = m.group("q")
        src = m.group("src")
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        if src.startswith("modules/"):
            return m.group(0)
        if src.startswith("assets/"):
            return f"src={quote}modules/{mod_id}/{src}{quote}"
        return m.group(0)

    pattern = re.compile(r"<img\s+[^>]*src=(?P<q>['\"])\s*(?P<src>[^'\"]+)\1", re.IGNORECASE)
    return pattern.sub(_repl, html)
