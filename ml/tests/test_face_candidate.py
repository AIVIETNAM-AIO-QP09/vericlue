"""Synthetic session fixtures test diagnostics, never real-data readiness."""

import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

from vericlue_ml.common import calibration
from vericlue_ml.eval import session_calibration as session

COMMIT = "a" * 40


def write(path, body):
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    from vericlue_ml.eval import face_candidate as candidate

    monkeypatch.setattr(session, "git_revision", lambda: COMMIT)
    monkeypatch.setattr(candidate, "git_revision", lambda: COMMIT)
    rows = [
        {
            "sample_id": f"sample-{i}",
            "subject_id": f"person-{i // 2}",
            "split": "calib_fit",
            "label": i % 2,
            "video_sha256": hashlib.sha256(f"video-{i}".encode()).hexdigest(),
            "challenge_sha256": hashlib.sha256(f"challenge-{i}".encode()).hexdigest(),
            "status": "ok",
            "error_code": None,
            "score": 0.2 if i % 2 == 0 else 0.8,
        }
        for i in range(12)
    ]
    rows[8].update(status="error", error_code="E_INTERNAL", score=None)
    rows[9].update(status="degraded", error_code="E_LOW_QUALITY", score=None)
    rows[10].update(split="calib_ltt", subject_id="unused-ltt")
    rows[11].update(split="test", subject_id="unused-test")
    paths = []
    for module in ("face_pad", "face_deepfake"):
        body = {
            "schema_version": 1,
            "dataset": "synthetic-session",
            "module": module,
            "model_version": f"{module}@123+session-video-v2",
            "source_commit": "b" * 40,
            "manifest_sha256": "c" * 64,
            "model_manifest_sha256": "d" * 64,
            "rows": json.loads(json.dumps(rows)),
        }
        if module == "face_deepfake":
            body["rows"][8].update(status="ok", error_code=None, score=0.3)
            body["rows"][9].update(status="not_applicable", error_code=None, score=None)
            body["rows"].reverse()
        report = write(tmp_path / f"{module}.json", body)
        result = session.fit_report(report, tmp_path / "calibrators", n_splits=2)
        artifact = Path(result["artifact"])
        fitted = json.loads(artifact.read_text())
        # Known synthetic coefficients make PAD win on attack, GenD on bona fide.
        fitted["parameters"].update(
            slope=3.0 if module == "face_pad" else 1.0,
            intercept=-1.0 if module == "face_pad" else 0.2,
        )
        write(artifact, fitted)
        paths.append((report, artifact))
    return candidate, paths[0][0], paths[1][0], paths[0][1], paths[1][1]


def score(inputs, output):
    candidate, *paths = inputs
    return candidate.score_report(*paths, output)


def relink(report, artifact):
    """Keep self-reported fit linkage coherent while testing row identity checks."""
    body = json.loads(report.read_text())
    fitted = json.loads(artifact.read_text())
    selected = [row for row in body["rows"] if row["split"] == "calib_fit"]
    usable = [row for row in selected if row["status"] == "ok"]
    meta = json.loads(fitted["dataset"])
    meta.update(
        dataset=body["dataset"],
        report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),
        manifest_sha256=body["manifest_sha256"],
        selected=len(selected),
        usable=len(usable),
        groups=len({row["subject_id"] for row in usable}),
        excluded_by_label={
            str(label): sum(row["label"] == label and row["status"] != "ok" for row in selected)
            for label in (0, 1)
        },
    )
    fitted.update(
        dataset=json.dumps(meta),
        n_pos=sum(row["label"] == 1 for row in usable),
        n_neg=sum(row["label"] == 0 for row in usable),
    )
    write(artifact, fitted)


