"""Tests for Table of Contents (TOC) linking functionality.

These tests ensure that PDF2Foundry correctly generates TOC entries with
proper @UUID links that reference Journal Entries and Pages, enabling
navigation within Foundry VTT modules.
"""

from __future__ import annotations

from pdf2foundry.builder.toc import (
    build_toc_entry_from_entries,
    build_uuid_link,
    collect_toc_metadata,
    extract_uuid_targets_from_html,
    validate_toc_links,
)
from pdf2foundry.model.foundry import make_journal_entry, make_text_page
from pdf2foundry.model.id_utils import make_entry_id, make_page_id


def test_collect_toc_metadata_orders_pages_and_preserves_ids() -> None:
    mod_id = "mod"
    entry_path = ["book", "chapter-1"]
    entry_id = make_entry_id(mod_id, entry_path)
    page1_id = make_page_id(mod_id, entry_path, "Overview")
    page2_id = make_page_id(mod_id, entry_path, "Usage")

    p2 = make_text_page(page2_id, "Usage", level=1, text_html="<div>Usage</div>", sort=200)
    p1 = make_text_page(page1_id, "Overview", level=1, text_html="<div>Overview</div>", sort=100)
    entry = make_journal_entry(_id=entry_id, name="Chapter 1 — Introduction", pages=[p2, p1])

    toc = collect_toc_metadata([entry])
    assert len(toc) == 1
    e = toc[0]
    assert e.entry_id == entry_id
    assert e.entry_name == "Chapter 1 — Introduction"

    # Sorted by `sort` ascending
    assert [p.page_id for p in e.pages] == [page1_id, page2_id]
    assert [p.label for p in e.pages] == ["Overview", "Usage"]


def test_build_uuid_link_formatting() -> None:
    mod_id = "mod"
    entry_path = ["book", "chapter-1"]
    entry_id = make_entry_id(mod_id, entry_path)
    page_id = make_page_id(mod_id, entry_path, "Overview")

    link = build_uuid_link(entry_id, page_id, "Overview")
    assert link == f"@UUID[JournalEntry.{entry_id}.JournalEntryPage.{page_id}]{{Overview}}"


def test_collect_toc_metadata_handles_entry_without_pages() -> None:
    entry = make_journal_entry(_id="deadbeefdeadbeef", name="Empty", pages=[])
    toc = collect_toc_metadata([entry])
    assert len(toc) == 1
    assert toc[0].entry_id == "deadbeefdeadbeef"
    assert toc[0].entry_name == "Empty"
    assert toc[0].pages == []


def test_build_toc_entry_from_entries_sets_flags_and_renders_links() -> None:
    mod_id = "mod"
    ch_path = ["book", "chapter-1"]
    ch_id = make_entry_id(mod_id, ch_path)
    p1_id = make_page_id(mod_id, ch_path, "Overview")
    p2_id = make_page_id(mod_id, ch_path, "Usage")

    p1 = make_text_page(p1_id, "Overview", level=1, text_html="<div>Overview</div>", sort=100)
    p2 = make_text_page(p2_id, "Usage", level=1, text_html="<div>Usage</div>", sort=200)
    ch = make_journal_entry(_id=ch_id, name="Chapter 1 — Introduction", pages=[p2, p1])

    toc_entry = build_toc_entry_from_entries(mod_id, [ch], title="Table of Contents", folder_path=["My Book"])

    # Deterministic IDs for TOC entry and its page
    expected_entry_id = make_entry_id(mod_id, ["toc"])
    expected_page_id = make_page_id(mod_id, ["toc"], "Table of Contents")
    assert toc_entry._id == expected_entry_id
    assert len(toc_entry.pages) == 1
    assert toc_entry.pages[0]._id == expected_page_id

    # Canonical metadata present (v13 doesn't require compendium-folders dependency)
    mod_ns = toc_entry.flags.get(mod_id)
    assert isinstance(mod_ns, dict)
    assert mod_ns.get("canonicalPath") == ["toc"]
    assert mod_ns.get("canonicalPathStr") == "toc"
    assert mod_ns.get("nameSlug") == "toc"

    # Page flags contain canonical path info
    p_ns = toc_entry.pages[0].flags.get(mod_id)
    assert isinstance(p_ns, dict)
    assert p_ns.get("canonicalPath") == ["toc", "Table of Contents"]
    assert p_ns.get("canonicalPathStr") == "toc/Table of Contents"
    assert p_ns.get("sectionOrder") == 0

    # Rendered content contains @UUID links for underlying chapter pages
    content_val = toc_entry.pages[0].text["content"]
    html = str(content_val)
    pat1 = f"@UUID[JournalEntry.{ch_id}.JournalEntryPage.{p1_id}]{{Overview}}"
    pat2 = f"@UUID[JournalEntry.{ch_id}.JournalEntryPage.{p2_id}]{{Usage}}"
    assert pat1 in html
    assert pat2 in html


