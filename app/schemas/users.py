"""User and authentication Pydantic models."""
import re
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

class UserRegisterRequest(BaseModel):
    display_name: str = Field(..., min_length=2, max_length=100)
    email: str
    password: str = Field(..., min_length=8)
    repeat_password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if not re.match(EMAIL_REGEX, v_clean):
            raise ValueError("Invalid email format.")
        return v_clean

class UserLoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.strip().lower()

class UserResponse(BaseModel):
    id: str
    display_name: str
    email: str
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
