"""VSASV adapter tests with local Parquet fixtures and no network."""

from __future__ import annotations

import io
import json
import re
import shutil
import struct
import sys
from pathlib import Path
from urllib.parse import unquote

import numpy as np
import pytest
from scipy.io import wavfile

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import data_download_audio as audio  # noqa: E402
import data_download_core as core  # noqa: E402


@pytest.mark.parametrize("rate", [8000, 22050])
def test_float32_wav_keeps_samples_and_original_sampling_rate(rate):
    values = np.asarray([0, 0.125, -0.25, 0.5, -0.75], dtype=np.float64)
    payload = audio._float32_wav(values, rate)
    actual_rate, decoded = wavfile.read(io.BytesIO(payload))
    assert actual_rate == rate
    assert decoded.dtype == np.float32
    np.testing.assert_array_equal(decoded, values.astype(np.float32))


@pytest.mark.parametrize("values", [np.asarray([]), np.asarray([np.nan]), np.asarray([np.inf])])
def test_float32_wav_rejects_empty_or_nonfinite_samples(values):
    with pytest.raises(core.DownloadError):
        audio._float32_wav(values, 16000)


def row(person, kind="bonafide", *, rate=16000, samples=None, index=0):
    return {
        "file": f"{person}/{kind}/{index:05}.wav",
        "label": person,
        "utt_type": kind,
        "audio": {
            "array": [0.0, 0.25, -0.5, 0.75] if samples is None else samples,
            "sampling_rate": rate,
        },
    }


class Remote(io.BytesIO):
    def __init__(self, client, name):
        super().__init__(client.shards[name])
        self.client, self.name = client, name

    def read(self, size=-1):
        start = self.tell()
        if self.client.phase == "prepare":
            assert size >= 0
            assert any(
                start >= first and start + size <= last
                for first, last in self.client.allowed[self.name]
            ), "prepare requested audio column bytes"
        else:
            self.client.audio_reads.append((self.name, start, size))
        return super().read(size)

    def readinto(self, buffer):
        value = self.read(len(buffer))
        buffer[: len(value)] = value
        return len(value)


class FakeClient:
    token = "fixture-token"

    def __init__(self, shards, allowed):
        self.shards, self.allowed = shards, allowed
        self.phase = "prepare"
        self.metadata_reads = []
        self.audio_reads = []

    def hf_files(self, repo, prefix=""):
        return "fixture-revision", [
            {"path": name, "size": len(payload)} for name, payload in self.shards.items()
        ]

    def remote_file(self, url, size):
        name = next(name for name in self.shards if unquote(url).endswith(name))
        assert size == len(self.shards[name])
        return Remote(self, name)

    def measured_network(self):
        from contextlib import nullcontext

        return nullcontext()


