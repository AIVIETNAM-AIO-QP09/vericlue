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

    # Illustrative demo cutoffs, never fitted to evaluation samples.
    spoof_max: float = Field(default=0.50, gt=0, lt=1, allow_inf_nan=False)
    lipsync_max: float = Field(default=0.50, gt=0, lt=1, allow_inf_nan=False)

    @property
    def policy_id(self) -> str:
        return hashlib.sha256(
            ("manual-full-demo-v2:" + self.model_dump_json()).encode()
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

    def _voice_valid(self, result: ModuleResult, *, bound: bool) -> bool:
        from vericlue_ml.voice.antispoof import AntiDeepfakeDetector
        from vericlue_ml.voice.syncnet import SyncNetDetector

        versions = {
            "voice_spoof": AntiDeepfakeDetector().version,
            "lipsync": SyncNetDetector().version,
        }
        expected = versions.get(result.module)
        if (
            expected is None
            or result.model_version != expected + (self.version_suffix if bound else "")
            or result.status != Status.OK
            or result.error_code is not None
            or result.gate == Gate.FAIL
            or result.prob_attack is not None
            or result.quality.get("diagnostic_only") is True
            or not _number(result.score, 0, 1)
        ):
            return False
        if bound and (
            result.gate != Gate.PASS
            or result.quality.get("manual_demo") is not True
            or result.quality.get("calibrated") is not False
            or result.quality.get("demo_policy_id") != self.policy_id
        ):
            return False

        def evidence(name):
            rows = [e.value for e in result.evidence if e.name == name]
            return rows[0] if len(rows) == 1 else None

        if result.module == "lipsync":
            flags = evidence("splice_flags")
            return (
                type(flags) is int
                and flags == 0
                and _number(evidence("av_offset_ms"), -600, 600)
                and _number(evidence("sync_confidence"), 0, 1)
                and _number(evidence("best_offset_confidence"), 0, 1)
                and (not bound or result.quality.get("hardware_clock_verified") is False)
            )
        windows = evidence("window_scores")
        quality = result.quality
        duration, speech, trim = (
            quality.get(k) for k in ("duration_s", "speech_duration_s", "trim_start_s")
        )
        if (
            not isinstance(windows, list)
            or not windows
            or not _number(quality.get("n_windows"), 1)
            or quality["n_windows"] != len(windows)
            or not _number(duration, 1, 120)
            or not _number(speech, 1, duration)
            or not _number(trim, 0, duration - speech + 1e-6)
        ):
            return False
        previous_end = trim
        for row in windows:
            if not isinstance(row, dict):
                return False
            start, end, logits = row.get("start_s"), row.get("end_s"), row.get("logits")
            if (
                not _number(start, trim, previous_end + 1e-6)
                or not _number(end, start, trim + speech + 1e-6)
                or end <= start
                or not _number(row.get("score"), 0, 1)
                or not isinstance(logits, list)
                or len(logits) != 2
                or not all(_number(v) for v in logits)
            ):
                return False
            previous_end = end
        return abs(previous_end - (trim + speech)) <= 1e-6

    def apply_voice(self, result: ModuleResult) -> ModuleResult:
        """Label valid raw inference only; preserve all failure states and evidence."""
        valid = self._voice_valid(result, bound=False)
        cutoff = self.spoof_max if result.module == "voice_spoof" else self.lipsync_max
        quality = {
            **result.quality,
            "manual_demo": True,
            "calibrated": False,
            "demo_policy_id": self.policy_id,
        }
        if result.module == "lipsync":
            quality["hardware_clock_verified"] = False
        return result.model_copy(
            update={
                "model_version": result.model_version + self.version_suffix,
                "prob_attack": None,
                "quality": quality,
                "status": result.status if valid or result.status != Status.OK else Status.DEGRADED,
                "gate": (Gate.PASS if result.score <= cutoff else Gate.FAIL)
                if valid
                else Gate.UNCLEAR,
            }
        )

    def accepts_voice_spoof(self, result: ModuleResult | None) -> bool:
        return (
            result is not None
            and result.module == "voice_spoof"
            and self._voice_valid(result, bound=True)
            and result.score <= self.spoof_max
        )

    def accepts_lipsync(self, result: ModuleResult | None) -> bool:
        return (
            result is not None
            and result.module == "lipsync"
            and self._voice_valid(result, bound=True)
            and result.score <= self.lipsync_max
        )


def _number(value, minimum=-math.inf, maximum=math.inf) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum


# Fixed engineering choices for phone-demo-fixed-v1, not fitted operating points.
# Keep the existing six-value policy hash and raw model/version evidence intact.
PHONE_DEMO_FIXED_V1 = ManualDemoThresholds(
    pad_max=0.70,
    gend_max=0.95,
    spoof_max=0.70,
    lipsync_max=0.60,
    match_min=0.30,
    consistency_min=0.30,
)
