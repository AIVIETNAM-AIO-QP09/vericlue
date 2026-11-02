"""Manual gates use successful raw backends, never diagnostic or probability shortcuts."""

import json
from pathlib import Path

import jsonschema
import pytest

from vericlue_ml.common.manual_demo import ManualDemoThresholds
from vericlue_ml.common.result import Evidence, ModuleResult
from vericlue_ml.voice.antispoof import AntiDeepfakeDetector
from vericlue_ml.voice.syncnet import SyncNetDetector


def raw_voice(kind="spoof", score=0.2):
    if kind == "spoof":
        return ModuleResult(
            module="voice_spoof",
            model_version=AntiDeepfakeDetector().version,
            status="ok",
            score=score,
            latency_ms=0,
            quality={
                "duration_s": 4.0,
                "speech_duration_s": 4.0,
                "trim_start_s": 0.0,
                "n_windows": 1,
            },
            evidence=[
                Evidence(
                    type="timeseries",
                    name="window_scores",
                    value=[{"start_s": 0.0, "end_s": 4.0, "score": score, "logits": [0.0, 1.0]}],
                )
            ],
        )
    return ModuleResult(
        module="lipsync",
        model_version=SyncNetDetector().version,
        status="ok",
        score=score,
        latency_ms=0,
        evidence=[
            Evidence(type="scalar", name=name, value=value)
            for name, value in (
                ("splice_flags", 0),
                ("av_offset_ms", 0.0),
                ("sync_confidence", 0.8),
                ("best_offset_confidence", 0.8),
            )
        ],
    )


@pytest.mark.parametrize("kind", ["spoof", "lipsync"])
@pytest.mark.parametrize(
    "score,gate", [(0.0, "pass"), (0.5, "pass"), (0.50001, "fail"), (1.0, "fail")]
)
def test_raw_threshold_boundary_and_policy_binding(kind, score, gate):
    policy = ManualDemoThresholds()
    result = policy.apply_voice(raw_voice(kind, score))
    assert result.status == "ok" and result.gate == gate
    assert result.prob_attack is None
    assert result.quality["calibrated"] is False
    assert result.quality["demo_policy_id"] == policy.policy_id
    assert result.model_version == raw_voice(kind).model_version + policy.version_suffix
    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "packages/contracts/schemas/module_result.schema.json"
        ).read_text(encoding="utf-8")
    )
    jsonschema.validate(result.to_contract(), schema)
    accepts = policy.accepts_voice_spoof if kind == "spoof" else policy.accepts_lipsync
    assert accepts(result) == (gate == "pass")
    assert not accepts(result.model_copy(update={"prob_attack": 0.01}))
    assert not accepts(result.model_copy(update={"quality": {}}))
    changed = ManualDemoThresholds(spoof_max=0.4, lipsync_max=0.4)
    assert not (
        changed.accepts_voice_spoof(result) if kind == "spoof" else changed.accepts_lipsync(result)
    )


@pytest.mark.parametrize("kind", ["spoof", "lipsync"])
@pytest.mark.parametrize(
    "fault",
    ["degraded", "error", "not_applicable", "missing", "nan", "version", "diagnostic", "mock"],
)
def test_raw_failures_cannot_be_promoted(kind, fault):
    policy = ManualDemoThresholds()
    raw = raw_voice(kind)
    if fault in {"degraded", "error", "not_applicable"}:
        raw.status = fault
    elif fault == "missing":
        raw.evidence = []
    elif fault == "nan":
        raw.score = float("nan")
    elif fault in {"version", "mock"}:
        raw.model_version = "mock@1" if fault == "mock" else "other"
    else:
        raw.quality["diagnostic_only"] = True
    result = policy.apply_voice(raw)
    assert result.gate != "pass"
    if fault in {"degraded", "error", "not_applicable"}:
        assert result.status == fault


@pytest.mark.parametrize("value", [1, -1, True, "0", float("nan"), 0.5])
def test_lipsync_requires_exact_zero_splice_count(value):
    raw = raw_voice("lipsync")
    raw.evidence[0].value = value
    assert ManualDemoThresholds().apply_voice(raw).gate != "pass"


@pytest.mark.parametrize("artifact", ["valid", "stale", "missing", "already_loaded"])
def test_manual_continuity_precedes_configured_calibration(monkeypatch, tmp_path, artifact):
    from test_face_continuity import fixture

    model, inp, _, _ = fixture(monkeypatch, tmp_path, threshold=0.9, similarities=(0.5, 0.5, 0.5))
    if artifact == "already_loaded":
        model.preload()
    policy = ManualDemoThresholds()
    model.matcher.manual_demo = policy
    if artifact == "stale":
        model.calibration_path.write_text('{"model_version":"stale"}')
    elif artifact == "missing":
        model.calibration_path = tmp_path / "missing.json"
    approved = inp.metadata["face_reference_result"]
    approved["model_version"] += policy.version_suffix
    approved["quality"] = {"manual_demo": True, "demo_policy_id": policy.policy_id}
    result = model.predict(inp)
    assert result.status == "ok" and result.gate == "pass"
    assert result.quality["calibrated"] is False


@pytest.mark.parametrize("field", ["spoof_max", "lipsync_max"])
@pytest.mark.parametrize("value", [0, 1, float("nan"), float("inf")])
def test_invalid_voice_policy_cannot_be_constructed(field, value):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ManualDemoThresholds(**{field: value})


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate",
        "missing_confidence",
        "nonfinite_confidence",
        "offset_range",
        "logits",
        "coverage",
        "duration",
    ],
)
def test_raw_evidence_integrity(fault):
    kind = "spoof" if fault in {"logits", "coverage", "duration"} else "lipsync"
    raw = raw_voice(kind)
    if fault == "duplicate":
        raw.evidence.append(raw.evidence[0].model_copy())
    elif fault == "missing_confidence":
        raw.evidence.pop(2)
    elif fault == "nonfinite_confidence":
        raw.evidence[2].value = float("nan")
    elif fault == "offset_range":
        raw.evidence[1].value = 601
    elif fault == "logits":
        raw.evidence[0].value[0]["logits"] = [0.0, float("nan")]
    elif fault == "coverage":
        raw.evidence[0].value[0]["end_s"] = 3.0
    elif fault == "duration":
        raw.quality.pop("speech_duration_s")
    assert ManualDemoThresholds().apply_voice(raw).gate != "pass"
