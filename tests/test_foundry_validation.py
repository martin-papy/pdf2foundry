"""Tests for Foundry VTT JSON schema validation.

These tests ensure that PDF2Foundry generates valid Foundry VTT Journal Entry
and module.json structures that comply with Foundry v13 specifications.
"""

from __future__ import annotations

import pytest

from pdf2foundry.builder.ir_builder import build_document_ir, map_ir_to_foundry_entries
from pdf2foundry.builder.manifest import build_module_manifest, validate_module_manifest
from pdf2foundry.model.content import HtmlPage, ParsedContent
from pdf2foundry.model.document import OutlineNode, ParsedDocument
from pdf2foundry.model.foundry import (
    JournalPageText,
    make_journal_entry,
    make_text_page,
    validate_entry,
)
from pdf2foundry.model.id_utils import make_entry_id, make_page_id


class TestJournalEntryValidation:
    """Test validation of Journal Entry structures."""

    def test_validate_entry_basic_valid(self) -> None:
        """Test validation passes for a properly structured entry."""
        section = OutlineNode(title="Overview", level=2, page_start=1, page_end=1, children=[], path=["ch", "ov"])
        chapter = OutlineNode(title="Chapter", level=1, page_start=1, page_end=1, children=[section], path=["ch"])
        parsed_doc = ParsedDocument(page_count=1, outline=[chapter])
        pages = [HtmlPage(html="<p>x</p>", page_no=1)]
        ir = build_document_ir(parsed_doc, ParsedContent(pages=pages), mod_id="m", doc_title="D")
        entries = map_ir_to_foundry_entries(ir)

        assert entries
        validate_entry(entries[0])  # Should not raise

    def test_validate_entry_missing_id(self) -> None:
        """Test validation fails when entry ID is missing or empty."""
        mod_id = "test-mod"
        entry_path = ["chapter"]
        page_id = make_page_id(mod_id, entry_path, "content")
        page = make_text_page(page_id, "Content", level=1, text_html="<p>Content</p>", sort=100)

        # Create entry with empty ID
        entry = make_journal_entry(_id="", name="Chapter", pages=[page])

        with pytest.raises(AssertionError):
            validate_entry(entry)

    def test_validate_entry_invalid_text_format(self) -> None:
        """Test validation fails when page text format is not 1 (HTML)."""
        mod_id = "test-mod"
        entry_path = ["chapter"]
        page_id = make_page_id(mod_id, entry_path, "content")

        # JournalPageText enforces format=1 in __post_init__, so this should raise ValueError
        with pytest.raises(ValueError, match="text.format must be 1"):
            JournalPageText(
                _id=page_id,
                name="Content",
                title={"show": True, "level": 1},
                text={"format": 0, "content": "<p>Content</p>"},  # Wrong format - should be 1
                sort=100,
                flags={},
            )

    def test_validate_entry_invalid_title_show(self) -> None:
        """Test validation fails when page title show is not True."""
        mod_id = "test-mod"
        entry_path = ["chapter"]
        page_id = make_page_id(mod_id, entry_path, "content")

        # JournalPageText enforces title.show=True in __post_init__
        with pytest.raises(ValueError, match="title.show must be True"):
            JournalPageText(
                _id=page_id,
                name="Content",
                title={"show": False, "level": 1},  # Wrong - should be True
                text={"format": 1, "content": "<p>Content</p>"},
                sort=100,
                flags={},
            )

    def test_validate_entry_invalid_title_level(self) -> None:
        """Test validation fails when page title level is invalid."""
        mod_id = "test-mod"
        entry_path = ["chapter"]
        page_id = make_page_id(mod_id, entry_path, "content")

        invalid_levels = [0, -1]

        for level in invalid_levels:
            with pytest.raises(ValueError, match="title.level must be >= 1"):
                JournalPageText(
                    _id=page_id,
                    name="Content",
                    title={"show": True, "level": level},  # Invalid level
                    text={"format": 1, "content": "<p>Content</p>"},
                    sort=100,
                    flags={},
                )

        # Test with non-integer level separately
        with pytest.raises((ValueError, TypeError)):
            JournalPageText(
                _id=page_id,
                name="Content",
                title={"show": True, "level": "not_an_int"},  # type: ignore
                text={"format": 1, "content": "<p>Content</p>"},
                sort=100,
                flags={},
            )

    def test_validate_entry_valid_title_levels(self) -> None:
        """Test validation passes for all valid title levels (1, 2, 3)."""
        mod_id = "test-mod"
        entry_path = ["chapter"]
        entry_id = make_entry_id(mod_id, entry_path)

        valid_levels = [1, 2, 3]

        for level in valid_levels:
            page_id = make_page_id(mod_id, entry_path, f"content-{level}")
            page = make_text_page(page_id, f"Content {level}", level=level, text_html="<p>Content</p>", sort=100)
            entry = make_journal_entry(_id=entry_id, name="Chapter", pages=[page])

            validate_entry(entry)  # Should not raise


