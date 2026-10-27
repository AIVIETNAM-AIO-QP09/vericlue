"""Private ML → API artifact; embeddings must never enter ModuleResult or HTTP."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FaceTemplate(BaseModel):
    """Matches contracts/schemas/face_template.schema.json; persist encrypted only."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)
    session_id: str = Field(pattern=r"^ses_[a-zA-Z0-9_-]+$")
    challenge_id: str = Field(min_length=1, max_length=80)
    model_version: str = Field(min_length=1)
    preprocessing: Literal["arcface112-rgb-minus1to1-v1"]
    source_video_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pixels_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    embedding: tuple[float, ...] = Field(min_length=512, max_length=512, repr=False)

    @field_validator("embedding")
    @classmethod
    def unit_vector(cls, values: tuple[float, ...]) -> tuple[float, ...]:
        if any(not math.isfinite(v) or abs(v) > 1 for v in values):
            raise ValueError("Invalid template vector")
        if not math.isclose(math.sqrt(sum(v * v for v in values)), 1, abs_tol=1e-5):
            raise ValueError("Template must be normalized")
        return values
