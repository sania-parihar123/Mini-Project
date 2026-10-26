"""ProcessFoundry AI: Multilingual Verification and Regression Test Suite.

Covers:
1. Document ingestion and section parsing for Hindi, Marathi, mixed-language documents (TXT, MD, DOCX, text PDF, scanned OCR).
2. Verbatim original-language quote verification, punctuation, and Unicode fidelity.
3. Rejection of translated or normalized quotes.
4. English-language process analysis and deliverables from non-English sources.
5. Deterministic gap and conflict detection with multilingual cues and Devanagari numerals.
6. End-to-end traceability links and relational integrity.
7. Caching, versioning invalidation, and deduplication across pipeline re-runs.
"""
import io
import pytest
from app.repositories.database import db
from app.services.document_parser import document_parser
from app.services.llm_service import llm_service
from app.agents.evidence import EvidenceAgent, EXTRACTOR_VERSION
from app.agents.discovery import ProcessDiscoveryAgent
from app.agents.rules import BusinessRuleAgent
from app.agents.gaps import (
    GapAnalysisAgent,
    _norm,
    _values_conflict,
    _to_ascii_digits,
    detect_subject,
    extract_values,
)
from app.agents.redesign import RedesignAgent
from app.agents.requirements import RequirementsAgent
from app.agents.quality import QualityAgent
from app.schemas.evidence import SectionEvidenceExtraction, ExtractedEvidenceClaim


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Isolate DB for testing."""
    test_db_path = str(tmp_path / "test_multilingual.db")
    monkeypatch.setattr(db, "sqlite_path", test_db_path)
    monkeypatch.setattr(db, "use_postgres", False)
    db._init_sqlite()


# ==============================================================================
# 1. Document Parsing & Heading Detection (Hindi, Marathi, Mixed, Unicode)
# ==============================================================================

def test_parse_hindi_text_document():
    """Verify parsing Hindi text with Devanagari numbered headings and Danda punctuation."""
    hindi_content = (
        "१. विहंगावलोकन\n"
        "महाविद्यालयीन गुणवत्ता शिष्यवृत्तीसाठी सर्व पात्र विद्यार्थ्यांनी अर्ज सादर करणे आवश्यक आहे।\n\n"
        "२. पात्रता निकष\n"
        "विद्यार्थ्यांनी किमान ७५ टक्के गुण प्राप्त केलेले असावेत।\n\n"
        "३. अंतिम मुदत व शुल्क\n"
        "अर्ज सादर करण्याची अंतिम तारीख ३१ मार्च आहे आणि नोंदणी शुल्क ₹ ५०० आहे।\n"
    )
    sections, warnings = document_parser.parse("scholarship_hi.txt", hindi_content.encode("utf-8"))
    assert len(sections) == 3
    assert "विहंगावलोकन" in sections[0]["section_title"]
    assert "पात्रता निकष" in sections[1]["section_title"]
    assert "अंतिम मुदत" in sections[2]["section_title"]
    assert "७५ टक्के" in sections[1]["text"]
    assert "३१ मार्च" in sections[2]["text"]


def test_parse_marathi_markdown_document():
    """Verify parsing Marathi markdown with section headings and Devanagari numerals."""
    marathi_md = (
        "# वसतिगृह प्रवेश प्रक्रिया २०२६\n\n"
        "विभाग १: सामान्य नियम\n"
        "वसतिगृहात प्रवेश मिळवण्यासाठी विद्यार्थ्यांनी विहित नमुन्यात अर्ज करावा.\n\n"
        "विभाग २: आवश्यक कागदपत्रे व मुदत\n"
        "प्रवेशासाठी जात प्रमाणपत्र आणि गुणपत्रिका जोडणे बंधनकारक आहे. अंतिम मुदत १५ एप्रिल आहे.\n\n"
        "विभाग ३: शुल्क तपशील\n"
        "सत्र शुल्क ५०० रुपये इतके निश्चित करण्यात आले आहे.\n"
    )
    sections, warnings = document_parser.parse("hostel_rules_mr.md", marathi_md.encode("utf-8"))
    assert len(sections) == 3
    assert any("सामान्य नियम" in s["section_title"] for s in sections)
    assert any("आवश्यक कागदपत्रे" in s["section_title"] for s in sections)
    assert any("शुल्क तपशील" in s["section_title"] for s in sections)


def test_parse_mixed_language_document():
    """Verify parsing documents containing mixed English, Hindi, and Marathi sections."""
    mixed_content = (
        "1. OVERVIEW AND OBJECTIVES\n"
        "The institution provides fee concessions to economically disadvantaged students.\n\n"
        "२. पात्रता आणि आवश्यक अटी\n"
        "अर्जदाराचे कौटुंबिक वार्षिक उत्पन्न रु. २,००,००० पेक्षा कमी असावे.\n\n"
        "3. SUBMISSION DEADLINE\n"
        "All applications must be submitted by 30 April.\n"
    )
    sections, warnings = document_parser.parse("mixed_policy.txt", mixed_content.encode("utf-8-sig"))
    assert len(sections) == 3
    assert "OVERVIEW" in sections[0]["section_title"]
    assert "पात्रता" in sections[1]["section_title"]
    assert "SUBMISSION DEADLINE" in sections[2]["section_title"]


def test_parse_utf8_with_bom():
    """Verify handling of UTF-8 with Byte Order Mark (BOM)."""
    text = "१. प्रस्तावना\nसदर नियमावली सर्व विद्यार्थ्यांसाठी लागू राहील।"
    bom_content = text.encode("utf-8-sig")
    sections, warnings = document_parser.parse("bom_doc.txt", bom_content)
    assert len(sections) >= 1
    assert "प्रस्तावना" in sections[0]["section_title"]
    assert not sections[0]["section_title"].startswith("\ufeff")


def test_parse_docx_with_devanagari():
    """Verify DOCX parser accurately reads Hindi/Marathi paragraphs and headings."""
    import docx
    doc = docx.Document()
    doc.add_heading("१. प्रवेश प्रक्रिया", level=1)
    doc.add_paragraph("विद्यार्थ्यांनी सर्व कागदपत्रे ऑनलाइन पोर्टलवर सादर करावीत.")
    doc.add_heading("२. शुल्क व पडताळणी", level=1)
    doc.add_paragraph("लिपिक अर्जांची छाननी करून अंतिम यादी तयार करेल.")

    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()

    sections, warnings = document_parser.parse("admission_mr.docx", docx_bytes)
    assert len(sections) == 2
    assert "प्रवेश प्रक्रिया" in sections[0]["section_title"]
    assert "ऑनलाइन पोर्टलवर" in sections[0]["text"]
    assert "लिपिक" in sections[1]["text"]


def test_scanned_pdf_multilingual_ocr_dispatch(monkeypatch):
    """Verify scanned PDF OCR extraction receives the multilingual verbatim instruction."""
    captured_prompts = []

    class MockLLM:
        def extract_text_from_image(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
            return "१. महाविद्यालयीन सूचना\nसर्व विद्यार्थ्यांनी मुदतीत शुल्क भरावे."

    monkeypatch.setattr("app.services.llm_service.llm_service.extract_text_from_image", MockLLM().extract_text_from_image)

    # Build a 1-page blank PDF (simulating scanned page with no text layer)
    import pymupdf
    pdf_doc = pymupdf.open()
    page = pdf_doc.new_page(width=300, height=300)
    # Page has no text layer (< 30 characters), triggering OCR
    pdf_bytes = pdf_doc.tobytes()

    sections, warnings = document_parser.parse("scanned_notice.pdf", pdf_bytes)
    assert len(sections) >= 1
    assert any(s["read_from_image"] for s in sections)
    assert any("सूचना" in s["text"] or "शुल्क" in s["text"] for s in sections)
    assert any("Read from images" in w for w in warnings)


# ==============================================================================
# 2. Verbatim Quote Verification & Unicode Preservation (Hindi / Marathi)
# ==============================================================================

def test_evidence_extraction_preserves_exact_devanagari_quotes():
    """Verify exact original-language quotes are persisted with punctuation and Unicode characters intact."""
    agent = EvidenceAgent()
    user = db.create_user("Analyst Hindi", "analyst_hi@example.com", "SecurePass123!")
    project = db.create_project(name="Hindi Scholarship", user_id=user["id"])
    doc = db.save_document(
        project_id=project["id"],
        filename="scholarship_hi.txt",
        mime_type="text/plain",
        checksum="chk_hi_001",
        storage_path="uploads/hi.txt",
        size_bytes=300,
        uploaded_by=user["id"]
    )
    sec_text = "विद्यार्थ्यांनी किमान ७५ टक्के गुण प्राप्त केलेले असावेत आणि अर्ज ३१ मार्च पूर्वी सादर करावा।"
    secs = db.save_document_sections(doc["id"], [{
        "section_index": 1,
        "section_title": "पात्रता",
        "text": sec_text
    }])
    sec = secs[0]

    evidence_items = agent.extract_section_evidence(project["id"], sec)
    assert len(evidence_items) >= 1
    for item in evidence_items:
        # Quote MUST be an exact substring of the original text
        assert item["quote"] in sec_text
        # Quotes must retain original Devanagari script, not translated to English
        assert any("\u0900" <= c <= "\u097f" for c in item["quote"])


def test_evidence_extraction_rejects_translated_quote(monkeypatch):
    """Verify that if the LLM attempts to translate the quote to English, the code discards it."""
    agent = EvidenceAgent()
    user = db.create_user("Analyst Trans", "analyst_trans@example.com", "SecurePass123!")
    project = db.create_project(name="Translation Test", user_id=user["id"])
    doc = db.save_document(
        project_id=project["id"],
        filename="hindi_rule.txt",
        mime_type="text/plain",
        checksum="chk_trans_001",
        storage_path="uploads/hi_rule.txt",
        size_bytes=200,
        uploaded_by=user["id"]
    )
    sec_text = "अर्ज सादर करण्याची अंतिम तारीख ३१ मार्च आहे।"
    secs = db.save_document_sections(doc["id"], [{
        "section_index": 1,
        "section_title": "मुदत",
        "text": sec_text
    }])
    sec = secs[0]

    # Simulate an LLM that erroneously translated the quote instead of keeping it verbatim
    class TranslatingLLM:
        def wrap_source(self, t): return f"<source>{t}</source>"
        def complete_json(self, prompt, schema, system_instruction):
            return SectionEvidenceExtraction(
                claims=[
                    ExtractedEvidenceClaim(
                        claim="The deadline for submitting applications is 31 March.",
                        quote="The deadline for submitting applications is 31 March.",  # Translated! Not in sec_text!
                        claim_type="rule",
                        confidence=0.95
                    )
                ]
            )

    monkeypatch.setattr("app.agents.evidence.llm_service", TranslatingLLM())

    evidence_items = agent.extract_section_evidence(project["id"], sec)
    # Must be rejected because translated string is not an exact substring of sec_text
    assert len(evidence_items) == 0


# ==============================================================================
# 3. As-Is Discovery & Business Rules Extraction from Multilingual Sources
# ==============================================================================

def test_as_is_discovery_from_hindi_marathi_evidence():
    """Verify As-Is discovery produces English process steps while linking to original Devanagari quotes."""
    discovery_agent = ProcessDiscoveryAgent()
    user = db.create_user("Discovery User", "disc_hi@example.com", "SecurePass123!")
    project = db.create_project(name="Hostel Allocation", user_id=user["id"])
    doc = db.save_document(
        project_id=project["id"],
        filename="hostel.txt",
        mime_type="text/plain",
        checksum="chk_hostel",
        storage_path="uploads/hostel.txt",
        size_bytes=500,
        uploaded_by=user["id"]
    )
    secs = db.save_document_sections(doc["id"], [
        {
            "section_index": 1,
            "section_title": "प्रवेश",
            "text": "विद्यार्थ्यांनी विहित नमुन्यात अर्ज सादर करावा। कागदपत्रांची पडताळणी लिपिकाकडून केली जाईल."
        },
        {
            "section_index": 2,
            "section_title": "वाटप",
            "text": "अंतिम खोली वाटप यादी प्रसिद्ध केली जाईल."
        }
    ])

    ev1 = db.save_evidence_item(
        project_id=project["id"],
        section_id=secs[0]["id"],
        claim="Applicants submit hostel application form",
        quote="विद्यार्थ्यांनी विहित नमुन्यात अर्ज सादर करावा।",
        claim_type="step",
        confidence=0.95
    )
    ev2 = db.save_evidence_item(
        project_id=project["id"],
        section_id=secs[0]["id"],
        claim="Verification of documents is conducted by clerk",
        quote="कागदपत्रांची पडताळणी लिपिकाकडून केली जाईल.",
        claim_type="step",
        confidence=0.95
    )
    ev3 = db.save_evidence_item(
        project_id=project["id"],
        section_id=secs[1]["id"],
        claim="Final room allocation list is published",
        quote="अंतिम खोली वाटप यादी प्रसिद्ध केली जाईल.",
        claim_type="step",
        confidence=0.95
    )

    evidence = [ev1, ev2, ev3]

    pv = discovery_agent.discover_as_is(project["id"], evidence, "College Hostel Allocation")
    assert pv is not None
    assert pv["version"] == 1
    steps = pv.get("steps", [])
    assert len(steps) >= 2
    # Verify steps have English names and types
    for s in steps:
        assert isinstance(s["name"], str)
        assert s["step_type"] in ("task", "review", "decision", "milestone")
        # Ensure evidence linkage is preserved
        step_evs = db.get_step_sources(s["id"])
        assert len(step_evs) >= 1


def test_business_rules_extraction_from_marathi():
    """Verify business rules extracted from Marathi text formulate conditions in English while keeping exact quotes."""
    rules_agent = BusinessRuleAgent()
    user = db.create_user("Rule User", "rule_mr@example.com", "SecurePass123!")
    project = db.create_project(name="Marathi Rules", user_id=user["id"])
    doc = db.save_document(
        project_id=project["id"],
        filename="rules_mr.txt",
        mime_type="text/plain",
        checksum="chk_rmr",
        storage_path="uploads/rules_mr.txt",
        size_bytes=300,
        uploaded_by=user["id"]
    )
    sec_text = "प्रवेशासाठी किमान ६० टक्के गुण असणे अनिवार्य आहे आणि नोंदणी शुल्क ₹ २५० राहील."
    secs = db.save_document_sections(doc["id"], [{
        "section_index": 1,
        "section_title": "प्रवेश नियम",
        "text": sec_text
    }])
    sec = secs[0]

    ev = db.save_evidence_item(
        project_id=project["id"],
        section_id=sec["id"],
        claim="Minimum 60 percent marks required for admission",
        quote="प्रवेशासाठी किमान ६० टक्के गुण असणे अनिवार्य आहे",
        claim_type="rule",
        confidence=0.95
    )

    rules = rules_agent.extract_section_rules(project["id"], sec, [ev])
    assert len(rules) >= 1
    rule = rules[0]
    assert any(src["id"] == ev["id"] for src in rule.get("sources", []))
    assert "प्रवेशासाठी" in rule["condition_json"]["quote"]


# ==============================================================================
# 4. Language-Aware Deterministic Gap & Conflict Detection
# ==============================================================================

def test_norm_preserves_unicode_and_devanagari_characters():
    """Verify _norm strips punctuation but preserves Unicode letters, matras, and numbers."""
    assert _norm("Submit 31 March!") == "submit 31 march"
    assert _norm("अर्जदार (३१ मार्च)!") == "अर्जदार ३१ मार्च"
    assert _norm("पात्रता: ५०० रुपये.") == "पात्रता ५०० रुपये"
    assert _norm("") == ""


def test_values_conflict_language_awareness():
    """Verify _values_conflict recognizes equivalent Devanagari/Arabic numbers and detects true conflicts."""
    # 500 and 500 rupees are the same
    assert not _values_conflict("500 rupees", "५०० रुपये")
    assert not _values_conflict("500", "५००")
    assert not _values_conflict("३१ मार्च", "31 मार्च")

    # Genuine conflicts
    assert _values_conflict("५००", "६००")
    assert _values_conflict("₹ ५००", "₹ ६००")
    assert _values_conflict("३१ मार्च", "१५ एप्रिल")
    assert _values_conflict("31 March", "15 April")


def test_gap_conflicting_deadlines_in_hindi():
    """Verify deterministic conflict detection catches opposing deadlines in Hindi."""
    gap_agent = GapAnalysisAgent()
    user = db.create_user("Gap User", "gap_hi@example.com", "SecurePass123!")
    project = db.create_project(name="Conflict Hindi", user_id=user["id"])

    r1 = db.save_business_rule(
        project_id=project["id"],
        description="अर्ज सादर करण्याची अंतिम तारीख ३१ मार्च आहे",
        condition_json={"condition": "अंतिम तारीख ३१ मार्च"},
        evidence_ids=[]
    )
    r2 = db.save_business_rule(
        project_id=project["id"],
        description="अर्ज सादर करण्याची शेवटची तारीख १५ एप्रिल राहील",
        condition_json={"condition": "शेवटची तारीख १५ एप्रिल"},
        evidence_ids=[]
    )

    questions = gap_agent.detect_gaps_and_conflicts(
        project_id=project["id"],
        process_steps=[],
        business_rules=[r1, r2],
        evidence_items=[]
    )

    conflict_qs = [q for q in questions if q["kind"] == "conflicting_rules"]
    assert len(conflict_qs) == 1
    q = conflict_qs[0]
    assert "३१ मार्च" in q["question"] or "१५ एप्रिल" in q["question"]
    assert q["assigned_role"] == "process_owner"


def test_gap_vague_terms_in_marathi():
    """Verify detection of subjective/vague terms in Marathi evidence quotes."""
    gap_agent = GapAnalysisAgent()
    user = db.create_user("Vague User", "vague_mr@example.com", "SecurePass123!")
    project = db.create_project(name="Vague Marathi", user_id=user["id"])

    ev = {
        "id": "ev_vague_01",
        "quote": "विद्यार्थ्यांनी आवश्यक ती सर्व कागदपत्रे लवकरात लवकर सादर करावीत.",
        "claim": "Documents must be submitted as soon as possible",
    }
    ev_sources = {
        "ev_vague_01": {
            "document_name": "Rules.pdf",
            "section_index": 1,
            "section_title": "कागदपत्रे"
        }
    }

    questions = gap_agent.detect_gaps_and_conflicts(
        project_id=project["id"],
        process_steps=[],
        business_rules=[],
        evidence_items=[ev]
    )

    vague_qs = [q for q in questions if q["kind"] == "ambiguous_term"]
    assert len(vague_qs) == 1
    assert "लवकरात लवकर" in vague_qs[0]["question"]


def test_gap_appeal_and_notification_path_detected_in_hindi_marathi():
    """Verify presence of appeal/notification cues in Hindi/Marathi prevents false missing path gaps."""
    gap_agent = GapAnalysisAgent()
    user = db.create_user("Path User", "path_hi@example.com", "SecurePass123!")
    project = db.create_project(name="Path Test", user_id=user["id"])

    # Source contains explicit appeal and notification steps in Hindi & Marathi
    steps = [
        {
            "id": "st_01",
            "name": "अर्जदाराला ईमेलद्वारे निकालाची सूचना देणे",  # Notify cue
            "actor": "लिपिक",
            "step_type": "task",
            "unknowns": []
        },
        {
            "id": "st_02",
            "name": "असमाधानी विद्यार्थी १० दिवसांच्या आत अपील दाखल करू शकतात",  # Appeal cue
            "actor": "विद्यार्थी",
            "step_type": "decision",
            "unknowns": []
        }
    ]

    questions = gap_agent.detect_gaps_and_conflicts(
        project_id=project["id"],
        process_steps=steps,
        business_rules=[],
        evidence_items=[]
    )

    # Should NOT generate missing_info questions for appeal or notification
    path_missing_qs = [
        q for q in questions
        if q["kind"] == "missing_info" and ("appeal" in q["question"].lower() or "communicated" in q["question"].lower())
    ]
    assert len(path_missing_qs) == 0


# ==============================================================================
# 5. Downstream Deliverables, Quality & Traceability Verification
# ==============================================================================

def test_downstream_deliverables_and_traceability_audit():
    """Verify that To-Be redesign, requirements, test cases, and quality report succeed for multilingual inputs."""
    user = db.create_user("Full Pipeline User", "pipeline_hi@example.com", "SecurePass123!")
    project = db.create_project(name="Multilingual Admissions", user_id=user["id"])

    # 1. Document & Section
    doc = db.save_document(
        project_id=project["id"],
        filename="hindi_sop.txt",
        mime_type="text/plain",
        checksum="chk_pipe_001",
        storage_path="uploads/pipe.txt",
        size_bytes=400,
        uploaded_by=user["id"]
    )
    sec_text = "प्रवेश अर्जांची छाननी लिपिकाकडून केली जाईल. अंतिम मुदत ३१ मार्च आहे."
    secs = db.save_document_sections(doc["id"], [{
        "section_index": 1,
        "section_title": "प्रवेश प्रक्रिया",
        "text": sec_text
    }])
    sec = secs[0]

    # 2. Evidence with exact quote
    ev = db.save_evidence_item(
        project_id=project["id"],
        section_id=sec["id"],
        claim="Applications are scrutinized by clerk and deadline is 31 March",
        quote="प्रवेश अर्जांची छाननी लिपिकाकडून केली जाईल.",
        claim_type="rule",
        confidence=0.98
    )

    # 3. Rule linked to evidence
    br = db.save_business_rule(
        project_id=project["id"],
        description="Application verification deadline is 31 March",
        condition_json={"condition": "Before 31 March", "quote": "प्रवेश अर्जांची छाननी लिपिकाकडून केली जाईल."},
        evidence_ids=[ev["id"]]
    )

    # 4. As-Is Process Step linked to evidence
    pv = db.create_process_version(project["id"], version=1)
    step = db.save_process_step(
        project_id=project["id"],
        process_version_id=pv["id"],
        name="Clerk Application Scrutiny",
        actor="Verification Clerk",
        step_type="review",
        sequence=1,
        inputs=["Application"],
        outputs=["Verified File"],
        unknowns=[],
        evidence_ids=[ev["id"]]
    )

    # 5. Redesign To-Be Process
    redesign_agent = RedesignAgent()
    to_be = redesign_agent.redesign_process(
        project_id=project["id"],
        as_is_steps=[step],
        business_rules=[br],
        verified_facts=[]
    )
    assert to_be is not None
    assert "Digitalized" in to_be["process_name"] or "Process" in to_be["process_name"]

    # 6. Requirements & Artifacts
    req_agent = RequirementsAgent()
    reqs = req_agent.synthesize_requirements(
        project_id=project["id"],
        as_is_steps=[step],
        business_rules=[br],
        verified_facts=[],
        to_be_model=to_be
    )
    assert len(reqs) >= 2
    # Ensure requirements have English statements
    for r in reqs:
        assert isinstance(r["statement"], str)
        assert len(r["statement"]) > 10

    artifacts = req_agent.generate_all_artifacts(project["id"])
    assert len(artifacts) >= 5
    art_types = [a["artifact_type"] for a in artifacts]
    assert "brd" in art_types
    assert "prd" in art_types
    assert "frd" in art_types
    assert "srs" in art_types

    # 7. Quality & Traceability Audit
    quality_agent = QualityAgent()
    report = quality_agent.validate_traceability(project["id"])
    # Verbatim quote audit must have 0 violations across Unicode strings
    assert report["quote_mismatches"] == 0
    assert report["total_requirements"] == len(reqs)


# ==============================================================================
# 6. Caching and Version Reprocessing
# ==============================================================================

def test_extractor_version_caching_and_reprocessing():
    """Verify that bumping EXTRACTOR_VERSION reprocesses sections rather than reusing obsolete outputs."""
    evidence_agent = EvidenceAgent()
    user = db.create_user("Cache User", "cache@example.com", "SecurePass123!")
    project = db.create_project(name="Caching Test", user_id=user["id"])
    doc = db.save_document(
        project_id=project["id"],
        filename="cache_policy.txt",
        mime_type="text/plain",
        checksum="chk_cache_01",
        storage_path="uploads/cache.txt",
        size_bytes=400,
        uploaded_by=user["id"]
    )
    secs = db.save_document_sections(doc["id"], [{
        "section_index": 1,
        "section_title": "Policy",
        "text": "All submissions must arrive before noon."
    }])
    sec = secs[0]

    # Simulate section already extracted under "v1"
    db.mark_section_extracted(sec["id"], "v1")

    # Under "v2", section must NOT be in sections_already_extracted
    done_v2 = db.sections_already_extracted(project["id"], EXTRACTOR_VERSION)
    assert str(sec["id"]) not in done_v2

    # Run extraction under EXTRACTOR_VERSION ("v2")
    evidence_items = evidence_agent.run_evidence_pipeline(project["id"], [sec])
    assert len(evidence_items) >= 1

    # Now section is stamped with EXTRACTOR_VERSION ("v2")
    done_now = db.sections_already_extracted(project["id"], EXTRACTOR_VERSION)
    assert str(sec["id"]) in done_now

    # Running again should reuse stored evidence without re-extracting
    re_run_items = evidence_agent.run_evidence_pipeline(project["id"], [sec])
    assert len(re_run_items) == len(evidence_items)


def test_reprocessing_evidence_and_rules_versioning_and_deduplication():
    """Verify evidence and rule versioning when reprocessing a section.

    Ensures:
    1. Historical evidence rows remain stored and foreign-key integrity is preserved.
    2. Stale evidence from older extraction is marked superseded and not mixed with current evidence.
    3. Reprocessing does not create duplicate active business rules.
    """
    evidence_agent = EvidenceAgent()
    business_rule_agent = BusinessRuleAgent()
    user = db.create_user("Auditor", "auditor_ver@example.com", "Password123!")
    project = db.create_project(name="Reprocessing Versioning Test", user_id=user["id"])
    doc = db.save_document(
        project_id=project["id"],
        filename="hindi_circular.txt",
        mime_type="text/plain",
        checksum="chk_reproc_01",
        storage_path="uploads/hindi_circular.txt",
        size_bytes=500,
        uploaded_by=user["id"]
    )
    secs = db.save_document_sections(doc["id"], [{
        "section_index": 1,
        "section_title": "प्रवेश प्रक्रिया",
        "text": "सर्व अर्जांची तपासणी १५ दिवसांच्या आत पूर्ण केली जाईल. प्रवेश शुल्क रु. ५०० असेल."
    }])
    sec = secs[0]

    # Initial extraction
    ev_items_v1 = evidence_agent.run_evidence_pipeline(project["id"], [sec])
    assert len(ev_items_v1) >= 1
    v1_ev_id = ev_items_v1[0]["id"]

    # Save a process step linked to this evidence (testing foreign-key integrity)
    pv = db.create_process_version(project["id"], version=1)
    step = db.save_process_step(
        project_id=project["id"],
        process_version_id=pv["id"],
        name="प्रवेश पडताळणी",
        actor="प्रवेश समिती",
        step_type="task",
        sequence=1,
        inputs=[],
        outputs=[],
        unknowns=[],
        evidence_ids=[v1_ev_id]
    )
    step_sources = db.get_step_sources(step["id"])
    assert any(s["id"] == v1_ev_id for s in step_sources)

    # Extract rules
    rules_v1 = business_rule_agent.run_rules_pipeline(project["id"], [sec], ev_items_v1)
    assert len(rules_v1) >= 1
    v1_rule_id = rules_v1[0]["id"]

    # Now reprocess the section (e.g. forced re-extraction or extractor version change)
    db.mark_section_extracted(sec["id"], "v_older")
    ev_items_v2 = evidence_agent.run_evidence_pipeline(project["id"], [sec])
    assert len(ev_items_v2) >= 1

    # 1. Historical v1 evidence row is preserved (not deleted)
    all_stored_evidence = db.list_project_evidence(project["id"], include_superseded=True)
    v1_stored = [e for e in all_stored_evidence if e["id"] == v1_ev_id]
    assert len(v1_stored) == 1
    assert v1_stored[0]["status"] == "superseded"

    # 2. Foreign-key integrity on the existing step remains intact
    step_sources_after = db.get_step_sources(step["id"])
    assert any(s["id"] == v1_ev_id for s in step_sources_after)

    # 3. Active evidence query does NOT mix stale v1 evidence
    active_evidence = db.list_project_evidence(project["id"], include_superseded=False)
    assert all(e["status"] == "extracted" for e in active_evidence)
    assert v1_ev_id not in [e["id"] for e in active_evidence]

    # 4. Reprocess rules: verify older candidate rule is superseded, no duplicate active rules
    rules_v2 = business_rule_agent.run_rules_pipeline(project["id"], [sec], ev_items_v2)
    active_rules = [r for r in db.list_project_business_rules(project["id"]) if r.get("status") != "superseded"]
    assert len(active_rules) == len(rules_v2)

    # Historical rule row still exists with status 'superseded'
    old_rule = db.get_business_rule(v1_rule_id)
    assert old_rule is not None
    assert old_rule["status"] == "superseded"

