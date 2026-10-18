"""FOR-03: quét nguồn gốc (AudioSeal + C2PA), kết luận MỘT CHIỀU, không cần trọng số thật hay mạng."""

from __future__ import annotations

import json
import os
import socket
import wave
from pathlib import Path
from typing import Any

import jsonschema
import numpy as np
import pytest
import yaml
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from vericlue_ml.common import DetectorInput, Evidence, EvidenceType, Module, ModuleResult, Status
from vericlue_ml.forensic import provenance as prov
from vericlue_ml.forensic.provenance import (
    CONCLUSION_NONE,
    EV_C2PA,
    EV_CONCLUSION,
    EV_INTERVALS,
    EV_NOTE,
    EV_PERTH,
    EV_TOOL,
    MIN_INTERVAL_SECONDS,
    NONE_NOTE,
    SAMPLE_RATE,
    WINDOW_THRESHOLD,
    ProvenanceDetector,
    parse_c2pa_manifest,
    provenance_summary,
    read_c2pa,
    watermark_intervals,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "packages" / "contracts" / "schemas"
MODULE_RESULT_SCHEMA = json.loads(
    (SCHEMAS / "module_result.schema.json").read_text(encoding="utf-8")
)
CONCLUSION_AI = "Phát hiện thủy vân AI của {tool}"
STORE_WEIGHTS = Path(r"D:\Projects\vericlue-store\models")


# --- tiện ích -----------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Cả file này không bao giờ được mở kết nối mạng."""

    def boom(*_a, **_k):
        raise AssertionError("Test không được truy cập mạng")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket.socket, "connect_ex", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)


def _forensic_validator(def_name: str) -> jsonschema.Draft202012Validator:
    schemas = [json.loads(p.read_text(encoding="utf-8")) for p in SCHEMAS.glob("*.schema.json")]
    registry = Registry()
    for s in schemas:
        registry = registry.with_resource(
            s["$id"], Resource.from_contents(s, default_specification=DRAFT202012)
        )
    base = "https://vericlue.local/contracts/forensic.schema.json"
    return jsonschema.Draft202012Validator({"$ref": f"{base}#/$defs/{def_name}"}, registry=registry)


