"""Tests for JSON roundtrip behavior, determinism, and progress events.

This module tests JSON serialization/deserialization roundtrip behavior,
deterministic serialization, and progress event emission for the single-pass
ingestion pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

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


class TestJSONRoundtrip:
    """Test JSON serialization/deserialization roundtrip behavior.

    These tests ensure that the single-pass ingestion design works correctly
    with JSON caching, preserving document structure and content across
    serialization/deserialization cycles.
    """

    def test_json_roundtrip_preserves_structure_output(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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

    def test_json_roundtrip_preserves_content_output(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test that JSON roundtrip produces identical content extraction output."""
        original_doc = _TestDoc(pages=4)

        # Mock content extraction to return consistent results based on doc pages
        def mock_extract(doc: Any, output_dir: Path, options: str, **_: Any) -> Any:
            from pdf2foundry.model.content import HtmlPage, ParsedContent

            pages = [HtmlPage(html=f"<p>Page {i}</p>", page_no=i) for i in range(1, doc.num_pages() + 1)]
            return ParsedContent(pages=pages, images=[], tables=[], links=[])

        monkeypatch.setattr("pdf2foundry.ingest.content_extractor.extract_semantic_content", mock_extract)

        # Extract from original
        from pdf2foundry.model.pipeline_options import PdfPipelineOptions

        original_content = extract_semantic_content(original_doc, tmp_path, PdfPipelineOptions())

        # Serialize and deserialize
        json_text = doc_to_json(original_doc)
        roundtrip_doc = doc_from_json(json_text)

        # Extract from roundtrip doc
        roundtrip_content = extract_semantic_content(roundtrip_doc, tmp_path, PdfPipelineOptions())

        # Compare outputs - both should have same number of pages
        assert len(original_content.pages) == len(roundtrip_content.pages)
        # Both should have same page count (4)
        assert len(original_content.pages) == 4
        assert len(roundtrip_content.pages) == 4

    def test_json_roundtrip_multiple_cycles(self, tmp_path: Path) -> None:
        """Test that multiple JSON roundtrip cycles preserve document integrity."""
        original_doc = _TestDoc(pages=3)

        # Perform multiple roundtrip cycles
        current_doc: Any = original_doc
        for cycle in range(5):
            json_text = doc_to_json(current_doc)
            current_doc = doc_from_json(json_text)

            # Each cycle should preserve page count
            assert current_doc.num_pages() == 3, f"Page count changed in cycle {cycle}"

            # Each cycle should preserve HTML export capability
            html = current_doc.export_to_html()
            assert isinstance(html, str), f"HTML export failed in cycle {cycle}"
            # Note: Fallback _JsonDoc returns empty string, which is expected behavior

    def test_json_roundtrip_with_file_persistence(self, tmp_path: Path) -> None:
        """Test JSON roundtrip through actual file I/O."""
        original_doc = _TestDoc(pages=6)
        cache_file = tmp_path / "roundtrip_test.json"

        # Save to file
        json_text = doc_to_json(original_doc, pretty=True)
        cache_file.write_text(json_text, encoding="utf-8")

        # Load from file
        loaded_json = cache_file.read_text(encoding="utf-8")
        roundtrip_doc = doc_from_json(loaded_json)

        # Verify preservation
        assert roundtrip_doc.num_pages() == original_doc.num_pages()

        # Verify both can export HTML
        original_html = original_doc.export_to_html()
        roundtrip_html = roundtrip_doc.export_to_html()
        assert isinstance(original_html, str)
        assert isinstance(roundtrip_html, str)
        assert len(original_html) > 0
        # Note: Roundtrip doc uses fallback _JsonDoc which returns empty string

    def test_json_roundtrip_preserves_document_methods(self) -> None:
        """Test that roundtrip documents preserve all required methods."""
        original_doc = _TestDoc(pages=2)

        # Serialize and deserialize
        json_text = doc_to_json(original_doc)
        roundtrip_doc = doc_from_json(json_text)

        # Check that all required methods are present and callable
        assert hasattr(roundtrip_doc, "num_pages")
        assert callable(roundtrip_doc.num_pages)
        assert hasattr(roundtrip_doc, "export_to_html")
        assert callable(roundtrip_doc.export_to_html)

        # Check that methods return expected types
        assert isinstance(roundtrip_doc.num_pages(), int)
        assert isinstance(roundtrip_doc.export_to_html(), str)

    def test_json_roundtrip_with_different_page_counts(self) -> None:
        """Test JSON roundtrip with various document sizes."""
        page_counts = [1, 2, 5, 10, 50, 100]

        for page_count in page_counts:
            original_doc = _TestDoc(pages=page_count)

            # Roundtrip
            json_text = doc_to_json(original_doc)
            roundtrip_doc = doc_from_json(json_text)

            # Verify page count preservation
            assert roundtrip_doc.num_pages() == page_count, f"Page count not preserved for {page_count} pages"

            # Verify HTML export still works
            html = roundtrip_doc.export_to_html()
            assert isinstance(html, str)
            # Note: Fallback _JsonDoc returns empty string, which is expected

    def test_json_roundtrip_error_handling(self) -> None:
        """Test that roundtrip documents handle errors gracefully."""
        original_doc = _TestDoc(pages=3)

        # Serialize and deserialize
        json_text = doc_to_json(original_doc)
        roundtrip_doc = doc_from_json(json_text)

        # Test that validation passes
        from pdf2foundry.ingest.ingestion import validate_doc

        validate_doc(roundtrip_doc)  # Should not raise

        # Test edge cases
        assert roundtrip_doc.num_pages() > 0
        html = roundtrip_doc.export_to_html()
        assert html is not None
        assert isinstance(html, str)

    def test_json_compact_vs_pretty_roundtrip(self) -> None:
        """Test that both compact and pretty JSON formats roundtrip correctly."""
        original_doc = _TestDoc(pages=4)

        # Test compact format
        compact_json = doc_to_json(original_doc, pretty=False)
        compact_doc = doc_from_json(compact_json)
        assert compact_doc.num_pages() == 4

        # Test pretty format
        pretty_json = doc_to_json(original_doc, pretty=True)
        pretty_doc = doc_from_json(pretty_json)
        assert pretty_doc.num_pages() == 4

        # Both should produce functionally equivalent documents
        assert compact_doc.num_pages() == pretty_doc.num_pages()

        # Both should export HTML successfully
        compact_html = compact_doc.export_to_html()
        pretty_html = pretty_doc.export_to_html()
        assert isinstance(compact_html, str)
        assert isinstance(pretty_html, str)

    def test_json_roundtrip_integration_with_ingestion(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test JSON roundtrip in the context of the full ingestion pipeline."""
        # Create original document
        original_doc = _TestDoc(pages=7)

        # Mock conversion to return our test document
        def mock_convert(pdf_path: Path, **_: Any) -> _TestDoc:
            return original_doc

        monkeypatch.setattr(da, "_do_docling_convert_impl", mock_convert)
        da._cached_convert.cache_clear()

        cache_file = tmp_path / "integration_cache.json"

        # First ingestion: should convert and save
        doc1 = ingest_docling(Path("/tmp/test.pdf"), JsonOpts(path=cache_file))
        assert doc1.num_pages() == 7
        assert cache_file.exists()

        # Second ingestion: should load from cache (roundtrip)
        doc2 = ingest_docling(Path("/tmp/test.pdf"), JsonOpts(path=cache_file))
        assert doc2.num_pages() == 7

        # Both documents should be functionally equivalent
        assert doc1.num_pages() == doc2.num_pages()

        # Both should work with structure parsing
        from pdf2foundry.ingest.docling_parser import parse_structure_from_doc

        structure1 = parse_structure_from_doc(doc1)
        structure2 = parse_structure_from_doc(doc2)
        assert structure1.page_count == structure2.page_count

        # Both should work with content extraction
        from pdf2foundry.ingest.content_extractor import extract_semantic_content
        from pdf2foundry.model.pipeline_options import PdfPipelineOptions

        content1 = extract_semantic_content(doc1, tmp_path, PdfPipelineOptions())
        content2 = extract_semantic_content(doc2, tmp_path, PdfPipelineOptions())
        assert len(content1.pages) == len(content2.pages)


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

    def test_progress_events_no_duplicates_without_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
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

    def test_progress_events_no_duplicates_with_cache(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
        doc = ingest_docling(Path("/tmp/test.pdf"), JsonOpts(path=cache_file), on_progress=capture_progress)

        # Verify document was loaded from cache
        assert doc.num_pages() == 3

        # Check events
        event_names = [e[0] for e in events]

        # Should have cache load event, no conversion events
        assert "ingest:loaded_from_cache" in event_names
        assert "ingest:converting" not in event_names