class TestModuleManifestValidation:
    """Test validation of module.json manifest structures."""

    def test_build_and_validate_minimal_manifest(self) -> None:
        """Test building and validating a minimal valid manifest."""
        manifest = build_module_manifest(
            mod_id="test-module",
            mod_title="Test Module",
            pack_name="test-journals",
            version="1.0.0",
        )

        issues = validate_module_manifest(manifest)
        assert issues == [], f"Valid manifest should have no issues: {issues}"

    def test_validate_manifest_missing_required_fields(self) -> None:
        """Test validation detects all missing required fields."""
        empty_manifest: dict[str, object] = {}
        issues = validate_module_manifest(empty_manifest)

        required_fields = ["id", "title", "version", "compatibility", "packs", "styles"]
        for field in required_fields:
            assert any(
                f"Missing required field: {field}" in issue for issue in issues
            ), f"Should detect missing field: {field}"

    def test_validate_manifest_wrong_field_types(self) -> None:
        """Test validation detects incorrect field types."""
        bad_manifest = {
            "id": 123,  # Should be string
            "title": ["not", "a", "string"],  # Should be string
            "version": 1.0,  # Should be string
            "compatibility": "not a dict",  # Should be dict
            "packs": "not a list",  # Should be list
            "styles": {"not": "a list"},  # Should be list
        }

        issues = validate_module_manifest(bad_manifest)

        type_errors = [
            ("id", "str"),
            ("title", "str"),
            ("version", "str"),
            ("compatibility", "dict"),
            ("packs", "list"),
            ("styles", "list"),
        ]

        for field, expected_type in type_errors:
            assert any(
                f"Field '{field}' must be {expected_type}" in issue for issue in issues
            ), f"Should detect wrong type for field: {field}"

    def test_validate_manifest_compatibility_version_too_low(self) -> None:
        """Test validation detects compatibility version below v13."""
        manifest = {
            "id": "test",
            "title": "Test",
            "version": "1.0.0",
            "compatibility": {"minimum": "12"},  # Too low
            "packs": [{"type": "JournalEntry", "name": "test", "path": "packs/test"}],
            "styles": ["styles/test.css"],
        }

        issues = validate_module_manifest(manifest)
        assert any("compatibility.minimum must be '13' or higher" in issue for issue in issues)

    def test_validate_manifest_wrong_pack_type(self) -> None:
        """Test validation detects non-JournalEntry pack type."""
        manifest = {
            "id": "test",
            "title": "Test",
            "version": "1.0.0",
            "compatibility": {"minimum": "13"},
            "packs": [{"type": "Actor", "name": "test", "path": "packs/test"}],  # Wrong type
            "styles": ["styles/test.css"],
        }

        issues = validate_module_manifest(manifest)
        assert any("first pack must have type 'JournalEntry'" in issue for issue in issues)
