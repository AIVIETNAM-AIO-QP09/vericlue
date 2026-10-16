"""Offline DATA-03 tests for audio identity boundaries and split provenance."""

from __future__ import annotations

import csv
import importlib
import json
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPLIT_NAMES = {"train", "calib_fit", "calib_ltt", "test"}
DATASETS = {"mlaad_vi", "vsasv", "vimd", "vivos", "vispoofdb"}


def implementation() -> ModuleType:
    """Import only when a test runs, allowing the production module to be developed separately."""
    return importlib.import_module("make_splits")


def write_manifest(data_dir: Path, name: str, rows: list[dict]) -> None:
    dest = data_dir / "raw" / name
    dest.mkdir(parents=True, exist_ok=True)
    for row in rows:
        target = dest / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
    (dest / "selected_manifest.json").write_text(json.dumps(rows), encoding="utf-8")


def audio_fixture(data_dir: Path, replay_per_person: int = 2) -> dict[str, list[dict]]:
    """Create metadata and empty media placeholders; tests never decode audio."""
    vsasv = []
    for index in range(16):
        speaker = f"id{index:05}"
        kinds = ["bonafide", "replay"] if index < 12 else ["bonafide"]
        for kind in kinds:
            for clip in range(replay_per_person):
                source = f"{speaker}/{kind}_{clip:03}.wav"
                vsasv.append(
                    {
                        "path": "audio/" + source,
                        "file": source,
                        "original_path": source,
                        "subject_id": speaker,
                        "source_label": speaker,
                        "source_group": speaker,
                        "label": int(kind == "replay"),
                        "utt_type": kind,
                    }
                )
    vimd = [
        {
            "path": f"audio/spk_{region_index}_{person}/clip.wav",
            "speakerID": f"spk_{region_index}_{person}",
            "subject_id": f"spk_{region_index}_{person}",
            "region": region,
            "filename": f"{region_index}_{person}.wav",
        }
        for region_index, region in enumerate(("North", "Central", "South"))
        for person in range(4)
    ]
    vivos = [
        {
            "path": f"vivos/train/waves/VIVOSSPK{person:02}/VIVOSSPK{person:02}_001.wav",
            "subject_id": f"VIVOSSPK{person:02}",
        }
        for person in range(1, 4)
    ]
    vispoof = [
        {"path": "real/audio_0000.wav", "subject_id": "", "split_policy": "test_only"},
        {"path": "fake/edgetts/edgetts_0000.wav", "subject_id": "", "split_policy": "test_only"},
        {"path": "fake/elevenlabs/voice_0000.mp3", "subject_id": "", "split_policy": "test_only"},
        {"path": "corpus.txt", "subject_id": "", "split_policy": "test_only"},
    ]
    reader_a = "en_US/by_book/female/reader_a/book/wavs/"
    reader_b = "en_US/by_book/male/reader_b/book/wavs/"
    mlaad = [
        {
            "path": "fake/vi/LEMAS-TTS/one.wav",
            "original_file": "source/one.wav",
            "reference_speaker": reader_a + "a.wav",
            "tts": "LEMAS-TTS",
        },
        {
            "path": "fake/vi/OmniVoice/one.wav",
            "original_file": "source/one.wav",
            "reference_speaker": reader_b + "b.wav",
            "tts": "OmniVoice",
        },
        {
            "path": "fake/vi/VoxCPM2/two.wav",
            "original_file": "source/two.wav",
            "reference_speaker": reader_b + "different.wav",
            "tts": "VoxCPM2",
        },
        {
            "path": "fake/vi/VieNeu-TTS/three.wav",
            "original_file": "source/three.wav",
            "reference_speaker": reader_a + "other.wav",
            "tts": "VieNeu-TTS",
        },
        {
            "path": "fake/vi/LEMAS-TTS/four.wav",
            "original_file": "source/four.wav",
            "reference_speaker": "unverified/same-reference.wav",
            "tts": "LEMAS-TTS",
        },
        {
            "path": "fake/vi/OmniVoice/five.wav",
            "original_file": "source/five.wav",
            "reference_speaker": "unverified/same-reference.wav",
            "tts": "OmniVoice",
        },
    ] + [
        {
            "path": f"fake/vi/vixTTS/missing_{i}.wav",
            "original_file": f"source/missing_{i}.wav",
            "tts": "vixTTS",
        }
        for i in range(12)
    ]
    manifests = dict(mlaad_vi=mlaad, vsasv=vsasv, vimd=vimd, vivos=vivos, vispoofdb=vispoof)
    for name, rows in manifests.items():
        write_manifest(data_dir, name, rows)
    return manifests


def flatten(splits: dict, name: str) -> list[dict]:
    return [row for rows in splits[name].values() for row in rows]


