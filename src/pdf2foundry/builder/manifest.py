from __future__ import annotations

from typing import Any


def build_module_manifest(
    *,
    mod_id: str,
    mod_title: str,
    pack_name: str,
    version: str,
    author: str = "",
    license_str: str = "",
    depend_compendium_folders: bool = True,
    description: str | None = None,
) -> dict[str, Any]:
    """Build module.json manifest dictionary.

    Produces a minimal, v13-compliant manifest with optional author and license.
    """

    manifest: dict[str, Any] = {
        "id": mod_id,
        "title": mod_title,
        "description": description or "Imported Journals generated from a PDF using PDF2Foundry.",
        "version": version,
        # Target v13; leave verified unset to avoid premature pinning
        "compatibility": {"minimum": "13"},
        "authors": ([{"name": author}] if author else []),
        "packs": [
            {
                "name": pack_name,
                "label": f"{mod_title} Journals",
                "path": f"packs/{pack_name}",
                "type": "JournalEntry",
            }
        ],
        "styles": ["styles/pdf2foundry.css"],
    }
    if license_str:
        manifest["license"] = license_str
    # Foundry v13 provides native compendium folders; do not declare dependency
    return manifest


def validate_module_manifest(manifest: dict[str, Any]) -> list[str]:
    """Lightweight validation for module.json content.

    Returns a list of human-readable error strings; empty list means OK.
    """

    issues: list[str] = []

    def _require(key: str, typ: type) -> None:
        if key not in manifest:
            issues.append(f"Missing required field: {key}")
            return
        if not isinstance(manifest[key], typ):
            issues.append(f"Field '{key}' must be {typ.__name__}")

    _require("id", str)
    _require("title", str)
    _require("version", str)
    _require("compatibility", dict)
    _require("packs", list)
    _require("styles", list)

    comp = manifest.get("compatibility", {})
    if isinstance(comp, dict) and str(comp.get("minimum", "")) < "13":
        issues.append("compatibility.minimum must be '13' or higher")

    packs = manifest.get("packs", [])
    if isinstance(packs, list):
        if not packs:
            issues.append("packs must contain at least one entry")
        else:
            p0 = packs[0]
            if not isinstance(p0, dict) or p0.get("type") != "JournalEntry":
                issues.append("first pack must have type 'JournalEntry'")
            path = p0.get("path")
            name = p0.get("name")
            if isinstance(path, str) and isinstance(name, str) and not path.endswith(name):
                issues.append("pack path should end with its name (packs/<name>)")

    return issues
