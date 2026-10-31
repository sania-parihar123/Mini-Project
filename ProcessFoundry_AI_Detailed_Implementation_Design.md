# ProcessFoundry AI
## Detailed System Design and One-Month Implementation Guide

**Document type:** Student-friendly system design and implementation specification  
**Project duration:** 1 month  
**Product scope:** Reusable platform for analyzing, redesigning, and digitalizing any college process  
**Recommended MVP UI:** Streamlit  
**Backend:** Python + FastAPI  
**Agent orchestration:** LangGraph  
**Persistence:** PostgreSQL; pgvector is optional for the first MVP  
**Document status:** Implementation baseline. The team should follow this design and record any deliberate deviations.

---

## 1. Project summary

ProcessFoundry AI is a platform that helps a college understand an existing process, improve it, and prepare the documents and workflow needed to digitalize it.

A user can select or describe **any college process**, provide relevant documents, and answer questions about how the process works. The platform then:

1. Extracts evidence from the supplied material.
2. Maps the current process (As-Is).
3. identifies missing, unclear, or conflicting rules.
4. Asks a human to clarify important unknowns.
5. Proposes a redesigned process (To-Be).
6. Classifies each activity as conventional software automation, AI-assisted work, human work, or a combination.
7. Generates linked requirements and engineering artifacts.
8. Creates a workflow preview and test/UAT pack.
9. Keeps links between source evidence, rules, requirements, workflow steps, and tests.

The platform is **not limited to scholarships or any other single process**. Example processes include admissions, examination/revaluation, certificate requests, internship NOCs, student-record corrections, hostel applications, scholarships, faculty approvals, and other administrative processes. These are examples, not separate hard-coded products.

### 1.1 What “agentic” means in this project

An AI agent is a software component that uses a language model to perform a defined task and may call approved tools. Agentic does not mean that the AI should make every decision or that every process step needs an LLM.

Use:
- **Deterministic code** for validations, calculations, permissions, status transitions, and other rules that must behave predictably.
- **AI agents** for interpreting documents, summarizing evidence, suggesting process improvements, drafting requirements, and creating candidate test scenarios.
- **Human approval** for unclear policy, conflicting source material, official process changes, and final acceptance.

The model proposes; application code validates; an authorized person approves important business decisions.

### 1.2 One-month delivery target

Deliver a working MVP demonstrated end-to-end on **one process selected by the team**. The underlying data model and agent pipeline must be process-independent. Do not attempt production-grade support for every college process in one month.

---

## 2. Scope and boundaries

### 2.1 In scope for the MVP

- Create a process project with a name, description, department, and stakeholders.
- Upload a small set of PDF, DOCX, or TXT source files.
- Extract text and store source metadata.
- Record source evidence and page/section references where available.
- Create a structured As-Is process model.
- Extract candidate business rules, actors, conditions, exceptions, and approvals.
- Identify missing information and potential contradictions.
- Ask clarification questions and store human answers.
- Generate a To-Be process proposal and automation assessment.
- Generate an initial set of documents from the shared approved project model.
- Allow users to view, edit, and approve artifacts.
- Produce a workflow preview, test cases, and UAT scenarios.
- Track artifact versions and source-to-requirement-to-test traceability.
- Run basic validation and tests.

### 2.2 Out of scope for the first month

- Production deployment for an entire university.
- Live integration with the college SIS/ERP, payment gateway, identity system, or government portals.
- Autonomous approval/rejection of student applications.
- Automatically changing official college policies.
- Generating a complete production application for every process.
- Perfect extraction from scanned documents, handwriting, or complex image-heavy files.
- Multi-tenant enterprise access control and enterprise-grade audit/compliance features.

These can be future extensions. The demo should use synthetic or approved non-sensitive data.

---

## 3. Documents the platform should generate

The agents generate **draft artifacts from one shared structured model**, not separate documents based on unrelated prompts. Each artifact must identify its status (Draft, Needs Clarification, Reviewed, or Approved), version, creation time, and source links.

Terminology varies by organization. If “OPRD” is used by the college, ask the user which template/meaning they expect and configure it; do not assume every organization uses the acronym identically.

| Artifact | What it contains | MVP priority |
|---|---|---|
| Process Discovery / As-Is Report | Current steps, actors, inputs, outputs, handoffs, pain points, evidence | Must have |
| Process Redesign / To-Be Specification | Proposed steps, decision points, exceptions, roles, controls, reasons for changes | Must have |
| Business Requirements Document (BRD) | Business problem, objectives, scope, stakeholders, business needs, success measures, assumptions and constraints | Must have |
| Functional Requirements Document (FRD) | System functions, rules, validations, roles, workflow behavior, notifications, exceptions | Must have |
| Product Requirements Document (PRD) | Users, problems, goals, features, user stories, priorities, acceptance criteria | Must have |
| Software Requirements Specification (SRS) | Consolidated functional and non-functional requirements, interfaces, constraints, quality attributes | If time permits |
| OPRD / Operational Requirements | Operational goals, responsibilities, service expectations, support and operating constraints, based on an agreed template | Optional/configurable |
| Business Rules Catalogue | Rule ID, rule text, condition, outcome, source, confidence, approval status | Must have |
| Roles and Permissions Matrix | Role, permitted actions, data access, approval responsibilities | Must have |
| Data Model / ERD | Entities, attributes, relationships, constraints, candidate schema | Must have |
| Solution Architecture / HLD | Components, integrations, deployment view, data flow, trust boundaries | Must have |
| API Specification | Endpoint, method, input/output schema, validation, errors | If time permits |
| Test Plan and Test Cases | Test IDs, linked requirements/rules, preconditions, steps, expected results, negative and edge cases | Must have |
| UAT Pack | Business scenarios, user journeys, acceptance criteria, reviewer outcome | Must have |
| Workflow JSON / Preview | Machine-readable steps, transitions, decision points, owners, automation classification | Must have |
| Traceability Matrix | Source → evidence → rule → requirement → workflow step → test/UAT | Must have |

