from __future__ import annotations

from pdf2foundry.transform.clean_html import (
    clean_html_fragment,
    normalize_whitespace,
    remove_zero_width,
)


def test_remove_zero_width() -> None:
    s = "A\u200b B\ufeff C"
    assert remove_zero_width(s) == "A B C"


def test_normalize_whitespace() -> None:
    s = "a   b\n\n\n c\t\t d\u00a0e"
    out = normalize_whitespace(s)
    assert out == "a b\n\n c d e"


def test_clean_html_fragment() -> None:
    s = (
        "<!DOCTYPE html><html><head><style>body{}</style></head><body>"
        "A&amp;B\u200b   C\u00ad\ufffd L' Appel d' Art fi che fl ammes "
        "D a\u006es T aille 1\u20442</body></html>"
    )
    out = clean_html_fragment(s)
    assert out == "A&B C L'Appel d'Art fiche flammes Dans Taille 1/2"