def test_max_uses_frozen_calibrators_and_preserves_failed_measurements(
    inputs, tmp_path, monkeypatch
):
    candidate, pad, gend, pad_cal, gend_cal = inputs
    originals = {path: path.read_bytes() for path in inputs[1:]}

    def forbidden(*args, **kwargs):
        pytest.fail("Scoring must not fit")

    monkeypatch.setattr(calibration, "fit", forbidden)
    monkeypatch.setattr(session, "fit", forbidden)
    result = score(inputs, tmp_path / "scores.json")
    assert result["split"] == "calib_fit"
    assert result["sample_count"] == 10
    by_id = {row["measurements"]["face_pad"]["sample_id"]: row for row in result["rows"]}
    pad_rows = {row["sample_id"]: row for row in json.loads(pad.read_text())["rows"]}
    gend_rows = {row["sample_id"]: row for row in json.loads(gend.read_text())["rows"]}
    for key, row in by_id.items():
        assert row["measurements"] == {"face_pad": pad_rows[key], "face_deepfake": gend_rows[key]}
        expected = {}
        for module, path in (("face_pad", pad_cal), ("face_deepfake", gend_cal)):
            measurement = row["measurements"][module]
            parameters = json.loads(path.read_text())["parameters"]
            z = parameters["slope"] * (measurement["score"] or 0) + parameters["intercept"]
            expected[module] = (
                min(0.9999, max(0.0001, 1 / (1 + math.exp(-z))))
                if measurement["status"] == "ok"
                else None
            )
        assert row["module_probabilities"] == pytest.approx(expected)
        probabilities = list(expected.values())
        assert row["candidate_probability"] == (
            pytest.approx(max(probabilities)) if None not in probabilities else None
        )
        assert "decision" not in row
    assert by_id["sample-8"]["module_probabilities"]["face_deepfake"] is not None
    assert by_id["sample-8"]["candidate_probability"] is None
    assert by_id["sample-9"]["candidate_probability"] is None
    for flag in (
        "deployed",
        "runtime_eligible",
        "ltt_ready",
        "source_crosswalk_verified",
        "prior_gates_measured",
        "runtime_binding_verified",
        "external_attestation_verified",
    ):
        assert result[flag] is False
    assert result["diagnostic_only"] is True
    assert result["execution_commit"] == COMMIT
    assert (
        result["sources"]["face_pad"]["report_sha256"] == hashlib.sha256(originals[pad]).hexdigest()
    )
    assert all(path.read_bytes() == content for path, content in originals.items())
    assert json.loads((tmp_path / "scores.json").read_text()) == result


@pytest.mark.parametrize(
    "fault",
    [
        "identity",
        "provisional",
        "missing_provisional",
        "module",
        "version",
        "count",
        "bool_count",
        "float_count",
        "string_count",
        "commit",
        "metadata_missing",
        "metadata_extra",
        "dataset",
        "report_sha256",
        "manifest_sha256",
        "model_manifest_sha256",
        "measurement_commit",
        "selected",
        "usable",
        "excluded_by_label",
        "groups",
        "metadata_bool",
    ],
)
def test_rejects_unlinked_or_unfitted_calibrators(inputs, tmp_path, fault):
    path = inputs[3]
    body = json.loads(path.read_text())
    if fault == "identity":
        body["method"] = "identity"
    elif fault == "provisional":
        body["provisional"] = True
    elif fault == "missing_provisional":
        del body["provisional"]
    elif fault == "module":
        body["module"] = "face_deepfake"
    elif fault == "version":
        body["model_version"] = "different+session-video-v2"
    elif fault in ("count", "bool_count", "float_count", "string_count"):
        body["n_pos"] = {"count": 99, "bool_count": True, "float_count": 4.0, "string_count": "4"}[
            fault
        ]
    elif fault == "commit":
        body["commit"] = COMMIT + "-dirty"
    else:
        meta = json.loads(body["dataset"])
        if fault == "metadata_missing":
            del meta["groups"]
        elif fault == "metadata_extra":
            meta["invented"] = 1
        elif fault == "metadata_bool":
            meta["excluded_by_label"]["0"] = True
        elif fault == "excluded_by_label":
            meta[fault]["1"] += 1
        elif fault in ("groups", "selected", "usable"):
            meta[fault] += 1
        else:
            meta[fault] = "wrong"
        body["dataset"] = json.dumps(meta)
    write(path, body)
    output = tmp_path / "rejected.json"
    with pytest.raises(ValueError):
        score(inputs, output)
    assert not output.exists()


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "extra",
        "subject_id",
        "split",
        "label",
        "video_sha256",
        "challenge_sha256",
        "dataset",
        "manifest_sha256",
        "module",
        "cross_split",
        "duplicate_video",
    ],
)
def test_checks_all_rows_including_unused_and_failed(inputs, tmp_path, fault):
    path = inputs[2]
    body = json.loads(path.read_text())
    # The first GenD row is unused test, the fourth is a failed calib_fit row.
    row = body["rows"][0]
    if fault == "missing":
        body["rows"].pop()
    elif fault == "extra":
        body["rows"].append({**row, "sample_id": "extra", "video_sha256": "f" * 64})
    elif fault in ("dataset", "manifest_sha256", "module"):
        body[fault] = {"dataset": "other", "manifest_sha256": "e" * 64, "module": "face_pad"}[fault]
    elif fault == "cross_split":
        row["subject_id"] = body["rows"][-1]["subject_id"]
    elif fault == "duplicate_video":
        row["video_sha256"] = body["rows"][-1]["video_sha256"]
    elif fault == "label":
        body["rows"][3][fault] = 1
    else:
        row[fault] = {
            "subject_id": "other",
            "split": "calib_ltt",
            "video_sha256": "e" * 64,
            "challenge_sha256": "e" * 64,
        }[fault]
    write(path, body)
    relink(path, inputs[4])
    with pytest.raises(ValueError):
        score(inputs, tmp_path / "rejected.json")


