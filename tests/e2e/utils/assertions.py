"""Rich assertion helpers for E2E tests."""

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from .validation import (
    check_toc_links,
    validate_assets,
    validate_compendium_structure,
    validate_module_json,
)

console = Console()


def assert_valid_module_json(path: Path, custom_message: str | None = None) -> None:
    """
    Assert that a module.json file is valid, with rich error output.

    Args:
        path: Path to the module.json file
        custom_message: Optional custom error message

    Raises:
        AssertionError: If validation fails
    """
    errors = validate_module_json(path)

    if errors:
        message = custom_message or f"Module validation failed for {path}"
        _display_validation_errors(message, errors, path)
        raise AssertionError(f"{message}: {len(errors)} validation errors found")


def assert_valid_compendium_structure(module_dir: Path, custom_message: str | None = None) -> None:
    """
    Assert that a module directory has valid structure, with rich error output.

    Args:
        module_dir: Path to the module directory
        custom_message: Optional custom error message

    Raises:
        AssertionError: If validation fails
    """
    errors = validate_compendium_structure(module_dir)

    if errors:
        message = custom_message or f"Compendium structure validation failed for {module_dir}"
        _display_validation_errors(message, errors, module_dir)
        raise AssertionError(f"{message}: {len(errors)} structure errors found")


def assert_no_broken_assets(module_dir: Path, custom_message: str | None = None) -> None:
    """
    Assert that all referenced assets exist and are valid, with rich error output.

    Args:
        module_dir: Path to the module directory
        custom_message: Optional custom error message

    Raises:
        AssertionError: If validation fails
    """
    errors = validate_assets(module_dir)

    if errors:
        message = custom_message or f"Asset validation failed for {module_dir}"
        _display_validation_errors(message, errors, module_dir)
        raise AssertionError(f"{message}: {len(errors)} asset errors found")


def assert_toc_resolves(module_dir: Path, custom_message: str | None = None) -> None:
    """
    Assert that TOC links resolve correctly, with rich error output.

    Args:
        module_dir: Path to the module directory
        custom_message: Optional custom error message

    Raises:
        AssertionError: If validation fails
    """
    errors = check_toc_links(module_dir)

    if errors:
        message = custom_message or f"TOC validation failed for {module_dir}"
        _display_validation_errors(message, errors, module_dir)
        raise AssertionError(f"{message}: {len(errors)} TOC errors found")


def assert_files_exist(file_paths: list[Path], custom_message: str | None = None) -> None:
    """
    Assert that all specified files exist, with rich error output.

    Args:
        file_paths: List of file paths to check
        custom_message: Optional custom error message

    Raises:
        AssertionError: If any files are missing
    """
    missing_files = [path for path in file_paths if not path.exists()]

    if missing_files:
        message = custom_message or "Required files are missing"

        table = Table(title="Missing Files", show_header=True, header_style="bold red")
        table.add_column("File Path", style="red")
        table.add_column("Parent Directory", style="dim")

        for path in missing_files:
            table.add_row(str(path.name), str(path.parent))

        console.print()
        console.print(Panel(table, title=message, border_style="red"))
        console.print()

        raise AssertionError(f"{message}: {len(missing_files)} files missing")


def assert_json_structure(json_path: Path, expected_structure: dict, custom_message: str | None = None) -> None:
    """
    Assert that a JSON file has the expected structure, with rich diff output.

    Args:
        json_path: Path to the JSON file
        expected_structure: Dictionary describing expected structure
        custom_message: Optional custom error message

    Raises:
        AssertionError: If structure doesn't match
    """
    import json

    if not json_path.exists():
        console.print(f"[red]JSON file not found: {json_path}[/red]")
        raise AssertionError(f"JSON file not found: {json_path}")

    try:
        with json_path.open() as f:
            actual_data = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON in {json_path}: {e}[/red]")
        raise AssertionError(f"Invalid JSON: {e}") from e

    errors = _check_structure_recursive(actual_data, expected_structure, "")

    if errors:
        message = custom_message or f"JSON structure validation failed for {json_path}"
        _display_structure_errors(message, errors, json_path, actual_data, expected_structure)
        raise AssertionError(f"{message}: {len(errors)} structure errors found")


