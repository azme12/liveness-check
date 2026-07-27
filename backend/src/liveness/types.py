"""Shared enums and value objects for checks."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


def utc_now() -> datetime:
    return datetime.now(UTC)


class CheckType(StrEnum):
    DOCUMENT = "document_check"
    IDENTITY = "identity_check"
    ENHANCED_IDENTITY = "enhanced_identity_check"
    FACE_AUTHENTICATION = "face_authentication_check"
    AGE_ESTIMATION = "age_estimation_check"
    PROOF_OF_ADDRESS = "proof_of_address_check"
    DRIVING_LICENSE = "driving_license_check"
    STANDARD_SCREENING = "standard_screening_check"
    EXTENSIVE_SCREENING = "extensive_screening_check"
    IDENTITY_FRAUD = "identity_fraud_check"
    DEVICE_INTELLIGENCE = "device_intelligence_check"
    EMAIL_INTELLIGENCE = "email_intelligence_check"
    MOBILE_INTELLIGENCE = "mobile_intelligence_check"
    MULTI_BUREAU = "multi_bureau_check"
    EID = "eid_check"
    SSN = "ssn_check"


class CheckStatus(StrEnum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


class CheckOutcome(StrEnum):
    CLEAR = "clear"
    CONSIDER = "consider"
    REJECT = "reject"


class SessionStatus(StrEnum):
    PENDING = "pending"
    CAPTURING = "capturing"
    PROCESSING = "processing"
    COMPLETE = "complete"
    EXPIRED = "expired"


class StructuredDate(BaseModel):
    day: int = Field(ge=1, le=31)
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=1900, le=2100)


class DocumentFields(BaseModel):
    full_name: str | None = None
    document_number: str | None = None
    nationality: str | None = None
    date_of_birth: StructuredDate | None = None
    expiry_date: StructuredDate | None = None
    sex: str | None = None
    issuing_country: str | None = None


class BiometricResult(BaseModel):
    liveness: str = "unknown"  # live | spoof | unknown
    liveness_score: float = 0.0
    face_match_score: float | None = None
    face_match_passed: bool | None = None
    face_detected: bool = False


class DocumentResult(BaseModel):
    valid: bool = False
    mrz_valid: bool | None = None
    quality_score: float = 0.0
    document_type: str | None = None
    fields: DocumentFields = Field(default_factory=DocumentFields)
    warnings: list[str] = Field(default_factory=list)


class CheckResult(BaseModel):
    outcome: CheckOutcome
    document: DocumentResult | None = None
    biometric: BiometricResult | None = None
    matches: list[dict[str, Any]] | None = None
    risk_score: float | None = None
    signals: dict[str, Any] | None = None
    explainability: list[str] = Field(default_factory=list)
    model_versions: dict[str, str] = Field(default_factory=dict)
