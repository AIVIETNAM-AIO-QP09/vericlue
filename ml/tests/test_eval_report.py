"""EVAL-01: CSV, locked reference and auditable reports from synthetic data."""

import csv
import json
import subprocess

import numpy as np
import pytest

from vericlue_ml.common.calibration import brier_score, ece
from vericlue_ml.common.result import Module, Status
from vericlue_ml.eval import report

CORE = [
    "sample_id",
    "subject_id",
    "label",
    "attack_type",
    "prob_attack",
    "status",
    "module",
    "model_version",
]


def prediction(
    index,
    label,
    probability,
    *,
    subject=None,
    status=Status.OK,
    attack="replay",
    module=Module.FACE_PAD,
    version="synthetic@1",
):
    return report.Prediction(
        sample_id=f"sample-{index}",
        subject_id=subject or f"person-{index}",
        label=label,
        attack_type=attack if label else "bona_fide",
        prob_attack=probability,
        status=status,
        module=module,
        model_version=version,
    )


def balanced_rows(prefix="eval"):
    return [
        prediction(
            f"{prefix}-{i}-{label}",
            label,
            0.2 if label == 0 else 0.8,
            subject=f"{prefix}-subject-{i}",
        )
        for i in range(10)
        for label in (0, 1)
    ]


@pytest.fixture
def clean_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (
        ["init"],
        ["config", "user.name", "Synthetic Test"],
        ["config", "user.email", "test@example.invalid"],
    ):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    (repo / "tracked.txt").write_text("original", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "synthetic fixture"],
        check=True,
        capture_output=True,
    )
    return repo


def write_csv(path, rows, columns=CORE):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def csv_row(**changes):
    row = dict(
        zip(CORE, ["s1", "p1", "1", "replay", "0.8", "ok", "face_pad", "synthetic@1"], strict=True)
    )
    return row | changes


def test_csv_retains_optional_metadata_and_non_ok(tmp_path):
    path = tmp_path / "predictions.csv"
    columns = CORE + ["path", "source", "region", "score", "compression"]
    write_csv(
        path,
        [
            csv_row(
                path="a.mp4", source="synthetic", region="north", score="2.5", compression="h264"
            ),
            csv_row(sample_id="s2", status="error", prob_attack=""),
        ],
        columns,
    )
    rows = report.read_predictions(path)
    assert len(rows) == 2
    assert rows[0].path == "a.mp4"
    assert rows[0].source == "synthetic"
    assert rows[0].region == "north"
    assert rows[0].score == 2.5
    assert rows[0].compression == "h264"
    assert rows[1].prob_attack is None
    assert rows[1].status == Status.ERROR


@pytest.mark.parametrize(
    "changes",
    [
        {"prob_attack": ""},
        {"prob_attack": "nan"},
        {"prob_attack": "1.1"},
        {"label": "2"},
        {"subject_id": ""},
        {"status": "unknown"},
        {"module": "unknown"},
        {"model_version": ""},
    ],
)
def test_csv_rejects_invalid_rows(tmp_path, changes):
    path = tmp_path / "bad.csv"
    write_csv(path, [csv_row(**changes)])
    with pytest.raises(ValueError):
        report.read_predictions(path)


def test_csv_requires_core_columns(tmp_path):
    path = tmp_path / "missing.csv"
    write_csv(path, [], CORE[:-1])
    with pytest.raises(ValueError):
        report.read_predictions(path)


def test_report_known_metrics_and_metadata(clean_repo, tmp_path):
    rows = balanced_rows()
    result = report.evaluate(
        rows, dataset="synthetic-known", repo=clean_repo, n_bootstrap=30, seed=17
    )
    group = result.groups[0]
    assert result.dataset == "synthetic-known"
    assert result.seed == 17 and result.n_bootstrap == 30
    assert not result.commit.endswith("-dirty")
    assert group.n_total == group.n_used == 20
    assert group.n_subjects == 10
    assert group.estimates["auc"].value == 1
    assert group.estimates["apcer_max"].value == 0
    assert group.estimates["bpcer"].value == 0
    labels = [row.label for row in rows]
    probabilities = [row.prob_attack for row in rows]
    assert group.estimates["ece"].value == pytest.approx(ece(labels, probabilities))
    assert group.estimates["brier"].value == pytest.approx(brier_score(labels, probabilities))
    assert group.estimates["apcer:replay"].cp_low == 0
    assert 0 < group.estimates["apcer:replay"].cp_high < 1
    markdown = report.render_markdown(result)
    assert "synthetic-known" in markdown and result.commit in markdown
    assert "synthetic@1" in markdown
    destination = tmp_path / "result.md"
    report.write_report(result, destination)
    assert destination.read_text(encoding="utf-8") == markdown


