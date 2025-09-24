# PySide6 Form Specs

## Definitions

- Typed **dataclasses** for all settings (with sensible defaults)
- Small **enums** for dropdowns
- A lightweight **JSON Schema generator** that walks the dataclasses (no 3rd-party deps)
- A `__main__` section that prints the schema (so you can pipe it to a file) and a default config JSON

```python
# form_spec.py
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict, fields, is_dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, get_origin, get_args

# ---------------------------
# Enums (for ComboBoxes)
# ---------------------------

class TablesMode(str, Enum):
    auto = "auto"
    structured = "structured"
    image_only = "image-only"

class OCRMode(str, Enum):
    auto = "auto"
    on = "on"
    off = "off"

class Verbosity(str, Enum):
    normal = "normal"   # no -v
    verbose = "verbose" # -v
    debug = "debug"     # -vv


# ---------------------------
# Dataclasses (GUI model)
# ---------------------------

@dataclass
class CoreConfig:
    pdf_file: str = ""          # required on run (must exist, .pdf)
    mod_id: str = ""            # required, slug
    mod_title: str = ""         # required, non-empty
    out_dir: str = "dist"       # must be creatable

@dataclass
class ModuleOptions:
    author: str = ""
    license: str = ""
    pack_name: str = ""         # defaults to f"{mod_id}-journals" if blank
    toc: bool = True
    deterministic_ids: bool = True

@dataclass
class ConversionOptions:
    tables: TablesMode = TablesMode.auto
    ocr: OCRMode = OCRMode.auto
    picture_descriptions: bool = False
    vlm_repo_id: str = ""       # required when picture_descriptions is True

@dataclass
class PerformanceOptions:
    pages: str = ""             # e.g. "1,5-10,15"
    workers: int = 1
    reflow_columns: bool = False

@dataclass
class CachingOptions:
    docling_json: str = ""      # path to load/save cache
    write_docling_json: bool = False
    fallback_on_json_failure: bool = True

@dataclass
class OutputOptions:
    compile_pack: bool = False

@dataclass
class LoggingOptions:
    verbosity: Verbosity = Verbosity.normal

@dataclass
class AppConfig:
    core: CoreConfig = CoreConfig()
    module: ModuleOptions = ModuleOptions()
    conversion: ConversionOptions = ConversionOptions()
    performance: PerformanceOptions = PerformanceOptions()
    caching: CachingOptions = CachingOptions()
    output: OutputOptions = OutputOptions()
    logging: LoggingOptions = LoggingOptions()


# ---------------------------
# Validation helpers (for UI)
# ---------------------------

MOD_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PAGES_RE = re.compile(r"^(\d+(-\d+)?)(,\d+(-\d+)?)*$")

def validate_core(cfg: CoreConfig) -> List[str]:
    errs: List[str] = []
    if not cfg.pdf_file or not cfg.pdf_file.lower().endswith(".pdf") or not os.path.exists(cfg.pdf_file):
        errs.append("pdf_file must point to an existing .pdf")
    if not cfg.mod_id or not MOD_ID_RE.match(cfg.mod_id):
        errs.append("mod_id must be a lowercase, dash-separated slug (e.g. my-book)")
    if not cfg.mod_title.strip():
        errs.append("mod_title is required")
    # out_dir will be created at run time; warn if parent not writable
    parent = os.path.abspath(os.path.join(cfg.out_dir or ".", ".."))
    if not os.path.exists(parent) or not os.access(parent, os.W_OK):
        errs.append(f"Parent directory not writable: {parent}")
    return errs

def validate_conversion(cfg: ConversionOptions) -> List[str]:
    errs: List[str] = []
    if cfg.picture_descriptions and not cfg.vlm_repo_id.strip():
        errs.append("vlm_repo_id is required when picture_descriptions is enabled")
    return errs

def validate_performance(cfg: PerformanceOptions) -> List[str]:
    errs: List[str] = []
    if cfg.pages and not PAGES_RE.match(cfg.pages.strip()):
        errs.append("pages must be a list of numbers and ranges, e.g. 1,5-10,15")
    if cfg.workers < 1:
        errs.append("workers must be >= 1")
    return errs

def validate_config(cfg: AppConfig) -> List[str]:
    errs: List[str] = []
    errs += validate_core(cfg.core)
    errs += validate_conversion(cfg.conversion)
    errs += validate_performance(cfg.performance)
    return errs


# ---------------------------
# JSON Schema generation
# ---------------------------

def _enum_schema(enum_cls: Any) -> Dict[str, Any]:
    return {
        "type": "string",
        "enum": [e.value for e in enum_cls]
    }

def _python_type_to_schema(py_t: Any) -> Dict[str, Any]:
    origin = get_origin(py_t)
    if origin is Optional or origin is Union := getattr(__import__('typing'), 'Union', None) and origin is Union:
        args = [a for a in get_args(py_t) if a is not type(None)]
        return _python_type_to_schema(args[0]) if args else {"type": "string"}

    if isinstance(py_t, type) and issubclass(py_t, Enum):
        return _enum_schema(py_t)

    if py_t in (str,):
        return {"type": "string"}
    if py_t in (int,):
        return {"type": "integer"}
    if py_t in (bool,):
        return {"type": "boolean"}
    if py_t in (float,):
        return {"type": "number"}
    if origin in (list, List):
        (item_t,) = get_args(py_t) or (str,)
        return {"type": "array", "items": _python_type_to_schema(item_t)}
    if origin in (tuple, Tuple):
        args = get_args(py_t) or ()
        return {"type": "array", "prefixItems": [_python_type_to_schema(a) for a in args]}
    return {"type": "object"}

def _dataclass_to_schema(dc_type: Any) -> Dict[str, Any]:
    assert is_dataclass(dc_type)
    props: Dict[str, Any] = {}
    required: List[str] = []
    for f in fields(dc_type):
        f_schema = _python_type_to_schema(f.type)
        # Attach common constraints by name (for small UX hints)
        if f.name == "mod_id":
            f_schema["pattern"] = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
            f_schema["description"] = "Lowercase, dash-separated slug."
        if f.name == "pages":
            f_schema["pattern"] = r"^(\d+(-\d+)?)(,\d+(-\d+)?)*$"
            f_schema["description"] = "Page list/ranges, e.g. 1,5-10,15"
        if f.name == "pdf_file":
            f_schema["description"] = "Path to a .pdf file"
        if f.name == "out_dir":
            f_schema["description"] = "Output directory (will be created if missing)"
        if f.default is not None and f.default != "":
            # provide default when meaningful (empty string is noisy)
            f_schema["default"] = f.default if not is_dataclass(f.default) else asdict(f.default)
        props[f.name] = f_schema

        # Minimal requireds (UI can handle others contextually)
        if dc_type is CoreConfig and f.name in ("pdf_file", "mod_id", "mod_title", "out_dir"):
            required.append(f.name)
    schema = {
        "type": "object",
        "properties": props,
    }
    if required:
        schema["required"] = required
    return schema

def app_config_json_schema() -> Dict[str, Any]:
    # Compose nested schema
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "pdf2foundry GUI Config",
        "type": "object",
        "properties": {
            "core": _dataclass_to_schema(CoreConfig),
            "module": _dataclass_to_schema(ModuleOptions),
            "conversion": _dataclass_to_schema(ConversionOptions),
            "performance": _dataclass_to_schema(PerformanceOptions),
            "caching": _dataclass_to_schema(CachingOptions),
            "output": _dataclass_to_schema(OutputOptions),
            "logging": _dataclass_to_schema(LoggingOptions),
        },
        "required": ["core"],
        "additionalProperties": False
    }


# ---------------------------
# Small helpers for presets
# ---------------------------

def to_json(cfg: AppConfig) -> str:
    return json.dumps(asdict(cfg), indent=2)

def from_json(s: str) -> AppConfig:
    raw = json.loads(s)
    # Convert enums back from strings
    raw["conversion"]["tables"] = TablesMode(raw["conversion"]["tables"])
    raw["conversion"]["ocr"] = OCRMode(raw["conversion"]["ocr"])
    raw["logging"]["verbosity"] = Verbosity(raw["logging"]["verbosity"])
    # Rehydrate dataclasses
    return AppConfig(
        core=CoreConfig(**raw["core"]),
        module=ModuleOptions(**raw["module"]),
        conversion=ConversionOptions(**raw["conversion"]),
        performance=PerformanceOptions(**raw["performance"]),
        caching=CachingOptions(**raw["caching"]),
        output=OutputOptions(**raw["output"]),
        logging=LoggingOptions(**raw["logging"]),
    )


# ---------------------------
# CLI demo (prints schema & defaults)
# ---------------------------

if __name__ == "__main__":
    cfg = AppConfig()
    schema = app_config_json_schema()
    print("# JSON Schema")
    print(json.dumps(schema, indent=2))
    print("\n# Default Config")
    print(to_json(cfg))
```

## How to use it

- **Generate JSON Schema**

  ```bash
  python form_spec.py > schema_and_defaults.json
  ```

  (The file will contain the schema and a default config example.)

- **Bind to PySide6**

  - Use each dataclass as your widget model (e.g., `QLineEdit` ↔ `CoreConfig.mod_id`, `QComboBox` ↔ `ConversionOptions.tables`).
  - When the form changes, update the `AppConfig` instance; serialize presets with `to_json(cfg)` and reload with `from_json(...)`.
  - For inline validation, call `validate_config(cfg)` before starting a conversion and surface errors in the UI.
