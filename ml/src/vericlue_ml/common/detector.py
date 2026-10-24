"""Giao diện chung của mọi bộ phát hiện (`docs/architecture/architecture.md` §3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from vericlue_ml.common.result import ModuleResult


class DetectorInput(BaseModel):
    """Đầu vào cho một bộ phát hiện. Bộ nào dùng trường nào thì đọc trường đó."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    session_id: str | None = None
    images: list[Path] = Field(default_factory=list, description="Ảnh mặt chất lượng cao")
    image_roles: list[Literal["front", "left", "right"]] = Field(default_factory=list)
    reference_image: Path | None = None
    video: Path | None = None
    audio: Path | None = None
    signals: dict[str, Any] = Field(
        default_factory=dict, description="Tín hiệu trình duyệt đo (schema Signals)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Ví dụ: scenario (cho mock), challenge, câu đề bài"
    )


@runtime_checkable
class Detector(Protocol):
    """Mọi bộ phát hiện (thật hay mock) đều có dạng này."""

    name: str
    version: str

    def predict(self, inp: DetectorInput) -> ModuleResult: ...
