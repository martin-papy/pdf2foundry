from __future__ import annotations

from pdf2foundry.builder.manifest import build_module_manifest, validate_module_manifest


def test_build_and_validate_manifest_minimum_fields() -> None:
    manifest = build_module_manifest(
        mod_id="m",
        mod_title="t",
        pack_name="m-journals",
        version="0.1.0",
        author="",
        license_str="",
        depend_compendium_folders=False,
    )
    # Compatibility should be v13 minimum
    assert manifest.get("compatibility", {}).get("minimum") == "13"
    # Packs typed correctly
    packs = manifest.get("packs")
    assert isinstance(packs, list) and packs and packs[0]["type"] == "JournalEntry"
    assert validate_module_manifest(manifest) == []


def test_validate_manifest_detects_missing_and_invalid_fields() -> None:
    manifest: dict[str, object] = {}
    issues = validate_module_manifest(manifest)
    # Missing required keys should be reported
    assert any("Missing required field: id" in s for s in issues)
    assert any("Missing required field: title" in s for s in issues)
    assert any("Missing required field: version" in s for s in issues)
    assert any("Missing required field: compatibility" in s for s in issues)
    assert any("Missing required field: packs" in s for s in issues)
    assert any("Missing required field: styles" in s for s in issues)

    # Invalid types and pack path/name mismatch
    bad = {
        "id": 1,  # wrong type
        "title": "x",
        "version": "0.0.0",
        "compatibility": {"minimum": "12"},  # too low (should be >= 13)
        "packs": [{"type": "Item", "name": "n", "path": "packs/wrong"}],
        "styles": [],
    }
    issues = validate_module_manifest(bad)
    assert any("Field 'id' must be str" in s for s in issues)
    assert any("compatibility.minimum must be '13' or higher" in s for s in issues)
    assert any("first pack must have type 'JournalEntry'" in s for s in issues)

    good = {
        "id": "x",
        "title": "x",
        "version": "0.0.0",
        "compatibility": {"minimum": "13"},
        "packs": [{"type": "JournalEntry", "name": "n", "path": "packs/n"}],
        "styles": ["styles/pdf2foundry.css"],
    }
    assert validate_module_manifest(good) == []
