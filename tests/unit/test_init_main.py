from __future__ import annotations

import importlib


def test_package_version_exposes_string() -> None:
    mod = importlib.import_module("pdf2foundry")
    v = getattr(mod, "__version__", None)
    assert isinstance(v, str)


def test_main_module_imports() -> None:
    # Ensure __main__ module imports without executing CLI
    importlib.import_module("pdf2foundry.__main__")
