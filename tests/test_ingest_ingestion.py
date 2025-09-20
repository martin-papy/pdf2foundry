from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pdf2foundry.ingest.docling_parser import parse_structure_from_doc
from pdf2foundry.ingest.ingestion import (
    JsonLoadError,
    JsonOpts,
    JsonValidationError,
    ingest_docling,
    load_json_file,
    try_load_doc_from_json,
    validate_doc,
)


class _DummyDoc:
    def __init__(self, pages: int = 3, outline: list[Any] | None = None) -> None:
        self._pages = pages
        self._outline = outline or []

    def num_pages(self) -> int:
        return self._pages

    def export_to_html(self, **_: object) -> str:  # pragma: no cover - not used here
        return "<html></html>"

    # Outline-like attribute for parse_structure_from_doc tests
    @property
    def outline(self) -> list[Any]:
        return self._outline

    # Optional serializer for ingestion JSON write path
    def to_json(self) -> str:  # pragma: no cover - trivial
        return "{}"


def test_ingest_docling_converts_and_emits(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, dict[str, int | str]]] = []

    def on_progress(event: str, payload: dict[str, int | str]) -> None:
        events.append((event, payload))

    dummy = _DummyDoc(pages=4)

    def fake_convert(_: Path) -> _DummyDoc:
        return dummy

    # Patch the symbol resolved inside ingest_docling by its fully qualified import
    monkeypatch.setattr("pdf2foundry.ingest.docling_adapter.run_docling_conversion", fake_convert)

    doc = ingest_docling(Path("/tmp/x.pdf"), JsonOpts(), on_progress=on_progress)
    assert doc is dummy
    # Expect ingest converting and converted events
    assert any(e[0] == "ingest:converting" for e in events)
    assert any(e[0] == "ingest:converted" for e in events)


def test_ingest_docling_writes_json_when_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = _DummyDoc(pages=1)

    def fake_convert(_: Path) -> _DummyDoc:
        return dummy

    monkeypatch.setattr("pdf2foundry.ingest.docling_adapter.run_docling_conversion", fake_convert)

    json_path = tmp_path / "docling.json"
    events: list[tuple[str, dict[str, int | str]]] = []

    def on_progress(event: str, payload: dict[str, int | str]) -> None:
        events.append((event, payload))

    doc = ingest_docling(Path("/tmp/x.pdf"), JsonOpts(path=json_path), on_progress=on_progress)
    assert doc is dummy
    assert json_path.exists()
    assert json_path.read_text(encoding="utf-8").strip() != ""
    assert any(e[0] == "ingest:saved_to_cache" for e in events)


def test_parse_structure_from_doc_outline() -> None:
    # Build a minimal outline tree compatible with _outline_from_docling expectations
    class _Node:
        def __init__(self, title: str, page: int, children: list[_Node] | None = None) -> None:
            self.title = title
            self.page = page
            self.children = children or []

    outline: list[Any] = [
        _Node(
            "Chapter 1",
            1,
            [
                _Node("Section 1", 2),
                _Node("Section 2", 3),
            ],
        )
    ]

    doc = _DummyDoc(pages=5, outline=outline)
    parsed = parse_structure_from_doc(doc)
    assert parsed.page_count == 5
    assert parsed.outline and parsed.outline[0].title == "Chapter 1"


# Error handling tests for Task 13.4


class _InvalidDoc:
    """Mock document that fails validation in various ways."""

    def __init__(
        self,
        *,
        pages: int = 0,
        has_export: bool = True,
        export_fails: bool = False,
        export_returns_non_string: bool = False,
    ) -> None:
        self._pages = pages
        self._has_export = has_export
        self._export_fails = export_fails
        self._export_returns_non_string = export_returns_non_string

    def num_pages(self) -> int:
        return self._pages

    def export_to_html(self, **_: object) -> Any:
        if not self._has_export:
            raise AttributeError("export_to_html not available")
        if self._export_fails:
            raise RuntimeError("Export failed")
        if self._export_returns_non_string:
            return 42  # Invalid return type
        return "<html></html>"


def test_validate_doc_success() -> None:
    """Test that a valid document passes validation."""
    doc = _DummyDoc(pages=3)
    validate_doc(doc)  # Should not raise


def test_validate_doc_zero_pages() -> None:
    """Test that zero pages fails validation."""
    doc = _InvalidDoc(pages=0)
    with pytest.raises(JsonValidationError, match="Invalid page count: 0"):
        validate_doc(doc)


def test_validate_doc_negative_pages() -> None:
    """Test that negative pages fails validation."""
    doc = _InvalidDoc(pages=-1)
    with pytest.raises(JsonValidationError, match="Invalid page count: -1"):
        validate_doc(doc)


def test_validate_doc_missing_export_method() -> None:
    """Test that missing export_to_html method fails validation."""

    # Create a document without the export_to_html method
    class _DocWithoutExport:
        def __init__(self) -> None:
            self._pages = 3

        def num_pages(self) -> int:
            return self._pages

    doc = _DocWithoutExport()
    with pytest.raises(JsonValidationError, match="Missing or invalid 'export_to_html' method"):
        validate_doc(doc)  # type: ignore[arg-type]


def test_validate_doc_export_method_fails() -> None:
    """Test that export_to_html method failure is caught."""
    doc = _InvalidDoc(pages=3, export_fails=True)
    with pytest.raises(JsonValidationError, match="export_to_html\\(\\) method failed"):
        validate_doc(doc)


