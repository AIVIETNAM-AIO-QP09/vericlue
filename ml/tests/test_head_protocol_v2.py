"""Longer capture schedule regressions, entirely synthetic and never accuracy evidence."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_gaze import inputs as gaze_input
from test_head_turn import inputs
from test_session_attack import fixture_detector
from test_session_calibration import fake_runtime, write_manifest

from vericlue_ml.common.result import Gate, Status
from vericlue_ml.eval import session_calibration as sc
from vericlue_ml.face.session_attack import SessionAttackDetector
from vericlue_ml.presence.gaze import parse_plan
from vericlue_ml.presence.head_turn import evaluate_head_turn, parse_head_plan
from vericlue_ml.presence.landmarks import FaceObservation, LandmarkError


def request(protocol=2):
    inp = inputs()
    inp.video = Path("synthetic.mp4")
    inp.metadata["expected_challenge"]["dynamic"].update(
        version=protocol, head_duration_ms={1: 6000, 2: 12000}[protocol]
    )
    return inp


def trace():
    return [
        FaceObservation(
            float(t),
            1,
            yaw_deg=28 if 12500 <= t < 16000 else -28 if 16500 <= t < 20000 else 0,
            pitch_deg=0,
            roll_deg=0,
        )
        for t in range(11500, 24001, 100)
    ]


def test_long_head_trace_requires_motion_and_complete_window():
    plan = parse_head_plan(request())
    assert plan.end_ms == 24000
    assert evaluate_head_turn(trace(), plan).gate == Gate.PASS
    assert (
        evaluate_head_turn([replace(r, yaw_deg=-r.yaw_deg) for r in trace()], plan).gate
        == Gate.FAIL
    )
    assert evaluate_head_turn(trace()[:-5], plan).status == Status.DEGRADED
    assert evaluate_head_turn([replace(r, yaw_deg=0) for r in trace()], plan).gate == Gate.FAIL


@pytest.mark.parametrize(
    "patch",
    [
        {"version": 1},
        {"head_duration_ms": 6000},
        {"version": True},
        {"head_start_at_ms": 19000},
        {"version": 3},
    ],
)
def test_head_protocol_rejects_crossed_or_overlong_timing(patch):
    inp = request()
    inp.metadata["expected_challenge"]["dynamic"].update(patch)
    with pytest.raises(LandmarkError):
        parse_head_plan(inp)


def test_gaze_v2_retains_binding_checks():
    inp = gaze_input()
    inp.metadata["expected_challenge"]["dynamic"]["version"] = 2
    assert len(parse_plan(inp).times) == 8
    inp.session_id = "ses_other"
    with pytest.raises(LandmarkError):
        parse_plan(inp)


def test_attack_calibration_isolated_across_protocols_and_threads(monkeypatch, tmp_path):
    backend, store, old = fixture_detector(monkeypatch, tmp_path)
    store.save(old)
    current = old.model_copy(update={"model_version": old.model_version.replace("-v1", "-v2")})
    store.save(current)
    detector = SessionAttackDetector(backend, SimpleNamespace(), store)
    protocols = [1, 2, 1, 2] * 8
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda v: detector.predict(request(v)), protocols))
    assert detector.version == old.model_version
    for v, result in zip(protocols, results, strict=True):
        assert result.model_version.endswith(f"+session-video-v{v}")
        assert result.status == Status.OK and result.prob_attack is not None


@pytest.mark.parametrize("kind", ["missing", "provisional", "backend-error"])
def test_v2_cannot_borrow_v1_artifact(monkeypatch, tmp_path, kind):
    backend, store, old = fixture_detector(
        monkeypatch, tmp_path, status="error" if kind == "backend-error" else "ok"
    )
    store.save(old)
    if kind == "provisional":
        store.save(
            old.model_copy(
                update={
                    "model_version": old.model_version.replace("-v1", "-v2"),
                    "provisional": True,
                }
            )
        )
    result = SessionAttackDetector(backend, SimpleNamespace(), store).predict(request())
    assert result.model_version.endswith("+session-video-v2")
    assert result.status != Status.OK and result.prob_attack is None


def test_v2_failure_keeps_result_protocol(monkeypatch, tmp_path):
    from vericlue_ml.common.result import ErrorCode
    from vericlue_ml.face import session_attack

    backend, store, _ = fixture_detector(monkeypatch, tmp_path)

    def fail(*_):
        raise LandmarkError(ErrorCode.E_DECODE)

    monkeypatch.setattr(session_attack, "session_views", fail)
    result = SessionAttackDetector(backend, SimpleNamespace(), store).predict(request())
    assert result.model_version.endswith("+session-video-v2")
    assert result.error_code == "E_DECODE"


def rewrite_protocol(root, indexes):
    for i in indexes:
        p = root / f"{i}.json"
        value = json.loads(p.read_text())
        value["challenge"]["dynamic"].update(version=2, head_duration_ms=12000)
        p.write_text(json.dumps(value))


def test_collect_fit_v2_keeps_exact_version(monkeypatch, tmp_path):
    path, _ = write_manifest(tmp_path)
    rewrite_protocol(tmp_path, range(8))
    fake_runtime(monkeypatch)
    report = tmp_path / "report.json"
    result = sc.collect(path, tmp_path, tmp_path / "models", "face_pad", report)
    assert result["model_version"] == "synthetic-views+session-video-v2"
    fitted = sc.fit_report(report, tmp_path / "calibrators", n_splits=3)
    assert fitted["model_version"] == result["model_version"]


def test_collect_rejects_mixed_protocol_before_model_loading(monkeypatch, tmp_path):
    path, _ = write_manifest(tmp_path)
    rewrite_protocol(tmp_path, [0])

    def unexpected(*_):
        pytest.fail("Mixed protocol must be rejected before model load")

    monkeypatch.setattr(sc, "make_runtime", unexpected)
    with pytest.raises(ValueError):
        sc.collect(path, tmp_path, tmp_path / "models", "face_pad", tmp_path / "out.json")


def test_video_match_passes_local_v2_version_to_identity_backend(monkeypatch):
    import numpy as np
    from test_video_frontal_match import inputs as match_input
    from test_video_frontal_match import setup

    from vericlue_ml.common.result import ModuleResult
    from vericlue_ml.face import video_match

    matcher, _ = setup(monkeypatch)
    matcher.with_consistency = True
    inp = match_input()
    inp.metadata["expected_challenge"]["dynamic"].update(
        version=2, head_start_at_ms=12000, head_duration_ms=12000
    )
    frames = {k: np.full((112, 112, 3), 42, np.uint8) for k in ("front", "left", "right")}
    monkeypatch.setattr(video_match, "session_views", lambda *_: (frames, "a" * 64))

    def score(inp, frames, *, result_version=None):
        assert result_version == video_match.VIDEO_MATCH_VERSION + "+head12s-v2"
        return ModuleResult(
            module="face_match", model_version=result_version, status="degraded", latency_ms=0
        )

    monkeypatch.setattr(matcher, "predict_frames", score)
    result = matcher.predict(inp)
    assert result.model_version.endswith("+head12s-v2")
    assert result.status == Status.DEGRADED
    assert matcher.version == video_match.VIDEO_MATCH_VERSION


def test_face_match_does_not_apply_threshold_of_another_result_protocol(tmp_path):
    from test_face_match import setup_detector

    matcher, inp = setup_detector(tmp_path, threshold=True)
    matcher._supported_versions = lambda: (matcher.version, matcher.version + "+head12s-v2")
    result = matcher.predict_frames(
        inp,
        {"front": __import__("numpy").full((112, 112, 3), 99, dtype="uint8")},
        result_version=matcher.version + "+head12s-v2",
    )
    assert result.prob_attack is None
    assert result.gate != Gate.PASS
    assert result.status == Status.DEGRADED


def test_face_match_accepts_only_exact_new_threshold_and_consistency(tmp_path):
    import numpy as np
    from test_face_match import artifact, setup_detector

    matcher, inp = setup_detector(tmp_path)
    version = matcher.version + "+head12s-v2"
    matcher._supported_versions = lambda: (matcher.version, version)
    matcher.calibration_path = artifact(tmp_path, model_version=version)
    matcher.preload()
    matcher._consistency_threshold = matcher._threshold.model_copy(
        update={"model_version": matcher.version + "+view-consistency-v1"}
    )
    frames = {
        k: np.full((112, 112, 3), 99 + i, dtype="uint8")
        for i, k in enumerate(("front", "left", "right"))
    }
    result = matcher.predict_frames(inp, frames, result_version=version)
    assert result.status == Status.OK and result.gate == Gate.PASS
    assert result.model_version == version
    assert result.quality["consistency_verified"] is False
