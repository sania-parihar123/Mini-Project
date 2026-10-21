# 02 LLM Service Gateway
Status: agreed
Source: Part 2.1, Part 6 Phase 0 Step 3, Part 9.2 [BASELINE + EXTENSION]

## Purpose
Provide a single, resilient model gateway that enforces structured JSON schema output, rate limiting, bounded retries, temperature control, and a mock/fake model mode for zero-cost automated tests.

## Requirements
- SPEC-02-01 All calls to LLMs shall pass through one service gateway (`app/services/llm_service.py`).
- SPEC-02-02 The gateway shall support Google Gemini as the primary provider via `LLM_PROVIDER=gemini`, using `google-genai` SDK and reading `LLM_API_KEY` and `LLM_MODEL` from environment variables.
- SPEC-02-03 The gateway shall support a deterministic `fake` / `mock` provider (`LLM_PROVIDER=mock`) used by automated test suites without external API keys or network latency.
- SPEC-02-04 Document excerpts sent to the model shall be wrapped in `<source>...</source>` tags and explicitly instructed as untrusted data rather than prompt instructions.
- SPEC-02-05 The service shall enforce bounded retries (maximum 2 retries on rate limits or invalid JSON schemas) and fail with clear, actionable error messages.
- SPEC-02-06 Prompt logs and error messages shall never expose `LLM_API_KEY`, plain passwords, or full sensitive document bodies.

## Acceptance criteria
- AC-02-01 (covers SPEC-02-01/02) Given valid Gemini configuration in environment variables, when `complete_json` is invoked with a prompt and Pydantic schema, then the response validates against the schema.
- AC-02-02 (covers SPEC-02-03) Given `LLM_PROVIDER=mock` or an empty `LLM_API_KEY`, when test suites execute, then mocked structured responses are returned deterministically and pytest completes without external network calls.
- AC-02-03 (covers SPEC-02-04) Given input text containing prompt injection attempts (e.g. "Ignore previous instructions"), when parsed by the gateway, the delimiters and system prompt isolate it as content only.
- AC-02-04 (covers SPEC-02-05) Given a malformed model JSON response, when retried twice and failing, then a structured `LLMValidationError` is raised.

## Design notes
- Files: `app/services/llm_service.py`, `app/core/config.py`.
- Interface: `complete_json(prompt: str, schema: Type[BaseModel], system_instruction: str = None) -> BaseModel`.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-02-01
  - `test_unchanged_sections_cost_no_model_calls_on_a_re_run` (`tests/test_full_loop_e2e.py`)
  - `test_an_unknown_provider_is_refused` (`tests/test_llm_configuration.py`)
  - `test_understanding_is_computed_once_per_document_content` (`tests/test_llm_configuration.py`)
- SPEC-02-02
  - `test_an_unknown_provider_is_refused` (`tests/test_llm_configuration.py`)
  - `test_gemini_without_a_key_is_refused_at_startup` (`tests/test_llm_configuration.py`)
  - `test_there_is_no_silent_fallback_from_gemini_to_mock` (`tests/test_llm_configuration.py`)
  - `test_gemini_provider_fails_without_silent_mock_fallback` (`tests/test_new_features.py`)
- SPEC-02-03
  - `test_mock_ocr_output_says_it_is_not_from_the_document` (`tests/test_llm_configuration.py`)
  - `test_mock_provider_is_allowed_in_a_test_environment` (`tests/test_llm_configuration.py`)
  - `test_mock_provider_is_refused_outside_a_test_environment` (`tests/test_llm_configuration.py`)
- SPEC-02-04
  - `test_document_text_is_wrapped_in_source_delimiters` (`tests/test_spec_coverage.py`)
  - `test_the_system_prompt_says_source_text_is_not_instructions` (`tests/test_spec_coverage.py`)
- SPEC-02-05
  - `test_the_configured_timeout_is_not_ignored` (`tests/test_llm_configuration.py`)
  - `test_the_gateway_caps_concurrent_calls_and_paces_them` (`tests/test_llm_configuration.py`)
- SPEC-02-06
  - `test_understanding_quotes_are_verified_against_the_source` (`tests/test_llm_configuration.py`)
