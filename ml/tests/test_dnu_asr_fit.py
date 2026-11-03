"""Fit-only ASR protocol and failure accounting without checkpoints or inference."""

import csv
import hashlib
import json
import wave
from pathlib import Path

import pytest

from vericlue_ml.eval import dnu_asr_fit as evaluation
from vericlue_ml.voice.asr import ASRError
from vericlue_ml.voice.challenge import VoiceChallengeDetector, normalize_text

TEXT = "tôi xác nhận thuyền đường thuyền đường mã không không không không không không"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def protocol(tmp_path):
    data = tmp_path / "dataset"
    train = data / "source/data/train"
    train.mkdir(parents=True)
    rows, metadata = [], []
    for person in range(1, 19):
        speaker = f"speaker{person:03}"
        for number in range(20):
            sample = f"{speaker}_{number:04}"
            filename = f"audio/{speaker}/{sample}.wav"
            relative = "DNU-ViSpeech/data/train/" + filename
            audio = data / relative
            audio.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(audio), "wb") as wav:
                wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                wav.writeframes(bytes(32000))
            checksum = digest(audio)
            rows.append(
                {
                    "sample_id": "DNU:" + sample,
                    "subject_ids": ["DNU:" + speaker],
                    "source_group": "DNU:" + sample,
                    "split": "calib_fit",
                    "label": 0,
                    "attack_type": "bonafide",
                    "audio": relative,
                    "audio_sha256": checksum,
                    "source_dataset": evaluation.REPOSITORY,
                    "source_revision": evaluation.REVISION,
                }
            )
            metadata.append(
                {
                    "audio_id": sample,
                    "speaker_id": speaker,
                    "file_name": filename,
                    "checksum_sha256": checksum,
                    "text_normalized": TEXT,
                    "split": "train",
                    "review_status": "accepted",
                    "qc_status": "passed",
                    "sample_rate": "16000",
                    "num_channels": "1",
                    "duration": "1",
                }
            )
    manifest = data / "manifest.json"
    manifest.write_text(
        json.dumps({"schema_version": 1, "dataset": evaluation.DATASET, "samples": rows})
    )
    metadata_path = train / "metadata.csv"
    with metadata_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=metadata[0].keys())
        writer.writeheader()
        writer.writerows(metadata)
    (data / "source/LICENSE").write_text("CC BY-NC 4.0")
    (data / "source/PUBLIC_RELEASE_APPROVAL.md").write_text("Synthetic approval fixture")
    selected = []
    for person in range(1, 19):
        candidates = rows[(person - 1) * 20 : person * 20]
        selected.append(
            min(
                candidates,
                key=lambda r: hashlib.sha256(
                    (evaluation.SEED + r["sample_id"]).encode()
                ).hexdigest(),
            )
        )
    body = {
        "protocol": evaluation.PROTOCOL,
        "selection_seed": evaluation.SEED,
        "dataset": evaluation.DATASET,
        "source_revision": evaluation.REVISION,
        "manifest_sha256": digest(manifest),
        "train_metadata_sha256": digest(metadata_path),
        "license_sha256": digest(data / "source/LICENSE"),
        "approval_sha256": digest(data / "source/PUBLIC_RELEASE_APPROVAL.md"),
        "train_manifest_rows": 360,
        "sample_count": 18,
        "subject_count": 18,
        "heldout_audio_or_metadata_read": False,
        "labels_not_model_context": True,
        "fixed_thresholds": True,
        "fit_or_threshold_install": False,
        "private_samples": selected,
        "data_root": str(data),
    }
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(body))
    return path, body


class FakeASR:
    version = "fake-asr@test"

    def __init__(self, failure=None):
        self.loads, self.calls = 0, []
        self.failure = failure

    def preload(self, **kwargs):
        self.loads += 1

    def transcribe(self, path, *, expected_syllable_count):
        self.calls.append((path, expected_syllable_count))
        if self.failure and len(self.calls) == 1:
            raise self.failure
        return TEXT


def test_collect_uses_one_load_count_only_asr_and_all_failure_denominators(
    protocol, tmp_path, monkeypatch
):
    path, _ = protocol
    monkeypatch.setattr(evaluation, "verify_models", lambda *args: {"verified": True})
    monkeypatch.setattr(evaluation, "git_revision", lambda: "f" * 40)
    asr = FakeASR(ASRError("PRIVATE_NATIVE_ERROR"))
    output = tmp_path / "result.json"
    report = evaluation.collect(
        path,
        digest(path),
        "phowhisper",
        tmp_path / "models",
        output,
        detector=VoiceChallengeDetector(asr),
    )
    assert asr.loads == 1 and len(asr.calls) == 18
    assert {count for _, count in asr.calls} == {len(normalize_text(TEXT).split())}
    assert report["overall"]["sample_count"] == 18
    assert report["overall"]["status_counts"] == {"error": 1, "ok": 17}
    assert report["overall"]["nonpass_count"] == 1
    assert report["overall"]["nonpass_denominator"] == 18
    assert report["overall"]["wer_available_count"] == 17
    assert report["overall"]["wer_unavailable_count"] == 1
    assert len(report["speaker_aggregates"]) == 18
    serialized = output.read_text()
    assert TEXT not in serialized and "PRIVATE_NATIVE_ERROR" not in serialized
    assert "speaker001" not in serialized and "DNU:" not in serialized
    assert str(tmp_path) not in serialized