**Generation rule:** Generate these from the same canonical project model. For example, if an approved requirement changes, mark related artifacts as “Needs regeneration/review” rather than silently leaving inconsistent versions.

---

## 4. Users and main user journey

### 4.1 Roles

- **Process Owner:** Explains the real process and approves business rules and proposed changes.
- **Analyst / Student Team Member:** Sets up a project, uploads evidence, reviews outputs, and manages clarification.
- **Technical Reviewer:** Reviews architecture, data model, API, and test artifacts.
- **System:** Runs extraction, retrieval, validation, and agent graph execution.

For the MVP, these can be simple role labels rather than a full identity-management system.

### 4.2 End-to-end journey

1. Create a project and describe the process to improve.
2. Upload relevant SOPs, forms, spreadsheets converted to CSV if needed, and sample policy documents.
3. Review extracted evidence and correct obvious parsing errors.
4. Run process discovery to build the As-Is model.
5. Review extracted rules and questions. Resolve conflicts with the process owner.
6. Generate the To-Be proposal and automation assessment.
7. Review and approve the core process model.
8. Generate BRD, FRD, PRD, business rules, roles, data model, architecture, tests, and UAT.
9. Review artifacts and traceability links.
10. Preview the proposed workflow and export the artifact pack.

---

## 5. System architecture

### 5.1 Recommended technology choices

| Layer | Choice | Why |
|---|---|---|
| UI | Streamlit | Fast Python-based multi-page interface; avoids building and maintaining a separate frontend during the one-month MVP |
| API / service layer | FastAPI | Typed request/response models and straightforward REST endpoints |
| Agent graph | LangGraph | Explicit graph state, conditional routing, retries, and human-in-the-loop pause/resume |
| LLM access | One model provider/SDK initially | Keeps setup and debugging small; select a model the team can access and afford |
| Structured validation | Pydantic | Validate model outputs before saving them |
| Database | PostgreSQL | Projects, evidence metadata, process models, artifacts, approvals, and versions |
| Semantic retrieval | pgvector, optional | Adds vector similarity search if semantic retrieval is needed; do not let it delay the first vertical slice |
| Document extraction | PyMuPDF for PDFs; python-docx for DOCX; standard parsing for TXT | Use mature libraries instead of writing parsers |
| Tests | pytest | Repeatable unit and API tests |
| Version control | Git + GitHub/GitLab | Branches, reviews, issues, and team coordination |

**Do not add LiteLLM, a separate React frontend, CopilotKit, AG-UI, a message queue, or microservices unless the team has a clear need.** For one month, a single Python repository and Streamlit UI are the recommended baseline. The backend and agent graph should be separated from UI code so a richer UI can be added later.

### 5.2 Architecture diagram

```mermaid
flowchart TD
    U[Process Owner / Analyst] --> UI[Streamlit UI]
    UI --> API[FastAPI Service Layer]
    API --> AUTH[Project and Input Validation]
    AUTH --> GRAPH[LangGraph Orchestrator]
    GRAPH --> ING[Document Ingestion and Evidence]
    GRAPH --> DISC[Discovery and Rule Analysis]
    GRAPH --> GAP[Gap and Conflict Detection]
    GAP -->|Questions needed| HITL[Human Clarification / Approval]
    HITL --> GRAPH
    GAP -->|Sufficient verified inputs| RED[Process Redesign and Automation Assessment]
    RED --> APPROVE[Human Review of To-Be Model]
    APPROVE --> GEN[Artifact Generation Nodes]
    GEN --> QA[Validation and Traceability Checks]
    QA -->|Invalid or incomplete| GEN
    QA -->|Validated drafts| STORE[(PostgreSQL)]
    ING --> STORE
    DISC --> STORE
    GRAPH --> LLM[Configured LLM]
    ING --> FILES[(Original Files / Extracted Text)]
    UI --> STORE
```

This is a logical view. In the MVP, these components can run as modules in one application; they do not need to be deployed as separate services.

### 5.3 Code boundaries

- `ui/` must contain Streamlit pages and presentation logic only.
- `api/` must contain FastAPI routes and request/response handling.
- `graph/` must contain LangGraph construction, state, nodes, and routing.
- `agents/` must contain focused task implementations/prompts.
- `services/` must contain document parsing, retrieval, artifact export, and deterministic validation.
- `schemas/` must contain Pydantic models.
- `repositories/` must contain database access.
- `tests/` must contain unit, API, and graph tests.

