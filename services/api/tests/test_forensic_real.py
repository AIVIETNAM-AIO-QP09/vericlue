"""Giám định đường THẬT (USE_MOCK_MODELS=false): job nền, tiến độ, lỗi, báo cáo, resolve_detectors.

Không cần mô hình hay cv2/av: nguồn media GIẢ + ForensicPipeline THẬT với detector GIẢ.
Cách thay thế: monkeypatch `FileMediaSource` và `build_pipeline` trong `forensic_runner`
(run_forensic_job phân giải chúng lúc gọi). TestClient chạy BackgroundTasks xong rồi mới trả về.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from contract_utils import validate
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_mixed_mode import make_client

from vericlue_api.db.models import ForensicJobRow, ForensicSegmentRow
from vericlue_api.services import forensic_runner
from vericlue_api.services.forensic_service import LIMITATIONS_VI, ForensicStore
from vericlue_ml.common.result import ErrorCode, Module, ModuleResult, Status
from vericlue_ml.forensic.media import MediaError, MediaInfo
from vericlue_ml.forensic.pipeline import ForensicPipeline, Thresholds
from vericlue_ml.forensic.provenance import ProvenanceDetector

DATA = b"\x00byte goc bat ky \xff\xfe" * 50
DURATION = 12.0  # 7 đoạn: 0, 1.5, ..., 9
FLAGGED_CALL = 3  # đoạn thứ 4 (4.5–7.5 s) bị đánh dấu → khoảng nghi giả 3.5–8.5 s
THRESHOLDS = Thresholds(face_b=0.15, face_a=0.60, voice_spoof=0.15)


# --- đồ giả --------------------------------------------------------------------
class FakeSource:
    """Nguồn media giả: không đọc file, chỉ tạo file rỗng tại nơi pipeline yêu cầu."""

    def __init__(self, path: Path, info: MediaInfo | None = None) -> None:
        self.path = path
        self.info = info or MediaInfo(
            kind="video",
            size_bytes=len(DATA),
            duration_s=DURATION,
            container="mp4",
            width=640,
            height=480,
            fps=25.0,
            has_audio=True,
        )

    def frames(self, t0: float, t1: float, count: int, outdir: Path) -> list[Path]:
        outdir.mkdir(parents=True, exist_ok=True)
        paths = [outdir / f"f{i}.png" for i in range(count)]
        for p in paths:
            p.write_bytes(b"png")
        return paths

    def audio_wav(self, t0: float, t1: float, out: Path) -> Path:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"wav")
        return out

    def full_audio_wav(self, out: Path) -> Path:
        return self.audio_wav(0, 0, out)


class FakeDetector:
    """Trả prob_attack theo `probs(call_index)`; `version` tùy chỉnh."""

    def __init__(self, module: Module, probs, version: str = "fake@1") -> None:
        self.name, self.module, self.version = str(module), module, version
        self._probs, self.calls = probs, 0

    def predict(self, inp) -> ModuleResult:
        prob = self._probs(self.calls)
        self.calls += 1
        return ModuleResult(
            module=self.module,
            model_version=self.version,
            status=Status.OK,
            score=prob,
            prob_attack=prob,
            latency_ms=1.0,
        )


def _face(flag_call: int | None = FLAGGED_CALL) -> FakeDetector:
    return FakeDetector(
        Module.FACE_DEEPFAKE, lambda i: 0.95 if flag_call is not None and i == flag_call else 0.05
    )


def _voice() -> FakeDetector:
    return FakeDetector(Module.VOICE_SPOOF, lambda i: 0.02)


def _pipeline(detectors: dict[Module, FakeDetector], unavailable=None) -> ForensicPipeline:
    return ForensicPipeline(
        detectors,
        unavailable or {Module.LIPSYNC: "Chưa có mô hình thật"},
        lambda result: result,  # calibrate giả: điểm đã là xác suất
        THRESHOLDS,
    )


@pytest.fixture
def real_client(monkeypatch, tmp_path):
    """App với USE_MOCK_MODELS=false, MODELS_DIR rỗng, nguồn media giả và pipeline đủ detector."""
    monkeypatch.setattr(forensic_runner, "FileMediaSource", FakeSource)
    monkeypatch.setattr(
        forensic_runner,
        "build_pipeline",
        lambda root: _pipeline({Module.FACE_DEEPFAKE: _face(), Module.VOICE_SPOOF: _voice()}),
    )
    with make_client(monkeypatch, tmp_path, "false") as client:
        yield client


def _post(client: TestClient, data: bytes = DATA):
    return client.post("/v1/forensic/jobs", files={"file": ("clip.mp4", data, "video/mp4")})


def _run(client: TestClient, data: bytes = DATA) -> tuple[str, dict]:
    created = _post(client, data)
    assert created.status_code == 200, created.text
    validate(created.json(), "forensic", "JobCreated")
    job_id = created.json()["job_id"]
    got = client.get(f"/v1/forensic/jobs/{job_id}")
    assert got.status_code == 200
    job = got.json()
    validate(job, "forensic", "ForensicJob")
    return job_id, job


# --- 1. tiếp nhận và hash ----------------------------------------------------------
def test_tao_job_queued_va_hash_tren_byte_goc(real_client):
    created = _post(real_client)
    assert created.status_code == 200
    assert created.json()["status"] == "queued"  # phản hồi trả trước khi tác vụ nền xong
    job_id = created.json()["job_id"]
    job = real_client.get(f"/v1/forensic/jobs/{job_id}").json()
    validate(job, "forensic", "ForensicJob")
    assert job["status"] == "done"
    digest = hashlib.sha256(DATA).hexdigest()
    assert job["file_sha256"] == digest
    with real_client.app.state.vericlue.database.sessions() as db:
        row = db.get(ForensicJobRow, job_id)
        assert row.file_sha256 == digest
        stored = Path(row.source_path).read_bytes()
    assert stored == DATA  # file lưu nguyên vẹn
    assert hashlib.sha256(stored).hexdigest() == digest


# --- 2. job hoàn tất ---------------------------------------------------------------
def test_job_done_co_doan_tien_do_media_va_khoang_nghi_gia(real_client):
    job_id, job = _run(real_client)
    assert job["status"] == "done"
    assert job["verdict"] == "suspect"
    assert job["error"] is None
    assert len(job["segments"]) == 7
    for segment in job["segments"]:
        modules = {s["module"]: s for s in segment["signals"]}
        assert set(modules) == {"face_deepfake", "voice_spoof", "lipsync"}
        for signal in segment["signals"]:
            assert signal["status"] in {"ok", "unavailable"}
            if signal["status"] == "ok":
                assert signal["applicable"] is True and signal["prob_attack"] is not None
            else:
                assert signal["applicable"] is False and signal["reason"]
        assert modules["lipsync"]["status"] == "unavailable"
    n = len(job["segments"])
    assert job["progress"] == {"stage": "finalize", "segments_done": n, "segments_total": n}
    assert job["media"]["kind"] == "video"
    assert job["media"]["duration_s"] == DURATION
    # đúng 1 khoảng: đoạn 4.5–7.5 s mở rộng ±1 s
    [interval] = job["suspect_intervals"]
    assert interval["t_start"] == pytest.approx(3.5)
    assert interval["t_end"] == pytest.approx(8.5)
    assert 0 <= interval["t_start"] < interval["t_end"] <= DURATION
    assert interval["modules"] == ["face_deepfake"]
    assert interval["max_prob_attack"] == pytest.approx(0.95)
    assert job["verdict_reason"]
    with real_client.app.state.vericlue.database.sessions() as db:
        rows = db.scalars(
            select(ForensicSegmentRow).where(ForensicSegmentRow.job_id == job_id)
        ).all()
        assert len(rows) == n
        assert all(r.signals and "status" in r.signals[0] for r in rows)
        assert db.get(ForensicJobRow, job_id).verdict == "suspect"


def test_khong_co_dau_hieu_va_du_buoc_bat_buoc_thi_authentic(monkeypatch, tmp_path):
    """Đối chứng cho mục 3: authentic chỉ khi mọi bước bắt buộc đã chạy và dưới ngưỡng."""
    monkeypatch.setattr(forensic_runner, "FileMediaSource", FakeSource)
    monkeypatch.setattr(
        forensic_runner,
        "build_pipeline",
        lambda root: _pipeline({Module.FACE_DEEPFAKE: _face(None), Module.VOICE_SPOOF: _voice()}),
    )
    with make_client(monkeypatch, tmp_path, "false") as client:
        _, job = _run(client)
    assert job["verdict"] == "authentic"
    assert job["suspect_intervals"] == []
    assert not any(u["required"] for u in job["unavailable_modules"])


# --- 3. thiếu bước bắt buộc --------------------------------------------------------
def test_thieu_face_deepfake_thi_inconclusive_khong_bao_gio_authentic(monkeypatch, tmp_path):
    monkeypatch.setattr(forensic_runner, "FileMediaSource", FakeSource)
    monkeypatch.setattr(
        forensic_runner,
        "build_pipeline",
        lambda root: _pipeline(
            {Module.VOICE_SPOOF: _voice()},
            {Module.FACE_DEEPFAKE: "Chưa có mô hình thật (FACE-02)"},
        ),
    )
    with make_client(monkeypatch, tmp_path, "false") as client:
        job_id, job = _run(client)
        assert job["status"] == "done"
        assert job["verdict"] == "inconclusive"
        assert job["verdict"] != "authentic"
        face = next(u for u in job["unavailable_modules"] if u["module"] == "face_deepfake")
        assert face["required"] is True
        assert "FACE-02" in face["reason"]
        assert "face_deepfake" in job["verdict_reason"]
        assert "thiếu bước bắt buộc" in job["verdict_reason"]
        # mọi tín hiệu face_deepfake đều unavailable, không có điểm
        for segment in job["segments"]:
            face_sig = next(s for s in segment["signals"] if s["module"] == "face_deepfake")
            assert face_sig["status"] == "unavailable" and face_sig["prob_attack"] is None
        report = real_client_report(client, job_id)
    assert "Kết luận: inconclusive" in report
    assert "Kết luận: authentic" not in report
    assert "face_deepfake (bắt buộc)" in report
    assert "thiếu bước bắt buộc" in report


def real_client_report(client: TestClient, job_id: str) -> str:
    res = client.get(f"/v1/forensic/jobs/{job_id}/report")
    assert res.status_code == 200
    return res.text


# --- 4. lỗi giữa chừng -------------------------------------------------------------
def test_pipeline_nem_exception_thi_job_failed(monkeypatch, tmp_path):
    class Boom:
        def run(self, source, on_progress=None):
            on_progress("segments", 0, 7)
            raise RuntimeError("hỏng giữa chừng")

    monkeypatch.setattr(forensic_runner, "FileMediaSource", FakeSource)
    monkeypatch.setattr(forensic_runner, "build_pipeline", lambda root: Boom())
    with make_client(monkeypatch, tmp_path, "false") as client:
        _, job = _run(client)
    assert job["status"] == "failed"
    assert job["error"]["error_code"] == "analysis_failed"
    assert job["error"]["message"]
    assert job["verdict"] is None
    assert job["segments"] == []


def test_media_error_thi_job_failed_voi_ma_loi_cua_no(monkeypatch, tmp_path):
    def broken(path):
        raise MediaError("File hỏng", "corrupt_media")

    monkeypatch.setattr(forensic_runner, "FileMediaSource", broken)
    with make_client(monkeypatch, tmp_path, "false") as client:
        job_id, job = _run(client)
        assert job["status"] == "failed"
        assert job["error"] == {"error_code": "corrupt_media", "message": "File hỏng"}
        assert job["verdict"] is None
        with client.app.state.vericlue.database.sessions() as db:
            row = db.get(ForensicJobRow, job_id)
            assert row.status == "failed" and row.verdict is None
            assert row.file_sha256 == hashlib.sha256(DATA).hexdigest()


def test_pipeline_builder_loi_cung_la_failed(monkeypatch, tmp_path):
    def builder(root):
        raise ValueError("không dựng được pipeline")

    monkeypatch.setattr(forensic_runner, "FileMediaSource", FakeSource)
    monkeypatch.setattr(forensic_runner, "build_pipeline", builder)
    with make_client(monkeypatch, tmp_path, "false") as client:
        _, job = _run(client)
    assert job["status"] == "failed" and job["error"]["error_code"] == "analysis_failed"
    assert job["verdict"] is None


# --- 5. tiến độ --------------------------------------------------------------------
def test_tien_do_tang_dan_va_trang_thai_running_sang_done(monkeypatch, real_client):
    seen: list[tuple[str, str, int, int]] = []
    original = ForensicStore.set_progress

    def spy(self, job_id, stage, done, total):
        seen.append((self._row(job_id).status, stage, done, total))
        return original(self, job_id, stage, done, total)

    monkeypatch.setattr(ForensicStore, "set_progress", spy)
    _, job = _run(real_client)
    assert job["status"] == "done"
    assert seen, "phải có ít nhất một lần ghi tiến độ"
    assert {status for status, *_ in seen} == {"running"}  # ghi tiến độ khi đang running
    dones = [d for _, stage, d, _ in seen if stage == "segments"]
    assert dones == sorted(dones) and dones[0] == 0 and dones[-1] == 7
    assert len(set(dones)) == len(dones)  # tăng dần từng đoạn, không lặp
    assert all(total == 7 for *_, total in seen)
    assert [stage for _, stage, _, _ in seen][-2:] == ["provenance", "finalize"]


# --- 6. báo cáo thật ----------------------------------------------------------------
def test_bao_cao_that_day_du_va_verify(real_client):
    job_id, job = _run(real_client)
    res = real_client.get(f"/v1/forensic/jobs/{job_id}/report")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    html = res.text
    for needle in (
        "Chữ ký: MOCK",
        "Giới hạn",
        job["file_sha256"],
        "Kết luận: suspect",
        "Khoảng nghi giả",
        "3.5–8.5 s",
        "face_deepfake",
        "Kết quả theo đoạn",
        "0–3 s",
        "lipsync",
        "Bước không chạy",
    ):
        assert needle in html, needle
    assert html.count("<tr>") == len(job["segments"])
    digest = res.headers["X-VeriClue-Report-SHA256"]
    sig = res.headers["X-VeriClue-Signature"]
    assert hashlib.sha256(res.text.encode("utf-8")).hexdigest() == digest

    ok = real_client.post("/v1/forensic/verify", json={"report_sha256": digest, "signature": sig})
    assert ok.json() == {"valid": True}
    tampered = sig[:-1] + ("0" if sig[-1] != "0" else "1")
    bad = real_client.post(
        "/v1/forensic/verify", json={"report_sha256": digest, "signature": tampered}
    )
    assert bad.json() == {"valid": False}


# --- 7. đường mock không đổi ---------------------------------------------------------
def test_duong_mock_van_done_ngay_khong_vao_duong_that(client, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("đường mock không được chạy tác vụ nền thật")

    monkeypatch.setattr(forensic_runner, "FileMediaSource", forbidden)
    monkeypatch.setattr(forensic_runner, "build_pipeline", forbidden)
    created = _post(client)
    assert created.status_code == 200
    assert created.json()["status"] == "done"
    job = client.get(f"/v1/forensic/jobs/{created.json()['job_id']}").json()
    validate(job, "forensic", "ForensicJob")
    assert job["status"] == "done" and job["verdict"] == "authentic"
    assert job["progress"] is None and job["media"] is None
    assert len(job["segments"]) == 2


# --- 8. resolve_detectors ------------------------------------------------------------
class _Orchestrator:
    def __init__(self, loaded: dict[Module, object], failed: list[str]) -> None:
        self._loaded, self.failed_modules = loaded, failed

    def loaded_detector(self, module: Module):
        return self._loaded.get(module)


def _root(loaded: dict[Module, object], failed: list[str]):
    return SimpleNamespace(orchestrator=_Orchestrator(loaded, failed))


@pytest.mark.parametrize("lipsync_registered", [False, True])
def test_resolve_detectors_loai_mock_va_luon_bo_lipsync(monkeypatch, lipsync_registered):
    def fake_get_detector(module, mock=False):
        if module == Module.LIPSYNC and lipsync_registered:
            return object()
        raise NotImplementedError

    monkeypatch.setattr(forensic_runner, "get_detector", fake_get_detector)
    mock_face = FakeDetector(Module.FACE_DEEPFAKE, lambda i: 0.1, version="mock@0.1")
    real_voice = FakeDetector(Module.VOICE_SPOOF, lambda i: 0.1, version="gend@1")
    root = _root(
        {Module.FACE_DEEPFAKE: mock_face, Module.VOICE_SPOOF: real_voice},
        failed=["provenance"],
    )
    detectors, unavailable = forensic_runner.resolve_detectors(root)
    assert Module.FACE_DEEPFAKE not in detectors  # mock không phải bằng chứng giám định
    assert "giả lập" in unavailable[Module.FACE_DEEPFAKE]
    assert detectors[Module.VOICE_SPOOF] is real_voice
    assert Module.VOICE_SPOOF not in unavailable
    assert Module.PROVENANCE not in detectors and Module.PROVENANCE in unavailable
    assert Module.LIPSYNC not in detectors and unavailable[Module.LIPSYNC]
    if lipsync_registered:
        assert unavailable[Module.LIPSYNC] == forensic_runner.LIPSYNC_REASON_REGISTERED


# --- 9. không tồn tại -----------------------------------------------------------------
def test_job_khong_ton_tai_404(real_client):
    for suffix in ("", "/report"):
        res = real_client.get(f"/v1/forensic/jobs/job_none{suffix}")
        assert res.status_code == 404
        assert res.json()["error_code"] == "job_not_found"


# --- schema và báo cáo job chưa done ------------------------------------------------------
def test_get_job_hop_le_schema_khi_co_provenance(real_client):
    _, job = _run(real_client)
    assert job["provenance"] is not None
    validate(job, "forensic", "ForensicJob")


def test_khong_ky_bao_cao_cho_job_failed(monkeypatch, tmp_path):
    def broken(path):
        raise MediaError("File hỏng", "corrupt_media")

    monkeypatch.setattr(forensic_runner, "FileMediaSource", broken)
    with make_client(monkeypatch, tmp_path, "false") as client:
        job_id, job = _run(client)
        assert job["status"] == "failed"
        res = client.get(f"/v1/forensic/jobs/{job_id}/report")
    assert res.status_code == 409
    assert res.json()["error_code"] == "job_not_ready"


@pytest.mark.parametrize("status", ["queued", "running"])
def test_khong_ky_bao_cao_cho_job_chua_done(real_client, status):
    root = real_client.app.state.vericlue
    with root.transaction() as state:
        job = state.forensic._create_queued(DATA, "clip.mp4")
        if status == "running":
            state.forensic.mark_running(job.job_id)
    res = real_client.get(f"/v1/forensic/jobs/{job.job_id}/report")
    assert res.status_code == 409
    assert res.json()["error_code"] == "job_not_ready"


# --- 1b. API: trường null/tối thiểu vẫn hợp lệ schema -------------------------------------
def test_job_done_voi_has_audio_none_va_c2pa_unavailable_hop_le(monkeypatch, tmp_path):
    class NoAudioSeal:
        def probabilities(self, samples):
            raise RuntimeError("không quét được")

    provenance = ProvenanceDetector(
        audioseal=NoAudioSeal(),
        c2pa_reader=lambda path: {"status": "unavailable", "note": "Chưa cài c2pa-python"},
    )
    info = MediaInfo(kind="video", size_bytes=len(DATA), duration_s=DURATION, has_audio=None)
    monkeypatch.setattr(forensic_runner, "FileMediaSource", lambda path: FakeSource(path, info))
    monkeypatch.setattr(
        forensic_runner,
        "build_pipeline",
        lambda root: _pipeline(
            {
                Module.FACE_DEEPFAKE: _face(None),
                Module.VOICE_SPOOF: _voice(),
                Module.PROVENANCE: provenance,
            }
        ),
    )
    with make_client(monkeypatch, tmp_path, "false") as client:
        _, job = _run(client)  # _run đã validate theo schema
    assert job["status"] == "done"
    assert job["media"]["has_audio"] is None
    assert job["provenance"]["c2pa"]["status"] == "unavailable"
    assert job["provenance"]["c2pa"]["note"]
    assert job["provenance"]["watermark_detected"] is False


# --- 2. giới hạn hàng đợi ---------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_pending():
    forensic_runner._PENDING = 0
    yield
    forensic_runner._PENDING = 0


def _count_jobs(client: TestClient) -> int:
    with client.app.state.vericlue.database.sessions() as db:
        return len(db.scalars(select(ForensicJobRow)).all())


def test_hang_doi_day_thi_429_forensic_busy(monkeypatch, real_client):
    monkeypatch.setattr(forensic_runner, "MAX_PENDING_JOBS", 0)
    res = _post(real_client)
    assert res.status_code == 429
    assert res.json()["error_code"] == "forensic_busy"
    assert _count_jobs(real_client) == 0  # không tạo job, không rò chỗ
    assert forensic_runner._PENDING == 0


def test_chiem_cho_bang_reserve_slot_roi_tra_lai(monkeypatch, real_client):
    monkeypatch.setattr(forensic_runner, "MAX_PENDING_JOBS", 2)
    assert forensic_runner.reserve_slot() and forensic_runner.reserve_slot()
    assert not forensic_runner.reserve_slot()
    assert _post(real_client).status_code == 429
    forensic_runner.release_slot()
    assert _post(real_client).status_code == 200  # còn một chỗ → nhận
    assert forensic_runner._PENDING == 1  # job vừa chạy xong đã trả chỗ của nó


def _raise_media_error(path):
    raise MediaError("File hỏng", "corrupt_media")


def test_slot_duoc_tra_sau_job_xong_va_sau_job_loi(monkeypatch, real_client):
    assert _post(real_client).status_code == 200
    assert forensic_runner._PENDING == 0
    monkeypatch.setattr(forensic_runner, "FileMediaSource", _raise_media_error)
    _, job = _run(real_client)
    assert job["status"] == "failed"
    assert forensic_runner._PENDING == 0


def test_slot_duoc_tra_khi_create_nem_loi(monkeypatch, real_client):
    def boom(self, data, filename, scenario):
        raise RuntimeError("DB hỏng")

    monkeypatch.setattr(ForensicStore, "create", boom)
    with pytest.raises(RuntimeError):
        _post(real_client)
    assert forensic_runner._PENDING == 0


def test_duong_mock_khong_bi_hang_doi_chan(client, monkeypatch):
    monkeypatch.setattr(forensic_runner, "MAX_PENDING_JOBS", 0)
    res = _post(client)
    assert res.status_code == 200 and res.json()["status"] == "done"
    assert forensic_runner._PENDING == 0


# --- 3. khởi động lại ---------------------------------------------------------------------------
def test_khoi_dong_lai_danh_dau_job_do_dang_la_failed_interrupted(monkeypatch, tmp_path):
    monkeypatch.setattr(forensic_runner, "FileMediaSource", FakeSource)
    monkeypatch.setattr(
        forensic_runner,
        "build_pipeline",
        lambda root: _pipeline({Module.FACE_DEEPFAKE: _face(), Module.VOICE_SPOOF: _voice()}),
    )
    with make_client(monkeypatch, tmp_path, "false") as first:
        done_id, _ = _run(first)
        with first.app.state.vericlue.transaction() as state:
            queued = state.forensic._create_queued(DATA, "q.mp4").job_id
            running = state.forensic._create_queued(DATA, "r.mp4").job_id
            state.forensic.mark_running(running)
            legacy = state.forensic._create_queued(DATA, "m.mp4").job_id
            # giả lập job kiểu mock (không có mode "real"): không được đụng tới
            row = state.db.get(ForensicJobRow, legacy)
            row.payload = {k: v for k, v in row.payload.items() if k != "mode"}
    with make_client(monkeypatch, tmp_path, "false") as second:
        for job_id in (queued, running):
            job = second.get(f"/v1/forensic/jobs/{job_id}").json()
            validate(job, "forensic", "ForensicJob")
            assert job["status"] == "failed"
            assert job["verdict"] is None
            assert job["error"]["error_code"] == "interrupted"
        assert second.get(f"/v1/forensic/jobs/{legacy}").json()["status"] == "queued"
        done = second.get(f"/v1/forensic/jobs/{done_id}").json()
        assert done["status"] == "done" and done["verdict"] == "suspect"
        with second.app.state.vericlue.transaction() as state:
            assert state.forensic.fail_interrupted() == 0  # lặp lại không đổi gì thêm


# --- 4. giới hạn media ----------------------------------------------------------------------------
def _run_with_info(monkeypatch, tmp_path, info: MediaInfo) -> dict:
    monkeypatch.setattr(forensic_runner, "FileMediaSource", lambda path: FakeSource(path, info))
    monkeypatch.setattr(
        forensic_runner,
        "build_pipeline",
        lambda root: _pipeline({Module.FACE_DEEPFAKE: _face(None), Module.VOICE_SPOOF: _voice()}),
    )
    with make_client(monkeypatch, tmp_path, "false") as client:
        _, job = _run(client)
    return job


def test_file_qua_dai_thi_failed_media_too_long(monkeypatch, tmp_path):
    info = MediaInfo(kind="video", size_bytes=1, duration_s=601.0, has_audio=True)
    job = _run_with_info(monkeypatch, tmp_path, info)
    assert job["status"] == "failed" and job["verdict"] is None
    assert job["error"]["error_code"] == "media_too_long"


@pytest.mark.parametrize("duration", [None, 0.0])
def test_anh_tinh_hoac_thieu_thoi_luong_thi_failed_unsupported_media(
    monkeypatch, tmp_path, duration
):
    info = MediaInfo(kind="video", size_bytes=1, duration_s=duration)
    job = _run_with_info(monkeypatch, tmp_path, info)
    assert job["status"] == "failed" and job["verdict"] is None
    assert job["error"]["error_code"] == "unsupported_media"


class _FewFaces(FakeDetector):
    """Chỉ 2 lần gọi đầu có mặt; các đoạn còn lại không thấy khuôn mặt (not_applicable)."""

    def predict(self, inp):
        if self.calls not in (0, 1):
            self.calls += 1
            return ModuleResult(
                module=self.module,
                model_version=self.version,
                status=Status.NOT_APPLICABLE,
                error_code=ErrorCode.E_NO_FACE,
                latency_ms=1.0,
            )
        return super().predict(inp)


def test_do_phu_duoi_50_phan_tram_thi_inconclusive(monkeypatch, tmp_path):
    """Chỉ 2/7 đoạn phân tích được → không đủ độ phủ → không authentic."""
    face = _FewFaces(Module.FACE_DEEPFAKE, lambda i: 0.05)
    monkeypatch.setattr(forensic_runner, "FileMediaSource", FakeSource)
    monkeypatch.setattr(
        forensic_runner,
        "build_pipeline",
        lambda root: _pipeline({Module.FACE_DEEPFAKE: face, Module.VOICE_SPOOF: _voice()}),
    )
    with make_client(monkeypatch, tmp_path, "false") as client:
        _, job = _run(client)
    assert job["status"] == "done"
    assert job["verdict"] == "inconclusive"
    assert "2/7" in job["verdict_reason"]
    assert "chỉ" in job["verdict_reason"] and "đoạn phân tích được" in job["verdict_reason"]
    assert "bị lỗi" not in job["verdict_reason"]


LONG_VIDEO_NOTE = "Ngưỡng eKYC áp cho từng đoạn nên video dài dễ báo nghi ngờ nhầm."


def test_bao_cao_that_neu_gioi_han_nguong_ekyc_cho_tung_doan(real_client):
    assert LONG_VIDEO_NOTE in LIMITATIONS_VI
    job_id, _ = _run(real_client)
    html = real_client.get(f"/v1/forensic/jobs/{job_id}/report").text
    assert LONG_VIDEO_NOTE in html
    assert html.index("Giới hạn") < html.index(LONG_VIDEO_NOTE)


class _Scripted(FakeDetector):
    """Trạng thái từng lần gọi theo `script(i)`; chỉ lần `Status.OK` mới có xác suất."""

    def __init__(self, module: Module, script) -> None:
        super().__init__(module, lambda i: 0.05)
        self._script = script

    def predict(self, inp):
        status = self._script(self.calls)
        if status == Status.OK:
            return super().predict(inp)
        self.calls += 1
        code = {
            Status.NOT_APPLICABLE: ErrorCode.E_NO_FACE,
            Status.DEGRADED: ErrorCode.E_LOW_QUALITY,
            Status.ERROR: ErrorCode.E_INTERNAL,
        }[status]
        return ModuleResult(
            module=self.module,
            model_version=self.version,
            status=status,
            error_code=code,
            latency_ms=1.0,
        )


def _scripted_job(monkeypatch, tmp_path, script) -> dict:
    face = _Scripted(Module.FACE_DEEPFAKE, script)
    monkeypatch.setattr(forensic_runner, "FileMediaSource", FakeSource)
    monkeypatch.setattr(
        forensic_runner,
        "build_pipeline",
        lambda root: _pipeline({Module.FACE_DEEPFAKE: face, Module.VOICE_SPOOF: _voice()}),
    )
    with make_client(monkeypatch, tmp_path, "false") as client:
        _, job = _run(client)
    assert job["status"] == "done"
    return job


def test_degraded_va_khong_ap_dung_nhung_phu_tu_50_phan_tram_thi_authentic(monkeypatch, tmp_path):
    """7 đoạn: 2 degraded + 1 not_applicable + 4 ok (57%) và dưới ngưỡng → authentic."""
    plan = [Status.DEGRADED, Status.DEGRADED, Status.NOT_APPLICABLE] + [Status.OK] * 4
    job = _scripted_job(monkeypatch, tmp_path, lambda i: plan[i])
    assert job["verdict"] == "authentic"
    assert job["suspect_intervals"] == []
    statuses = [
        next(s for s in seg["signals"] if s["module"] == "face_deepfake")["status"]
        for seg in job["segments"]
    ]
    assert statuses.count("degraded") == 2 and statuses.count("not_applicable") == 1


def test_mot_doan_error_o_buoc_bat_buoc_thi_inconclusive_bi_loi(monkeypatch, tmp_path):
    plan = [Status.OK] * 7
    plan[3] = Status.ERROR
    job = _scripted_job(monkeypatch, tmp_path, lambda i: plan[i])
    assert job["verdict"] == "inconclusive"
    assert "face_deepfake" in job["verdict_reason"]
    assert "bị lỗi" in job["verdict_reason"]
