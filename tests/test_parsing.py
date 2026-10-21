"""Tests for document parsing, format handling, and section detection (SPEC-03)."""
import pytest
from app.services.document_parser import document_parser, DocumentParserError

def test_parse_text_sections_numbered_and_caps():
    """Covers SPEC-03-01, SPEC-03-03."""
    content = """# MERIT SCHOLARSHIP SOP

1. OVERVIEW
This is the scholarship overview text describing basic requirements.

2. APPLICATION DEADLINE
All applications must be submitted before 31 March.

3. VERIFICATION
The form is verified.
"""
    sections, warnings = document_parser.parse("scholarship.txt", content.encode("utf-8"))
    assert len(sections) >= 3
    titles = [s["section_title"] for s in sections]
    assert any("OVERVIEW" in t for t in titles)
    assert any("APPLICATION DEADLINE" in t for t in titles)
    assert any("VERIFICATION" in t for t in titles)

def test_parse_text_checksum():
    """Covers SPEC-03-04."""
    content = b"Sample policy document text."
    checksum1 = document_parser.compute_checksum(content)
    checksum2 = document_parser.compute_checksum(content)
    assert checksum1 == checksum2
    assert len(checksum1) == 64

def test_unsupported_file_format_rejected():
    """Covers SPEC-03-02."""
    with pytest.raises(DocumentParserError) as exc_info:
        document_parser.parse("bad_file.exe", b"\x00\x01\x02\x03")
    assert "Unsupported file format" in str(exc_info.value)
