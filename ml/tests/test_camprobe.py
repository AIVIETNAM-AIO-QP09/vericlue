"""PRES-03: bộ luật CamProbe — thuần luật, không cần mô hình, GPU hay mạng."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from vericlue_ml.common import DetectorInput, Gate, Module, Status
from vericlue_ml.common.result import ModuleResult
from vericlue_ml.mock import MOCK_DETECTORS
from vericlue_ml.mock.detectors import MockDetector
from vericlue_ml.presence.camprobe import (
    MAX_DUPLICATE_FRAME_RATIO,
    MIN_APPLY_CONSTRAINTS_MS,
    CamProbeDetector,
    flag_label_vi,
)
from vericlue_ml.registry import get_detector
from vericlue_ml.router.policy import TrustRouter

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "packages/contracts/schemas/module_result.schema.json").read_text(encoding="utf-8")
)


def probe(apply_ms: Any = 100.0, *, ok: bool = True, settings: bool = True, size: bool = True):
    return {
        "requested": {"width": 1280, "height": 720},
        "ok": ok,
        "apply_ms": apply_ms,
        "settings_changed": settings,
        "frame_size_changed": size,
    }


def real_camprobe(**overrides: Any) -> dict[str, Any]:
    """Tín hiệu của một camera thật hợp lý; `overrides` ghi đè từng trường."""
    data: dict[str, Any] = {
        "api_tamper_flags": [],
        "constraint_probes": [probe(80.0), probe(120.0)],
        "duplicate_frame_ratio": 0.0,
        "device_label": "Integrated Camera",
    }
    data.update(overrides)
    return data


def run(camprobe: Any = None, *, signals: dict[str, Any] | None = None) -> ModuleResult:
    sig = signals if signals is not None else {"camprobe": camprobe}
    return CamProbeDetector().predict(DetectorInput(signals=sig))


def names(result: ModuleResult, name: str) -> list:
    return [e for e in result.evidence if e.name == name]


def assert_fail(result: ModuleResult) -> None:
    assert result.status == Status.OK and result.gate == Gate.FAIL


def assert_pass(result: ModuleResult) -> None:
    assert result.status == Status.OK and result.gate == Gate.PASS


def test_camera_that_hop_ly_thi_pass():
    r = run(real_camprobe())
    assert_pass(r)
    assert r.is_usable
    assert r.module == Module.CAMPROBE.value
    assert r.model_version == CamProbeDetector.version
    assert not names(r, "api_tamper_flag") and not names(r, "constraint_probe")
    assert not names(r, "device_label")
    assert r.quality["probes_evaluated"] == 2.0
    assert r.quality["failed_rules"] == 0.0
    assert r.prob_attack is None and r.score is None


def test_api_tamper_flags_khac_rong_thi_fail_va_co_nhan_tieng_viet():
    flags = ["getUserMedia:non_native_tostring", "tham_so_la:ly_do_la"]
    r = run(real_camprobe(api_tamper_flags=flags))
    assert_fail(r)
    ev = names(r, "api_tamper_flag")
    assert [e.value for e in ev] == flags
    assert ev[0].label_vi == flag_label_vi(flags[0])
    assert "getUserMedia" in ev[0].label_vi and "bị thay mã" in ev[0].label_vi
    # cờ lạ vẫn có nhãn, giữ nguyên chuỗi gốc
    assert ev[1].label_vi == "Dấu hiệu can thiệp camera: tham_so_la:ly_do_la"


def test_flag_label_vi_co_la_hoac_ly_do_la_giu_nguyen_chuoi():
    assert (
        flag_label_vi("getUserMedia:ly_do_la") == "Dấu hiệu can thiệp camera: getUserMedia:ly_do_la"
    )
    assert flag_label_vi("khong_co_dau_hai_cham").endswith("khong_co_dau_hai_cham")
    assert "không còn là hàm" in flag_label_vi("enumerateDevices:not_function")


def test_apply_nhanh_ma_settings_khong_doi_thi_fail():
    r = run(real_camprobe(constraint_probes=[probe(MIN_APPLY_CONSTRAINTS_MS - 1, settings=False)]))
    assert_fail(r)
    ev = names(r, "constraint_probe")
    assert len(ev) == 1 and ev[0].value.startswith("fast_apply_constraints")
    assert "1280x720" in ev[0].value
    assert ev[0].label_vi


def test_apply_cham_settings_khong_doi_nhung_khung_doi_thi_khong_fail_luat_apply():
    r = run(real_camprobe(constraint_probes=[probe(50.0, settings=False, size=True)]))
    assert_pass(r)
    assert not names(r, "constraint_probe")


def test_frame_size_khong_doi_thi_fail():
    r = run(real_camprobe(constraint_probes=[probe(100.0, settings=True, size=False)]))
    assert_fail(r)
    ev = names(r, "constraint_probe")
    assert len(ev) == 1 and ev[0].value.startswith("frame_size_unchanged")


def test_frame_size_thieu_truong_la_khong_do_duoc_khong_fail():
    # Không đo được khung (ví dụ <video> ẩn trên iOS) không phải bằng chứng can thiệp.
    p = probe(100.0)
    del p["frame_size_changed"]
    r = run(real_camprobe(constraint_probes=[p]))
    assert_pass(r)
    assert not names(r, "constraint_probe")


def test_frame_size_null_la_khong_do_duoc_khong_fail():
    p = probe(100.0)
    p["frame_size_changed"] = None
    assert_pass(run(real_camprobe(constraint_probes=[p])))


def test_apply_nhanh_settings_khong_doi_va_khong_do_duoc_khung_van_fail_luat_apply():
    p = probe(1.0, settings=False)
    p["frame_size_changed"] = None
    r = run(real_camprobe(constraint_probes=[p]))
    assert_fail(r)
    assert names(r, "constraint_probe")[0].value.startswith("fast_apply_constraints")


def test_probe_ok_false_bi_bo_qua():
    bad = probe(1.0, ok=False, settings=False, size=False)
    r = run(real_camprobe(constraint_probes=[bad]))
    assert_pass(r)
    assert r.quality["probes_evaluated"] == 0.0


def test_bien_apply_ms_bang_nguong_khong_fail():
    r = run(real_camprobe(constraint_probes=[probe(MIN_APPLY_CONSTRAINTS_MS, settings=False)]))
    assert_pass(r)


def test_apply_nhanh_nhung_settings_doi_thi_khong_fail_luat_apply():
    r = run(real_camprobe(constraint_probes=[probe(0.1, settings=True)]))
    assert_pass(r)


def test_ca_hai_luat_probe_cung_hong_thi_co_hai_bang_chung():
    r = run(real_camprobe(constraint_probes=[probe(1.0, settings=False, size=False)]))
    assert_fail(r)
    assert len(names(r, "constraint_probe")) == 2
    assert r.quality["failed_rules"] == 2.0


def test_mot_probe_hong_trong_nhieu_probe_van_fail():
    r = run(real_camprobe(constraint_probes=[probe(100.0), probe(1.0, settings=False)]))
    assert_fail(r)


def test_duplicate_ratio_vuot_nguong_thi_fail():
    r = run(real_camprobe(duplicate_frame_ratio=MAX_DUPLICATE_FRAME_RATIO + 0.01))
    assert_fail(r)
    assert len(names(r, "duplicate_frame_ratio")) == 1


def test_duplicate_ratio_dung_bang_nguong_thi_pass():
    r = run(real_camprobe(duplicate_frame_ratio=MAX_DUPLICATE_FRAME_RATIO))
    assert_pass(r)
    assert names(r, "duplicate_frame_ratio")[0].value == MAX_DUPLICATE_FRAME_RATIO


@pytest.mark.parametrize("value", [None, "0.9", float("nan"), float("inf"), True, [], {}])
def test_duplicate_ratio_khong_hop_le_thi_bo_qua(value):
    r = run(real_camprobe(duplicate_frame_ratio=value))
    assert_pass(r)
    assert not names(r, "duplicate_frame_ratio")


def test_duplicate_ratio_thieu_truong_thi_bo_qua():
    data = real_camprobe()
    del data["duplicate_frame_ratio"]
    r = run(data)
    assert_pass(r)
    assert not names(r, "duplicate_frame_ratio")


@pytest.mark.parametrize("label", ["OBS Virtual Camera", "ManyCam Virtual Webcam", "Dummy Device"])
def test_ten_thiet_bi_nghi_ngo_chi_la_bang_chung_phu(label):
    r = run(real_camprobe(device_label=label))
    assert_pass(r)
    ev = names(r, "device_label")
    assert len(ev) == 1 and ev[0].value == label and ev[0].label_vi
    assert r.quality["failed_rules"] == 0.0


@pytest.mark.parametrize("label", ["Integrated Camera", "HD Webcam C920", "", None, 123])
def test_ten_thiet_bi_binh_thuong_khong_co_bang_chung(label):
    r = run(real_camprobe(device_label=label))
    assert_pass(r)
    assert not names(r, "device_label")


def test_ten_thiet_bi_nghi_ngo_ket_hop_luat_khac_van_fail_do_luat_khac():
    r = run(real_camprobe(device_label="OBS Virtual Camera", api_tamper_flags=["getSettings:x"]))
    assert_fail(r)
    assert names(r, "device_label")


@pytest.mark.parametrize(
    "signals",
    [
        {},
        {"camprobe": None},
        {"camprobe": []},
        {"camprobe": "x"},
        {"camprobe": 1},
        {"camprobe": {}},
        {"camprobe": {"api_tamper_flags": None}},
        {"camprobe": {"api_tamper_flags": "getUserMedia:not_function"}},
        {"camprobe": {"api_tamper_flags": {"a": 1}}},
        {"camprobe": {"api_tamper_flags": ["ok:x", 3]}},
        {"camprobe": {"api_tamper_flags": [None]}},
    ],
)
def test_thieu_hoac_sai_dang_thi_degraded_khong_bao_gio_la_dat(signals):
    r = run(signals=signals)
    assert r.status == Status.DEGRADED
    assert r.gate is None
    assert r.is_usable is False
    assert r.prob_attack is None


def test_degraded_ghi_camprobe_present():
    assert run(signals={}).quality == {"camprobe_present": False}
    assert run({"api_tamper_flags": None}).quality == {"camprobe_present": True}


@pytest.mark.parametrize(
    "probes",
    [
        ["x", 1, None, [], {"ok": True}],
        "khong-phai-list",
        None,
        {"ok": True},
        [{"ok": True, "requested": "1280x720", "apply_ms": 1, "frame_size_changed": False}],
        [{"ok": True, "requested": None, "apply_ms": "nhanh", "settings_changed": "yes"}],
        [probe("5"), probe(None), probe(float("nan")), probe(True), probe([])],
    ],
)
def test_dau_vao_pha_hong_khong_nem_ngoai_le(probes):
    r = run(real_camprobe(constraint_probes=probes))
    assert r.status == Status.OK
    assert r.gate in (Gate.PASS, Gate.FAIL)
    jsonschema.validate(r.to_contract(), SCHEMA)


def test_apply_ms_dang_chuoi_bi_bo_qua_luat_apply():
    r = run(real_camprobe(constraint_probes=[probe("1", settings=False)]))
    assert_pass(r)


def test_requested_khong_phai_dict_van_ghi_bang_chung_probe_hong():
    p = probe(100.0, size=False)
    p["requested"] = "bậy"
    r = run(real_camprobe(constraint_probes=[p]))
    assert_fail(r)
    assert "None" in names(r, "constraint_probe")[0].value


def test_thieu_constraint_probes_thi_khong_co_probe_nao_duoc_danh_gia():
    data = real_camprobe()
    del data["constraint_probes"]
    r = run(data)
    assert_pass(r)
    assert r.quality["probes_evaluated"] == 0.0


def test_khong_sua_dau_vao():
    data = real_camprobe(api_tamper_flags=["getUserMedia:not_function"])
    before = deepcopy(data)
    run(data)
    assert data == before


@pytest.mark.parametrize(
    "camprobe",
    [
        real_camprobe(),
        real_camprobe(api_tamper_flags=["getUserMedia:non_native_tostring", "lạ:lạ"]),
        real_camprobe(constraint_probes=[probe(1.0, settings=False, size=False)]),
        real_camprobe(duplicate_frame_ratio=0.9, device_label="OBS Virtual Camera"),
        {"api_tamper_flags": 5},
    ],
    ids=["pass", "tamper", "probe", "duplicate+label", "degraded"],
)
def test_ket_qua_hop_le_voi_hop_dong(camprobe):
    r = run(camprobe)
    jsonschema.validate(r.to_contract(), SCHEMA)
    assert r.module == "camprobe"


def test_ket_qua_degraded_khong_signals_hop_le_voi_hop_dong():
    r = run(signals={})
    jsonschema.validate(r.to_contract(), SCHEMA)
    assert r.to_contract()["status"] == "degraded"


# --- registry ---


def test_registry_mixed_chon_camprobe_that(monkeypatch):
    monkeypatch.setenv("USE_MOCK_MODELS", "mixed")
    assert isinstance(get_detector(Module.CAMPROBE), CamProbeDetector)


def test_registry_false_cung_la_camprobe_that(monkeypatch):
    monkeypatch.setenv("USE_MOCK_MODELS", "false")
    assert isinstance(get_detector(Module.CAMPROBE), CamProbeDetector)


def test_registry_true_van_la_mock(monkeypatch):
    monkeypatch.setenv("USE_MOCK_MODELS", "true")
    assert get_detector(Module.CAMPROBE) is MOCK_DETECTORS[Module.CAMPROBE]


def test_registry_mixed_tra_cung_instance(monkeypatch):
    monkeypatch.setenv("USE_MOCK_MODELS", "mixed")
    assert get_detector(Module.CAMPROBE) is get_detector(Module.CAMPROBE)


# --- tích hợp router ---


def mock_results() -> dict[Module, ModuleResult]:
    inp = DetectorInput(metadata={"scenario": "genuine"})
    return {module: MockDetector(module).predict(inp) for module in Module}


def test_router_camprobe_that_pass_thi_khong_chan_quyet_dinh():
    values = mock_results()
    values[Module.CAMPROBE] = run(real_camprobe())
    assert TrustRouter().finalize(values).status == "pass"


def test_router_camprobe_gate_fail_thi_review_uu_tien_cao():
    values = mock_results()
    values[Module.CAMPROBE] = run(real_camprobe(api_tamper_flags=["getUserMedia:not_function"]))
    decision = TrustRouter().finalize(values)
    assert decision.status == "review" and decision.priority == "high"


def test_router_camprobe_degraded_thi_review():
    values = mock_results()
    values[Module.CAMPROBE] = run(signals={})
    assert TrustRouter().finalize(values).status == "review"
