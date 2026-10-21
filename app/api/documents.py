"""Document upload and section management endpoints."""
import os
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, status

from app.schemas.documents import (
    DocumentResponse,
    DocumentSectionResponse,
    DocumentUnderstandingResponse,
    BatchUploadResponse,
)
from app.repositories.database import db
from app.services.permissions import get_current_user, require_project_member, check_permission
from app.services.document_parser import document_parser, DocumentParserError
from app.core.config import settings

router = APIRouter(prefix="/api", tags=["Documents"])

ALLOWED_EXTENSIONS = (".pdf", ".docx", ".txt", ".md")

# Extension -> the content types a browser or OS plausibly reports for it.
# Checked in addition to the extension (brief 5.4 asks for size, extension,
# MIME and parser result; MIME used to be stored but never validated).
ALLOWED_MIME_TYPES = {
    ".pdf": {"application/pdf", "application/x-pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip", "application/octet-stream",
    },
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/plain", "text/markdown", "text/x-markdown", "application/octet-stream"},
}

# Magic bytes that must be present for the container formats.
REQUIRED_MAGIC = {
    ".pdf": b"%PDF-",
    ".docx": b"PK\x03\x04",
}

_CHUNK = 64 * 1024

# Starlette renamed this constant; support both spellings.
_HTTP_413 = getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413)