def _write_wav(path: Path, seconds: float = 8.0, rate: int = SAMPLE_RATE) -> Path:
    t = np.arange(int(seconds * rate)) / rate
    pcm = (0.3 * np.sin(2 * np.pi * 440 * t) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return path


class FakeAudioSeal:
    """Backend giả: thủy vân (p cao) trong [t0, t1] giây, nếu có."""

    def __init__(self, mark: tuple[float, float] | None = None, bits=None, error=None):
        self.mark = mark
        self.bits = bits
        self.error = error
        self.calls = 0

    def probabilities(self, samples):
        self.calls += 1
        if self.error:
            raise self.error
        probs = np.zeros(samples.size, dtype=np.float32)
        if self.mark:
            probs[int(self.mark[0] * SAMPLE_RATE) : int(self.mark[1] * SAMPLE_RATE)] = 0.9
        return probs, self.bits


def _c2pa(info: dict[str, Any]):
    return lambda _path: dict(info)


def _ev(result: ModuleResult, name: str) -> list[Evidence]:
    return [e for e in result.evidence if e.name == name]


def _value(result: ModuleResult, name: str) -> Any:
    found = _ev(result, name)
    return found[0].value if found else None


@pytest.fixture
def wav(tmp_path) -> Path:
    return _write_wav(tmp_path / "a.wav")


def _run(wav_path, *, audioseal=None, c2pa=None, source=None, audio=True) -> ModuleResult:
    det = ProvenanceDetector(
        audioseal=audioseal or FakeAudioSeal(),
        c2pa_reader=c2pa or _c2pa({"status": "unavailable"}),
    )
    meta = {"source_file": str(source)} if source else {}
    return det.predict(DetectorInput(audio=wav_path if audio else None, metadata=meta))


def _assert_contract(result: ModuleResult) -> None:
    contract = result.to_contract()
    jsonschema.validate(contract, MODULE_RESULT_SCHEMA)
    assert "prob_attack" not in contract  # None bị bỏ khỏi dict hợp đồng


# --- 1. watermark_intervals ---------------------------------------------------------------------


def test_khoang_mang_rong():
    assert watermark_intervals(np.zeros(0, dtype=np.float32)) == ([], 0.0)


def test_khoang_toan_so_0():
    assert watermark_intervals(np.zeros(8 * SAMPLE_RATE, dtype=np.float32)) == ([], 0.0)


def test_khoang_ca_doan_p1():
    intervals, peak = watermark_intervals(np.ones(8 * SAMPLE_RATE, dtype=np.float32))
    assert intervals == [{"t_start": 0.0, "t_end": 8.0, "prob": 1.0}]
    assert peak == 1.0


def test_khoang_thuy_van_giay_3_den_5():
    probs = np.zeros(8 * SAMPLE_RATE, dtype=np.float32)
    probs[3 * SAMPLE_RATE : 5 * SAMPLE_RATE] = 0.9
    intervals, peak = watermark_intervals(probs)
    assert len(intervals) == 1
    assert intervals[0]["t_start"] == pytest.approx(3.0, abs=0.5)
    assert intervals[0]["t_end"] == pytest.approx(5.0, abs=0.5)
    assert intervals[0]["prob"] == pytest.approx(0.9, abs=1e-3)
    assert peak == pytest.approx(0.9, abs=1e-3)


def test_khoang_ngan_hon_toi_thieu_bi_bo():
    probs = np.zeros(8 * SAMPLE_RATE, dtype=np.float32)
    dur = MIN_INTERVAL_SECONDS / 2  # đúng một cửa sổ 0,5 s
    probs[2 * SAMPLE_RATE : int((2 + dur) * SAMPLE_RATE)] = 1.0
    intervals, peak = watermark_intervals(probs)
    assert intervals == []
    assert peak == 1.0  # peak vẫn phản ánh p lớn nhất


def test_khoang_dung_bang_toi_thieu_duoc_giu():
    probs = np.zeros(8 * SAMPLE_RATE, dtype=np.float32)
    probs[2 * SAMPLE_RATE : int((2 + MIN_INTERVAL_SECONDS) * SAMPLE_RATE)] = 1.0
    intervals, _ = watermark_intervals(probs)
    assert len(intervals) == 1


def test_hai_khoang_tach_nhau():
    probs = np.zeros(8 * SAMPLE_RATE, dtype=np.float32)
    probs[1 * SAMPLE_RATE : int(2.5 * SAMPLE_RATE)] = 1.0
    probs[5 * SAMPLE_RATE : int(6.5 * SAMPLE_RATE)] = 1.0
    intervals, _ = watermark_intervals(probs)
    assert len(intervals) == 2
    assert intervals[0]["t_end"] <= intervals[1]["t_start"]


def test_p_dung_nguong_cua_so_duoc_tinh_la_co():
    probs = np.full(4 * SAMPLE_RATE, WINDOW_THRESHOLD, dtype=np.float32)
    intervals, peak = watermark_intervals(probs)
    assert len(intervals) == 1
    assert peak == pytest.approx(WINDOW_THRESHOLD)


def test_p_ngay_duoi_nguong_khong_tinh():
    probs = np.full(4 * SAMPLE_RATE, WINDOW_THRESHOLD - 0.01, dtype=np.float32)
    assert watermark_intervals(probs)[0] == []


# --- 2. ProvenanceDetector --------------------------------------------------------------------


def test_co_thuy_van_audioseal(wav):
    backend = FakeAudioSeal(mark=(3, 5), bits=[1, 0] * 8)
    r = _run(wav, audioseal=backend)
    assert r.status == Status.OK
    assert r.prob_attack is None
    assert r.score == pytest.approx(0.9, abs=1e-3)
    assert _value(r, EV_CONCLUSION) == CONCLUSION_AI.format(tool="AudioSeal")
    assert _value(r, EV_TOOL) == "AudioSeal"
    intervals = _ev(r, EV_INTERVALS)[0]
    assert intervals.type == EvidenceType.SEGMENTS
    assert len(intervals.value) == 1
    notes = [e.value for e in _ev(r, EV_NOTE)]
    assert any("16 bit" in n and "1010101010101010" in n for n in notes)
    assert "chưa hỗ trợ" in _value(r, EV_PERTH)
    assert r.quality["audio_seconds"] == pytest.approx(8.0, abs=0.01)
    _assert_contract(r)


def test_co_thuy_van_khong_co_thong_diep(wav):
    r = _run(wav, audioseal=FakeAudioSeal(mark=(3, 5), bits=None))
    assert _value(r, EV_TOOL) == "AudioSeal"
    assert not any("16 bit" in str(e.value) for e in _ev(r, EV_NOTE))


def test_khong_thuy_van(wav):
    r = _run(wav)
    assert r.status == Status.OK
    assert r.prob_attack is None
    assert r.score == 0.0
    assert _value(r, EV_CONCLUSION) == CONCLUSION_NONE
    assert _ev(r, EV_TOOL) == []
    assert _ev(r, EV_INTERVALS) == []
    assert NONE_NOTE in provenance_summary(r)["notes"]
    assert "KHÔNG có nghĩa là thật" in " ".join(provenance_summary(r)["notes"])
    _assert_contract(r)


def test_khong_audio_khong_source_la_degraded_va_khong_goi_y_that():
    backend = FakeAudioSeal(mark=(3, 5))
    r = _run(None, audioseal=backend, audio=False)
    assert r.status == Status.DEGRADED
    assert backend.calls == 0
    assert r.score is None and r.prob_attack is None
    assert _value(r, EV_CONCLUSION) == CONCLUSION_NONE
    assert "thật" not in _value(r, EV_CONCLUSION)
    assert _ev(r, EV_TOOL) == []
    summary = provenance_summary(r)
    assert summary["status"] == "degraded"
    assert summary["watermark_detected"] is False
    assert not r.is_usable
    _assert_contract(r)


def test_c2pa_ai_hop_le_khong_thuy_van(wav, tmp_path):
    seen: list[Path] = []

    def reader(path):
        seen.append(path)
        return {"status": "ok", "present": True, "valid": True, "ai_generated": True, "signer": "X"}

    r = _run(wav, c2pa=reader, source=tmp_path / "f.wav")
    assert seen == [tmp_path / "f.wav"]
    assert r.status == Status.OK
    assert _value(r, EV_CONCLUSION) == CONCLUSION_AI.format(tool="X")
    assert _value(r, EV_TOOL) == "X"
    assert _value(r, EV_C2PA)["signer"] == "X"
    assert provenance_summary(r)["watermark_detected"] is True
    _assert_contract(r)


def test_c2pa_ai_nhung_chi_c2pa_khong_audio(tmp_path):
    c2pa = _c2pa(
        {"status": "ok", "present": True, "valid": True, "ai_generated": True, "signer": "X"}
    )
    r = _run(None, c2pa=c2pa, source=tmp_path / "f.mp4", audio=False)
    assert r.status == Status.OK  # C2PA đã chạy
    assert _value(r, EV_CONCLUSION) == CONCLUSION_AI.format(tool="X")


def test_c2pa_ai_nhung_khong_hop_le_khong_tinh(wav, tmp_path):
    c2pa = _c2pa(
        {"status": "ok", "present": True, "valid": False, "ai_generated": True, "signer": "X"}
    )
    r = _run(wav, c2pa=c2pa, source=tmp_path / "f.wav")
    assert _value(r, EV_CONCLUSION) == CONCLUSION_NONE
    assert _ev(r, EV_TOOL) == []
    assert provenance_summary(r)["watermark_detected"] is False


def test_c2pa_ai_khong_ro_hop_le_van_tinh(wav, tmp_path):
    c2pa = _c2pa({"status": "ok", "present": True, "valid": None, "ai_generated": True})
    r = _run(wav, c2pa=c2pa, source=tmp_path / "f.wav")
    assert _value(r, EV_CONCLUSION) == CONCLUSION_AI.format(tool="C2PA")


def test_c2pa_khong_co_manifest_va_khong_thuy_van(wav, tmp_path):
    c2pa = _c2pa({"status": "ok", "present": False})
    r = _run(wav, c2pa=c2pa, source=tmp_path / "f.wav")
    assert r.status == Status.OK
    assert _value(r, EV_CONCLUSION) == CONCLUSION_NONE
    assert _value(r, EV_C2PA) == {"status": "ok", "present": False}


def test_c2pa_thieu_thu_vien_van_ok_neu_audioseal_chay(wav, tmp_path):
    c2pa = _c2pa({"status": "unavailable", "note": "Chưa cài c2pa-python"})
    r = _run(wav, c2pa=c2pa, source=tmp_path / "f.wav")
    assert r.status == Status.OK
    assert _value(r, EV_C2PA)["status"] == "unavailable"
    assert "Chưa cài" in provenance_summary(r)["c2pa"]["note"]
    _assert_contract(r)


def test_c2pa_thieu_thu_vien_va_khong_audio_la_degraded(tmp_path):
    c2pa = _c2pa({"status": "unavailable", "note": "Chưa cài c2pa-python"})
    r = _run(None, c2pa=c2pa, source=tmp_path / "f.mp4", audio=False)
    assert r.status == Status.DEGRADED
    assert _value(r, EV_CONCLUSION) == CONCLUSION_NONE


def test_c2pa_loi_doc_khong_phai_ok(tmp_path):
    c2pa = _c2pa({"status": "error", "note": "hỏng"})
    r = _run(None, c2pa=c2pa, source=tmp_path / "f.mp4", audio=False)
    assert r.status == Status.DEGRADED


def test_backend_nem_loi_khong_nem_ra_ngoai(wav):
    backend = FakeAudioSeal(error=RuntimeError("hỏng"))
    r = _run(wav, audioseal=backend)
    assert backend.calls == 1
    assert r.status == Status.DEGRADED
    assert r.score is None and r.prob_attack is None
    notes = " ".join(str(e.value) for e in _ev(r, EV_NOTE))
    assert "lỗi" in notes and "RuntimeError" in notes
    assert _value(r, EV_CONCLUSION) == CONCLUSION_NONE
    _assert_contract(r)


def test_backend_loi_nhung_c2pa_chay_thi_ok(wav, tmp_path):
    r = _run(
        wav,
        audioseal=FakeAudioSeal(error=ValueError("x")),
        c2pa=_c2pa({"status": "ok", "present": False}),
        source=tmp_path / "f.wav",
    )
    assert r.status == Status.OK
    assert r.score is None
    assert any("ValueError" in str(e.value) for e in _ev(r, EV_NOTE))


def test_audio_khong_doc_duoc_khong_nem(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"khong phai am thanh")
    backend = FakeAudioSeal(mark=(0, 8))
    r = _run(bad, audioseal=backend)
    assert backend.calls == 0
    assert r.status == Status.DEGRADED
    assert _value(r, EV_CONCLUSION) == CONCLUSION_NONE


# --- 3. provenance_summary ---------------------------------------------------------------------


def _manual(evidence: list[Evidence], status: Status = Status.OK) -> ModuleResult:
    return ModuleResult(
        module=Module.PROVENANCE,
        model_version="t",
        status=status,
        evidence=evidence,
        latency_ms=0.0,
    )


def _text(name: str, value: Any) -> Evidence:
    return Evidence(type=EvidenceType.TEXT, name=name, value=value)


def test_summary_tu_ket_qua_that_su_hop_le_hop_dong(wav, tmp_path):
    c2pa = {
        "status": "ok",
        "present": True,
        "valid": True,
        "signer": "X",
        "ai_generated": True,
        "note": "n",
    }
    r = _run(
        wav,
        audioseal=FakeAudioSeal(mark=(3, 5), bits=[0] * 16),
        c2pa=_c2pa(c2pa),
        source=tmp_path / "f",
    )
    s = provenance_summary(r)
    assert set(s) == {
        "status",
        "conclusion",
        "watermark_detected",
        "tool",
        "watermark_intervals",
        "notes",
        "c2pa",
    }
    assert s["status"] == "ok"
    assert s["conclusion"] == CONCLUSION_AI.format(tool="AudioSeal")
    assert s["watermark_detected"] is True
    assert s["tool"] == "AudioSeal"
    assert len(s["watermark_intervals"]) == 1
    assert set(s["watermark_intervals"][0]) == {"t_start", "t_end", "prob"}
    assert any("chưa hỗ trợ" in n for n in s["notes"])
    assert s["c2pa"] == c2pa
    _forensic_validator("ForensicProvenance").validate(s)


def test_summary_chi_giu_khoa_c2pa_hop_le():
    c2pa = {"status": "ok", "present": True, "valid": True, "signer": "S", "rac": 1, "x": "y"}
    s = provenance_summary(_manual([_text(EV_C2PA, c2pa)]))
    assert set(s["c2pa"]) == {"status", "present", "valid", "signer"}
    _forensic_validator("ForensicProvenance").validate(s)


def test_summary_khong_co_c2pa_thi_khong_co_khoa():
    s = provenance_summary(_manual([]))
    assert "c2pa" not in s
    assert s["conclusion"] == CONCLUSION_NONE
    assert s["tool"] is None
    assert NONE_NOTE in s["notes"]
    _forensic_validator("ForensicProvenance").validate(s)


def test_summary_c2pa_ai_hop_le_la_detected():
    c2pa = {"status": "ok", "present": True, "valid": True, "ai_generated": True, "signer": "Z"}
    s = provenance_summary(_manual([_text(EV_C2PA, c2pa)]))
    assert s["watermark_detected"] is True
    assert s["tool"] == "Z"
    assert s["conclusion"] == CONCLUSION_AI.format(tool="Z")
    assert NONE_NOTE not in s["notes"]


def test_summary_c2pa_valid_none_van_detected_con_valid_false_thi_khong():
    base = {"status": "ok", "present": True, "ai_generated": True}
    assert provenance_summary(_manual([_text(EV_C2PA, {**base, "valid": None})]))[
        "watermark_detected"
    ]
    s = provenance_summary(_manual([_text(EV_C2PA, {**base, "valid": False})]))
    assert s["watermark_detected"] is False
    assert s["tool"] is None
    assert s["conclusion"] == CONCLUSION_NONE
    _forensic_validator("ForensicProvenance").validate(s)


def test_summary_giu_trang_thai_degraded():
    s = provenance_summary(_manual([], status=Status.DEGRADED))
    assert s["status"] == "degraded"
    assert s["watermark_detected"] is False
    _forensic_validator("ForensicProvenance").validate(s)


def test_summary_khoang_bo_qua_muc_hong():
    items = [{"t_start": 1, "t_end": 2, "prob": 0.8}, {"t_start": 3}, "rac"]
    s = provenance_summary(_manual([_text(EV_INTERVALS, items), _text(EV_TOOL, "AudioSeal")]))
    assert s["watermark_intervals"] == [{"t_start": 1.0, "t_end": 2.0, "prob": 0.8}]
    _forensic_validator("ForensicProvenance").validate(s)


def test_summary_ghi_chu_va_perth_di_theo_thu_tu():
    s = provenance_summary(
        _manual([_text(EV_NOTE, "a"), _text(EV_NOTE, "b"), _text(EV_PERTH, "perth chưa hỗ trợ")])
    )
    assert s["notes"][:3] == ["a", "b", "perth chưa hỗ trợ"]


# --- 4. parse_c2pa_manifest ----------------------------------------------------------------------

AI_ACTION = {
    "label": "c2pa.actions.v2",
    "data": {
        "actions": [
            {
                "action": "c2pa.created",
                "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
            }
        ]
    },
}


def _manifest(assertions=None, status=None, state="Valid", signature=None) -> dict[str, Any]:
    return {
        "active_manifest": "urn:uuid:1",
        "manifests": {
            "urn:uuid:1": {
                "assertions": assertions if assertions is not None else [],
                "signature_info": signature if signature is not None else {"common_name": "CN"},
            }
        },
        "validation_status": status or [],
        "validation_state": state,
    }


def test_parse_ai_va_chung_chi_chua_tin_cay():
    out = parse_c2pa_manifest(
        _manifest([AI_ACTION], [{"code": "signingCredential.untrusted"}], "Valid")
    )
    assert out["status"] == "ok" and out["present"] is True
    assert out["ai_generated"] is True
    assert out["valid"] is True
    assert "chưa được tin cậy" in out["note"]
    assert out["signer"] == "CN"


def test_parse_ma_loi_khac_la_khong_hop_le():
    out = parse_c2pa_manifest(
        _manifest([AI_ACTION], [{"code": "assertion.dataHash.mismatch"}], "Invalid")
    )
    assert out["valid"] is False
    assert "note" not in out  # không có untrusted → không có ghi chú


def test_parse_loi_ket_hop_untrusted_van_la_khong_hop_le():
    status = [{"code": "signingCredential.untrusted"}, {"code": "assertion.dataHash.mismatch"}]
    out = parse_c2pa_manifest(_manifest([AI_ACTION], status, "Valid"))
    assert out["valid"] is False
    assert "chưa được tin cậy" in out["note"]


def test_parse_state_invalid_du_khong_co_status_van_khong_hop_le():
    assert parse_c2pa_manifest(_manifest([AI_ACTION], [], "Invalid"))["valid"] is False


def test_parse_state_trusted_la_hop_le():
    assert parse_c2pa_manifest(_manifest([AI_ACTION], [], "Trusted"))["valid"] is True


def test_parse_khong_co_action_ai():
    camera = {
        "label": "c2pa.actions",
        "data": {
            "actions": [
                {
                    "action": "c2pa.created",
                    "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture",
                }
            ]
        },
    }
    out = parse_c2pa_manifest(_manifest([camera]))
    assert out["ai_generated"] is None
    assert out["valid"] is True


def test_parse_assertion_khac_actions_bi_bo_qua():
    other = {"label": "c2pa.hash.data", "data": AI_ACTION["data"]}
    assert parse_c2pa_manifest(_manifest([other]))["ai_generated"] is None


def test_parse_dang_viet_khac_cua_digital_source_type():
    action = {
        "label": "c2pa.actions",
        "data": {"actions": [{"digitalSourceType": "compositeWithTrained_Algorithmic_Media"}]},
    }
    assert parse_c2pa_manifest(_manifest([action]))["ai_generated"] is True


def test_parse_signer_lay_common_name_roi_issuer():
    assert (
        parse_c2pa_manifest(_manifest(signature={"common_name": "CN", "issuer": "IS"}))["signer"]
        == "CN"
    )
    assert parse_c2pa_manifest(_manifest(signature={"issuer": "IS"}))["signer"] == "IS"
    assert parse_c2pa_manifest(_manifest(signature={}))["signer"] is None


def test_parse_dict_rong_khong_nem_loi():
    out = parse_c2pa_manifest({})
    assert out["status"] == "ok"
    assert out["ai_generated"] is None
    assert out["valid"] is False  # không có validation_state → không coi là hợp lệ
    assert out["signer"] is None


def test_parse_ket_qua_khop_hop_dong():
    out = parse_c2pa_manifest(_manifest([AI_ACTION], [{"code": "signingCredential.untrusted"}]))
    summary = provenance_summary(_manual([_text(EV_C2PA, out)]))
    assert summary["watermark_detected"] is True
    _forensic_validator("ForensicProvenance").validate(summary)


# --- 5. read_c2pa thật -------------------------------------------------------------------------


def test_read_c2pa_wav_thuong_khong_co_manifest(tmp_path):
    pytest.importorskip("c2pa")
    out = read_c2pa(_write_wav(tmp_path / "a.wav", seconds=1))
    assert out["status"] == "ok"
    assert out["present"] is False


def test_read_c2pa_file_khong_ton_tai_la_error(tmp_path):
    pytest.importorskip("c2pa")
    out = read_c2pa(tmp_path / "khong_co.wav")
    assert out["status"] == "error"
    assert "note" in out


def test_read_c2pa_file_rac_khong_nem_loi(tmp_path):
    pytest.importorskip("c2pa")
    junk = tmp_path / "rac.wav"
    junk.write_bytes(os.urandom(2048))
    out = read_c2pa(junk)
    assert out["status"] in {"error", "ok"}
    assert out.get("valid") is not True  # không bao giờ "hợp lệ" với file rác
    assert out.get("ai_generated") is not True


def test_read_c2pa_thieu_thu_vien_ghi_unavailable(monkeypatch, tmp_path):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "c2pa":
            raise ImportError("giả lập thiếu thư viện")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    out = read_c2pa(tmp_path / "x.wav")
    assert out["status"] == "unavailable"
    assert "note" in out


# --- 6. nạp trọng số offline có kiểm SHA-256 ---------------------------------------------------


def _manifest_file(tmp_path: Path, sha256: str, revision: str = "rev12345abcdef") -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "models": [
                    {
                        "id": prov.AUDIOSEAL_ID,
                        "source": {"revision": revision},
                        "files": [{"path": prov.AUDIOSEAL_FILE, "sha256": sha256}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _put_weights(models_dir: Path, content: bytes) -> Path:
    target = models_dir / prov.AUDIOSEAL_ID / prov.AUDIOSEAL_FILE
    target.parent.mkdir(parents=True)
    target.write_bytes(content)
    return target


def test_thieu_trong_so_ghi_chu_khong_nem(monkeypatch, tmp_path, wav):
    monkeypatch.setenv("ML_MODELS_MANIFEST", str(_manifest_file(tmp_path, "0" * 64)))
    models = tmp_path / "models"
    models.mkdir()
    det = ProvenanceDetector()
    det.preload(models_dir=models)
    r = det.predict(DetectorInput(audio=wav))
    assert r.status == Status.DEGRADED
    notes = " ".join(str(e.value) for e in _ev(r, EV_NOTE))
    assert "Thiếu trọng số" in notes
    assert _value(r, EV_CONCLUSION) == CONCLUSION_NONE
    assert r.prob_attack is None
    _assert_contract(r)


def test_sai_sha256_la_e_integrity_va_khong_nap(monkeypatch, tmp_path, wav):
    monkeypatch.setenv("ML_MODELS_MANIFEST", str(_manifest_file(tmp_path, "ab" * 32)))
    models = tmp_path / "models"
    _put_weights(models, b"rac khong phai trong so")

    def must_not_load(*_a, **_k):
        raise AssertionError("Không được nạp mô hình khi SHA-256 sai")

    monkeypatch.setattr(prov, "RealAudioSeal", must_not_load)
    det = ProvenanceDetector()
    det.preload(models_dir=models)
    assert det._audioseal is None
    assert det._audioseal_error is not None
    assert det._audioseal_error.code == prov.ErrorCode.E_INTEGRITY
    r = det.predict(DetectorInput(audio=wav))
    assert r.status == Status.DEGRADED
    assert any("SHA-256" in str(e.value) for e in _ev(r, EV_NOTE))
    assert _value(r, EV_CONCLUSION) == CONCLUSION_NONE


def test_dung_sha256_moi_nap_va_dung_duong_dan(monkeypatch, tmp_path, wav):
    import hashlib

    content = b"trong so gia"
    monkeypatch.setenv(
        "ML_MODELS_MANIFEST", str(_manifest_file(tmp_path, hashlib.sha256(content).hexdigest()))
    )
    models = tmp_path / "models"
    weights = _put_weights(models, content)
    loaded: list[tuple[Path, str]] = []

    class FakeReal(FakeAudioSeal):
        def __init__(self, path, revision):
            super().__init__()
            loaded.append((path, revision))

    monkeypatch.setattr(prov, "RealAudioSeal", FakeReal)
    det = ProvenanceDetector(c2pa_reader=_c2pa({"status": "unavailable"}))
    det.preload(models_dir=models)
    assert loaded == [(weights, "rev12345abcdef")]
    assert det.version.startswith("audioseal-detector@rev12345")
    assert det.predict(DetectorInput(audio=wav)).status == Status.OK


def test_loi_nap_dinh_khong_kiem_lai(monkeypatch, tmp_path, wav):
    monkeypatch.setenv("ML_MODELS_MANIFEST", str(_manifest_file(tmp_path, "0" * 64)))
    models = tmp_path / "models"
    models.mkdir()
    calls = {"n": 0}
    original = prov._verified_weights

    def counting(root):
        calls["n"] += 1
        return original(root)

    monkeypatch.setattr(prov, "_verified_weights", counting)
    det = ProvenanceDetector()
    det.preload(models_dir=models)
    det.preload(models_dir=models)
    assert calls["n"] == 1
    det.predict(DetectorInput(audio=wav))  # predict gọi preload() lần nữa → vẫn không kiểm lại
    det.predict(DetectorInput(audio=wav))
    assert calls["n"] == 1


def test_nap_thanh_cong_chi_mot_lan(monkeypatch, tmp_path):
    import hashlib

    content = b"x"
    monkeypatch.setenv(
        "ML_MODELS_MANIFEST", str(_manifest_file(tmp_path, hashlib.sha256(content).hexdigest()))
    )
    models = tmp_path / "models"
    _put_weights(models, content)
    made: list[int] = []

    class FakeReal(FakeAudioSeal):
        def __init__(self, path, revision):
            super().__init__()
            made.append(1)

    monkeypatch.setattr(prov, "RealAudioSeal", FakeReal)
    det = ProvenanceDetector()
    det.preload(models_dir=models)
    det.preload(models_dir=models)
    assert made == [1]


def test_manifest_thieu_muc_audioseal_ghi_loi_khong_nem(monkeypatch, tmp_path, wav):
    empty = tmp_path / "m.yaml"
    empty.write_text(yaml.safe_dump({"models": []}), encoding="utf-8")
    monkeypatch.setenv("ML_MODELS_MANIFEST", str(empty))
    det = ProvenanceDetector()
    det.preload(models_dir=tmp_path)
    r = det.predict(DetectorInput(audio=wav))
    assert r.status == Status.DEGRADED
    assert _value(r, EV_CONCLUSION) == CONCLUSION_NONE


def test_preload_thu_tu_models_dir_khong_dung_mang(monkeypatch, tmp_path):
    """Fixture no_network (autouse) làm mọi kết nối ném lỗi; preload/predict vẫn phải xong."""
    monkeypatch.setenv("ML_MODELS_MANIFEST", str(_manifest_file(tmp_path, "0" * 64)))
    det = ProvenanceDetector()
    det.preload(models_dir=tmp_path / "khong_co")
    with pytest.raises(AssertionError, match="mạng"):
        socket.getaddrinfo("example.com", 80)  # xác nhận chốt chặn thật sự đang bật
    assert det._audioseal_error is not None


# --- 7. AudioSeal thật (chậm) --------------------------------------------------------------------


def _real_models_dir() -> Path | None:
    candidates = [os.environ.get("MODELS_DIR"), str(STORE_WEIGHTS)]
    for c in candidates:
        if c and (Path(c) / prov.AUDIOSEAL_ID / prov.AUDIOSEAL_FILE).is_file():
            return Path(c)
    return None


@pytest.mark.slow
def test_audioseal_that_khong_thuy_van(monkeypatch, tmp_path):
    models = _real_models_dir()
    if models is None:
        pytest.skip("Thiếu detector_base.pth (đặt MODELS_DIR hoặc dùng vericlue-store)")
    pytest.importorskip("audioseal")
    pytest.importorskip("torch")
    monkeypatch.setenv("NO_TORCH_COMPILE", "1")
    monkeypatch.delenv("ML_MODELS_MANIFEST", raising=False)
    rng = np.random.default_rng(0)
    t = np.arange(8 * SAMPLE_RATE) / SAMPLE_RATE
    signal = 0.2 * np.sin(2 * np.pi * 300 * t) + 0.05 * rng.standard_normal(t.size)
    pcm = (np.clip(signal, -1, 1) * 32767).astype("<i2")
    path = tmp_path / "noise.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())

    det = ProvenanceDetector()
    det.preload(models_dir=models)
    assert det._audioseal is not None, det._audioseal_error
    r = det.predict(DetectorInput(audio=path))
    assert r.status == Status.OK
    assert r.prob_attack is None
    assert _value(r, EV_CONCLUSION) == CONCLUSION_NONE
    assert provenance_summary(r)["watermark_detected"] is False
    _assert_contract(r)
