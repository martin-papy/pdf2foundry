"""Smoke tests for E2E testing infrastructure."""

import json
from pathlib import Path

import pytest


def test_schema_loads():
    """Test that the module schema loads correctly."""
    schema_path = Path(__file__).parent / "schemas" / "module.schema.json"
    assert schema_path.exists(), f"Schema file not found: {schema_path}"

    with schema_path.open() as f:
        schema = json.load(f)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["title"] == "Foundry VTT v13 Module Schema"
    assert "properties" in schema
    assert "id" in schema["properties"]
    assert "title" in schema["properties"]


def test_fixtures_manifest_loads():
    """Test that the fixtures manifest loads correctly."""
    manifest_path = Path(__file__).parent / "fixtures" / "manifest.json"
    assert manifest_path.exists(), f"Manifest file not found: {manifest_path}"

    with manifest_path.open() as f:
        manifest = json.load(f)

    assert "fixtures" in manifest
    assert "version" in manifest
    assert isinstance(manifest["fixtures"], dict)


def test_utils_package_imports():
    """Test that utils package imports work correctly."""
    # Test that the package structure is correct
    utils_path = Path(__file__).parent / "utils"
    assert utils_path.exists()
    assert (utils_path / "__init__.py").exists()

    # Test that we can import the utils package (relative import)
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    try:
        import utils

        assert utils is not None
    finally:
        sys.path.pop(0)


@pytest.mark.slow
def test_readme_exists():
    """Test that README documentation exists."""
    readme_path = Path(__file__).parent / "README.md"
    assert readme_path.exists(), f"README not found: {readme_path}"

    content = readme_path.read_text()
    assert "End-to-End Testing for PDF2Foundry" in content
    assert "Test Markers" in content
    assert "Environment Variables" in content
