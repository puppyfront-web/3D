"""User schemas."""

import uuid
from datetime import datetime
from typing import Optional

from app.schemas.common import APIBaseModel
from pydantic import EmailStr, Field


class RoleBase(APIBaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(APIBaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None


class RoleOut(RoleBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class UserBase(APIBaseModel):
    email: str = Field(..., max_length=255)
    name: str = Field(..., max_length=255)


class UserCreate(UserBase):
    role_id: uuid.UUID
    is_active: bool = True


class UserUpdate(APIBaseModel):
    email: Optional[str] = Field(None, max_length=255)
    name: Optional[str] = Field(None, max_length=255)
    avatar_url: Optional[str] = Field(None, max_length=500)
    role_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class UserOut(UserBase):
    id: uuid.UUID
    avatar_url: Optional[str] = None
    role_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    role: Optional["RoleOut"] = None


class LoginRequest(APIBaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=1)


class LoginResponse(APIBaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
