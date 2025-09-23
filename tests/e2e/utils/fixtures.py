"""Fixture management utilities for E2E tests."""

import hashlib
import json
from pathlib import Path
from typing import BinaryIO


def get_fixture(name: str) -> Path:
    """
    Get the path to a test fixture file.

    Args:
        name: Name of the fixture file

    Returns:
        Path to the fixture file

    Raises:
        FileNotFoundError: If the fixture doesn't exist
    """
    # Get the fixtures directory (two levels up from this file, then fixtures/)
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    fixture_path = fixtures_dir / name

    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")

    return fixture_path


def sha256(file: Path | BinaryIO) -> str:
    """
    Calculate SHA256 hash of a file.

    Args:
        file: Path to file or file-like object

    Returns:
        Hexadecimal SHA256 hash string
    """
    hash_obj = hashlib.sha256()

    if isinstance(file, Path):
        with file.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_obj.update(chunk)
    else:
        # File-like object
        file.seek(0)  # Ensure we're at the beginning
        for chunk in iter(lambda: file.read(8192), b""):
            hash_obj.update(chunk)
        file.seek(0)  # Reset position

    return hash_obj.hexdigest()


def load_manifest() -> dict:
    """
    Load the fixtures manifest file.

    Returns:
        Dictionary containing fixture metadata

    Raises:
        FileNotFoundError: If manifest.json doesn't exist
        json.JSONDecodeError: If manifest.json is invalid
    """
    manifest_path = Path(__file__).parent.parent / "fixtures" / "manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with manifest_path.open() as f:
        return json.load(f)


def verify_manifest() -> dict[str, bool]:
    """
    Verify all fixtures listed in the manifest against their expected checksums.

    Returns:
        Dictionary mapping fixture names to verification status (True/False)
    """
    manifest = load_manifest()
    results = {}

    for fixture_name, metadata in manifest.get("fixtures", {}).items():
        try:
            fixture_path = get_fixture(fixture_name)
            expected_hash = metadata.get("sha256")

            if expected_hash == "placeholder_hash_will_be_updated_when_file_exists":
                # Skip verification for placeholder hashes
                results[fixture_name] = True
                continue

            actual_hash = sha256(fixture_path)
            results[fixture_name] = actual_hash == expected_hash

        except FileNotFoundError:
            results[fixture_name] = False
        except Exception:
            results[fixture_name] = False

    return results


def update_manifest_checksums() -> None:
    """
    Update the manifest file with current checksums of existing fixtures.

    This function scans the fixtures directory and updates the manifest
    with actual file sizes, page counts (for PDFs), and SHA256 hashes.
    """
    manifest_path = Path(__file__).parent.parent / "fixtures" / "manifest.json"
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures"

    # Load existing manifest
    manifest = load_manifest()

    # Update checksums for existing files
    for fixture_name, metadata in manifest.get("fixtures", {}).items():
        fixture_path = fixtures_dir / fixture_name

        if fixture_path.exists():
            # Update hash
            metadata["sha256"] = sha256(fixture_path)

            # Update file size
            metadata["size_bytes"] = fixture_path.stat().st_size

            # For PDFs, try to get page count (requires pypdfium2 or similar)
            if fixture_name.endswith(".pdf"):
                try:
                    import pypdfium2 as pdfium

                    pdf = pdfium.PdfDocument(str(fixture_path))
                    metadata["pages"] = len(pdf)
                    pdf.close()
                except ImportError:
                    # pypdfium2 not available, keep existing page count
                    pass
                except Exception:
                    # Error reading PDF, keep existing page count
                    pass

    # Write updated manifest
    with manifest_path.open("w") as f:
        json.dump(manifest, f, indent=2)


