"""Readiness is a structural diagnostic, never calibration or permission to pass."""

import hashlib
import json

import numpy as np
import pytest
from test_nes2net_utterance import timeline

from vericlue_ml.eval import nes2net_utterance as tool
from vericlue_ml.voice import nes2net


def sample(index, label, *, subjects=None, split="calib_fit", attack_type="tts"):
    return tool.Sample(
        sample_id=f"s{index}",
        subject_ids=subjects or [f"person{index}"],
        source_group=f"source{index}",
        split=split,
        label=label,
        attack_type=attack_type if label else "bonafide",
        audio=f"synthetic-{index}.wav",
        audio_sha256=hashlib.sha256(f"file-{index}".encode()).hexdigest(),
        source_dataset="synthetic-unit-fixture",
        source_revision="v1",
        rights_reference="Synthetic test signal; no human recording",
        usage="calibration_evaluation",
    )


def manifest_checks(samples):
    manifest = tool.Manifest(schema_version=1, dataset="synthetic-unit-fixture", samples=samples)
    checks = [
        {
            "pcm_sha256": hashlib.sha256(f"pcm-{s.sample_id}".encode()).hexdigest(),
            "input_samples": 64000,
        }
        for s in samples
    ]
    groups = tool._partition(samples, checks)
    for s, check in zip(samples, checks, strict=True):
        check["group_id"] = groups[s.sample_id]
    return manifest, checks


def report_fixture(tmp_path, monkeypatch, samples, *, failed=()):
    manifest, checks = manifest_checks(samples)
    detector = timeline(monkeypatch, failed=True)
    rows = []
    for s, check in zip(samples, checks, strict=True):
        pcm = np.full(64000, 1.0 if s.sample_id in failed else 0.1, dtype=np.float32)
        measured = detector.predict_samples(pcm)
        rows.append(
            {
                "sample": s.model_dump(),
                **check,
                "timeline": measured.to_contract(),
                "aggregate": tool.aggregate_timeline(measured, len(pcm)).to_contract(),
            }
        )
    config = nes2net.Nes2NetBackend().config
    body = {
        "schema_version": 1,
        "protocol": tool.PROTOCOL,
        "model_version": tool.VERSION,
        "source_commit": "c" * 40,
        "manifest_sha256": "b" * 64,
        "manifest": manifest.model_dump(),
        "dataset": manifest.dataset,
        "checkpoint_sha256": config["sha256"],
        "parity_report_sha256": "a" * 64,
        "numerical_binding": tool.implementation_identity(config),
        "runtime": {"synthetic_test": True},
        "sample_count": len(rows),
        "audit": tool.audit(manifest, checks),
        "rows": rows,
    }
    path = tmp_path / "measurements.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    monkeypatch.setattr(tool, "git_revision", lambda: "d" * 40)

    def forbidden_fit(*args, **kwargs):
        pytest.fail("Readiness must not fit a calibrator")

    monkeypatch.setattr(tool, "fit", forbidden_fit)
    return path, body


def balanced_samples():
    return [sample(i, i % 2, subjects=[f"person{i // 2}"]) for i in range(4)]


def test_both_classes_do_not_make_single_attack_group_cv_feasible():
    samples = [
        sample(0, 0, subjects=["a"]),
        sample(1, 1, subjects=["a", "b"]),
        sample(2, 1, subjects=["b"]),
        sample(3, 0, subjects=["c"]),
    ]
    report = tool.audit(*manifest_checks(samples))
    assert report["split_group_counts"]["calib_fit"] == 2
    assert report["cv"]["both_classes"] is True
    assert report["cv"]["n_splits"] == 2
    assert report["cv"]["train_folds_have_both_classes"] is False
    assert report["cv"]["feasible"] is False
    assert report["cv"]["reasons"]


def test_expected_attack_types_are_explicit_and_test_does_not_define_them():
    samples = balanced_samples() + [sample(4, 1, split="test", attack_type="unseen")]
    manifest, checks = manifest_checks(samples)
    default = tool.audit(manifest, checks)
    assert default["expected_attack_types"] == []
    assert all(types == [] for types in default["missing_attack_types"].values())
    explicit = tool.audit(manifest, checks, expected_attack_types=("tts", "replay"))
    assert explicit["split_attack_type_counts"]["calib_fit"] == {"tts": 2}
    assert explicit["missing_attack_types"]["calib_fit"] == ["replay"]
    assert set(explicit["missing_attack_types"]["calib_ltt"]) == {"tts", "replay"}
    assert "unseen" not in explicit["expected_attack_types"]
    assert explicit["cv"]["feasible"] is True
    assert explicit["isotonic_sample_eligible"] is False
    assert explicit["structural_only"] is True
    assert explicit["calibration_ready"] is False