---

## 6. Agent catalogue: exact responsibilities

Implement the following as **focused graph nodes/modules**. A node does not have to be a separate autonomous agent. In a short project, use an LLM only when reasoning or language generation is needed; ordinary parsing and validation should remain normal Python functions.

| ID | Agent / node | Input | Responsibilities | Output |
|---|---|---|---|---|
| A0 | Orchestrator / Supervisor | User task + graph state | Selects next node from explicit status and validation results; enforces allowed transitions; does not invent business rules | Next graph route |
| A1 | Document Ingestion | Uploaded file metadata | Calls deterministic parsers, extracts text, page/section metadata, headings and tables where possible | Extracted document sections |
| A2 | Evidence Structuring | Extracted sections | Identifies candidate process steps, actors, dates, forms, rules and source quotations; each claim includes source reference | Evidence records |
| A3 | Process Discovery | Evidence records + user description | Builds current As-Is steps, actors, handoffs, decisions, inputs/outputs and pain points | As-Is process model |
| A4 | Business Rule Analysis | Evidence records + As-Is model | Extracts candidate rules, conditions, exceptions, deadlines, approvals and consequences | Candidate rule catalogue |
| A5 | Gap and Conflict Analysis | Evidence + rules + process model | Finds missing details, contradictions, ambiguous terms, unsupported claims, duplicate steps and unanswered questions | Issues and clarification questions |
| A6 | Clarification / HITL Handler | Questions + user answers | Presents prioritized questions, records answers and who approved them, links answers to affected issues | Resolved issues / verified facts |
| A7 | Process Redesign | Verified As-Is model + rules + issues | Suggests removing, combining, parallelizing, simplifying or reordering steps; explains why and what evidence supports each change | Candidate To-Be model |
| A8 | Automation Assessment | To-Be steps + rules | Classifies steps as deterministic automation, AI-assisted, human decision, or hybrid; records risks, rationale and required controls | Automation assessment |
| A9 | Requirements Engineering | Approved To-Be model + verified rules + stakeholders | Generates BRD, FRD, PRD and candidate SRS sections from canonical data; links every requirement to rules/evidence | Structured requirements + document drafts |
| A10 | Data and Architecture Design | Approved requirements + workflow | Proposes entities, relationships, system components, boundaries and integrations; does not claim unavailable integrations exist | Data model + HLD drafts |
| A11 | Workflow / Prototype Generator | Approved To-Be model + requirements | Produces validated workflow JSON and a simple visual preview; optionally creates a basic form/prototype from a template | Workflow artifact / prototype |
| A12 | Test and UAT Generator | Requirements + rules + workflow | Generates positive, negative, boundary, exception, permission and business-journey tests; links each test to requirement IDs | Test cases + UAT pack |
| A13 | Quality and Traceability Validator | All candidate artifacts | Checks required fields, duplicate IDs, missing evidence links, broken references, inconsistent rules, and coverage gaps | Validation report and repair list |
| A14 | Artifact Exporter | Validated artifacts | Exports Markdown and JSON files; records artifact version and status | Downloadable artifact pack |

### 6.1 Which agents are mandatory in one month?

**Build first:** A0, A1, A2, A3, A4, A5, A6, A7, A9, A11, A12, A13, A14.

**Implement as simple deterministic modules initially:** A8 classification validation, A10 data/architecture templates, document versioning, IDs, traceability checks, export.

Do not create fourteen independent LLM agents merely because there are fourteen rows. A1, IDs, validation, exports, and persistence are mostly deterministic. Keep the LLM workflow small and controlled.

### 6.2 Agent input/output contract

Every reasoning node should:
1. Receive a defined Pydantic input model or a specific subset of graph state.
2. Use only authorized evidence and approved tools.
3. Return a structured object matching a Pydantic schema.
4. Include evidence references for claims derived from source material.
5. Mark unsupported details as unknown, assumption, or question.
6. Never mark its own output “Approved.”
7. Save errors and validation findings in a consistent format.

Do not pass an unlimited chat transcript and ask an agent to “do everything.” Pass only the context it needs.

---

## 7. Orchestration design

### 7.1 Graph state

Define a typed `ProcessFoundryState` containing at least:

```python
class ProcessFoundryState(TypedDict, total=False):
    project_id: str
    process_description: str
    source_document_ids: list[str]
    extracted_sections: list[dict]
    evidence_items: list[dict]
    as_is_process: dict
    candidate_rules: list[dict]
    issues: list[dict]
    clarification_answers: list[dict]
    verified_facts: list[dict]
    to_be_process: dict
    automation_assessment: list[dict]
    requirements: list[dict]
    artifacts: list[dict]
    validation_errors: list[dict]
    approval_status: str
    next_action: str
    retry_count: int
```

In the implementation, replace generic `dict` values with specific Pydantic models where practical. Do not store secrets or raw credentials in graph state.

### 7.2 Main graph flow

