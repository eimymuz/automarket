import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=8, max_length=72, description="8 a 72 caracteres")
    full_name: str = Field(min_length=3, max_length=150)
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9 ]{10,20}$")


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    role: str
    is_active: bool
    created_at: datetime

    @classmethod
    def from_model(cls, user) -> "UserOut":
        return cls(
            id=user.id, email=user.email, full_name=user.full_name, phone=user.phone,
            role=user.role.name, is_active=user.is_active, created_at=user.created_at,
        )


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut
