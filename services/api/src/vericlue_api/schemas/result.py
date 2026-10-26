"""Matches result.schema.json; strict integration data, never biometric evidence."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SigningKey(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    algorithm: Literal["Ed25519"] = "Ed25519"
    key_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    public_key_spki: str = Field(min_length=40, max_length=128)


class SignedResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    algorithm: Literal["Ed25519"]
    key_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload: str = Field(min_length=16, max_length=4096, pattern=r"^[A-Za-z0-9_-]+$")
    signature: str = Field(min_length=86, max_length=86, pattern=r"^[A-Za-z0-9_-]+$")


class ResultClaims(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal[1]
    issuer: str = Field(pattern=r"^[A-Za-z0-9:/._-]{1,200}$")
    audience: str = Field(pattern=r"^[A-Za-z0-9:/._-]{1,200}$")
    result_id: str = Field(pattern=r"^res_[0-9a-f]{64}$")
    session_id: str = Field(pattern=r"^ses_[A-Za-z0-9_-]{1,120}$")
    purpose: Literal["reauth", "recovery"]
    nonce: str = Field(pattern=r"^[A-Za-z0-9_-]{16,128}$")
    status: Literal["pass", "deny", "recovery_required"]
    issued_at: int = Field(ge=0, le=9999999999)
    expires_at: int = Field(ge=0, le=9999999999)
    account_id: str | None = Field(default=None, pattern=r"^acct_[0-9a-f]{32}$")
    device_id: str | None = Field(default=None, pattern=r"^dev_[0-9a-f]{32}$")

    @field_validator("version", mode="before")
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError("Integer protocol version required")
        return value

    @model_validator(mode="after")
    def bounded_lifetime_and_identity(self):
        if not 0 < self.expires_at - self.issued_at <= 60:
            raise ValueError("Invalid result lifetime")
        if self.status == "pass" and (not self.account_id or not self.device_id):
            raise ValueError("Successful account context required")
        if (self.account_id is None) != (self.device_id is None):
            raise ValueError("Incomplete account context")
        if self.purpose == "recovery" and self.status != "pass":
            raise ValueError("Recovery only issues a successful device replacement")
        return self