```mermaid
flowchart TD
    START([Start]) --> INGEST[Parse uploaded documents]
    INGEST --> EVIDENCE[Structure evidence]
    EVIDENCE --> DISCOVERY[Build As-Is process]
    DISCOVERY --> RULES[Extract business rules]
    RULES --> GAP[Find gaps and conflicts]
    GAP --> DECIDE{Unresolved critical issues?}
    DECIDE -->|Yes| ASK[Ask process owner]
    ASK --> MERGE[Validate and store answer]
    MERGE --> GAP
    DECIDE -->|No| REDESIGN[Propose To-Be process]
    REDESIGN --> REVIEW{Human approves To-Be?}
    REVIEW -->|Edit / reject| REDESIGN
    REVIEW -->|Approve| GENERATE[Generate requirements and artifacts]
    GENERATE --> VALIDATE[Validate schemas and traceability]
    VALIDATE --> VALID{Passes validation?}
    VALID -->|No, retry budget remains| REPAIR[Repair selected artifacts]
    REPAIR --> VALIDATE
    VALID -->|No, retry limit reached| NEEDS[Mark Needs Review]
    VALID -->|Yes| EXPORT[Save and export artifact pack]
    NEEDS --> END([End with findings])
    EXPORT --> END
```

### 7.3 Routing rules

Use explicit Python routing functions; do not ask the LLM to decide whether a human approval is required.

- If no source documents exist, request process description and/or upload.
- If critical rules conflict or a required fact is missing, create clarification items and pause.
- If clarification is answered, mark the issue as resolved only after validation; then re-run relevant analysis.
- If the To-Be model has not been approved, do not generate final/approved downstream artifacts.
- If artifact schema validation fails, allow at most **two repair attempts**.
- If still invalid, save the error report and mark the artifact `Needs Review`; do not loop indefinitely.
- If the user edits an approved rule or To-Be step, create a new version and mark dependent artifacts stale.
- Only a human reviewer can set business/process approval status.

### 7.4 Human-in-the-loop implementation

Use LangGraph’s interrupt/checkpoint pattern for pauses if supported by the selected version. Provide a stable project/run identifier so the graph can resume. For the MVP, a simpler persisted `waiting_for_human` status can also work if reliable pause/resume integration becomes a blocker.

The UI should show:
- The question and why it matters.
- Source evidence or the conflicting sources.
- Suggested answer, clearly labelled as an AI suggestion.
- Text input for the process owner’s answer.
- Actions: **Submit answer**, **Mark unknown**, and **Cancel run**.
- Who provided the answer and when.
- Which artifacts must be regenerated after the answer.

Do not silently resolve conflicting official policies by choosing the newest-looking or most common value. Ask the owner to decide.

---

## 8. Canonical data model and traceability

### 8.1 Core principle

Documents must be different views of one shared project model. Do not independently ask a model to create a BRD, FRD, and test plan from scratch without shared IDs and relationships.

### 8.2 Recommended core entities

| Entity/table | Key fields | Purpose |
|---|---|---|
| `projects` | `id`, `name`, `process_type`, `description`, `status`, timestamps | One redesign project for any process |
| `documents` | `id`, `project_id`, `filename`, `mime_type`, `checksum`, `version`, `storage_path` | Original source file metadata |
| `document_sections` | `id`, `document_id`, `page_number`, `section_title`, `text` | Extracted source content |
| `evidence_items` | `id`, `project_id`, `document_section_id`, `quote`, `claim_type`, `confidence` | Source-grounded statements |
| `process_versions` | `id`, `project_id`, `version`, `as_is_json`, `to_be_json`, `status` | Versioned process models |
| `process_steps` | `id`, `process_version_id`, `step_key`, `name`, `actor`, `step_type`, `sequence` | Individual steps and transitions |
| `business_rules` | `id`, `project_id`, `rule_key`, `description`, `condition_json`, `status` | Rules, conditions, exceptions |
| `rule_evidence` | `rule_id`, `evidence_id` | Links rules to evidence |
| `clarification_items` | `id`, `project_id`, `question`, `reason`, `status`, `answer`, `answered_by` | Questions and approved clarifications |
| `requirements` | `id`, `project_id`, `requirement_key`, `type`, `statement`, `priority`, `status` | PRD/BRD/FRD/SRS requirement records |
| `requirement_links` | `source_requirement_id`, `target_id`, `link_type` | Relationships among requirements and rules |
| `artifacts` | `id`, `project_id`, `artifact_type`, `version`, `content_json`, `markdown`, `status` | Generated documents and exports |
| `artifact_links` | `artifact_id`, `target_type`, `target_id`, `link_type` | Evidence and traceability links |
| `test_cases` | `id`, `project_id`, `test_key`, `requirement_id`, `scenario`, `expected_result` | Tests tied to requirements |
| `approvals` | `id`, `project_id`, `target_type`, `target_id`, `decision`, `reviewer`, `timestamp`, `comment` | Human decisions |
| `agent_runs` | `id`, `project_id`, `node_name`, `status`, `input_summary`, `output_ref`, `error`, timestamps | Debugging and run history |

