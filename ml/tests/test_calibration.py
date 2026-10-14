"""ROUT-01: đáp án tổng hợp, chia theo người, persistence và lỗi an toàn trên CPU."""

import builtins
import json
from pathlib import Path

import jsonschema
import numpy as np
import pytest
from sklearn.model_selection import GroupKFold

from vericlue_ml.common import Module, ModuleResult, Status
from vericlue_ml.common import calibration as cal


def nonlinear_data(subjects: int = 20) -> cal.CalibFit:
    # Every subject has the same known non-logistic attack frequencies.
    scores, labels, groups = [], [], []
    for subject in range(subjects):
        for score, positives in zip([0.1, 0.3, 0.5, 0.7, 0.9], [0, 8, 10, 12, 20], strict=True):
            scores.extend([score] * 20)
            labels.extend([1] * positives + [0] * (20 - positives))
            groups.extend([f"subject-{subject}"] * 20)
    return cal.CalibFit(scores=scores, labels=labels, subject_ids=groups, dataset="synthetic-step")


def fit_data(data: cal.CalibFit) -> cal.Calibrator:
    return cal.fit(data, module="face_pad", model_version="test@1", commit="synthetic-test")


@pytest.fixture(scope="module")
def isotonic() -> cal.Calibrator:
    return fit_data(nonlinear_data())


@pytest.fixture(scope="module")
def platt() -> cal.Calibrator:
    rng = np.random.default_rng(14)
    p = rng.uniform(0.02, 0.98, 1600)
    return fit_data(
        cal.CalibFit(
            scores=(0.65 + 0.2 * p).tolist(),
            labels=(rng.random(p.size) < p).astype(int).tolist(),
            subject_ids=[f"person-{i // 16}" for i in range(p.size)],
            dataset="synthetic-distorted",
        )
    )


def test_ece_and_brier_known_answer():
    y, p = [0, 1, 0, 1], [0, 0.25, 0.5, 1]
    assert cal.ece(y, p, n_bins=2) == pytest.approx(0.3125)
    assert cal.brier_score(y, p) == pytest.approx(0.203125)
    rows = cal.reliability_table(y, p, n_bins=4)
    assert [r.count for r in rows] == [1, 1, 1, 1]
    assert rows[-1].mean_probability == 1
    empty = cal.reliability_table([0, 1], [0, 1], n_bins=3)
    assert empty[1].count == 0 and empty[1].attack_rate is None
    markdown = cal.reliability_markdown(empty)
    assert "| Bin |" in markdown and "—" in markdown and "1.000]" in markdown
    assert cal.log_loss([0, 1], [0, 1]) == pytest.approx(-np.log(1 - cal.EPSILON))


@pytest.mark.parametrize("fixture", ["platt", "isotonic"])
def test_synthetic_ece_improves_out_of_fold(request, fixture):
    artifact = request.getfixturevalue(fixture)
    assert artifact.method == fixture
    assert artifact.after.ece < artifact.before.ece
    assert artifact.after.brier < artifact.before.brier
    assert artifact.metrics_scope == "group_oof"
    assert artifact.n_pos + artifact.n_neg > 0
    assert artifact.prior_attack == pytest.approx(
        artifact.n_pos / (artifact.n_pos + artifact.n_neg)
    )
    assert artifact.cv_folds == 5


def test_isotonic_recovers_known_curve_and_clips(isotonic):
    assert isotonic.predict([0.1, 0.3, 0.5, 0.7, 0.9]).tolist() == pytest.approx(
        [cal.EPSILON, 0.4, 0.5, 0.6, 1 - cal.EPSILON]
    )
    assert isotonic.predict([-1e9, 1e9]).tolist() == pytest.approx([cal.EPSILON, 1 - cal.EPSILON])


def test_platt_extreme_scores_are_finite(platt):
    p = platt.predict([-1e100, 1e100])
    assert np.isfinite(p).all()
    assert p.tolist() == pytest.approx([cal.EPSILON, 1 - cal.EPSILON])


def test_selection_requires_counts_and_two_percent():
    assert not cal._choose_isotonic(99, 100, {"platt": 1, "isotonic": 0.1})
    assert not cal._choose_isotonic(100, 99, {"platt": 1, "isotonic": 0.1})
    assert not cal._choose_isotonic(100, 100, {"platt": 1, "isotonic": 0.981})
    assert cal._choose_isotonic(100, 100, {"platt": 1, "isotonic": 0.98})
    assert not cal._choose_isotonic(100, 100, {"platt": 1, "isotonic": 1})


