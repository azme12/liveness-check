from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    organization_name: str = Field(min_length=2, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class ClientCreate(BaseModel):
    type: Literal["person", "company"] = "person"
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    company_name: str | None = None
    email: EmailStr | None = None
    mobile: str | None = None
    nationality: str | None = None
    date_of_birth: str | None = None
    external_id: str | None = None


class ClientBulkDelete(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=100)


class ClientOut(BaseModel):
    id: str
    name: str
    email: str | None = None
    risk: str = "low"
    type: str = "person"
    created_at: datetime


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=lambda: [{"type": "identity_check", "label": "Identity Check"}])


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: Literal["active", "inactive", "draft", "archived"] | None = None
    steps: list[dict[str, Any]] | None = None


class WorkflowVersionUpdate(BaseModel):
    description: str | None = None
    status: Literal["active", "inactive"] | None = None
    steps: list[dict[str, Any]] | None = None


class WebhookCreate(BaseModel):
    url: str
    description: str | None = None
    events: list[str] = Field(
        default_factory=lambda: [
            "check.completed",
            "check.failed",
            "check.updated",
            "check.monitoring.attention",
        ]
    )
    enabled: bool = True


class WebhookUpdate(BaseModel):
    url: str | None = None
    description: str | None = None
    events: list[str] | None = None
    enabled: bool | None = None


class AllowedIpCreate(BaseModel):
    cidr: str = Field(min_length=3, max_length=64)
    label: str = Field(default="", max_length=120)


class ProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=60)
    last_name: str | None = Field(default=None, min_length=1, max_length=60)
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=120)


class NotificationPrefsUpdate(BaseModel):
    email_checks: bool | None = None
    email_webhooks: bool | None = None
    in_app: bool | None = None


class ActivationBusinessDetails(BaseModel):
    legal_company_name: str = Field(min_length=2, max_length=200)
    registration_number: str = Field(min_length=1, max_length=80)
    tax_number: str | None = Field(default=None, max_length=80)
    incorporation_country: str = Field(min_length=2, max_length=80)
    industry: str = Field(min_length=2, max_length=120)


class ActivationBusinessAddress(BaseModel):
    line1: str = Field(min_length=2, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=2, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    postal_code: str = Field(min_length=2, max_length=40)
    country: str = Field(min_length=2, max_length=80)


class ActivationUsage(BaseModel):
    monthly_volume: str = Field(min_length=1, max_length=80)
    primary_use_case: str = Field(min_length=2, max_length=200)
    regions: str = Field(default="", max_length=200)


class ActivationIdentity(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    role: str = Field(min_length=2, max_length=80)
    confirmed: bool = True


class Paginated(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    pages: int
