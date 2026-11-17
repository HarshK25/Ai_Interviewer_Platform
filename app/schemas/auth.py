from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid


class UserRegisterRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True
