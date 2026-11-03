"""Offline candidate pins and shared ASR behavior without checkpoints or inference."""

import numpy as np
import pytest
import yaml

from vericlue_ml.eval import dnu_asr_fit
from vericlue_ml.voice import qwen_asr
from vericlue_ml.voice.asr import ASRError, generation_token_budget

REVISION = "bcd2b5b7f32b480ab5790554cfa8347f246a14f3"
VERSION = f"qwen3-asr-17b@{REVISION}+cpu-fp32-content-v2-assistant-prefix"
WEIGHT_SHA256 = "2db53c7d81bd9b8cbc6a074e89be2c968a0d373fb4ee68bb1b1e14f7042dfee1"


def candidate_class():
    from vericlue_ml.eval.qwen17_asr import Qwen17ASR

    return Qwen17ASR


def test_default_runtime_still_rejects_the_candidate_revision(monkeypatch, tmp_path):
    config = {
        "revision": REVISION,
        "sha256": dict.fromkeys(qwen_asr.RUNTIME_FILES, "0" * 64),
        "cpu_threads": 4,
        "model_subdir": ".",
    }
    path = tmp_path / "candidate-as-production.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setenv("QWEN_ASR_CONFIG", str(path))
    with pytest.raises(ASRError, match="Unsupported Qwen ASR configuration"):
        qwen_asr.QwenASR(tmp_path)


def test_offline_candidate_has_immutable_pins_and_ignores_production_override(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("QWEN_ASR_CONFIG", str(tmp_path / "must-not-open.yaml"))
    candidate = candidate_class()(tmp_path)
    assert candidate.version == VERSION and candidate.version != qwen_asr.VERSION
    assert candidate.config["repo"] == "Qwen/Qwen3-ASR-1.7B-hf"
    assert candidate.config["revision"] == REVISION
    assert candidate.config["model_subdir"] == "." and candidate.config["cpu_threads"] == 4
    assert set(candidate.config["sha256"]) == qwen_asr.RUNTIME_FILES
    assert candidate.config["sha256"]["model.safetensors"] == WEIGHT_SHA256
    assert (
        candidate.config["sha256"]["config.json"]
        == "117ac8e63e2af7cae3665e5a632d6eb03f5f384915519ceb6403c15ec6533f63"
    )
    with pytest.raises(TypeError):
        candidate.config["revision"] = "unapproved"
    with pytest.raises(TypeError):
        candidate.config["sha256"]["model.safetensors"] = "0" * 64


def test_candidate_reuses_exact_native_preprocessing_decoder_and_detector_version(tmp_path):
    cls = candidate_class()
    for name in (
        "_verify",
        "preload",
        "_load_native",
        "_infer",
        "transcribe",
        "transcribe_samples",
    ):
        assert getattr(cls, name) is getattr(qwen_asr.QwenASR, name)
    candidate = cls(tmp_path)
    detector = qwen_asr.QwenVoiceChallengeDetector(candidate)
    assert detector.version == VERSION


def test_candidate_file_path_uses_the_existing_vad_and_count_only_budget(monkeypatch, tmp_path):
    cls = candidate_class()
    candidate = cls(tmp_path)
    path = tmp_path / "synthetic.wav"
    path.write_bytes(b"synthetic fixture")
    original = np.zeros(18000, np.float32)
    trimmed = original[1000:-1000]
    calls = []
    monkeypatch.setattr(
        qwen_asr, "load_audio", lambda source, **kw: calls.append(("load", source, kw)) or original
    )
    monkeypatch.setattr(
        qwen_asr, "trim_silence", lambda audio, **kw: calls.append(("vad", audio, kw)) or trimmed
    )
    monkeypatch.setattr(
        cls,
        "_infer",
        lambda self, audio, **kw: calls.append(("infer", audio, kw)) or "synthetic transcript",
    )
    assert candidate.transcribe(path, expected_syllable_count=14) == "synthetic transcript"
    assert calls[0] == ("load", path, {"max_seconds": 30})
    assert calls[1][0] == "vad" and calls[1][1] is original and calls[1][2] == {"mode": 1}
    assert calls[2][0] == "infer" and calls[2][1] is trimmed
    assert calls[2][2] == {"token_budget": max(64, generation_token_budget(14))}


def test_candidate_integrity_failure_precedes_native_import(monkeypatch, tmp_path):
    cls = candidate_class()
    for name in qwen_asr.RUNTIME_FILES:
        (tmp_path / name).write_bytes(b"invalid fixture")
    monkeypatch.setattr(
        cls, "_load_native", lambda *_: pytest.fail("Invalid candidate must never load")
    )
    with pytest.raises(ASRError, match="Cannot load verified local Qwen ASR"):
        cls(tmp_path).preload()


def test_fit_backend_has_the_candidate_version_and_same_content_detector(tmp_path):
    assert dnu_asr_fit.VERSIONS.get("qwen17") == VERSION
    detector = dnu_asr_fit._detector("qwen17", tmp_path)
    assert type(detector) is qwen_asr.QwenVoiceChallengeDetector
    assert type(detector.asr) is candidate_class()
    assert detector.version == VERSION


def test_fit_verifies_candidate_pins_and_records_adapter_source(monkeypatch, tmp_path):
    cls = candidate_class()
    calls = []

    def verify(self):
        calls.append(self.models_dir)
        self.model_hashes = {"model.safetensors": WEIGHT_SHA256}
        return self.models_dir

    monkeypatch.setattr(cls, "_verify", verify)
    result = dnu_asr_fit.verify_models("qwen17", tmp_path)
    assert calls == [tmp_path]
    assert result == {
        "verified": True,
        "revision": REVISION,
        "file_sha256": {"model.safetensors": WEIGHT_SHA256},
    }
    sources = dnu_asr_fit._source_provenance()
    assert "ml/src/vericlue_ml/eval/qwen17_asr.py" in sources
    assert len(sources["ml/src/vericlue_ml/eval/qwen17_asr.py"]) == 64