For the first week, the team can begin with fewer tables (`projects`, `documents`, `evidence_items`, `process_versions`, `requirements`, `artifacts`, `clarification_items`, `approvals`, `agent_runs`) and add normalized link tables as needed. Never store only one giant JSON blob if you need to query traceability.

### 8.3 Traceability requirements

Every item should have a stable ID:
- Evidence: `EVD-001`
- Business rule: `BR-001`
- Requirement: `REQ-001`
- Workflow step: `STEP-001`
- Test: `TEST-001`
- UAT scenario: `UAT-001`

Example:

`Source PDF page 3 → EVD-004 → BR-002 → REQ-007 → STEP-003 → TEST-011`

If a source cannot support a generated claim, label it `Assumption` or `Needs Clarification`. Do not fabricate a citation, page number, policy, or requirement source.

---

## 9. Structured output examples

### 9.1 Workflow JSON

Use a schema like the following as the canonical representation. Validate it with Pydantic before saving it.

```json
{
  "process_id": "PROC-001",
  "version": 1,
  "name": "Example college process",
  "status": "draft",
  "steps": [
    {
      "id": "STEP-001",
      "name": "Submit request",
      "actor": "Student",
      "kind": "form_submission",
      "automation": "deterministic",
      "inputs": ["required form fields", "supporting documents"],
      "outputs": ["request record"],
      "rules": [],
      "evidence_ids": [],
      "human_approval_required": false
    },
    {
      "id": "STEP-002",
      "name": "Review request",
      "actor": "Department reviewer",
      "kind": "review",
      "automation": "human",
      "inputs": ["request record"],
      "outputs": ["review decision", "comments"],
      "rules": [],
      "evidence_ids": [],
      "human_approval_required": true
    }
  ],
  "transitions": [
    {"from": "STEP-001", "to": "STEP-002", "condition": "submission is valid"}
  ]
}
```

This is only a schema illustration. The team must not treat its example rules or process steps as official college policy.

### 9.2 Requirement JSON

```json
{
  "id": "REQ-001",
  "type": "functional",
  "title": "Validate request completeness",
  "statement": "The system shall identify missing required fields before submission.",
  "priority": "Must",
  "source_evidence_ids": ["EVD-001"],
  "related_rule_ids": ["BR-001"],
  "related_step_ids": ["STEP-001"],
  "acceptance_criteria": [
    "Given a required field is missing, when the user submits the form, then the system shows the missing field."
  ],
  "status": "draft"
}
```

### 9.3 Business rule JSON

```json
{
  "id": "BR-001",
  "statement": "A request must include all fields designated as required.",
  "condition": "One or more required fields are empty",
  "outcome": "Do not accept submission; show validation errors",
  "source_evidence_ids": ["EVD-001"],
  "status": "needs_review",
  "approved_by": null
}
```

Only use rules grounded in project evidence or explicitly supplied and approved by the process owner.

---

## 10. Document generation design

### 10.1 Recommended generation sequence

1. Generate and validate the As-Is process.
2. Resolve important gaps and conflicts.
3. Generate the To-Be model and automation assessment.
4. Obtain human approval for the To-Be model.
5. Generate business rules catalogue and roles matrix.
6. Generate BRD and PRD from the approved model and goals.
7. Generate FRD and SRS sections from the same requirement records.
8. Generate data model, architecture, and API specifications.
9. Generate tests and UAT scenarios from requirements and rules.
10. Run traceability and consistency checks.
11. Export each artifact to Markdown; JSON exports should be available for structured artifacts.

### 10.2 How to avoid contradictions across documents

- Store requirement statements as records, not only as prose.
- Use stable IDs across all artifacts.
- Use document templates with required headings.
- Require source links for policy and business-rule claims.
- Validate all generated JSON against schemas.
- Run cross-document checks: every test points to a requirement; every requirement points to a process step or approved business need; every official rule has a source or an explicit approval record.
- When requirements change, mark dependent artifacts as `Needs Review`.
- Do not describe an AI-generated document as approved until an authorized person approves it.

### 10.3 Minimum templates

**BRD headings:** Purpose, business problem, goals, scope, stakeholders, current process, business needs, business rules, constraints, assumptions, risks, success measures, approvals.

**PRD headings:** Product goal, users/personas, user problems, features, user stories, priorities, acceptance criteria, dependencies, non-functional needs, open questions.

**FRD headings:** System overview, actors/roles, functional requirements, workflow, decision rules, validations, exceptions, notifications, permissions, audit events, external interfaces, acceptance criteria.

**SRS headings:** Purpose, scope, definitions, system context, functional requirements, interfaces, performance and availability expectations, security/privacy, data requirements, constraints, assumptions, verification criteria.

**HLD headings:** Architecture diagram, component responsibilities, data flow, storage, model/tool integration, security boundaries, failure handling, deployment and configuration.

**Test plan headings:** Scope, test strategy, environment, test data, cases, expected results, edge cases, permissions, requirement coverage, known limitations.

**UAT headings:** User role, scenario, starting conditions, actions, expected outcome, actual outcome, pass/fail, reviewer, comments.

