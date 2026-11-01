"""Offline whole-utterance measurements never grant an eKYC decision."""

import copy
import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.voice import nes2net
from vericlue_ml.voice.asr import SpeechNotFound
from vericlue_ml.voice.nes2net_timeline import Nes2NetTimelineDetector


def timeline(monkeypatch, *, failed=False):
    def vad(x):
        if not np.any(x):
            raise SpeechNotFound("synthetic silence")
        return 0, len(x)

    def logits(x):
        if failed and x[0] > 0.5:
            raise RuntimeError("backend unavailable")
        return [float(x.mean()) * 10, 1]

    monkeypatch.setattr(nes2net, "speech_bounds", vad)
    return Nes2NetTimelineDetector(backend=SimpleNamespace(logits=logits, parity_sha256="a" * 64))


def test_utterance_score_sees_later_window_and_never_becomes_probability(monkeypatch):
    from vericlue_ml.eval.nes2net_utterance import VERSION, aggregate_timeline

    x = np.concatenate([np.full(64000, 0.1), np.full(64000, 0.8)]).astype(np.float32)
    original = timeline(monkeypatch).predict_samples(x)
    result = aggregate_timeline(original, len(x))
    assert result.model_version == VERSION and result.model_version != original.model_version
    assert result.score == pytest.approx(7, abs=1e-5)
    assert original.score is None
    assert result.status == "degraded" and result.gate == "unclear"
    assert result.prob_attack is None and not result.is_usable
    assert len(result.evidence[0].value) == 2


@pytest.mark.parametrize("missing", ["silence", "error"])
def test_any_unmeasured_window_prevents_whole_utterance_score(monkeypatch, missing):
    from vericlue_ml.eval.nes2net_utterance import aggregate_timeline

    first = np.zeros(64000) if missing == "silence" else np.ones(64000)
    x = np.concatenate([first, np.full(64000, 0.1)]).astype(np.float32)
    measured = timeline(monkeypatch, failed=missing == "error").predict_samples(x)
    result = aggregate_timeline(measured, len(x))
    assert result.score is None and result.prob_attack is None
    assert result.status == ("error" if missing == "error" else "degraded")
    assert len(result.evidence[0].value) == 2


def make_manifest(tmp_path):
    sf = pytest.importorskip("soundfile")

    samples = []
    for i, split in enumerate(["calib_fit", "calib_ltt", "test"]):
        for label in (0, 1):
            name = f"{i}-{label}.wav"
            x = np.random.default_rng(i * 2 + label).uniform(-0.2, 0.2, 16000)
            sf.write(tmp_path / name, x, 16000, subtype="PCM_16")
            samples.append(
                dict(
                    sample_id=f"s{i}-{label}",
                    subject_ids=[f"person{i}"],
                    source_group=f"origin{i}",
                    split=split,
                    label=label,
                    attack_type="bonafide" if label == 0 else "tts",
                    audio=name,
                    audio_sha256=hashlib.sha256((tmp_path / name).read_bytes()).hexdigest(),
                    source_dataset="synthetic-unit-fixture",
                    source_revision="v1",
                    rights_reference="Synthetic test signal, not human data",
                    usage="calibration_evaluation",
                )
            )
    manifest = dict(schema_version=1, dataset="synthetic-unit-fixture", samples=samples)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, manifest


@pytest.mark.parametrize(
    "fault",
    [
        "person",
        "source",
        "duplicate_audio",
        "changed_audio",
        "vivos_fit",
        "test_only_fit",
        "path",
        "missing_rights",
    ],
)
def test_manifest_rejects_leakage_unlicensed_and_parity_inputs(tmp_path, fault):
    from vericlue_ml.eval.nes2net_utterance import load_manifest

    path, body = make_manifest(tmp_path)
    samples = body["samples"]
    if fault == "person":
        samples[2]["subject_ids"].append("person0")
    elif fault == "source":
        samples[2]["source_group"] = "origin0"
    elif fault == "duplicate_audio":
        samples[2].update(audio=samples[0]["audio"], audio_sha256=samples[0]["audio_sha256"])
    elif fault == "changed_audio":
        samples[0]["audio_sha256"] = "0" * 64
    elif fault == "vivos_fit":
        samples[0]["source_dataset"] = "AILAB-VNUHCM/vivos"
    elif fault == "test_only_fit":
        samples[0]["usage"] = "test_only"
    elif fault == "path":
        samples[0]["audio"] = "../outside.wav"
    else:
        samples[0]["rights_reference"] = ""
    path.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(ValueError):
        load_manifest(path, tmp_path)


