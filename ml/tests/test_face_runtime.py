"""Diagnostic reporting, failure isolation and output protection without native weights."""

import json
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.eval import face_runtime


def fake_backends(monkeypatch, broken=None):
    closed = []
    reader = SimpleNamespace(
        preload=lambda **kwargs: None,
        observe=lambda *args, **kwargs: SimpleNamespace(face_count=0),
        close=lambda: closed.append(True),
        expected_sha256="a" * 64,
    )
    matcher = SimpleNamespace(
        version="synthetic-lvface@unit",
        preload=lambda **kwargs: None,
        finder=SimpleNamespace(find=lambda frame: []),
        embedder=SimpleNamespace(
            embed=lambda tensor: np.ones(512) / np.sqrt(512),
            session=SimpleNamespace(get_providers=lambda: ["CPUExecutionProvider"]),
        ),
    )

    def detector(name):
        def score(batch):
            if name == broken:
                raise RuntimeError("private/biometric/path")
            return [0.25]

        return SimpleNamespace(
            version=f"synthetic-{name}@unit",
            preload=lambda **kwargs: None,
            _classifier=SimpleNamespace(p_fake=score, device="cpu"),
        )

    monkeypatch.setattr(face_runtime, "FaceObservationReader", lambda: reader)
    monkeypatch.setattr(face_runtime, "FaceMatchDetector", lambda: matcher)
    monkeypatch.setattr(face_runtime, "FaceDeepfakeDetector", lambda: detector("gend"))
    monkeypatch.setattr(face_runtime, "FsvfmPadDetector", lambda: detector("pad"))
    monkeypatch.setattr(face_runtime, "_manifest_entry", lambda *args: {"sha256": "b" * 64})
    return closed


def test_all_backends_report_without_embeddings_or_synthetic_attack_scores(monkeypatch, tmp_path):
    closed = fake_backends(monkeypatch)
    # A valid elapsed time may equal the fake score; text searches confuse the two.
    ticks = iter([0.0, 0.00025] * 4)
    monkeypatch.setattr(face_runtime, "perf_counter", lambda: next(ticks))
    result = face_runtime.check_backends(tmp_path)
    assert result["all_backends_ok"] and closed == [True]
    assert set(result["checks"]) == {"landmarker", "face_match", "face_deepfake", "face_pad"}
    assert result["checks"]["face_match"]["output_shape"] == [512]
    common = {"status", "diagnostic_elapsed_ms", "model_sha256"}
    classifier = {"model_version", "finite_output", "device"}
    expected = {
        "landmarker": common | {"face_count", "covers_modules"},
        "face_match": common | classifier | {"output_shape", "providers"},
        "face_deepfake": common | classifier,
        "face_pad": common | classifier,
    }
    for name, row in result["checks"].items():
        # Exact public fields forbid embedding/score output without banning timings.
        assert set(row) == expected[name]
        assert row["diagnostic_elapsed_ms"] == 0.25


@pytest.mark.parametrize("broken", ["gend", "pad"])
def test_backend_error_keeps_other_results_and_closes_reader(monkeypatch, tmp_path, broken):
    closed = fake_backends(monkeypatch, broken)
    result = face_runtime.check_backends(tmp_path)
    assert result["all_backends_ok"] is False and closed == [True]
    failed = "face_deepfake" if broken == "gend" else "face_pad"
    assert result["checks"][failed]["status"] == "error"
    assert sum(row["status"] == "ok" for row in result["checks"].values()) == 3
    assert "private/" not in json.dumps(result)


def test_cli_report_marks_zero_biometric_samples_and_returns_error_code(monkeypatch, tmp_path):
    monkeypatch.setattr(
        face_runtime,
        "check_backends",
        lambda root, **kwargs: {"all_backends_ok": False, "checks": {}},
    )
    monkeypatch.setattr(face_runtime, "runtime_versions", lambda: {"torch": "synthetic-cpu@unit"})
    monkeypatch.setattr(face_runtime, "git_revision", lambda: "unit-commit-dirty")
    report = tmp_path / "report.json"
    assert (
        face_runtime.main(["--models-dir", str(tmp_path / "models"), "--output", str(report)]) == 1
    )
    body = json.loads(report.read_text(encoding="utf-8"))
    assert body["sample_count"] == 0 and body["dirty"] is True
    assert body["dataset"] == "synthetic_constant_tensors_not_biometric_evaluation"


def test_cli_cannot_overwrite_model_files(monkeypatch, tmp_path):
    model = tmp_path / "models" / "model.json"
    model.parent.mkdir()
    model.write_text("preserve model")
    monkeypatch.setattr(
        face_runtime, "check_backends", lambda root: pytest.fail("must reject before load")
    )
    with pytest.raises(SystemExit) as error:
        face_runtime.main(["--models-dir", str(model.parent), "--output", str(model)])
    assert error.value.code == 2 and model.read_text() == "preserve model"