def test_small_sample_falls_back_to_platt():
    artifact = fit_data(
        cal.CalibFit(
            scores=[0.1, 0.9] * 5,
            labels=[0, 1] * 5,
            subject_ids=[f"s{i // 2}" for i in range(10)],
            dataset="small-synthetic",
        )
    )
    assert artifact.method == "platt" and set(artifact.cv_log_loss) == {"platt"}


def test_group_folds_never_leak_and_final_fit_uses_all(monkeypatch):
    original_split = GroupKFold.split
    seen, fit_sizes = [], []
    original_fit = cal._fit_parameters

    def checked_split(self, x, y, groups):
        for train, valid in original_split(self, x, y, groups):
            assert set(groups[train]).isdisjoint(groups[valid])
            seen.extend(valid.tolist())
            yield train, valid

    def checked_fit(method, x, y):
        fit_sizes.append(len(x))
        return original_fit(method, x, y)

    monkeypatch.setattr(GroupKFold, "split", checked_split)
    monkeypatch.setattr(cal, "_fit_parameters", checked_fit)
    data = nonlinear_data()
    fit_data(data)
    assert sorted(seen) == list(range(len(data.scores)))
    assert fit_sizes[-1] == len(data.scores)
    assert all(size < len(data.scores) for size in fit_sizes[:-1])


@pytest.mark.parametrize("fixture", ["platt", "isotonic"])
def test_json_round_trip_and_cache(request, fixture, tmp_path):
    artifact = request.getfixturevalue(fixture)
    store = cal.CalibrationStore(tmp_path)
    path = store.save(artifact)
    loaded_store = cal.CalibrationStore(tmp_path)
    loaded = loaded_store.load("face_pad", "test@1")
    assert loaded == artifact
    assert loaded.predict([0.1, 0.7]).tolist() == artifact.predict([0.1, 0.7]).tolist()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert {
        "module",
        "model_version",
        "method",
        "parameters",
        "epsilon",
        "n_pos",
        "n_neg",
        "before",
        "after",
        "date",
        "commit",
    } <= raw.keys()
    path.write_text("bad JSON", encoding="utf-8")
    assert loaded_store.load("face_pad", "test@1") is loaded
    with pytest.raises(cal.CalibrationError, match="Không nạp"):
        cal.CalibrationStore(tmp_path).load("face_pad", "test@1")


def result(module="face_pad", version="test@1", status="ok", score=0.7):
    return ModuleResult(
        module=module,
        model_version=version,
        status=status,
        score=score,
        prob_attack=0.99,
        latency_ms=1,
    )


@pytest.mark.parametrize("module", sorted(cal.REQUIRED_MODULES))
def test_missing_calibrator_raises_even_with_probability(module, tmp_path):
    with pytest.raises(cal.CalibrationError, match="Không nạp"):
        cal.CalibrationStore(tmp_path).apply(result(module=module))


def test_apply_preserves_result_and_contract(isotonic, tmp_path):
    store = cal.CalibrationStore(tmp_path)
    store.save(isotonic)
    original = result()
    calibrated = store.apply(original)
    assert calibrated.prob_attack == pytest.approx(0.6)
    assert original.prob_attack == 0.99
    assert calibrated.status == Status.OK
    assert calibrated.score == original.score
    assert set(calibrated.to_contract()) == set(original.to_contract())
    schema_path = (
        Path(__file__).resolve().parents[2] / "packages/contracts/schemas/module_result.schema.json"
    )
    jsonschema.validate(
        calibrated.to_contract(), json.loads(schema_path.read_text(encoding="utf-8"))
    )
    with pytest.raises(cal.CalibrationError, match="Thiếu score"):
        store.apply(result(score=None))


@pytest.mark.parametrize("status", ["error", "degraded", "not_applicable"])
def test_bad_status_never_becomes_usable(status, tmp_path):
    original = result(status=status)
    calibrated = cal.CalibrationStore(tmp_path).apply(original)
    assert calibrated.status == status and not calibrated.is_usable
    assert calibrated.prob_attack is None and original.prob_attack == 0.99


@pytest.mark.parametrize("module", list(Module))
def test_mock_bypasses_calibration(module, tmp_path):
    original = result(module=module, version="mock@0.1")
    assert cal.CalibrationStore(tmp_path).apply(original) is original


@pytest.mark.parametrize("module", sorted(set(Module) - cal.REQUIRED_MODULES))
def test_gate_modules_are_exempt(module, tmp_path):
    original = result(module=module, score=None)
    assert cal.CalibrationStore(tmp_path).apply(original) is original


