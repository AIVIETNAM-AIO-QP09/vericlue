"""PRES-03 — chấm điểm tín hiệu CamProbe thành `gate` (pass | fail).

Đầu vào là `signals["camprobe"]` do trình duyệt đo (apps/web/src/lib/capture/camprobe.ts, CAP-05).
Hai phía PHẢI khớp tên trường; schema `Signals.camprobe` chưa khai trường con của `constraint_probes`
nên tên trường được ghi ở đây và ở camprobe.ts (đề xuất siết schema nằm trong bàn giao CAP-06).

Luật (thẻ PRES-03, ADR-0007):
1. `api_tamper_flags` khác rỗng → fail.
2. Với mỗi lần thăm dò `applyConstraints` đã thành công: phản hồi < MIN_APPLY_CONSTRAINTS_MS mà
   `getSettings()` không đổi, hoặc kích thước khung thật ĐO ĐƯỢC mà không đổi → fail. Thăm dò thất bại
   (thiết bị không hỗ trợ độ phân giải đó, ok=false) hoặc không đo được khung (null) bị bỏ qua, KHÔNG
   phải bằng chứng can thiệp. Giới hạn đã biết: camera ảo từ chối mọi `exact` không bị bắt ở luật này.
3. `duplicate_frame_ratio` > MAX_DUPLICATE_FRAME_RATIO → fail.
4. Tên thiết bị chứa "virtual", "obs", "dummy", "manycam" → chỉ là bằng chứng phụ, KHÔNG fail một mình
   (tên rất dễ giả).

Thiếu `camprobe` hoặc sai dạng → `degraded` (không bao giờ được coi là đạt, AGENTS.md §6 luật 4).
CamProbe chỉ là MỘT lớp kiểm tra (ADR-0007): kẻ tấn công có thể vá API về sau.
"""

from __future__ import annotations

import math
import time
from typing import Any

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import (
    ErrorCode,
    Evidence,
    EvidenceType,
    Gate,
    Module,
    ModuleResult,
    Status,
)

CAMPROBE_VERSION = "camprobe-rules@0.1"

# Ngưỡng của CamProbe CHƯA có trong thresholds.yaml (ADR-0012 mục 3): hằng số có tên, TẠM, chờ ROUT-03
# chọn chính thức trên calib_ltt. Không phải kết quả đo.
# applyConstraints trả về nhanh hơn mức này mà getSettings() không đổi → không có phần cứng đổi cấu hình.
MIN_APPLY_CONSTRAINTS_MS = 5.0
# Tỉ lệ cặp khung liên tiếp giống hệt nhau (30 khung, ảnh xám 24×24). Camera thật luôn có nhiễu cảm biến.
MAX_DUPLICATE_FRAME_RATIO = 0.5
# Chỉ là bằng chứng phụ, không fail một mình.
SUSPICIOUS_DEVICE_LABEL_WORDS = ("virtual", "obs", "dummy", "manycam")

# Nhãn tiếng Việt cho người duyệt. Cờ có dạng "<api>:<lý do>" (xem camprobe.ts).
API_LABELS_VI = {
    "getUserMedia": "Hàm mở camera (getUserMedia)",
    "enumerateDevices": "Hàm liệt kê thiết bị (enumerateDevices)",
    "getSettings": "Hàm đọc thông số camera (getSettings)",
    "getCapabilities": "Hàm đọc khả năng camera (getCapabilities)",
    "applyConstraints": "Hàm đổi thông số camera (applyConstraints)",
    "Function.toString": "Hàm toString của trình duyệt",
}
REASON_LABELS_VI = {
    "not_function": "không còn là hàm",
    "non_native_tostring": "không còn là hàm gốc của trình duyệt (bị thay mã)",
    "has_prototype": "có thuộc tính prototype lạ (hàm gốc không có)",
    "unexpected_own_properties": "có thuộc tính riêng lạ",
    "iframe_mismatch": "khác bản gốc lấy từ khung sạch",
    "own_property_override": "bị gán đè trực tiếp lên đối tượng",
}
PROBE_LABELS_VI = {
    "fast_apply_constraints": "Camera phản hồi đổi độ phân giải quá nhanh nhưng thông số không đổi",
    "frame_size_unchanged": "Khung hình thật không đổi kích thước theo yêu cầu",
}