def location(splits: dict, name: str, suffix: str) -> str:
    matches = [
        split
        for split, rows in splits[name].items()
        for row in rows
        if row["path"].endswith(suffix)
    ]
    assert len(matches) == 1
    return matches[0]


def test_all_audio_rows_appear_once_with_explicit_labels(tmp_path: Path) -> None:
    manifests = audio_fixture(tmp_path)
    splits = implementation().build_splits(tmp_path, seed=42)
    assert set(splits) == DATASETS
    for name in DATASETS:
        assert set(splits[name]) == SPLIT_NAMES
        rows = flatten(splits, name)
        expected = sum(Path(row["path"]).suffix in {".wav", ".mp3"} for row in manifests[name])
        assert len(rows) == expected
        assert len({row["path"] for row in rows}) == expected
        assert {row["label"] for row in rows} <= {"0", "1"}
        assert all(row["source"] for row in rows)
    assert {r["label"] for r in flatten(splits, "mlaad_vi")} == {"1"}
    assert {r["label"] for r in flatten(splits, "vivos")} == {"0"}
    assert {r["label"] for r in flatten(splits, "vimd")} == {"0"}
    assert all(not r["path"].endswith("corpus.txt") for r in flatten(splits, "vispoofdb"))


def test_vivos_and_vispoof_remain_test_only_without_invented_vispoof_ids(tmp_path: Path) -> None:
    audio_fixture(tmp_path)
    splits = implementation().build_splits(tmp_path)
    for name in ("vivos", "vispoofdb"):
        assert splits[name]["test"]
        assert not any(splits[name][split] for split in SPLIT_NAMES - {"test"})
    assert all(not row["subject_id"] for row in splits["vispoofdb"]["test"])
    assert Counter(row["label"] for row in splits["vispoofdb"]["test"]) == {"0": 1, "1": 2}


def test_vimd_assigns_exactly_one_person_per_region_to_every_split(tmp_path: Path) -> None:
    audio_fixture(tmp_path)
    splits = implementation().build_splits(tmp_path)
    seen = set()
    for rows in splits["vimd"].values():
        assert len(rows) == 3
        assert Counter(row["region"] for row in rows) == {"North": 1, "Central": 1, "South": 1}
        people = {row["subject_id"] for row in rows}
        assert len(people) == 3
        assert seen.isdisjoint(people)
        seen.update(people)
    assert len(seen) == 12


def test_vsasv_keeps_people_and_bonafide_replay_pairs_together(tmp_path: Path) -> None:
    audio_fixture(tmp_path)
    splits = implementation().build_splits(tmp_path)
    seen = set()
    for rows in splits["vsasv"].values():
        people = {row["subject_id"] for row in rows}
        assert seen.isdisjoint(people)
        seen.update(people)
    assert len(seen) == 16
    for index in range(12):
        suffix = f"id{index:05}/"
        member_splits = {
            split
            for split, rows in splits["vsasv"].items()
            for row in rows
            if suffix in row["path"]
        }
        assert len(member_splits) == 1
    assert sum(len(rows) for rows in splits["vsasv"].values()) == 56


def test_vsasv_calib_ltt_reaches_sixty_replays_using_whole_people_when_available(
    tmp_path: Path,
) -> None:
    audio_fixture(tmp_path, replay_per_person=40)
    splits = implementation().build_splits(tmp_path)
    ltt = splits["vsasv"]["calib_ltt"]
    assert sum(row["label"] == "1" for row in ltt) >= 60
    for person in {row["subject_id"] for row in ltt}:
        elsewhere = [
            row for split, rows in splits["vsasv"].items() if split != "calib_ltt" for row in rows
        ]
        assert all(row["subject_id"] != person for row in elsewhere)


def test_mlaad_unions_original_and_reference_reader_transitively(tmp_path: Path) -> None:
    audio_fixture(tmp_path)
    splits = implementation().build_splits(tmp_path)
    same_component = {
        location(splits, "mlaad_vi", suffix)
        for suffix in (
            "LEMAS-TTS/one.wav",
            "OmniVoice/one.wav",
            "VoxCPM2/two.wav",
            "VieNeu-TTS/three.wav",
        )
    }
    assert len(same_component) == 1
    assert location(splits, "mlaad_vi", "LEMAS-TTS/four.wav") == location(
        splits, "mlaad_vi", "OmniVoice/five.wav"
    )
    assert all(not row["subject_id"] for row in flatten(splits, "mlaad_vi"))


def test_missing_mlaad_reference_does_not_union_all_vix_tts_clips(tmp_path: Path) -> None:
    audio_fixture(tmp_path)
    rows = [
        {"path": f"fake/vi/vixTTS/{i}.wav", "original_file": f"source/{i}.wav", "tts": "vixTTS"}
        for i in range(20)
    ]
    write_manifest(tmp_path, "mlaad_vi", rows)
    splits = implementation().build_splits(tmp_path)
    nonempty = [split for split, members in splits["mlaad_vi"].items() if members]
    assert len(nonempty) == 4
    assert len(flatten(splits, "mlaad_vi")) == 20
    assert all(not row["subject_id"] for row in flatten(splits, "mlaad_vi"))


