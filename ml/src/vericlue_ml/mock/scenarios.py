"""Bảng kịch bản cho mô-đun giả lập.

Mỗi kịch bản quy định từng bộ phát hiện trả kết quả gì, để web, API và TrustRouter
thử được mọi nhánh quyết định khi chưa có mô hình thật. Kịch bản khớp proposal §1.4
và mô hình đe dọa §2.4.

Giá trị là CỐ ĐỊNH (deterministic) để test lặp lại được.
"""

from __future__ import annotations

from typing import Any

from vericlue_ml.common.result import Module

Spec = dict[str, Any]

SCENARIOS = (
    "genuine",  # người thật, điều kiện tốt
    "print",  # ảnh in trước camera
    "replay",  # video phát lại trên màn hình
    "virtual_cam",  # camera ảo / tiện ích trình duyệt chèn video (thủ đoạn Thanh Hóa)
    "faceswap",  # ghép mặt thời gian thực (Deep-Live-Cam)
    "voice_clone",  # mặt mơ hồ → bước giọng nói → giọng clone
    "low_quality",  # người thật nhưng phòng tối, mờ
    "error",  # mọi bộ phát hiện lỗi
)


def _scalar(name: str, value: Any, label_vi: str, unit: str | None = None) -> dict[str, Any]:
    ev = {"type": "scalar", "name": name, "value": value, "label_vi": label_vi}
    if unit:
        ev["unit"] = unit
    return ev


def _text(name: str, value: str, label_vi: str) -> dict[str, Any]:
    return {"type": "text", "name": name, "value": value, "label_vi": label_vi}


# Kết quả của người thật — mặc định cho mọi kịch bản nếu không ghi đè.
GENUINE: dict[Module, Spec] = {
    Module.GAZE_TRACKING: {"status": "ok", "gate": "pass"},
    Module.HEAD_TURN: {"status": "ok", "gate": "pass"},
    Module.FACE_MATCH: {"status": "ok", "gate": "pass"},
    Module.QUALITY: {
        "status": "ok",
        "gate": "pass",
        "quality": {"face_px": 180, "blur": 0.05, "illum": 0.70, "yaw_deg": 3.0},
    },
    Module.FACE_PAD: {"status": "ok", "score": 0.04, "prob_attack": 0.03},
    Module.FACE_DEEPFAKE: {"status": "ok", "score": 0.06, "prob_attack": 0.05},
    Module.CHROMAPULSE: {
        "status": "ok",
        "gate": "pass",
        "evidence": [
            _scalar("r2", 0.82, "Mức khớp phản chiếu với chuỗi màu"),
            _scalar("lag_ms", 45, "Độ trễ phản chiếu", "ms"),
            _scalar("symbols_decoded", 8, "Số màu giải mã đúng (trên 8)"),
        ],
    },
    Module.CAMPROBE: {
        "status": "ok",
        "gate": "pass",
        "evidence": [_text("flags", "", "Không có dấu hiệu camera bị can thiệp")],
    },
    Module.VOICE_SPOOF: {"status": "ok", "score": 0.05, "prob_attack": 0.04},
    Module.VOICE_CHALLENGE: {
        "status": "ok",
        "gate": "pass",
        "evidence": [
            _scalar("syllable_error_rate", 0.05, "Tỷ lệ sai âm tiết so với câu đề bài"),
            _scalar("splice_flags", 0, "Số dấu hiệu cắt ghép"),
        ],
    },
    Module.LIPSYNC: {
        "status": "ok",
        "score": 0.08,
        "prob_attack": 0.06,
        "evidence": [_scalar("av_offset_frames", 0, "Lệch hình–tiếng", "khung")],
    },
    Module.PROVENANCE: {
        "status": "ok",
        "evidence": [_text("watermark", "none", "Không có tín hiệu nguồn gốc")],
    },
}

