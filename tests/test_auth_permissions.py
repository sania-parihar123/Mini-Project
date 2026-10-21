"""Tests for Authentication, Password Security, Tokens, Lockout, and Permissions (SPEC-01, SPEC-02)."""
import pytest
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException

from app.repositories.database import db
from app.services.permissions import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    check_permission
)
from app.api.auth import register, login
from app.schemas.users import UserRegisterRequest, UserLoginRequest

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_auth.db")
    monkeypatch.setattr(db, "sqlite_path", test_db_path)
    monkeypatch.setattr(db, "use_postgres", False)
    db._init_sqlite()

def test_password_hashing_and_verification():
    """SPEC-01: Password must be hashed using bcrypt and verified accurately.

    Covers SPEC-14-01.
    """
    plain = "SuperSecret123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPass123!", hashed) is False

def test_user_registration_success():
    """SPEC-01: User registration with display name, email, and password.

    Covers SPEC-14-01.
    """
    req = UserRegisterRequest(
        display_name="Dr. Aris",
        email="aris@university.edu",
        password="ValidPassword123!",
        repeat_password="ValidPassword123!"
    )
    res = register(req)
    assert res.access_token is not None
    assert res.user["email"] == "aris@university.edu"
    assert res.user["display_name"] == "Dr. Aris"

    # Verify stored in DB
    user = db.get_user_by_email("aris@university.edu")
    assert user is not None
    assert verify_password("ValidPassword123!", user["password_hash"])

def test_user_registration_duplicate_email_rejected():
    """SPEC-01: Re-registration with same email returns HTTP 400.

    Covers SPEC-14-01.
    """
    req = UserRegisterRequest(
        display_name="Dr. Aris",
        email="duplicate@university.edu",
        password="ValidPassword123!",
        repeat_password="ValidPassword123!"
    )
    register(req)

    with pytest.raises(HTTPException) as exc_info:
        register(req)
    assert exc_info.value.status_code == 400
    assert "already has an account" in exc_info.value.detail

def test_user_login_success_and_failure():
    """SPEC-01: Login with correct password succeeds; wrong password returns 401.

    Covers SPEC-14-02.
    """
    pwd_hash = hash_password("CorrectPassword123!")
    db.create_user("Test User", "testlogin@university.edu", pwd_hash)

    # Correct login
    res = login(UserLoginRequest(email="testlogin@university.edu", password="CorrectPassword123!"))
    assert res.access_token is not None
    assert res.user["email"] == "testlogin@university.edu"

    # Wrong password
    with pytest.raises(HTTPException) as exc_info:
        login(UserLoginRequest(email="testlogin@university.edu", password="WrongPassword123!"))
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "E-mail or password is incorrect."

def test_user_lockout_after_five_failed_attempts():
    """SPEC-01: Account locked for 10 minutes after 5 consecutive failed login attempts.

    Covers SPEC-14-02.
    """
    pwd_hash = hash_password("ValidPassword123!")
    db.create_user("Lockout Target", "target@university.edu", pwd_hash)

    # 4 failed attempts should return 401
    for _ in range(4):
        with pytest.raises(HTTPException) as exc:
            login(UserLoginRequest(email="target@university.edu", password="BadPassword!"))
        assert exc.value.status_code == 401

    # 5th failed attempt triggers lockout HTTP 429
    with pytest.raises(HTTPException) as exc:
        login(UserLoginRequest(email="target@university.edu", password="BadPassword!"))
    assert exc.value.status_code == 429
    assert "locked for 10 minutes" in exc.value.detail

def test_token_creation_and_expiration():
    """SPEC-01: Tokens are signed with 8-hour expiry.

    Covers SPEC-14-03, SPEC-12-01.
    """
    token = create_access_token("usr_123", "token@example.com")
    payload = decode_access_token(token)
    assert payload["sub"] == "usr_123"
    assert payload["email"] == "token@example.com"

def test_permission_matrix_enforcement():
    """SPEC-02: Enforce Part 7.9 role permission matrix.

    Covers SPEC-14-06, SPEC-00-04.
    """
    # Process owner can approve To-Be
    check_permission("approve_to_be", role="process_owner")

    # Analyst CANNOT approve To-Be (must raise 403)
    with pytest.raises(HTTPException) as exc:
        check_permission("approve_to_be", role="analyst")
    assert exc.value.status_code == 403

    # Viewer CANNOT upload documents
    with pytest.raises(HTTPException) as exc:
        check_permission("upload_document", role="viewer")
    assert exc.value.status_code == 403

    # Only Process Owner can approve business artifacts like BRD
    check_permission("approve_artifact", role="process_owner", artifact_type="brd")
    with pytest.raises(HTTPException) as exc:
        check_permission("approve_artifact", role="technical_reviewer", artifact_type="brd")
    assert exc.value.status_code == 403

    # Only Technical Reviewer can approve technical artifacts like HLD
    check_permission("approve_artifact", role="technical_reviewer", artifact_type="hld")
    with pytest.raises(HTTPException) as exc:
        check_permission("approve_artifact", role="process_owner", artifact_type="hld")
    assert exc.value.status_code == 403