def test_seed_is_repeatable_and_manifest_order_independent(tmp_path: Path) -> None:
    manifests = audio_fixture(tmp_path)
    first = implementation().build_splits(tmp_path, seed=42)
    assert first == implementation().build_splits(tmp_path, seed=42)
    for name, rows in manifests.items():
        write_manifest(tmp_path, name, list(reversed(rows)))
    assert first == implementation().build_splits(tmp_path, seed=42)
    different = implementation().build_splits(tmp_path, seed=7)
    assert any(first[name] != different[name] for name in ("vsasv", "vimd", "mlaad_vi"))


@pytest.mark.parametrize(
    "name,field", [("vsasv", "subject_id"), ("vimd", "speakerID"), ("vivos", "subject_id")]
)
def test_required_identity_missing_fails_instead_of_random_row_split(
    tmp_path: Path, name: str, field: str
) -> None:
    manifests = audio_fixture(tmp_path)
    manifests[name][0][field] = ""
    if name == "vimd":
        manifests[name][0]["subject_id"] = ""
    write_manifest(tmp_path, name, manifests[name])
    with pytest.raises(ValueError):
        implementation().build_splits(tmp_path)


def test_missing_media_file_fails_with_no_splits_written(tmp_path: Path) -> None:
    manifests = audio_fixture(tmp_path)
    (tmp_path / "raw" / "vimd" / manifests["vimd"][0]["path"]).unlink()
    with pytest.raises(ValueError):
        implementation().build_splits(tmp_path)
    assert not (tmp_path / "splits").exists()


def test_write_splits_emits_four_csvs_per_dataset_and_a_summary(tmp_path: Path) -> None:
    audio_fixture(tmp_path)
    module = implementation()
    splits = module.build_splits(tmp_path, seed=42)
    summary = module.write_splits(tmp_path, splits, seed=42)
    assert isinstance(summary, Path) and summary.is_file()
    assert summary.name == "SUMMARY.md"
    assert "42" in summary.read_text(encoding="utf-8")
    for name in DATASETS:
        for split in SPLIT_NAMES:
            csv_path = tmp_path / "splits" / name / f"{split}.csv"
            with csv_path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                assert {"path", "label", "attack_type", "subject_id", "source"} <= set(
                    reader.fieldnames or ()
                )
                assert len(list(reader)) == len(splits[name][split])


def test_data_dir_location_does_not_change_assignment_or_component_ids(tmp_path: Path) -> None:
    first_dir, second_dir = tmp_path / "machine-one", tmp_path / "another-machine"
    audio_fixture(first_dir)
    audio_fixture(second_dir)
    module = implementation()

    def snapshot(data_dir: Path) -> dict[tuple[str, str], tuple[str, str]]:
        splits = module.build_splits(data_dir, seed=42)
        return {
            (source, Path(row["path"]).relative_to(data_dir).as_posix()): (split, row["group_id"])
            for source, part in splits.items()
            for split, rows in part.items()
            for row in rows
        }

    assert snapshot(first_dir) == snapshot(second_dir)