Use templates as starting points. The user should be able to choose or customize a document template because institutions use different terminology and formats.

---

## 11. RAG and evidence retrieval

RAG means **Retrieval-Augmented Generation**: before drafting an answer, the system searches the project's source material and gives relevant excerpts to the model. This improves grounding, but it does not guarantee correctness.

### MVP retrieval steps

1. Extract text from source files.
2. Split long text into chunks while retaining document ID, page/section, version, and access scope.
3. Store chunks and metadata in PostgreSQL.
4. Start with keyword/full-text retrieval if time is limited.
5. Add embeddings and pgvector if semantic search is needed and the model embedding option is available.
6. Retrieve a small number of relevant chunks for each agent task.
7. Include evidence IDs in the structured output.
8. Validate evidence IDs against actual stored records before accepting the output.

### Important safety note

Documents are untrusted input. They may contain irrelevant or malicious instructions. Treat document contents as evidence, not as instructions that override system behavior. Never allow uploaded content to grant permissions, reveal secrets, or directly execute code.

---

## 12. UI design using Streamlit

The aim is a clear review-and-build studio, not a complicated custom frontend.

### Page 1 — Projects
- Create a project.
- Enter process name, department, goals, stakeholders, and known constraints.
- Show project status and latest run.

### Page 2 — Sources
- Upload PDF, DOCX, or TXT.
- List uploaded files and parsing status.
- Preview extracted text and source sections.
- Show parsing warnings.

### Page 3 — Discovery
- Display As-Is steps in a table or simple diagram.
- Show actors, inputs, outputs, handoffs, evidence and confidence/unknown markers.
- Allow the analyst to edit the model.

### Page 4 — Questions and Rules
- List missing information and conflicting claims.
- Display source excerpts side by side where applicable.
- Allow a reviewer to answer, mark unknown, or reject an AI suggestion.
- Display candidate rules and approval status.

### Page 5 — Redesigned Process
- Display the proposed To-Be flow.
- Classify each step: deterministic automation, AI-assisted, human, or hybrid.
- Show why a step is being changed and which evidence supports the proposal.
- Provide Approve, Request Changes, and Reject actions.

### Page 6 — Documents
- Tabs or a selector for BRD, PRD, FRD, SRS, rules, architecture, data model, tests and UAT.
- Show Draft / Needs Review / Approved status and version.
- Allow editing and Markdown download.
- Display links to evidence, requirements, and workflow steps.

### Page 7 — Workflow and Traceability
- Show workflow JSON and a simple visual preview.
- Select a requirement and view linked rule, source evidence, workflow step and test.
- Show missing links and validation errors.

**Streamlit recommendation:** use its official multipage navigation API. Build the first usable screen early; do not spend the first week on styling. Use Streamlit's upload widget, but still validate file type, file size, content, and parser errors on the server.

---

## 13. FastAPI API design

Keep the API small. Streamlit can call these endpoints; agent logic must not live inside UI scripts.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/projects` | Create a project |
| `GET` | `/api/projects` | List projects |
| `GET` | `/api/projects/{project_id}` | Get project status and summary |
| `POST` | `/api/projects/{project_id}/documents` | Upload a source document |
| `GET` | `/api/projects/{project_id}/documents` | List documents and parse status |
| `POST` | `/api/projects/{project_id}/runs` | Start discovery/redesign/artifact generation |
| `GET` | `/api/runs/{run_id}` | Read run status and errors |
| `GET` | `/api/projects/{project_id}/questions` | List clarification items |
| `POST` | `/api/questions/{question_id}/answer` | Save a human answer |
| `POST` | `/api/process-versions/{version_id}/decision` | Approve, request changes, or reject To-Be model |
| `GET` | `/api/projects/{project_id}/artifacts` | List generated artifacts |
| `GET` | `/api/artifacts/{artifact_id}` | Read artifact content and status |
| `PATCH` | `/api/artifacts/{artifact_id}` | Save a human edit as a new version |
| `GET` | `/api/projects/{project_id}/traceability` | Return evidence-to-test relationships |
| `GET` | `/api/artifacts/{artifact_id}/download` | Download Markdown or JSON |

Use Pydantic request and response models. Return useful HTTP error codes and messages. Do not return raw stack traces or API keys.

For the MVP, the run can execute in-process. If long-running requests cause problems, use a background task and persist the run status. Avoid adding a queue infrastructure unless it is needed.

---

## 14. Suggested repository layout

```text
processfoundry-ai/
├── README.md
├── pyproject.toml
├── .env.example
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── projects.py
│   │   ├── documents.py
│   │   ├── runs.py
│   │   ├── questions.py
│   │   ├── artifacts.py
│   │   └── traceability.py
│   ├── ui/
│   │   ├── streamlit_app.py
│   │   └── pages/
│   ├── graph/
│   │   ├── state.py
│   │   ├── build_graph.py
│   │   └── routing.py
│   ├── agents/
│   │   ├── evidence.py
│   │   ├── discovery.py
│   │   ├── rules.py
│   │   ├── gaps.py
│   │   ├── redesign.py
│   │   ├── requirements.py
│   │   ├── architecture.py
│   │   ├── testing.py
│   │   └── quality.py
│   ├── schemas/
│   │   ├── process.py
│   │   ├── evidence.py
│   │   ├── requirements.py
│   │   ├── artifacts.py
│   │   └── tests.py
│   ├── services/
│   │   ├── document_parser.py
│   │   ├── retrieval.py
│   │   ├── artifact_export.py
│   │   └── validators.py
│   └── repositories/
│       ├── projects.py
│       ├── documents.py
│       └── artifacts.py
└── tests/
    ├── test_schemas.py
    ├── test_parsing.py
    ├── test_graph_routing.py
    ├── test_api.py
    └── test_traceability.py