@pytest.mark.parametrize("index", range(1, 5))
def test_mutation_during_prediction_prevents_output(inputs, tmp_path, monkeypatch, index):
    predict = calibration.Calibrator.predict
    path = inputs[index]

    def mutate(self, scores):
        result = predict(self, scores)
        path.write_text(path.read_text() + " ")
        return result

    monkeypatch.setattr(calibration.Calibrator, "predict", mutate)
    output = tmp_path / "no-output.json"
    with pytest.raises(ValueError, match="changed"):
        score(inputs, output)
    assert not output.exists()


@pytest.mark.parametrize(
    "destination",
    ["input", "existing", "configs", "models", "data", "env_models", "env_data", "env_calibrators"],
)
def test_output_guards(inputs, tmp_path, monkeypatch, destination):
    from vericlue_ml.eval import face_candidate as candidate

    repo = tmp_path / "repo"
    monkeypatch.setattr(candidate, "ROOT", repo)
    output = tmp_path / "output.json"
    if destination == "input":
        output = inputs[1]
    elif destination == "existing":
        output.write_text("keep")
    elif destination == "configs":
        output = repo / "ml/configs/new.json"
    elif destination in ("models", "data"):
        output = repo / destination / "new.json"
    else:
        storage = tmp_path / destination
        variable = {
            "env_models": "MODELS_DIR",
            "env_data": "DATA_DIR",
            "env_calibrators": "CALIBRATORS_DIR",
        }[destination]
        monkeypatch.setenv(variable, str(storage))
        output = storage / "new.json"
    before = output.read_bytes() if output.exists() else None
    with pytest.raises(ValueError):
        score(inputs, output)
    assert (output.read_bytes() if output.exists() else None) == before


@pytest.mark.parametrize("commit", ["unknown", COMMIT + "-dirty", "", "g" * 40])
def test_requires_clean_execution_commit(inputs, tmp_path, monkeypatch, commit):
    monkeypatch.setattr(inputs[0], "git_revision", lambda: commit)
    with pytest.raises(ValueError):
        score(inputs, tmp_path / "no-output.json")


def test_cli_only_exposes_calib_fit(inputs, tmp_path, capsys):
    candidate, *paths = inputs
    output = tmp_path / "cli.json"
    flags = ("--pad-report", "--gend-report", "--pad-calibrator", "--gend-calibrator", "--output")
    argv = [
        arg for flag, path in zip(flags, [*paths, output], strict=True) for arg in (flag, str(path))
    ]
    assert candidate.main(argv) == 0
    assert json.loads(output.read_text())["sample_count"] == 10
    with pytest.raises(SystemExit) as exc:
        candidate.main([*argv, "--split", "test"])
    assert exc.value.code == 2
    assert "test" not in {
        row["measurements"]["face_pad"]["split"] for row in json.loads(output.read_text())["rows"]
    }


def test_bounded_snapshot_rejects_oversized_input(inputs, tmp_path):
    with inputs[1].open("ab") as stream:
        stream.write(b" " * (32 * 1024 * 1024))
    with pytest.raises(ValueError, match="32 MiB"):
        score(inputs, tmp_path / "no-output.json")


def test_cli_help_runs_on_windows_default_encoding():
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "cp1252"
    result = subprocess.run(
        [sys.executable, "-m", "vericlue_ml.eval.face_candidate", "--help"],
        capture_output=True,
        env=environment,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr.decode("ascii", errors="replace")
    assert b"--pad-report" in result.stdout
