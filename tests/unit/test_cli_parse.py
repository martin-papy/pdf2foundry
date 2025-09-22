"""Tests for CLI parsing utilities."""

import pytest

from pdf2foundry.cli.parse import parse_page_spec


class TestParsePageSpec:
    """Test page specification parsing."""

    def test_single_page(self) -> None:
        """Test parsing a single page."""
        assert parse_page_spec("1") == [1]
        assert parse_page_spec("5") == [5]
        assert parse_page_spec("100") == [100]

    def test_multiple_pages(self) -> None:
        """Test parsing multiple individual pages."""
        assert parse_page_spec("1,3,5") == [1, 3, 5]
        assert parse_page_spec("5,1,3") == [1, 3, 5]  # Should be sorted
        assert parse_page_spec("1,1,3") == [1, 3]  # Should be deduplicated

    def test_ranges(self) -> None:
        """Test parsing page ranges."""
        assert parse_page_spec("1-3") == [1, 2, 3]
        assert parse_page_spec("5-7") == [5, 6, 7]
        assert parse_page_spec("10-10") == [10]  # Single page range

    def test_mixed_pages_and_ranges(self) -> None:
        """Test parsing mixed individual pages and ranges."""
        assert parse_page_spec("1,3,5-7") == [1, 3, 5, 6, 7]
        assert parse_page_spec("2-2,4") == [2, 4]
        assert parse_page_spec("1,5-10,15") == [1, 5, 6, 7, 8, 9, 10, 15]

    def test_whitespace_handling(self) -> None:
        """Test that whitespace is handled correctly."""
        assert parse_page_spec(" 1 , 3 , 5 ") == [1, 3, 5]
        assert parse_page_spec("1 - 3") == [1, 2, 3]
        assert parse_page_spec(" 1,3,5-7 ") == [1, 3, 5, 6, 7]

    def test_empty_spec(self) -> None:
        """Test that empty specifications raise ValueError."""
        with pytest.raises(ValueError, match="Page specification cannot be empty"):
            parse_page_spec("")
        with pytest.raises(ValueError, match="Page specification cannot be empty"):
            parse_page_spec("   ")

    def test_empty_token(self) -> None:
        """Test that empty tokens raise ValueError."""
        with pytest.raises(ValueError, match="empty token found"):
            parse_page_spec("1,,3")
        with pytest.raises(ValueError, match="empty token found"):
            parse_page_spec("1, ,3")

    def test_invalid_range_format(self) -> None:
        """Test that malformed ranges raise ValueError."""
        with pytest.raises(ValueError, match="malformed range"):
            parse_page_spec("1-2-3")
        with pytest.raises(ValueError, match="malformed range"):
            parse_page_spec("1--3")

    def test_non_numeric_values(self) -> None:
        """Test that non-numeric values raise ValueError."""
        with pytest.raises(ValueError, match="non-numeric"):
            parse_page_spec("a")
        with pytest.raises(ValueError, match="non-numeric"):
            parse_page_spec("1,b,3")
        with pytest.raises(ValueError, match="non-numeric"):
            parse_page_spec("a-b")

    def test_zero_and_negative_pages(self) -> None:
        """Test that zero and negative page numbers raise ValueError."""
        with pytest.raises(ValueError, match="page numbers must be positive"):
            parse_page_spec("0")
        with pytest.raises(ValueError, match="page numbers must be positive"):
            parse_page_spec("-1")
        with pytest.raises(ValueError, match="page numbers must be positive"):
            parse_page_spec("1,0,3")
        with pytest.raises(ValueError, match="page numbers must be positive"):
            parse_page_spec("0-3")

    def test_inverted_ranges(self) -> None:
        """Test that inverted ranges raise ValueError."""
        with pytest.raises(ValueError, match="range start must be <= end"):
            parse_page_spec("5-3")
        with pytest.raises(ValueError, match="range start must be <= end"):
            parse_page_spec("10-1")

    def test_complex_valid_specs(self) -> None:
        """Test complex but valid specifications."""
        # Large mixed specification
        result = parse_page_spec("1,3,5-10,15,20-22,25")
        expected = [1, 3, 5, 6, 7, 8, 9, 10, 15, 20, 21, 22, 25]
        assert result == expected

        # Overlapping ranges and duplicates
        result = parse_page_spec("1-5,3-7,5,10")
        expected = [1, 2, 3, 4, 5, 6, 7, 10]
        assert result == expected
