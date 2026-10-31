"""Explicit experimental cutoffs, never fitted probabilities or authentication policy."""

import hashlib
import math

from pydantic import BaseModel, ConfigDict, Field

from vericlue_ml.common.result import Gate, ModuleResult, Status


class ManualDemoThresholds(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    pad_max: float = Field(default=0.50, gt=0, lt=1, allow_inf_nan=False)
    gend_max: float = Field(default=0.50, gt=0, lt=1, allow_inf_nan=False)
    match_min: float = Field(default=0.30, gt=0, lt=1, allow_inf_nan=False)
    consistency_min: float = Field(default=0.30, gt=0, lt=1, allow_inf_nan=False)

    @property
    def policy_id(self) -> str:
        return hashlib.sha256(
            ("manual-face-demo-v1:" + self.model_dump_json()).encode()
        ).hexdigest()

    @property
    def version_suffix(self) -> str:
        return "+manual-demo-" + self.policy_id[:16]

    def accepts_attack(self, result: ModuleResult) -> bool:
        cutoff = {"face_pad": self.pad_max, "face_deepfake": self.gend_max}.get(result.module)
        return bool(
            cutoff is not None
            and result.status == Status.OK
            and result.error_code is None
            and result.gate != Gate.FAIL
            and not result.model_version.startswith("mock")
            and type(result.score) in (float, int)
            and math.isfinite(result.score)
            and 0 <= result.score <= cutoff
        )
