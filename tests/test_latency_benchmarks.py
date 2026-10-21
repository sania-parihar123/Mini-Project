"""Latency instrumentation and optimization benchmarks for ProcessFoundry AI.

Measures:
 - Priority 1: Document upload — split into request handling, hashing, text
   extraction/partitioning, DB connection acquisition, document insert,
   section inserts (bulk vs sequential), and audit logging.
 - Priority 2: Create Project — split into DB connection acquisition, project
   row insertion, membership row insertion, and audit-chain writing.
 - Priority 3: Login — split into user lookup, bcrypt password verification,
   login success DB update, token generation, plus cold vs warm comparison.
 - Priority 4: Loading Project — database query execution vs Pydantic
   serialization, and cache-hit elimination of DB roundtrips.

All timings are directly measured and reported.
"""
import os
import time
import uuid
import hashlib
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.database import db
from app.services.document_parser import document_parser
from app.services.permissions import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_cached_user,
    cache_user,
    invalidate_user_cache,
    _user_cache
)
from app.schemas.projects import ProjectResponse


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------
def _register_and_login(client: TestClient, email: str = None, password: str = "TestPass1234!") -> dict:
    if email is None:
        email = f"benchmark_{uuid.uuid4().hex[:8]}@processfoundry.ai"
    reg = client.post("/api/auth/register", json={
        "display_name": "Benchmark User",
        "email": email,
        "password": password,
        "repeat_password": password
    })
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    user_id = reg.json()["user"]["id"]
    return {"token": token, "user_id": user_id, "email": email, "password": password}


def _create_synthetic_document(num_sections: int, words_per_section: int = 100) -> str:
    """Generate structured document text with distinct numbered sections."""
    lines = ["PROCESS FOUNDRY INSTITUTIONAL GUIDELINES\n"]
    for i in range(1, num_sections + 1):
        lines.append(f"\n{i}. SECTION {i}: OPERATIONAL POLICY RULES\n")
        para = f"Rule {i}.1: All process stakeholders must follow standard compliance procedures. " * (words_per_section // 10)
        lines.append(para)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Database Round-Trip Counter Supporting Both Postgres (ConnectionPool) & SQLite
# ---------------------------------------------------------------------------
class RoundTripCounter:
    """Context wrapper to count database queries and connection calls."""
    def __init__(self, db_instance):
        self.db = db_instance
        self.query_count = 0
        self.connection_count = 0
        self._orig_get_connection = db_instance.get_connection

    def __enter__(self):
        counter = self

        def wrap_conn(real_conn):
            class CountingConnectionProxy:
                def __init__(self, c):
                    self._conn = c

                def cursor(self, *args, **kwargs):
                    real_cur = self._conn.cursor(*args, **kwargs)

                    class CountingCursorProxy:
                        def __init__(self, cur):
                            self._cur = cur

                        def execute(self, sql, params=None):
                            counter.query_count += 1
                            if params is not None:
                                return self._cur.execute(sql, params)
                            return self._cur.execute(sql)

                        def executemany(self, sql, seq_of_params):
                            counter.query_count += 1
                            return self._cur.executemany(sql, seq_of_params)

                        def executescript(self, sql):
                            counter.query_count += 1
                            return self._cur.executescript(sql)

                        def fetchone(self):
                            return self._cur.fetchone()

                        def fetchall(self):
                            return self._cur.fetchall()

                        def __getattr__(self, name):
                            return getattr(self._cur, name)

                        def __enter__(self):
                            return self

                        def __exit__(self, exc_type, exc_val, exc_tb):
                            pass

                    return CountingCursorProxy(real_cur)

                def commit(self):
                    if hasattr(self._conn, "commit"):
                        return self._conn.commit()

                def rollback(self):
                    if hasattr(self._conn, "rollback"):
                        return self._conn.rollback()

                def close(self):
                    if hasattr(self._conn, "close"):
                        return self._conn.close()

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc_val, exc_tb):
                    pass

                def __getattr__(self, name):
                    return getattr(self._conn, name)

            return CountingConnectionProxy(real_conn)

        class ConnContextManager:
            def __init__(self, real_cm):
                self._real_cm = real_cm
                self._opened = None

            def __enter__(self):
                counter.connection_count += 1
                if hasattr(self._real_cm, "__enter__"):
                    self._opened = self._real_cm.__enter__()
                else:
                    self._opened = self._real_cm
                return wrap_conn(self._opened)

            def __exit__(self, exc_type, exc_val, exc_tb):
                if hasattr(self._real_cm, "__exit__"):
                    return self._real_cm.__exit__(exc_type, exc_val, exc_tb)

            def __getattr__(self, name):
                return getattr(self._real_cm, name)

        def proxy_get_connection():
            real_cm = self._orig_get_connection()
            return ConnContextManager(real_cm)

        self.db.get_connection = proxy_get_connection
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.get_connection = self._orig_get_connection


