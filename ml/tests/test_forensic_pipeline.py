"""FOR-01 — pipeline giám định với nguồn media giả và bộ phát hiện giả (không cần mô hình thật)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import (
    ErrorCode,
    Evidence,
    EvidenceType,
    Module,
    ModuleResult,
    Status,
)
from vericlue_ml.forensic.media import AudioUnavailable, MediaError, MediaInfo, _write_wav
from vericlue_ml.forensic.pipeline import (
    MAX_DURATION_SECONDS,
    MIN_COVERAGE_FRACTION,
    ForensicPipeline,
    Thresholds,
)
from vericlue_ml.forensic.provenance import (
    CONCLUSION_NONE,
    EV_CONCLUSION,
    EV_INTERVALS,
    EV_TOOL,
)

THRESHOLDS = Thresholds(face_b=0.3, face_a=0.7, voice_spoof=0.5)
DURATION = 10.0
# plan_segments(10): (0,3) (1.5,4.5) (3,6) (4.5,7.5) (6,9) (7,10)
N_SEGMENTS = 6
FACE = Module.FACE_DEEPFAKE
VOICE = Module.VOICE_SPOOF
LIPSYNC = Module.LIPSYNC
PROV = Module.PROVENANCE


# --- đồ giả -----------------------------------------------------------------


class FakeSource:
    def __init__(
        self,
        info: MediaInfo,
        *,
        frames_ok: bool = True,
        audio_error: str | None = None,
        full_audio_exc: Exception | None = None,
        path: Path | None = None,
    ) -> None:
        self.info = info
        self.frames_ok = frames_ok
        self.audio_error = audio_error
        self.full_audio_exc = full_audio_exc
        if path is not None:
            self.path = path
        self.frame_calls: list[tuple[float, float, int]] = []
        self.audio_calls: list[tuple[float, float]] = []
        self.outdirs: list[Path] = []

    def frames(self, t0: float, t1: float, count: int, outdir: Path) -> list[Path]:
        self.frame_calls.append((t0, t1, count))
        self.outdirs.append(outdir)
        if not self.frames_ok:
            return []
        outdir.mkdir(parents=True, exist_ok=True)
        paths = []
        for i in range(2):
            p = outdir / f"f{i}.png"
            p.write_bytes(b"x")
            paths.append(p)
        return paths

    def audio_wav(self, t0: float, t1: float, out: Path) -> Path:
        self.audio_calls.append((t0, t1))
        if self.audio_error is not None:
            raise AudioUnavailable(self.audio_error)
        return _write_wav(out, _silence())

    def full_audio_wav(self, out: Path) -> Path:
        if self.full_audio_exc is not None:
            raise self.full_audio_exc
        if self.audio_error is not None:
            raise AudioUnavailable(self.audio_error)
        return _write_wav(out, _silence())


def _silence():
    import numpy as np

    return np.zeros(1600, dtype="float32")


def make_result(
    module: Module,
    score: float | None = 0.1,
    status: Status = Status.OK,
    error_code: ErrorCode | None = None,
    evidence: list[Evidence] | None = None,
) -> ModuleResult:
    return ModuleResult(
        module=module,
        model_version="fake-1",
        status=status,
        error_code=error_code,
        score=score if status == Status.OK else None,
        evidence=evidence or [],
        latency_ms=0.0,
    )


class FakeDetector:
    """Lần gọi thứ i trả items[i] (lặp lại phần tử cuối nếu hết). Phần tử có thể là điểm, kết quả
    hoặc ngoại lệ."""

    version = "fake-1"

    def __init__(self, module: Module, items: list[Any] | float = 0.1) -> None:
        self.module = module
        self.name = f"fake_{module.value}"
        self.items = items if isinstance(items, list) else [items]
        self.calls: list[DetectorInput] = []

    def predict(self, inp: DetectorInput) -> ModuleResult:
        i = len(self.calls)
        self.calls.append(inp)
        item = self.items[min(i, len(self.items) - 1)]
        if isinstance(item, Exception):
            raise item
        if isinstance(item, ModuleResult):
            return item
        return make_result(self.module, item)


def calibrate_identity(result: ModuleResult) -> ModuleResult:
    return result.model_copy(update={"prob_attack": result.score})


def calibrate_missing(result: ModuleResult) -> ModuleResult:
    raise KeyError("thiếu calibrator cho " + result.model_version)


def video_info(has_audio: bool | None = True, duration: float = DURATION) -> MediaInfo:
    return MediaInfo(
        kind="video", size_bytes=1000, duration_s=duration, width=64, height=48, fps=10.0,
        has_audio=has_audio,
    )  # fmt: skip


def audio_info(duration: float = DURATION) -> MediaInfo:
    return MediaInfo(kind="audio", size_bytes=1000, duration_s=duration, has_audio=True)


def build(
    detectors: dict[Module, FakeDetector],
    unavailable: dict[Module, str] | None = None,
    calibrate=calibrate_identity,
    **kwargs,
) -> ForensicPipeline:
    return ForensicPipeline(detectors, unavailable or {}, calibrate, THRESHOLDS, **kwargs)


def low_detectors(**overrides: Any) -> dict[Module, FakeDetector]:
    """face + voice đều thấp, trừ khi ghi đè."""
    items = {FACE: 0.1, VOICE: 0.1}
    items.update(overrides)
    return {m: FakeDetector(m, v) for m, v in items.items()}


def sig(analysis, module: Module, index: int):
    return next(s for s in analysis.segments[index].signals if s.module == module.value)


def sigs(analysis, module: Module):
    return [s for seg in analysis.segments for s in seg.signals if s.module == module.value]


def prov_result(*evidence: Evidence) -> ModuleResult:
    return make_result(PROV, score=None, evidence=list(evidence))


def ev(name: str, value: Any) -> Evidence:
    kind = EvidenceType.SEGMENTS if name == EV_INTERVALS else EvidenceType.TEXT
    return Evidence(type=kind, name=name, value=value)


# --- (a) chia đoạn và tín hiệu theo loại media ---------------------------------


def test_video_chia_doan_dung_va_ba_module_moi_doan():
    source = FakeSource(video_info())
    analysis = build(low_detectors()).run(source)
    assert len(analysis.segments) == N_SEGMENTS
    assert (analysis.segments[0].t_start, analysis.segments[0].t_end) == (0.0, 3.0)
    assert (analysis.segments[-1].t_start, analysis.segments[-1].t_end) == (7.0, 10.0)
    for seg in analysis.segments:
        assert [s.module for s in seg.signals] == ["face_deepfake", "voice_spoof", "lipsync"]
    assert all(s.status == "ok" for s in sigs(analysis, FACE) + sigs(analysis, VOICE))


def test_video_lipsync_chua_ho_tro_thi_unavailable_ca_khi_co_bo_phat_hien():
    detectors = low_detectors()
    detectors[LIPSYNC] = FakeDetector(LIPSYNC, 0.99)
    analysis = build(detectors).run(FakeSource(video_info()))
    assert all(s.status == "unavailable" for s in sigs(analysis, LIPSYNC))
    assert detectors[LIPSYNC].calls == []
    assert analysis.verdict == "authentic"  # lipsync không bắt buộc, không tạo khoảng nghi giả


def test_video_goi_face_voi_dung_so_khung_va_cua_so():
    source = FakeSource(video_info())
    build(low_detectors(), frames_per_segment=3).run(source)
    assert [c[2] for c in source.frame_calls] == [3] * N_SEGMENTS
    assert source.frame_calls[0][:2] == (0.0, 3.0)
    assert source.frame_calls[2][:2] == (3.0, 6.0)


def test_audio_chi_co_voice_spoof():
    source = FakeSource(audio_info())
    detectors = low_detectors()
    analysis = build(detectors).run(source)
    assert len(analysis.segments) == N_SEGMENTS
    for seg in analysis.segments:
        assert [s.module for s in seg.signals] == ["voice_spoof"]
    assert source.frame_calls == []
    assert detectors[FACE].calls == []
    assert analysis.verdict == "authentic"


def test_audio_khong_can_face_nhung_thieu_voice_thi_inconclusive():
    analysis = build({}, {VOICE: "chưa có mô hình giọng"}).run(FakeSource(audio_info()))
    assert analysis.verdict == "inconclusive"
    assert all(s.status == "unavailable" for s in sigs(analysis, VOICE))


@pytest.mark.parametrize("duration", [None, 0, 0.0, -2.0])
def test_thoi_luong_khong_xac_dinh_nem_media_error_unsupported(duration):
    info = MediaInfo(kind="video", size_bytes=1, duration_s=duration)
    with pytest.raises(MediaError) as exc:
        build(low_detectors()).run(FakeSource(info))
    assert exc.value.code == "unsupported_media"


def test_qua_dai_nem_media_error_media_too_long():
    info = audio_info(duration=MAX_DURATION_SECONDS + 0.5)
    detectors = low_detectors()
    with pytest.raises(MediaError) as exc:
        build(detectors).run(FakeSource(info))
    assert exc.value.code == "media_too_long"
    assert detectors[VOICE].calls == []


def test_dung_bang_gioi_han_do_dai_van_chay():
    assert MAX_DURATION_SECONDS == 600
    analysis = build(low_detectors()).run(FakeSource(audio_info(duration=MAX_DURATION_SECONDS)))
    assert analysis.verdict == "authentic"
    assert analysis.segments[-1].t_end == MAX_DURATION_SECONDS


def test_phien_ban_mo_hinh_duoc_ghi():
    analysis = build(low_detectors()).run(FakeSource(video_info()))
    assert analysis.model_versions == {"face_deepfake": "fake-1", "voice_spoof": "fake-1"}


# --- (b) đoạn vượt ngưỡng -> khoảng nghi giả ----------------------------------


def test_face_vuot_nguong_tao_khoang_gop_cong_ttru_1s():
    face_scores = [0.1, 0.1, 0.9, 0.1, 0.1, 0.1]
    analysis = build(low_detectors(**{FACE: face_scores})).run(FakeSource(video_info()))
    assert analysis.verdict == "suspect"
    assert analysis.suspect_intervals == [
        {"t_start": 2.0, "t_end": 7.0, "modules": ["face_deepfake"], "max_prob_attack": 0.9}
    ]


def test_hai_module_o_hai_doan_ke_nhau_gop_thanh_mot_khoang():
    face_scores = [0.1, 0.1, 0.8, 0.1, 0.1, 0.1]
    voice_scores = [0.1, 0.1, 0.1, 0.6, 0.1, 0.1]
    detectors = low_detectors(**{FACE: face_scores, VOICE: voice_scores})
    analysis = build(detectors).run(FakeSource(video_info()))
    assert analysis.suspect_intervals == [
        {
            "t_start": 2.0,
            "t_end": 8.5,
            "modules": ["face_deepfake", "voice_spoof"],
            "max_prob_attack": 0.8,
        }
    ]
    assert analysis.verdict == "suspect"


def test_voice_vuot_nguong_tao_khoang_chi_voice():
    voice_scores = [0.1, 0.1, 0.1, 0.1, 0.1, 0.55]
    analysis = build(low_detectors(**{VOICE: voice_scores})).run(FakeSource(video_info()))
    # đoạn cuối (7, 10) -> (6, 10 cắt vào duration)
    assert analysis.suspect_intervals == [
        {"t_start": 6.0, "t_end": 10.0, "modules": ["voice_spoof"], "max_prob_attack": 0.55}
    ]


def test_hai_nhom_xa_nhau_thanh_hai_khoang_nghi_gia():
    info = video_info(duration=30.0)
    # 19 đoạn; đoạn 1 = (1.5, 4.5), đoạn 15 = (22.5, 25.5)
    face_scores = [0.1] * 19
    face_scores[1] = 0.75
    face_scores[15] = 0.95
    analysis = build(low_detectors(**{FACE: face_scores})).run(FakeSource(info))
    assert [(i["t_start"], i["t_end"]) for i in analysis.suspect_intervals] == [
        (0.5, 5.5),
        (21.5, 26.5),
    ]
    assert [i["max_prob_attack"] for i in analysis.suspect_intervals] == [0.75, 0.95]


def test_diem_dung_bang_nguong_face_a_la_vuot():
    analysis = build(low_detectors(**{FACE: 0.7})).run(FakeSource(video_info()))
    assert analysis.verdict == "suspect"
    assert analysis.suspect_intervals[0]["max_prob_attack"] == 0.7


def test_khoang_nghi_gia_khi_co_vuot_nguong_van_ghi_luu_y_neu_thieu_buoc():
    detectors = {VOICE: FakeDetector(VOICE, [0.9])}
    analysis = build(detectors, {FACE: "chưa có mô hình mặt"}).run(FakeSource(video_info()))
    assert analysis.verdict == "suspect"
    assert "chưa có mô hình mặt" in analysis.verdict_reason


# --- (c) authentic -----------------------------------------------------------


def test_tat_ca_duoi_nguong_la_authentic_nhung_khong_phai_chung_nhan_that():
    analysis = build(low_detectors()).run(FakeSource(video_info()))
    assert analysis.verdict == "authentic"
    assert analysis.suspect_intervals == []
    assert "không phải chứng nhận" in analysis.verdict_reason
    assert "Không phát hiện dấu hiệu" in analysis.verdict_reason


# --- (d) thiếu module bắt buộc -----------------------------------------------


def test_thieu_face_deepfake_cho_video_la_inconclusive():
    analysis = build({VOICE: FakeDetector(VOICE, 0.1)}, {FACE: "chưa có trọng số"}).run(
        FakeSource(video_info())
    )
    assert analysis.verdict == "inconclusive"
    assert analysis.verdict != "authentic"
    entry = next(m for m in analysis.unavailable_modules if m["module"] == "face_deepfake")
    assert entry["required"] is True
    assert entry["reason"] == "chưa có trọng số"
    assert all(s.status == "unavailable" for s in sigs(analysis, FACE))
    assert sigs(analysis, FACE)[0].reason == "chưa có trọng số"
    assert "face_deepfake" in analysis.verdict_reason


def test_thieu_face_khong_ly_do_dung_ly_do_mac_dinh():
    analysis = build({VOICE: FakeDetector(VOICE, 0.1)}).run(FakeSource(video_info()))
    assert analysis.verdict == "inconclusive"
    assert sigs(analysis, FACE)[0].reason == "Chưa có mô hình thật cho bước này"


def test_lipsync_va_provenance_thieu_khong_bat_buoc():
    analysis = build(low_detectors()).run(FakeSource(video_info()))
    by_module = {m["module"]: m for m in analysis.unavailable_modules}
    assert by_module["lipsync"]["required"] is False
    assert by_module["provenance"]["required"] is False
    assert "face_deepfake" not in by_module and "voice_spoof" not in by_module


# --- (e) module bắt buộc báo lỗi ---------------------------------------------


def test_module_bat_buoc_loi_o_moi_doan_la_inconclusive():
    err = make_result(FACE, status=Status.ERROR, error_code=ErrorCode.E_INTERNAL)
    analysis = build(low_detectors(**{FACE: [err]})).run(FakeSource(video_info()))
    assert analysis.verdict == "inconclusive"
    assert all(s.status == "error" for s in sigs(analysis, FACE))
    assert "E_INTERNAL" in sigs(analysis, FACE)[0].reason


def test_module_bat_buoc_loi_o_mot_so_doan_cung_khong_authentic():
    err = make_result(VOICE, status=Status.ERROR, error_code=ErrorCode.E_DECODE)
    scores = [0.1, err, 0.1, 0.1, 0.1, 0.1]
    analysis = build(low_detectors(**{VOICE: scores})).run(FakeSource(video_info()))
    assert analysis.verdict == "inconclusive"
    assert "1/6" in analysis.verdict_reason


def test_degraded_khong_bao_gio_duoc_coi_la_dat():
    degraded = make_result(FACE, status=Status.DEGRADED)
    analysis = build(low_detectors(**{FACE: [degraded]})).run(FakeSource(video_info()))
    assert all(s.status == "degraded" and not s.applicable for s in sigs(analysis, FACE))
    assert analysis.verdict == "inconclusive"


def test_khong_doc_duoc_khung_hinh_la_loi_va_inconclusive():
    detectors = low_detectors()
    analysis = build(detectors).run(FakeSource(video_info(), frames_ok=False))
    assert all(s.status == "error" for s in sigs(analysis, FACE))
    assert detectors[FACE].calls == []
    assert analysis.verdict == "inconclusive"


# --- (f) not_applicable ------------------------------------------------------


def test_not_applicable_khong_co_mat_khong_tao_khoang_va_khong_tinh_diem():
    na = make_result(FACE, status=Status.NOT_APPLICABLE, error_code=ErrorCode.E_NO_FACE)
    scores = [0.1, na, 0.1, 0.1, 0.1, 0.1]
    analysis = build(low_detectors(**{FACE: scores})).run(FakeSource(video_info()))
    signal = sig(analysis, FACE, 1)
    assert signal.status == "not_applicable"
    assert signal.applicable is False
    assert signal.prob_attack is None
    assert "khuôn mặt" in signal.reason
    assert analysis.suspect_intervals == []
    assert analysis.verdict == "authentic"  # còn đoạn khác chạy được, không có lỗi


def test_not_applicable_low_quality_co_ly_do_rieng():
    na = make_result(VOICE, status=Status.NOT_APPLICABLE, error_code=ErrorCode.E_LOW_QUALITY)
    analysis = build(low_detectors(**{VOICE: [0.1, na, 0.1, 0.1, 0.1, 0.1]})).run(
        FakeSource(video_info())
    )
    signal = sig(analysis, VOICE, 1)
    assert signal.status == "not_applicable" and signal.applicable is False
    assert "tiếng nói" in signal.reason
    assert analysis.suspect_intervals == []


def test_not_applicable_ma_khong_co_gi_khac_tao_khoang_nghi_gia():
    # not_applicable ở mọi đoạn: không đoạn nào được coi là cờ
    na = make_result(FACE, status=Status.NOT_APPLICABLE, error_code=ErrorCode.E_NO_FACE)
    scores = [na, na, na, na, na, na]
    analysis = build(low_detectors(**{FACE: scores})).run(FakeSource(video_info()))
    assert analysis.suspect_intervals == []


def test_moi_doan_not_applicable_o_module_bat_buoc_la_inconclusive():
    na = make_result(FACE, status=Status.NOT_APPLICABLE, error_code=ErrorCode.E_NO_FACE)
    analysis = build(low_detectors(**{FACE: [na]})).run(FakeSource(video_info()))
    assert all(s.status == "not_applicable" for s in sigs(analysis, FACE))
    assert analysis.verdict == "inconclusive"
    assert analysis.suspect_intervals == []


def test_not_applicable_van_de_suspect_neu_module_khac_vuot_nguong():
    na = make_result(FACE, status=Status.NOT_APPLICABLE, error_code=ErrorCode.E_NO_FACE)
    detectors = low_detectors(**{FACE: [na], VOICE: [0.1, 0.1, 0.9, 0.1, 0.1, 0.1]})
    analysis = build(detectors).run(FakeSource(video_info()))
    assert analysis.verdict == "suspect"
    assert analysis.suspect_intervals[0]["modules"] == ["voice_spoof"]


# --- độ bao phủ tối thiểu ---------------------------------------------------------


def _na(module: Module, code: ErrorCode = ErrorCode.E_NO_FACE) -> ModuleResult:
    return make_result(module, status=Status.NOT_APPLICABLE, error_code=code)


def test_do_bao_phu_duoi_50_phan_tram_la_inconclusive():
    assert MIN_COVERAGE_FRACTION == 0.5
    na = _na(FACE)
    scores = [0.1, 0.1, na, na, na, na]  # 2/6 đoạn phân tích được
    analysis = build(low_detectors(**{FACE: scores})).run(FakeSource(video_info()))
    assert analysis.verdict == "inconclusive"
    assert analysis.verdict != "authentic"
    assert "chỉ 2/6 đoạn phân tích được" in analysis.verdict_reason
    assert analysis.suspect_intervals == []


def test_do_bao_phu_dung_50_phan_tram_va_duoi_nguong_la_authentic():
    na = _na(FACE)
    scores = [0.1, 0.1, 0.1, na, na, na]  # 3/6
    analysis = build(low_detectors(**{FACE: scores})).run(FakeSource(video_info()))
    assert analysis.verdict == "authentic"


def test_do_bao_phu_thap_o_voice_bat_buoc_cung_inconclusive():
    na = _na(VOICE, ErrorCode.E_LOW_QUALITY)
    scores = [0.1, na, na, na, na, na]  # 1/6
    analysis = build(low_detectors(**{VOICE: scores})).run(FakeSource(video_info()))
    assert analysis.verdict == "inconclusive"
    assert "voice_spoof: chỉ 1/6" in analysis.verdict_reason


def test_do_bao_phu_thap_nhung_co_doan_vuot_nguong_van_suspect():
    na = _na(FACE)
    scores = [0.1, 0.9, na, na, na, na]
    analysis = build(low_detectors(**{FACE: scores})).run(FakeSource(video_info()))
    assert analysis.verdict == "suspect"
    assert "chỉ 2/6" not in analysis.verdict_reason.split("Lưu ý")[0]
    assert "chỉ 2/6" in analysis.verdict_reason  # nhưng có ghi lưu ý


def test_do_bao_phu_ap_dung_cho_audio():
    na = _na(VOICE, ErrorCode.E_LOW_QUALITY)
    analysis = build(low_detectors(**{VOICE: [0.1, na, na, na, na, na]})).run(
        FakeSource(audio_info())
    )
    assert analysis.verdict == "inconclusive"


# --- (g) calibrate lỗi ---------------------------------------------------------


def test_thieu_calibrator_la_error_va_khong_dung_diem_tho():
    # điểm thô cao 0.99: nếu bị dùng nhầm sẽ thành suspect
    detectors = low_detectors(**{FACE: 0.99, VOICE: 0.99})
    analysis = build(detectors, calibrate=calibrate_missing).run(FakeSource(video_info()))
    for s in sigs(analysis, FACE) + sigs(analysis, VOICE):
        assert s.status == "error"
        assert s.prob_attack is None
        assert "KeyError" in s.reason
    assert analysis.suspect_intervals == []
    assert analysis.verdict == "inconclusive"
    assert analysis.verdict != "authentic"


def test_calibrator_tra_prob_attack_none_la_error():
    analysis = build(low_detectors(), calibrate=lambda r: r).run(FakeSource(video_info()))
    assert all(s.status == "error" for s in sigs(analysis, FACE))
    assert analysis.verdict == "inconclusive"


# --- (h) bộ phát hiện ném ngoại lệ -------------------------------------------


def test_predict_nem_ngoai_le_thanh_error_khong_do_pipeline():
    scores = [0.1, RuntimeError("boom"), 0.1, 0.1, 0.1, 0.1]
    analysis = build(low_detectors(**{FACE: scores})).run(FakeSource(video_info()))
    signal = sig(analysis, FACE, 1)
    assert signal.status == "error"
    assert "RuntimeError" in signal.reason
    assert analysis.verdict == "inconclusive"
    assert len(analysis.segments) == N_SEGMENTS


def test_predict_nem_ngoai_le_o_moi_doan_van_chay_het():
    analysis = build(low_detectors(**{VOICE: [ValueError("x")]})).run(FakeSource(video_info()))
    assert all(s.status == "error" for s in sigs(analysis, VOICE))
    assert analysis.verdict == "inconclusive"


# --- (i) âm thanh của video --------------------------------------------------


def test_video_khong_co_am_thanh_thi_khong_co_tin_hieu_voice_va_khong_bat_buoc():
    detectors = low_detectors()
    source = FakeSource(video_info(has_audio=False))
    pipeline = build(detectors)
    analysis = pipeline.run(source)
    assert sigs(analysis, VOICE) == []
    assert detectors[VOICE].calls == []
    assert source.audio_calls == []
    assert VOICE not in pipeline.required_modules(source.info)
    assert analysis.verdict == "authentic"


def test_video_khong_am_thanh_va_khong_co_voice_detector_van_authentic():
    analysis = build({FACE: FakeDetector(FACE, 0.1)}).run(FakeSource(video_info(has_audio=False)))
    assert analysis.verdict == "authentic"
    by_module = {m["module"]: m for m in analysis.unavailable_modules}
    assert by_module["voice_spoof"]["required"] is False


def test_has_audio_none_va_audio_unavailable_thi_voice_unavailable_khong_authentic():
    reason = "Cần PyAV để lấy tiếng của video."
    source = FakeSource(video_info(has_audio=None), audio_error=reason)
    detectors = low_detectors()
    analysis = build(detectors).run(source)
    assert all(s.status == "unavailable" and s.reason == reason for s in sigs(analysis, VOICE))
    assert detectors[VOICE].calls == []
    assert analysis.verdict == "inconclusive"
    assert "voice_spoof" in analysis.verdict_reason


def test_has_audio_none_nhung_giai_ma_duoc_van_chay_voice():
    detectors = low_detectors()
    analysis = build(detectors).run(FakeSource(video_info(has_audio=None)))
    assert len(detectors[VOICE].calls) == N_SEGMENTS
    assert analysis.verdict == "authentic"


def test_voice_duoc_goi_voi_duong_dan_wav_cua_doan():
    detectors = low_detectors()
    source = FakeSource(video_info())
    build(detectors).run(source)
    assert source.audio_calls[0] == (0.0, 3.0)
    assert all(c.audio is not None and c.audio.name == "audio.wav" for c in detectors[VOICE].calls)
    assert all(len(c.images) == 2 for c in detectors[FACE].calls)


# --- (j) giữa hai ngưỡng ------------------------------------------------------


def test_face_giua_hai_nguong_khong_co_doan_vuot_la_inconclusive():
    analysis = build(low_detectors(**{FACE: [0.1, 0.1, 0.5, 0.1, 0.1, 0.1]})).run(
        FakeSource(video_info())
    )
    assert analysis.suspect_intervals == []
    assert analysis.verdict == "inconclusive"
    assert "giữa hai ngưỡng" in analysis.verdict_reason


def test_face_dung_bang_face_b_cung_la_inconclusive():
    analysis = build(low_detectors(**{FACE: 0.3})).run(FakeSource(video_info()))
    assert analysis.verdict == "inconclusive"


def test_face_ngay_duoi_face_b_van_authentic():
    analysis = build(low_detectors(**{FACE: 0.29})).run(FakeSource(video_info()))
    assert analysis.verdict == "authentic"


def test_voice_giua_hai_nguong_khong_anh_huong_vi_chi_co_mot_nguong_giong():
    # voice chỉ có một ngưỡng: dưới voice_spoof thì không cờ và không "giữa hai ngưỡng"
    analysis = build(low_detectors(**{VOICE: 0.49})).run(FakeSource(video_info()))
    assert analysis.verdict == "authentic"


# --- (k) provenance -----------------------------------------------------------


def test_thuy_van_phat_hien_thi_suspect_du_tin_hieu_khac_thap():
    intervals = [{"t_start": 2.0, "t_end": 4.5, "prob": 0.93}]
    found = prov_result(
        ev(EV_CONCLUSION, "Phát hiện thủy vân AI của AudioSeal"),
        ev(EV_TOOL, "AudioSeal"),
        ev(EV_INTERVALS, intervals),
    )
    detectors = low_detectors()
    detectors[PROV] = FakeDetector(PROV, [found])
    analysis = build(detectors).run(FakeSource(video_info()))
    assert analysis.suspect_intervals == []
    assert analysis.verdict == "suspect"
    assert "AudioSeal" in analysis.verdict_reason
    prov = analysis.provenance
    assert prov is not None
    assert prov["watermark_detected"] is True
    assert prov["tool"] == "AudioSeal"
    assert prov["conclusion"] == "Phát hiện thủy vân AI của AudioSeal"
    assert prov["watermark_intervals"] == intervals
    assert prov["status"] == "ok"


def test_provenance_nhan_audio_day_du_va_duong_dan_nguon():
    detectors = low_detectors()
    detectors[PROV] = FakeDetector(PROV, [prov_result()])
    source = FakeSource(video_info(), path=Path("clip.mp4"))
    build(detectors).run(source)
    (call,) = detectors[PROV].calls
    assert call.audio is not None and call.audio.name == "full.wav"
    assert call.metadata == {"source_file": "clip.mp4"}


def test_provenance_khong_co_tin_hieu_khong_lam_authentic_neu_thieu_module_bat_buoc():
    detectors = {VOICE: FakeDetector(VOICE, 0.1), PROV: FakeDetector(PROV, [prov_result()])}
    analysis = build(detectors, {FACE: "chưa có"}).run(FakeSource(video_info()))
    prov = analysis.provenance
    assert prov is not None
    assert prov["conclusion"] == CONCLUSION_NONE
    assert prov["watermark_detected"] is False
    assert analysis.verdict == "inconclusive"


def test_provenance_khong_co_tin_hieu_khong_pha_ket_luan_authentic_hop_le():
    detectors = low_detectors()
    detectors[PROV] = FakeDetector(PROV, [prov_result()])
    analysis = build(detectors).run(FakeSource(video_info()))
    assert analysis.provenance["watermark_detected"] is False
    assert analysis.provenance["conclusion"] == CONCLUSION_NONE
    assert analysis.verdict == "authentic"
    assert "không phải chứng nhận" in analysis.verdict_reason
    assert any("KHÔNG có nghĩa là thật" in n for n in analysis.provenance["notes"])


def test_provenance_khong_dang_ky_thi_unavailable_va_khong_do():
    analysis = build(low_detectors(), {PROV: "chưa cài AudioSeal"}).run(FakeSource(video_info()))
    prov = analysis.provenance
    assert prov["status"] == "unavailable"
    assert prov["watermark_detected"] is False
    assert "chưa cài AudioSeal" in prov["conclusion"]
    assert analysis.verdict == "authentic"
    entry = next(m for m in analysis.unavailable_modules if m["module"] == "provenance")
    assert entry["reason"] == "chưa cài AudioSeal"


def test_provenance_nem_ngoai_le_thanh_error_khong_do():
    detectors = low_detectors()
    detectors[PROV] = FakeDetector(PROV, [RuntimeError("hỏng")])
    analysis = build(detectors).run(FakeSource(video_info()))
    assert analysis.provenance["status"] == "error"
    assert analysis.provenance["watermark_detected"] is False
    assert "RuntimeError" in analysis.provenance["conclusion"]
    assert analysis.verdict == "authentic"


def test_provenance_khong_co_am_thanh_ghi_chu_va_van_chay():
    detectors = low_detectors()
    detectors[PROV] = FakeDetector(PROV, [prov_result()])
    source = FakeSource(video_info(has_audio=False), audio_error="Không có tiếng.")
    analysis = build(detectors).run(source)
    (call,) = detectors[PROV].calls
    assert call.audio is None
    assert "Không có tiếng." in analysis.provenance["notes"]


# --- (l) tiến độ ----------------------------------------------------------------


def test_on_progress_segments_tang_dan_roi_provenance_va_finalize():
    events: list[tuple[str, int, int]] = []
    build(low_detectors()).run(
        FakeSource(video_info()), on_progress=lambda s, d, t: events.append((s, d, t))
    )
    expected = [("segments", i, N_SEGMENTS) for i in range(N_SEGMENTS + 1)]
    expected += [("provenance", N_SEGMENTS, N_SEGMENTS), ("finalize", N_SEGMENTS, N_SEGMENTS)]
    assert events == expected


# --- (m) thư mục tạm --------------------------------------------------------------


def test_workdir_tam_do_pipeline_tu_tao_bi_don_sau_khi_chay(monkeypatch):
    created: list[Path] = []
    real = tempfile.mkdtemp

    def spy(*args, **kwargs):
        path = real(*args, **kwargs)
        created.append(Path(path))
        return path

    monkeypatch.setattr(tempfile, "mkdtemp", spy)
    source = FakeSource(video_info())
    detectors = low_detectors()
    detectors[PROV] = FakeDetector(PROV, [prov_result()])
    build(detectors).run(source)
    assert len(created) == 1
    assert not created[0].exists()
    # các thư mục khung đã được dùng nằm dưới workdir tạm đó
    assert all(created[0] in o.parents for o in source.outdirs)


def test_workdir_tam_van_duoc_don_khi_pipeline_nem_ngoai_le(monkeypatch):
    created: list[Path] = []
    real = tempfile.mkdtemp

    def spy(*args, **kwargs):
        path = real(*args, **kwargs)
        created.append(Path(path))
        return path

    monkeypatch.setattr(tempfile, "mkdtemp", spy)
    detectors = low_detectors()
    detectors[PROV] = FakeDetector(PROV, [prov_result()])
    source = FakeSource(video_info(), full_audio_exc=OSError("đĩa đầy"))
    with pytest.raises(OSError):
        build(detectors).run(source)
    assert len(created) == 1
    assert not created[0].exists()


def test_workdir_do_nguoi_goi_cung_cap_khong_bi_xoa(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    source = FakeSource(video_info())
    build(low_detectors(), workdir=work).run(source)
    assert work.exists()
    assert all(work in o.parents for o in source.outdirs)
