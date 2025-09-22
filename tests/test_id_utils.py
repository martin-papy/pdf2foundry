"""Tests for deterministic ID generation utilities.

These tests ensure that PDF2Foundry generates stable, deterministic UUIDs
for Journal Entries and Pages that remain consistent across runs, enabling
reliable cross-references and stable @UUID links in Foundry VTT.
"""

from __future__ import annotations

from pdf2foundry.model.id_utils import make_entry_id, make_page_id, sha1_16_hex


class TestSha1_16_Hex:
    """Test the core SHA1-based ID generation function."""

    def test_deterministic_output(self) -> None:
        """Test that identical inputs always produce identical outputs."""
        input_text = "test-input-string"
        result1 = sha1_16_hex(input_text)
        result2 = sha1_16_hex(input_text)

        assert result1 == result2, "SHA1 hash should be deterministic"

    def test_output_format(self) -> None:
        """Test that output is exactly 16 lowercase hex characters."""
        result = sha1_16_hex("abc")

        assert len(result) == 16, "Output should be exactly 16 characters"
        assert all(c in "0123456789abcdef" for c in result), "Output should be lowercase hex"
        assert result.islower(), "Output should be lowercase"

    def test_different_inputs_different_outputs(self) -> None:
        """Test that different inputs produce different outputs."""
        result1 = sha1_16_hex("input1")
        result2 = sha1_16_hex("input2")
        result3 = sha1_16_hex("input1 ")  # Note the trailing space

        assert result1 != result2, "Different inputs should produce different hashes"
        assert result1 != result3, "Even small differences should produce different hashes"

    def test_unicode_handling(self) -> None:
        """Test that Unicode characters are handled consistently."""
        unicode_inputs = ["café", "测试", "🎮", "Ñoño"]

        for text in unicode_inputs:
            result1 = sha1_16_hex(text)
            result2 = sha1_16_hex(text)
            assert result1 == result2, f"Unicode text '{text}' should hash consistently"
            assert len(result1) == 16, f"Unicode text '{text}' should produce 16-char hash"

    def test_known_values(self) -> None:
        """Test against known SHA1 values for regression testing."""
        # These are the first 16 chars of known SHA1 hashes
        test_cases = [
            ("abc", "a9993e364706816a"),  # SHA1 of "abc" starts with this
            ("", "da39a3ee5e6b4b0d"),  # SHA1 of empty string starts with this
            ("test", "a94a8fe5ccb19ba6"),  # SHA1 of "test" starts with this
        ]

        for input_text, expected in test_cases:
            result = sha1_16_hex(input_text)
            assert result == expected, f"SHA1 of '{input_text}' should start with {expected}"


class TestMakeEntryId:
    """Test Journal Entry ID generation."""

    def test_deterministic_entry_ids(self) -> None:
        """Test that entry IDs are deterministic across calls."""
        mod_id = "test-module"
        path = ["chapter-1", "section-a"]

        id1 = make_entry_id(mod_id, path)
        id2 = make_entry_id(mod_id, path)

        assert id1 == id2, "Entry IDs should be deterministic"
        assert len(id1) == 16, "Entry ID should be 16 characters"

    def test_different_modules_different_ids(self) -> None:
        """Test that different module IDs produce different entry IDs."""
        path = ["chapter-1"]

        id1 = make_entry_id("module-a", path)
        id2 = make_entry_id("module-b", path)

        assert id1 != id2, "Different modules should produce different entry IDs"

    def test_different_paths_different_ids(self) -> None:
        """Test that different canonical paths produce different entry IDs."""
        mod_id = "test-module"

        id1 = make_entry_id(mod_id, ["chapter-1"])
        id2 = make_entry_id(mod_id, ["chapter-2"])
        id3 = make_entry_id(mod_id, ["chapter-1", "section-a"])

        assert id1 != id2, "Different chapter paths should produce different IDs"
        assert id1 != id3, "Different path depths should produce different IDs"
        assert id2 != id3, "All different paths should produce unique IDs"

    def test_path_order_matters(self) -> None:
        """Test that path order affects the generated ID."""
        mod_id = "test-module"

        id1 = make_entry_id(mod_id, ["a", "b"])
        id2 = make_entry_id(mod_id, ["b", "a"])

        assert id1 != id2, "Path order should affect entry ID generation"

    def test_special_characters_in_paths(self) -> None:
        """Test handling of special characters in canonical paths."""
        mod_id = "test-module"
        special_paths = [
            ["chapter with spaces"],
            ["chapter-with-hyphens"],
            ["chapter_with_underscores"],
            ["chapter.with.dots"],
            ["chapter|with|pipes"],  # This uses the separator character
        ]

        ids = []
        for path in special_paths:
            entry_id = make_entry_id(mod_id, path)
            assert len(entry_id) == 16, f"Path {path} should produce valid ID"
            ids.append(entry_id)

        # All IDs should be unique
        assert len(set(ids)) == len(ids), "All special character paths should produce unique IDs"


class TestMakePageId:
    """Test Journal Entry Page ID generation."""

    def test_deterministic_page_ids(self) -> None:
        """Test that page IDs are deterministic across calls."""
        mod_id = "test-module"
        entry_path = ["chapter-1"]
        page_name = "Overview"

        id1 = make_page_id(mod_id, entry_path, page_name)
        id2 = make_page_id(mod_id, entry_path, page_name)

        assert id1 == id2, "Page IDs should be deterministic"
        assert len(id1) == 16, "Page ID should be 16 characters"

    def test_different_page_names_different_ids(self) -> None:
        """Test that different page names produce different IDs."""
        mod_id = "test-module"
        entry_path = ["chapter-1"]

        id1 = make_page_id(mod_id, entry_path, "Overview")
        id2 = make_page_id(mod_id, entry_path, "Details")
        id3 = make_page_id(mod_id, entry_path, "Summary")

        assert id1 != id2, "Different page names should produce different IDs"
        assert id1 != id3, "All page names should produce unique IDs"
        assert id2 != id3, "All page names should produce unique IDs"

    def test_page_vs_entry_id_uniqueness(self) -> None:
        """Test that page IDs don't collide with entry IDs."""
        mod_id = "test-module"
        path = ["chapter-1"]

        entry_id = make_entry_id(mod_id, path)
        page_id = make_page_id(mod_id, path, "some-page")

        assert entry_id != page_id, "Entry and page IDs should never collide"

    def test_foundry_uuid_compatibility(self) -> None:
        """Test that generated IDs are compatible with Foundry @UUID format."""
        mod_id = "test-module"
        entry_path = ["chapter-1"]
        page_name = "overview"

        entry_id = make_entry_id(mod_id, entry_path)
        page_id = make_page_id(mod_id, entry_path, page_name)

        # Foundry UUIDs should be valid hex strings
        assert all(c in "0123456789abcdef" for c in entry_id), "Entry ID should be valid hex"
        assert all(c in "0123456789abcdef" for c in page_id), "Page ID should be valid hex"

        # Test that they can be used in @UUID format
        entry_uuid = f"@UUID[JournalEntry.{entry_id}]"
        page_uuid = f"@UUID[JournalEntry.{entry_id}.JournalEntryPage.{page_id}]"

        assert entry_uuid.count(".") == 1, "Entry UUID should have correct format"
        assert page_uuid.count(".") == 3, "Page UUID should have correct format"
