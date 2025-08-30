from __future__ import annotations

from pdf2foundry.transform.html_wrap import rewrite_img_srcs, wrap_html


def test_wrap_html_idempotent() -> None:
    raw = "<p>hello</p>"
    wrapped = wrap_html(raw)
    assert wrapped.startswith("<div class='pdf2foundry'>")
    assert wrap_html(wrapped) == wrapped


def test_rewrite_img_srcs() -> None:
    mod = "book-mod"
    html = (
        "<div>"
        '<img src="assets/a.png">'
        "<img src='assets/b.jpg'>"
        '<img src="http://example.com/c.png">'
        '<img src="data:image/png;base64,AAA">'
        f'<img src="modules/{mod}/assets/d.png">'
        "</div>"
    )
    out = rewrite_img_srcs(html, mod)
    assert f'src="modules/{mod}/assets/a.png"' in out
    assert f"src='modules/{mod}/assets/b.jpg'" in out
    assert "http://example.com/c.png" in out
    assert "data:image/png;base64,AAA" in out
    assert f'src="modules/{mod}/assets/d.png"' in out
