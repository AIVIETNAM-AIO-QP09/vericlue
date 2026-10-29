"""Versioned developer contract, separate from VeriClue's public session API."""

from typing import Literal

from pydantic import BaseModel, Field


class OCRLine(BaseModel):
    text: str
    confidence: float = Field(ge=0, le=1)
    polygon: list[list[float]]
    alternate_text: str | None = None
    alternate_confidence: float | None = None
    words: list[str] = Field(default_factory=list)
    word_regions: list[list[list[float]]] = Field(default_factory=list)


class FieldCandidates(BaseModel):
    id_number_candidates: list[str]
    date_candidates: list[str]


class Reread(BaseModel):
    text: str
    confidence: float
    padding_ratio: float
    polygon: list[list[float]]
    source_line_id: int


class ExtractedField(BaseModel):
    value: str | None
    status: Literal["missing", "consistent", "review"]
    source_line_ids: list[int]
    candidates: list[str]
    reasons: list[str]
    original_value: str | None = None
    rereads: list[Reread] = Field(default_factory=list)


class OCRResult(BaseModel):
    schema_version: Literal["identity-lab/v2"]
    fields: dict[str, ExtractedField]
    document_status: Literal["review", "retry"]
    coordinate_space: Literal["exif_corrected_input_pixels"]
    status: Literal["ok", "retry"]
    reason: str | None
    model: str
    lines: list[OCRLine]
    candidates: FieldCandidates
    alternate_candidates: FieldCandidates
    qr_payloads: list[str]
    identity_verified: Literal[False]
    warnings: list[str]
    elapsed_ms: float


class MatchResult(BaseModel):
    schema_version: Literal["identity-lab/v1"]
    status: Literal["ok"]
    model: str
    cosine_similarity: float = Field(ge=-1, le=1)
    decision: Literal["not_calibrated"]
    threshold: None
    reference_bbox: list[float]
    selfie_bbox: list[float]
    identical_files: bool
    warnings: list[str]
    elapsed_ms: float


class FaceEvidence(BaseModel):
    bbox: list[float]
    landmarks: list[list[float]]
    detection_score: float
    quality: dict[str, float]
    warnings: list[str]


class FacePairResult(BaseModel):
    schema_version: Literal["face-pair-lab/v2"]
    status: Literal["ok", "retry"]
    reason: str | None
    decision: Literal["review", "retry"]
    identity_verified: Literal[False]
    cosine_similarity: float | None = Field(default=None, ge=-1, le=1)
    threshold: None = None
    model: str
    embedding_mode: Literal["single", "flip_mean"] = "single"
    reference_roi: list[int] | None = None
    coordinate_space: Literal["exif_corrected_input_pixels"] = "exif_corrected_input_pixels"
    reference: FaceEvidence | None = None
    selfie: FaceEvidence | None = None
    identical_pixels: bool
    warnings: list[str]
    elapsed_ms: float