def test_extract_uuid_targets_from_html() -> None:
    html = (
        "<div>"
        "@UUID[JournalEntry.aaaa1111bbbb2222.JournalEntryPage.cccc3333dddd4444]{One}"
        " and "
        "@UUID[JournalEntry.eeee5555ffff6666.JournalEntryPage.7777aaaa8888bbbb]{Two}"
        "</div>"
    )
    targets = extract_uuid_targets_from_html(html)
    assert targets == [
        ("aaaa1111bbbb2222", "cccc3333dddd4444", "One"),
        ("eeee5555ffff6666", "7777aaaa8888bbbb", "Two"),
    ]


def test_validate_toc_links_reports_missing_targets() -> None:
    # Build TOC for an entry with a single valid page
    mod_id = "mod"
    ch_path = ["book", "chapter-1"]
    ch_id = make_entry_id(mod_id, ch_path)
    p_id = make_page_id(mod_id, ch_path, "Overview")
    p = make_text_page(p_id, "Overview", level=1, text_html="<div>Overview</div>", sort=100)
    ch = make_journal_entry(_id=ch_id, name="Ch", pages=[p])

    toc_entry = build_toc_entry_from_entries(mod_id, [ch])
    # Corrupt the HTML to include a bad entry and bad page
    bad_html = str(toc_entry.pages[0].text["content"]) + " "
    bad_html += f"@UUID[JournalEntry.BADENTRY.JournalEntryPage.{p_id}]{{Bad Entry}}"
    bad_html += " "
    bad_html += f"@UUID[JournalEntry.{ch_id}.JournalEntryPage.BADPAGE]{{Bad Page}}"
    toc_entry.pages[0].text["content"] = bad_html

    issues = validate_toc_links(toc_entry, [ch])
    assert any("missing entry" in msg for msg in issues)
    assert any("missing page" in msg for msg in issues)


