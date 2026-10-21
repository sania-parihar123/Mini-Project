"""Authentication and current user endpoints."""
import re
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, status

from app.schemas.users import UserRegisterRequest, UserLoginRequest, UserResponse
from app.schemas.common import TokenResponse
from app.repositories.database import db
from app.services.permissions import hash_password, verify_password, create_access_token, get_current_user, cache_user

router = APIRouter(prefix="/api", tags=["Authentication"])

@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: UserRegisterRequest):
    email_clean = req.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_clean):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email format.")

    if req.password != req.repeat_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match.")

    if len(req.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters.")

    if req.password.lower() == email_clean:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password cannot be identical to email.")

    existing = db.get_user_by_email(email_clean)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That e-mail already has an account.")

    pwd_hash = hash_password(req.password)
    user = db.create_user(req.display_name, email_clean, pwd_hash)
    cache_user(user)
    token = create_access_token(user["id"], user["email"])
    return TokenResponse(
        access_token=token,
        user={
            "id": user["id"],
            "display_name": user["display_name"],
            "email": user["email"]
        }
    )

@router.post("/auth/login", response_model=TokenResponse)
def login(req: UserLoginRequest):
    email_clean = req.email.strip().lower()
    user = db.get_user_by_email(email_clean)

    # Generic error message required by Part 7.3
    GENERIC_ERROR = "E-mail or password is incorrect."

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_ERROR)

    # Check lockout
    locked_until = user.get("locked_until")
    if locked_until:
        try:
            lock_time = datetime.fromisoformat(locked_until.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) < lock_time:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Account locked for 10 minutes after 5 failed attempts. Please try again later."
                )
        except (ValueError, TypeError):
            pass

    if not verify_password(req.password, user["password_hash"]):
        failed = user.get("failed_attempts", 0) + 1
        new_lock = None
        if failed >= 5:
            new_lock = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
            db.update_user_failed_attempts(email_clean, 0, locked_until=new_lock)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Account locked for 10 minutes after 5 failed attempts. Please try again later."
            )
        else:
            db.update_user_failed_attempts(email_clean, failed)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_ERROR)

    # Login successful: reset failed attempts and record last login
    db.update_user_login_success(email_clean)
    cache_user(user)
    token = create_access_token(user["id"], user["email"])
    return TokenResponse(
        access_token=token,
        user={
            "id": user["id"],
            "display_name": user["display_name"],
            "email": user["email"]
        }
    )

@router.get("/me", response_model=UserResponse)
def get_me(user: dict = Depends(get_current_user)):
    return UserResponse(
        id=user["id"],
        display_name=user["display_name"],
        email=user["email"],
        last_login_at=user.get("last_login_at"),
        created_at=user.get("created_at")
    )
