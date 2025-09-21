"""Tests for heuristics module."""

from __future__ import annotations

from unittest.mock import Mock

from pdf2foundry.ingest.heuristics import build_outline_from_headings


class TestBuildOutlineFromHeadings:
    """Test the build_outline_from_headings function."""

    def test_no_blocks_fallback(self) -> None:
        """Test fallback when document has no blocks."""
        doc = Mock()
        doc.blocks = None

        outline = build_outline_from_headings(doc, 10)

        assert len(outline) == 1
        assert outline[0].title == "Document"
        assert outline[0].level == 1
        assert outline[0].page_start == 1
        assert outline[0].page_end == 10
        assert outline[0].children == []
        assert outline[0].path == ["document"]

    def test_empty_blocks_fallback(self) -> None:
        """Test fallback when document has empty blocks."""
        doc = Mock()
        doc.blocks = []

        outline = build_outline_from_headings(doc, 5)

        assert len(outline) == 1
        assert outline[0].title == "Document"
        assert outline[0].level == 1
        assert outline[0].page_start == 1
        assert outline[0].page_end == 5
        assert outline[0].children == []
        assert outline[0].path == ["document"]

    def test_blocks_access_exception(self) -> None:
        """Test handling of exception when accessing blocks."""
        doc = Mock()
        # Create blocks that will raise exception on indexing
        doc.blocks = Mock()
        doc.blocks.__getitem__ = Mock(side_effect=IndexError("No first page"))

        outline = build_outline_from_headings(doc, 3)

        assert len(outline) == 1
        assert outline[0].title == "Document"
        assert outline[0].level == 1
        assert outline[0].page_start == 1
        assert outline[0].page_end == 3

    def test_title_category_detection(self) -> None:
        """Test detection of title by category attribute."""
        # Create block with title category
        title_block = Mock()
        title_block.category = "title"
        title_block.text = "My Document Title"
        title_block.font_size = None
        title_block.size = None

        # Create other blocks
        other_block = Mock()
        other_block.category = "paragraph"
        other_block.text = "Some paragraph text"

        first_page_blocks = [other_block, title_block]

        doc = Mock()
        doc.blocks = [first_page_blocks]

        outline = build_outline_from_headings(doc, 8)

        assert len(outline) == 1
        assert outline[0].title == "My Document Title"
        assert outline[0].level == 1
        assert outline[0].page_start == 1
        assert outline[0].page_end == 8
        assert outline[0].path == ["my-document-title"]

    def test_heading_category_detection(self) -> None:
        """Test detection of title by heading category."""
        # Create block with heading category
        heading_block = Mock()
        heading_block.category = "heading"
        heading_block.text = "Chapter One"
        heading_block.font_size = None

        first_page_blocks = [heading_block]

        doc = Mock()
        doc.blocks = [first_page_blocks]

        outline = build_outline_from_headings(doc, 12)

        assert len(outline) == 1
        assert outline[0].title == "Chapter One"
        assert outline[0].path == ["chapter-one"]

    def test_type_attribute_fallback(self) -> None:
        """Test using type attribute when category is not available."""
        # Create block with type instead of category
        title_block = Mock()
        title_block.category = None
        title_block.type = "TITLE"
        title_block.text = "Document Title"

        first_page_blocks = [title_block]

        doc = Mock()
        doc.blocks = [first_page_blocks]

        outline = build_outline_from_headings(doc, 6)

        assert len(outline) == 1
        assert outline[0].title == "Document Title"

    def test_font_size_detection(self) -> None:
        """Test detection of title by large font size."""
        # Create block with large font
        large_font_block = Mock()
        large_font_block.category = "paragraph"  # Not a title category
        large_font_block.type = None
        large_font_block.text = "Big Title Text"
        large_font_block.font_size = 18  # >= 16

        # Create block with small font
        small_font_block = Mock()
        small_font_block.category = "paragraph"
        small_font_block.text = "Small text"
        small_font_block.font_size = 12  # < 16

        first_page_blocks = [small_font_block, large_font_block]

        doc = Mock()
        doc.blocks = [first_page_blocks]

        outline = build_outline_from_headings(doc, 4)

        assert len(outline) == 1
        assert outline[0].title == "Big Title Text"
        assert outline[0].path == ["big-title-text"]

    def test_size_attribute_fallback(self) -> None:
        """Test using size attribute when font_size is not available."""
        # Create block with size instead of font_size
        large_block = Mock()
        large_block.category = "paragraph"
        large_block.text = "Large Size Title"
        large_block.font_size = None
        large_block.size = 20.5  # >= 16

        first_page_blocks = [large_block]

        doc = Mock()
        doc.blocks = [first_page_blocks]

        outline = build_outline_from_headings(doc, 7)

        assert len(outline) == 1
        assert outline[0].title == "Large Size Title"

    def test_priority_category_over_font_size(self) -> None:
        """Test that category detection takes priority over font size."""
        # Create block with title category but small font
        title_block = Mock()
        title_block.category = "title"
        title_block.text = "Small Title"
        title_block.font_size = 10  # Small font

        # Create block with large font but no title category
        large_block = Mock()
        large_block.category = "paragraph"
        large_block.text = "Large Paragraph"
        large_block.font_size = 20  # Large font

        first_page_blocks = [title_block, large_block]  # Put title block first

        doc = Mock()
        doc.blocks = [first_page_blocks]

        outline = build_outline_from_headings(doc, 9)

        # Should pick the title category block, not the large font block
        assert len(outline) == 1
        assert outline[0].title == "Small Title"

    def test_no_suitable_title_found(self) -> None:
        """Test fallback when no suitable title is found in blocks."""
        # Create blocks without title category or large font
        block1 = Mock()
        block1.category = "paragraph"
        block1.text = "Regular text"
        block1.font_size = 12

        block2 = Mock()
        block2.category = "image"
        block2.text = None
        block2.font_size = 14

        first_page_blocks = [block1, block2]

        doc = Mock()
        doc.blocks = [first_page_blocks]

        outline = build_outline_from_headings(doc, 15)

        assert len(outline) == 1
        assert outline[0].title == "Document"  # Fallback title
        assert outline[0].path == ["document"]

    def test_empty_text_ignored(self) -> None:
        """Test that blocks with empty text are ignored."""
        # Create block with title category but empty text (falsy, so skipped)
        empty_title = Mock()
        empty_title.category = "title"
        empty_title.text = ""

        # Create block with whitespace-only text (truthy, gets selected but strips to empty)
        whitespace_title = Mock()
        whitespace_title.category = "title"
        whitespace_title.text = "   \n\t  "

        first_page_blocks = [empty_title, whitespace_title]

        doc = Mock()
        doc.blocks = [first_page_blocks]

        outline = build_outline_from_headings(doc, 11)

        assert len(outline) == 1
        # The whitespace text is truthy, so it gets selected and then stripped to empty
        # Since the stripped result is empty, it falls back to "Document"
        assert outline[0].title == "Document"

    def test_valid_text_after_empty_ones(self) -> None:
        """Test that valid text is found after empty/whitespace ones."""
        # Create block with empty text (skipped)
        empty_title = Mock()
        empty_title.category = "title"
        empty_title.text = ""

        # Create block with valid text
        good_title = Mock()
        good_title.category = "title"
        good_title.text = "  Real Title  "

        first_page_blocks = [empty_title, good_title]

        doc = Mock()
        doc.blocks = [first_page_blocks]

        outline = build_outline_from_headings(doc, 11)

        assert len(outline) == 1
        assert outline[0].title == "Real Title"  # Stripped text

    def test_text_stripping(self) -> None:
        """Test that title text is properly stripped of whitespace."""
        title_block = Mock()
        title_block.category = "title"
        title_block.text = "  \n  Padded Title  \t  "

        first_page_blocks = [title_block]

        doc = Mock()
        doc.blocks = [first_page_blocks]

        outline = build_outline_from_headings(doc, 2)

        assert len(outline) == 1
        assert outline[0].title == "Padded Title"
        assert outline[0].path == ["padded-title"]

    def test_path_generation_with_spaces_and_case(self) -> None:
        """Test path generation handles spaces and case conversion."""
        title_block = Mock()
        title_block.category = "title"
        title_block.text = "My Complex Document Title"

        first_page_blocks = [title_block]

        doc = Mock()
        doc.blocks = [first_page_blocks]

        outline = build_outline_from_headings(doc, 1)

        assert len(outline) == 1
        assert outline[0].title == "My Complex Document Title"
        assert outline[0].path == ["my-complex-document-title"]

    def test_none_first_page_blocks(self) -> None:
        """Test handling when first page blocks is None."""
        doc = Mock()
        doc.blocks = [None]  # First page is None

        outline = build_outline_from_headings(doc, 3)

        assert len(outline) == 1
        assert outline[0].title == "Document"

    def test_missing_attributes_handled(self) -> None:
        """Test that missing attributes on blocks are handled gracefully."""
        # Create block with minimal attributes
        minimal_block = Mock()
        # Don't set category, type, text, font_size, or size
        del minimal_block.category
        del minimal_block.type
        del minimal_block.text
        del minimal_block.font_size
        del minimal_block.size

        first_page_blocks = [minimal_block]

        doc = Mock()
        doc.blocks = [first_page_blocks]

        outline = build_outline_from_headings(doc, 5)

        # Should fall back to "Document" since no valid title found
        assert len(outline) == 1
        assert outline[0].title == "Document"

    def test_case_insensitive_category_matching(self) -> None:
        """Test that category matching is case insensitive."""
        # Test various cases
        cases = ["TITLE", "Title", "title", "HEADING", "Heading", "heading"]

        for i, category_value in enumerate(cases):
            title_block = Mock()
            title_block.category = category_value
            title_block.text = f"Title {i}"

            first_page_blocks = [title_block]

            doc = Mock()
            doc.blocks = [first_page_blocks]

            outline = build_outline_from_headings(doc, 1)

            assert len(outline) == 1
            assert outline[0].title == f"Title {i}"