class TestTocLinkingEdgeCases:
    """Test edge cases and error conditions for TOC linking."""

    def test_empty_entries_list(self) -> None:
        """Test TOC generation with empty entries list."""
        toc_metadata = collect_toc_metadata([])
        assert toc_metadata == []

        # Building TOC from empty list should still work
        toc_entry = build_toc_entry_from_entries("test-mod", [])
        assert toc_entry.name == "Table of Contents"
        assert len(toc_entry.pages) == 1
        # Should contain empty or minimal content
        content = str(toc_entry.pages[0].text["content"])
        assert "Table of Contents" in content

    def test_entries_with_no_pages(self) -> None:
        """Test TOC generation with entries that have no pages."""
        mod_id = "test-mod"
        entry_id = make_entry_id(mod_id, ["empty-chapter"])
        empty_entry = make_journal_entry(_id=entry_id, name="Empty Chapter", pages=[])

        toc_metadata = collect_toc_metadata([empty_entry])
        assert len(toc_metadata) == 1
        assert toc_metadata[0].entry_id == entry_id
        assert toc_metadata[0].entry_name == "Empty Chapter"
        assert toc_metadata[0].pages == []

        # TOC should still be buildable
        toc_entry = build_toc_entry_from_entries(mod_id, [empty_entry])
        assert toc_entry.name == "Table of Contents"

    def test_mixed_entries_some_empty_some_with_pages(self) -> None:
        """Test TOC with mix of empty and populated entries."""
        mod_id = "test-mod"

        # Empty entry
        empty_id = make_entry_id(mod_id, ["empty"])
        empty_entry = make_journal_entry(_id=empty_id, name="Empty", pages=[])

        # Entry with pages
        full_path = ["full-chapter"]
        full_id = make_entry_id(mod_id, full_path)
        page_id = make_page_id(mod_id, full_path, "Content")
        page = make_text_page(page_id, "Content", level=1, text_html="<p>Content</p>", sort=100)
        full_entry = make_journal_entry(_id=full_id, name="Full Chapter", pages=[page])

        toc_metadata = collect_toc_metadata([empty_entry, full_entry])
        assert len(toc_metadata) == 2
        assert toc_metadata[0].pages == []  # Empty entry
        assert len(toc_metadata[1].pages) == 1  # Full entry

    def test_large_number_of_entries_and_pages(self) -> None:
        """Test TOC generation with many entries and pages."""
        mod_id = "large-mod"
        entries = []

        # Create 50 entries with 5 pages each
        for i in range(50):
            entry_path = [f"chapter-{i:02d}"]
            entry_id = make_entry_id(mod_id, entry_path)
            pages = []

            for j in range(5):
                page_id = make_page_id(mod_id, entry_path, f"section-{j}")
                page = make_text_page(page_id, f"Section {j}", level=1, text_html=f"<p>Content {j}</p>", sort=j * 100)
                pages.append(page)

            entry = make_journal_entry(_id=entry_id, name=f"Chapter {i}", pages=pages)
            entries.append(entry)

        toc_metadata = collect_toc_metadata(entries)
        assert len(toc_metadata) == 50
        assert all(len(entry_ref.pages) == 5 for entry_ref in toc_metadata)

        # TOC should still be buildable (though large)
        toc_entry = build_toc_entry_from_entries(mod_id, entries)
        assert toc_entry.name == "Table of Contents"
        content = str(toc_entry.pages[0].text["content"])
        assert "Chapter 0" in content
        assert "Chapter 49" in content

    def test_unicode_in_entry_and_page_names(self) -> None:
        """Test TOC with Unicode characters in names."""
        mod_id = "unicode-mod"
        unicode_names = [
            ("Café Chapter", "Café Overview"),
            ("测试章节", "测试页面"),
            ("🎮 Gaming", "🎮 Rules"),
            ("Ñoño's Guide", "Ñoño's Tips"),
        ]

        entries = []
        for i, (entry_name, page_name) in enumerate(unicode_names):
            entry_path = [f"chapter-{i}"]
            entry_id = make_entry_id(mod_id, entry_path)
            page_id = make_page_id(mod_id, entry_path, page_name)
            page = make_text_page(page_id, page_name, level=1, text_html="<p>Content</p>", sort=100)
            entry = make_journal_entry(_id=entry_id, name=entry_name, pages=[page])
            entries.append(entry)

        toc_metadata = collect_toc_metadata(entries)
        assert len(toc_metadata) == 4

        # Check that Unicode names are preserved
        assert toc_metadata[0].entry_name == "Café Chapter"
        assert toc_metadata[0].pages[0].label == "Café Overview"
        assert toc_metadata[1].entry_name == "测试章节"
        assert toc_metadata[1].pages[0].label == "测试页面"

        # TOC should build correctly with Unicode
        toc_entry = build_toc_entry_from_entries(mod_id, entries)
        content = str(toc_entry.pages[0].text["content"])
        assert "Café Chapter" in content
        assert "测试章节" in content
        assert "🎮 Gaming" in content

    def test_page_sorting_with_various_sort_values(self) -> None:
        """Test that pages are correctly sorted by their sort values."""
        mod_id = "sort-test"
        entry_path = ["chapter"]
        entry_id = make_entry_id(mod_id, entry_path)

        # Create pages with various sort values (including negative, zero, large)
        sort_values = [1000, -100, 0, 500, 999999, 1, -1]
        pages = []

        for i, sort_val in enumerate(sort_values):
            page_id = make_page_id(mod_id, entry_path, f"page-{i}")
            page = make_text_page(
                page_id,
                f"Page {i} (sort={sort_val})",
                level=1,
                text_html=f"<p>Page {i}</p>",
                sort=sort_val,
            )
            pages.append(page)

        entry = make_journal_entry(_id=entry_id, name="Sort Test", pages=pages)
        toc_metadata = collect_toc_metadata([entry])

        # Pages should be sorted by sort value ascending
        expected_order = sorted(range(len(sort_values)), key=lambda i: sort_values[i])
        actual_labels = [page.label for page in toc_metadata[0].pages]
        expected_labels = [f"Page {i} (sort={sort_values[i]})" for i in expected_order]

        assert actual_labels == expected_labels

    def test_custom_toc_title_and_folder_path(self) -> None:
        """Test TOC generation with custom title and folder path."""
        mod_id = "custom-mod"
        entry_path = ["chapter"]
        entry_id = make_entry_id(mod_id, entry_path)
        page_id = make_page_id(mod_id, entry_path, "content")
        page = make_text_page(page_id, "Content", level=1, text_html="<p>Content</p>", sort=100)
        entry = make_journal_entry(_id=entry_id, name="Chapter", pages=[page])

        # Custom title and folder path
        custom_title = "Custom Table of Contents"
        folder_path = ["My Book", "Navigation"]

        toc_entry = build_toc_entry_from_entries(mod_id, [entry], title=custom_title, folder_path=folder_path)

        assert toc_entry.name == custom_title
        assert toc_entry.pages[0].name == custom_title

        # Check folder flags
        assert "compendium-folders" in toc_entry.flags
        folder_flags = toc_entry.flags["compendium-folders"]
        assert isinstance(folder_flags, dict)
        assert folder_flags.get("folderPath") == folder_path


