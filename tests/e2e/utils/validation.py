"""Validation utilities for E2E tests."""

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator
from PIL import Image


def load_schema(name: str) -> dict[str, Any]:
    """
    Load a JSON schema by name.

    Args:
        name: Schema name (without .schema.json extension)

    Returns:
        Dictionary containing the JSON schema

    Raises:
        FileNotFoundError: If schema file doesn't exist
        json.JSONDecodeError: If schema is invalid JSON
    """
    schema_path = Path(__file__).parent.parent / "schemas" / f"{name}.schema.json"

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")

    with schema_path.open() as f:
        return json.load(f)


def validate_module_json(path: Path) -> list[str]:
    """
    Validate a Foundry module.json file against the schema.

    Args:
        path: Path to the module.json file

    Returns:
        List of validation error messages (empty if valid)
    """
    if not path.exists():
        return [f"Module file not found: {path}"]

    try:
        # Load the module.json file
        with path.open() as f:
            module_data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON in module file: {e}"]

    try:
        # Load and validate against schema
        schema = load_schema("module")
        validator = Draft202012Validator(schema)

        errors = []
        for error in validator.iter_errors(module_data):
            # Format error message with path
            path_str = " -> ".join(str(p) for p in error.absolute_path)
            if path_str:
                errors.append(f"At {path_str}: {error.message}")
            else:
                errors.append(error.message)

        return errors

    except Exception as e:
        return [f"Schema validation error: {e}"]


def validate_compendium_structure(module_dir: Path) -> list[str]:
    """
    Validate the structure of a Foundry module directory.

    Args:
        module_dir: Path to the module directory

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    if not module_dir.exists():
        return [f"Module directory not found: {module_dir}"]

    if not module_dir.is_dir():
        return [f"Module path is not a directory: {module_dir}"]

    # Check for required module.json
    module_json_path = module_dir / "module.json"
    if not module_json_path.exists():
        errors.append("Missing required module.json file")
    else:
        # Validate module.json structure
        module_errors = validate_module_json(module_json_path)
        errors.extend(module_errors)

        # If module.json is valid, check pack structure
        if not module_errors:
            try:
                with module_json_path.open() as f:
                    module_data = json.load(f)

                # Check pack directories
                for pack in module_data.get("packs", []):
                    pack_path = module_dir / pack.get("path", "")
                    if not pack_path.exists():
                        errors.append(f"Pack directory not found: {pack_path}")
                    elif not pack_path.is_dir():
                        errors.append(f"Pack path is not a directory: {pack_path}")

            except Exception as e:
                errors.append(f"Error reading module.json: {e}")

    # Check for sources directory (common for PDF2Foundry modules)
    sources_dir = module_dir / "sources"
    if sources_dir.exists():
        if not sources_dir.is_dir():
            errors.append(f"Sources path is not a directory: {sources_dir}")
        else:
            # Check for journals subdirectory
            journals_dir = sources_dir / "journals"
            if journals_dir.exists() and not journals_dir.is_dir():
                errors.append(f"Journals path is not a directory: {journals_dir}")

    # Check for assets directory
    assets_dir = module_dir / "assets"
    if assets_dir.exists() and not assets_dir.is_dir():
        errors.append(f"Assets path is not a directory: {assets_dir}")

    # Check for styles directory
    styles_dir = module_dir / "styles"
    if styles_dir.exists() and not styles_dir.is_dir():
        errors.append(f"Styles path is not a directory: {styles_dir}")

    return errors


def validate_assets(module_dir: Path) -> list[str]:
    """
    Validate that all referenced assets exist and are accessible.

    Args:
        module_dir: Path to the module directory

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    if not module_dir.exists():
        return [f"Module directory not found: {module_dir}"]

    # Find all HTML files in sources
    sources_dir = module_dir / "sources"
    html_files = []

    if sources_dir.exists():
        html_files.extend(sources_dir.rglob("*.html"))

        # Also check JSON files for HTML content
        for json_file in sources_dir.rglob("*.json"):
            try:
                with json_file.open() as f:
                    data = json.load(f)

                # Extract HTML content from journal entries/pages
                html_content = _extract_html_from_json(data)
                if html_content:
                    # Create a temporary file-like object for processing
                    html_files.append((json_file, html_content))

            except Exception as e:
                errors.append(f"Error reading JSON file {json_file}: {e}")

    # Check assets referenced in HTML
    for html_source in html_files:
        if isinstance(html_source, tuple):
            # JSON-embedded HTML
            json_file, html_content = html_source
            try:
                soup = BeautifulSoup(html_content, "html.parser")
                asset_errors = _check_html_assets(soup, module_dir, f"JSON file {json_file}")
                errors.extend(asset_errors)
            except Exception as e:
                errors.append(f"Error parsing HTML from {json_file}: {e}")
        else:
            # Regular HTML file
            try:
                with html_source.open() as f:
                    soup = BeautifulSoup(f, "html.parser")

                asset_errors = _check_html_assets(soup, module_dir, str(html_source))
                errors.extend(asset_errors)

            except Exception as e:
                errors.append(f"Error reading HTML file {html_source}: {e}")

    return errors