@pytest.mark.parametrize(
    "change",
    [
        {"model_version": "another"},
        {"module": "voice_spoof"},
        {"epsilon": 0},
        {"parameters": {"x": [1, 0], "y": [0, 1]}},
        {"n_pos": 0},
        {"parameters": {"x": [0, 1], "y": [0, float("nan")]}},
    ],
)
def test_corrupt_or_mismatched_artifact_raises(isotonic, tmp_path, change):
    path = cal.CalibrationStore(tmp_path).path("face_pad", "test@1")
    path.parent.mkdir(parents=True)
    raw = isotonic.model_dump(mode="json") | change
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(cal.CalibrationError):
        cal.CalibrationStore(tmp_path).load("face_pad", "test@1")


def test_reverse_direction_and_invalid_fit_rejected():
    data = nonlinear_data()
    with pytest.raises(cal.CalibrationError, match="AUC < 0.5"):
        fit_data(data.model_copy(update={"scores": [-s for s in data.scores]}))
    with pytest.raises(cal.CalibrationError, match="hai subject"):
        fit_data(data.model_copy(update={"subject_ids": ["same"] * len(data.scores)}))
    with pytest.raises(cal.CalibrationError, match="hai lớp"):
        fit_data(data.model_copy(update={"labels": [0] * len(data.scores)}))
    with pytest.raises(cal.CalibrationError, match="thiếu lớp"):
        fit_data(
            cal.CalibFit(scores=[0.1, 0.9], labels=[0, 1], subject_ids=["a", "b"], dataset="bad")
        )
    with pytest.raises(ValueError):
        cal.CalibFit(
            scores=[0, 1], labels=[0, 1], subject_ids=["a", "b"], dataset="bad", split="calib_ltt"
        )


@pytest.mark.parametrize(
    "labels,probabilities",
    [
        ([], []),
        ([0], [float("nan")]),
        ([0], [1.1]),
        ([0], [-0.1]),
        ([2], [0.5]),
        ([0, 1], [0.5]),
        ([[0]], [[0.5]]),
    ],
)
def test_invalid_metric_inputs(labels, probabilities):
    for metric in (cal.ece, cal.brier_score, cal.log_loss):
        with pytest.raises(cal.CalibrationError):
            metric(labels, probabilities)


def test_store_root_and_version_path(monkeypatch, tmp_path):
    monkeypatch.setenv("CALIBRATORS_DIR", str(tmp_path))
    store = cal.CalibrationStore()
    assert store.root == tmp_path
    assert store.path("face_pad", "v1:a/b").parent == tmp_path / "face_pad"
    assert store.path("face_pad", "v1:a/b").name == "v1%3Aa%2Fb.json"
    for version in ("", " ", ".", ".."):
        with pytest.raises(cal.CalibrationError):
            store.path("face_pad", version)
    monkeypatch.delenv("CALIBRATORS_DIR")
    assert (
        cal.CalibrationStore().root
        == Path(cal.__file__).resolve().parents[3] / "configs/calibrators"
    )


def test_png_dependency_is_optional(monkeypatch, tmp_path):
    original_import = builtins.__import__

    def without_matplotlib(name, *args, **kwargs):
        if name.startswith("matplotlib"):
            raise ImportError("optional")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_matplotlib)
    rows = cal.reliability_table([0, 1], [0.1, 0.9])
    assert cal.reliability_markdown(rows)
    with pytest.raises(cal.CalibrationError, match="extra eval"):
        cal.plot_reliability(rows, tmp_path / "plot.png")


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_score_rejected(isotonic, tmp_path, score):
    store = cal.CalibrationStore(tmp_path)
    store.save(isotonic)
    with pytest.raises(cal.CalibrationError, match="hữu hạn"):
        store.apply(result(score=score))


def test_constant_score_fits_prior():
    artifact = fit_data(
        cal.CalibFit(
            scores=[0.5] * 10,
            labels=[0, 1] * 5,
            subject_ids=[f"s{i // 2}" for i in range(10)],
            dataset="synthetic-constant",
        )
    )
    assert artifact.method == "platt"
    assert artifact.predict([0.5]).tolist() == pytest.approx([0.5])


def test_png_export_when_extra_installed(tmp_path):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    rows = cal.reliability_table([0, 1], [0.1, 0.9])
    path = tmp_path / "nested/reliability.png"
    cal.plot_reliability(rows, path)
    assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