def test_validate_doc_export_returns_non_string() -> None:
    """Test that export_to_html returning non-string fails validation."""
    doc = _InvalidDoc(pages=3, export_returns_non_string=True)
    with pytest.raises(JsonValidationError, match="export_to_html\\(\\) must return a string"):
        validate_doc(doc)


def test_load_json_file_success(tmp_path: Path) -> None:
    """Test successful JSON file loading."""
    json_file = tmp_path / "test.json"
    json_content = '{"test": "value"}'
    json_file.write_text(json_content, encoding="utf-8")

    result = load_json_file(json_file)
    assert result == json_content


def test_load_json_file_missing_file(tmp_path: Path) -> None:
    """Test that missing file raises JsonLoadError."""
    missing_file = tmp_path / "missing.json"
    with pytest.raises(JsonLoadError, match="Failed to load JSON from.*missing.json"):
        load_json_file(missing_file)


def test_load_json_file_invalid_json(tmp_path: Path) -> None:
    """Test that invalid JSON raises JsonLoadError."""
    json_file = tmp_path / "invalid.json"
    json_file.write_text("{ invalid json", encoding="utf-8")

    with pytest.raises(JsonLoadError, match="Failed to load JSON from.*invalid.json"):
        load_json_file(json_file)


def test_load_json_file_permission_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that permission errors are handled properly."""
    json_file = tmp_path / "test.json"
    json_file.write_text('{"test": "value"}', encoding="utf-8")

    # Mock read_text to raise PermissionError
    def mock_read_text(*args: Any, **kwargs: Any) -> str:
        raise PermissionError("Permission denied")

    monkeypatch.setattr(Path, "read_text", mock_read_text)

    with pytest.raises(
        JsonLoadError, match="Failed to load JSON from.*test.json.*Permission denied"
    ):
        load_json_file(json_file)


def test_try_load_doc_from_json_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test successful document loading from JSON."""
    json_file = tmp_path / "doc.json"
    json_file.write_text('{"num_pages": 3}', encoding="utf-8")

    # Mock doc_from_json to return a valid document
    def mock_doc_from_json(text: str) -> _DummyDoc:
        return _DummyDoc(pages=3)

    monkeypatch.setattr("pdf2foundry.ingest.json_io.doc_from_json", mock_doc_from_json)

    doc, warnings = try_load_doc_from_json(json_file, fallback_on_failure=False)
    assert doc is not None
    assert doc.num_pages() == 3
    assert warnings == []


def test_try_load_doc_from_json_fallback_enabled(tmp_path: Path) -> None:
    """Test that fallback returns None and warnings when enabled."""
    json_file = tmp_path / "missing.json"  # File doesn't exist

    doc, warnings = try_load_doc_from_json(json_file, fallback_on_failure=True)
    assert doc is None
    assert len(warnings) == 1
    assert "Failed to load DoclingDocument from" in warnings[0]
    assert "Will fall back to conversion" in warnings[0]


def test_try_load_doc_from_json_fallback_disabled(tmp_path: Path) -> None:
    """Test that fallback disabled raises exceptions."""
    json_file = tmp_path / "missing.json"  # File doesn't exist

    with pytest.raises(JsonLoadError, match="Failed to load JSON from.*missing.json"):
        try_load_doc_from_json(json_file, fallback_on_failure=False)


def test_try_load_doc_from_json_validation_error_fallback_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that validation errors trigger fallback when enabled."""
    json_file = tmp_path / "invalid_doc.json"
    json_file.write_text('{"num_pages": 3}', encoding="utf-8")

    # Mock doc_from_json to return an invalid document
    def mock_doc_from_json(text: str) -> _InvalidDoc:
        return _InvalidDoc(pages=0)  # Invalid: zero pages

    monkeypatch.setattr("pdf2foundry.ingest.json_io.doc_from_json", mock_doc_from_json)

    doc, warnings = try_load_doc_from_json(json_file, fallback_on_failure=True)
    assert doc is None
    assert len(warnings) == 1
    assert "Failed to load DoclingDocument from" in warnings[0]


def test_try_load_doc_from_json_validation_error_fallback_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that validation errors raise when fallback disabled."""
    json_file = tmp_path / "invalid_doc.json"
    json_file.write_text('{"num_pages": 3}', encoding="utf-8")

    # Mock doc_from_json to return an invalid document
    def mock_doc_from_json(text: str) -> _InvalidDoc:
        return _InvalidDoc(pages=0)  # Invalid: zero pages

    monkeypatch.setattr("pdf2foundry.ingest.json_io.doc_from_json", mock_doc_from_json)

    with pytest.raises(
        JsonValidationError,
        match="Invalid DoclingDocument JSON at.*invalid_doc.json.*Invalid page count: 0",
    ):
        try_load_doc_from_json(json_file, fallback_on_failure=False)


def test_try_load_doc_from_json_corrupt_json_fallback_enabled(tmp_path: Path) -> None:
    """Test that corrupt JSON triggers fallback when enabled."""
    json_file = tmp_path / "corrupt.json"
    json_file.write_text("{ invalid json", encoding="utf-8")

    doc, warnings = try_load_doc_from_json(json_file, fallback_on_failure=True)
    assert doc is None
    assert len(warnings) == 1
    assert "Failed to load DoclingDocument from" in warnings[0]


def test_try_load_doc_from_json_corrupt_json_fallback_disabled(tmp_path: Path) -> None:
    """Test that corrupt JSON raises when fallback disabled."""
    json_file = tmp_path / "corrupt.json"
    json_file.write_text("{ invalid json", encoding="utf-8")

    with pytest.raises(JsonLoadError, match="Failed to load JSON from.*corrupt.json"):
        try_load_doc_from_json(json_file, fallback_on_failure=False)
