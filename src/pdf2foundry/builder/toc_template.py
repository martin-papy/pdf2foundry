from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from jinja2 import Environment

if TYPE_CHECKING:  # pragma: no cover - types only
    from pdf2foundry.builder.toc import TocEntryRef


TOC_TEMPLATE = """
<div class="pdf2foundry toc">
  <h1>{{ title }}</h1>
  {% for chapter in chapters %}
  <section class="toc-chapter">
    <h2>{{ chapter.entry_name }}</h2>
    {% if chapter.pages %}
    <ul>
      {% for page in chapter.pages %}
      <li>{{ uuid(page.entry_id, page.page_id, page.label) }}</li>
      {% endfor %}
    </ul>
    {% endif %}
  </section>
  {% endfor %}
</div>
""".strip()


def _default_uuid(entry_id: str, page_id: str, label: str) -> str:
    return f"@UUID[JournalEntry.{entry_id}.JournalEntryPage.{page_id}]{{{label}}}"


def render_toc_html(
    entries: Sequence[TocEntryRef],
    title: str = "Table of Contents",
    *,
    uuid: Callable[[str, str, str], str] | None = None,
) -> str:
    """Render a TOC HTML fragment using a simple Jinja2 template.

    Autoescape is disabled intentionally to preserve @UUID syntax.
    """

    env = Environment(autoescape=False)
    template = env.from_string(TOC_TEMPLATE)
    html: str = template.render(chapters=entries, title=title, uuid=uuid or _default_uuid)
    return html
