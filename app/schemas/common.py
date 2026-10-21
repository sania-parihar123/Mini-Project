"""Common Pydantic models for ProcessFoundry AI."""
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict

class StatusResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 28800  # 8 hours in seconds
    user: dict
