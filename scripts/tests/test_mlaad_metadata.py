"""Offline regression tests for incomplete MLAAD Vietnamese metadata."""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import data_download_audio as audio  # noqa: E402
import data_download_core as core  # noqa: E402


class FakeClient:
    """Serve only fixture metadata and synthetic bytes, with no network client."""

    token = "dummy_token_must_not_be_written"

    def __init__(self, metadata: dict[str, bytes], wavs: dict[str, int]) -> None:
        self.metadata = metadata
        self.wavs = wavs
        self.downloaded: list[str] = []
        self.entries = [
            {"path": path, "size": len(payload), "type": "file"}
            for path, payload in metadata.items()
        ] + [{"path": path, "size": size, "type": "file"} for path, size in wavs.items()]

    def hf_files(self, repo: str, prefix: str = "") -> tuple[str, list[dict]]:
        assert repo == "mueller91/MLAAD"
        assert prefix == "fake/vi"
        return "pinned-fixture-revision", self.entries

    def get_bytes(self, url: str, **kwargs: object) -> bytes:
        path = unquote(url.split("/resolve/pinned-fixture-revision/", 1)[1])
        assert path in self.metadata, "prepare must not read audio payloads"
        return self.metadata[path]

    def download(self, file: core.RemoteFile, dest: Path) -> None:
        self.downloaded.append(file.path)
        payload = self.metadata.get(file.path, b"x" * file.size)
        assert len(payload) == file.size
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)