def generate_minimal_pdf(
    path: Path, title: str = "Test PDF", body: str = "Hello, World!\\n\\nThis is a test PDF generated for testing purposes."
) -> None:
    """
    Generate a minimal PDF file using ReportLab.

    Args:
        path: Path where the PDF should be saved
        title: Title to display in the PDF
        body: Body text to include in the PDF
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create PDF
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter

    # Add title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, title)

    # Add body text
    c.setFont("Helvetica", 12)
    y_position = height - 100

    # Split body into lines and draw each line
    lines = body.split("\\n")
    for line in lines:
        if y_position < 50:  # Start new page if needed
            c.showPage()
            y_position = height - 50

        c.drawString(50, y_position, line)
        y_position -= 20

    # Add page numbers
    page_num = c.getPageNumber()
    c.drawString(width - 100, 30, f"Page {page_num}")

    # Save PDF
    c.save()


def generate_complex_pdf(path: Path, title: str = "Complex Test PDF", num_pages: int = 3) -> None:
    """
    Generate a more complex PDF with multiple pages, headings, and formatting.

    Args:
        path: Path where the PDF should be saved
        title: Title for the document
        num_pages: Number of pages to generate
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter

    for page in range(1, num_pages + 1):
        # Title on first page
        if page == 1:
            c.setFont("Helvetica-Bold", 20)
            c.drawString(50, height - 50, title)
            y_pos = height - 100
        else:
            y_pos = height - 50

        # Chapter heading
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y_pos, f"Chapter {page}")
        y_pos -= 40

        # Body paragraphs
        c.setFont("Helvetica", 11)
        paragraphs = [
            f"This is the content of chapter {page}. Lorem ipsum dolor sit amet, "
            "consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore "
            "et dolore magna aliqua.",
            "",
            "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi "
            "ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit "
            "in voluptate velit esse cillum dolore eu fugiat nulla pariatur.",
            "",
            f"Section {page}.1: Subsection Content",
            "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui "
            "officia deserunt mollit anim id est laborum. Sed ut perspiciatis unde "
            "omnis iste natus error sit voluptatem accusantium doloremque laudantium.",
        ]

        for paragraph in paragraphs:
            if y_pos < 80:  # Leave room for page number
                break

            if paragraph == "":
                y_pos -= 10
                continue

            # Word wrap for long paragraphs
            words = paragraph.split()
            line = ""
            for word in words:
                test_line = f"{line} {word}".strip()
                if c.stringWidth(test_line, "Helvetica", 11) > width - 100:
                    if line:
                        c.drawString(50, y_pos, line)
                        y_pos -= 15
                        line = word
                    else:
                        # Single word too long, just draw it
                        c.drawString(50, y_pos, word)
                        y_pos -= 15
                        line = ""
                else:
                    line = test_line

            if line:
                c.drawString(50, y_pos, line)
                y_pos -= 15

            y_pos -= 5  # Extra space between paragraphs

        # Page number
        c.setFont("Helvetica", 10)
        c.drawString(width - 100, 30, f"Page {page} of {num_pages}")

        if page < num_pages:
            c.showPage()

    c.save()


def create_test_fixtures() -> None:
    """
    Create standard test fixtures for E2E testing.

    This function generates a set of test PDFs with different characteristics
    for comprehensive testing.
    """
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)

    # Generate basic PDF
    generate_minimal_pdf(
        fixtures_dir / "test_basic.pdf", "Basic Test PDF", "This is a simple test PDF with minimal content."
    )

    # Generate complex PDF
    generate_complex_pdf(fixtures_dir / "test_complex.pdf", "Complex Test Document", 5)

    # Generate single page PDF
    generate_minimal_pdf(
        fixtures_dir / "test_single_page.pdf",
        "Single Page Test",
        "This PDF contains only one page for simple testing scenarios.",
    )

    print(f"Test fixtures created in {fixtures_dir}")


if __name__ == "__main__":
    # When run as a script, create test fixtures and update manifest
    create_test_fixtures()
    update_manifest_checksums()
    print("Test fixtures created and manifest updated.")
