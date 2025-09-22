"""Tests for fixture utilities."""

import sys
from pathlib import Path

import pytest

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.fixtures import (
    generate_complex_pdf,
    generate_minimal_pdf,
    get_fixture,
    load_manifest,
    sha256,
    verify_manifest,
)


def test_load_manifest():
    """Test that the manifest loads correctly."""
    manifest = load_manifest()

    assert isinstance(manifest, dict)
    assert "fixtures" in manifest
    assert "version" in manifest
    assert isinstance(manifest["fixtures"], dict)


def test_sha256_with_path(tmp_path):
    """Test SHA256 calculation with file path."""
    # Create a test file
    test_file = tmp_path / "test.txt"
    test_content = b"Hello, World!"
    test_file.write_bytes(test_content)

    # Calculate hash
    hash_result = sha256(test_file)

    # Verify it's a valid hex string
    assert isinstance(hash_result, str)
    assert len(hash_result) == 64
    assert all(c in "0123456789abcdef" for c in hash_result)

    # Verify it matches expected hash for this content
    import hashlib

    expected = hashlib.sha256(test_content).hexdigest()
    assert hash_result == expected


def test_sha256_with_file_object(tmp_path):
    """Test SHA256 calculation with file-like object."""
    from io import BytesIO

    test_content = b"Test content for hashing"
    file_obj = BytesIO(test_content)

    hash_result = sha256(file_obj)

    # Verify it's a valid hex string
    assert isinstance(hash_result, str)
    assert len(hash_result) == 64

    # Verify file position is reset
    assert file_obj.tell() == 0


def test_generate_minimal_pdf(tmp_path):
    """Test minimal PDF generation."""
    pdf_path = tmp_path / "test.pdf"
    title = "Test PDF"
    body = "This is a test PDF content."

    generate_minimal_pdf(pdf_path, title, body)

    # Verify file was created
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0

    # Verify it's a PDF (starts with PDF header)
    with pdf_path.open("rb") as f:
        header = f.read(4)
        assert header == b"%PDF"


def test_generate_complex_pdf(tmp_path):
    """Test complex PDF generation."""
    pdf_path = tmp_path / "complex.pdf"
    title = "Complex Test Document"
    num_pages = 3

    generate_complex_pdf(pdf_path, title, num_pages)

    # Verify file was created
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0

    # Verify it's a PDF
    with pdf_path.open("rb") as f:
        header = f.read(4)
        assert header == b"%PDF"

    # Complex PDF should be larger than minimal PDF
    minimal_path = tmp_path / "minimal.pdf"
    generate_minimal_pdf(minimal_path)

    assert pdf_path.stat().st_size > minimal_path.stat().st_size


def test_verify_manifest_with_missing_files():
    """Test manifest verification when files are missing."""
    results = verify_manifest()

    # Results should be a dictionary
    assert isinstance(results, dict)

    # All results should be boolean
    for _fixture_name, result in results.items():
        assert isinstance(result, bool)
        # Since we're using placeholder hashes, most should be True
        # or False if files don't exist


def test_get_fixture_existing():
    """Test getting an existing fixture."""
    # This test assumes basic.pdf exists in fixtures
    # If it doesn't, it should raise FileNotFoundError
    try:
        fixture_path = get_fixture("basic.pdf")
        assert isinstance(fixture_path, Path)
        assert fixture_path.name == "basic.pdf"
        assert fixture_path.exists()
    except FileNotFoundError:
        # This is expected if the fixture doesn't exist yet
        pytest.skip("basic.pdf fixture not found - this is expected for new setups")


def test_get_fixture_nonexistent():
    """Test getting a non-existent fixture."""
    with pytest.raises(FileNotFoundError):
        get_fixture("definitely_does_not_exist.pdf")


def test_pdf_generation_creates_valid_structure(tmp_path):
    """Test that generated PDFs have valid internal structure."""
    pdf_path = tmp_path / "structure_test.pdf"
    generate_minimal_pdf(pdf_path, "Structure Test", "Content for structure validation.")

    # Read the PDF content as text to check for basic PDF structure
    content = pdf_path.read_bytes()

    # Check for PDF version
    assert content.startswith(b"%PDF-")

    # Check for basic PDF objects
    assert b"obj" in content
    assert b"endobj" in content

    # Check for EOF marker
    assert content.endswith(b"%%EOF\n") or content.endswith(b"%%EOF")


@pytest.mark.slow
def test_large_pdf_generation(tmp_path):
    """Test generation of larger PDFs."""
    pdf_path = tmp_path / "large.pdf"

    # Generate a PDF with many pages
    generate_complex_pdf(pdf_path, "Large Test Document", 10)

    assert pdf_path.exists()
    # Large PDF should be significantly bigger
    assert pdf_path.stat().st_size > 10000  # At least 10KB


def test_manifest_structure():
    """Test that the manifest has the expected structure."""
    manifest = load_manifest()

    # Check top-level keys
    required_keys = ["description", "version", "fixtures"]
    for key in required_keys:
        assert key in manifest

    # Check fixture entries structure
    for fixture_name, metadata in manifest["fixtures"].items():
        assert isinstance(fixture_name, str)
        assert isinstance(metadata, dict)

        # Check required metadata fields
        required_fields = ["description", "sha256", "size_bytes", "pages", "tags"]
        for field in required_fields:
            assert field in metadata

        assert isinstance(metadata["tags"], list)
        assert isinstance(metadata["size_bytes"], int)
        assert isinstance(metadata["pages"], int)
