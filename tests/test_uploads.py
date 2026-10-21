"""Upload behaviour: batches, duplicates, limits, MIME and orphan files.

Covers AC-03-01, AC-03-02, AC-03-03 (SPEC-03-01..05) and review item 4.
Findings addressed: duplicate content returned an unhandled HTTP 500; the
uploader took one file at a time; the size limit was applied only after the
whole body had been buffered; MIME was stored but never validated; and a failed
upload left its file behind on disk.
"""
import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.repositories.database import db

GOOD = b"""1. ELIGIBILITY
Applications must be submitted before 31 March of each year.
The scholarship clerk verifies the income certificate.
"""


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def project(client):
    email = f"up_{uuid.uuid4().hex[:8]}@example.com"
    password = "UploadPass123!"
    reg = client.post("/api/auth/register", json={
        "display_name": "Upload Tester", "email": email,
        "password": password, "repeat_password": password,
    })
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    pid = client.post("/api/projects", headers=headers,
                      json={"name": "Uploads", "role": "process_owner"}).json()["id"]
    return headers, pid


def _unique(tag: str) -> bytes:
    return GOOD.replace(b"31 March", f"{tag} March".encode())


def _files_on_disk(pid: str) -> int:
    root = Path(settings.upload_dir) / pid
    if not root.exists():
        return 0
    return len([p for p in root.rglob("*") if p.is_file()])