def test_prepare_groups_related_people_and_sources_and_reports_missing_classes(tmp_path):
    from vericlue_ml.eval.nes2net_utterance import audit, load_manifest

    path, _ = make_manifest(tmp_path)
    manifest, checks = load_manifest(path, tmp_path)
    report = audit(manifest, checks)
    assert report["sample_count"] == 6
    assert report["split_counts"] == {
        s: {"bonafide": 1, "attack": 1} for s in ("calib_fit", "calib_ltt", "test")
    }
    assert report["group_count"] == 3
    assert report["calibration_fitted"] is False
    assert report["warnings"]  # Explicitly insufficient sample counts; never a ready artifact.


@pytest.mark.parametrize(
    "fault", ["score", "checkpoint", "manifest", "schema", "parity", "dataset"]
)
def test_collector_keeps_failed_samples_and_fit_does_not_use_test(tmp_path, monkeypatch, fault):
    from vericlue_ml.eval import nes2net_utterance as tool

    path, body = make_manifest(tmp_path)
    detector = timeline(monkeypatch)
    detector.preload = lambda: None
    detector.backend.config = nes2net.Nes2NetBackend().config
    logits = detector.backend.logits
    calls = 0

    def fail_first_window(x):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("model unavailable for this sample")
        return logits(x)

    detector.backend.logits = fail_first_window
    monkeypatch.setattr(tool, "git_revision", lambda: "c" * 40)
    output = tmp_path / "report.json"
    report = tool.collect(path, tmp_path, tmp_path / "models", output, detector=detector)
    monkeypatch.setattr(tool, "git_revision", lambda: "d" * 40)
    assert len(report["rows"]) == 6
    assert all(row["aggregate"].get("prob_attack") is None for row in report["rows"])
    assert report["model_version"] == tool.VERSION
    # Failed/partial rows remain in collection; data fitting never upgrades degraded.
    observed = {}

    def fit(data, **kwargs):
        observed.update(scores=data.scores, subjects=data.subject_ids, labels=data.labels, **kwargs)
        return SimpleNamespace(model_dump=lambda **_: {"synthetic_test": True})

    monkeypatch.setattr(tool, "fit", fit)
    fitted = tool.fit_report(output, tmp_path / "artifact.json")
    assert fitted["excluded_calib_fit"] == {"error": 1}
    assert len(observed["scores"]) == 1 and observed["labels"] == [1]
    assert observed["model_version"] == tool.VERSION
    assert observed["commit"] == "d" * 40
    assert fitted["measurement_commit"] == "c" * 40
    bad = copy.deepcopy(report)
    if fault == "score":
        bad["rows"][0]["aggregate"]["score"] = 1000
    elif fault == "checkpoint":
        bad["checkpoint_sha256"] = "0" * 64
    elif fault == "manifest":
        bad.pop("manifest_sha256")
    elif fault == "schema":
        bad["schema_version"] = 0
    elif fault == "parity":
        bad["parity_report_sha256"] = "z" * 64
    else:
        bad["dataset"] = "AILAB-VNUHCM/vivos"
    output.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        tool.fit_report(output, tmp_path / "tampered.json")


def test_fit_refuses_report_changed_during_fitting(tmp_path, monkeypatch):
    from vericlue_ml.eval import nes2net_utterance as tool

    path, _ = make_manifest(tmp_path)
    detector = timeline(monkeypatch)
    detector.preload = lambda: None
    detector.backend.config = nes2net.Nes2NetBackend().config
    monkeypatch.setattr(tool, "git_revision", lambda: "c" * 40)
    output = tmp_path / "report.json"
    tool.collect(path, tmp_path, tmp_path / "models", output, detector=detector)

    def changed_report(*args, **kwargs):
        output.write_text("{}", encoding="utf-8")
        return SimpleNamespace(model_dump=lambda **_: {"synthetic_test": True})

    monkeypatch.setattr(tool, "fit", changed_report)
    with pytest.raises(ValueError):
        tool.fit_report(output, tmp_path / "must-not-exist.json")
    assert not (tmp_path / "must-not-exist.json").exists()
