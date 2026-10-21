# 03 Ingestion
Status: agreed
Source: Part 3.1 (A1), Part 4.6, Part 5.2, Part 6 Step 5 [BASELINE]

## Purpose
Deterministically parse uploaded source documents (PDF, DOCX, TXT), detect section boundaries by headings, extract text without loss, calculate SHA-256 checksums, and store structured sections and searchable chunks in the database.

## Requirements
- SPEC-03-01 The system shall support PDF (`.pdf`), Microsoft Word (`.docx`), and Plain Text (`.txt`) file ingestion.
- SPEC-03-02 Unsupported or corrupted file uploads shall be rejected with clear descriptive errors on the server.
- SPEC-03-03 The parser shall detect section headings (numbered sections like "1. ELIGIBILITY", ALL-CAPS lines, and markdown headings `#`) to segment documents into ordered `document_sections`.
- SPEC-03-04 Uploaded documents shall be hashed with SHA-256 (`checksum`), and stored on disk under `uploads/<project_id>/<uuid>` rather than using user-supplied filenames.
- SPEC-03-05 The parser shall generate `document_chunks` with full-text search capability for retrieval.

## Acceptance criteria
- AC-03-01 (covers SPEC-03-01/03) Given a valid text or markdown document containing sections "1. OVERVIEW" and "2. DEADLINE", when parsed, then `document_sections` has 2 records with matching titles and sequential indices.
- AC-03-02 (covers SPEC-03-02) Given an invalid file or unsupported file type (e.g. `.exe` or corrupt binary), when uploaded, the server returns an HTTP 400 error stating the file format is invalid.
- AC-03-03 (covers SPEC-03-04) Given an uploaded document, the stored filename in the file system uses a generated UUID path and not the original client-provided filename.

## Design notes
- Files: `app/services/document_parser.py`, `app/api/documents.py`.
- Libraries: `pymupdf` (for PDF), `python-docx` (for DOCX), standard Python string/regex parsers for TXT/MD.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-03-01
  - `test_fixture_parsing_detects_all_sections` (`tests/test_fixtures.py`)
  - `test_scanned_pdf_triggers_image_extraction_and_warning` (`tests/test_new_features.py`)
  - `test_parse_text_sections_numbered_and_caps` (`tests/test_parsing.py`)
  - `test_markdown_is_accepted` (`tests/test_uploads.py`)
  - `test_several_files_upload_at_once_with_one_result_line_each` (`tests/test_uploads.py`)
  - `test_unsupported_extension_lists_every_accepted_type` (`tests/test_uploads.py`)
- SPEC-03-02
  - `test_a_whitespace_only_document_is_rejected_by_the_parser` (`tests/test_llm_configuration.py`)
  - `test_an_empty_document_is_an_error_not_a_summary` (`tests/test_llm_configuration.py`)
  - `test_empty_document_rejection` (`tests/test_new_features.py`)
  - `test_unsupported_file_format_rejected` (`tests/test_parsing.py`)
  - `test_a_failing_file_does_not_stop_the_others` (`tests/test_uploads.py`)
  - `test_a_fake_pdf_is_refused` (`tests/test_uploads.py`)
  - `test_a_text_file_with_null_bytes_is_refused` (`tests/test_uploads.py`)
  - `test_mime_type_is_validated_not_just_the_extension` (`tests/test_uploads.py`)
  - `test_oversize_upload_is_rejected_without_buffering_everything` (`tests/test_uploads.py`)
  - `test_unsupported_extension_lists_every_accepted_type` (`tests/test_uploads.py`)
- SPEC-03-03
  - `test_fixture_parsing_detects_all_sections` (`tests/test_fixtures.py`)
  - `test_parse_text_sections_numbered_and_caps` (`tests/test_parsing.py`)
- SPEC-03-04
  - `test_fixture_document_sha256_checksum_is_deterministic` (`tests/test_fixtures.py`)
  - `test_understanding_cache_is_keyed_on_the_content_checksum` (`tests/test_llm_configuration.py`)
  - `test_parse_text_checksum` (`tests/test_parsing.py`)
  - `test_a_rejected_upload_leaves_no_file_on_disk` (`tests/test_uploads.py`)
  - `test_duplicate_content_is_reported_not_a_500` (`tests/test_uploads.py`)
  - `test_duplicate_in_a_batch_is_reported_per_file` (`tests/test_uploads.py`)
  - `test_the_client_filename_is_never_used_as_a_path` (`tests/test_uploads.py`)
- SPEC-03-05
  - `test_uploading_a_document_creates_searchable_chunks` (`tests/test_spec_coverage.py`)
