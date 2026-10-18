"""Ordered fail-closed policy. Counters, challenges and transactions belong to the API."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Literal

from vericlue_ml.common.calibration import CalibrationError, CalibrationStore
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, Module, ModuleResult, Status
from vericlue_ml.router.config import RouterConfig, load_config
from vericlue_ml.router.fusion import FusionError, max_probability
from vericlue_ml.router.profiles import RouterProfileName, get_profile

ResultMap = dict[Module, ModuleResult]
Action = Literal["pass", "retry", "review", "voice_challenge"]
Priority = Literal["normal", "high"]

logger = logging.getLogger(__name__)
FACE_MODULES = (Module.FACE_PAD, Module.FACE_DEEPFAKE)
PRESENCE_MODULES = (Module.CHROMAPULSE, Module.CAMPROBE)
VOICE_MODULES = (Module.VOICE_SPOOF, Module.LIPSYNC)
FINALIZE_MODULES = (Module.QUALITY, *FACE_MODULES, *PRESENCE_MODULES)
VOICE_STEP_MODULES = (Module.VOICE_CHALLENGE, *VOICE_MODULES)
MAX_VOICE_REREADS = 1


@dataclass(frozen=True)
class Decision:
    status: Action
    retry_hint: str | None = None
    priority: Priority = "normal"
    reason: str = ""
    config_version: str = ""
    thresholds: dict = field(default_factory=dict)
    results: dict[Module, ModuleResult] = field(default_factory=dict, repr=False)


class TrustRouter:
    def __init__(
        self,
        config: RouterConfig | None = None,
        *,
        calibrators: CalibrationStore | None = None,
        profile: RouterProfileName = "full",
    ) -> None:
        self.profile = get_profile(profile)
        self.config = config if config is not None else load_config()
        self.calibrators = calibrators if calibrators is not None else CalibrationStore()

    def _decision(
        self,
        status: Action,
        results: ResultMap,
        *,
        reason: str,
        retry_hint: str | None = None,
        priority: Priority = "normal",
    ) -> Decision:
        decision_results = dict(results)
        for module in self.profile.advisory_voice_modules:
            result = decision_results.get(module)
            if result is not None and not any(
                evidence.name == "decision_role" and evidence.value == "advisory"
                for evidence in result.evidence
            ):
                role = Evidence(
                    type="text",
                    name="decision_role",
                    value="advisory",
                    label_vi="Khớp môi chỉ tham khảo ở chế độ MVP",
                )
                decision_results[module] = result.model_copy(
                    update={"evidence": [*result.evidence, role]}
                )
        return Decision(
            status,
            retry_hint,
            priority,
            reason,
            self.config.config_version,
            {**self.config.snapshot(), "router_profile": "mvp"}
            if self.profile.name == "mvp"
            else self.config.snapshot(),
            decision_results,
        )

    def _retry(
        self, results: ResultMap, used: int, maximum: int, hint: str, reason: str
    ) -> Decision:
        if used >= maximum:
            return self._decision("review", results, reason=reason + "; retry limit")
        return self._decision("retry", results, reason=reason, retry_hint=hint)

    @staticmethod
    def _usable(results: ResultMap, modules: tuple[Module, ...]) -> bool:
        return all(
            (r := results.get(m)) is not None and r.module == m and r.status == Status.OK
            for m in modules
        )

    def _calibrate(self, results: ResultMap, modules: tuple[Module, ...]) -> ResultMap:
        calibrated = dict(results)
        for module in modules:
            result = calibrated.get(module)
            if result is None:
                continue
            try:
                calibrated[module] = self.calibrators.apply(result)
            except CalibrationError:
                logger.exception("Calibration unavailable for %s/%s", module, result.model_version)
                calibrated[module] = result.model_copy(
                    update={
                        "status": Status.ERROR,
                        "error_code": ErrorCode.E_INTERNAL,
                        "prob_attack": None,
                    }
                )
        return calibrated

    def finalize(
        self,
        results: dict[Module, ModuleResult],
        *,
        retries_used: int = 0,
        max_retries: int = 2,
        session_valid: bool = True,
        ood: bool | None = None,
    ) -> Decision:
        """Gate quality before presence/face; error/degraded at a reached gate cannot pass."""
        if not session_valid:
            return self._decision("review", results, reason="invalid session", priority="high")
        if not self._usable(results, (Module.QUALITY,)):
            return self._decision("review", results, reason="quality missing/error/degraded")
        quality = results[Module.QUALITY]
        if quality.gate != Gate.PASS:
            hint = next(
                (
                    e.value
                    for e in quality.evidence
                    if e.name == "retry_hint" and isinstance(e.value, str)
                ),
                "MORE_LIGHT",
            )
            return self._retry(results, retries_used, max_retries, hint, "quality not passed")
        if not self._usable(results, self.profile.presence_modules):
            return self._decision("review", results, reason="presence missing/error/degraded")
        gates = [results[m].gate for m in self.profile.presence_modules]
        if Gate.FAIL in gates:
            return self._decision("review", results, reason="presence failed", priority="high")
        if any(g not in (Gate.PASS, Gate.FAIL, Gate.UNCLEAR) for g in gates):
            return self._decision("review", results, reason="presence gate missing/invalid")
        if Gate.UNCLEAR in gates:
            return self._retry(
                results, retries_used, max_retries, "BRIGHTNESS_UP", "presence unclear"
            )
        if ood is True:
            return self._decision("review", results, reason="out of distribution")
        calibrated = self._calibrate(results, FACE_MODULES)
        try:
            probability = max_probability(calibrated, FACE_MODULES)
        except FusionError:
            return self._decision(
                "review", calibrated, reason="face missing/error/degraded/probability"
            )
        if probability <= self.config.face.b:
            return self._decision("pass", calibrated, reason="face <= B")
        if probability >= self.config.face.a:
            return self._decision("review", calibrated, reason="face >= A")
        return self._decision("voice_challenge", calibrated, reason="B < face < A")

    def voice(
        self,
        results: dict[Module, ModuleResult],
        *,
        rereads_used: int = 0,
        session_valid: bool = True,
        splice_flags: int | float | None = None,
    ) -> Decision:
        """Match the phrase and independently gate spoof/lipsync; WER never enters fusion."""
        if not session_valid:
            return self._decision("review", results, reason="invalid session", priority="high")
        if not self._usable(results, (Module.VOICE_CHALLENGE,)):
            return self._decision(
                "review", results, reason="voice challenge missing/error/degraded"
            )
        challenge = results[Module.VOICE_CHALLENGE]
        if challenge.gate == Gate.FAIL:
            action = "voice_challenge" if rereads_used < MAX_VOICE_REREADS else "review"
            return self._decision(action, results, reason="phrase mismatch")
        if challenge.gate != Gate.PASS:
            return self._decision("review", results, reason="phrase unclear")
        flags = [e.value for r in results.values() for e in r.evidence if e.name == "splice_flags"]
        if splice_flags is not None:
            flags.append(splice_flags)
        invalid_flag = False
        positive_flag = False
        for value in flags:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or (isinstance(value, float) and not math.isfinite(value))
            ):
                invalid_flag = True
            elif value > 0:
                positive_flag = True
        if positive_flag:
            return self._decision("review", results, reason="positive splice flag", priority="high")
        if invalid_flag:
            return self._decision("review", results, reason="invalid splice flag")
        if not self._usable(results, self.profile.required_voice_step_modules):
            return self._decision("review", results, reason="voice missing/error/degraded")
        calibrated = self._calibrate(results, self.profile.voice_modules)
        try:
            probability = max_probability(calibrated, self.profile.voice_modules)
        except FusionError:
            return self._decision(
                "review", calibrated, reason="voice missing/error/degraded/probability"
            )
        action = "pass" if probability <= self.config.voice.spoof_threshold else "review"
        return self._decision(action, calibrated, reason="independent voice spoof threshold")
