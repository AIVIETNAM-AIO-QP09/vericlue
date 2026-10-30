from __future__ import annotations

import base64
import json
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _rel in ("services/api/src", "ml/src", "."):
    _p = str(REPO_ROOT / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scripts.diagnose_presence_session as diag  # noqa: E402
from vericlue_api.core.config import Settings  # noqa: E402
from vericlue_api.db.database import Database  # noqa: E402
from vericlue_api.db.models import Base, SessionRow  # noqa: E402
from vericlue_api.services.session_privacy import SessionPrivacy  # noqa: E402
from vericlue_ml.common.calibration import CalibrationStore, identity  # noqa: E402


def _make_settings(tmp_path: Path) -> Settings:
    master_key = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        media_dir=str(media_dir),
        session_privacy=True,
        session_master_key=master_key,
        account_enrollment=False,
        identity_face_calibration=None,
        identity_consistency_calibration=None,
    )


def test_diagnostic_report_redacts_private_payload_and_keeps_failures(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    db = Database(settings.database_url)
    Base.metadata.create_all(db.engine)

    calibrators_dir = tmp_path / "calibrators"
    store = CalibrationStore(root=calibrators_dir)
    # Save an IdentityCalibrator (provisional=True) for face_pad to verify provisional is NOT ready.
    pad_ver = (
        "fs-vfm-vit-l-fas@59f7b50a+scrfd@bfcc7d48+scrfd128-align224-rgb-v1"
        "+headturn-3views-max-v1+session-video-v2"
    )
    store.save(identity(module="face_pad", model_version=pad_ver, commit="a" * 40))

    session_id = "ses_1122334455667788"
    secret_token = "tok_super_secret_bearer_value_999"
    secret_cccd = "001099123456"
    secret_name = "NGUYEN VAN SECRET"
    secret_phone_hmac = "hmac_phone_secret_value_abc"
    secret_video_path = str(Path(settings.media_dir) / session_id / "video.mp4")

    raw_payload = {
        "session_id": session_id,
        "token": secret_token,
        "token_hash": "hash_secret_123",
        "phone_hmac": secret_phone_hmac,
        "id_number_hmac": "hmac_id_secret_456",
        "sensitive_id_number": secret_cccd,
        "sensitive_confirmed_id_number": secret_cccd,
        "id_fields": {"id_number": secret_cccd, "full_name": secret_name},
        "id_confirmed_fields": {"id_number": secret_cccd, "full_name": secret_name},
        "id_front": str(tmp_path / "id_front.jpg"),
        "id_back": str(tmp_path / "id_back.jpg"),
        "images": [str(tmp_path / "still.jpg")],
        "video": secret_video_path,
        "challenge": {
            "challenge_id": "ch_test",
            "baseline_ms": 1000,
            "color_sequence": [],
            "dynamic": {
                "version": 2,
                "frontal_capture_at_ms": 500,
                "head_start_at_ms": 13500,
                "head_duration_ms": 12000,
                "head_turns": ["right", "left", "center"],
                "voice_start_at_ms": 25500,
                "gaze_points": [{"at_ms": 6000, "x": 0.2, "y": 0.5}],
            },
        },
        "results": {
            "gaze_tracking": {
                "module": "gaze_tracking",
                "model_version": "gaze-rules@0.2+face-landmarker-f16-1",
                "status": "ok",
                "gate": "fail",
                "error_code": None,
                "score": 0.409,
                "prob_attack": None,
                "quality": {"provisional": True},
                "evidence": [
                    {"type": "text", "name": "gaze_reason", "value": "trajectory_mismatch"},
                    {
                        "type": "scalar",
                        "name": "gaze_diagnostics",
                        "value": {
                            "valid_samples": 70.0,
                            "coverage": 0.9859,
                            "head_deviation_deg": 1.28,
                            "iris_span_x": 0.0503,
                            "iris_span_y": 0.0342,
                            "correlation_x": 0.4085,
                            "correlation_y": 0.8548,
                            "lag_ms": 100.0,
                        },
                    },
                ],
                "latency_ms": 12.0,
            },
            "head_turn": {
                "module": "head_turn",
                "model_version": "head-turn-rules@0.1+face-landmarker-f16-1",
                "status": "degraded",
                "gate": "unclear",
                "error_code": None,
                "score": None,
                "prob_attack": None,
                "quality": {"provisional": True},
                "evidence": [
                    {"type": "text", "name": "head_reason", "value": "incomplete_time_window"}
                ],
                "latency_ms": 15.0,
            },
            "face_pad": {
                "module": "face_pad",
                "model_version": pad_ver,
                "status": "degraded",
                "gate": "unclear",
                "error_code": "E_LOW_QUALITY",
                "score": None,
                "prob_attack": None,
                "quality": {},
                "evidence": [],
                "latency_ms": 5.0,
            },
        },
    }

    with db.sessions() as orm:
        privacy = SessionPrivacy(settings, orm)
        sealed = privacy.seal_json(session_id, "session", raw_payload)
        orm.add(
            SessionRow(
                session_id=session_id,
                status="review",
                created_at=datetime(2026, 10, 30, 14, 39, 35, tzinfo=UTC),
                payload=sealed,
            )
        )
        orm.commit()

    out_file = tmp_path / "report.json"
    rc = diag.main(
        [
            "--session-id",
            session_id,
            "--calibrators-dir",
            str(calibrators_dir),
            "--output",
            str(out_file),
            "--no-video-extract",
        ],
        settings=settings,
    )
    assert rc == 0
    report_text = out_file.read_text(encoding="utf-8")
    for forbidden in (
        secret_token,
        "hash_secret_123",
        secret_cccd,
        secret_name,
        secret_phone_hmac,
        "hmac_id_secret_456",
        secret_video_path,
        "id_front.jpg",
        "still.jpg",
    ):
        assert forbidden not in report_text

    report = json.loads(report_text)
    assert report["schema_version"] == 1
    assert len(report["sessions"]) == 1
    sess = report["sessions"][0]
    assert sess["status"] == "review"
    assert sess["protocol"] == 2
    assert sess["head_duration_ms"] == 12000
    assert sess["head_turns"] == ["right", "left", "center"]

    mods = {m["module"]: m for m in sess["modules"]}
    assert mods["gaze_tracking"]["status"] == "ok"
    assert mods["gaze_tracking"]["gate"] == "fail"
    assert mods["gaze_tracking"]["reason"] == ["trajectory_mismatch"]
    assert mods["gaze_tracking"]["diagnostics"]["correlation_x"] == 0.4085
    assert mods["head_turn"]["status"] == "degraded"
    assert mods["head_turn"]["gate"] == "unclear"
    assert mods["head_turn"]["reason"] == ["incomplete_time_window"]
    assert mods["face_pad"]["status"] == "degraded"
    assert mods["face_pad"]["error_code"] == "E_LOW_QUALITY"

    readiness = report["artifact_readiness"]
    assert readiness["account_enrollment"] is False
    assert readiness["identity_face_calibration"] == "unavailable"
    assert readiness["identity_consistency_calibration"] == "unavailable"
    cal_map = {c["module"]: c for c in readiness["calibrators"]}
    assert cal_map["face_pad"]["artifact_state"] == "provisional_rejected"
    assert cal_map["face_deepfake"]["artifact_state"] == "unavailable"
    db.dispose()


def test_diagnostic_media_lease_released_on_reader_failure(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    db = Database(settings.database_url)
    Base.metadata.create_all(db.engine)

    session_active = "ses_aaaa1111bbbb2222"
    session_expired = "ses_cccc3333dddd4444"
    media_root = Path(settings.media_dir)
    sess_dir = media_root / session_active
    sess_dir.mkdir(parents=True, exist_ok=True)
    video_file = sess_dir / "video.mp4"

    def make_payload(sid: str, vpath: str | None) -> dict:
        return {
            "session_id": sid,
            "token_hash": "h",
            "video": vpath,
            "challenge": {
                "challenge_id": "ch",
                "baseline_ms": 1000,
                "color_sequence": [],
                "dynamic": {
                    "version": 2,
                    "frontal_capture_at_ms": 500,
                    "head_start_at_ms": 13500,
                    "head_duration_ms": 12000,
                    "head_turns": ["right", "left", "center"],
                    "voice_start_at_ms": 25500,
                    "gaze_points": [],
                },
            },
            "results": {},
        }

    with db.sessions() as orm:
        privacy = SessionPrivacy(settings, orm)
        sealed_active = privacy.seal_json(
            session_active, "session", make_payload(session_active, str(video_file))
        )
        video_file.write_bytes(
            privacy.seal_media(session_active, "video.mp4", b"not-a-real-mp4-stream")
        )
        orm.add(SessionRow(session_id=session_active, status="review", payload=sealed_active))

        sealed_expired = privacy.seal_json(
            session_expired, "session", make_payload(session_expired, None)
        )
        orm.add(SessionRow(session_id=session_expired, status="review", payload=sealed_expired))
        orm.flush()
        privacy.destroy(session_expired)
        orm.commit()

    class FailingReader:
        def extract(self, video_path: Path, *, start_ms: float = 0.0, end_ms: float | None = None):
            assert video_path.exists()
            raise RuntimeError("synthetic reader failure")

    report = diag.build_diagnostic_report(
        settings=settings,
        session_ids=[session_active, session_expired],
        calibrators_dir=tmp_path / "calibrators",
        reader_factory=FailingReader,
    )
    decoded_dir = media_root / "_decoded"
    if decoded_dir.exists():
        assert list(decoded_dir.glob("lease-*")) == []

    by_id = {item["session_index"]: item for item in report["sessions"]}
    assert by_id[0]["head_observations"]["state"] == "reader_error"
    assert by_id[1]["state"] == "unavailable"
    db.dispose()