@pytest.mark.parametrize("status", [Status.ERROR, Status.DEGRADED, Status.NOT_APPLICABLE])
def test_non_ok_requires_explicit_exclusion(clean_repo, status):
    rows = balanced_rows() + [prediction("bad", 1, None, status=status)]
    with pytest.raises(ValueError):
        report.evaluate(rows, dataset="synthetic", repo=clean_repo, n_bootstrap=20)
    result = report.evaluate(
        rows, dataset="synthetic", repo=clean_repo, n_bootstrap=20, exclude_non_ok=True
    )
    group = result.groups[0]
    assert (group.n_total, group.n_used) == (21, 20)
    excluded = {item.group: item for item in group.excluded}
    assert excluded["replay"].total == 11
    assert excluded["replay"].excluded == 1
    assert excluded["replay"].rate == pytest.approx(1 / 11)
    assert excluded["bona_fide"].total == 10
    assert excluded["bona_fide"].excluded == 0


def test_all_excluded_remains_visible(clean_repo):
    rows = [prediction("bad", 1, None, status=Status.ERROR)]
    result = report.evaluate(
        rows, dataset="synthetic", repo=clean_repo, n_bootstrap=20, exclude_non_ok=True
    )
    group = result.groups[0]
    assert (group.n_total, group.n_used) == (1, 0)
    assert group.warnings
    assert all(estimate.value is None for estimate in group.estimates.values())


def test_reference_threshold_is_locked_and_subjects_disjoint(clean_repo):
    reference = report.select_reference_threshold(
        balanced_rows("calib"), dataset="synthetic-calib", repo=clean_repo
    )
    assert reference.split == "calib_fit"
    assert reference.threshold == pytest.approx(0.8)
    assert reference.target_apcer == pytest.approx(0.05)
    result = report.evaluate(
        balanced_rows(),
        dataset="synthetic-test",
        reference=reference,
        repo=clean_repo,
        n_bootstrap=20,
    )
    estimates = result.groups[0].estimates
    assert estimates["bpcer_at_apcer5_locked"].value == 0
    assert estimates["apcer_max_at_reference"].value == 0
    assert estimates["bpcer_at_apcer5_descriptive"].value == 0
    with pytest.raises(ValueError):
        report.evaluate(
            balanced_rows("calib"),
            dataset="synthetic-overlap",
            reference=reference,
            repo=clean_repo,
            n_bootstrap=20,
        )


@pytest.mark.parametrize("split", ["test", "calib_ltt", "train"])
def test_reference_selection_rejects_other_splits(clean_repo, split):
    with pytest.raises(ValueError):
        report.select_reference_threshold(
            balanced_rows(), dataset="synthetic", repo=clean_repo, split=split
        )


def test_reference_selection_rejects_single_class_and_mixed_version(clean_repo):
    rows = balanced_rows()
    for invalid in (
        [row for row in rows if row.label == 0],
        rows + [prediction("v2", 1, 0.9, version="synthetic@2")],
        rows + [prediction("bad", 1, None, status=Status.ERROR)],
    ):
        with pytest.raises(ValueError):
            report.select_reference_threshold(invalid, dataset="synthetic", repo=clean_repo)


def test_report_groups_module_versions_separately(clean_repo):
    rows = balanced_rows() + [
        row.model_copy(update={"model_version": "synthetic@2"}) for row in balanced_rows()
    ]
    result = report.evaluate(rows, dataset="synthetic", repo=clean_repo, n_bootstrap=20)
    assert {group.model_version for group in result.groups} == {"synthetic@1", "synthetic@2"}
    assert all(group.n_used == 20 for group in result.groups)


