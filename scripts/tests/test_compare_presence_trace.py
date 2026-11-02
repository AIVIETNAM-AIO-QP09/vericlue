"""The join uses capture time and an exact attempt digest, never the latest session."""

import hashlib

import pytest

from scripts.compare_presence_trace import compare_observations, match_attempt
from vericlue_ml.presence.landmarks import FaceObservation


def test_attempt_join_rejects_unmatched_and_duplicate_challenges():
    trace = {"attempt_sha256": hashlib.sha256(b"correct").hexdigest()}
    correct = {"challenge": {"challenge_id": "correct"}, "token": "private"}
    other = {"challenge": {"challenge_id": "different"}}
    assert match_attempt(trace, [other, correct]) is correct
    with pytest.raises(ValueError):
        match_attempt(trace, [other])
    with pytest.raises(ValueError):
        match_attempt(trace, [correct, correct])


@pytest.mark.parametrize("state", ["Hold", "Completed"])
def test_pairs_use_capture_time_instead_of_delivery_time_and_do_not_fill_gaps(state):
    trace = {
        "events": [
            {"kind": "face", "at_ms": 2500, "frame_ms": 1000, "yaw": 25, "age_ms": 1500},
            {"kind": "face", "at_ms": 3000, "frame_ms": 1700, "yaw": 40, "age_ms": 1300},
            {"kind": "guidance", "at_ms": 1050, "frame_ms": 1000, "state": state},
        ]
    }
    rows = [
        FaceObservation(1000, 1, yaw_deg=60, pitch_deg=0, roll_deg=0),
        FaceObservation(2500, 1, yaw_deg=30, pitch_deg=0, roll_deg=0),
    ]
    report = compare_observations(trace, rows, {"gaze_points": []})
    assert report["pose_pairs"] == 1
    assert report["median_yaw_delta_deg"] == -35
    assert report["stale_client_samples"] == 2
    assert report["green_outside_server_pose"] == 1
    assert "events" not in report and "token" not in str(report)


def test_drawn_dot_is_compared_at_render_time_without_optimizing_a_lag():
    trace = {"events": [{"kind": "dot", "at_ms": 1500, "x": 0.5, "y": 0.5}]}
    dynamic = {
        "gaze_points": [{"at_ms": 1000, "x": 0.2, "y": 0.2}, {"at_ms": 2000, "x": 0.8, "y": 0.8}]
    }
    report = compare_observations(trace, [], dynamic)
    assert report["rendered_dot_samples"] == 1
    assert report["max_dot_plan_error"] == pytest.approx(0)


def test_retention_is_checked_before_decrypting():
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    from scripts.compare_presence_trace import open_retained_payload
    from vericlue_api.core.errors import ApiError

    opened = []
    row = SimpleNamespace(
        session_id="synthetic",
        payload={},
        status="review",
        created_at=datetime.now(UTC) - timedelta(days=3),
        decided_at=None,
        media_deleted_at=None,
    )
    settings = SimpleNamespace(
        product_mode="ekyc", media_ttl_unverified_hours=1, session_max_seconds=1800
    )
    privacy = SimpleNamespace(open_json=lambda *args: opened.append(True))
    with pytest.raises(ApiError):
        open_retained_payload(settings, privacy, row)
    assert opened == []


@pytest.mark.parametrize("constructor_error", [False, True])
def test_private_reader_gets_configured_models_and_always_releases_lease(constructor_error):
    from pathlib import Path
    from types import SimpleNamespace

    from scripts.compare_presence_trace import compare_private_video

    released = []
    lease = SimpleNamespace(release=lambda: released.append(True))
    privacy = SimpleNamespace(prepare=lambda *args: ({"video": Path("synthetic.mp4")}, lease))

    class Reader:
        def preload(self, *, models_dir):
            self.root = models_dir

        def extract(self, *args, **kwargs):
            assert getattr(self, "root", None) == Path("external-models")
            return []

        def close(self):
            pass

    def factory():
        if constructor_error:
            raise RuntimeError("synthetic constructor failure")
        return Reader()

    settings = SimpleNamespace(models_dir="external-models")
    payload = {
        "session_id": "synthetic",
        "video": "synthetic.mp4",
        "challenge": {
            "dynamic": {
                "gaze_points": [{"at_ms": 1000}],
                "head_start_at_ms": 8000,
                "head_duration_ms": 12000,
            }
        },
    }
    if constructor_error:
        with pytest.raises(RuntimeError):
            compare_private_video(settings, privacy, payload, {}, factory)
    else:
        compare_private_video(settings, privacy, payload, {}, factory)
    assert released == [True]


@pytest.mark.parametrize("failure", [None, "native", "database_close"])
def test_cli_closes_database_before_native_work_and_releases_detached_lease(
    tmp_path, monkeypatch, failure
):
    import json
    from types import SimpleNamespace

    from scripts import compare_presence_trace as script

    state = {"database_open": False, "released": 0, "disposed": False, "native_called": False}
    payload = {
        "session_id": "synthetic",
        "video": "synthetic.mp4",
        "challenge": {
            "challenge_id": "synthetic-challenge",
            "dynamic": {
                "gaze_points": [{"at_ms": 1000}],
                "head_start_at_ms": 8000,
                "head_duration_ms": 12000,
            },
        },
    }
    trace = {
        "schema_version": 1,
        "events": [],
        "attempt_sha256": hashlib.sha256(b"synthetic-challenge").hexdigest(),
    }
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(json.dumps(trace), encoding="utf-8")

    class DatabaseScope:
        def __enter__(self):
            state["database_open"] = True
            return SimpleNamespace(scalars=lambda _: [object()])

        def __exit__(self, *args):
            state["database_open"] = False
            if failure == "database_close":
                raise RuntimeError("synthetic database close failure")

    class Database:
        def __init__(self, _url):
            pass

        def sessions(self):
            return DatabaseScope()

        def dispose(self):
            state["disposed"] = True

    def release():
        state["released"] += 1

    def prepare(*args):
        assert state["database_open"]
        return {"video": tmp_path / "decoded-synthetic.mp4"}, SimpleNamespace(release=release)

    def preload(_reader, **kwargs):
        assert not state["database_open"], "Native work must not retain a database transaction"
        assert state["released"] == 0
        state["native_called"] = True
        if failure == "native":
            raise RuntimeError("synthetic native failure")

    def extract(_reader, *args, **kwargs):
        assert not state["database_open"] and state["released"] == 0
        return []

    monkeypatch.setattr(
        script,
        "Settings",
        lambda: SimpleNamespace(database_url="synthetic", models_dir="external-models"),
    )
    monkeypatch.setattr(script, "Database", Database)
    monkeypatch.setattr(script, "SessionPrivacy", lambda *args: SimpleNamespace(prepare=prepare))
    monkeypatch.setattr(script, "open_retained_payload", lambda *args: payload)
    monkeypatch.setattr(script.FaceObservationReader, "preload", preload)
    monkeypatch.setattr(script.FaceObservationReader, "extract", extract)
    monkeypatch.setattr(script.subprocess, "check_output", lambda *args, **kwargs: "synthetic")
    argv = [
        "--trace",
        str(trace_path),
        "--server-dir",
        str(tmp_path),
        "--output",
        str(tmp_path / "report.json"),
    ]
    if failure:
        with pytest.raises(RuntimeError, match="synthetic"):
            script.main(argv)
    else:
        assert script.main(argv) == 0
    assert state["released"] == 1
    assert state["disposed"]
    assert state["native_called"] == (failure != "database_close")