def _extract_html_from_json(data: Any) -> str:
    """Extract HTML content from JSON data structures."""
    html_content = ""

    if isinstance(data, dict):
        # Check for text content in journal pages
        if "text" in data and isinstance(data["text"], dict):
            content = data["text"].get("content", "")
            if content:
                html_content += content + "\\n"

        # Recursively check nested structures
        for value in data.values():
            html_content += _extract_html_from_json(value)

    elif isinstance(data, list):
        for item in data:
            html_content += _extract_html_from_json(item)

    return html_content


def _check_html_assets(soup: BeautifulSoup, module_dir: Path, source_name: str) -> list[str]:
    """Check that assets referenced in HTML exist."""
    errors = []

    # Check images
    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            asset_path = _resolve_asset_path(src, module_dir)
            if asset_path and not asset_path.exists():
                errors.append(f"Missing image asset in {source_name}: {src}")
            elif asset_path:
                # Verify it's a valid image
                try:
                    with Image.open(asset_path) as image:
                        image.verify()
                except Exception:
                    errors.append(f"Invalid image file in {source_name}: {src}")

    # Check links to other assets
    for link in soup.find_all("a"):
        href = link.get("href")
        if href and not _is_external_url(href) and not href.startswith("#"):
            asset_path = _resolve_asset_path(href, module_dir)
            if asset_path and not asset_path.exists():
                errors.append(f"Missing linked asset in {source_name}: {href}")

    return errors


def _resolve_asset_path(asset_ref: str, module_dir: Path) -> Path | None:
    """Resolve an asset reference to a file path."""
    if _is_external_url(asset_ref):
        return None

    # Remove leading slash if present
    if asset_ref.startswith("/"):
        asset_ref = asset_ref[1:]

    # Resolve relative to module directory
    return module_dir / asset_ref


def _is_external_url(url: str) -> bool:
    """Check if a URL is external (has a scheme)."""
    parsed = urlparse(url)
    return bool(parsed.scheme)


def check_toc_links(module_dir: Path) -> list[str]:
    """
    Check that Table of Contents links resolve correctly.

    Args:
        module_dir: Path to the module directory

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    if not module_dir.exists():
        return [f"Module directory not found: {module_dir}"]

    # Look for TOC files or embedded TOC content
    sources_dir = module_dir / "sources"
    if not sources_dir.exists():
        return []  # No sources to check

    # Check JSON files for TOC content and UUID references
    for json_file in sources_dir.rglob("*.json"):
        try:
            with json_file.open() as f:
                data = json.load(f)

            # Extract and validate UUID references
            uuid_errors = _check_uuid_references(data, module_dir, str(json_file))
            errors.extend(uuid_errors)

        except Exception as e:
            errors.append(f"Error reading JSON file {json_file}: {e}")

    return errors


def _check_uuid_references(data: Any, module_dir: Path, source_name: str) -> list[str]:
    """Check UUID references in JSON data."""
    errors = []

    if isinstance(data, dict):
        for _key, value in data.items():
            if isinstance(value, str) and "@UUID[" in value:
                # Extract UUID references
                import re

                uuid_pattern = r"@UUID\\[([^\\]]+)\\]"
                matches = re.findall(uuid_pattern, value)

                for match in matches:
                    # Basic validation - check format
                    if not _is_valid_uuid_reference(match):
                        errors.append(f"Invalid UUID reference format in {source_name}: {match}")

            # Recursively check nested structures
            errors.extend(_check_uuid_references(value, module_dir, source_name))

    elif isinstance(data, list):
        for item in data:
            errors.extend(_check_uuid_references(item, module_dir, source_name))

    return errors


def _is_valid_uuid_reference(uuid_ref: str) -> bool:
    """Validate UUID reference format."""
    # Basic format check for Foundry UUID references
    # Should be like: JournalEntry.abcdef1234567890.JournalEntryPage.1234567890abcdef
    parts = uuid_ref.split(".")

    if len(parts) < 2:
        return False

    # Check that IDs are hexadecimal and proper length
    for i in range(1, len(parts), 2):
        if i < len(parts):
            id_part = parts[i]
            if len(id_part) != 16 or not all(c in "0123456789abcdef" for c in id_part):
                return False

    return True


def validate_json_structure(json_path: Path, expected_keys: list[str]) -> list[str]:
    """
    Validate that a JSON file contains expected keys.

    Args:
        json_path: Path to the JSON file
        expected_keys: List of required keys

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    if not json_path.exists():
        return [f"JSON file not found: {json_path}"]

    try:
        with json_path.open() as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return [f"JSON file is not an object: {json_path}"]

        for key in expected_keys:
            if key not in data:
                errors.append(f"Missing required key '{key}' in {json_path}")

    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON in {json_path}: {e}")
    except Exception as e:
        errors.append(f"Error reading {json_path}: {e}")

    return errors