# Ghi đè theo kịch bản (chỉ những bộ phát hiện khác với người thật).
OVERRIDES: dict[str, dict[Module, Spec]] = {
    "genuine": {},
    "print": {
        Module.FACE_PAD: {"status": "ok", "score": 0.93, "prob_attack": 0.91},
        Module.FACE_DEEPFAKE: {"status": "ok", "score": 0.20, "prob_attack": 0.15},
        Module.CHROMAPULSE: {
            "status": "ok",
            "gate": "fail",
            "evidence": [
                _scalar("r2", 0.71, "Mức khớp phản chiếu với chuỗi màu"),
                _scalar("region_variation", 0.02, "Khác biệt phản chiếu giữa các vùng mặt"),
                _text("reason", "flat_reflection", "Phản chiếu phẳng như mặt giấy"),
            ],
        },
    },
    "replay": {
        Module.FACE_PAD: {"status": "ok", "score": 0.88, "prob_attack": 0.86},
        Module.CHROMAPULSE: {
            "status": "ok",
            "gate": "fail",
            "evidence": [
                _scalar("r2", 0.05, "Mức khớp phản chiếu với chuỗi màu"),
                _text("reason", "no_reflection", "Không phản chiếu chuỗi màu"),
            ],
        },
    },
    "virtual_cam": {
        Module.FACE_PAD: {"status": "ok", "score": 0.10, "prob_attack": 0.08},
        Module.FACE_DEEPFAKE: {"status": "ok", "score": 0.30, "prob_attack": 0.25},
        Module.CHROMAPULSE: {
            "status": "ok",
            "gate": "fail",
            "evidence": [
                _scalar("r2", 0.02, "Mức khớp phản chiếu với chuỗi màu"),
                _text("reason", "no_reflection", "Không phản chiếu chuỗi màu"),
            ],
        },
        Module.CAMPROBE: {
            "status": "ok",
            "gate": "fail",
            "evidence": [
                _text(
                    "flags",
                    "api_tamper:getUserMedia,fast_apply_constraints",
                    "Hàm camera bị can thiệp; camera phản hồi nhanh bất thường",
                ),
                _scalar("apply_constraints_ms", 1.4, "Thời gian camera đổi cấu hình", "ms"),
            ],
        },
    },
    "faceswap": {
        Module.FACE_PAD: {"status": "ok", "score": 0.15, "prob_attack": 0.12},
        Module.FACE_DEEPFAKE: {"status": "ok", "score": 0.91, "prob_attack": 0.90},
        Module.CHROMAPULSE: {
            "status": "ok",
            "gate": "fail",
            "evidence": [
                _scalar("r2", 0.60, "Mức khớp phản chiếu với chuỗi màu"),
                _scalar("lag_ms", 160, "Độ trễ phản chiếu", "ms"),
                _text("reason", "late_reflection", "Phản chiếu trễ hơn người thật"),
            ],
        },
    },
    "voice_clone": {
        Module.FACE_PAD: {"status": "ok", "score": 0.20, "prob_attack": 0.18},
        Module.FACE_DEEPFAKE: {"status": "ok", "score": 0.50, "prob_attack": 0.45},
        Module.VOICE_SPOOF: {"status": "ok", "score": 0.94, "prob_attack": 0.93},
        Module.LIPSYNC: {
            "status": "ok",
            "score": 0.70,
            "prob_attack": 0.65,
            "evidence": [_scalar("av_offset_frames", 4, "Lệch hình–tiếng", "khung")],
        },
        Module.PROVENANCE: {
            "status": "ok",
            "prob_attack": 0.99,
            "evidence": [_text("watermark", "perth", "Phát hiện thủy vân AI PerTh (Resemble)")],
        },
    },
    "low_quality": {
        Module.QUALITY: {
            "status": "ok",
            "gate": "fail",
            "error_code": "E_LOW_QUALITY",
            "quality": {"face_px": 95, "blur": 0.62, "illum": 0.12, "yaw_deg": 4.0},
            "evidence": [_text("retry_hint", "MORE_LIGHT", "Thiếu sáng")],
        },
        Module.FACE_PAD: {"status": "degraded", "score": 0.40, "prob_attack": 0.35},
        Module.FACE_DEEPFAKE: {"status": "degraded", "score": 0.30, "prob_attack": 0.28},
        Module.CHROMAPULSE: {
            "status": "ok",
            "gate": "unclear",
            "evidence": [_text("reason", "low_amplitude", "Tín hiệu phản chiếu quá yếu")],
        },
    },
}


def spec_for(module: Module, scenario: str) -> Spec:
    """Kết quả giả lập của `module` trong `scenario`."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Kịch bản không hợp lệ: {scenario!r}. Chọn một trong {SCENARIOS}")
    if scenario == "error":
        return {"status": "error", "error_code": "E_INTERNAL"}
    return OVERRIDES[scenario].get(module, GENUINE[module])
