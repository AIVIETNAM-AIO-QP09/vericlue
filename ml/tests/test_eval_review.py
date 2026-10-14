"""Regression coverage for PR review, using synthetic predictions only."""

import csv
import json
import subprocess
from dataclasses import asdict

import numpy as np
import pytest

from vericlue_ml.common.result import Module, Status
from vericlue_ml.eval import metrics, report


@pytest.fixture
def repo(tmp_path):
    directory = tmp_path / "repo"
    directory.mkdir()
    for args in (
        ["init"],
        ["config", "user.name", "Synthetic"],
        ["config", "user.email", "test@example.invalid"],
        ["commit", "--allow-empty", "-m", "fixture"],
    ):
        subprocess.run(["git", "-C", str(directory), *args], check=True, capture_output=True)
    return directory


def rows(labels, probabilities, *, prefix="eval", attacks=None):
    return [
        report.Prediction(
            sample_id=f"{prefix}-{index}",
            subject_id=f"{prefix}-person-{index % 4}",
            label=label,
            attack_type=(attacks[index] if attacks else "replay") if label else "bona_fide",
            prob_attack=probability,
            status=Status.OK,
            module=Module.FACE_PAD,
            model_version="synthetic@1",
        )
        for index, (label, probability) in enumerate(zip(labels, probabilities, strict=True))
    ]


def test_markdown_discloses_bootstrap_subjects_warning_and_default(repo):
    result = report.evaluate(
        rows([0, 1, 0, 1], [0.1, 0.8, 0.2, 0.9]),
        dataset="synthetic",
        seed=23,
        n_bootstrap=20,
        repo=repo,
    )
    text = report.render_markdown(result)
    assert "seed=23" in text and "số lần=20" in text
    assert "số người dùng=4" in text
    assert "<10" in text
    assert "khoảng tin cậy không đáng tin" in text
    assert result.groups[0].warnings
    assert all(warning in text for warning in result.groups[0].warnings)
    assert result.groups[0].threshold_source == "default"
    assert "mặc định 0.5, không do caller cung cấp" in text
    supplied = report.evaluate(
        rows([0, 1], [0.1, 0.8]), dataset="synthetic", threshold=0.5, n_bootstrap=20, repo=repo
    )
    assert supplied.groups[0].threshold_source == "caller"
    assert "mặc định 0.5, không do caller cung cấp" not in report.render_markdown(supplied)


def test_descriptive_line_is_pooled_and_no_descriptive_threshold_persisted(repo):
    result = report.evaluate(
        rows([0, 1, 0, 1], [0.1, 0.8, 0.2, 0.9]), dataset="synthetic", n_bootstrap=20, repo=repo
    )
    text = report.render_markdown(result)
    line = next(line for line in text.splitlines() if "BPCER@APCER 5% (mô tả" in line)
    assert "APCER gộp" in line and "ngưỡng" not in line
    assert "threshold" not in asdict(result.groups[0].estimates["bpcer_at_apcer5_descriptive"])
    serialized = json.dumps(asdict(result), ensure_ascii=False)
    assert "descriptive_threshold" not in serialized
    assert "threshold_descriptive" not in serialized
    assert "ngưỡng mô tả" not in text.lower()


def test_overlap_metrics_known_by_hand(repo):
    reference = report.select_reference_threshold(
        rows([1] * 20 + [0], [0.1, 0.6] + [0.9] * 18 + [0.05], prefix="calib"),
        dataset="synthetic-calib",
        repo=repo,
    )
    assert reference.threshold == 0.6
    # At .5: two of four attacks accepted, two of four genuine rejected.
    # The ROC edge from APCER .25 to 0 holds BPCER .75; genuine .3 crosses first.
    result = report.evaluate(
        rows([1] * 4 + [0] * 4, [0.2, 0.4, 0.6, 0.8, 0.1, 0.3, 0.5, 0.7]),
        dataset="synthetic-overlap",
        reference=reference,
        threshold=0.5,
        n_bootstrap=20,
        repo=repo,
    )
    estimates = result.groups[0].estimates
    assert estimates["apcer_max"].value == 0.5
    assert estimates["bpcer"].value == 0.5
    assert estimates["bpcer_at_apcer5_locked"].value == 0.25
    assert estimates["apcer_max_at_reference"].value == 0.5
    assert estimates["bpcer_at_apcer5_descriptive"].value == pytest.approx(0.75)


