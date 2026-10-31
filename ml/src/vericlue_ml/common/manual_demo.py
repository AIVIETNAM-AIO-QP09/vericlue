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
        if not (
            cutoff is not None
            and result.status == Status.OK
            and result.error_code is None
            and result.gate != Gate.FAIL
            and not result.model_version.startswith("mock")
            and type(result.score) in (float, int)
            and math.isfinite(result.score)
            and 0 <= result.score <= 1
        ):
            return False
        score = result.score
        if result.module == "face_deepfake":
            views = next(
                (
                    e.value
                    for e in result.evidence
                    if e.name == "view_scores" and isinstance(e.value, dict)
                ),
                None,
            )
            if views is not None:
                expected_views = (
                    {"front"}
                    if result.quality.get("sampling") == "single-frame-v1"
                    else {"front", "left", "right"}
                )
                if set(views) != expected_views or any(
                    type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1
                    for v in views.values()
                ):
                    return False
                score = views["front"]
        return 0 <= score <= cutoff

    def accepts_voice_spoof(self, result: ModuleResult | None) -> bool:
        if (
            result is None
            or result.module != "voice_spoof"
            or result.status != Status.OK
            or result.error_code is not None
            or result.gate == Gate.FAIL
            or result.model_version.startswith("mock")
            or result.quality.get("diagnostic_only") is True
        ):
            return False
        windows = next(
            (
                e.value
                for e in result.evidence
                if e.name == "nes2net_windows" and isinstance(e.value, list)
            ),
            None,
        )
        if windows is not None:
            if (
                not windows
                or result.quality.get("error_windows", 0) != 0
                or result.quality.get("low_quality_windows", 0) != 0
                or result.quality.get("all_source_samples_measured") is not True
                or result.quality.get("planned_windows") not in (None, len(windows))
                or result.quality.get("measured_windows") not in (None, len(windows))
            ):
                return False
            for row in windows:
                if not isinstance(row, dict) or not isinstance(row.get("result"), dict):
                    return False
                w = row["result"]
                w_quality = w.get("quality") if isinstance(w.get("quality"), dict) else {}
                if (
                    w.get("status") != "ok"
                    or w.get("error_code") is not None
                    or w.get("gate") == "fail"
                    or w_quality.get("diagnostic_only") is True
                    or type(w.get("score")) not in (float, int)
                    or not math.isfinite(w["score"])
                    or w["score"] > 2.0
                ):
                    return False
            return True
        return (
            type(result.prob_attack) in (float, int)
            and math.isfinite(result.prob_attack)
            and 0 <= result.prob_attack <= 0.5
        )
