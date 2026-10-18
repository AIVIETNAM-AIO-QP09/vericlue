"""VOICE-05 synchrony/alignment regressions without weights, media or GPU."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Module, Status
from vericlue_ml.mock.detectors import MockDetector
from vericlue_ml.router.policy import TrustRouter
from vericlue_ml.voice import syncnet
from vericlue_ml.voice.align import AlignmentError


def alignment(*, splice=False, segments=((0.0, 4.0),)):
    return SimpleNamespace(
        aligned_segments=[SimpleNamespace(start_s=start, end_s=end) for start, end in segments],
        syllables=[SimpleNamespace(text="câu", start_s=0.0, end_s=4.0)],
        splice_events=[SimpleNamespace(kind="pause", start_s=1.0, end_s=2.1)] if splice else [],
    )


class FakeAligner:
    def __init__(self, value=None):
        self.value = value if value is not None else alignment()
        self.preloads = []
        self.calls = []

    def preload(self, *, models_dir, device):
        self.preloads.append((models_dir, device))

    def align(self, audio, prompt):
        self.calls.append((audio, prompt))
        return self.value


class FakeBackend:
    def __init__(self):
        self.preloads = []
        self.video_calls = []
        self.audio_calls = []

    def preload(self, *, models_dir, device):
        self.preloads.append((models_dir, device))

    def embed_video(self, crops):
        assert len(crops) == syncnet.SYNCNET_FRAMES
        assert all(crop.dtype == np.uint8 and crop.shape[-1] == 3 for crop in crops)
        self.video_calls.append(crops)
        return np.array([1.0, 0.0], dtype=np.float32)

    def embed_audio(self, mel):
        assert mel.shape == (syncnet.MEL_BANDS, syncnet.MEL_WINDOW_COLUMNS)
        assert mel.dtype == np.float32
        self.audio_calls.append(mel)
        return np.array([1.0, 0.0], dtype=np.float32)


@pytest.fixture
def pipeline(monkeypatch):
    aligner, backend = FakeAligner(), FakeBackend()
    finder = object()
    detector = syncnet.SyncNetDetector(
        models_dir=Path("synthetic-models"), aligner=aligner, backend=backend, finder=finder
    )
    windows = []

    def read_windows(video, starts, received_finder):
        assert received_finder is finder
        windows.append((video, starts))
        return [
            [np.zeros((4, 6, 3), dtype=np.uint8) for _ in range(syncnet.SYNCNET_FRAMES)]
            for _ in starts
        ]

    monkeypatch.setattr(syncnet, "_read_windows", read_windows)
    monkeypatch.setattr(syncnet, "load_audio", lambda path: np.zeros(64000, dtype=np.float32))
    monkeypatch.setattr(
        syncnet, "_mel_spectrogram", lambda audio: np.zeros((80, 500), dtype=np.float32)
    )
    return detector, aligner, backend, windows


def input_with_video(**metadata):
    return DetectorInput(
        audio=Path("unopened.wav"),
        video=Path("unopened.mp4"),
        metadata={"prompt": "câu đề bài phía máy chủ", **metadata},
    )


def test_measurement_uses_original_clock_confidence_and_attack_score_direction():
    visual = np.array([[1.0, 0.0], [1.0, 0.0]])
    unrelated = np.array([[0.0, 1.0], [0.0, 1.0]])
    genuine = syncnet.measure_sync(visual, {0: visual * 4, 10: unrelated})
    shifted = syncnet.measure_sync(visual, {0: unrelated, 10: visual})
    assert genuine.offset_ms == 0
    assert genuine.confidence == genuine.best_confidence == 1
    assert genuine.score == 0
    assert shifted.offset_ms == 400
    assert shifted.confidence == 0
    assert shifted.best_confidence == 1
    assert shifted.score == 1


def test_identical_offset_candidates_prefer_zero_without_inventing_delay():
    visual = np.array([[1.0, 0.0]])
    result = syncnet.measure_sync(visual, {-15: visual, 0: visual, 15: visual})
    assert result.offset_ms == result.score == 0


@pytest.mark.parametrize(
    "visual,audio",
    [
        (np.array([1.0, 0.0]), {0: np.array([[1.0, 0.0]])}),
        (np.empty((0, 2)), {0: np.empty((0, 2))}),
        (np.array([[1.0, 0.0]]), {1: np.array([[1.0, 0.0]])}),
        (np.array([[0.0, 0.0]]), {0: np.array([[1.0, 0.0]])}),
        (np.array([[np.nan, 0.0]]), {0: np.array([[1.0, 0.0]])}),
        (np.array([[1.0, 0.0]]), {0: np.array([[0.0, 0.0]])}),
        (np.array([[1.0, 0.0]]), {0: np.array([[np.inf, 0.0]])}),
        (np.array([[1.0, 0.0]]), {0: np.array([[1.0, 0.0], [1.0, 0.0]])}),
    ],
)
def test_measurement_rejects_missing_invalid_or_unequal_anchor_embeddings(visual, audio):
    with pytest.raises(ValueError):
        syncnet.measure_sync(visual, audio)


def test_all_offset_windows_stay_inside_original_disjoint_aligned_segments():
    segments = ((2.0, 6.0), (20.0, 24.0))
    starts = syncnet._window_starts(alignment(segments=segments))
    assert 0 < len(starts) <= syncnet.MAX_SYNC_WINDOWS
    assert any(start / syncnet.SYNCNET_FPS >= 20 for start in starts)
    for start in starts:
        left = (start - syncnet.MAX_OFFSET_FRAMES) / syncnet.SYNCNET_FPS
        right = (start + syncnet.SYNCNET_FRAMES + syncnet.MAX_OFFSET_FRAMES) / syncnet.SYNCNET_FPS
        assert any(
            segment_start <= left and right <= segment_end
            for segment_start, segment_end in segments
        )


def test_too_short_aligned_prompt_is_degraded_instead_of_measuring_outside_it():
    with pytest.raises(syncnet.SyncNetError) as caught:
        syncnet._window_starts(alignment(segments=((0, 0.3),)))
    assert caught.value.status == "degraded"


def test_no_video_is_not_applicable_without_preload_decode_or_inference(pipeline, monkeypatch):
    detector, aligner, backend, windows = pipeline

    def forbidden(**kwargs):
        raise AssertionError("No-video path must not preload")

    monkeypatch.setattr(detector, "preload", forbidden)
    result = detector.predict(DetectorInput(audio=Path("unopened.wav")))
    assert result.status == Status.NOT_APPLICABLE
    assert result.score is result.prob_attack is None
    assert not aligner.calls and not backend.video_calls and not backend.audio_calls and not windows
    values = {
        module: MockDetector(module).predict(DetectorInput())
        for module in (Module.VOICE_CHALLENGE, Module.VOICE_SPOOF)
    }
    values[Module.LIPSYNC] = result
    assert TrustRouter(profile="mvp").voice(values).status == "review"


@pytest.mark.parametrize("missing", ["audio", "prompt"])
def test_missing_audio_or_prompt_errors_before_preload(pipeline, missing):
    detector, aligner, backend, _ = pipeline
    inp = input_with_video()
    inp = inp.model_copy(update={"audio": None} if missing == "audio" else {"metadata": {}})
    result = detector.predict(inp)
    assert result.status == Status.ERROR
    assert result.score is result.prob_attack is None
    assert not aligner.preloads and not backend.preloads


def test_predict_aligns_server_prompt_and_keeps_raw_score_for_calibration(pipeline):
    detector, aligner, backend, windows = pipeline
    inp = input_with_video(transcript="ASR output must never replace the challenge")
    first = detector.predict(inp)
    second = detector.predict(inp)
    assert first.status == second.status == Status.OK
    assert first.score == second.score == 0
    assert first.prob_attack is None
    assert aligner.calls == [(inp.audio, inp.metadata["prompt"])] * 2
    assert len(aligner.preloads) == len(backend.preloads) == 1
    assert windows and windows[0][0] == inp.video
    assert all(start / syncnet.SYNCNET_FPS >= 0 for _, starts in windows for start in starts)
    assert any(item.name == "sync_confidence" and item.value == 1 for item in first.evidence)


def test_no_face_remains_not_applicable_and_keeps_alignment_evidence(pipeline, monkeypatch):
    detector, _, backend, _ = pipeline

    def no_face(*args):
        raise syncnet.SyncNetError("No face", ErrorCode.E_NO_FACE, "not_applicable")

    monkeypatch.setattr(syncnet, "_read_windows", no_face)
    result = detector.predict(input_with_video())
    assert result.status == Status.NOT_APPLICABLE
    assert result.error_code == ErrorCode.E_NO_FACE
    assert result.score is result.prob_attack is None
    assert any(item.name == "aligned_prompt" for item in result.evidence)
    assert not backend.video_calls and not backend.audio_calls


@pytest.mark.parametrize("where", ["preload", "align", "video", "audio"])
def test_backend_and_alignment_failures_cannot_produce_usable_probability(
    pipeline, monkeypatch, where
):
    detector, aligner, backend, _ = pipeline

    def failure(*args, **kwargs):
        raise AlignmentError("synthetic unavailable input")

    target, attribute = {
        "preload": (backend, "preload"),
        "align": (aligner, "align"),
        "video": (backend, "embed_video"),
        "audio": (backend, "embed_audio"),
    }[where]
    monkeypatch.setattr(target, attribute, failure)
    result = detector.predict(input_with_video())
    assert result.status == Status.ERROR
    assert result.score is result.prob_attack is None


def test_short_audio_window_is_degraded_and_retains_splice_flags(pipeline, monkeypatch):
    detector, aligner, _, _ = pipeline
    aligner.value = alignment(splice=True)
    monkeypatch.setattr(
        syncnet, "_mel_spectrogram", lambda audio: np.zeros((80, 1), dtype=np.float32)
    )
    result = detector.predict(input_with_video())
    assert result.status == Status.DEGRADED
    assert result.score is result.prob_attack is None
    assert any(item.name == "splice_flags" and item.value == 1 for item in result.evidence)


def test_aligner_splice_evidence_requires_high_priority_review_even_with_good_sync(pipeline):
    detector, aligner, _, _ = pipeline
    aligner.value = alignment(splice=True)
    result = detector.predict(input_with_video())
    assert result.status == Status.OK and result.score == 0
    flags = next(item.value for item in result.evidence if item.name == "splice_flags")
    assert flags == 1 and type(flags) is int
    values = {
        module: MockDetector(module).predict(DetectorInput())
        for module in (Module.VOICE_CHALLENGE, Module.VOICE_SPOOF)
    }
    values[Module.LIPSYNC] = result
    decision = TrustRouter(profile="mvp").voice(values)
    assert decision.status == "review" and decision.priority == "high"
