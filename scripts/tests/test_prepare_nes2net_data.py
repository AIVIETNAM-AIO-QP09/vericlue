"""Cloud data preparation: real WAV bytes, no model or network required."""

import csv
import hashlib
import importlib
import io
import json
import wave
import zipfile

import pytest


def wav(seed=1, *, rate=16000, channels=1):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as handle:
        handle.setparams((channels, 2, rate, rate, "NONE", "not compressed"))
        handle.writeframes(bytes([seed, 0]) * rate * channels)
    return stream.getvalue()


def metadata(split, speaker, audios):
    stream = io.StringIO()
    fields = (
        "file_name",
        "audio_id",
        "speaker_id",
        "checksum_sha256",
        "duration",
        "sample_rate",
        "num_channels",
        "review_status",
        "qc_status",
        "split",
    )
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for name, raw in audios.items():
        writer.writerow(
            dict(
                file_name=f"wavs/{name}.wav",
                audio_id=name,
                speaker_id=speaker,
                checksum_sha256=hashlib.sha256(raw).hexdigest(),
                duration=1,
                sample_rate=16000,
                num_channels=1,
                review_status="accepted",
                qc_status="passed",
                split=split,
            )
        )
    return stream.getvalue().encode()


def sources():
    audio = {
        "train": {"speaker001_0001": wav(1), "speaker001_0002": wav(2)},
        "validation": {"speaker019_0001": wav(3)},
        "test": {"speaker023_0001": wav(4)},
    }
    meta = {
        split: metadata(split, next(iter(files)).split("_")[0], files)
        for split, files in audio.items()
    }
    payloads = {f"data/{split}/metadata.csv": raw for split, raw in meta.items()}
    payloads |= {
        f"data/{split}/wavs/{name}.wav": raw
        for split, files in audio.items()
        for name, raw in files.items()
    }
    payloads |= {
        "LICENSE": b"Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)",
        "PUBLIC_RELEASE_APPROVAL.md": b"PUBLIC release, research data; no direct identity records",
    }
    return meta, payloads


def test_selection_preserves_subject_splits_and_is_independent_of_csv_order():
    prep = importlib.import_module("scripts.prepare_nes2net_data")
    meta, _ = sources()
    selected = prep.select_samples(meta, per_speaker=1, seed=42)
    assert len(selected) == 3
    assert [(s["subject_ids"], s["split"], s["usage"]) for s in selected] == [
        (["DNU:speaker001"], "calib_fit", "calibration_evaluation"),
        (["DNU:speaker019"], "calib_ltt", "calibration_evaluation"),
        (["DNU:speaker023"], "test", "test_only"),
    ]
    lines = meta["train"].decode().splitlines()
    meta["train"] = ("\n".join([lines[0], *reversed(lines[1:])]) + "\n").encode()
    assert prep.select_samples(meta, per_speaker=1, seed=42) == selected


@pytest.mark.parametrize("fault", ["subject_overlap", "path", "hash", "duplicate_id"])
def test_invalid_source_metadata_cannot_produce_a_plan(fault):
    prep = importlib.import_module("scripts.prepare_nes2net_data")
    meta, _ = sources()
    if fault == "subject_overlap":
        meta["validation"] = metadata("validation", "speaker001", {"speaker001_0003": wav(3)})
    elif fault == "path":
        meta["train"] = meta["train"].replace(b"wavs/", b"../")
    elif fault == "hash":
        meta["train"] = meta["train"].replace(
            hashlib.sha256(wav(1)).hexdigest().encode(), b"bad-hash"
        )
    else:
        meta["train"] += meta["train"].splitlines(keepends=True)[1]
    with pytest.raises(ValueError):
        prep.select_samples(meta, per_speaker=20, seed=42)


def test_complete_bonafide_bundle_is_partial_and_resume_never_redownloads_audio(tmp_path):
    prep = importlib.import_module("scripts.prepare_nes2net_data")
    _, payloads = sources()

    def fetch(url):
        return payloads[url.split(prep.REVISION + "/", 1)[1]]

    report = prep.prepare(tmp_path, per_speaker=20, seed=42, fetch=fetch, commit="a" * 40)
    assert report["downloaded_audio_files"] == 4
    assert report["pcm_duplicate_check"] == "passed"
    assert report["calibration_ready"] is False and report["missing"] == ["attack_data"]
    body = json.loads((tmp_path / "manifest.json").read_text())
    assert len(body["samples"]) == 4 and all(s["label"] == 0 for s in body["samples"])

    def no_audio_fetch(url):
        if url.endswith(".wav"):
            raise AssertionError("Verified existing audio must be reused")
        return fetch(url)

    again = prep.prepare(tmp_path, per_speaker=20, seed=42, fetch=no_audio_fetch, commit="a" * 40)
    assert again["reused_audio_files"] == 4


