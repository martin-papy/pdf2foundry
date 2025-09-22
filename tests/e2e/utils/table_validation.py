"""Table validation utilities for E2E tests."""

import json
from pathlib import Path
from typing import Any

import pytest


def analyze_table_representations(module_dir: Path, mode: str) -> dict[str, Any]:
    """
    Analyze table representations in the generated module.

    Args:
        module_dir: Path to the generated module directory
        mode: Table processing mode for context

    Returns:
        Dictionary with table analysis results

    Raises:
        pytest.fail: If analysis fails
    """
    analysis = {
        "structured_count": 0,
        "image_count": 0,
        "structured_tables": [],
        "image_tables": [],
        "pages_with_tables": set(),
        "mode": mode,
    }

    # Analyze sources directory for structured tables
    sources_dir = module_dir / "sources"
    if sources_dir.exists():
        analysis.update(analyze_structured_tables(sources_dir))

    # Analyze assets directory for image tables
    assets_dir = module_dir / "assets"
    if assets_dir.exists():
        analysis.update(analyze_image_tables(assets_dir))

    return analysis


def analyze_structured_tables(sources_dir: Path) -> dict[str, Any]:
    """
    Analyze structured table representations in sources.

    Args:
        sources_dir: Path to the sources directory

    Returns:
        Dictionary with structured table analysis
    """
    structured_count = 0
    structured_tables = []
    pages_with_structured = set()

    # Check JSON files for structured table content
    for json_file in sources_dir.rglob("*.json"):
        try:
            with json_file.open() as f:
                data = json.load(f)

            # Extract table information from journal entries/pages
            tables_found = extract_structured_tables_from_json(data, str(json_file))
            structured_count += len(tables_found)
            structured_tables.extend(tables_found)

            if tables_found:
                pages_with_structured.add(str(json_file.relative_to(sources_dir)))

        except Exception as e:
            pytest.fail(f"Error analyzing JSON file {json_file}: {e}")

    # Check HTML files for table elements
    for html_file in sources_dir.rglob("*.html"):
        try:
            with html_file.open() as f:
                html_content = f.read()

            tables_found = extract_structured_tables_from_html(html_content, str(html_file))
            structured_count += len(tables_found)
            structured_tables.extend(tables_found)

            if tables_found:
                pages_with_structured.add(str(html_file.relative_to(sources_dir)))

        except Exception as e:
            pytest.fail(f"Error analyzing HTML file {html_file}: {e}")

    return {
        "structured_count": structured_count,
        "structured_tables": structured_tables,
        "pages_with_structured": pages_with_structured,
    }


def analyze_image_tables(assets_dir: Path) -> dict[str, Any]:
    """
    Analyze image table representations in assets.

    Args:
        assets_dir: Path to the assets directory

    Returns:
        Dictionary with image table analysis
    """
    image_count = 0
    image_tables = []
    pages_with_images = set()

    # Look for table-related images
    image_extensions = {".png", ".jpg", ".jpeg", ".webp"}
    for image_file in assets_dir.rglob("*"):
        if image_file.is_file() and image_file.suffix.lower() in image_extensions and is_table_image(image_file):
            image_count += 1
            image_tables.append(
                {
                    "path": image_file,
                    "rel_path": image_file.relative_to(assets_dir),
                    "size_bytes": image_file.stat().st_size,
                }
            )
            pages_with_images.add(str(image_file.parent.relative_to(assets_dir)))

    return {
        "image_count": image_count,
        "image_tables": image_tables,
        "pages_with_images": pages_with_images,
    }


def extract_structured_tables_from_json(data: Any, source_name: str) -> list[dict[str, Any]]:
    """Extract structured table information from JSON data."""
    tables = []

    if isinstance(data, dict):
        # Check for table-specific content in text fields
        if "text" in data and isinstance(data["text"], dict):
            content = data["text"].get("content", "")
            if content and "<table" in content.lower():
                # Parse HTML content for table details
                table_info = parse_html_tables(content, source_name)
                tables.extend(table_info)

        # Check for explicit table entries (if the format supports them)
        if data.get("type") == "table" and "rows" in data and "columns" in data:
            tables.append(
                {
                    "source": source_name,
                    "type": "json_table",
                    "rows": len(data.get("rows", [])),
                    "columns": len(data.get("columns", [])),
                }
            )

        # Recursively check nested structures
        for value in data.values():
            tables.extend(extract_structured_tables_from_json(value, source_name))

    elif isinstance(data, list):
        for item in data:
            tables.extend(extract_structured_tables_from_json(item, source_name))

    return tables


