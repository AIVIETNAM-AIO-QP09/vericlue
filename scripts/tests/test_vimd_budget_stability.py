"""ViMD budgets must preserve seeded people and every selected clip, offline."""

from __future__ import annotations

import io
import json
import sys
import wave
from collections import Counter
from dataclasses import replace
from pathlib import Path
from urllib.parse import unquote

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import data_download_audio as audio  # noqa: E402
import data_download_core as core  # noqa: E402


def test_vimd_800mb_and_300mb_keep_identical_people_rowgroups_and_clips(tmp_path, monkeypatch):
    """Changing disk allowance alone cannot change the bounded ViMD population."""
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    shards = {}
    expected = {}
    regions = ("North", "Central", "South")
    for shard_index in range(3):
        rows = []
        for region in regions:
            for person_index in range(6):
                subject = f"{region}-{person_index}"
                for clip_index in range(2):
                    name = f"{subject}-{shard_index}-{clip_index}.wav"
                    samples = bytes([person_index, shard_index, clip_index, 0]) * 16
                    buffer = io.BytesIO()
                    with wave.open(buffer, "wb") as stream:
                        stream.setnchannels(1)
                        stream.setsampwidth(2)
                        stream.setframerate(16000)
                        stream.writeframes(samples)
                    payload = buffer.getvalue()
                    expected[name] = (subject, region, payload)
                    rows.append(
                        {
                            "speakerID": subject,
                            "region": region,
                            "filename": name,
                            "audio": {"path": name, "bytes": payload},
                        }
                    )
        buffer = io.BytesIO()
        pq.write_table(pa.Table.from_pylist(rows), buffer, row_group_size=4)
        shards[f"data/train-{shard_index:03}.parquet"] = buffer.getvalue()

    class Remote(io.BytesIO):
        def __init__(self, payload, name, client):
            super().__init__(payload)
            self.shard_name = name
            self.client = client

    class FakeClient:
        def __init__(self):
            self.phase = "prepare"
            self.audio_groups = []
            self.metadata_groups = []

        def hf_files(self, repo):
            assert repo == audio.AUDIO_REPOS["vimd"]
            return "fixed-revision", [
                {"path": name, "size": len(payload)} for name, payload in shards.items()
            ]

        def remote_file(self, url, size):
            name = unquote(url.split("/resolve/fixed-revision/", 1)[1])
            assert size == len(shards[name])
            return Remote(shards[name], name, self)

    original_parquet = pq.ParquetFile

    class InspectedParquet:
        def __init__(self, handle):
            self.handle = handle
            self.parquet = original_parquet(handle)

        def __getattr__(self, name):
            return getattr(self.parquet, name)

        def read_row_group(self, index, columns=None, **kwargs):
            request = (self.handle.shard_name, index)
            if self.handle.client.phase == "prepare":
                assert columns is not None and "audio" not in columns
                self.handle.client.metadata_groups.append(request)
            else:
                assert columns == ["audio"]
                self.handle.client.audio_groups.append(request)
            return self.parquet.read_row_group(index, columns=columns, **kwargs)

    monkeypatch.setattr(pq, "ParquetFile", InspectedParquet)
    monkeypatch.setattr(audio, "check_disk", lambda *_args, **_kwargs: None)
    dataset = core.Dataset(
        "vimd", "https://example.test/vimd", "CC BY-NC-ND 4.0", None, 800_000_000
    )
    snapshots = []
    for budget in (800_000_000, 300_000_000):
        client = FakeClient()
        plan = audio.prepare(replace(dataset, budget_bytes=budget), client, 42, "small")
        assert len(plan.groups) == len(set(plan.groups)) == 12
        assert Counter(subject.split("-")[0] for subject in plan.groups) == dict.fromkeys(
            regions, 4
        )
        assert plan.peak_bytes <= budget
        assert client.audio_groups == []
        destination = tmp_path / str(budget)
        destination.mkdir()
        client.phase = "execute"
        assert plan.execute is not None
        plan.execute(destination, client)
        manifest = json.loads((destination / "selected_manifest.json").read_text("utf-8"))
        assert len(manifest) == 12 * 3 * 2
        assert Counter(row["subject_id"] for row in manifest) == dict.fromkeys(plan.groups, 6)
        expected_names = {
            name for name, (subject, _, _) in expected.items() if subject in plan.groups
        }
        assert {row["original_path"] for row in manifest} == expected_names
        for row in manifest:
            subject, region, payload = expected[row["original_path"]]
            assert row["subject_id"] == row["speakerID"] == subject
            assert row["region"] == region
            assert (destination / row["path"]).read_bytes() == payload
        assert len(client.audio_groups) == len(set(client.audio_groups))
        assert set(client.audio_groups) == {(row["shard"], row["row_group"]) for row in manifest}
        provenance = [note for note in plan.notes if note.startswith(("Shards", "Range rowgroups"))]
        snapshots.append(
            (plan.groups, client.metadata_groups, client.audio_groups, provenance, manifest)
        )
    assert snapshots[0] == snapshots[1]