def assert_performance_within_threshold(
    actual_time: float, expected_time: float, threshold: float = 0.2, custom_message: str | None = None
) -> None:
    """
    Assert that performance is within acceptable threshold, with rich output.

    Args:
        actual_time: Actual execution time in seconds
        expected_time: Expected/baseline time in seconds
        threshold: Acceptable threshold as a ratio (0.2 = 20% slower)
        custom_message: Optional custom error message

    Raises:
        AssertionError: If performance is outside threshold
    """
    max_allowed = expected_time * (1 + threshold)

    if actual_time > max_allowed:
        message = custom_message or "Performance regression detected"

        table = Table(title="Performance Comparison", show_header=True)
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")
        table.add_column("Status", justify="center")

        table.add_row("Expected Time", f"{expected_time:.3f}s", "✓")
        table.add_row("Actual Time", f"{actual_time:.3f}s", "[red]✗[/red]")
        table.add_row("Max Allowed", f"{max_allowed:.3f}s", "")
        table.add_row("Threshold", f"{threshold:.1%}", "")

        regression = (actual_time - expected_time) / expected_time
        status = "[red]FAIL[/red]" if regression > threshold else "[green]PASS[/green]"
        table.add_row("Regression", f"{regression:.1%}", status)

        console.print()
        console.print(Panel(table, title=message, border_style="red"))
        console.print()

        raise AssertionError(f"{message}: {regression:.1%} regression (threshold: {threshold:.1%})")


def _display_validation_errors(title: str, errors: list[str], path: Path) -> None:
    """Display validation errors in a rich format."""
    table = Table(title="Validation Errors", show_header=True, header_style="bold red")
    table.add_column("Error", style="red")

    for error in errors:
        table.add_row(error)

    console.print()
    console.print(Panel(table, title=f"{title}\\n[dim]{path}[/dim]", border_style="red"))
    console.print()


def _display_structure_errors(title: str, errors: list[str], path: Path, actual_data: Any, expected_structure: dict) -> None:
    """Display JSON structure errors with diff-like output."""
    # Create error table
    error_table = Table(title="Structure Errors", show_header=True, header_style="bold red")
    error_table.add_column("Path", style="yellow")
    error_table.add_column("Error", style="red")

    for error in errors:
        if ":" in error:
            path_part, error_part = error.split(":", 1)
            error_table.add_row(path_part.strip(), error_part.strip())
        else:
            error_table.add_row("", error)

    # Create structure comparison
    import json

    actual_json = json.dumps(actual_data, indent=2)[:500] + ("..." if len(str(actual_data)) > 500 else "")
    expected_json = json.dumps(expected_structure, indent=2)

    actual_syntax = Syntax(actual_json, "json", theme="monokai", line_numbers=True)
    expected_syntax = Syntax(expected_json, "json", theme="monokai", line_numbers=True)

    console.print()
    console.print(Panel(error_table, title=f"{title}\\n[dim]{path}[/dim]", border_style="red"))

    console.print("\\n[bold]Expected Structure:[/bold]")
    console.print(expected_syntax)

    console.print("\\n[bold]Actual Structure (first 500 chars):[/bold]")
    console.print(actual_syntax)
    console.print()


def _check_structure_recursive(actual: Any, expected: dict, path: str) -> list[str]:
    """Recursively check JSON structure against expected format."""
    errors = []

    if not isinstance(actual, dict):
        errors.append(f"{path}: Expected object, got {type(actual).__name__}")
        return errors

    for key, expected_type in expected.items():
        current_path = f"{path}.{key}" if path else key

        if key not in actual:
            errors.append(f"{current_path}: Missing required key")
            continue

        actual_value = actual[key]

        if isinstance(expected_type, dict):
            # Nested structure
            if isinstance(actual_value, dict):
                errors.extend(_check_structure_recursive(actual_value, expected_type, current_path))
            else:
                errors.append(f"{current_path}: Expected object, got {type(actual_value).__name__}")
        elif isinstance(expected_type, list) and len(expected_type) == 1:
            # Array of specific type
            if isinstance(actual_value, list):
                for i, item in enumerate(actual_value):
                    item_path = f"{current_path}[{i}]"
                    if isinstance(expected_type[0], dict):
                        if isinstance(item, dict):
                            errors.extend(_check_structure_recursive(item, expected_type[0], item_path))
                        else:
                            errors.append(f"{item_path}: Expected object, got {type(item).__name__}")
                    elif not isinstance(item, expected_type[0]):
                        errors.append(f"{item_path}: Expected {expected_type[0].__name__}, got {type(item).__name__}")
            else:
                errors.append(f"{current_path}: Expected array, got {type(actual_value).__name__}")
        elif isinstance(expected_type, type) and not isinstance(actual_value, expected_type):
            # Simple type check
            errors.append(f"{current_path}: Expected {expected_type.__name__}, got {type(actual_value).__name__}")

    return errors


def display_test_summary(test_name: str, passed: bool, details: str | None = None) -> None:
    """Display a formatted test summary."""
    status = "[green]PASSED[/green]" if passed else "[red]FAILED[/red]"
    title = f"Test: {test_name}"

    content = f"Status: {status}"
    if details:
        content += f"\\n\\n{details}"

    border_style = "green" if passed else "red"

    console.print()
    console.print(Panel(content, title=title, border_style=border_style))
    console.print()