@pytest.mark.parametrize("n_attack", [20, 40])
def test_descriptive_vertical_roc_segment_uses_best_bpcer(n_attack):
    n_low = n_attack // 20
    labels = [1] * n_attack + [0] * 10
    probabilities = [0.9] * (n_attack - n_low) + [0.1] * n_low + [0.5, 0.4, 0.3] + [0.05] * 7
    assert metrics.descriptive_bpcer_at_apcer(labels, probabilities) == 0


@pytest.mark.parametrize("bad_label", ["1.0", "abc"])
def test_csv_rejects_noninteger_label(tmp_path, bad_label):
    path = tmp_path / "invalid.csv"
    path.write_text(
        "sample_id,subject_id,label,attack_type,prob_attack,status,module,model_version\n"
        f"s,p,{bad_label},replay,0.9,ok,face_pad,synthetic@1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        report.read_predictions(path)


def test_csv_rejects_duplicate_sample_ids(tmp_path):
    path = tmp_path / "duplicate.csv"
    path.write_text(
        "sample_id,subject_id,label,attack_type,prob_attack,status,module,model_version\n"
        "same,p1,1,replay,0.9,ok,face_pad,synthetic@1\n"
        "same,p2,0,bona_fide,0.1,ok,face_pad,synthetic@1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        report.read_predictions(path)


def test_attack_types_normalized_and_reference_remembers_types(repo):
    predictions = rows(
        [0, 1, 1], [0.1, 0.7, 0.8], prefix="calib", attacks=["", " replay ", " deepfake "]
    )
    assert [row.attack_type for row in predictions] == ["bona_fide", "replay", "deepfake"]
    reference = report.select_reference_threshold(predictions, dataset="synthetic-calib", repo=repo)
    assert reference.attack_types == ("deepfake", "replay")
    missing = reference.model_dump()
    del missing["attack_types"]
    with pytest.raises(ValueError):
        report.ReferenceThreshold.model_validate(missing)
    result = report.evaluate(
        rows([0, 1], [0.1, 0.9], attacks=["", "novel_attack"]),
        dataset="synthetic-eval",
        reference=reference,
        n_bootstrap=20,
        repo=repo,
    )
    assert any("novel_attack" in warning for warning in result.groups[0].warnings)
    assert "novel_attack" in report.render_markdown(result)


@pytest.mark.parametrize("attack_type", ["", "bona_fide", " bona_fide "])
def test_genuine_attack_type_accepts_only_empty_or_bona_fide(attack_type):
    prediction = rows([0], [0.1])[0]
    data = prediction.model_dump() | {"attack_type": attack_type}
    assert report.Prediction.model_validate(data).attack_type == attack_type.strip()


@pytest.mark.parametrize("attack_type", ["replay", "deepfake", " bona_fide_other "])
def test_genuine_attack_type_rejects_attack_names(attack_type):
    with pytest.raises(ValueError):
        report.Prediction.model_validate(
            rows([0], [0.1])[0].model_dump() | {"attack_type": attack_type}
        )


def test_precomputed_cluster_mapping_preserves_multiplicities():
    subjects = np.array(["a", "b", "a", "c", "b", "a"])
    clusters = report._subject_clusters(subjects)
    assert len(clusters) == 3
    for seed in range(5):
        chosen = np.random.default_rng(seed).choice(["a", "b", "c"], size=3)
        actual = report._cluster_indices(subjects, np.random.default_rng(seed), clusters=clusters)
        for index, subject in enumerate(subjects):
            assert np.count_nonzero(actual == index) == np.count_nonzero(chosen == subject)
        original = report._cluster_indices(subjects, np.random.default_rng(seed))
        np.testing.assert_array_equal(actual, original)


def test_cli_default_threshold_is_declared_as_default(repo, tmp_path):
    source, destination = tmp_path / "input.csv", tmp_path / "result.md"
    predictions = rows([0, 1], [0.1, 0.9])
    columns = sorted(report.CORE_COLUMNS)
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(
            {column: row.model_dump(mode="json")[column] for column in columns}
            for row in predictions
        )
    assert (
        report.main(
            [
                str(source),
                "--dataset",
                "synthetic-cli",
                "--output",
                str(destination),
                "--repo",
                str(repo),
                "--n-bootstrap",
                "20",
            ]
        )
        == 0
    )
    assert "mặc định 0.5, không do caller cung cấp" in destination.read_text(encoding="utf-8")
