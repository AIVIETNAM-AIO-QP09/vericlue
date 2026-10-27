"""Holder-bound BBS issuance contract; no client-provided verdict or identity claims."""

from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

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


class VerificationDisclosed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    protocol: Literal["vericlue-private-verification-v1"]
    issuer: str = Field(pattern=r"^[A-Za-z0-9:/._-]{1,200}$")
    assurance: Literal["server-decision"]
    verification_completed: Literal[True]
    valid_from: int = Field(ge=0, le=9999999999)
    valid_until: int = Field(ge=0, le=9999999999)
    policy_version: Literal["vericlue-session-result-v1"]

    @field_validator("verification_completed", mode="before")
    @classmethod
    def true_boolean(cls, value):
        if type(value) is not bool or not value:
            raise ValueError("Explicit boolean required")
        return value

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


class VerificationClaims(VerificationDisclosed):
    protocol: Literal["vericlue-private-verification-v1"] = "vericlue-private-verification-v1"
    assurance: Literal["server-decision"] = "server-decision"
    verification_completed: Literal[True] = True
    policy_version: Literal["vericlue-session-result-v1"] = "vericlue-session-result-v1"
    source_result_id: str = Field(pattern=r"^res_[a-f0-9]{64}$")
    account_id: str = Field(pattern=r"^acct_[a-f0-9]{32}$")
    device_id: str = Field(pattern=r"^dev_[a-f0-9]{32}$")
    source_purpose: Literal["reauth", "recovery"]


class VerificationCredential(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    claims: VerificationClaims
    signature: str = Field(pattern=r"^[A-Za-z0-9_-]{107}$")
    signer_entropy: str = Field(pattern=r"^[a-f0-9]{64}$")
    key_id: str = Field(pattern=r"^[a-f0-9]{64}$")


def https_origin(value: str) -> str:
    """Require a canonical HTTPS origin, matching the Node verifier's URL origin."""
    parsed = AnyHttpUrl(value)
    if (
        not value.isascii()
        or not 9 <= len(value) <= 200
        or parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or str(parsed) != value + "/"
    ):
        raise ValueError("Canonical HTTPS origin required")
    return value


class CredentialChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class VerificationChallenge(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{22}$")
    nonce: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    audience: str = Field(min_length=9, max_length=200)
    format: Literal["bbs-nym"] = "bbs-nym"
    policy: Literal["verified"] = "verified"
    issued_at: int = Field(ge=0, le=9999999999)
    expires_at: int = Field(ge=0, le=9999999999)

    @field_validator("audience")
    @classmethod
    def origin(cls, value: str) -> str:
        return https_origin(value)

    @model_validator(mode="after")
    def lifetime(self):
        if not 0 < self.expires_at - self.issued_at <= 60:
            raise ValueError("Invalid challenge lifetime")
        return self


class VerificationPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    protocol: Literal["vericlue-private-verification-v1"]
    challenge_id: str = Field(pattern=r"^[A-Za-z0-9_-]{22}$")
    disclosed: VerificationDisclosed
    proof: str = Field(pattern=r"^[A-Za-z0-9_-]{662}$")
    pseudonym: str = Field(pattern=r"^[A-Za-z0-9_-]{64}$")


class VerificationRejected(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    valid: Literal[False] = False


class VerificationAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    valid: Literal[True] = True
    assurance: Literal["server-decision"] = "server-decision"
    disclosed: VerificationDisclosed
    pseudonym: str = Field(pattern=r"^[A-Za-z0-9_-]{64}$")