def identity_crosswalk(path: Path, rows: list[tuple[str, str, str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("source", "kind", "identity", "canonical_id"))
        writer.writerows(rows)
    return path


def test_verified_identity_link_moves_entire_mlaad_component_to_vivos_test(tmp_path: Path) -> None:
    audio_fixture(tmp_path)
    module = implementation()
    # Choose a fixture seed whose component needs moving, so ignoring the crosswalk fails.
    candidates = (42, 0, 1, 2, 3, 4, 5)
    seed = next(
        value
        for value in candidates
        if location(module.build_splits(tmp_path, seed=value), "mlaad_vi", "LEMAS-TTS/one.wav")
        != "test"
    )
    links = identity_crosswalk(
        tmp_path / "identity-links.csv",
        [
            ("mlaad_vi", "reference_group", "en_US/by_book/female/reader_a", "verified-person"),
            ("vivos", "subject_id", "VIVOSSPK01", "verified-person"),
        ],
    )
    splits = module.build_splits(tmp_path, seed=seed, identity_links=links)
    for suffix in (
        "LEMAS-TTS/one.wav",
        "OmniVoice/one.wav",
        "VoxCPM2/two.wav",
        "VieNeu-TTS/three.wav",
    ):
        assert location(splits, "mlaad_vi", suffix) == "test"
    assert location(splits, "vivos", "VIVOSSPK01_001.wav") == "test"
    assert all(not row["subject_id"] for row in flatten(splits, "mlaad_vi"))


@pytest.mark.parametrize(
    "source,kind,identity",
    [
        ("mlaad_vi", "reference_group", "unknown-reference"),
        ("vivos", "subject_id", "UNKNOWN-SPEAKER"),
    ],
)
def test_crosswalk_unknown_identity_is_rejected(
    tmp_path: Path, source: str, kind: str, identity: str
) -> None:
    audio_fixture(tmp_path)
    links = identity_crosswalk(
        tmp_path / "identity-links.csv", [(source, kind, identity, "verified-person")]
    )
    with pytest.raises(ValueError):
        implementation().build_splits(tmp_path, identity_links=links)


def unique_audio_bytes(splits: dict) -> None:
    """Give placeholders distinct tiny payloads so hashes exercise only intentional duplicates."""
    for source, part in splits.items():
        for rows in part.values():
            for index, row in enumerate(rows):
                Path(row["path"]).write_bytes(f"{source}|{row['path']}|{index}".encode())


def test_hash_audit_rejects_known_byte_duplicate_across_test_boundary(tmp_path: Path) -> None:
    audio_fixture(tmp_path)
    module = implementation()
    splits = module.build_splits(tmp_path)
    unique_audio_bytes(splits)
    target = splits["vsasv"]["train"][0]
    heldout = splits["vispoofdb"]["test"][0]
    payload = b"intentional-identical-fixture-audio"
    Path(target["path"]).write_bytes(payload)
    Path(heldout["path"]).write_bytes(payload)
    with pytest.raises(ValueError):
        module.audit_hashes(splits)


def test_hash_audit_allows_identical_bytes_when_both_sources_stay_in_test(tmp_path: Path) -> None:
    audio_fixture(tmp_path)
    module = implementation()
    splits = module.build_splits(tmp_path)
    unique_audio_bytes(splits)
    target = splits["vivos"]["test"][0]
    heldout = splits["vispoofdb"]["test"][0]
    payload = b"intentional-identical-test-only-fixture"
    Path(target["path"]).write_bytes(payload)
    Path(heldout["path"]).write_bytes(payload)
    result = module.audit_hashes(splits)
    assert isinstance(result, list) and result


def test_quota_report_and_summary_show_actual_shortfalls(tmp_path: Path) -> None:
    audio_fixture(tmp_path)
    module = implementation()
    splits = module.build_splits(tmp_path)
    fit = Counter(row["label"] for part in splits.values() for row in part["calib_fit"])
    ltt = Counter(
        row["attack_type"]
        for part in splits.values()
        for row in part["calib_ltt"]
        if row["label"] == "1"
    )
    messages = module.quota_report(splits)
    expected = [
        f"calib_fit lớp {label}: {fit[label]}/100; thiếu {100 - fit[label]}" for label in ("0", "1")
    ] + [
        f"calib_ltt {attack}: {ltt[attack]}/60; thiếu {60 - ltt[attack]}"
        for attack in ("replay", "tts")
    ]
    assert all(fit[label] < 100 for label in ("0", "1"))
    assert all(ltt[attack] < 60 for attack in ("replay", "tts"))
    assert all(message in messages for message in expected)
    summary = module.write_splits(tmp_path, splits).read_text(encoding="utf-8")
    assert all(message in summary for message in expected)


@pytest.mark.parametrize("sentinel", ["None", "null", "nan", " "])
def test_placeholder_reference_is_missing_and_never_unions_all_vix(
    tmp_path: Path, sentinel: str
) -> None:
    audio_fixture(tmp_path)
    rows = [
        {
            "path": f"fake/vi/vixTTS/{index}.wav",
            "original_file": f"source/{index}.wav",
            "reference_speaker": sentinel,
            "tts": "vixTTS",
        }
        for index in range(20)
    ]
    write_manifest(tmp_path, "mlaad_vi", rows)
    splits = implementation().build_splits(tmp_path)
    members = flatten(splits, "mlaad_vi")
    assert len(members) == 20
    assert all(not row["reference_group"] for row in members)
    assert len({row["group_id"] for row in members}) == 20
    assert all(splits["mlaad_vi"][split] for split in SPLIT_NAMES)


@pytest.mark.parametrize(
    "name,field,conflicting_value",
    [
        ("vsasv", "source_label", "id99999"),
        ("vsasv", "original_path", "id99999/other.wav"),
        ("vimd", "speakerID", "different-speaker"),
    ],
)
def test_identity_metadata_mismatch_is_rejected(
    tmp_path: Path, name: str, field: str, conflicting_value: str
) -> None:
    manifests = audio_fixture(tmp_path)
    manifests[name][0][field] = conflicting_value
    write_manifest(tmp_path, name, manifests[name])
    with pytest.raises(ValueError):
        implementation().build_splits(tmp_path)