@pytest.mark.parametrize("kind", ["tracked", "untracked"])
def test_report_marks_dirty_commit(clean_repo, kind):
    path = clean_repo / ("tracked.txt" if kind == "tracked" else "untracked.txt")
    path.write_text("changed", encoding="utf-8")
    result = report.evaluate(balanced_rows(), dataset="synthetic", repo=clean_repo, n_bootstrap=20)
    assert result.commit.endswith("-dirty")


def test_small_subject_warning_and_reproducible_bootstrap(clean_repo):
    rows = balanced_rows()[:8]
    first = report.evaluate(rows, dataset="synthetic", repo=clean_repo, seed=31, n_bootstrap=30)
    second = report.evaluate(rows, dataset="synthetic", repo=clean_repo, seed=31, n_bootstrap=30)
    assert first.groups[0].warnings
    assert first.groups[0].estimates == second.groups[0].estimates


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dataset": ""},
        {"dataset": "   "},
        {"n_bootstrap": 0},
        {"n_bootstrap": -1},
        {"n_bootstrap": True},
        {"seed": -1},
        {"seed": True},
    ],
)
def test_report_validates_run_parameters(clean_repo, kwargs):
    options = {"dataset": "synthetic", "repo": clean_repo, "n_bootstrap": 20} | kwargs
    with pytest.raises(ValueError):
        report.evaluate(balanced_rows(), **options)


def test_locked_and_descriptive_bpcer_are_distinct(clean_repo):
    reference = report.select_reference_threshold(
        balanced_rows("calib"), dataset="synthetic-calib", repo=clean_repo
    )
    rows = [
        prediction(
            f"eval-{i}-{label}", label, 0.7 if label == 0 else 0.6, subject=f"eval-person-{i}"
        )
        for i in range(10)
        for label in (0, 1)
    ]
    result = report.evaluate(
        rows, dataset="synthetic-shift", reference=reference, repo=clean_repo, n_bootstrap=20
    )
    group = result.groups[0]
    assert group.estimates["bpcer_at_apcer5_locked"].value == 0
    assert group.estimates["apcer_max_at_reference"].value == 1
    assert group.estimates["bpcer_at_apcer5_descriptive"].value > 0
    assert not any("descriptive" in key for key in vars(group) if "threshold" in key)
    markdown = report.render_markdown(result)
    assert "BPCER@APCER 5% (ngưỡng khóa" in markdown
    assert "BPCER@APCER 5% (mô tả" in markdown


def test_bootstrap_reports_missing_class_draws(clean_repo):
    rows = [prediction("negative", 0, 0.2), prediction("positive", 1, 0.8)]
    result = report.evaluate(
        rows, dataset="synthetic-two-people", repo=clean_repo, seed=42, n_bootstrap=50
    )
    estimates = result.groups[0].estimates
    assert 0 < estimates["auc"].n_valid < 50
    assert estimates["ece"].n_valid == 50


def test_cli_writes_report_and_requires_explicit_exclusion(clean_repo, tmp_path):
    path, output = tmp_path / "predictions.csv", tmp_path / "report.md"
    write_csv(path, [csv_row(), csv_row(sample_id="bad", status="degraded", prob_attack="")])
    args = [
        str(path),
        "--dataset",
        "synthetic-cli",
        "--output",
        str(output),
        "--repo",
        str(clean_repo),
        "--n-bootstrap",
        "20",
    ]
    with pytest.raises(SystemExit) as error:
        report.main(args)
    assert error.value.code == 2
    assert not output.exists()
    assert report.main([*args, "--exclude-non-ok"]) == 0
    markdown = output.read_text(encoding="utf-8")
    assert "synthetic-cli" in markdown
    assert "50.00%" in markdown


