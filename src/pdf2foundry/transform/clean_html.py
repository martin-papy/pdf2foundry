from __future__ import annotations

import html
import re

_SPACE_TRANSLATION = {
    0x00A0: " ",  # NO-BREAK SPACE
    0x2007: " ",  # FIGURE SPACE
    0x2008: " ",  # PUNCTUATION SPACE
    0x2009: " ",  # THIN SPACE
    0x200A: " ",  # HAIR SPACE
    0x2002: " ",  # EN SPACE
    0x2003: " ",  # EM SPACE
    0x2004: " ",  # THREE-PER-EM SPACE
    0x2005: " ",  # FOUR-PER-EM SPACE
    0x2006: " ",  # SIX-PER-EM SPACE
    0x202F: " ",  # NARROW NO-BREAK SPACE
    0x205F: " ",  # MEDIUM MATHEMATICAL SPACE
}


def _replace_special_spaces(text: str) -> str:
    return text.translate(_SPACE_TRANSLATION)


def _remove_soft_hyphen(text: str) -> str:
    # SOFT HYPHEN often appears from PDF extraction and should vanish
    return text.replace("\u00ad", "")


def _remove_replacement_char(text: str) -> str:
    # U+FFFD replacement character indicates decode errors - drop it
    return text.replace("\ufffd", "")


def _fix_apostrophe_spacing(text: str) -> str:
    # Collapse spaces after straight or curly apostrophes: L' Appel -> L'Appel, d' Art -> d'Art
    text = re.sub(r"([\u2019'])\s+([A-Za-zÀ-ÖØ-öø-ÿ])", r"\1\2", text)
    # Collapse spaces before apostrophes: L 'Appel -> L'Appel
    text = re.sub(r"([A-Za-zÀ-ÖØ-öø-ÿ])\s+([\u2019'])", r"\1\2", text)
    return text


def _fix_ligature_splits(text: str) -> str:
    # Address common ligature-induced splits: "fi che" -> "fiche", "fl ammes" -> "flammes",
    # and words like "diff érentes" -> "différentes"
    # Apply a few passes to catch chained cases.
    for _ in range(2):
        text = re.sub(
            r"\b(fi|fl|ff|ffi|ffl)\s+([A-Za-zÀ-ÖØ-öø-ÿ])",
            r"\1\2",
            text,
        )
        # Also handle splits like "diff érentes" where the split happens after double letters
        text = re.sub(r"(ff)\s+([A-Za-zÀ-ÖØ-öø-ÿ])", r"\1\2", text)
    return text


def _join_split_single_letter_word(text: str) -> str:
    # Join patterns like "A vant" -> "Avant", "T aille" -> "Taille"
    return re.sub(r"\b([A-ZÀ-Ö])\s+([a-zà-öø-ÿ]{2,})\b", r"\1\2", text)


def _normalize_fraction_slash(text: str) -> str:
    # Replace fraction slash with regular slash to avoid mojibake combinations
    return text.replace("\u2044", "/")


def _strip_heading_wrappers(html_text: str) -> str:
    # Remove stray heading wrappers like: <h2>w Title x</h2> -> <h2>Title</h2>
    def _repl(m: re.Match[str]) -> str:
        start, inner, end = m.group(1), m.group(2), m.group(3)
        cleaned = re.sub(r"^\s*[wx]\s+", "", inner, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+[wx]\s*$", "", cleaned, flags=re.IGNORECASE)
        return f"{start}{cleaned}{end}"

    return re.sub(r"(<h[1-6][^>]*>)([\s\S]*?)(</h[1-6]>)", _repl, html_text, flags=re.IGNORECASE)


def _remove_stray_bullet_i(html_text: str) -> str:
    # Remove list items that are just a stray 'i' artifact from extraction
    return re.sub(r"<li>\s*[iI]\s*</li>", "", html_text)


def _strip_leading_bullet_i_marker(html_text: str) -> str:
    # Strip a leading 'i ' marker inside list items: <li> i Text -> <li>Text
    return re.sub(r"(<li(?:\s+[^>]*)?>)\s*[iI]\s+(?=[^<])", r"\1", html_text)


def _normalize_hyphens(text: str) -> str:
    # Replace non-breaking hyphen with regular hyphen, and normalize minus sign
    return text.replace("\u2011", "-").replace("\u2212", "-")


def _extract_body_inner(html_text: str) -> str:
    # Prefer content inside body when present
    m = re.search(r"<body[^>]*>([\s\S]*?)</body>", html_text, flags=re.IGNORECASE)
    return m.group(1) if m else html_text


def _strip_doclevel_scaffold(html_text: str) -> str:
    # Remove DOCTYPE, html, and head sections if present
    t = re.sub(r"<!DOCTYPE[^>]*>\s*", "", html_text, flags=re.IGNORECASE)
    t = re.sub(r"<head[^>]*>[\s\S]*?</head>\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"</?html[^>]*>\s*", "", t, flags=re.IGNORECASE)
    # Also remove stray style blocks anywhere to avoid heavy inline styling
    t = re.sub(r"<style[^>]*>[\s\S]*?</style>\s*", "", t, flags=re.IGNORECASE)
    return t


def normalize_whitespace(text: str) -> str:
    # Replace tabs with spaces
    t = text.replace("\t", " ")
    # Normalize special Unicode space separators to regular space first
    t = _replace_special_spaces(t)
    # Collapse runs of spaces (not crossing newlines)
    t = re.sub(r" {2,}", " ", t)
    # Collapse 3+ newlines to exactly 2 to preserve paragraph breaks
    t = re.sub(r"\n{3,}", "\n\n", t)
    # Trim trailing spaces at end of lines
    t = re.sub(r"[ ]+\n", "\n", t)
    return t.strip()


def remove_zero_width(text: str) -> str:
    # Remove zero-width spaces and other non-printing chars commonly seen in PDFs
    # Covers: ZERO WIDTH SPACE, ZERO WIDTH NO-BREAK SPACE, ZERO WIDTH JOINER, etc.
    return re.sub(r"[\u200B\u200C\u200D\uFEFF]", "", text)


def clean_html_fragment(html_in: str) -> str:
    # Decode HTML entities
    s = html.unescape(html_in)
    # Strip encoding artifacts
    s = _remove_soft_hyphen(s)
    s = _remove_replacement_char(s)
    s = remove_zero_width(s)
    s = _normalize_fraction_slash(s)
    s = _normalize_hyphens(s)
    # Reduce document-level wrappers to body inner
    s = _extract_body_inner(s)
    s = _strip_doclevel_scaffold(s)
    # Fix common spacing issues
    s = _fix_apostrophe_spacing(s)
    s = _fix_ligature_splits(s)
    s = _join_split_single_letter_word(s)
    # Structural cleanups that are safe via regex
    s = _strip_heading_wrappers(s)
    s = _remove_stray_bullet_i(s)
    s = _strip_leading_bullet_i_marker(s)
    # Normalize whitespace last
    s = normalize_whitespace(s)
    return s
