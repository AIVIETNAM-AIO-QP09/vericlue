"""Adaptive measurements never inherit a timed protocol's fitted evidence."""

import json
from types import SimpleNamespace

import pytest
from test_enrolled_match import setup, threshold
from test_head_protocol_v2 import request
from test_session_attack import fixture_detector
from test_video_identity import Reader

from vericlue_ml.common.manual_demo import ManualDemoThresholds
from vericlue_ml.common.result import Gate, Status
from vericlue_ml.face.enrolled import RECOVERY_MATCH_VERSION, match_enrolled
from vericlue_ml.face.match import MatchThreshold
from vericlue_ml.face.session_attack import SessionAttackDetector
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION
from vericlue_ml.presence.head_protocol import head_protocol_version, session_model_version
from vericlue_ml.presence.head_turn import HEAD_VERSION, HeadTurnDetector


def adaptive_request():
    inp = request()
    inp.metadata["expected_challenge"]["dynamic"].update(
        head_mode="adaptive", head_timeout_ms=18000
    )
    return inp


def test_adaptive_measurement_protocol_is_distinct_from_nominal_wire_v2():
    inp = adaptive_request()
    assert inp.metadata["expected_challenge"]["dynamic"]["version"] == 2
    assert head_protocol_version(inp) == 3
    assert session_model_version("synthetic", 3) == "synthetic+session-video-v3-adaptive"


def test_head_result_identifies_adaptive_rule_path():
    result = HeadTurnDetector(Reader()).predict(adaptive_request())
    assert result.model_version == HEAD_VERSION + "+adaptive-v1"
    assert result.status == Status.OK and result.gate == Gate.PASS


def test_adaptive_cannot_borrow_fitted_timed_v2_artifact(monkeypatch, tmp_path):
    backend, store, old = fixture_detector(monkeypatch, tmp_path)
    store.save(old.model_copy(update={"model_version": old.model_version.replace("-v1", "-v2")}))
    result = SessionAttackDetector(backend, SimpleNamespace(), store).predict(adaptive_request())
    assert result.model_version.endswith("+session-video-v3-adaptive")
    assert result.status == Status.DEGRADED
    assert result.gate == Gate.UNCLEAR and result.prob_attack is None


def test_adaptive_manual_demo_preserves_protocol_and_policy_binding(monkeypatch, tmp_path):
    backend, store, _ = fixture_detector(monkeypatch, tmp_path)
    policy = ManualDemoThresholds()
    result = SessionAttackDetector(backend, SimpleNamespace(), store, manual_demo=policy).predict(
        adaptive_request()
    )
    assert result.model_version.endswith("+session-video-v3-adaptive" + policy.version_suffix)
    assert result.status == Status.OK and result.gate == Gate.PASS
    assert result.quality["demo_policy_id"] == policy.policy_id
    assert result.prob_attack is None


def test_adaptive_recovery_cannot_reuse_timed_identity_thresholds(monkeypatch, tmp_path):
    matcher, inp, template, artifact, _, _ = setup(monkeypatch, tmp_path, recovery=True)
    inp.metadata["expected_challenge"]["dynamic"].update(
        version=2, head_duration_ms=12000, head_mode="adaptive", head_timeout_ms=18000
    )
    artifact.write_text(json.dumps(threshold(RECOVERY_MATCH_VERSION + "+head12s-v2")))
    matcher._consistency_threshold = MatchThreshold(
        **threshold(VIDEO_MATCH_VERSION + "+head12s-v2+view-consistency-v1")
    )
    result = match_enrolled(matcher, inp, template, artifact)
    assert result.status != Status.OK and result.gate == Gate.UNCLEAR


@pytest.mark.parametrize("same_person", [False, True])
def test_adaptive_recovery_compares_existing_embedding_under_its_own_protocol(
    monkeypatch, tmp_path, same_person
):
    matcher, inp, template, artifact, _, calls = setup(monkeypatch, tmp_path, recovery=True)
    inp.metadata["expected_challenge"]["dynamic"].update(
        version=2, head_duration_ms=12000, head_mode="adaptive", head_timeout_ms=18000
    )
    adaptive_version = RECOVERY_MATCH_VERSION + "+head-adaptive-v1"
    artifact.write_text(json.dumps(threshold(adaptive_version)))
    matcher._consistency_threshold = MatchThreshold(
        **threshold(VIDEO_MATCH_VERSION + "+head-adaptive-v1+view-consistency-v1")
    )
    if not same_person:
        template = template.model_copy(update={"embedding": (-1.0, *([0.0] * 511))})
    result = match_enrolled(matcher, inp, template, artifact)
    assert template.model_version == VIDEO_MATCH_VERSION
    assert result.model_version == adaptive_version
    assert result.status == Status.OK
    assert result.gate == (Gate.PASS if same_person else Gate.FAIL)
    assert calls == [{"front", "left", "right"}]


def test_adaptive_onboarding_passes_distinct_version_to_identity_backend(monkeypatch):
    import numpy as np
    from test_video_frontal_match import inputs as match_input
    from test_video_frontal_match import setup as setup_video

    from vericlue_ml.common.result import ModuleResult
    from vericlue_ml.face import video_match

    matcher, _ = setup_video(monkeypatch)
    matcher.with_consistency = True
    inp = match_input()
    inp.metadata["expected_challenge"]["dynamic"].update(
        version=2,
        head_start_at_ms=12000,
        head_duration_ms=12000,
        head_mode="adaptive",
        head_timeout_ms=18000,
    )
    frames = {key: np.full((112, 112, 3), 42, np.uint8) for key in ("front", "left", "right")}
    monkeypatch.setattr(video_match, "session_views", lambda *_: (frames, "a" * 64))

    def score(inp, frames, *, result_version=None):
        assert result_version == VIDEO_MATCH_VERSION + "+head-adaptive-v1"
        return ModuleResult(
            module="face_match", model_version=result_version, status="degraded", latency_ms=0
        )

    monkeypatch.setattr(matcher, "predict_frames", score)
    result = matcher.predict(inp)
    assert result.model_version == VIDEO_MATCH_VERSION + "+head-adaptive-v1"
    assert result.status == Status.DEGRADED and result.gate != Gate.PASS