def extract_structured_tables_from_html(html_content: str, source_name: str) -> list[dict[str, Any]]:
    """Extract structured table information from HTML content."""
    return parse_html_tables(html_content, source_name)


def parse_html_tables(html_content: str, source_name: str) -> list[dict[str, Any]]:
    """Parse HTML content for table elements and extract metadata."""
    tables = []

    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")
        table_elements = soup.find_all("table")

        for i, table in enumerate(table_elements):
            rows = table.find_all("tr")
            row_count = len(rows)

            # Count columns from the first row
            col_count = 0
            if rows:
                first_row = rows[0]
                col_count = len(first_row.find_all(["td", "th"]))

            tables.append(
                {
                    "source": source_name,
                    "type": "html_table",
                    "index": i,
                    "rows": row_count,
                    "columns": col_count,
                }
            )

    except ImportError:
        # Fallback: simple regex-based detection
        import re

        table_matches = re.findall(r"<table[^>]*>.*?</table>", html_content, re.DOTALL | re.IGNORECASE)
        for i, match in enumerate(table_matches):
            # Basic row counting
            row_count = len(re.findall(r"<tr[^>]*>", match, re.IGNORECASE))
            tables.append(
                {
                    "source": source_name,
                    "type": "html_table_regex",
                    "index": i,
                    "rows": row_count,
                    "columns": 0,  # Cannot reliably count columns with regex
                }
            )

    return tables


def is_table_image(image_path: Path) -> bool:
    """
    Determine if an image file appears to be a table representation.

    Args:
        image_path: Path to the image file

    Returns:
        True if the image appears to be a table
    """
    # Check filename for table-related keywords
    filename_lower = image_path.name.lower()
    table_keywords = ["table", "chart", "data", "grid"]

    return any(keyword in filename_lower for keyword in table_keywords)


def assert_mode_specific_requirements(table_analysis: dict[str, Any], mode: str) -> None:
    """
    Assert mode-specific table processing requirements.

    Args:
        table_analysis: Table analysis results
        mode: Table processing mode

    Raises:
        pytest.fail: If mode-specific requirements are not met
    """
    structured_count = table_analysis["structured_count"]
    image_count = table_analysis["image_count"]

    if mode == "structured":
        # Structured mode: should have structured tables, no image tables
        if structured_count == 0:
            pytest.fail(f"Structured mode should produce structured tables, but found {structured_count}")

        if image_count > 0:
            pytest.fail(f"Structured mode should not produce image tables, but found {image_count}")

        # Validate that structured tables have proper dimensions
        for table in table_analysis["structured_tables"]:
            if table["rows"] <= 0:
                pytest.fail(f"Structured table has invalid row count: {table}")
            if table.get("columns", 0) <= 0 and table["type"] != "html_table_regex":
                pytest.fail(f"Structured table has invalid column count: {table}")

    elif mode == "image-only":
        # Image-only mode: should have image tables, no structured tables
        if image_count == 0:
            pytest.fail(f"Image-only mode should produce image tables, but found {image_count}")

        if structured_count > 0:
            pytest.fail(f"Image-only mode should not produce structured tables, but found {structured_count}")

        # Validate that image tables exist and have reasonable sizes
        for table in table_analysis["image_tables"]:
            if table["size_bytes"] <= 0:
                pytest.fail(f"Image table has invalid size: {table}")

    elif mode == "auto":
        # Auto mode: should have at least one type of table
        total_tables = structured_count + image_count
        if total_tables == 0:
            pytest.fail(f"Auto mode should produce at least one table representation, but found {total_tables}")

    else:
        pytest.fail(f"Unknown table processing mode: {mode}")


def assert_representation_exclusivity(table_analysis: dict[str, Any], mode: str) -> None:
    """
    Assert that pages don't contain both structured and image table representations.

    This applies to structured and image-only modes, but not auto mode.

    Args:
        table_analysis: Table analysis results
        mode: Table processing mode

    Raises:
        pytest.fail: If exclusivity is violated
    """
    if mode == "auto":
        return  # Auto mode allows mixed representations

    pages_with_structured = table_analysis.get("pages_with_structured", set())
    pages_with_images = table_analysis.get("pages_with_images", set())

    # Check for overlap
    overlapping_pages = pages_with_structured.intersection(pages_with_images)
    if overlapping_pages:
        pytest.fail(
            f"Mode {mode} should not have pages with both structured and image tables. "
            f"Overlapping pages: {overlapping_pages}"
        )
