"""Fixed demo cutoffs retain boundary failures and evidence/version guards."""

import pytest
from test_manual_voice import raw_voice

from vericlue_ml.common import manual_demo
from vericlue_ml.common.result import ModuleResult


@pytest.mark.parametrize(
    "module,score,accepted",
    [
        ("face_pad", 0.70, True),
        ("face_pad", 0.700001, False),
        ("face_deepfake", 0.95, True),
        ("face_deepfake", 0.950001, False),
    ],
)
def test_fixed_attack_boundaries(module, score, accepted):
    policy = manual_demo.PHONE_DEMO_FIXED_V1
    raw = ModuleResult(
        module=module, model_version="real-backend", status="ok", score=score, latency_ms=0
    )
    assert policy.accepts_attack(raw) is accepted
    for status in ("error", "degraded"):
        assert not policy.accepts_attack(raw.model_copy(update={"status": status}))


@pytest.mark.parametrize(
    "kind,score,accepted",
    [
        ("spoof", 0.70, True),
        ("spoof", 0.700001, False),
        ("lipsync", 0.60, True),
        ("lipsync", 0.600001, False),
    ],
)
def test_fixed_voice_boundaries_keep_version_binding(kind, score, accepted):
    policy = manual_demo.PHONE_DEMO_FIXED_V1
    raw = raw_voice(kind, score)
    result = policy.apply_voice(raw)
    accepts = policy.accepts_voice_spoof if kind == "spoof" else policy.accepts_lipsync
    assert accepts(result) is accepted
    assert result.prob_attack is None and result.quality["calibrated"] is False
    assert not accepts(result.model_copy(update={"model_version": raw.model_version}))
    assert not accepts(manual_demo.ManualDemoThresholds().apply_voice(raw))


@pytest.mark.parametrize("kind", ["spoof", "lipsync"])
@pytest.mark.parametrize("fault", ["error", "degraded", "missing_evidence", "bad_version"])
def test_fixed_voice_policy_does_not_promote_failures(kind, fault):
    policy = manual_demo.PHONE_DEMO_FIXED_V1
    raw = raw_voice(kind)
    if fault in {"error", "degraded"}:
        raw.status = fault
    elif fault == "missing_evidence":
        raw.evidence = []
    else:
        raw.model_version = "other-backend"
    assert policy.apply_voice(raw).gate != "pass"


def test_fixed_lipsync_keeps_splice_guard():
    raw = raw_voice("lipsync", 0.01)
    raw.evidence[0].value = 1
    assert manual_demo.PHONE_DEMO_FIXED_V1.apply_voice(raw).gate != "pass"
