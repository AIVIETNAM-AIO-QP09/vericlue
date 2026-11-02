"""Synthetic local manifests only; never model accuracy or real calibration artifacts."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.result import ErrorCode, ModuleResult
from vericlue_ml.eval import session_calibration as sc
from vericlue_ml.presence.landmarks import LandmarkError


def write_manifest(root):
    rows = []
    for i in range(8):
        (root / f"{i}.mp4").write_bytes(f"synthetic-video-{i}".encode())
        body = {
            "session_id": f"ses_{i}",
            "challenge": {
                "challenge_id": f"ch_{i}",
                "dynamic": {
                    "version": 1,
                    "session_id": f"ses_{i}",
                    "head_start_at_ms": 12000,
                    "head_duration_ms": 6000,
                    "head_turns": ["left", "right", "center"],
                    "frontal_capture_at_ms": 1000,
                },
            },
        }
        (root / f"{i}.json").write_text(json.dumps(body), encoding="utf-8")
        rows.append(
            dict(
                sample_id=f"s{i}",
                subject_id=f"g{i // 2}",
                split="calib_fit",
                label=i % 2,
                video=f"{i}.mp4",
                server_response=f"{i}.json",
            )
        )
    payload = dict(schema_version=1, dataset="synthetic-unit-only", samples=rows)
    path = root / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, payload


@pytest.mark.parametrize(
    "kind",
    [
        "group-leak",
        "duplicate-id",
        "duplicate-video",
        "absolute",
        "escape",
        "label",
        "split",
        "missing-context",
    ],
)
def test_manifest_rejects_bad_provenance_before_loading_any_model(tmp_path, kind):
    path, payload = write_manifest(tmp_path)
    row = payload["samples"][1]
    if kind == "group-leak":
        row["split"] = "test"
    elif kind == "duplicate-id":
        row["sample_id"] = "s0"
    elif kind == "duplicate-video":
        row["video"] = "0.mp4"
    elif kind == "absolute":
        row["video"] = str((tmp_path / "1.mp4").resolve())
    elif kind == "escape":
        row["video"] = "../escape.mp4"
    elif kind == "label":
        row["label"] = True
    elif kind == "split":
        row["split"] = "train"
    else:
        (tmp_path / "1.json").write_text("{}", encoding="utf-8")
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        sc.load_manifest(path, tmp_path)


def fake_runtime(monkeypatch, *, fail=False, changed=False):
    frames = {
        role: np.full((2, 2, 3), i, np.uint8) for i, role in enumerate(("front", "left", "right"))
    }

    class Backend:
        name = "face_pad"
        frames_version = "synthetic-views"

        def preload(self, **kwargs):
            pass

        def predict_frames(self, inp, actual):
            assert actual is frames
            if changed:
                inp.video.write_bytes(b"changed")
            return ModuleResult(
                module="face_pad",
                model_version=self.frames_version,
                status="ok",
                score=0.1 if int(inp.video.stem) % 2 == 0 else 0.9,
                latency_ms=0,
            )

    reader = SimpleNamespace(close=lambda: None, preload=lambda **_: None)
    monkeypatch.setattr(sc, "make_runtime", lambda *_: (Backend(), reader))
    monkeypatch.setattr(sc, "git_revision", lambda: "1" * 40)

    def views(inp, _):
        if fail and inp.video.stem == "0":
            raise LandmarkError(ErrorCode.E_NO_FACE)
        return frames, hashlib.sha256(inp.video.read_bytes()).hexdigest()

    monkeypatch.setattr(sc, "session_views", views)


def test_collect_preserves_failures_and_exact_version_without_exporting_pixels(
    monkeypatch, tmp_path
):
    path, _ = write_manifest(tmp_path)
    fake_runtime(monkeypatch, fail=True)
    report = sc.collect(path, tmp_path, tmp_path / "models", "face_pad", tmp_path / "out.json")
    assert len(report["rows"]) == 8
    assert report["rows"][0]["status"] != "ok" and report["rows"][0]["score"] is None
    assert report["model_version"] == "synthetic-views+session-video-v1"
    assert report["rows"][1]["score"] == 0.9
    assert "pixels" not in json.dumps(report) and "embedding" not in json.dumps(report)


def test_changed_video_does_not_keep_a_score(monkeypatch, tmp_path):
    path, _ = write_manifest(tmp_path)
    fake_runtime(monkeypatch, changed=True)
    report = sc.collect(path, tmp_path, tmp_path / "models", "face_pad", tmp_path / "out.json")
    assert all(r["score"] is None and r["status"] != "ok" for r in report["rows"])


@pytest.mark.parametrize("target", ["manifest.json", "0.mp4", "models/out.json"])
def test_collect_cannot_overwrite_input_or_model_storage(monkeypatch, tmp_path, target):
    path, _ = write_manifest(tmp_path)
    fake_runtime(monkeypatch)
    with pytest.raises(ValueError):
        sc.collect(path, tmp_path, tmp_path / "models", "face_pad", tmp_path / target)


def test_fit_uses_only_calib_fit_and_keeps_counts(monkeypatch, tmp_path):
    path, payload = write_manifest(tmp_path)
    for i in (6, 7):
        payload["samples"][i]["split"] = "test"
    path.write_text(json.dumps(payload), encoding="utf-8")
    fake_runtime(monkeypatch)
    report = tmp_path / "report.json"
    sc.collect(path, tmp_path, tmp_path / "models", "face_pad", report)
    result = sc.fit_report(report, tmp_path / "calibrators", n_splits=3)
    assert result["n_pos"] == result["n_neg"] == 3
    assert result["model_version"].endswith("+session-video-v1")
    assert Path(result["artifact"]).is_file()
    with pytest.raises(ValueError):
        sc.fit_report(report, tmp_path / "calibrators", n_splits=3)


@pytest.mark.parametrize(
    "kind", ["leak-in-failed", "legacy-version", "missing-provenance", "no-class"]
)
def test_fit_rejects_corrupt_or_ineligible_report(monkeypatch, tmp_path, kind):
    path, _ = write_manifest(tmp_path)
    fake_runtime(monkeypatch)
    report_path = tmp_path / "report.json"
    data = sc.collect(path, tmp_path, tmp_path / "models", "face_pad", report_path)
    if kind == "leak-in-failed":
        data["rows"][1].update(split="test", status="error", error_code="E_INTERNAL", score=None)
    elif kind == "legacy-version":
        data["model_version"] = "legacy"
    elif kind == "missing-provenance":
        data.pop("manifest_sha256")
    else:
        for row in data["rows"]:
            row["label"] = 0
    report_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        sc.fit_report(report_path, tmp_path / "calibrators", n_splits=3)


def test_collect_records_effective_model_manifest_override(monkeypatch, tmp_path):
    path, _ = write_manifest(tmp_path)
    fake_runtime(monkeypatch)
    custom = tmp_path / "weights-manifest.yaml"
    custom.write_text("synthetic-custom-manifest", encoding="utf-8")
    monkeypatch.setenv("ML_MODELS_MANIFEST", str(custom))
    report = sc.collect(path, tmp_path, tmp_path / "models", "face_pad", tmp_path / "out.json")
    assert report["model_manifest_sha256"] == hashlib.sha256(custom.read_bytes()).hexdigest()


def test_model_manifest_change_during_measurement_discards_report(monkeypatch, tmp_path):
    path, _ = write_manifest(tmp_path)
    fake_runtime(monkeypatch)
    custom = tmp_path / "weights-manifest.yaml"
    custom.write_text("synthetic-before", encoding="utf-8")
    monkeypatch.setenv("ML_MODELS_MANIFEST", str(custom))
    factory = sc.make_runtime

    def runtime(*args):
        backend, reader = factory(*args)
        original = backend.predict_frames

        def changed(*args):
            custom.write_text("synthetic-changed", encoding="utf-8")
            return original(*args)

        backend.predict_frames = changed
        return backend, reader

    monkeypatch.setattr(sc, "make_runtime", runtime)
    output = tmp_path / "out.json"
    with pytest.raises(ValueError):
        sc.collect(path, tmp_path, tmp_path / "models", "face_pad", output)
    assert not output.exists()