def test_excluded_bridge_does_not_split_original_connected_groups(tmp_path, monkeypatch):
    samples = [
        sample(0, 0, subjects=["a"]),
        sample(1, 1, subjects=["b"]),
        sample(2, 0, subjects=["a", "b"]),
    ]
    path, _ = report_fixture(tmp_path, monkeypatch, samples, failed=("s2",))
    result = tool.readiness_report(path, tmp_path / "readiness.json")
    assert result["declared"]["split_group_counts"]["calib_fit"] == 1
    assert result["usable"]["sample_count"] == 2
    assert result["usable"]["cv"]["both_classes"] is True
    assert result["usable"]["cv"]["groups"] == 1
    assert result["usable"]["cv"]["feasible"] is False


def test_excluding_only_attack_group_reports_class_and_type_loss(tmp_path, monkeypatch):
    samples = [sample(0, 0), sample(1, 0), sample(2, 1)]
    path, _ = report_fixture(tmp_path, monkeypatch, samples, failed=("s2",))
    result = tool.readiness_report(
        path, tmp_path / "readiness.json", expected_attack_types=("tts",)
    )
    assert result["declared"]["cv"]["both_classes"] is True
    assert result["usable"]["cv"]["both_classes"] is False
    assert result["usable"]["cv"]["feasible"] is False
    assert result["usable"]["missing_attack_types"]["calib_fit"] == ["tts"]
    assert result["excluded"]["calib_fit"] == {
        "count": 1,
        "by_status": {"error": 1},
        "by_class": {"bonafide": 0, "attack": 1},
        "by_attack_type": {"tts": 1},
    }


def test_all_unusable_rows_produce_diagnostic_with_no_readiness(tmp_path, monkeypatch):
    samples = balanced_samples()
    path, _ = report_fixture(
        tmp_path, monkeypatch, samples, failed=tuple(s.sample_id for s in samples)
    )
    result = tool.readiness_report(path, tmp_path / "readiness.json")
    assert result["usable"]["sample_count"] == 0
    assert result["usable"]["group_count"] == 0
    assert result["usable"]["cv"]["n_splits"] == 0
    assert result["usable"]["cv"]["feasible"] is False
    assert result["excluded"]["calib_fit"]["count"] == 4
    assert result["calibration_ready"] is False


def test_readiness_binds_report_and_commit_without_mutation_or_fit(tmp_path, monkeypatch):
    path, body = report_fixture(tmp_path, monkeypatch, balanced_samples())
    before = path.read_bytes()
    output = tmp_path / "readiness.json"
    result = tool.readiness_report(path, output)
    assert result == json.loads(output.read_text("utf-8"))
    assert result["schema_version"] == 1
    assert result["dataset"] == body["dataset"]
    assert result["measurement_report_sha256"] == hashlib.sha256(before).hexdigest()
    assert result["measurement_commit"] == "c" * 40
    assert result["audit_commit"] == "d" * 40
    assert result["model_version"] == tool.VERSION
    assert result["usable"]["cv"]["feasible"] is True
    assert result["calibration_fitted"] is False
    assert result["calibration_ready"] is False
    assert result["deployed"] is False
    assert path.read_bytes() == before
    assert all(row["aggregate"]["status"] == "degraded" for row in body["rows"])
    assert all(row["aggregate"].get("prob_attack") is None for row in body["rows"])


@pytest.mark.parametrize("fault", ["group", "status", "aggregation"])
def test_readiness_refuses_unvalidated_measurements(tmp_path, monkeypatch, fault):
    path, body = report_fixture(tmp_path, monkeypatch, balanced_samples())
    if fault == "group":
        body["rows"][0]["group_id"] = "forged-independent-group"
    elif fault == "status":
        body["rows"][0]["aggregate"]["status"] = "ok"
    else:
        body["rows"][0]["aggregate"]["score"] += 1
    path.write_text(json.dumps(body), encoding="utf-8")
    output = tmp_path / "must-not-exist.json"
    with pytest.raises(ValueError):
        tool.readiness_report(path, output)
    assert not output.exists()


def test_readiness_cli_does_not_overwrite_existing_report(tmp_path, monkeypatch):
    path, _ = report_fixture(tmp_path, monkeypatch, balanced_samples())
    output = tmp_path / "readiness.json"
    output.write_text("reviewed output", encoding="utf-8")
    with pytest.raises(ValueError):
        tool.main(["readiness", "--report", str(path), "--output", str(output)])
    assert output.read_text("utf-8") == "reviewed output"
