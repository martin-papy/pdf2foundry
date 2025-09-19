from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class JsonOpts:
    """Options controlling DoclingDocument JSON cache behavior.

    Fields:
    - path: When provided via --docling-json PATH. If exists and is valid, load;
      if missing, convert then save to this path.
    - write: When True (from --write-docling-json), save after conversion when
      no explicit path is provided.
    - fallback_on_json_failure: When True, if JSON loading fails, fall back to
      conversion and (if applicable) overwrite cache.
    - pretty: Pretty-print JSON when writing.
    - default_path: Default destination path computed by CLI when write is True
      and no explicit path is set (typically dist/<mod-id>/sources/docling.json).
    """

    path: Path | None = None
    write: bool = False
    fallback_on_json_failure: bool = False
    pretty: bool = True
    default_path: Path | None = None


__all__ = ["JsonOpts"]
