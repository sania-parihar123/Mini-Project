"""ProcessFoundry AI: Frontend API Client communicating with FastAPI."""
import httpx
from typing import Optional, Dict, Any, List

from app.core.config import settings


class APIError(RuntimeError):
    """A non-success response from the backend, with the server's own message."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code

class APIClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.api_base_url).rstrip("/")
        # Persistent HTTP client: reuses TCP connections across all API calls
        # instead of opening/closing a new connection per method call.
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=180.0,  # large analyses make the rules/traceability reads slow on a remote database
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
        )

    def _headers(self, token: Optional[str] = None) -> Dict[str, str]:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @staticmethod
    def _detail(resp: "httpx.Response", fallback: str) -> str:
        """Best human-readable message from an error response, never a stack trace."""
        try:
            body = resp.json()
        except Exception:
            return f"{fallback} (HTTP {resp.status_code})"
        detail = body.get("detail") if isinstance(body, dict) else None
        if isinstance(detail, str) and detail.strip():
            return detail
        if isinstance(detail, list) and detail:
            first = detail[0]
            if isinstance(first, dict) and first.get("msg"):
                loc = ".".join(str(x) for x in first.get("loc", [])[1:])
                return f"{first['msg']}{f' ({loc})' if loc else ''}"
        return f"{fallback} (HTTP {resp.status_code})"

    def _unwrap(self, resp: "httpx.Response", fallback: str, expected: int = 200):
        """Return the decoded body, or raise APIError.

        Previously every list endpoint did `return resp.json() if resp.status_code
        == 200 else []`. That turned a server error into an empty page: finding F1
        in REVIEW_REPORT.md, where the Questions page and "Waiting for me" showed
        "no questions" because the endpoint was returning HTTP 500.
        """
        if resp.status_code != expected:
            raise APIError(self._detail(resp, fallback), status_code=resp.status_code)
        return resp.json()

    def register(self, display_name: str, email: str, password: str, repeat_password: str) -> Dict[str, Any]:
        resp = self._client.post("/api/auth/register", json={
            "display_name": display_name,
            "email": email,
            "password": password,
            "repeat_password": repeat_password
        })
        return self._unwrap(resp, "Registration failed.", expected=201)

    def login(self, email: str, password: str) -> Dict[str, Any]:
        resp = self._client.post("/api/auth/login", json={
            "email": email,
            "password": password
        })
        return self._unwrap(resp, "Sign in failed.", expected=200)

    def health(self) -> Dict[str, Any]:
        """Service health, including whether the configured model invents content."""
        resp = self._client.get("/api/health")
        return self._unwrap(resp, "Backend is not reachable.")

    def get_me(self, token: str) -> Dict[str, Any]:
        resp = self._client.get("/api/me", headers=self._headers(token))
        return self._unwrap(resp, "Session invalid.", expected=200)

    def list_projects(self, token: str) -> List[Dict[str, Any]]:
        resp = self._client.get("/api/projects", headers=self._headers(token))
        return self._unwrap(resp, "Could not load your projects.")

    def create_project(self, token: str, name: str, role: str, process_type: str = "general", description: str = "", department: str = "", goals: str = "", constraints: str = "") -> Dict[str, Any]:
        resp = self._client.post("/api/projects", headers=self._headers(token), json={
            "name": name,
            "role": role,
            "process_type": process_type,
            "description": description,
            "department": department,
            "goals": goals,
            "constraints": constraints
        })
        return self._unwrap(resp, "Failed to create project.", expected=201)

    def get_project(self, token: str, project_id: str) -> Dict[str, Any]:
        resp = self._client.get(f"/api/projects/{project_id}", headers=self._headers(token))
        return self._unwrap(resp, "Project not found.", expected=200)

    def delete_project(self, token: str, project_id: str) -> Dict[str, Any]:
        resp = self._client.delete(f"/api/projects/{project_id}", headers=self._headers(token))
        return self._unwrap(resp, "Failed to delete project.", expected=200)

    def upload_document(self, token: str, project_id: str, filename: str, content: bytes, mime_type: str) -> Dict[str, Any]:
        files = {"file": (filename, content, mime_type)}
        resp = self._client.post(f"/api/projects/{project_id}/documents", headers=self._headers(token), files=files, timeout=60.0)
        return self._unwrap(resp, "Upload failed.", expected=201)

    def upload_documents_batch(self, token: str, project_id: str, files: List[tuple]) -> Dict[str, Any]:
        """Upload several files in one request; returns one result line per file.

        `files` is a list of (filename, content_bytes, mime_type).
        """
        payload = [("files", (name, content, mime)) for name, content, mime in files]
        resp = self._client.post(
            f"/api/projects/{project_id}/documents/batch",
            headers=self._headers(token), files=payload, timeout=180.0,
        )
        return self._unwrap(resp, "Upload failed.", expected=200)

    def list_documents(self, token: str, project_id: str) -> List[Dict[str, Any]]:
        resp = self._client.get(f"/api/projects/{project_id}/documents", headers=self._headers(token))
        return self._unwrap(resp, "Could not load the project documents.")

    def trigger_run(self, token: str, project_id: str) -> Dict[str, Any]:
        resp = self._client.post(f"/api/projects/{project_id}/runs", headers=self._headers(token), timeout=60.0)
        return self._unwrap(resp, "Analysis failed to start.", expected=200)

    def get_document_understanding(self, token: str, document_id: str) -> Dict[str, Any]:
        resp = self._client.get(f"/api/documents/{document_id}/understanding", headers=self._headers(token), timeout=60.0)
        return self._unwrap(resp, "Failed to retrieve document understanding.", expected=200)

    def get_run(self, token: str, run_id: str) -> Dict[str, Any]:
        resp = self._client.get(f"/api/runs/{run_id}", headers=self._headers(token))
        return self._unwrap(resp, "Could not read the analysis run status.")

    def cancel_run(self, token: str, run_id: str) -> Dict[str, Any]:
        resp = self._client.post(f"/api/runs/{run_id}/cancel", headers=self._headers(token))
        return self._unwrap(resp, "Failed to cancel run.", expected=200)

    def list_questions(self, token: str, project_id: str) -> List[Dict[str, Any]]:
        resp = self._client.get(f"/api/projects/{project_id}/questions", headers=self._headers(token))
        return self._unwrap(resp, "Could not load the project questions.")

    def get_waiting_for_me(self, token: str) -> List[Dict[str, Any]]:
        resp = self._client.get("/api/me/questions", headers=self._headers(token))
        return self._unwrap(resp, "Could not load the questions waiting for you.")

    def answer_question(self, token: str, question_id: str, kind: str, answer_text: Optional[str] = None) -> Dict[str, Any]:
        resp = self._client.post(f"/api/questions/{question_id}/answer", headers=self._headers(token), json={
            "kind": kind,
            "answer_text": answer_text
        })
        return self._unwrap(resp, "Failed to submit answer.", expected=200)

    def escalate_question(self, token: str, question_id: str, reason: str) -> Dict[str, Any]:
        resp = self._client.post(f"/api/questions/{question_id}/escalate", headers=self._headers(token), json={
            "reason": reason
        })
        return self._unwrap(resp, "Failed to escalate question.", expected=200)

    def list_artifacts(self, token: str, project_id: str) -> List[Dict[str, Any]]:
        resp = self._client.get(f"/api/projects/{project_id}/artifacts", headers=self._headers(token))
        return self._unwrap(resp, "Could not load the generated documents.")

    def get_discovery(self, token: str, project_id: str) -> Dict[str, Any]:
        resp = self._client.get(f"/api/projects/{project_id}/discovery", headers=self._headers(token))
        return self._unwrap(resp, "Could not load the current process.")

    def get_rules(self, token: str, project_id: str) -> List[Dict[str, Any]]:
        resp = self._client.get(f"/api/projects/{project_id}/rules", headers=self._headers(token))
        return self._unwrap(resp, "Could not load the business rules.")

    def get_evidence(self, token: str, project_id: str) -> List[Dict[str, Any]]:
        resp = self._client.get(f"/api/projects/{project_id}/evidence", headers=self._headers(token))
        return self._unwrap(resp, "Could not load the evidence.")

    def get_traceability(self, token: str, project_id: str) -> Dict[str, Any]:
        resp = self._client.get(f"/api/projects/{project_id}/traceability", headers=self._headers(token))
        return self._unwrap(resp, "Could not load the traceability report.")

    def decide_process_version(self, token: str, version_id: str, decision: str, comment: Optional[str] = None) -> Dict[str, Any]:
        resp = self._client.post(f"/api/process-versions/{version_id}/decision", headers=self._headers(token), json={
            "decision": decision,
            "comment": comment
        })
        return self._unwrap(resp, "Failed to record process version decision.", expected=200)

    def decide_artifact(self, token: str, artifact_id: str, decision: str, comment: Optional[str] = None) -> Dict[str, Any]:
        resp = self._client.post(f"/api/artifacts/{artifact_id}/decision", headers=self._headers(token), json={
            "decision": decision,
            "comment": comment
        })
        return self._unwrap(resp, "Failed to record artifact decision.", expected=200)

    def get_team(self, token: str, project_id: str) -> Dict[str, Any]:
        resp = self._client.get(f"/api/projects/{project_id}/members", headers=self._headers(token))
        return self._unwrap(resp, "Could not load the project team.")

    def invite_teammate(self, token: str, project_id: str, email: str, role: str) -> Dict[str, Any]:
        resp = self._client.post(f"/api/projects/{project_id}/invitations", headers=self._headers(token), json={
            "email": email,
            "role": role
        })
        return self._unwrap(resp, "Failed to send invitation.", expected=200)

    def get_my_invitations(self, token: str) -> List[Dict[str, Any]]:
        resp = self._client.get("/api/me/invitations", headers=self._headers(token))
        return self._unwrap(resp, "Could not load your invitations.")

    def accept_invitation(self, token: str, inv_id: str) -> Dict[str, Any]:
        resp = self._client.post(f"/api/invitations/{inv_id}/accept", headers=self._headers(token))
        return self._unwrap(resp, "Failed to accept invitation.", expected=200)

    def decline_invitation(self, token: str, inv_id: str) -> Dict[str, Any]:
        resp = self._client.post(f"/api/invitations/{inv_id}/decline", headers=self._headers(token))
        return self._unwrap(resp, "Failed to decline invitation.", expected=200)

    def resend_invitation(self, token: str, inv_id: str) -> Dict[str, Any]:
        resp = self._client.post(f"/api/invitations/{inv_id}/resend", headers=self._headers(token))
        return self._unwrap(resp, "Failed to resend the invitation.", expected=200)

    def revoke_invitation(self, token: str, inv_id: str) -> Dict[str, Any]:
        resp = self._client.post(f"/api/invitations/{inv_id}/revoke", headers=self._headers(token))
        return self._unwrap(resp, "Failed to revoke invitation.", expected=200)

    def remove_member(self, token: str, project_id: str, target_user_id: str) -> Dict[str, Any]:
        resp = self._client.delete(f"/api/projects/{project_id}/members/{target_user_id}", headers=self._headers(token))
        return self._unwrap(resp, "Failed to remove member.", expected=200)

    def get_audit_log(self, token: str, project_id: str) -> List[Dict[str, Any]]:
        resp = self._client.get(f"/api/projects/{project_id}/audit", headers=self._headers(token))
        return self._unwrap(resp, "Could not load the audit log.")

    def get_prototype_spec(self, token: str, project_id: str) -> Optional[Dict[str, Any]]:
        resp = self._client.get(f"/api/projects/{project_id}/prototype", headers=self._headers(token))
        if resp.status_code == 404:
            return None
        return self._unwrap(resp, "Could not load the prototype spec.")

    def regenerate_prototype(self, token: str, project_id: str) -> Dict[str, Any]:
        resp = self._client.post(f"/api/projects/{project_id}/prototype/generate", headers=self._headers(token))
        return self._unwrap(resp, "Failed to generate prototype.", expected=200)

    def get_prototype_html(self, token: str, project_id: str) -> Optional[str]:
        resp = self._client.get(f"/api/projects/{project_id}/prototype/html", headers=self._headers(token))
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise APIError(self._detail(resp, "Could not load prototype HTML."), status_code=resp.status_code)
        return resp.text

    def get_prototype_versions(self, token: str, project_id: str) -> List[Dict[str, Any]]:
        resp = self._client.get(f"/api/projects/{project_id}/prototype/versions", headers=self._headers(token))
        if resp.status_code == 404:
            return []
        return self._unwrap(resp, "Could not load prototype version history.")

api_client = APIClient()
