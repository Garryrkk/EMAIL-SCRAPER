from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

class PersonCreate(BaseModel):
    """Schema for creating a new Person."""
    name: str
    email: Optional[EmailStr] = None
    linkedin_url: Optional[str] = None

class PersonRead(BaseModel):
    """Schema for reading a Person from the database."""
    id: str
    name: str
    email: Optional[EmailStr] = None
    linkedin_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True  # Important: allows SQLAlchemy models to work with Pydantic
        
class SignupRequest(BaseModel):
    """User signup request."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=2, max_length=255)
    company: Optional[str] = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


class UserResponse(BaseModel):
    """User response."""
    id: str
    email: str
    name: str
    company: Optional[str] = None
    plan: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChangePasswordRequest(BaseModel):
    """Change password request."""
    current_password: str
    new_password: str = Field(..., min_length=8)


class ResetPasswordRequest(BaseModel):
    """Reset password request."""
    email: EmailStr


class ResetPasswordConfirm(BaseModel):
    """Reset password confirmation."""
    token: str
    new_password: str = Field(..., min_length=8)