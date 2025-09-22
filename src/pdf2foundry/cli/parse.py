"""CLI parsing utilities for PDF2Foundry."""

from __future__ import annotations


def parse_page_spec(spec: str) -> list[int]:
    """Parse a page specification string into a sorted list of 1-based page indices.

    Args:
        spec: Comma-separated list of page indices and ranges (e.g., "1,3,5-10")

    Returns:
        Sorted list of unique 1-based page indices

    Raises:
        ValueError: If the specification is invalid

    Examples:
        >>> parse_page_spec("1")
        [1]
        >>> parse_page_spec("1,3,5-7")
        [1, 3, 5, 6, 7]
        >>> parse_page_spec("2-2,4")
        [2, 4]
    """
    if not spec.strip():
        raise ValueError("Page specification cannot be empty")

    pages: set[int] = set()
    tokens = spec.split(",")

    for token in tokens:
        token = token.strip()
        if not token:
            raise ValueError(f"Invalid page specification '{spec}': empty token found")

        if "-" in token and not token.startswith("-"):
            # Range specification (but not negative number)
            parts = token.split("-")
            if len(parts) != 2:
                raise ValueError(f"Invalid page specification '{spec}': malformed range '{token}'")

            try:
                start = int(parts[0])
                end = int(parts[1])
            except ValueError as exc:
                raise ValueError(f"Invalid page specification '{spec}': non-numeric range '{token}'") from exc

            if start <= 0 or end <= 0:
                raise ValueError(f"Invalid page specification '{spec}': " f"page numbers must be positive, got '{token}'")

            if start > end:
                raise ValueError(f"Invalid page specification '{spec}': " f"range start must be <= end, got '{token}'")

            pages.update(range(start, end + 1))
        else:
            # Single page
            try:
                page = int(token)
            except ValueError as exc:
                raise ValueError(f"Invalid page specification '{spec}': non-numeric page '{token}'") from exc

            if page <= 0:
                raise ValueError(f"Invalid page specification '{spec}': " f"page numbers must be positive, got '{token}'")

            pages.add(page)

    return sorted(pages)


__all__ = ["parse_page_spec"]
