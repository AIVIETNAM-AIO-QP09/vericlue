"""Audio batching preserves window order and fail-closed scores without Torch or weights."""

from __future__ import annotations

import sys
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Status
from vericlue_ml.voice import syncnet


class FakeTensor:
    def __init__(self, values):
        self.values = np.asarray(values)

    def __getitem__(self, index):
        return FakeTensor(self.values[index])

    def to(self, device):
        return self

    def flatten(self, start):
        assert start == 1
        return FakeTensor(self.values.reshape(len(self.values), -1))

    def cpu(self):
        return self

    def numpy(self):
        return self.values


@pytest.fixture
def fake_torch(monkeypatch):
    torch = ModuleType("torch")
    functional = ModuleType("torch.nn.functional")
    torch.from_numpy = FakeTensor
    torch.inference_mode = nullcontext
    functional.normalize = lambda tensor, dim: FakeTensor(
        tensor.values / np.linalg.norm(tensor.values, axis=dim, keepdims=True)
    )
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "torch.nn", ModuleType("torch.nn"))
    monkeypatch.setitem(sys.modules, "torch.nn.functional", functional)


@pytest.mark.parametrize("device", ["cpu", "cuda:0"])
def test_backend_minibatches_are_bounded_and_preserve_order(fake_torch, device):
    backend = syncnet.StableBackend()
    backend.device = device
    limit = syncnet.CPU_AUDIO_BATCH_SIZE if device == "cpu" else syncnet.GPU_AUDIO_BATCH_SIZE
    count = limit * 2 + 1
    calls = []

    def encoder(tensor):
        values = tensor.values
        assert values.shape[1:] == (1, 80, 52)
        calls.append(len(values))
        identifiers = values[:, 0, 0, 0]
        return FakeTensor(np.stack([identifiers + 1, np.ones(len(values))], axis=1))

    backend.model = SimpleNamespace(audio_encoder=encoder)
    mels = np.broadcast_to(np.arange(count, dtype=np.float32)[:, None, None], (count, 80, 52))
    embeddings = backend.embed_audio_batch(mels)
    expected = np.stack([np.arange(count) + 1, np.ones(count)], axis=1)
    expected = expected / np.linalg.norm(expected, axis=1, keepdims=True)
    assert calls == [limit, limit, 1]
    np.testing.assert_allclose(embeddings, expected)


def test_single_audio_window_delegates_to_batch_one(monkeypatch):
    backend = syncnet.StableBackend()
    captured = []
    expected = np.array([[0.2, 0.8]], dtype=np.float32)

    def batch(mels):
        captured.append(mels)
        return expected

    monkeypatch.setattr(backend, "embed_audio_batch", batch)
    mel = np.zeros((80, 52), dtype=np.float32)
    np.testing.assert_array_equal(backend.embed_audio(mel), expected[0])
    assert len(captured) == 1
    assert captured[0].shape == (1, 80, 52)


@pytest.mark.parametrize(
    "values",
    [
        np.empty((0, 80, 52)),
        np.zeros((80, 52)),
        np.zeros((1, 80, 51)),
        np.full((1, 80, 52), np.nan),
    ],
)
def test_backend_rejects_invalid_mels_before_importing_torch(values):
    with pytest.raises(ValueError, match="mel windows"):
        syncnet.StableBackend().embed_audio_batch(values)


def column_embedding(column):
    angle = np.asarray(column, dtype=np.float64) / 40
    return np.stack([np.cos(angle), np.sin(angle)], axis=-1)


class LegacyBackend:
    def __init__(self):
        self.columns = []

    def preload(self, **kwargs):
        pass

    def embed_video(self, crops):
        start = crops[0]
        column = int((start + 3) * (syncnet.AUDIO_SAMPLE_RATE / syncnet.MEL_HOP_SAMPLES) / 25)
        return column_embedding(column)

    def embed_audio(self, mel):
        column = float(mel[0, 0])
        self.columns.append(column)
        return column_embedding(column)


class BatchBackend(LegacyBackend):
    def __init__(self, invalid=None):
        super().__init__()
        self.batches = []
        self.invalid = invalid

    def embed_audio_batch(self, mels):
        self.batches.append(mels)
        columns = mels[:, 0, 0]
        self.columns.extend(columns.tolist())
        if self.invalid == "row_count":
            return np.ones((len(mels) - 1, 2))
        if self.invalid == "rank":
            return np.ones(len(mels))
        if self.invalid == "empty_dimension":
            return np.empty((len(mels), 0))
        if self.invalid == "nonfinite":
            return np.full((len(mels), 2), np.nan)
        if self.invalid == "zero":
            return np.zeros((len(mels), 2))
        return column_embedding(columns)


@pytest.fixture
def synthetic_pipeline(monkeypatch):
    alignment = SimpleNamespace(
        splice_events=[],
        syllables=[],
        aligned_segments=[SimpleNamespace(start_s=0.0, end_s=4.0)],
    )
    aligner = SimpleNamespace(preload=lambda **kwargs: None, align=lambda audio, prompt: alignment)
    monkeypatch.setattr(
        syncnet, "_read_windows", lambda video, starts, finder: [[start] * 16 for start in starts]
    )
    monkeypatch.setattr(syncnet, "load_audio", lambda audio: np.zeros(64000, dtype=np.float32))
    mel = np.broadcast_to(np.arange(500, dtype=np.float32), (80, 500))
    monkeypatch.setattr(syncnet, "_mel_spectrogram", lambda audio: mel)

    def predict(backend):
        detector = syncnet.SyncNetDetector(aligner=aligner, finder=object(), backend=backend)
        assert detector.version.endswith("voice05-v2")
        return detector.predict(
            DetectorInput(
                video=Path("unopened.mp4"),
                audio=Path("unopened.wav"),
                metadata={"prompt": "câu đề bài"},
            )
        )

    return predict, alignment


def test_detector_batches_unique_columns_once_and_preserves_serial_score(synthetic_pipeline):
    predict, alignment = synthetic_pipeline
    legacy, batched = LegacyBackend(), BatchBackend()
    serial_result, batch_result = predict(legacy), predict(batched)
    assert serial_result.status == batch_result.status == Status.OK
    assert batch_result.score == pytest.approx(serial_result.score, abs=1e-12)
    serial_evidence = {item.name: item.value for item in serial_result.evidence}
    batch_evidence = {item.name: item.value for item in batch_result.evidence}
    assert batch_evidence == serial_evidence
    assert batch_evidence["av_offset_ms"] == 120
    assert len(batched.batches) == 1
    assert batched.columns == legacy.columns
    assert len(batched.columns) == len(set(batched.columns))
    candidate_count = len(syncnet._window_starts(alignment)) * (2 * syncnet.MAX_OFFSET_FRAMES + 1)
    assert len(batched.columns) < candidate_count


@pytest.mark.parametrize("invalid", ["row_count", "rank", "empty_dimension", "nonfinite", "zero"])
def test_invalid_batch_output_returns_error_without_score(synthetic_pipeline, invalid):
    predict, _ = synthetic_pipeline
    result = predict(BatchBackend(invalid))
    assert result.status == Status.ERROR
    assert result.error_code == ErrorCode.E_INTERNAL
    assert result.score is result.prob_attack is None


def test_all_audio_bounds_are_checked_before_encoding():
    backend = BatchBackend()
    with pytest.raises(syncnet.SyncNetError) as caught:
        syncnet._audio_offset_embeddings(backend, np.zeros((80, 100), dtype=np.float32), [16, 1000])
    assert caught.value.status == "degraded"
    assert not backend.batches and not backend.columns
