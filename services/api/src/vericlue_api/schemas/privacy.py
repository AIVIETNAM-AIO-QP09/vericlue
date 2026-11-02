"""Session privacy requests/receipts matching privacy.schema.json."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

PrivacyCategory = Literal["contact", "id_document", "face_biometrics", "voice_biometrics"]


class PrivacyConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_version: str = Field(pattern=r"^[A-Za-z0-9._-]{1,64}$")
    categories: list[PrivacyCategory] = Field(
        min_length=1, max_length=4, json_schema_extra={"uniqueItems": True}
    )
    consent: StrictBool = Field(json_schema_extra={"const": True})

    @field_validator("categories")
    @classmethod
    def distinct_categories(cls, value: list[PrivacyCategory]) -> list[PrivacyCategory]:
        if len(set(value)) != len(value):
            raise ValueError("Duplicate privacy category")
        return value

    @field_validator("consent")
    @classmethod
    def affirmative(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Explicit consent required")
        return value


class PrivacyWithdrawalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: StrictBool = Field(json_schema_extra={"const": True})

    @field_validator("confirm")
    @classmethod
    def affirmative(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Explicit confirmation required")
        return value


class PrivacyState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(pattern=r"^ses_[A-Za-z0-9_-]{1,120}$")
    scope: Literal["session"] = "session"
    policy_version: str = Field(pattern=r"^[A-Za-z0-9._-]{1,64}$")
    status: Literal["not_granted", "granted", "withdrawn"]
    categories: list[PrivacyCategory] = Field(max_length=4, json_schema_extra={"uniqueItems": True})
    consent_receipt_id: str | None = Field(default=None, pattern=r"^prv_[0-9a-f]{32}$")
    consented_at: datetime | None = None
    withdrawal_receipt_id: str | None = Field(default=None, pattern=r"^prv_[0-9a-f]{32}$")
    withdrawn_at: datetime | None = None
    storage_erasure: Literal["not_requested", "key_destroyed", "files_deleted"] = "not_requested"
    processing_cleanup: Literal["not_applicable", "not_verified"] = "not_applicable"
    account_data_erased: Literal[False] = False
    credential_revocation: Literal["not_performed"] = "not_performed"


class AccountTemplateConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_version: str = Field(pattern=r"^[A-Za-z0-9._-]{1,64}$")
    purpose: Literal["account_template"] = Field(json_schema_extra={"const": "account_template"})
    consent: StrictBool = Field(json_schema_extra={"const": True})

    @field_validator("consent")
    @classmethod
    def affirmative(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Explicit consent required")
        return value


class AccountTemplatePrivacyState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(pattern=r"^ses_[A-Za-z0-9_-]{1,120}$")
    scope: Literal["account_template"] = "account_template"
    purpose: Literal["account_template"] = "account_template"
    policy_version: str = Field(pattern=r"^[A-Za-z0-9._-]{1,64}$")
    retention_seconds: Literal[86400] = 86400
    status: Literal["not_granted", "granted", "withdrawn"]
    consent_receipt_id: str | None = Field(default=None, pattern=r"^prv_[0-9a-f]{32}$")
    consented_at: datetime | None = None
