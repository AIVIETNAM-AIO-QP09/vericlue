"""FOR-01 — chạy các bộ phát hiện THẬT theo từng đoạn rồi gộp thành kết luận giám định.

Khác luồng eKYC: gọi thẳng từng bộ phát hiện (không qua orchestrator, vì trần 4 giây mỗi lần gọi của
orchestrator không đủ cho phân tích video), nhưng vẫn:
- đưa điểm thô qua calibrator của chính `model_version` (identity tạm theo ADR-0012; calibrator `forensic`
  riêng chưa có, chờ DATA-05) — thiếu calibrator thì đoạn đó là `error`, không dùng điểm thô;
- dùng ngưỡng face.b/face.a và voice.spoof_threshold như eKYC (không sửa thresholds.yaml);
- `error`/`degraded`/`unavailable` ở bước BẮT BUỘC không bao giờ cho ra `authentic`.

Kết luận (một chiều, ADR-0008): có bằng chứng giả (đoạn vượt ngưỡng hoặc thủy vân AI) → `suspect`;
thiếu bước bắt buộc hoặc điểm nằm giữa hai ngưỡng → `inconclusive`; chỉ khi mọi bước bắt buộc đã chạy
trên ít nhất một đoạn, không lỗi và dưới ngưỡng → `authentic` ("không phát hiện dấu hiệu", không phải
chứng nhận thật).
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vericlue_ml.common.detector import Detector, DetectorInput
from vericlue_ml.common.result import Module, ModuleResult, Status
from vericlue_ml.forensic.media import AudioUnavailable, MediaError, MediaInfo, MediaSource
from vericlue_ml.forensic.provenance import provenance_summary
from vericlue_ml.forensic.segment import (
    INTERVAL_MARGIN_SECONDS,
    merge_flagged,
    plan_segments,
)

# Số khung hình đưa cho face_deepfake trên mỗi đoạn 3 giây. Hằng số tạm (ADR-0012 mục 3): ít khung để
# video 60 giây xong trong thời gian chấp nhận được trên CPU; tăng khi có GPU.
FRAMES_PER_SEGMENT = 4

# Hằng số tạm (ADR-0012 mục 3), chưa đo trên dữ liệu thật.
# Bước bắt buộc phải phân tích được ít nhất tỉ lệ này số đoạn mới được phép kết luận `authentic`: kẻ làm giả
# có thể né bộ dò mặt ở đúng phần bị sửa, nên "có 1 đoạn ok" không đủ.
MIN_COVERAGE_FRACTION = 0.5
# Trần thời lượng (giây): file 50 MB có thể chứa hàng giờ âm thanh; phân tích CPU theo đoạn quá lâu.
MAX_DURATION_SECONDS = 600.0

SEGMENT_MODULES = (Module.FACE_DEEPFAKE, Module.VOICE_SPOOF, Module.LIPSYNC)

_NOT_APPLICABLE_REASONS = {
    "E_NO_FACE": "Không thấy khuôn mặt trong đoạn này",
    "E_LOW_QUALITY": "Đoạn quá ngắn hoặc không có tiếng nói",
}


@dataclass(frozen=True)
class Thresholds:
    """Ngưỡng lấy từ thresholds.yaml (face.b, face.a, voice.spoof_threshold)."""

    face_b: float
    face_a: float
    voice_spoof: float


@dataclass
class SignalOutcome:
    module: str
    status: str  # ok | not_applicable | degraded | error | unavailable
    prob_attack: float | None = None
    reason: str | None = None
    model_version: str | None = None

    @property
    def applicable(self) -> bool:
        return self.status == "ok"


@dataclass
class SegmentOutcome:
    t_start: float
    t_end: float
    signals: list[SignalOutcome] = field(default_factory=list)


@dataclass
class ForensicAnalysis:
    media: MediaInfo
    segments: list[SegmentOutcome]
    suspect_intervals: list[dict[str, Any]]
    unavailable_modules: list[dict[str, Any]]
    provenance: dict[str, Any] | None
    verdict: str
    verdict_reason: str
    model_versions: dict[str, str]


Progress = Callable[[str, int, int], None]
Calibrate = Callable[[ModuleResult], ModuleResult]


def _outcome(module: Module, result: ModuleResult, calibrate: Calibrate) -> SignalOutcome:
    """ModuleResult → kết quả tín hiệu, sau hiệu chỉnh. Không bao giờ để điểm thô thành xác suất."""
    name = module.value
    status = str(result.status)
    if status == Status.OK:
        try:
            calibrated = calibrate(result)
        except Exception as exc:  # noqa: BLE001 — thiếu/hỏng calibrator
            return SignalOutcome(
                name,
                "error",
                reason=f"Không hiệu chỉnh được điểm ({type(exc).__name__}): chưa có calibrator.",
                model_version=result.model_version,
            )
        if calibrated.prob_attack is None:
            return SignalOutcome(
                name,
                "error",
                reason="Thiếu xác suất sau hiệu chỉnh.",
                model_version=result.model_version,
            )
        return SignalOutcome(
            name, "ok", prob_attack=calibrated.prob_attack, model_version=result.model_version
        )
    code = str(result.error_code) if result.error_code else ""
    if status == Status.NOT_APPLICABLE:
        reason = _NOT_APPLICABLE_REASONS.get(code, "Không áp dụng cho đoạn này")
    elif status == Status.DEGRADED:
        reason = "Đầu vào kém, kết quả không dùng được" + (f" ({code})" if code else "")
    else:
        reason = "Bộ phát hiện báo lỗi" + (f" ({code})" if code else "")
    return SignalOutcome(name, status, reason=reason, model_version=result.model_version)


class ForensicPipeline:
    def __init__(
        self,
        detectors: Mapping[Module, Detector],
        unavailable: Mapping[Module, str],
        calibrate: Calibrate,
        thresholds: Thresholds,
        *,
        frames_per_segment: int = FRAMES_PER_SEGMENT,
        workdir: Path | None = None,
    ) -> None:
        self.detectors = dict(detectors)
        self.unavailable = dict(unavailable)
        self.calibrate = calibrate
        self.thresholds = thresholds
        self.frames_per_segment = frames_per_segment
        self.workdir = workdir

    # --- tiện ích ---------------------------------------------------------
    def _missing(self, module: Module) -> SignalOutcome | None:
        if module in self.detectors:
            return None
        reason = self.unavailable.get(module, "Chưa có mô hình thật cho bước này")
        return SignalOutcome(module.value, "unavailable", reason=reason)

    def _call(self, module: Module, inp: DetectorInput) -> SignalOutcome:
        try:
            result = self.detectors[module].predict(inp)
        except Exception as exc:  # noqa: BLE001
            return SignalOutcome(
                module.value, "error", reason=f"Lỗi khi chạy bộ phát hiện ({type(exc).__name__})"
            )
        return _outcome(module, result, self.calibrate)

    def required_modules(self, info: MediaInfo) -> list[Module]:
        """Bước bắt buộc để được phép kết luận `authentic` (lipsync/provenance chưa bắt buộc)."""
        required: list[Module] = []
        if info.kind == "video":
            required.append(Module.FACE_DEEPFAKE)
        if info.kind == "audio" or info.has_audio is not False:
            required.append(Module.VOICE_SPOOF)
        return required

    def _segment_modules(self, info: MediaInfo) -> list[Module]:
        modules: list[Module] = []
        if info.kind == "video":
            modules.append(Module.FACE_DEEPFAKE)
        if info.kind == "audio" or info.has_audio is not False:
            modules.append(Module.VOICE_SPOOF)
        if info.kind == "video":
            modules.append(Module.LIPSYNC)
        return modules

    # --- chạy --------------------------------------------------------------
    def run(self, source: MediaSource, on_progress: Progress | None = None) -> ForensicAnalysis:
        info = source.info
        if not info.duration_s or info.duration_s <= 0:
            raise MediaError(
                "Không xác định được thời lượng (có thể là ảnh tĩnh); chỉ hỗ trợ video và âm thanh.",
                "unsupported_media",
            )
        if info.duration_s > MAX_DURATION_SECONDS:
            raise MediaError(
                f"File dài {info.duration_s:.0f} giây, vượt giới hạn {MAX_DURATION_SECONDS:.0f} giây.",
                "media_too_long",
            )
        spans = plan_segments(info.duration_s)
        if not spans:
            raise MediaError("Không chia được đoạn nào từ file này.", "unsupported_media")
        modules = self._segment_modules(info)
        notify = on_progress or (lambda stage, done, total: None)

        own_tmp = self.workdir is None
        work = Path(tempfile.mkdtemp(prefix="vericlue-forensic-")) if own_tmp else self.workdir
        assert work is not None
        try:
            segments: list[SegmentOutcome] = []
            notify("segments", 0, len(spans))
            for index, (t0, t1) in enumerate(spans):
                segments.append(self._run_segment(source, modules, index, t0, t1, work))
                notify("segments", index + 1, len(spans))
            notify("provenance", len(spans), len(spans))
            provenance = self._run_provenance(source, work)
        finally:
            if own_tmp:
                shutil.rmtree(work, ignore_errors=True)

        notify("finalize", len(spans), len(spans))
        return self._conclude(info, spans, segments, provenance)

    def _run_segment(
        self,
        source: MediaSource,
        modules: list[Module],
        index: int,
        t0: float,
        t1: float,
        work: Path,
    ) -> SegmentOutcome:
        outcome = SegmentOutcome(t0, t1)
        seg_dir = work / f"seg{index:04d}"
        for module in modules:
            missing = self._missing(module)
            if missing is not None:
                outcome.signals.append(missing)
                continue
            if module == Module.FACE_DEEPFAKE:
                frames = source.frames(t0, t1, self.frames_per_segment, seg_dir / "frames")
                if not frames:
                    outcome.signals.append(
                        SignalOutcome(module.value, "error", reason="Không đọc được khung hình")
                    )
                    continue
                signal = self._call(module, DetectorInput(images=frames))
                shutil.rmtree(seg_dir / "frames", ignore_errors=True)
            elif module == Module.VOICE_SPOOF:
                try:
                    wav = source.audio_wav(t0, t1, seg_dir / "audio.wav")
                except AudioUnavailable as exc:
                    outcome.signals.append(
                        SignalOutcome(module.value, "unavailable", reason=exc.reason)
                    )
                    continue
                signal = self._call(module, DetectorInput(audio=wav))
                wav.unlink(missing_ok=True)
            else:
                # lipsync: cần video đoạn + câu đề bài (VOICE-05), chưa hỗ trợ cắt đoạn cho giám định.
                signal = SignalOutcome(
                    module.value,
                    "unavailable",
                    reason="Khớp môi cần video đoạn và câu đề bài (VOICE-05); chưa hỗ trợ giám định.",
                )
            outcome.signals.append(signal)
        return outcome

    def _run_provenance(self, source: MediaSource, work: Path) -> dict[str, Any]:
        missing = self._missing(Module.PROVENANCE)
        if missing is not None:
            return {
                "status": "unavailable",
                "conclusion": "Không có tín hiệu nguồn gốc (bước quét chưa chạy: "
                + (missing.reason or "")
                + ")",
                "watermark_detected": False,
                "notes": [missing.reason or ""],
            }
        audio_path: Path | None = None
        notes: list[str] = []
        try:
            audio_path = source.full_audio_wav(work / "full.wav")
        except AudioUnavailable as exc:
            notes.append(exc.reason)
        metadata: dict[str, Any] = {}
        source_path = getattr(source, "path", None)
        if source_path is not None:
            metadata["source_file"] = str(source_path)
        try:
            result = self.detectors[Module.PROVENANCE].predict(
                DetectorInput(audio=audio_path, metadata=metadata)
            )
            summary = provenance_summary(result)
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "error",
                "conclusion": "Không có tín hiệu nguồn gốc (bước quét gặp lỗi: "
                f"{type(exc).__name__})",
                "watermark_detected": False,
                "notes": notes,
            }
        summary["notes"] = notes + list(summary.get("notes", []))
        return summary

    # --- kết luận -----------------------------------------------------------
    def _flag(self, signal: SignalOutcome) -> bool:
        if signal.status != "ok" or signal.prob_attack is None:
            return False
        if signal.module == Module.FACE_DEEPFAKE.value:
            return signal.prob_attack >= self.thresholds.face_a
        if signal.module == Module.VOICE_SPOOF.value:
            return signal.prob_attack >= self.thresholds.voice_spoof
        return False

    def _conclude(
        self,
        info: MediaInfo,
        spans: list[tuple[float, float]],
        segments: list[SegmentOutcome],
        provenance: dict[str, Any],
    ) -> ForensicAnalysis:
        flags = [any(self._flag(s) for s in seg.signals) for seg in segments]
        merged = merge_flagged(
            spans, flags, info.duration_s or spans[-1][1], INTERVAL_MARGIN_SECONDS
        )
        intervals: list[dict[str, Any]] = []
        for t_start, t_end, indices in merged:
            hit = [s for i in indices for s in segments[i].signals if self._flag(s)]
            probs = [s.prob_attack for s in hit if s.prob_attack is not None]
            intervals.append(
                {
                    "t_start": t_start,
                    "t_end": t_end,
                    "modules": sorted({s.module for s in hit}),
                    "max_prob_attack": max(probs) if probs else None,
                }
            )

        required = self.required_modules(info)
        unavailable: list[dict[str, Any]] = []
        for module in (*SEGMENT_MODULES, Module.PROVENANCE):
            if module in self.detectors:
                continue
            if module in (Module.LIPSYNC, Module.FACE_DEEPFAKE) and info.kind != "video":
                continue  # không áp dụng cho file âm thanh: không liệt vào bước thiếu
            unavailable.append(
                {
                    "module": module.value,
                    "reason": self.unavailable.get(module, "Chưa có mô hình thật cho bước này"),
                    "required": module in required,
                }
            )
        # Bước đang đăng ký nhưng không chạy được trên mọi đoạn (ví dụ thiếu PyAV để lấy tiếng).
        problems: list[str] = []
        for module in required:
            signals = [s for seg in segments for s in seg.signals if s.module == module.value]
            if module not in self.detectors:
                problems.append(
                    f"{module.value}: {self.unavailable.get(module, 'chưa có mô hình thật')}"
                )
                continue
            if not signals:
                continue
            ok = [s for s in signals if s.status == "ok"]
            bad = [s for s in signals if s.status in {"error", "degraded", "unavailable"}]
            if not ok:
                why = next(
                    (s.reason for s in signals if s.reason), "không có đoạn nào phân tích được"
                )
                problems.append(f"{module.value}: {why}")
            elif bad:
                problems.append(
                    f"{module.value}: {len(bad)}/{len(signals)} đoạn lỗi hoặc không dùng được"
                )
            elif len(ok) / len(signals) < MIN_COVERAGE_FRACTION:
                problems.append(
                    f"{module.value}: chỉ {len(ok)}/{len(signals)} đoạn phân tích được "
                    f"(cần ít nhất {MIN_COVERAGE_FRACTION:.0%})"
                )

        watermark = bool(provenance.get("watermark_detected"))
        max_face = max(
            (
                s.prob_attack
                for seg in segments
                for s in seg.signals
                if s.module == Module.FACE_DEEPFAKE.value
                and s.status == "ok"
                and s.prob_attack is not None
            ),
            default=None,
        )

        if intervals or watermark:
            verdict = "suspect"
            parts = []
            if intervals:
                parts.append(f"{len(intervals)} khoảng có tín hiệu vượt ngưỡng")
            if watermark:
                parts.append(str(provenance.get("conclusion", "Phát hiện thủy vân AI")))
            reason = "; ".join(parts) + "."
            if problems:
                reason += " Lưu ý còn bước chưa đầy đủ: " + "; ".join(problems) + "."
        elif problems:
            verdict = "inconclusive"
            reason = "Chưa thể kết luận vì thiếu bước bắt buộc: " + "; ".join(problems) + "."
        elif max_face is not None and max_face >= self.thresholds.face_b:
            verdict = "inconclusive"
            reason = "Điểm khuôn mặt nằm giữa hai ngưỡng, chưa đủ cơ sở kết luận."
        else:
            verdict = "authentic"
            reason = (
                "Không phát hiện dấu hiệu làm giả ở các tín hiệu đã chạy. Đây không phải chứng nhận "
                "là thật; xem mục giới hạn của báo cáo."
            )

        versions = {
            s.module: s.model_version for seg in segments for s in seg.signals if s.model_version
        }
        return ForensicAnalysis(
            media=info,
            segments=segments,
            suspect_intervals=intervals,
            unavailable_modules=unavailable,
            provenance=provenance,
            verdict=verdict,
            verdict_reason=reason,
            model_versions=versions,
        )