@pytest.mark.parametrize("fault", ["bytes", "stereo", "rate", "duplicate_pcm"])
def test_download_corruption_and_wrong_pcm_are_recorded_without_becoming_ready(tmp_path, fault):
    prep = importlib.import_module("scripts.prepare_nes2net_data")
    _, payloads = sources()
    key = "data/test/wavs/speaker023_0001.wav"
    changed = (
        b"broken"
        if fault == "bytes"
        else wav(4, channels=2)
        if fault == "stereo"
        else wav(4, rate=8000)
        if fault == "rate"
        else wav(1)
    )
    payloads[key] = changed
    if fault != "bytes":
        payloads["data/test/metadata.csv"] = metadata(
            "test", "speaker023", {"speaker023_0001": changed}
        )
    report = prep.prepare(
        tmp_path,
        per_speaker=20,
        seed=42,
        fetch=lambda url: payloads[url.split(prep.REVISION + "/", 1)[1]],
        commit="a" * 40,
    )
    assert report["calibration_ready"] is False
    assert report["errors"] and report["state"] == "incomplete"
    assert not (tmp_path / "bundle.zip").exists()


def test_existing_altered_audio_is_never_overwritten(tmp_path):
    prep = importlib.import_module("scripts.prepare_nes2net_data")
    _, payloads = sources()

    def fetch(url):
        return payloads[url.split(prep.REVISION + "/", 1)[1]]

    prep.prepare(tmp_path, per_speaker=20, seed=42, fetch=fetch, commit="a" * 40)
    target = tmp_path / "DNU-ViSpeech/data/train/wavs/speaker001_0001.wav"
    target.write_bytes(b"keep this evidence")
    report = prep.prepare(tmp_path, per_speaker=20, seed=42, fetch=fetch, commit="a" * 40)
    assert target.read_bytes() == b"keep this evidence"
    assert report["state"] == "incomplete" and report["errors"]


def test_archive_contains_only_manifested_evidence_and_checks_current_bytes(tmp_path):
    prep = importlib.import_module("scripts.prepare_nes2net_data")
    _, payloads = sources()
    root = tmp_path / "bundle"
    prep.prepare(
        root,
        per_speaker=20,
        seed=42,
        fetch=lambda url: payloads[url.split(prep.REVISION + "/", 1)[1]],
        commit="a" * 40,
    )
    (root / "unrelated-private.env").write_bytes(b"never export unrelated files")
    archive = tmp_path / "bundle.zip"
    prep.archive_bundle(root, archive)
    with zipfile.ZipFile(archive) as handle:
        assert "manifest.json" in handle.namelist()
        assert "unrelated-private.env" not in handle.namelist()
    (root / "DNU-ViSpeech/data/train/wavs/speaker001_0001.wav").write_bytes(
        b"changed after preparation"
    )
    with pytest.raises(ValueError):
        prep.archive_bundle(root, tmp_path / "must-not-export.zip")
    assert not (tmp_path / "must-not-export.zip").exists()


def test_archive_refuses_bytes_changed_since_preparation(tmp_path):
    prep = importlib.import_module("scripts.prepare_nes2net_data")
    _, payloads = sources()
    root = tmp_path / "bundle"
    prep.prepare(
        root,
        per_speaker=20,
        seed=42,
        fetch=lambda url: payloads[url.split(prep.REVISION + "/", 1)[1]],
        commit="a" * 40,
    )
    (root / "DNU-ViSpeech/data/train/wavs/speaker001_0001.wav").write_bytes(b"changed")
    with pytest.raises(ValueError):
        prep.archive_bundle(root, tmp_path / "must-not-export.zip")
    assert not (tmp_path / "must-not-export.zip").exists()


@pytest.mark.parametrize("name", ["source", "runs"])
def test_resume_never_writes_through_symlink_outside_bundle(tmp_path, name):
    prep = importlib.import_module("scripts.prepare_nes2net_data")
    _, payloads = sources()
    root, outside = tmp_path / "bundle", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    try:
        (root / name).symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not permit directory symlinks")
    with pytest.raises(ValueError):
        prep.prepare(
            root,
            per_speaker=20,
            seed=42,
            fetch=lambda url: payloads[url.split(prep.REVISION + "/", 1)[1]],
            commit="a" * 40,
        )
    assert list(outside.iterdir()) == []