def test_fully_excluded_attack_type_makes_apcer_max_unavailable(clean_repo):
    reference = report.select_reference_threshold(
        balanced_rows("calib"), dataset="synthetic-calib", repo=clean_repo
    )
    rows = balanced_rows() + [
        prediction("missing-kind", 1, None, status=Status.ERROR, attack="deepfake")
    ]
    result = report.evaluate(
        rows,
        dataset="synthetic-missing-kind",
        reference=reference,
        repo=clean_repo,
        n_bootstrap=20,
        exclude_non_ok=True,
    )
    group = result.groups[0]
    assert group.estimates["apcer:replay"].value == 0
    assert group.estimates["apcer:deepfake"].value is None
    assert group.estimates["apcer_max"].value is None
    assert group.estimates["apcer_max_at_reference"].value is None
    assert group.warnings
    exclusion = next(item for item in group.excluded if item.group == "deepfake")
    assert exclusion.total == exclusion.excluded == 1
    assert exclusion.rate == 1


def test_cluster_bootstrap_preserves_subject_rows_and_multiplicity():
    subjects = np.array(["a", "b", "a", "c", "b", "a"])
    for seed in range(8):
        expected_people = np.random.default_rng(seed).choice(["a", "b", "c"], size=3)
        indices = report._cluster_indices(subjects, np.random.default_rng(seed))
        # Compare frequency of each original row against how often its owner was sampled.
        for row_index, subject in enumerate(subjects):
            assert np.count_nonzero(indices == row_index) == np.count_nonzero(
                expected_people == subject
            )
        assert len(indices) == sum(
            np.count_nonzero(subjects == subject) for subject in expected_people
        )


@pytest.mark.parametrize("repo_kind", ["missing", "no_head", "not_repository"])
def test_git_metadata_failure_is_explicit(tmp_path, repo_kind):
    repo = tmp_path / "metadata-repo"
    if repo_kind != "missing":
        repo.mkdir()
    if repo_kind == "no_head":
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
    with pytest.raises(ValueError):
        report.evaluate(balanced_rows(), dataset="synthetic", repo=repo, n_bootstrap=20)


def test_reference_subject_ids_normalized_before_disjoint_check(clean_repo):
    reference = report.select_reference_threshold(
        balanced_rows("calib"), dataset="synthetic-calib", repo=clean_repo
    )
    metadata = reference.model_dump()
    metadata["subject_ids"] = [" person-1 ", "person-1"]
    normalized = report.ReferenceThreshold.model_validate_json(json.dumps(metadata))
    assert normalized.subject_ids == ("person-1",)
    rows = balanced_rows() + [prediction("overlap", 0, 0.1, subject="person-1")]
    with pytest.raises(ValueError):
        report.evaluate(
            rows, dataset="synthetic-overlap", reference=normalized, repo=clean_repo, n_bootstrap=20
        )
    metadata["subject_ids"] = ["   "]
    with pytest.raises(ValueError):
        report.ReferenceThreshold.model_validate_json(json.dumps(metadata))


@pytest.mark.parametrize("ties", [False, True])
def test_reference_maximum_threshold_respects_each_attack_type(clean_repo, ties):
    rows = [prediction("real", 0, 0.1)]
    scores_by_type = {
        "replay": [0.2, 0.4, *([0.8] * 18)],
        "deepfake": [0.1, 0.3, *([0.9] * 18)],
    }
    if ties:
        scores_by_type["deepfake"] = [0.1, 0.1, *([0.9] * 18)]
    for attack, scores in scores_by_type.items():
        rows.extend(
            prediction(f"{attack}-{index}", 1, score, attack=attack)
            for index, score in enumerate(scores)
        )
    reference = report.select_reference_threshold(
        rows, dataset="synthetic-two-attacks", repo=clean_repo
    )
    expected = 0.1 if ties else 0.3
    assert reference.threshold == expected
    for scores in scores_by_type.values():
        assert np.mean(np.asarray(scores) < reference.threshold) <= 0.05
    # The very next representable threshold fails one group; tied scores move together.
    next_threshold = np.nextafter(reference.threshold, np.inf)
    assert (
        max(np.mean(np.asarray(scores) < next_threshold) for scores in scores_by_type.values())
        > 0.05
    )