# ---------------------------------------------------------------------------
# Several files at once, one result line each
# ---------------------------------------------------------------------------
def test_several_files_upload_at_once_with_one_result_line_each(client, project):
    """Review item 4: a batch upload reports every file separately.

    Covers SPEC-03-01, SPEC-12-03.
    """
    headers, pid = project
    payload = [
        ("files", ("a.txt", _unique("10"), "text/plain")),
        ("files", ("b.txt", _unique("11"), "text/plain")),
        ("files", ("c.txt", _unique("12"), "text/plain")),
    ]
    resp = client.post(f"/api/projects/{pid}/documents/batch", headers=headers, files=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["accepted_count"] == 3
    assert body["rejected_count"] == 0
    assert len(body["results"]) == 3
    assert {r["filename"] for r in body["results"]} == {"a.txt", "b.txt", "c.txt"}
    for line in body["results"]:
        assert line["accepted"] is True
        assert line["document_id"]
        assert line["sections_count"] >= 1
        assert "section" in line["message"]

    assert len(client.get(f"/api/projects/{pid}/documents", headers=headers).json()) == 3


def test_a_failing_file_does_not_stop_the_others(client, project):
    """Review item 4: one bad file must not abort the batch.

    Covers SPEC-03-02.
    """
    headers, pid = project
    payload = [
        ("files", ("good1.txt", _unique("13"), "text/plain")),
        ("files", ("bad.exe", b"MZ\x90\x00binary", "application/x-msdownload")),
        ("files", ("good2.txt", _unique("14"), "text/plain")),
        ("files", ("empty.txt", b"", "text/plain")),
    ]
    resp = client.post(f"/api/projects/{pid}/documents/batch", headers=headers, files=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    by_name = {r["filename"]: r for r in body["results"]}
    assert by_name["good1.txt"]["accepted"] is True
    assert by_name["good2.txt"]["accepted"] is True
    assert by_name["bad.exe"]["accepted"] is False
    assert by_name["empty.txt"]["accepted"] is False
    assert body["accepted_count"] == 2
    assert body["rejected_count"] == 2
    assert len(client.get(f"/api/projects/{pid}/documents", headers=headers).json()) == 2


# ---------------------------------------------------------------------------
# Duplicates
# ---------------------------------------------------------------------------
def test_duplicate_content_is_reported_not_a_500(client, project):
    """Review item 4: the second upload of identical content is a handled 409.

    Covers SPEC-03-04.
    """
    headers, pid = project
    first = client.post(f"/api/projects/{pid}/documents", headers=headers,
                        files={"file": ("same.txt", GOOD, "text/plain")})
    assert first.status_code == 201, first.text

    second = client.post(f"/api/projects/{pid}/documents", headers=headers,
                         files={"file": ("same-again.txt", GOOD, "text/plain")})
    assert second.status_code == 409, f"expected a handled conflict, got {second.status_code}"
    detail = second.json()["detail"]
    assert "already been uploaded" in detail
    assert "same.txt" in detail, "the message should name the existing document"

    assert len(client.get(f"/api/projects/{pid}/documents", headers=headers).json()) == 1


def test_duplicate_in_a_batch_is_reported_per_file(client, project):
    """Review item 4: duplicates are reported, never silently added.

    Covers SPEC-03-04.
    """
    headers, pid = project
    payload = [
        ("files", ("one.txt", GOOD, "text/plain")),
        ("files", ("one-copy.txt", GOOD, "text/plain")),
    ]
    resp = client.post(f"/api/projects/{pid}/documents/batch", headers=headers, files=payload)
    body = resp.json()
    assert body["accepted_count"] == 1
    assert body["rejected_count"] == 1
    rejected = [r for r in body["results"] if not r["accepted"]][0]
    assert rejected["status_code"] == 409
    assert "already been uploaded" in rejected["message"]


# ---------------------------------------------------------------------------
# No orphan files
# ---------------------------------------------------------------------------
def test_a_rejected_upload_leaves_no_file_on_disk(client, project):
    """F14: three attempts used to leave three files with one document row.

    Covers SPEC-03-04.
    """
    headers, pid = project
    client.post(f"/api/projects/{pid}/documents", headers=headers,
                files={"file": ("keep.txt", GOOD, "text/plain")})
    assert _files_on_disk(pid) == 1

    for _ in range(3):
        dup = client.post(f"/api/projects/{pid}/documents", headers=headers,
                          files={"file": ("dup.txt", GOOD, "text/plain")})
        assert dup.status_code == 409
    client.post(f"/api/projects/{pid}/documents", headers=headers,
                files={"file": ("bad.pdf", b"not a pdf at all", "application/pdf")})

    assert _files_on_disk(pid) == 1, "a rejected upload left an orphan file behind"
    assert len(client.get(f"/api/projects/{pid}/documents", headers=headers).json()) == 1


# ---------------------------------------------------------------------------
# Validation: size, MIME, extension
# ---------------------------------------------------------------------------
def test_oversize_upload_is_rejected_without_buffering_everything(client, project, monkeypatch):
    """F14: the limit is enforced while streaming, not after the body is in memory.

    Covers SPEC-03-02.
    """
    headers, pid = project
    monkeypatch.setattr(settings, "max_upload_mb", 1)

    oversize = b"A" * (2 * 1024 * 1024)
    resp = client.post(f"/api/projects/{pid}/documents", headers=headers,
                       files={"file": ("big.txt", oversize, "text/plain")})
    assert resp.status_code == 413, f"expected 413 Payload Too Large, got {resp.status_code}"
    assert "maximum upload size" in resp.json()["detail"]
    assert _files_on_disk(pid) == 0


def test_the_limit_is_checked_in_chunks(client, project, monkeypatch):
    """F14: reading stops as soon as the limit is passed."""
    headers, pid = project
    monkeypatch.setattr(settings, "max_upload_mb", 1)

    from app.api import documents as docs_api
    read_sizes = []
    original = docs_api._read_within_limit

    async def spy(file, max_bytes, filename):
        read_sizes.append(max_bytes)
        return await original(file, max_bytes, filename)

    monkeypatch.setattr(docs_api, "_read_within_limit", spy)
    client.post(f"/api/projects/{pid}/documents", headers=headers,
                files={"file": ("big.txt", b"B" * (3 * 1024 * 1024), "text/plain")})
    assert read_sizes == [1024 * 1024]


def test_mime_type_is_validated_not_just_the_extension(client, project):
    """Brief 5.4 / F14: binary content behind a .txt name must be refused.

    Covers SPEC-03-02.
    """
    headers, pid = project
    resp = client.post(f"/api/projects/{pid}/documents", headers=headers,
                       files={"file": ("evil.exe.txt", b"MZ\x90\x00" + b"A" * 200,
                                       "application/x-msdownload")})
    assert resp.status_code == 400, f"binary content was accepted: {resp.status_code}"
    assert "content type" in resp.json()["detail"].lower()


def test_a_fake_pdf_is_refused(client, project):
    """Brief 5.4: a .pdf without PDF magic bytes is not a PDF.

    Covers SPEC-03-02.
    """
    headers, pid = project
    resp = client.post(f"/api/projects/{pid}/documents", headers=headers,
                       files={"file": ("fake.pdf", b"This is plain text, not a PDF.",
                                       "application/pdf")})
    assert resp.status_code == 400
    assert "valid PDF data" in resp.json()["detail"]


def test_a_text_file_with_null_bytes_is_refused(client, project):
    """Brief 5.4: a binary payload wearing a text extension is refused.

    Covers SPEC-03-02.
    """
    headers, pid = project
    resp = client.post(f"/api/projects/{pid}/documents", headers=headers,
                       files={"file": ("sneaky.txt", b"text\x00\x00binary", "text/plain")})
    assert resp.status_code == 400
    assert "binary" in resp.json()["detail"].lower()


def test_unsupported_extension_lists_every_accepted_type(client, project):
    """AC-03-02 / F14: the message used to omit .md, which is accepted.

    Covers SPEC-03-01, SPEC-03-02.
    """
    headers, pid = project
    resp = client.post(f"/api/projects/{pid}/documents", headers=headers,
                       files={"file": ("notes.rtf", b"some content here", "application/rtf")})
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    for ext in (".pdf", ".docx", ".txt", ".md"):
        assert ext in detail, f"{ext} is accepted but not listed in the error"


def test_markdown_is_accepted(client, project):
    """The parser supports .md, so the API must too.

    Covers SPEC-03-01.
    """
    headers, pid = project
    resp = client.post(f"/api/projects/{pid}/documents", headers=headers,
                       files={"file": ("policy.md", b"# ELIGIBILITY\nApplications close on 31 March.\n",
                                       "text/markdown")})
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Permissions and isolation are unchanged
# ---------------------------------------------------------------------------
def test_batch_upload_respects_the_permission_matrix(client, project):
    """Brief 7.9: a Technical Reviewer may not upload, in batch either.

    Covers SPEC-14-06.
    """
    headers, pid = project
    email = f"tr_{uuid.uuid4().hex[:8]}@example.com"
    password = "UploadPass123!"
    reg = client.post("/api/auth/register", json={
        "display_name": "Tech Reviewer", "email": email,
        "password": password, "repeat_password": password,
    })
    tr = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    inv = client.post(f"/api/projects/{pid}/invitations", headers=headers,
                      json={"email": email, "role": "technical_reviewer"}).json()
    client.post(f"/api/invitations/{inv['id']}/accept", headers=tr)

    resp = client.post(f"/api/projects/{pid}/documents/batch", headers=tr,
                       files=[("files", ("x.txt", GOOD, "text/plain"))])
    assert resp.status_code == 403


def test_batch_upload_is_closed_to_non_members(client, project):
    """Brief 7.3: a non-member gets "not found", not the data.

    Covers SPEC-14-05, SPEC-01-01.
    """
    headers, pid = project
    email = f"out_{uuid.uuid4().hex[:8]}@example.com"
    password = "UploadPass123!"
    reg = client.post("/api/auth/register", json={
        "display_name": "Outsider", "email": email,
        "password": password, "repeat_password": password,
    })
    outsider = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    resp = client.post(f"/api/projects/{pid}/documents/batch", headers=outsider,
                       files=[("files", ("x.txt", GOOD, "text/plain"))])
    assert resp.status_code == 404


def test_the_client_filename_is_never_used_as_a_path(client, project):
    """AC-03-03 / brief 8.3 rule 9: storage paths are server-generated.

    Covers SPEC-03-04.
    """
    headers, pid = project
    resp = client.post(f"/api/projects/{pid}/documents", headers=headers,
                       files={"file": ("../../escape.txt", GOOD, "text/plain")})
    assert resp.status_code == 201, resp.text
    assert resp.json()["filename"] == "../../escape.txt", "the name is kept for display"
    assert not os.path.exists("escape.txt")
    assert not os.path.exists(os.path.join("..", "escape.txt"))
    assert _files_on_disk(pid) == 1