class TestUuidLinkGeneration:
    """Test @UUID link generation and parsing."""

    def test_build_uuid_link_format(self) -> None:
        """Test that UUID links are formatted correctly."""
        entry_id = "1234567890abcdef"
        page_id = "fedcba0987654321"
        label = "Test Page"

        link = build_uuid_link(entry_id, page_id, label)
        expected = f"@UUID[JournalEntry.{entry_id}.JournalEntryPage.{page_id}]{{Test Page}}"
        assert link == expected

    def test_build_uuid_link_with_special_characters(self) -> None:
        """Test UUID link generation with special characters in labels."""
        entry_id = "1234567890abcdef"
        page_id = "fedcba0987654321"

        special_labels = [
            "Page with spaces",
            "Page-with-hyphens",
            "Page_with_underscores",
            "Page.with.dots",
            "Page [with] brackets",
            "Page {with} braces",
            "Page (with) parentheses",
            "Page & symbols!",
            "Café & 测试",
        ]

        for label in special_labels:
            link = build_uuid_link(entry_id, page_id, label)
            assert link.startswith(f"@UUID[JournalEntry.{entry_id}.JournalEntryPage.{page_id}]{{")
            assert link.endswith("}")
            assert label in link

    def test_extract_uuid_targets_complex_html(self) -> None:
        """Test UUID target extraction from complex HTML."""
        html = """
        <div class="toc">
            <h1>Table of Contents</h1>
            <ul>
                <li>@UUID[JournalEntry.aaaa1111bbbb2222.JournalEntryPage.cccc3333dddd4444]{Chapter 1}</li>
                <li>@UUID[JournalEntry.eeee5555ffff6666.JournalEntryPage.7777aaaa8888bbbb]{Chapter 2: Advanced Topics}</li>
                <li>Some text without UUID</li>
                <li>@UUID[JournalEntry.1111222233334444.JournalEntryPage.5555666677778888]{Appendix A & B}</li>
            </ul>
            <p>Footer text with @UUID[JournalEntry.9999aaaabbbbcccc.JournalEntryPage.ddddeeeeffffaaaa]{Index}</p>
        </div>
        """

        targets = extract_uuid_targets_from_html(html)
        expected = [
            ("aaaa1111bbbb2222", "cccc3333dddd4444", "Chapter 1"),
            ("eeee5555ffff6666", "7777aaaa8888bbbb", "Chapter 2: Advanced Topics"),
            ("1111222233334444", "5555666677778888", "Appendix A & B"),
            ("9999aaaabbbbcccc", "ddddeeeeffffaaaa", "Index"),
        ]
        assert targets == expected

    def test_extract_uuid_targets_malformed_links(self) -> None:
        """Test UUID extraction handles malformed links gracefully."""
        html = """
        <div>
            @UUID[JournalEntry.aaaa1111bbbb2222.JournalEntryPage.cccc3333dddd4444]{Valid Link}
            @UUID[JournalEntry.invalid]{Missing Page ID}
            @UUID[JournalEntry.]{Empty IDs}
            @UUID[]{Completely Empty}
            @UUID[JournalEntry.aaaa1111bbbb2222.JournalEntryPage.cccc3333dddd4444]
            @UUID[JournalEntry.aaaa1111bbbb2222.JournalEntryPage.cccc3333dddd4444]{Valid Link 2}
        </div>
        """

        targets = extract_uuid_targets_from_html(html)
        # Should only extract valid, complete UUID links
        expected = [
            ("aaaa1111bbbb2222", "cccc3333dddd4444", "Valid Link"),
            ("aaaa1111bbbb2222", "cccc3333dddd4444", "Valid Link 2"),
        ]
        assert targets == expected

    def test_extract_uuid_targets_no_matches(self) -> None:
        """Test UUID extraction with HTML containing no UUID links."""
        html = "<div><p>Just regular HTML content</p><a href='#'>Regular link</a></div>"
        targets = extract_uuid_targets_from_html(html)
        assert targets == []