```

Students may adjust the file names, but preserve the separation between UI, orchestration, agent logic, schemas, and persistence.

---

## 15. One-month execution plan

### Week 1 — Foundation and vertical slice

**Goal:** Upload a document and generate one structured process model.

- Day 1: Create repository, virtual environment, configuration, `.env.example`, and basic README.
- Day 2: Build Streamlit project and upload pages.
- Day 3: Implement PDF/DOCX/TXT extraction and store source metadata.
- Day 4: Define Pydantic schemas for evidence, rules, process steps, and requirements.
- Day 5: Build a basic LangGraph with ingestion → evidence → As-Is process and save outputs.

**Exit criteria:** One uploaded sample can be parsed, source evidence is visible, and the As-Is model validates against a schema.

### Week 2 — Rules, gaps, and human review

**Goal:** Make the discovery process trustworthy.

- Extract candidate business rules with evidence references.
- Implement gap/conflict checks.
- Build the clarification screen and persist answers.
- Implement explicit pause/resume or a persisted waiting-for-human status.
- Add deterministic routing tests.

**Exit criteria:** The system flags a deliberately ambiguous/conflicting sample and waits for a human decision instead of silently choosing a rule.

### Week 3 — Redesign and documents

**Goal:** Generate a coherent redesign and core artifacts.

- Generate the To-Be process and automation assessment.
- Implement human review and approval of the To-Be model.
- Generate BRD, PRD, FRD, business rules, data model, and workflow JSON.
- Generate test cases and UAT scenarios.
- Add stable IDs and basic traceability.

**Exit criteria:** Core artifacts are generated from the same approved model and cross-reference the same IDs.

### Week 4 — Validation, export, and demonstration

**Goal:** Deliver a stable end-to-end demo.

- Add schema validation and limited repair retries.
- Add traceability checks and stale-artifact warnings.
- Add Markdown/JSON exports.
- Run unit, API, and graph tests.
- Prepare sample documents and a scripted demonstration.
- Document limitations and next steps.

**Exit criteria:** A team member can create a project, upload source material, resolve a question, approve a redesign, generate artifacts, inspect traceability, and export results.

### Suggested team split

For a team of 4–5 students:
- Student 1: Streamlit UI and project/source screens.
- Student 2: FastAPI, database, file handling and schemas.
- Student 3: document parsing, evidence, retrieval and rule analysis.
- Student 4: LangGraph orchestration, clarification, redesign and approvals.
- Student 5 (if available): requirements/templates, tests/UAT, traceability and integration.

Agree on Pydantic schemas and API contracts before parallel work. Merge small changes daily. Everyone should be able to run the project locally from the README.

---

## 16. Test and evaluation plan

Use a small synthetic sample process and deliberately include missing and conflicting details. Do not use real student personal data in a public demo.

### Required tests

1. **Parsing:** Supported file parses; unsupported/corrupt file returns a clear error.
2. **Evidence:** Each cited evidence ID exists and points to a real document section.
3. **Rules:** Unknown or conflicting rules are flagged instead of silently resolved.
4. **HITL:** A critical clarification pauses downstream generation; a human answer is stored and the run resumes.
5. **Routing:** Approved To-Be model is required before final artifact generation.
6. **Schemas:** Invalid generated JSON is rejected and gets a bounded repair attempt.
7. **Traceability:** Every generated test links to a requirement; requirements link to a rule, process step, or explicitly documented business need.
8. **Versioning:** Editing a rule or process model marks dependent outputs as needing review.
9. **Security:** File names are not used directly as storage paths; secrets are not included in prompts or logs; uploaded content cannot change authorization rules.
10. **Repeatability:** Fixed synthetic examples are used to compare expected outputs after prompt or code changes.

### Demo success criteria

- The platform accepts a source document for a general college process.
- It presents the current process and evidence.
- It identifies at least one intentionally missing/ambiguous item.
- It requests and records human clarification.
- It proposes an improved process with reasons.
- A human can approve or request changes.
- It generates BRD/PRD/FRD plus workflow JSON and test/UAT outputs.
- It shows source/requirement/test links and exports the artifacts.
- It communicates uncertainty and limitations instead of pretending every output is correct.

---

## 17. Reliability, security, and responsible AI

- Keep API keys in environment variables or a secret manager, never in source control.
- Provide `.env.example` with placeholder names only.
- Validate upload size, extension, MIME type, and parser result. Extension checks alone are not a security guarantee.
- Treat source documents as untrusted text, not executable instructions.
- Restrict retrieval to the current project and authorized user.
- Separate draft AI outputs from human-approved policy and process facts.
- Do not allow an LLM to execute arbitrary SQL, shell commands, or code.
- Do not let an AI agent make final eligibility, disciplinary, financial, or official administrative decisions.
- Log run IDs, node names, validation errors and artifact versions, but avoid logging secrets or unnecessary personal data.
- Use synthetic data for the student demo.
- If an LLM provider is external, explain that uploaded text may be sent to that provider and follow the team's institution rules.
- Use bounded retries, timeouts, and clear failure states.
- Include a way to correct AI outputs and identify assumptions.

---

## 18. Key implementation decisions

1. **One general platform:** no process-specific code branches for scholarships, admissions, or other examples. Represent process variation in data, rules, and templates.
2. **One demo process:** choose a process with available sample documents and a process owner who can answer questions. This is a demonstration choice, not a product restriction.
3. **Few reasoning agents, many deterministic functions:** build small, testable LangGraph nodes instead of a swarm of independent agents.
4. **Shared source of truth:** requirements, workflow, and tests must use stable IDs from one canonical model.
5. **Human approval is explicit:** AI-generated content starts as a draft.
6. **Streamlit first:** optimize for working behavior and evaluation in one month. Keep backend modules reusable.
7. **No production claims:** the one-month result is an MVP, not a complete university workflow deployment.
8. **Use official documentation:** consult the links below and pin compatible dependency versions in the repository.

---

## 19. Official documentation and learning references

These are official project documentation pages or official project repositories. Students should use them for setup and API details. The design recommendations in this document are project-specific choices built on these tools, not claims that the tools automatically implement ProcessFoundry.

### UI

1. **Streamlit — Get started**  
   https://docs.streamlit.io/get-started
2. **Streamlit — Multipage apps**  
   https://docs.streamlit.io/develop/concepts/multipage-apps
3. **Streamlit — File uploader API**  
   https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader

### Backend and data validation

4. **FastAPI — Tutorial**  
   https://fastapi.tiangolo.com/tutorial/
5. **Pydantic — Documentation**  
   https://docs.pydantic.dev/latest/
6. **PostgreSQL — Official documentation**  
   https://www.postgresql.org/docs/current/
7. **pgvector — Official repository and usage**  
   https://github.com/pgvector/pgvector

### Agents and orchestration

8. **LangGraph — Overview**  
   https://docs.langchain.com/oss/python/langgraph/overview
9. **LangGraph — Workflows and agents**  
   https://docs.langchain.com/oss/python/langgraph/workflows-agents
10. **LangGraph — Human-in-the-loop / interrupts**  
    https://docs.langchain.com/oss/python/langgraph/interrupts
11. **LangChain — Retrieval-Augmented Generation (RAG)**  
    https://docs.langchain.com/oss/python/langchain/rag

### Document parsing, testing, and safety

12. **PyMuPDF — Documentation**  
    https://pymupdf.readthedocs.io/en/latest/
13. **python-docx — Documentation**  
    https://python-docx.readthedocs.io/en/latest/
14. **pytest — Getting started**  
    https://docs.pytest.org/en/stable/getting-started.html
15. **OWASP GenAI Security Project**  
    https://genai.owasp.org/
16. **OWASP Top 10 for LLM Applications**  
    https://owasp.org/www-project-top-10-for-large-language-model-applications/

### Suggested learning order

1. Streamlit basics and file upload.
2. FastAPI tutorial and Pydantic models.
3. LangGraph overview, then workflows/agents.
4. LangGraph interrupts for human review.
5. PostgreSQL basics and database access.
6. RAG only after parsing and evidence IDs work.
7. pytest and OWASP guidance before final demo.

---

## 20. First tasks students should start today

1. Create the repository and agree on Python version and dependency management.
2. Implement the Pydantic models for `Evidence`, `BusinessRule`, `ProcessStep`, `Requirement`, `Artifact`, and `ClarificationItem`.
3. Build a Streamlit page to create a project and upload one PDF/DOCX/TXT file.
4. Build a parser that extracts text and records document/page metadata.
5. Build a small LangGraph: `extract_evidence → build_as_is → validate_schema`.
6. Add one synthetic sample process and one intentionally ambiguous rule.
7. Add the clarification pause and test that the graph does not proceed to the To-Be model until the issue is resolved.
8. Commit working code and instructions before adding more agents.

**Do not start by implementing all agents simultaneously.** First make the vertical slice work; then add rule analysis, clarification, redesign, artifact generation, and traceability in that order.

---

## 21. Definition of done

The one-month MVP is complete when a reviewer can:

- Create a project for a college process without changing the source code.
- Upload and inspect source material.
- View an evidence-backed As-Is process.
- See missing or conflicting details and answer clarification questions.
- Review and approve a To-Be proposal.
- Generate the core documents and structured workflow from the same model.
- See traceability from evidence to requirements and tests.
- Export Markdown/JSON outputs.
- Run automated tests and reproduce the demo using the README.

Anything not meeting these criteria should be listed as a known limitation or future improvement rather than presented as implemented.

