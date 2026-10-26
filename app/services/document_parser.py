"""ProcessFoundry AI: Document Ingestion and Section Parsing Service."""
import hashlib
import io
import logging
import re
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("processfoundry.parser")

class DocumentParserError(Exception):
    """Raised when parsing fails."""
    pass

class DocumentParser:
    def compute_checksum(self, content: bytes) -> str:
        """Compute SHA-256 checksum of raw file bytes."""
        return hashlib.sha256(content).hexdigest()

    def parse(self, filename: str, content: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Parse raw document bytes into structured sections.
        
        Returns:
            Tuple of (sections_list, warnings_list)
        """
        lower_name = filename.lower()
        if lower_name.endswith(".txt") or lower_name.endswith(".md"):
            sections, warnings = self._parse_text(content.decode("utf-8-sig", errors="replace"))
        elif lower_name.endswith(".docx"):
            sections, warnings = self._parse_docx(content)
        elif lower_name.endswith(".pdf"):
            sections, warnings = self._parse_pdf(content)
        else:
            raise DocumentParserError(f"Unsupported file format for '{filename}'. ProcessFoundry AI supports .txt, .md, .docx, and .pdf files.")

        if not sections or not any(s.get("text", "").strip() for s in sections):
            raise DocumentParserError(f"Document '{filename}' produced zero usable text sections. It may be empty or unreadable.")

        return sections, warnings

    def _is_heading(self, line: str) -> bool:
        """Detect section headings: Numbered (e.g. '1. TITLE'), Markdown ('# TITLE'), or ALL-CAPS short lines."""
        stripped = line.strip()
        if not stripped or len(stripped) > 100:
            return False

        # Markdown headings
        if re.match(r"^#{1,6}\s+\S+", stripped):
            return True

        # Numbered headings e.g. "1. OVERVIEW", "Section 2: Rules", "2.1 Deadlines", "१. प्रवेश प्रक्रिया", "विभाग २: नियम"
        if re.match(
            r"^(\d+(\.\d+)*\.?|(?:section|भाग|विभाग|अध्याय|अनुभाग|परिशिष्ट|कलम)\s+\d+[:.]?)\s+[^\W\d_]",
            stripped,
            re.IGNORECASE | re.UNICODE,
        ):
            return True

        # ALL-CAPS short titles (at least 4 letters, no period/danda at end, mostly upper)
        clean_letters = re.sub(r"[^A-Za-z]", "", stripped)
        if len(clean_letters) >= 4 and clean_letters.isupper() and not stripped.endswith((".", "।", "॥")):
            return True

        return False

    def _clean_heading(self, line: str) -> str:
        return re.sub(r"^#{1,6}\s+", "", line).strip()

    def _parse_text(self, text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        lines = text.splitlines()
        sections = []
        warnings = []
        current_title = "Document Overview"
        current_lines = []
        section_idx = 1

        for line in lines:
            if self._is_heading(line):
                if current_lines:
                    sec_text = "\n".join(current_lines).strip()
                    if sec_text:
                        sections.append({
                            "section_index": section_idx,
                            "page_number": 1,
                            "section_title": current_title,
                            "text": sec_text,
                            "read_from_image": False
                        })
                        section_idx += 1
                    current_lines = []
                current_title = self._clean_heading(line)
            else:
                current_lines.append(line)

        # Flush final section
        if current_lines:
            sec_text = "\n".join(current_lines).strip()
            if sec_text:
                sections.append({
                    "section_index": section_idx,
                    "page_number": 1,
                    "section_title": current_title,
                    "text": sec_text,
                    "read_from_image": False
                })

        if not sections and text.strip():
            sections.append({
                "section_index": 1,
                "page_number": 1,
                "section_title": "Full Document",
                "text": text.strip(),
                "read_from_image": False
            })

        return sections, warnings

    def _parse_docx(self, content: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
        try:
            import docx
            doc = docx.Document(io.BytesIO(content))
        except Exception as e:
            raise DocumentParserError(f"Corrupt or unreadable DOCX document: {e}")

        sections = []
        warnings = []
        current_title = "Document Overview"
        current_lines = []
        section_idx = 1

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            is_style_heading = para.style and "Heading" in para.style.name
            if is_style_heading or self._is_heading(text):
                if current_lines:
                    sec_text = "\n".join(current_lines).strip()
                    if sec_text:
                        sections.append({
                            "section_index": section_idx,
                            "page_number": 1,
                            "section_title": current_title,
                            "text": sec_text,
                            "read_from_image": False
                        })
                        section_idx += 1
                    current_lines = []
                current_title = text
            else:
                current_lines.append(text)

        if current_lines:
            sec_text = "\n".join(current_lines).strip()
            if sec_text:
                sections.append({
                    "section_index": section_idx,
                    "page_number": 1,
                    "section_title": current_title,
                    "text": sec_text,
                    "read_from_image": False
                })

        return sections, warnings

    def _parse_pdf(self, content: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
        try:
            import pymupdf
            doc = pymupdf.open(stream=content, filetype="pdf")
        except Exception as e:
            raise DocumentParserError(f"Corrupt or unreadable PDF document: {e}")

        # Protect against oversized PDFs
        if len(doc) > 100:
            raise DocumentParserError(f"PDF exceeds maximum page limit (100 pages). Found {len(doc)} pages.")

        sections = []
        warnings = []
        current_title = "Document Overview"
        current_lines = []
        current_page = 1
        section_idx = 1
        any_read_from_image = False
        unreadable_pages = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text() or ""
            is_image_page = False

            # Check if page has no usable text layer (scanned page)
            if len(page_text.strip()) < 30:
                try:
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")
                    from app.services.llm_service import llm_service
                    ocr_text = llm_service.extract_text_from_image(img_bytes, mime_type="image/png")
                    if ocr_text and ocr_text.strip():
                        page_text = ocr_text
                        is_image_page = True
                        any_read_from_image = True
                    else:
                        unreadable_pages.append(page_num + 1)
                except Exception as e:
                    # Record it on the document: a page silently contributing no
                    # text used to leave a partly-read file looking fully parsed.
                    unreadable_pages.append(page_num + 1)
                    logger.warning(f"Page {page_num + 1} could not be read: {e}")

            lines = page_text.splitlines()
            for line in lines:
                if self._is_heading(line):
                    if current_lines:
                        sec_text = "\n".join(current_lines).strip()
                        if sec_text:
                            sections.append({
                                "section_index": section_idx,
                                "page_number": current_page,
                                "section_title": current_title,
                                "text": sec_text,
                                "read_from_image": is_image_page
                            })
                            section_idx += 1
                        current_lines = []
                    current_title = self._clean_heading(line)
                    current_page = page_num + 1
                else:
                    current_lines.append(line)

            if current_lines:
                sec_text = "\n".join(current_lines).strip()
                if sec_text:
                    sections.append({
                        "section_index": section_idx,
                        "page_number": current_page,
                        "section_title": current_title,
                        "text": sec_text,
                        "read_from_image": is_image_page
                    })
                    section_idx += 1
                current_lines = []

        if any_read_from_image:
            warnings.append("Read from images, check the wording.")
        if unreadable_pages:
            pages = ", ".join(str(p) for p in unreadable_pages)
            warnings.append(
                f"{len(unreadable_pages)} page(s) could not be read and are missing from "
                f"the text below (page {pages}). This document is only partly read."
            )

        return sections, warnings

document_parser = DocumentParser()