@pytest.mark.parametrize(
    "fault", ["heldout", "selection", "receipt", "source", "join", "wav", "protocol_hash"]
)
def test_protocol_rejects_bad_provenance_before_detector_load(protocol, fault):
    path, body = protocol
    expected = digest(path)
    if fault == "heldout":
        body["private_samples"][0]["split"] = "test"
    elif fault == "selection":
        body["private_samples"][0] = body["private_samples"][1]
    elif fault == "receipt":
        body["license_sha256"] = "0" * 64
    elif fault == "source":
        body["source_revision"] = "0" * 40
    elif fault == "join":
        meta = Path(body["data_root"]) / "source/data/train/metadata.csv"
        meta.write_text(
            meta.read_text(encoding="utf-8-sig").replace("accepted", "rejected", 1),
            encoding="utf-8-sig",
        )
        body["train_metadata_sha256"] = digest(meta)
    elif fault == "wav":
        audio = Path(body["data_root"]) / body["private_samples"][0]["audio"]
        audio.write_bytes(b"changed")
    path.write_text(json.dumps(body))
    if fault != "protocol_hash":
        expected = digest(path)
    else:
        path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError):
        evaluation.load_protocol(path, expected)


def test_changed_audio_during_inference_remains_nonpass(protocol, tmp_path, monkeypatch):
    path, _ = protocol
    monkeypatch.setattr(evaluation, "verify_models", lambda *args: {"verified": True})
    monkeypatch.setattr(evaluation, "git_revision", lambda: "f" * 40)

    class ChangedASR(FakeASR):
        def transcribe(self, audio, *, expected_syllable_count):
            result = super().transcribe(audio, expected_syllable_count=expected_syllable_count)
            if len(self.calls) == 1:
                audio.write_bytes(b"modified while reading")
            return result

    report = evaluation.collect(
        path,
        digest(path),
        "phowhisper",
        tmp_path / "models",
        tmp_path / "result.json",
        detector=VoiceChallengeDetector(ChangedASR()),
    )
    assert report["overall"]["nonpass_count"] == 1
    assert report["overall"]["error_code_counts"]["E_INTEGRITY"] == 1


def test_model_verifier_rejects_wrong_weights_without_loading_torch(tmp_path, monkeypatch):
    model = tmp_path / "models/phowhisper"
    model.mkdir(parents=True)
    weight = model / "pytorch_model.bin"
    weight.write_bytes(b"synthetic weights")
    entry = {
        "source": {"revision": evaluation.PHOWHISPER_REVISION},
        "license": "BSD-3-Clause",
        "license_status": "verified",
        "files": [{"path": weight.name, "size_bytes": weight.stat().st_size, "sha256": "0" * 64}],
    }
    monkeypatch.setattr(evaluation, "phowhisper_manifest_entry", lambda: entry)
    with pytest.raises(ValueError):
        evaluation.verify_models("phowhisper", tmp_path / "models")


def test_error_bearing_result_cannot_count_as_pass_or_zero_wer():
    row = evaluation._measurement(
        {
            "status": "ok",
            "gate": "pass",
            "error_code": "E_INTERNAL",
            "quality": {"syllable_error_rate": 0.0, "unaccented_similarity": 1.0},
        },
        1,
    )
    assert row["nonpass"] is True and row["wer"] is None


def test_runtime_provenance_reads_package_metadata_without_importing_models(monkeypatch):
    monkeypatch.setattr(evaluation.metadata, "version", lambda name: "test-version")
    result = evaluation.runtime_provenance()
    assert result["python"] and result["torch"] == "test-version"
    assert set(result) == {
        "python",
        "torch",
        "transformers",
        "tokenizers",
        "safetensors",
        "numpy",
        "scipy",
        "soundfile",
        "webrtcvad-wheels",
        "jiwer",
        "rapidfuzz",
    }


def test_phowhisper_cannot_load_an_unverified_alternate_model_directory(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from vericlue_ml.voice import asr

    monkeypatch.setattr(
        asr,
        "PhoWhisperASR",
        lambda *args, **kwargs: SimpleNamespace(model_dir=tmp_path / "other", vad_mode=1),
    )
    with pytest.raises(ValueError):
        evaluation._detector("phowhisper", tmp_path)