class TestTocValidation:
    """Test TOC link validation functionality."""

    def test_validate_toc_links_all_valid(self) -> None:
        """Test validation with all valid links."""
        mod_id = "valid-mod"
        entry_path = ["chapter"]
        entry_id = make_entry_id(mod_id, entry_path)
        page_id = make_page_id(mod_id, entry_path, "content")
        page = make_text_page(page_id, "Content", level=1, text_html="<p>Content</p>", sort=100)
        entry = make_journal_entry(_id=entry_id, name="Chapter", pages=[page])

        toc_entry = build_toc_entry_from_entries(mod_id, [entry])
        issues = validate_toc_links(toc_entry, [entry])

        assert issues == [], "Valid TOC should have no validation issues"

    def test_validate_toc_links_missing_entry(self) -> None:
        """Test validation detects missing entry references."""
        mod_id = "test-mod"
        entry_path = ["chapter"]
        entry_id = make_entry_id(mod_id, entry_path)
        page_id = make_page_id(mod_id, entry_path, "content")
        page = make_text_page(page_id, "Content", level=1, text_html="<p>Content</p>", sort=100)
        entry = make_journal_entry(_id=entry_id, name="Chapter", pages=[page])

        toc_entry = build_toc_entry_from_entries(mod_id, [entry])

        # Add a bad UUID link to the TOC content
        bad_html = str(toc_entry.pages[0].text["content"])
        bad_html += f" @UUID[JournalEntry.NONEXISTENT.JournalEntryPage.{page_id}]{{Bad Entry}}"
        toc_entry.pages[0].text["content"] = bad_html

        issues = validate_toc_links(toc_entry, [entry])
        assert len(issues) > 0
        assert any("missing entry" in issue.lower() for issue in issues)

    def test_validate_toc_links_missing_page(self) -> None:
        """Test validation detects missing page references."""
        mod_id = "test-mod"
        entry_path = ["chapter"]
        entry_id = make_entry_id(mod_id, entry_path)
        page_id = make_page_id(mod_id, entry_path, "content")
        page = make_text_page(page_id, "Content", level=1, text_html="<p>Content</p>", sort=100)
        entry = make_journal_entry(_id=entry_id, name="Chapter", pages=[page])

        toc_entry = build_toc_entry_from_entries(mod_id, [entry])

        # Add a bad UUID link to the TOC content
        bad_html = str(toc_entry.pages[0].text["content"])
        bad_html += f" @UUID[JournalEntry.{entry_id}.JournalEntryPage.NONEXISTENT]{{Bad Page}}"
        toc_entry.pages[0].text["content"] = bad_html

        issues = validate_toc_links(toc_entry, [entry])
        assert len(issues) > 0
        assert any("missing page" in issue.lower() for issue in issues)

    def test_validate_toc_links_multiple_issues(self) -> None:
        """Test validation detects multiple different issues."""
        mod_id = "test-mod"
        entry_path = ["chapter"]
        entry_id = make_entry_id(mod_id, entry_path)
        page_id = make_page_id(mod_id, entry_path, "content")
        page = make_text_page(page_id, "Content", level=1, text_html="<p>Content</p>", sort=100)
        entry = make_journal_entry(_id=entry_id, name="Chapter", pages=[page])

        toc_entry = build_toc_entry_from_entries(mod_id, [entry])

        # Add multiple bad UUID links
        bad_html = str(toc_entry.pages[0].text["content"])
        bad_html += f" @UUID[JournalEntry.BADENTRY1.JournalEntryPage.{page_id}]{{Bad Entry 1}}"
        bad_html += f" @UUID[JournalEntry.BADENTRY2.JournalEntryPage.{page_id}]{{Bad Entry 2}}"
        bad_html += f" @UUID[JournalEntry.{entry_id}.JournalEntryPage.BADPAGE1]{{Bad Page 1}}"
        bad_html += f" @UUID[JournalEntry.{entry_id}.JournalEntryPage.BADPAGE2]{{Bad Page 2}}"
        toc_entry.pages[0].text["content"] = bad_html

        issues = validate_toc_links(toc_entry, [entry])
        assert len(issues) >= 4  # Should detect all bad references

        entry_issues = [issue for issue in issues if "missing entry" in issue.lower()]
        page_issues = [issue for issue in issues if "missing page" in issue.lower()]

        assert len(entry_issues) >= 2  # Two bad entries
        assert len(page_issues) >= 2  # Two bad pages
