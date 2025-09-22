#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path


def iter_python_files(paths: Iterable[Path]) -> Iterable[Path]:
    for root in paths:
        if root.is_file() and root.suffix == ".py":
            yield root
            continue
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            # Skip common generated/third-party dirs if user passed a parent
            if any(part in {".git", ".venv", "node_modules", "dist", "build", ".taskmaster"} for part in p.parts):
                continue
            yield p


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enforce maximum Python file length in lines")
    parser.add_argument("--max-lines", type=int, default=500, help="Maximum allowed lines per file (default: 500)")
    parser.add_argument(
        "--paths",
        nargs="+",
        default=["src", "tests"],
        help="Paths to scan (directories or files). Defaults to src and tests",
    )
    args = parser.parse_args(argv)

    max_lines = int(args.max_lines)
    roots = [Path(p).resolve() for p in args.paths]

    violations: list[tuple[Path, int]] = []
    for py_file in iter_python_files(roots):
        try:
            with py_file.open("r", encoding="utf-8", errors="ignore") as f:
                count = sum(1 for _ in f)
        except Exception:
            # If a file can't be read, skip it rather than blocking commits
            continue
        if count > max_lines:
            violations.append((py_file, count))

    if violations:
        print(f"The following files exceed the maximum allowed length ({max_lines} lines):")
        for path, count in sorted(violations, key=lambda x: x[1], reverse=True):
            rel = path.relative_to(Path.cwd()) if str(path).startswith(str(Path.cwd())) else path
            print(f" - {rel}: {count} lines")
        print("\nPlease split large modules into smaller, focused modules per our" " architecture guidelines.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