def metadata_csv(columns: tuple[str, ...], rows: list[tuple[str, ...]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter="|", lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def dataset(client: FakeClient, wav_budget: int = 10_000) -> core.Dataset:
    return core.Dataset(
        "mlaad_vi",
        "https://huggingface.co/datasets/mueller91/MLAAD",
        "CC BY-NC 4.0",
        None,
        wav_budget + sum(map(len, client.metadata.values())) + 10_000_000,
        True,
    )


def prepare(client: FakeClient, wav_budget: int = 10_000) -> core.Plan:
    plan = audio.prepare(dataset(client, wav_budget), client, 42, "small")
    assert not client.downloaded
    assert plan.revision == "pinned-fixture-revision"
    return plan


def test_orphan_wavs_do_not_discard_valid_cross_tts_source_group() -> None:
    client = FakeClient(
        {
            "fake/vi/a/meta.csv": metadata_csv(
                ("path", "original_file"), [("./fake/vi/a/a.wav", "original/sentence.wav")]
            ),
            "fake/vi/b/meta.csv": metadata_csv(
                ("path", "original_file"), [("b.wav", "original/sentence.wav")]
            ),
        },
        {
            "fake/vi/a/a.wav": 4,
            "fake/vi/b/b.wav": 4,
            "fake/vi/a/orphan-one.wav": 4,
            "fake/vi/a/orphan-two.wav": 4,
            "fake/en/a/ignore.wav": 4,
        },
    )
    plan = prepare(client)
    assert plan.groups == ["original/sentence.wav"]
    assert {f.path for f in plan.files} == {"fake/vi/a/a.wav", "fake/vi/b/b.wav"}
    notes = " ".join(plan.notes)
    assert "2" in notes and "no_metadata" in notes
    assert "a" in notes


def test_blank_original_file_excludes_only_ungroupable_wav() -> None:
    client = FakeClient(
        {
            "fake/vi/a/meta.csv": metadata_csv(
                ("path", "original_file"),
                [("valid.wav", "original/valid.wav"), ("blank.wav", "   ")],
            )
        },
        {"fake/vi/a/valid.wav": 4, "fake/vi/a/blank.wav": 4},
    )
    plan = prepare(client)
    assert [f.path for f in plan.files] == ["fake/vi/a/valid.wav"]
    assert plan.groups == ["original/valid.wav"]
    assert "missing_original_file" in " ".join(plan.notes)


def test_missing_original_column_in_one_system_keeps_other_system() -> None:
    client = FakeClient(
        {
            "fake/vi/a/meta.csv": metadata_csv(("path", "transcript"), [("a.wav", "text")]),
            "fake/vi/b/meta.csv": metadata_csv(
                ("path", "original_file"), [("b.wav", "original/b.wav")]
            ),
        },
        {"fake/vi/a/a.wav": 4, "fake/vi/b/b.wav": 4},
    )
    plan = prepare(client)
    assert [f.path for f in plan.files] == ["fake/vi/b/b.wav"]
    assert plan.groups == ["original/b.wav"]
    assert "original_file" in " ".join(plan.notes)


def test_conflicting_duplicate_path_is_excluded_without_duplicate_downloads() -> None:
    client = FakeClient(
        {
            "fake/vi/a/meta.csv": metadata_csv(
                ("path", "original_file", "transcript"),
                [
                    ("conflict.wav", "original/one.wav", "first"),
                    ("./fake/vi/a/conflict.wav", "original/two.wav", "second"),
                    ("safe.wav", "original/safe.wav", "safe"),
                ],
            )
        },
        {"fake/vi/a/conflict.wav": 4, "fake/vi/a/safe.wav": 4},
    )
    plan = prepare(client)
    assert [f.path for f in plan.files] == ["fake/vi/a/safe.wav"]
    assert plan.groups == ["original/safe.wav"]
    assert len({f.path for f in plan.files}) == len(plan.files)
    assert "metadata_conflict" in " ".join(plan.notes)


def test_optional_reference_path_and_original_group_survive_manifest_and_source(
    tmp_path: Path,
) -> None:
    reference = "en_US/by_book/female/speaker/book/wavs/reference.wav"
    original = "en_US/by_book/male/reader/book/wavs/sentence.wav"
    client = FakeClient(
        {
            "fake/vi/a/meta.csv": metadata_csv(
                ("path", "original_file", "reference_speaker", "transcript"),
                [("a.wav", original, reference, "first transcript")],
            ),
            "fake/vi/b/meta.csv": metadata_csv(
                ("path", "original_file", "transcript"), [("b.wav", original, "variant")]
            ),
        },
        {"fake/vi/a/a.wav": 4, "fake/vi/b/b.wav": 4},
    )
    plan = prepare(client)
    assert plan.execute is not None
    plan.execute(tmp_path, client)
    rows = json.loads((tmp_path / "selected_manifest.json").read_text(encoding="utf-8"))
    by_path = {row["path"]: row for row in rows}
    assert len(rows) == 2
    assert by_path["fake/vi/a/a.wav"]["reference_speaker"] == reference
    assert not by_path["fake/vi/b/b.wav"].get("reference_speaker")
    assert all(row["source_group"] == original for row in rows)
    assert all(not row.get("subject_id") for row in rows)
    source_path = core.write_source(plan, tmp_path, 42, "complete")
    source = source_path.read_text(encoding="utf-8")
    assert original in source
    assert "reference_speaker" in source
    assert "DATA-03" in source
    assert "42" in source and "pinned-fixture-revision" in source
    assert client.token not in source
    assert client.token not in (tmp_path / "selected_manifest.json").read_text(encoding="utf-8")
    assert len(client.downloaded) == len(set(client.downloaded))


def test_seed_and_budget_keep_whole_cross_tts_groups() -> None:
    rows_a = [(f"{i}.wav", f"original/{i}.wav") for i in range(12)]
    rows_b = [(f"{i}.wav", f"original/{i}.wav") for i in range(12)]
    metadata = {
        "fake/vi/a/meta.csv": metadata_csv(("path", "original_file"), rows_a),
        "fake/vi/b/meta.csv": metadata_csv(("path", "original_file"), rows_b),
    }
    wavs = {f"fake/vi/{model}/{i}.wav": 4 for model in ("a", "b") for i in range(12)}
    client = FakeClient(metadata, wavs)
    first = prepare(client, wav_budget=17)
    again_client = FakeClient(
        dict(reversed(list(metadata.items()))), dict(reversed(list(wavs.items())))
    )
    again = prepare(again_client, wav_budget=17)
    assert first.groups == again.groups
    assert {f.path for f in first.files} == {f.path for f in again.files}
    assert len(first.groups) == 2 and len(first.files) == 4
    assert sum(f.size for f in first.files) == 16
    assert first.peak_bytes <= first.dataset.budget_bytes
    for group in first.groups:
        stem = Path(group).stem
        assert {f.path for f in first.files if Path(f.path).stem == stem} == {
            f"fake/vi/a/{stem}.wav",
            f"fake/vi/b/{stem}.wav",
        }
    with pytest.raises(core.SkipDataset):
        prepare(client, wav_budget=7)


@pytest.mark.parametrize("changed_field", ["reference_speaker", "transcript"])
def test_same_original_with_conflicting_provenance_excludes_path(changed_field: str) -> None:
    first = {
        "path": "ambiguous.wav",
        "original_file": "source/sentence.wav",
        "reference_speaker": "reference/speaker-a.wav",
        "transcript": "first transcript",
    }
    second = {**first, changed_field: "conflicting provenance"}
    columns = tuple(first)
    client = FakeClient(
        {
            "fake/vi/a/meta.csv": metadata_csv(
                columns,
                [
                    tuple(first.values()),
                    tuple(second.values()),
                    ("safe.wav", "source/safe.wav", "reference/safe.wav", "safe"),
                ],
            )
        },
        {"fake/vi/a/ambiguous.wav": 4, "fake/vi/a/safe.wav": 4},
    )
    plan = prepare(client)
    assert [file.path for file in plan.files] == ["fake/vi/a/safe.wav"]
    assert plan.groups == ["source/safe.wav"]
    assert "metadata_conflict" in " ".join(plan.notes)


def test_exact_duplicate_metadata_row_is_kept_and_downloaded_once(tmp_path: Path) -> None:
    row = ("./fake/vi/a/one.wav", "source/one.wav", "reference/one.wav", "same text")
    client = FakeClient(
        {
            "fake/vi/a/meta.csv": metadata_csv(
                ("path", "original_file", "reference_speaker", "transcript"), [row, row]
            )
        },
        {"fake/vi/a/one.wav": 4},
    )
    plan = prepare(client)
    assert [file.path for file in plan.files] == ["fake/vi/a/one.wav"]
    assert plan.groups == ["source/one.wav"]
    assert plan.execute is not None
    plan.execute(tmp_path, client)
    assert client.downloaded.count("fake/vi/a/one.wav") == 1
    manifest = json.loads((tmp_path / "selected_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 1
    assert manifest[0]["reference_speaker"] == "reference/one.wav"