class UploadRejected(Exception):
    """A single file could not be accepted; the rest of the batch continues."""

    def __init__(self, reason: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


def _extension_of(filename: str) -> str:
    lower = (filename or "").lower()
    for ext in ALLOWED_EXTENSIONS:
        if lower.endswith(ext):
            return ext
    raise UploadRejected(
        f"Unsupported file format '{filename}'. ProcessFoundry AI accepts "
        + ", ".join(ALLOWED_EXTENSIONS) + " files."
    )


async def _read_within_limit(file: UploadFile, max_bytes: int, filename: str) -> bytes:
    """Read the body in chunks, stopping as soon as the limit is exceeded.

    The whole body used to be buffered with `await file.read()` and only then
    compared against MAX_UPLOAD_MB, so an oversized upload was fully held in
    memory before being rejected (finding F14).
    """
    chunks = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise UploadRejected(
                f"'{filename}' exceeds the maximum upload size of "
                f"{settings.max_upload_mb} MB.",
                _HTTP_413,
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_content_type(ext: str, content_type: Optional[str], content: bytes, filename: str) -> None:
    declared = (content_type or "").split(";")[0].strip().lower()
    allowed = ALLOWED_MIME_TYPES.get(ext, set())
    if declared and declared not in allowed:
        raise UploadRejected(
            f"'{filename}' declares content type '{declared}', which does not match "
            f"a {ext} file."
        )
    magic = REQUIRED_MAGIC.get(ext)
    if magic and not content.startswith(magic):
        raise UploadRejected(
            f"'{filename}' does not contain valid {ext.lstrip('.').upper()} data. "
            "It may be renamed or corrupt."
        )
    if ext in (".txt", ".md"):
        # Reject binary payloads wearing a text extension.
        sample = content[:4096]
        if b"\x00" in sample:
            raise UploadRejected(
                f"'{filename}' looks like a binary file, not text."
            )


async def _store_one_document(project_id: str, file: UploadFile, user: dict) -> Dict[str, Any]:
    """Validate, parse and persist one file. Raises UploadRejected on refusal.

    Order matters: the file is written to disk only after parsing succeeded and
    the database row exists, and it is removed again if anything fails, so a
    rejected upload leaves no orphan behind (finding F14).
    """
    filename = file.filename or "uploaded_file.txt"
    ext = _extension_of(filename)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = await _read_within_limit(file, max_bytes, filename)
    if not content:
        raise UploadRejected(f"'{filename}' is empty.")
    _validate_content_type(ext, file.content_type, content, filename)

    checksum = document_parser.compute_checksum(content)

    # Report duplicates instead of letting the UNIQUE constraint surface as a 500.
    existing = db.find_document_by_checksum(project_id, checksum)
    if existing:
        raise UploadRejected(
            f"'{filename}' has already been uploaded as '{existing['filename']}'. "
            "The same content is only stored once.",
            status.HTTP_409_CONFLICT,
        )

    try:
        sections, warnings = document_parser.parse(filename, content)
    except DocumentParserError as pe:
        raise UploadRejected(str(pe))

    project_upload_dir = Path(settings.upload_dir) / project_id
    project_upload_dir.mkdir(parents=True, exist_ok=True)
    # Server-generated path; the client filename is display-only (brief 8.3 r9).
    storage_path = str(project_upload_dir / str(uuid.uuid4()))

    doc = None
    try:
        doc = db.save_document_with_sections(
            project_id=project_id,
            filename=filename,
            mime_type=file.content_type or "application/octet-stream",
            checksum=checksum,
            storage_path=storage_path,
            size_bytes=len(content),
            uploaded_by=user["id"],
            sections=sections,
            warnings=warnings,
        )
        with open(storage_path, "wb") as f:
            f.write(content)
    except Exception as exc:
        try:
            os.remove(storage_path)
        except OSError:
            pass
        if doc:
            db.delete_document(doc["id"])
        if "UNIQUE" in str(exc).upper() or "DUPLICATE" in str(exc).upper():
            raise UploadRejected(
                f"'{filename}' has already been uploaded to this project.",
                status.HTTP_409_CONFLICT,
            )
        raise UploadRejected(f"'{filename}' could not be stored: {exc}",
                             status.HTTP_500_INTERNAL_SERVER_ERROR)
    return doc


@router.post("/projects/{project_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    """Upload one source document. Kept for single-file clients."""
    my_role = require_project_member(project_id, user)
    check_permission("upload_document", my_role)
    try:
        return await _store_one_document(project_id, file, user)
    except UploadRejected as rejected:
        raise HTTPException(status_code=rejected.status_code, detail=rejected.reason)


@router.post("/projects/{project_id}/documents/batch", response_model=BatchUploadResponse)
async def upload_documents_batch(
    project_id: str,
    files: List[UploadFile] = File(...),
    user: dict = Depends(get_current_user)
):
    """Upload several documents at once, one result line per file.

    A file that fails does not stop the others (review item 4): every file is
    attempted and reported individually, so three good files and one duplicate
    produce three stored documents and one clear refusal.
    """
    my_role = require_project_member(project_id, user)
    check_permission("upload_document", my_role)

    results: List[Dict[str, Any]] = []
    for file in files:
        filename = file.filename or "uploaded_file"
        try:
            doc = await _store_one_document(project_id, file, user)
            results.append({
                "filename": filename,
                "accepted": True,
                "document_id": doc["id"],
                "sections_count": doc.get("sections_count", 0),
                "parse_warnings": doc.get("parse_warnings", []),
                "message": f"Stored and parsed into {doc.get('sections_count', 0)} section(s).",
            })
        except UploadRejected as rejected:
            results.append({
                "filename": filename,
                "accepted": False,
                "status_code": rejected.status_code,
                "message": rejected.reason,
            })
        except Exception as exc:  # never let one bad file abort the batch
            results.append({
                "filename": filename,
                "accepted": False,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Unexpected error: {exc}",
            })

    accepted = sum(1 for r in results if r["accepted"])
    return {
        "results": results,
        "accepted_count": accepted,
        "rejected_count": len(results) - accepted,
    }


@router.get("/projects/{project_id}/documents", response_model=List[DocumentResponse])
def list_project_documents(project_id: str, user: dict = Depends(get_current_user)):
    require_project_member(project_id, user)
    return db.list_project_documents(project_id)

@router.get("/documents/{document_id}/sections", response_model=List[DocumentSectionResponse])
def list_document_sections(document_id: str, user: dict = Depends(get_current_user)):
    doc = db.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    require_project_member(doc["project_id"], user)
    return db.list_document_sections(document_id)

@router.get("/documents/{document_id}/understanding", response_model=DocumentUnderstandingResponse)
def get_document_understanding(document_id: str, user: dict = Depends(get_current_user)):
    """"What I understood" for one document, with every quote verified in code.

    Two changes from the original (REVIEW_REPORT.md item 6):
      * each quote must be a verbatim substring of a stored section, exactly as
        the evidence pipeline requires; an unverifiable quote is dropped rather
        than shown with a page number and a FACT badge;
      * the result is cached per document checksum, so opening a page does not
        fire one model call per document on every render.
    """
    doc = db.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    require_project_member(doc["project_id"], user)

    sections = db.list_document_sections(document_id)
    if not sections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no parsed sections to extract understanding from."
        )

    warnings = doc.get("parse_warnings") or []
    read_from_img = any(bool(s.get("read_from_image")) for s in sections)
    partially_read = any("could not be read" in str(w).lower()
                         or "ocr failed" in str(w).lower() for w in warnings)

    cached = db.get_document_understanding(document_id, doc["checksum"])
    if cached:
        cached["document_id"] = doc["id"]
        cached["filename"] = doc["filename"]
        cached["read_from_image"] = read_from_img
        cached["partially_read"] = partially_read
        return DocumentUnderstandingResponse.model_validate(cached)

    from app.services.llm_service import llm_service
    combined_text = "\n\n".join([
        f"[Page {s.get('page_number', 1)}] {s.get('section_title', '')}\n{s.get('text', '')}"
        for s in sections
    ])

    prompt = (
        f"Analyze this institutional document:\n"
        f"{llm_service.wrap_source(combined_text)}\n\n"
        "Extract the verified ground-truth facts across these categories:\n"
        "1. Document type\n"
        "2. Summary\n"
        "3. Required documents\n"
        "4. Process steps\n"
        "5. Fees and waivers\n"
        "6. Dates and deadlines\n"
        "7. People, roles, and responsibilities\n\n"
        "Rules:\n"
        "- For every fact, include the exact verbatim supporting quotation and page reference from the source.\n"
        "- Clearly distinguish extracted facts (is_extracted_fact=True) from interpretations (is_extracted_fact=False).\n"
        "- If information for a category is missing or not stated in the source, list it in missing_or_uncertain_information.\n"
        "- Never invent quotes or present unsupported details as facts."
    )

    result = llm_service.complete_json(prompt, DocumentUnderstandingResponse)
    result.document_id = doc["id"]
    result.filename = doc["filename"]
    result.read_from_image = read_from_img
    result.partially_read = partially_read
    result.model_is_mock = llm_service.is_mock()

    dropped = _verify_understanding_quotes(result, sections)
    result.unverified_quotes_dropped = dropped
    if dropped:
        result.missing_or_uncertain_information.append(
            f"{dropped} quotation(s) offered by the model could not be found in the "
            "source text and were discarded."
        )

    db.save_document_understanding(document_id, doc["checksum"], result.model_dump())
    return result


_UNDERSTANDING_LIST_FIELDS = (
    "required_documents", "process_steps", "fees",
    "dates_and_deadlines", "people_roles_responsibilities",
)


def _verify_understanding_quotes(result: DocumentUnderstandingResponse, sections: List[Dict[str, Any]]) -> int:
    """Drop or demote any quote that is not verbatim in a stored section.

    Same deterministic rule the evidence agent applies (SPEC-04-02): the model
    proposes, code validates. Returns how many facts were discarded.
    """
    section_texts = [s.get("text") or "" for s in sections]

    def verified(quote: Optional[str]) -> bool:
        if not quote or not quote.strip():
            return False
        needle = quote.strip()
        return any(needle in text for text in section_texts)

    dropped = 0
    for field in _UNDERSTANDING_LIST_FIELDS:
        kept = []
        for fact in getattr(result, field):
            if verified(fact.exact_quote):
                fact.quote_verified = True
                kept.append(fact)
            elif not fact.is_extracted_fact:
                # An interpretation may stand without a quote, but never with an
                # unverifiable one presented as support.
                fact.exact_quote = None
                fact.quote_verified = False
                kept.append(fact)
            else:
                dropped += 1
        setattr(result, field, kept)

    # document_type and summary are single fields: demote rather than delete, so
    # the view still says what kind of document this is.
    for single in ("document_type", "summary"):
        fact = getattr(result, single)
        if verified(fact.exact_quote):
            fact.quote_verified = True
        else:
            if fact.exact_quote:
                dropped += 1
            fact.exact_quote = None
            fact.quote_verified = False
            fact.is_extracted_fact = False

    return dropped
