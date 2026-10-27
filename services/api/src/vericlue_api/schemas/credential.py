"""Holder-bound BBS issuance contract; no client-provided verdict or identity claims."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vericlue_api.core.signing import decode


class CredentialOfferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    commitment: str = Field(pattern=r"^[A-Za-z0-9_-]{235}$")
    consent: Literal[True]

    @field_validator("consent", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError("Explicit consent required")
        return value

    @model_validator(mode="after")
    def canonical_commitment(self):
        if type(self.consent) is not bool or len(decode(self.commitment)) != 176:
            raise ValueError("Invalid commitment or consent")
        return self


class CredentialIssueRequest(CredentialOfferRequest):
    device_signature: str = Field(min_length=12, max_length=108)


class CredentialAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    algorithm: Literal["ES256-DER"] = "ES256-DER"
    message: str = Field(min_length=80, max_length=2048)
    expires_at: int = Field(ge=0, le=9999999999)


class CredentialKey(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    algorithm: Literal["BBS-BLS12-381-SHA-256-NYM"] = "BBS-BLS12-381-SHA-256-NYM"
    key_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    public_key: str = Field(pattern=r"^[A-Za-z0-9_-]{128}$")


class VerificationClaims(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    protocol: Literal["vericlue-private-verification-v1"] = "vericlue-private-verification-v1"
    issuer: str = Field(pattern=r"^[A-Za-z0-9:/._-]{1,200}$")
    assurance: Literal["server-decision"] = "server-decision"
    verification_completed: Literal[True] = True
    valid_from: int = Field(ge=0, le=9999999999)
    valid_until: int = Field(ge=0, le=9999999999)
    policy_version: Literal["vericlue-session-result-v1"] = "vericlue-session-result-v1"
    source_result_id: str = Field(pattern=r"^res_[a-f0-9]{64}$")
    account_id: str = Field(pattern=r"^acct_[a-f0-9]{32}$")
    device_id: str = Field(pattern=r"^dev_[a-f0-9]{32}$")
    source_purpose: Literal["reauth", "recovery"]

    @model_validator(mode="after")
    def short_lifetime(self):
        if (
            type(self.verification_completed) is not bool
            or not 0 < self.valid_until - self.valid_from <= 60
            or self.valid_from % 10
            or self.valid_until % 10
        ):
            raise ValueError("Invalid credential validity")
        return self


class VerificationCredential(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    claims: VerificationClaims
    signature: str = Field(pattern=r"^[A-Za-z0-9_-]{107}$")
    signer_entropy: str = Field(pattern=r"^[a-f0-9]{64}$")
    key_id: str = Field(pattern=r"^[a-f0-9]{64}$")