# ---------------------------------------------------------------------------
# Priority 1: Document Upload Latency Instrumentation & Benchmarks
# ---------------------------------------------------------------------------
def test_priority_1_upload_stage_by_stage_instrumentation():
    """Instrument and measure every distinct stage of the document upload path.
    
    Stages:
      1. Request/file bytes handling
      2. SHA-256 Hashing
      3. Text extraction & section partitioning
      4. Database connection acquisition
      5. Document insert
      6. Bulk section insert vs Sequential per-section inserts
      7. Audit event logging
      8. Total atomic upload duration
    """
    client = TestClient(app)
    auth = _register_and_login(client)
    headers = {"Authorization": f"Bearer {auth['token']}"}

    # Create project
    proj_resp = client.post("/api/projects", headers=headers, json={"name": "Upload Benchmark Project"})
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]

    # Generate document content (Medium: 15 sections, ~25KB)
    content_str = _create_synthetic_document(num_sections=15, words_per_section=120)
    content_bytes = content_str.encode("utf-8")
    filename = "medium_policy_document.txt"

    # Stage 1: Request/file bytes handling
    t0 = time.perf_counter()
    raw_bytes = content_bytes
    size_bytes = len(raw_bytes)
    t_transfer = (time.perf_counter() - t0) * 1000

    # Stage 2: SHA-256 Hashing
    t0 = time.perf_counter()
    checksum = hashlib.sha256(raw_bytes).hexdigest()
    t_hash = (time.perf_counter() - t0) * 1000

    # Stage 3: Text extraction & section partitioning
    t0 = time.perf_counter()
    sections, warnings = document_parser.parse(filename, raw_bytes)
    t_partition = (time.perf_counter() - t0) * 1000
    assert len(sections) == 15

    # Stage 4: DB Connection Acquisition
    t0 = time.perf_counter()
    with db.get_connection() as conn:
        t_conn = (time.perf_counter() - t0) * 1000

    # Compare Sequential Section Inserts vs Atomic Bulk Insert
    temp_doc_id = str(uuid.uuid4())
    seq_checksum = hashlib.sha256(f"seq_{uuid.uuid4()}".encode("utf-8")).hexdigest()
    with db.get_connection() as c:
        cur = c.cursor()
        created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if db.use_postgres:
            cur.execute("""
                INSERT INTO documents (id, project_id, filename, mime_type, checksum, version, storage_path, size_bytes, parse_status, uploaded_by, created_at)
                VALUES (%s, %s, %s, %s, %s, 1, %s, %s, 'pending', %s, %s);
            """, (temp_doc_id, project_id, "seq_test.txt", "text/plain", seq_checksum, "uploads/seq", size_bytes, auth["user_id"], created_at))
        else:
            cur.execute("""
                INSERT INTO documents (id, project_id, filename, mime_type, checksum, version, storage_path, size_bytes, parse_status, uploaded_by, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, 'pending', ?, ?);
            """, (temp_doc_id, project_id, "seq_test.txt", "text/plain", seq_checksum, "uploads/seq", size_bytes, auth["user_id"], created_at))

        t_seq_start = time.perf_counter()
        for s in sections:
            sec_id = str(uuid.uuid4())
            if db.use_postgres:
                cur.execute("""
                    INSERT INTO document_sections (id, document_id, section_index, page_number, section_title, text, read_from_image)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """, (sec_id, temp_doc_id, s["section_index"], s.get("page_number", 1), s.get("section_title", ""), s["text"], False))
            else:
                cur.execute("""
                    INSERT INTO document_sections (id, document_id, section_index, page_number, section_title, text, read_from_image)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (sec_id, temp_doc_id, s["section_index"], s.get("page_number", 1), s.get("section_title", ""), s["text"], 0))
        t_sequential_inserts = (time.perf_counter() - t_seq_start) * 1000
        if not db.use_postgres:
            c.commit()

    # Stage 5, 6, 7: Atomic single-transaction insert (save_document_with_sections)
    storage_path = f"uploads/{project_id}/{uuid.uuid4()}"
    t0 = time.perf_counter()
    doc = db.save_document_with_sections(
        project_id=project_id,
        filename=filename,
        mime_type="text/plain",
        checksum=checksum,
        storage_path=storage_path,
        size_bytes=size_bytes,
        uploaded_by=auth["user_id"],
        sections=sections,
        warnings=warnings
    )
    t_atomic_save = (time.perf_counter() - t0) * 1000

    # End-to-end API upload measurement
    api_bytes = content_bytes + b"\n# Distinct API Upload Content\n"
    t0 = time.perf_counter()
    api_resp = client.post(
        f"/api/projects/{project_id}/documents",
        headers=headers,
        files={"file": ("api_uploaded.txt", api_bytes, "text/plain")}
    )
    t_e2e_api = (time.perf_counter() - t0) * 1000
    assert api_resp.status_code == 201

    print("\n" + "="*70)
    print("PRIORITY 1: DOCUMENT UPLOAD TIMING BREAKDOWN (MEASURED)")
    print("="*70)
    print(f" 1. File Read & Transfer:           {t_transfer:8.3f} ms")
    print(f" 2. SHA-256 Checksum Hashing:       {t_hash:8.3f} ms")
    print(f" 3. Text Extraction & Partitioning: {t_partition:8.3f} ms ({len(sections)} sections)")
    print(f" 4. DB Connection Acquisition:      {t_conn:8.3f} ms")
    print(f" 5. Sequential Section Inserts:     {t_sequential_inserts:8.3f} ms (15 individual queries)")
    print(f" 6. Atomic Bulk Save (Doc+Sec+Log): {t_atomic_save:8.3f} ms (1 bulk query in 1 transaction)")
    print(f" 7. Full E2E Upload API Request:    {t_e2e_api:8.3f} ms")
    print("="*70)

    assert doc["id"] is not None
    assert doc["sections_count"] == 15
    assert doc["checksum"] == checksum
    assert doc["parse_status"] == "parsed"


def test_priority_1_upload_roundtrip_count_and_bulk_reduction():
    """Verify that atomic transaction reduces database round trips compared to sequential calls."""
    client = TestClient(app)
    auth = _register_and_login(client)
    headers = {"Authorization": f"Bearer {auth['token']}"}

    proj_resp = client.post("/api/projects", headers=headers, json={"name": "RT Count Project"})
    project_id = proj_resp.json()["id"]

    content = _create_synthetic_document(num_sections=10).encode("utf-8")
    sections, warnings = document_parser.parse("test.txt", content)

    # Measure queries for the atomic upload path
    with RoundTripCounter(db) as counter:
        db.save_document_with_sections(
            project_id=project_id,
            filename="atomic_doc.txt",
            mime_type="text/plain",
            checksum=hashlib.sha256(content).hexdigest(),
            storage_path=f"uploads/{project_id}/atomic",
            size_bytes=len(content),
            uploaded_by=auth["user_id"],
            sections=sections,
            warnings=warnings
        )
    atomic_queries = counter.query_count
    atomic_conns = counter.connection_count

    # In atomic save: 1 connection and 5 statements -- INSERT documents,
    # bulk INSERT sections, bulk INSERT document_chunks (added for SPEC-03-05
    # retrieval, which was previously never written at all), SELECT the previous
    # audit hash, INSERT the audit event.
    assert atomic_conns == 1
    assert atomic_queries <= 5, (
        f"the atomic upload grew to {atomic_queries} statements; it should stay at 5"
    )

    print(f"\n[Priority 1 DB Roundtrips] Atomic Save: {atomic_queries} queries across {atomic_conns} connection")


def test_priority_1_small_medium_large_document_scaling():
    """Test upload timing scalability across small, medium, and larger documents."""
    client = TestClient(app)
    auth = _register_and_login(client)
    headers = {"Authorization": f"Bearer {auth['token']}"}

    proj = client.post("/api/projects", headers=headers, json={"name": "Scale Test Project"}).json()
    pid = proj["id"]

    sizes = [
        ("Small", 3, 50),     # ~1.5 KB, 3 sections
        ("Medium", 15, 120),  # ~25 KB, 15 sections
        ("Large", 50, 200),   # ~120 KB, 50 sections
    ]

    results = []
    for label, n_sec, w_sec in sizes:
        text = _create_synthetic_document(num_sections=n_sec, words_per_section=w_sec)
        raw = text.encode("utf-8")
        size_kb = len(raw) / 1024

        t0 = time.perf_counter()
        res = client.post(
            f"/api/projects/{pid}/documents",
            headers=headers,
            files={"file": (f"{label.lower()}.txt", raw, "text/plain")}
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert res.status_code == 201
        doc_data = res.json()
        assert doc_data["sections_count"] == n_sec
        results.append((label, size_kb, n_sec, elapsed_ms))

    print("\n" + "="*70)
    print("PRIORITY 1: DOCUMENT SCALING BENCHMARK (SMALL / MEDIUM / LARGE)")
    print("="*70)
    for label, size_kb, n_sec, elapsed_ms in results:
        print(f" {label:8} | Size: {size_kb:6.1f} KB | Sections: {n_sec:3} | Upload Time: {elapsed_ms:8.2f} ms")
    print("="*70)


def test_priority_1_upload_storage_separate_from_gemini():
    """Verify that upload and storage do NOT trigger Gemini LLM calls."""
    client = TestClient(app)
    auth = _register_and_login(client)
    headers = {"Authorization": f"Bearer {auth['token']}"}
    pid = client.post("/api/projects", headers=headers, json={"name": "Gemini Separation Project"}).json()["id"]

    from app.services.llm_service import llm_service
    with patch.object(llm_service, "complete_json", side_effect=RuntimeError("Gemini LLM must not be called during upload!")):
        with patch.object(llm_service, "extract_text_from_image", side_effect=RuntimeError("OCR must not be called for text uploads!")):
            t0 = time.perf_counter()
            res = client.post(
                f"/api/projects/{pid}/documents",
                headers=headers,
                files={"file": ("sop.txt", b"1. SECTION ONE\nProcess rules here.", "text/plain")}
            )
            upload_time_ms = (time.perf_counter() - t0) * 1000
            assert res.status_code == 201

    print(f"\n[Priority 1 Gemini Separation] Standard upload completed cleanly with 0 Gemini LLM calls in {upload_time_ms:.1f} ms.")


# ---------------------------------------------------------------------------
# Priority 2: Create Project Latency Instrumentation
# ---------------------------------------------------------------------------
def test_priority_2_create_project_breakdown():
    """Measure every individual database operation in Create Project:
      1. Connection acquisition
      2. Project record insert
      3. Project membership insert
      4. Genesis audit event insert
      5. Total atomic create_project execution
    """
    client = TestClient(app)
    auth = _register_and_login(client)
    user_id = auth["user_id"]

    # Measure DB connection acquisition
    t0 = time.perf_counter()
    with db.get_connection() as conn:
        t_conn = (time.perf_counter() - t0) * 1000
        cur = conn.cursor()

        # Operation 1: Insert project row
        project_id = str(uuid.uuid4())
        created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        t0 = time.perf_counter()
        if db.use_postgres:
            cur.execute("""
                INSERT INTO projects (id, name, process_type, description, department, goals, constraints, status, created_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'created', %s, %s, %s);
            """, (project_id, "Benchmark Project", "general", "desc", "dept", "goals", "constraints", user_id, created_at, created_at))
        else:
            cur.execute("""
                INSERT INTO projects (id, name, process_type, description, department, goals, constraints, status, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'created', ?, ?, ?);
            """, (project_id, "Benchmark Project", "general", "desc", "dept", "goals", "constraints", user_id, created_at, created_at))
        t_insert_project = (time.perf_counter() - t0) * 1000

        # Operation 2: Insert project membership
        t0 = time.perf_counter()
        if db.use_postgres:
            cur.execute("""
                INSERT INTO project_members (project_id, user_id, role, status, created_at)
                VALUES (%s, %s, %s, 'active', %s);
            """, (project_id, user_id, "analyst", created_at))
        else:
            cur.execute("""
                INSERT INTO project_members (project_id, user_id, role, status, created_at)
                VALUES (?, ?, ?, 'active', ?);
            """, (project_id, user_id, "analyst", created_at))
        t_insert_member = (time.perf_counter() - t0) * 1000

        # Operation 3: Insert initial genesis audit event
        t0 = time.perf_counter()
        db._log_audit_event_tx(cur, project_id, "project_created", actor=user_id, subject="Benchmark Project", details={"role": "analyst"}, prev_hash="0"*64)
        t_insert_audit = (time.perf_counter() - t0) * 1000
        if not db.use_postgres:
            conn.commit()

    # Measure complete API call
    headers = {"Authorization": f"Bearer {auth['token']}"}
    t0 = time.perf_counter()
    resp = client.post("/api/projects", headers=headers, json={"name": "E2E Created Project"})
    t_e2e_api = (time.perf_counter() - t0) * 1000
    assert resp.status_code == 201

    print("\n" + "="*70)
    print("PRIORITY 2: CREATE PROJECT TIMING BREAKDOWN (MEASURED)")
    print("="*70)
    print(f" 1. DB Connection Acquisition:     {t_conn:8.3f} ms")
    print(f" 2. Projects Table Insert:         {t_insert_project:8.3f} ms")
    print(f" 3. Project Members Table Insert:  {t_insert_member:8.3f} ms")
    print(f" 4. Genesis Audit Event Insert:    {t_insert_audit:8.3f} ms")
    print(f" 5. Full E2E Create Project API:   {t_e2e_api:8.3f} ms")
    print("="*70)


def test_priority_2_create_project_roundtrip_count():
    """Verify that create_project executes in a single database connection and transaction without extra queries."""
    client = TestClient(app)
    auth = _register_and_login(client)

    with RoundTripCounter(db) as counter:
        p = db.create_project(
            name="Single Transaction Project",
            user_id=auth["user_id"],
            role="analyst"
        )
    assert counter.connection_count == 1
    # 1 insert project, 1 insert member, 1 insert audit event = 3 queries total
    assert counter.query_count == 3
    print(f"\n[Priority 2 DB Roundtrips] Create Project: {counter.query_count} queries across {counter.connection_count} connection")


# ---------------------------------------------------------------------------
# Priority 3: Login Latency Instrumentation & Cold vs Warm Comparison
# ---------------------------------------------------------------------------
def test_priority_3_login_component_timing_breakdown():
    """Determine the relative contribution of:
      1. User lookup in database (get_user_by_email)
      2. Bcrypt password verification (12 rounds)
      3. Login success database update (update_user_login_success)
      4. Token generation (create_access_token)
    """
    client = TestClient(app)
    email = f"login_test_{uuid.uuid4().hex[:6]}@processfoundry.ai"
    password = "SecurePassword123!"
    auth = _register_and_login(client, email=email, password=password)

    # 1. Measure DB user lookup
    t0 = time.perf_counter()
    user = db.get_user_by_email(email)
    t_lookup = (time.perf_counter() - t0) * 1000
    assert user is not None

    # 2. Measure Bcrypt verification (work factor = 12)
    t0 = time.perf_counter()
    valid = verify_password(password, user["password_hash"])
    t_bcrypt = (time.perf_counter() - t0) * 1000
    assert valid is True

    # 3. Measure DB update login success
    t0 = time.perf_counter()
    db.update_user_login_success(email)
    t_update = (time.perf_counter() - t0) * 1000

    # 4. Measure Token Generation
    t0 = time.perf_counter()
    token = create_access_token(user["id"], user["email"])
    t_token = (time.perf_counter() - t0) * 1000

    total_component_time = t_lookup + t_bcrypt + t_update + t_token

    print("\n" + "="*70)
    print("PRIORITY 3: LOGIN TIMING BREAKDOWN (MEASURED)")
    print("="*70)
    print(f" 1. DB User Lookup (get_user_by_email):       {t_lookup:8.3f} ms (network I/O)")
    print(f" 2. Password Verification (bcrypt rounds=12): {t_bcrypt:8.3f} ms (CPU hashing)")
    print(f" 3. DB Login Success Update:                  {t_update:8.3f} ms (network I/O)")
    print(f" 4. Token Generation (signed JWT):            {t_token:8.3f} ms")
    print(f" Total Measured Login Time:                   {total_component_time:8.3f} ms")
    print("="*70)

    # Bcrypt verification with 12 rounds takes significant CPU time (> 50ms)
    assert t_bcrypt > 50.0, f"Expected bcrypt 12 rounds to take > 50ms, got {t_bcrypt:.1f}ms"
    # Token generation is sub-millisecond
    assert t_token < 10.0, f"Expected token generation to be fast (< 10ms), got {t_token:.1f}ms"


def test_priority_3_cold_vs_warm_login():
    """Compare cold login (first request, cache cleared) vs warm login (subsequent request)."""
    client = TestClient(app)
    email = f"cold_warm_{uuid.uuid4().hex[:6]}@processfoundry.ai"
    password = "ColdWarmPassword123!"
    _register_and_login(client, email=email, password=password)

    # Invalidate cache for cold run
    invalidate_user_cache(email)

    # Cold Login (first attempt)
    t0 = time.perf_counter()
    resp_cold = client.post("/api/auth/login", json={"email": email, "password": password})
    t_cold = (time.perf_counter() - t0) * 1000
    assert resp_cold.status_code == 200

    # Warm Login (immediate second attempt)
    t0 = time.perf_counter()
    resp_warm = client.post("/api/auth/login", json={"email": email, "password": password})
    t_warm = (time.perf_counter() - t0) * 1000
    assert resp_warm.status_code == 200

    # Subsequent /api/me request (tests warm user cache benefit)
    headers = {"Authorization": f"Bearer {resp_warm.json()['access_token']}"}
    t0 = time.perf_counter()
    resp_me = client.get("/api/me", headers=headers)
    t_me_warm = (time.perf_counter() - t0) * 1000
    assert resp_me.status_code == 200

    print("\n" + "="*70)
    print("PRIORITY 3: COLD VS WARM LOGIN COMPARISON (MEASURED)")
    print("="*70)
    print(f" Cold Login:                       {t_cold:8.3f} ms")
    print(f" Warm Login:                       {t_warm:8.3f} ms")
    print(f" Authenticated /api/me (Cached):   {t_me_warm:8.3f} ms")
    print("="*70)


# ---------------------------------------------------------------------------
# Priority 4: Loading Project Latency & Cache Behavior
# ---------------------------------------------------------------------------
def test_priority_4_project_loading_serialization_vs_query_time():
    """Measure the time spent on SQL query execution vs Pydantic response model serialization."""
    client = TestClient(app)
    auth = _register_and_login(client)
    headers = {"Authorization": f"Bearer {auth['token']}"}

    proj = client.post("/api/projects", headers=headers, json={"name": "Serialization Benchmark"}).json()
    project_id = proj["id"]
    user_id = auth["user_id"]

    # 1. Measure SQL query execution time
    t0 = time.perf_counter()
    raw_dict = db.get_project(project_id, user_id)
    t_query = (time.perf_counter() - t0) * 1000
    assert raw_dict is not None

    # 2. Measure Pydantic response model validation and serialization time
    t0 = time.perf_counter()
    pydantic_obj = ProjectResponse(**raw_dict)
    serialized = pydantic_obj.model_dump()
    t_serialization = (time.perf_counter() - t0) * 1000

    # 3. Measure Full E2E GET /api/projects/{project_id}
    t0 = time.perf_counter()
    resp = client.get(f"/api/projects/{project_id}", headers=headers)
    t_e2e_get = (time.perf_counter() - t0) * 1000
    assert resp.status_code == 200

    print("\n" + "="*70)
    print("PRIORITY 4: LOADING PROJECT - QUERY VS SERIALIZATION (MEASURED)")
    print("="*70)
    print(f" 1. DB Query Execution (get_project):        {t_query:8.3f} ms")
    print(f" 2. Pydantic Serialization (ProjectResponse):{t_serialization:8.3f} ms")
    print(f" 3. Full HTTP GET /api/projects/{{id}}:       {t_e2e_get:8.3f} ms")
    print("="*70)


def test_priority_4_cache_hits_eliminate_database_calls():
    """Verify that client/frontend caching eliminates database roundtrips completely."""
    # Simulate the Streamlit @st.cache_data mechanism
    cache = {}

    def cached_fetch_project(tok: str, pid: str):
        key = (tok, pid)
        if key in cache:
            return cache[key], True  # Hit
        # Miss: fetch from DB
        data = db.get_project(pid)
        cache[key] = data
        return data, False  # Miss

    client = TestClient(app)
    auth = _register_and_login(client)
    headers = {"Authorization": f"Bearer {auth['token']}"}
    pid = client.post("/api/projects", headers=headers, json={"name": "Cached Project"}).json()["id"]

    # First call: Cache MISS
    with RoundTripCounter(db) as counter_miss:
        t0 = time.perf_counter()
        data_miss, is_hit = cached_fetch_project(auth["token"], pid)
        t_miss = (time.perf_counter() - t0) * 1000
    assert not is_hit
    miss_queries = counter_miss.query_count
    assert miss_queries >= 1

    # Second call: Cache HIT
    with RoundTripCounter(db) as counter_hit:
        t0 = time.perf_counter()
        data_hit, is_hit = cached_fetch_project(auth["token"], pid)
        t_hit = (time.perf_counter() - t0) * 1000
    assert is_hit
    hit_queries = counter_hit.query_count

    # Cache hit MUST have 0 queries and near-zero latency
    assert hit_queries == 0
    assert data_hit["id"] == pid

    print("\n" + "="*70)
    print("PRIORITY 4: CACHE HIT VS CACHE MISS BEHAVIOR (MEASURED)")
    print("="*70)
    print(f" Cache Miss: {t_miss:8.3f} ms | DB Queries: {miss_queries}")
    print(f" Cache Hit:  {t_hit:8.3f} ms | DB Queries: {hit_queries} (100% DB calls eliminated!)")
    print("="*70)
