"""Account dashboard access, separate from biometric or integration assertions."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class AccountPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,31}$")
    password: SecretStr = Field(min_length=12, max_length=128)


class AccountAccessSetupRequest(AccountPasswordRequest):
    username: str = Field(
        pattern=r"^0[0-9]{9}$",
        description="Số điện thoại đã xác thực OTP, được server đối chiếu với tài khoản.",
    )
    profile_consent: Literal[True]
    policy_version: Literal["account-profile-v1"]

    @field_validator("profile_consent", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Explicit boolean consent required")
        return value


class AccountProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str = Field(pattern=r"^acct_[0-9a-f]{32}$")
    username: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,31}$")
    full_name: str | None = Field(max_length=200)
    masked_id_number: str | None = Field(pattern=r"^\*{8}[0-9]{4}$")
    created_at: datetime
    expires_at: datetime
    evaluation_mode: Literal["standard", "manual_full_demo"]
    demo_policy_id: str | None = Field(pattern=r"^[0-9a-f]{64}$")


class AccountAccessSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str = Field(pattern=r"^vca_[A-Za-z0-9_-]{43}$", repr=False)
    expires_at: datetime
    authentication_method: Literal["password", "face"]
    profile: AccountProfile


class AccountLogoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revoked: Literal[True] = True
