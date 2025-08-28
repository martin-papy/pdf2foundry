from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined


@dataclass(frozen=True)
class Templates:
    env: Environment

    def render_entry(self, context: dict[str, Any]) -> str:
        tpl = self.env.get_template("entry.html")
        return str(tpl.render(**context))

    def render_page(self, context: dict[str, Any]) -> str:
        tpl = self.env.get_template("page.html")
        return str(tpl.render(**context))


def create_environment(templates_dir: Path) -> Templates:
    loader = FileSystemLoader(str(templates_dir))
    env = Environment(loader=loader, undefined=StrictUndefined, autoescape=True)
    return Templates(env=env)


def write_default_templates(target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "entry.html").write_text(
        """
<!doctype html>
<html>
  <body>
    <div class="pdf2foundry">
      <h1>{{ title }}</h1>
      {% if description %}<p class="description">{{ description }}</p>{% endif %}
      {% block content %}{% endblock %}
    </div>
  </body>
</html>
""".strip()
    )
    (target_dir / "page.html").write_text(
        """
{% extends "entry.html" %}
{% block content %}
  {{ body|safe }}
{% endblock %}
""".strip()
    )
