"""ProcessFoundry AI: Security, Authentication Tokens, and Permission Engine."""
import bcrypt
import time
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from fastapi import HTTPException, status, Header

from app.core.config import settings
from app.repositories.database import db

serializer = URLSafeTimedSerializer(settings.secret_key)

# ----------------------------------------------------------------
# Password Hashing (bcrypt)
# ----------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

# ----------------------------------------------------------------
# Token Management (8-Hour Signed Tokens)
# ----------------------------------------------------------------
def create_access_token(user_id: str, email: str) -> str:
    """Generate signed bearer token expiring in 8 hours."""
    data = {
        "sub": user_id,
        "email": email.lower(),
        "exp": int(time.time()) + (8 * 3600)
    }
    return serializer.dumps(data)

def decode_access_token(token: str) -> Dict[str, Any]:
    """Validate token and return payload. Raises HTTP 401 if expired or invalid."""
    try:
        data = serializer.loads(token, max_age=8 * 3600)
        return data
    except SignatureExpired:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session token has expired. Please sign in again.")
    except (BadTimeSignature, Exception):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token.")

# In-memory cache of the caller's own user row, to avoid one extra query on
# every authenticated request. It is bounded and short-lived (finding F14: it
# was TTL-only and never evicted, so it grew with the number of distinct users).
#
# It deliberately holds ONLY the user row. Project membership and role are never
# cached: `require_project_member` reads them fresh on every request, so removing
# a member or changing a role takes effect on the caller's very next request.
_user_cache: "OrderedDict[str, Tuple[float, Dict[str, Any]]]" = OrderedDict()
_USER_CACHE_TTL = 30.0   # seconds; short, so a lockout is noticed quickly
_USER_CACHE_MAX = 512    # entries; oldest evicted first

def _remember_user(user_id: str, user: Dict[str, Any]) -> None:
    _user_cache[user_id] = (time.time(), user)
    _user_cache.move_to_end(user_id)
    while len(_user_cache) > _USER_CACHE_MAX:
        _user_cache.popitem(last=False)

def get_cached_user(user_id: str) -> Optional[Dict[str, Any]]:
    now = time.time()
    cached = _user_cache.get(user_id)
    if cached and (now - cached[0]) < _USER_CACHE_TTL:
        _user_cache.move_to_end(user_id)
        return cached[1]
    if cached:
        _user_cache.pop(user_id, None)
    user = db.get_user_by_id(user_id)
    if user:
        _remember_user(user_id, user)
    return user

def cache_user(user: Dict[str, Any]):
    if user and "id" in user:
        _remember_user(user["id"], user)

def invalidate_user_cache(user_id: str):
    _user_cache.pop(user_id, None)

def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Dependency: Extract and verify current user from Authorization: Bearer <token>."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or malformed Authorization header.")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    user = get_cached_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account not found.")
    return user

# ----------------------------------------------------------------
# Permission Matrix Enforcement (Part 7.9)
# ----------------------------------------------------------------
BUSINESS_ARTIFACTS = {"brd", "prd", "frd", "rules_catalogue", "roles_matrix", "workflow_json", "as_is_report", "to_be_spec"}
TECHNICAL_ARTIFACTS = {"data_model", "hld", "api_spec", "test_plan", "uat_pack", "traceability_matrix", "srs"}

def require_project_member(project_id: str, user: Dict[str, Any]) -> str:
    """Ensure user is an active member of the project and return their role."""
    role = db.get_member_role(project_id, user["id"])
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or you are not an active member.")
    return role

# Every action this matrix knows about. An action that is not listed is denied,
# so adding a new endpoint cannot accidentally be open to everyone.
KNOWN_ACTIONS = frozenset({
    "view",
    "upload_document", "start_run", "cancel_run", "edit_content",
    "invite_member", "revoke_invitation", "resend_invitation", "remove_member",
    "escalate_question",
    "approve_business_rule", "approve_to_be",
    "approve_artifact",
})


def check_permission(action: str, role: str, is_creator: bool = False, artifact_type: Optional[str] = None):
    """Enforce Part 7.9 Permission Matrix deterministically, failing closed.

    Finding F14: the matrix used to end in a bare `return`, so an unrecognised
    action, or an `approve_artifact` whose artifact_type was in neither the
    business nor the technical set, was allowed for every role. Unknown now means
    denied.
    """
    if action not in KNOWN_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Action '{action}' is not permitted.",
        )

    if action == "view":
        return  # Any active member can view

    if action in ("upload_document", "start_run", "cancel_run", "edit_content"):
        if role not in ("process_owner", "analyst"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an Analyst or Process Owner can perform this action.")
        return

    if action in ("invite_member", "revoke_invitation", "resend_invitation", "remove_member"):
        if role == "process_owner" or is_creator:
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the Process Owner or project creator can manage team members and invitations.")

    if action == "escalate_question":
        if role != "analyst":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an Analyst can escalate questions to the Process Owner.")
        return

    if action in ("approve_business_rule", "approve_to_be"):
        if role != "process_owner":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a Process Owner can approve business rules and the To-Be process.")
        return

    if action == "approve_artifact":
        art = (artifact_type or "").lower()
        if art in BUSINESS_ARTIFACTS:
            if role != "process_owner":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Only a Process Owner can approve business artifact '{art}'.")
            return
        if art in TECHNICAL_ARTIFACTS:
            if role != "technical_reviewer":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Only a Technical Reviewer can approve technical artifact '{art}'.")
            return
        # An artifact type nobody has classified must not be approvable by anyone.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Artifact type '{art or 'unknown'}' has no approval rule, so it "
                "cannot be approved. Classify it as a business or technical "
                "artifact first."
            ),
        )

    # Unreachable: every known action returns above. Deny by default.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Action '{action}' is not permitted for your role.",
    )
