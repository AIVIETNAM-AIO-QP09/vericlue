"""Validated, immutable threshold snapshot; raw-file hash identifies every decision."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class FaceConfig(FrozenConfig):
    b: float = Field(ge=0, le=1)
    a: float = Field(ge=0, le=1)
    sources: dict[str, str]

    @model_validator(mode="after")
    def ordered(self) -> FaceConfig:
        if any(not self.sources.get(key, "").strip() for key in ("b", "a")):
            raise ValueError("Source required for each face threshold")
        if self.b >= self.a:
            raise ValueError("face.b must be less than face.a")
        return self


class VoiceConfig(FrozenConfig):
    spoof_threshold: float = Field(ge=0, le=1)
    max_syllable_wer: float = Field(ge=0)
    min_unaccented_similarity: float = Field(ge=0, le=1)
    sources: dict[str, str]

    @model_validator(mode="after")
    def documented_sources(self) -> VoiceConfig:
        if any(
            not self.sources.get(key, "").strip()
            for key in ("spoof_threshold", "max_syllable_wer", "min_unaccented_similarity")
        ):
            raise ValueError("Source required for each voice threshold")
        return self


class FusionConfig(FrozenConfig):
    method: str
    source: str

    @model_validator(mode="after")
    def implemented(self) -> FusionConfig:
        if self.method != "max" or not self.source.strip():
            raise ValueError("Only provisional max is enabled; learned artifacts require review")
        return self


class RouterConfig(FrozenConfig):
    version: str
    provisional: bool
    face: FaceConfig
    voice: VoiceConfig
    fusion: FusionConfig
    config_version: str

    def snapshot(self) -> dict:
        """Internal audit metadata, never a citizen response."""
        return self.model_dump(exclude={"config_version"})


def load_config(path: str | Path | None = None) -> RouterConfig:
    """Read once at application startup; explicit path overrides THRESHOLDS_CONFIG."""
    selected = path or os.getenv("THRESHOLDS_CONFIG")
    source = (
        Path(selected)
        if selected
        else Path(__file__).resolve().parents[3] / "configs/thresholds.yaml"
    )
    raw = source.read_bytes()
    values = yaml.safe_load(raw)
    if not isinstance(values, dict) or "config_version" in values:
        raise ValueError("Invalid thresholds config: config_version is derived from raw bytes")
    return RouterConfig(**values, config_version="sha256:" + hashlib.sha256(raw).hexdigest())
