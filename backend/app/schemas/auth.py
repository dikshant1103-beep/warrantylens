from pydantic import BaseModel, EmailStr

from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_slug: str | None = None  # required only if the email exists in >1 tenant


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
