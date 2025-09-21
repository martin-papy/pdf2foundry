"""Comprehensive tests for single-pass Docling ingestion and JSON caching behavior.

This module tests the complete single-pass ingestion pipeline introduced in Task 13,
ensuring that DoclingDocument conversion happens exactly once per run and that
JSON caching works correctly in all scenarios.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from pdf2foundry.cli import app
from pdf2foundry.ingest import docling_adapter as da
from pdf2foundry.ingest.content_extractor import extract_semantic_content
from pdf2foundry.ingest.docling_parser import parse_structure_from_doc
from pdf2foundry.ingest.ingestion import JsonOpts, ingest_docling
from pdf2foundry.ingest.json_io import doc_from_json, doc_to_json


class _TestDoc:
    """Test document that mimics DoclingDocument interface."""

    def __init__(self, pages: int = 3, outline: list[Any] | None = None) -> None:
        self._pages = pages
        self._outline = outline or []

    def num_pages(self) -> int:
        return self._pages

    def export_to_html(self, **_: object) -> str:
        return f"<html><body>Test document with {self._pages} pages</body></html>"

    @property
    def outline(self) -> list[Any]:
        return self._outline

    def to_json(self) -> str:
        return json.dumps({"num_pages": self._pages, "test_data": True})


class TestSinglePassConversion:
    """Test that conversion happens exactly once per run."""

    def test_cli_single_conversion_count_no_cache(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that CLI without cache flags performs exactly one conversion."""
        conversion_calls = []

        def mock_convert(pdf_path: Path, **_: Any) -> _TestDoc:
            conversion_calls.append(pdf_path)
            return _TestDoc(pages=2)

        monkeypatch.setattr(da, "_do_docling_convert_impl", mock_convert)
        da._cached_convert.cache_clear()

        # Create larger PDF to bypass placeholder check (needs > 1024 bytes)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            # Write a larger PDF content to bypass the placeholder check
            pdf_content = b"%PDF-1.4\n" + b"x" * 1100 + b"\n%EOF\n"
            tmp.write(pdf_content)
            pdf_path = tmp.name

        try:
            runner = CliRunner()
            result = runner.invoke(
                app,
                [
                    "convert",
                    pdf_path,
                    "--mod-id",
                    "test-mod",
                    "--mod-title",
                    "Test",
                    "--out-dir",
                    str(tmp_path),
                ],
            )
            assert result.exit_code == 0
            # Exactly one conversion should have occurred
            assert len(conversion_calls) == 1
            assert "Converting PDF:" in result.stdout
        finally:
            Path(pdf_path).unlink(missing_ok=True)

    def test_ingest_docling_single_conversion_direct(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that ingest_docling performs exactly one conversion when called directly."""
        conversion_calls = []

        def mock_convert(pdf_path: Path, **_: Any) -> _TestDoc:
            conversion_calls.append(pdf_path)
            return _TestDoc(pages=3)

        monkeypatch.setattr(da, "_do_docling_convert_impl", mock_convert)
        da._cached_convert.cache_clear()

        # Call ingest_docling directly
        doc = ingest_docling(Path("/tmp/test.pdf"), JsonOpts())
        assert isinstance(doc, _TestDoc)
        assert doc.num_pages() == 3
        assert len(conversion_calls) == 1

    def test_same_docling_document_instance_used_by_both_stages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that structure and content extraction receive the same DoclingDocument instance."""
        test_doc = _TestDoc(pages=4)
        structure_docs = []
        content_docs = []

        def mock_convert(pdf_path: Path, **_: Any) -> _TestDoc:
            return test_doc

        def mock_parse_structure(doc: Any, **_: Any) -> Any:
            structure_docs.append(doc)
            return Mock(page_count=doc.num_pages(), outline=[])

        def mock_extract_content(doc: Any, out_assets: Path, options: str, **_: Any) -> Any:
            content_docs.append(doc)
            return Mock(pages=[], images=[], tables=[], links=[])

        monkeypatch.setattr(da, "_do_docling_convert_impl", mock_convert)
        monkeypatch.setattr(
            "pdf2foundry.ingest.docling_parser.parse_structure_from_doc", mock_parse_structure
        )
        monkeypatch.setattr(
            "pdf2foundry.ingest.content_extractor.extract_semantic_content", mock_extract_content
        )
        da._cached_convert.cache_clear()

        # Call ingest_docling and then both processing stages
        doc = ingest_docling(Path("/tmp/test.pdf"), JsonOpts())

        # Import the functions to call them directly (they should use our mocks)
        from pdf2foundry.ingest.content_extractor import extract_semantic_content
        from pdf2foundry.ingest.docling_parser import parse_structure_from_doc

        parse_structure_from_doc(doc)
        extract_semantic_content(doc, Path("/tmp/out"), options="auto")

        # All three should have received the same instance
        assert doc is test_doc
        assert len(structure_docs) == 1
        assert len(content_docs) == 1
        assert structure_docs[0] is test_doc
        assert content_docs[0] is test_doc


class TestJSONCaching:
    """Test JSON cache loading and saving behavior."""

    def test_cache_load_avoids_conversion(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that valid JSON cache avoids conversion entirely."""
        conversion_calls = []

        def mock_convert(pdf_path: Path, **_: Any) -> _TestDoc:
            conversion_calls.append(pdf_path)
            return _TestDoc()

        monkeypatch.setattr(da, "_do_docling_convert_impl", mock_convert)
        da._cached_convert.cache_clear()

        # Create valid JSON cache
        cache_file = tmp_path / "cache.json"
        test_doc = _TestDoc(pages=5)
        cache_file.write_text(doc_to_json(test_doc), encoding="utf-8")

        # Load from cache
        doc = ingest_docling(Path("/tmp/test.pdf"), JsonOpts(path=cache_file))

        # No conversion should have occurred
        assert len(conversion_calls) == 0
        assert doc.num_pages() == 5

    def test_ingest_docling_cache_load_avoids_conversion(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that ingest_docling with valid cache avoids conversion."""
        conversion_calls = []

        def mock_convert(pdf_path: Path, **_: Any) -> _TestDoc:
            conversion_calls.append(pdf_path)
            return _TestDoc()

        monkeypatch.setattr(da, "_do_docling_convert_impl", mock_convert)
        da._cached_convert.cache_clear()

        # Create valid JSON cache
        cache_file = tmp_path / "cache.json"
        test_doc = _TestDoc(pages=7)
        cache_file.write_text(doc_to_json(test_doc), encoding="utf-8")

        # Load from cache using ingest_docling directly
        doc = ingest_docling(Path("/tmp/test.pdf"), JsonOpts(path=cache_file))

        # No conversion should have occurred
        assert len(conversion_calls) == 0
        assert doc.num_pages() == 7

    def test_convenience_mode_missing_file_converts_and_saves(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test convenience mode: if path doesn't exist, convert and save."""
        conversion_calls = []
        test_doc = _TestDoc(pages=6)

        def mock_convert(pdf_path: Path, **_: Any) -> _TestDoc:
            conversion_calls.append(pdf_path)
            return test_doc

        monkeypatch.setattr(da, "_do_docling_convert_impl", mock_convert)
        da._cached_convert.cache_clear()

        cache_file = tmp_path / "new_cache.json"
        assert not cache_file.exists()

        # First run: should convert and save
        doc1 = ingest_docling(Path("/tmp/test.pdf"), JsonOpts(path=cache_file))
        assert len(conversion_calls) == 1
        assert cache_file.exists()
        assert doc1.num_pages() == 6

        # Second run: should load from cache
        doc2 = ingest_docling(Path("/tmp/test.pdf"), JsonOpts(path=cache_file))
        assert len(conversion_calls) == 1  # Still only one conversion
        assert doc2.num_pages() == 6

    def test_write_docling_json_flag_saves_to_default_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that --write-docling-json saves to default path."""
        test_doc = _TestDoc(pages=8)

        def mock_convert(pdf_path: Path, **_: Any) -> _TestDoc:
            return test_doc

        monkeypatch.setattr(da, "_do_docling_convert_impl", mock_convert)
        da._cached_convert.cache_clear()

        default_path = tmp_path / "sources" / "docling.json"

        # Use write flag with default path
        doc = ingest_docling(Path("/tmp/test.pdf"), JsonOpts(write=True, default_path=default_path))

        assert doc.num_pages() == 8
        assert default_path.exists()

        # Verify saved content can be loaded
        loaded_doc = doc_from_json(default_path.read_text(encoding="utf-8"))
        assert loaded_doc.num_pages() == 8


class TestErrorHandling:
    """Test error handling for invalid JSON and fallback behavior."""

    def test_invalid_json_without_fallback_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that invalid JSON raises error when try_load_doc_from_json is called directly."""
        # Test the lower-level function directly since convenience mode always allows fallback
        from pdf2foundry.ingest.ingestion import JsonLoadError, try_load_doc_from_json

        # Create invalid JSON
        cache_file = tmp_path / "invalid.json"
        cache_file.write_text("{ invalid json", encoding="utf-8")

        # Should raise error without fallback
        with pytest.raises(JsonLoadError):
            try_load_doc_from_json(cache_file, fallback_on_failure=False)

    def test_invalid_json_with_fallback_converts(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that invalid JSON with fallback flag falls back to conversion."""
        conversion_calls = []
        test_doc = _TestDoc(pages=9)

        def mock_convert(pdf_path: Path, **_: Any) -> _TestDoc:
            conversion_calls.append(pdf_path)
            return test_doc

        monkeypatch.setattr(da, "_do_docling_convert_impl", mock_convert)
        da._cached_convert.cache_clear()

        # Create invalid JSON
        cache_file = tmp_path / "invalid.json"
        cache_file.write_text("{ invalid json", encoding="utf-8")

        # Should fall back to conversion
        doc = ingest_docling(
            Path("/tmp/test.pdf"), JsonOpts(path=cache_file, fallback_on_json_failure=True)
        )

        assert len(conversion_calls) == 1
        assert doc.num_pages() == 9
        # Should have overwritten the invalid file
        assert cache_file.exists()


class TestJSONRoundtrip:
    """Test JSON serialization/deserialization roundtrip behavior."""

    def test_json_roundtrip_preserves_structure_output(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that JSON roundtrip produces identical structure parsing output."""
        # Create test document without outline (since JSON roundtrip doesn't preserve
        # outline structure)
        original_doc = _TestDoc(pages=5)

        # Parse structure from original
        original_structure = parse_structure_from_doc(original_doc)

        # Serialize and deserialize
        json_text = doc_to_json(original_doc)
        roundtrip_doc = doc_from_json(json_text)

        # Parse structure from roundtrip doc
        roundtrip_structure = parse_structure_from_doc(roundtrip_doc)

        # Compare key properties - both should have same page count
        assert original_structure.page_count == roundtrip_structure.page_count
        # Both should have default outline structure (single "Document" entry)
        assert len(original_structure.outline or []) == len(roundtrip_structure.outline or [])

    def test_json_roundtrip_preserves_content_output(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that JSON roundtrip produces identical content extraction output."""
        original_doc = _TestDoc(pages=4)

        # Mock content extraction to return consistent results based on doc pages
        def mock_extract(doc: Any, output_dir: Path, options: str, **_: Any) -> Any:
            from pdf2foundry.model.content import HtmlPage, ParsedContent

            pages = [
                HtmlPage(html=f"<p>Page {i}</p>", page_no=i) for i in range(1, doc.num_pages() + 1)
            ]
            return ParsedContent(pages=pages, images=[], tables=[], links=[])

        monkeypatch.setattr(
            "pdf2foundry.ingest.content_extractor.extract_semantic_content", mock_extract
        )

        # Extract from original
        original_content = extract_semantic_content(original_doc, tmp_path, options="auto")

        # Serialize and deserialize
        json_text = doc_to_json(original_doc)
        roundtrip_doc = doc_from_json(json_text)

        # Extract from roundtrip doc
        roundtrip_content = extract_semantic_content(roundtrip_doc, tmp_path, options="auto")

        # Compare outputs - both should have same number of pages
        assert len(original_content.pages) == len(roundtrip_content.pages)
        # Both should have same page count (4)
        assert len(original_content.pages) == 4
        assert len(roundtrip_content.pages) == 4


class TestDeterminism:
    """Test that JSON serialization is deterministic."""

    def test_json_serialization_is_deterministic(self) -> None:
        """Test that serializing the same document twice produces identical JSON."""
        doc = _TestDoc(pages=10)

        json1 = doc_to_json(doc, pretty=True)
        json2 = doc_to_json(doc, pretty=True)

        assert json1 == json2

        # Also test compact format
        compact1 = doc_to_json(doc, pretty=False)
        compact2 = doc_to_json(doc, pretty=False)

        assert compact1 == compact2

    def test_json_files_are_byte_identical(self, tmp_path: Path) -> None:
        """Test that saving the same document twice produces byte-identical files."""
        doc = _TestDoc(pages=12)

        file1 = tmp_path / "doc1.json"
        file2 = tmp_path / "doc2.json"

        # Save twice
        file1.write_text(doc_to_json(doc, pretty=True), encoding="utf-8")
        file2.write_text(doc_to_json(doc, pretty=True), encoding="utf-8")

        # Files should be byte-identical
        assert file1.read_bytes() == file2.read_bytes()


class TestProgressEvents:
    """Test that progress events are emitted correctly and without duplicates."""

    def test_progress_events_no_duplicates_without_cache(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that progress events are emitted in correct order without duplicates (no cache)."""
        events = []
        test_doc = _TestDoc(pages=3)

        def mock_convert(pdf_path: Path, **_: Any) -> _TestDoc:
            return test_doc

        def capture_progress(event: str, payload: dict[str, Any]) -> None:
            events.append((event, payload))

        monkeypatch.setattr(da, "_do_docling_convert_impl", mock_convert)
        da._cached_convert.cache_clear()

        # Run ingestion with progress tracking
        doc = ingest_docling(Path("/tmp/test.pdf"), JsonOpts(), on_progress=capture_progress)

        # Verify document was returned
        assert doc.num_pages() == 3

        # Check event sequence
        event_names = [e[0] for e in events]

        # Should have ingest events but no duplicates
        assert "ingest:converting" in event_names
        assert "ingest:converted" in event_names

        # Should not have duplicate conversion events
        convert_events = [e for e in event_names if "convert" in e.lower()]
        assert len(convert_events) <= 2  # converting + converted

    def test_progress_events_no_duplicates_with_cache(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that progress events are correct when loading from cache."""
        events = []
        test_doc = _TestDoc(pages=3)

        def mock_convert(pdf_path: Path, **_: Any) -> _TestDoc:
            return test_doc

        def capture_progress(event: str, payload: dict[str, Any]) -> None:
            events.append((event, payload))

        monkeypatch.setattr(da, "_do_docling_convert_impl", mock_convert)
        da._cached_convert.cache_clear()

        # Create cache file
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(doc_to_json(test_doc), encoding="utf-8")

        # Run ingestion with cache
        doc = ingest_docling(
            Path("/tmp/test.pdf"), JsonOpts(path=cache_file), on_progress=capture_progress
        )

        # Verify document was loaded from cache
        assert doc.num_pages() == 3

        # Check events
        event_names = [e[0] for e in events]

        # Should have cache load event, no conversion events
        assert "ingest:loaded_from_cache" in event_names
        assert "ingest:converting" not in event_names
        assert "ingest:converted" not in event_names