def flag_label_vi(flag: str) -> str:
    """Nhãn tiếng Việt cho một cờ can thiệp "<api>:<lý do>"; cờ lạ thì giữ nguyên chuỗi."""
    api, _, reason = flag.partition(":")
    api_label = API_LABELS_VI.get(api)
    reason_label = REASON_LABELS_VI.get(reason)
    if api_label is None or reason_label is None:
        return f"Dấu hiệu can thiệp camera: {flag}"
    return f"{api_label} {reason_label}"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _probe_failures(probe: dict[str, Any]) -> list[str]:
    """Các luật hỏng của một lần thăm dò đã thành công (danh sách mã ngắn)."""
    failures: list[str] = []
    apply_ms = _number(probe.get("apply_ms"))
    settings_changed = probe.get("settings_changed") is True
    if apply_ms is not None and apply_ms < MIN_APPLY_CONSTRAINTS_MS and not settings_changed:
        failures.append("fast_apply_constraints")
    # Chỉ khi ĐO ĐƯỢC mà khung không đổi (False). Thiếu hoặc null = không đo được khung (ví dụ
    # <video> ẩn không nhận khung trên iOS): không phải bằng chứng, tránh fail oan người thật.
    if probe.get("frame_size_changed") is False:
        failures.append("frame_size_unchanged")
    return failures


class CamProbeDetector:
    """Cổng luật CamProbe: không mô hình, không trọng số."""

    name = Module.CAMPROBE.value
    version = CAMPROBE_VERSION

    def predict(self, inp: DetectorInput) -> ModuleResult:
        started = time.perf_counter()

        def result(status: Status, **fields: Any) -> ModuleResult:
            return ModuleResult(
                module=Module.CAMPROBE,
                model_version=self.version,
                status=status,
                latency_ms=(time.perf_counter() - started) * 1000,
                **fields,
            )

        try:
            probe = inp.signals.get("camprobe")
            flags = probe.get("api_tamper_flags") if isinstance(probe, dict) else None
            if not isinstance(flags, list) or not all(isinstance(f, str) for f in flags):
                # Thiếu hoặc sai dạng: không có bằng chứng hiện diện → không bao giờ là "đạt".
                return result(
                    Status.DEGRADED,
                    quality={"camprobe_present": isinstance(probe, dict)},
                )
            return self._score(result, probe, flags)
        except Exception:
            return result(Status.ERROR, error_code=ErrorCode.E_INTERNAL)

    @staticmethod
    def _score(result: Any, probe: dict[str, Any], flags: list[str]) -> ModuleResult:
        evidence: list[Evidence] = []
        failed: list[str] = []

        for flag in flags:
            failed.append(f"api_tamper:{flag}")
            evidence.append(
                Evidence(
                    type=EvidenceType.TEXT,
                    name="api_tamper_flag",
                    value=flag,
                    label_vi=flag_label_vi(flag),
                )
            )

        raw_probes = probe.get("constraint_probes")
        probes = (
            [p for p in raw_probes if isinstance(p, dict)] if isinstance(raw_probes, list) else []
        )
        evaluated = 0
        for item in probes:
            if item.get("ok") is not True:
                continue  # thiết bị không hỗ trợ độ phân giải thăm dò: không phải bằng chứng
            evaluated += 1
            requested = item.get("requested")
            size = requested if isinstance(requested, dict) else {}
            for reason in _probe_failures(item):
                failed.append(f"constraint_probe:{reason}")
                evidence.append(
                    Evidence(
                        type=EvidenceType.TEXT,
                        name="constraint_probe",
                        value=f"{reason} ({size.get('width')}x{size.get('height')})",
                        label_vi=PROBE_LABELS_VI[reason],
                    )
                )

        ratio = _number(probe.get("duplicate_frame_ratio"))
        if ratio is not None:
            evidence.append(
                Evidence(
                    type=EvidenceType.SCALAR,
                    name="duplicate_frame_ratio",
                    value=ratio,
                    label_vi="Tỉ lệ khung hình lặp lại giống hệt",
                )
            )
            if ratio > MAX_DUPLICATE_FRAME_RATIO:
                failed.append("duplicate_frames")

        label = probe.get("device_label")
        if isinstance(label, str) and any(
            w in label.lower() for w in SUSPICIOUS_DEVICE_LABEL_WORDS
        ):
            # Bằng chứng phụ: không vào `failed`.
            evidence.append(
                Evidence(
                    type=EvidenceType.TEXT,
                    name="device_label",
                    value=label,
                    label_vi="Tên thiết bị gợi ý camera ảo (chỉ là bằng chứng phụ)",
                )
            )

        return result(
            Status.OK,
            gate=Gate.FAIL if failed else Gate.PASS,
            quality={"probes_evaluated": float(evaluated), "failed_rules": float(len(failed))},
            evidence=evidence,
        )
