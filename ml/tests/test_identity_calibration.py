"""ADR-0012 identity artifacts are explicit provisional transforms, never fitted results."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from vericlue_ml.common import calibration as cal
from vericlue_ml.common.result import Gate, Module, ModuleResult, Status
from vericlue_ml.router.policy import TrustRouter

VERSION = "actual-detector@123+recipe-v1"
COMMIT = "a" * 40


def identity(module: Module = Module.FACE_PAD):
    return cal.identity(module=module, model_version=VERSION, commit=COMMIT)


def result(
    module: Module = Module.FACE_PAD,
    *,
    version: str = VERSION,
    status: Status = Status.OK,
    score: float | None = 0.01,
    gate: Gate | None = None,
) -> ModuleResult:
    return ModuleResult(
        module=module,
        model_version=version,
        status=status,
        score=score,
        prob_attack=0.8,
        gate=gate,
        latency_ms=1,
    )


def test_identity_clips_raw_scores_without_changing_interior_values() -> None:
    assert identity().predict([-100, 0, 0.25, 1, 100]).tolist() == pytest.approx(
        [cal.EPSILON, cal.EPSILON, 0.25, 1 - cal.EPSILON, 1 - cal.EPSILON]
    )


@pytest.mark.parametrize("scores", [[], [[0.1]], [float("nan")], [float("inf")], [float("-inf")]])
def test_identity_rejects_unusable_scores(scores) -> None:
    with pytest.raises(cal.CalibrationError):
        identity().predict(scores)


def test_identity_records_no_invented_samples_metrics_or_prior() -> None:
    artifact = identity()
    payload = artifact.model_dump(mode="json")
    assert artifact.method == "identity"
    assert artifact.provisional is True
    assert artifact.note == "MVP — không dùng cho báo cáo"
    assert artifact.n_pos == artifact.n_neg == 0
    assert artifact.dataset == "not_fitted"
    assert artifact.split == "none"
    assert artifact.metrics_scope == "not_evaluated"
    assert artifact.commit == COMMIT
    assert artifact.parameters == cal.Parameters()
    assert (
        not {
            "before",
            "after",
            "before_reliability",
            "after_reliability",
            "cv_folds",
            "cv_log_loss",
        }
        & payload.keys()
    )
    with pytest.raises(cal.CalibrationError):
        _ = artifact.prior_attack


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provisional", False),
        ("n_pos", 1),
        ("n_neg", 1),
        ("dataset", "calibration-data"),
        ("split", "calib_fit"),
        ("metrics_scope", "group_oof"),
        ("note", ""),
        ("parameters", {"slope": 1, "intercept": 0}),
        ("before", {"log_loss": 0, "ece": 0, "brier": 0}),
        ("cv_folds", 5),
    ],
)
def test_identity_rejects_misleading_metadata_or_learned_parameters(field, value) -> None:
    payload = identity().model_dump(mode="json")
    payload[field] = value
    with pytest.raises(ValidationError):
        cal.IdentityCalibrator.model_validate(payload)


@pytest.mark.parametrize("module", [Module.FACE_PAD, Module.FACE_DEEPFAKE, Module.VOICE_SPOOF])
def test_identity_store_roundtrip_and_apply_uses_exact_version(
    tmp_path: Path, module: Module
) -> None:
    store = cal.CalibrationStore(tmp_path)
    artifact = identity(module)
    path = store.save(artifact)
    assert json.loads(path.read_text(encoding="utf-8"))["method"] == "identity"
    reloaded = cal.CalibrationStore(tmp_path)
    loaded = reloaded.load(module, VERSION)
    assert isinstance(loaded, cal.IdentityCalibrator)
    assert loaded == artifact
    original = result(module, score=0.25)
    applied = reloaded.apply(original)
    assert applied.prob_attack == 0.25
    assert original.prob_attack == 0.8
    with pytest.raises(cal.CalibrationError):
        reloaded.apply(result(module, version="other-version", score=0.25))


@pytest.mark.parametrize("status", [Status.ERROR, Status.DEGRADED, Status.NOT_APPLICABLE])
def test_identity_never_manufactures_probability_for_unusable_status(
    tmp_path: Path, status: Status
) -> None:
    store = cal.CalibrationStore(tmp_path)
    store.save(identity())
    original = result(status=status)
    applied = store.apply(original)
    assert applied.status == status
    assert applied.prob_attack is None
    assert applied.model_dump(exclude={"prob_attack"}) == original.model_dump(
        exclude={"prob_attack"}
    )
    assert original.prob_attack == 0.8


def test_identity_still_requires_raw_score(tmp_path: Path) -> None:
    store = cal.CalibrationStore(tmp_path)
    store.save(identity())
    with pytest.raises(cal.CalibrationError):
        store.apply(result(score=None))


def test_mvp_missing_versioned_identity_calibrator_reviews_instead_of_passing(
    tmp_path: Path,
) -> None:
    store = cal.CalibrationStore(tmp_path)
    for module in (Module.FACE_PAD, Module.FACE_DEEPFAKE):
        store.save(identity(module))
    router = TrustRouter(calibrators=store, profile="mvp")
    results = {
        Module.QUALITY: result(Module.QUALITY, gate=Gate.PASS),
        Module.CAMPROBE: result(Module.CAMPROBE, gate=Gate.PASS),
        Module.FACE_PAD: result(Module.FACE_PAD),
        Module.FACE_DEEPFAKE: result(Module.FACE_DEEPFAKE),
    }
    assert router.finalize(results).status == "pass"
    results[Module.FACE_PAD] = result(Module.FACE_PAD, version="other-version")
    decision = router.finalize(results)
    assert decision.status == "review"
    assert decision.results[Module.FACE_PAD].status == Status.ERROR
    assert decision.results[Module.FACE_PAD].prob_attack is None


def test_existing_platt_artifact_stays_compatible_with_store(tmp_path: Path) -> None:
    artifact = cal.fit(
        cal.CalibFit(
            scores=[0.1, 0.9] * 6,
            labels=[0, 1] * 6,
            subject_ids=[f"subject-{i // 2}" for i in range(12)],
            dataset="synthetic",
        ),
        module=Module.FACE_PAD,
        model_version=VERSION,
        commit=COMMIT,
    )
    store = cal.CalibrationStore(tmp_path)
    path = store.save(artifact)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("provisional", None)
    path.write_text(json.dumps(raw), encoding="utf-8")
    reloaded = cal.CalibrationStore(tmp_path)
    loaded = reloaded.load(Module.FACE_PAD, VERSION)
    assert isinstance(loaded, cal.Calibrator)
    assert loaded.method == "platt"
    assert loaded.n_pos == loaded.n_neg == 6
    assert loaded.prior_attack == 0.5
    assert loaded.predict([0.1, 0.9]).tolist() == artifact.predict([0.1, 0.9]).tolist()
    assert reloaded.apply(result(score=0.1)).prob_attack == pytest.approx(
        artifact.predict([0.1])[0]
    )