@pytest.fixture
def parquet_fixtures(monkeypatch):
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    original = pq.ParquetFile
    state = {"client": None}

    class AudioTable:
        def __init__(self, table):
            self.table = table

        def to_pylist(self):
            pytest.fail("whole audio tables must not become Python lists")

        def __getattr__(self, name):
            return getattr(self.table, name)

        def __getitem__(self, key):
            return self.table[key]

    class InspectedParquet:
        def __init__(self, *args, **kwargs):
            self.inner = original(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def read_row_group(self, index, columns=None, **kwargs):
            if state["client"].phase == "prepare":
                assert columns is not None and "audio" not in columns
                state["client"].metadata_reads.append((index, tuple(columns)))
            result = self.inner.read_row_group(index, columns=columns, **kwargs)
            return AudioTable(result) if columns == ["audio"] else result

    monkeypatch.setattr(pq, "ParquetFile", InspectedParquet)
    monkeypatch.setattr(
        core.shutil,
        "disk_usage",
        lambda _: shutil._ntuple_diskusage(100_000_000_000, 0, 100_000_000_000),
    )

    def make(shards, *, budget=100_000_000):
        payloads, allowed = {}, {}
        for name, rows in shards.items():
            buffer = io.BytesIO()
            schema = pa.schema(
                [
                    ("file", pa.string()),
                    (
                        "audio",
                        pa.struct(
                            [("array", pa.list_(pa.float64())), ("sampling_rate", pa.int64())]
                        ),
                    ),
                    ("label", pa.string()),
                    ("utt_type", pa.string()),
                ]
            )
            pq.write_table(pa.Table.from_pylist(rows, schema=schema), buffer, row_group_size=512)
            payload = buffer.getvalue()
            payloads[name] = payload
            footer_length = struct.unpack("<I", payload[-8:-4])[0]
            ranges = [(len(payload) - 8 - footer_length, len(payload))]
            metadata = original(io.BytesIO(payload)).metadata
            for group_index in range(metadata.num_row_groups):
                group = metadata.row_group(group_index)
                for column_index in range(group.num_columns):
                    column = group.column(column_index)
                    if not column.path_in_schema.startswith("audio."):
                        start = min(
                            offset
                            for offset in [column.dictionary_page_offset, column.data_page_offset]
                            if offset is not None and offset >= 0
                        )
                        ranges.append((start, start + column.total_compressed_size))
            allowed[name] = ranges
        client = FakeClient(payloads, allowed)
        state["client"] = client
        dataset = core.Dataset(
            "vsasv",
            "https://example.test/vsasv",
            "CC BY-NC 4.0",
            sum(map(len, payloads.values())),
            budget,
            gated=True,
        )
        plan = audio.prepare(dataset, client, 42, "small")
        assert client.audio_reads == []
        client.phase = "execute"
        return plan, client

    return make


def test_actual_schema_keeps_complete_label_groups_across_shards(parquet_fixtures, tmp_path):
    plan, client = parquet_fixtures(
        {
            "data/train-0.parquet": [row("id00000"), row("id00001")],
            "data/train-1.parquet": [row("id00000", "replay", index=1)],
        }
    )
    assert set(plan.groups) == {"id00000", "id00001"}
    assert len(client.metadata_reads) == 2
    plan.execute(tmp_path, client)
    manifest = json.loads((tmp_path / "selected_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 3
    assert sum(r["subject_id"] == "id00000" for r in manifest) == 2
    assert {r["utt_type"] for r in manifest} == {"bonafide", "replay"}
    assert {r["label"] for r in manifest} == {0, 1}
    assert all(r["source_label"] == r["subject_id"] == r["source_group"] for r in manifest)


def test_replay_groups_are_prioritized_with_deterministic_selection(parquet_fixtures):
    genuine = {"data/genuine.parquet": [row("id00000")]}
    replay = {"data/replay.parquet": [row("id00001"), row("id00001", "replay", index=1)]}
    genuine_plan, _ = parquet_fixtures(genuine)
    replay_plan, _ = parquet_fixtures(replay)
    budget = max(genuine_plan.peak_bytes, replay_plan.peak_bytes) + 128
    plan, _ = parquet_fixtures({**genuine, **replay}, budget=budget)
    assert plan.groups == ["id00001"]
    repeated, _ = parquet_fixtures({**replay, **genuine}, budget=budget)
    assert repeated.groups == plan.groups


@pytest.mark.parametrize("rate", [8000, 22050])
def test_array_extraction_is_float32_without_resampling(parquet_fixtures, tmp_path, rate):
    values = [0.0, 0.125, -0.25, 0.5, -0.75]
    plan, client = parquet_fixtures(
        {"data/train.parquet": [row("id00000", rate=rate, samples=values)]}
    )
    plan.execute(tmp_path, client)
    manifest = json.loads((tmp_path / "selected_manifest.json").read_text(encoding="utf-8"))
    actual_rate, decoded = wavfile.read(tmp_path / manifest[0]["path"])
    assert actual_rate == rate
    assert decoded.dtype == np.float32
    np.testing.assert_array_equal(decoded, np.asarray(values, dtype=np.float32))


def test_missing_and_mismatched_metadata_skips_rows_without_fake_ids(parquet_fixtures, tmp_path):
    samples = [
        row("id00000"),
        dict(row("id00001"), label=None),
        dict(row("id00002"), file=None),
        dict(row("id00003"), utt_type=None),
        dict(row("id00004"), file="id99999/bonafide/00000.wav"),
    ]
    plan, client = parquet_fixtures({"data/train.parquet": samples})
    assert plan.groups == ["id00000"]
    plan.execute(tmp_path, client)
    manifest = json.loads((tmp_path / "selected_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 1
    assert manifest[0]["subject_id"] == "id00000"


def test_vc_and_adversarial_exclusion_counts_are_recorded_in_source(parquet_fixtures, tmp_path):
    samples = [
        row("id00000"),
        row("id00000", "replay", index=1),
        row("id00000", "voice_conversion", index=2),
        row("id00000", "adversarial_attack", index=3),
    ]
    plan, client = parquet_fixtures({"data/train.parquet": samples})
    plan.execute(tmp_path, client)
    source = core.write_source(plan, tmp_path, 42, "complete").read_text(encoding="utf-8")
    manifest = json.loads((tmp_path / "selected_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 2
    for kind in ["voice_conversion", "adversarial_attack"]:
        assert re.search(rf"{kind}[^\n]*\b1\b", source)
    assert "16/10" in source


def test_manifest_overhead_is_included_in_output_budget(parquet_fixtures):
    with pytest.raises(core.SkipDataset):
        parquet_fixtures({"data/train.parquet": [row("id00000")]}, budget=100)


def test_resume_skips_verified_outputs_without_audio_refetch(parquet_fixtures, tmp_path):
    plan, client = parquet_fixtures({"data/train.parquet": [row("id00000")]})
    plan.execute(tmp_path, client)
    first_reads = list(client.audio_reads)
    manifest = json.loads((tmp_path / "selected_manifest.json").read_text(encoding="utf-8"))
    output = tmp_path / manifest[0]["path"]
    timestamp = output.stat().st_mtime_ns
    plan.execute(tmp_path, client)
    assert client.audio_reads == first_reads
    assert output.stat().st_mtime_ns == timestamp


def test_float32_wav_does_not_clip_or_integer_quantize_values():
    values = np.asarray([2.125, -3.5, 0.000001], dtype=np.float64)
    _, decoded = wavfile.read(io.BytesIO(audio._float32_wav(values, 16000)))
    np.testing.assert_array_equal(decoded, values.astype(np.float32))


@pytest.mark.parametrize("rate", [0, -16000, True, None, 16000.5])
def test_float32_wav_rejects_invalid_sampling_rates(rate):
    with pytest.raises(core.DownloadError):
        audio._float32_wav(np.asarray([0.1]), rate)


def test_float32_wav_requires_mono_array():
    with pytest.raises(core.DownloadError):
        audio._float32_wav(np.asarray([[0.1, 0.2]]), 16000)


def test_oversized_cached_receipt_fails_before_manifest_without_audio_refetch(
    parquet_fixtures, tmp_path
):
    plan, client = parquet_fixtures({"data/train.parquet": [row("id00000")]})
    plan.execute(tmp_path, client)
    manifest_path = tmp_path / "selected_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output = tmp_path / manifest[0]["path"]
    receipt_path = output.with_name(output.name + ".verified.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["unexpected_padding"] = "x" * (plan.peak_bytes + 1)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    manifest_path.unlink()
    previous_reads = list(client.audio_reads)
    previous_output = output.read_bytes()
    with pytest.raises(core.DownloadError, match="metadata"):
        plan.execute(tmp_path, client)
    assert client.audio_reads == previous_reads
    assert output.read_bytes() == previous_output
    assert not manifest_path.exists()


def test_saved_waveform_stats_report_out_of_range_without_clipping(tmp_path):
    path = tmp_path / "sample.wav"
    wavfile.write(path, 8000, np.asarray([-1.25, 0.0, 1.0], dtype=np.float32))
    (tmp_path / "selected_manifest.json").write_text(json.dumps([{"path": "sample.wav"}]))
    stats = audio._vsasv_waveform_stats(tmp_path)
    assert stats == {"n_files": 1, "max_abs": 1.25, "out_of_range_files": 1}
    assert "1.25" in audio._vsasv_amplitude_note(stats)
    assert wavfile.read(path)[1][0] == -1.25
