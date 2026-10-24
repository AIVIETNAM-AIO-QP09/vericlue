"""RAM windows, raw-only results and voice-lab isolation without model/device access."""

import json
import sys
import threading
from types import SimpleNamespace

import numpy as np
import pytest
from test_microphone_lab import fake_detector, finish_thread

from vericlue_ml.common.av_recording import AVRecording, EncodedVideoFrame
from vericlue_ml.eval.voice_trial import VoiceTrial
from vericlue_ml.voice import av_lipsync as lip
from vericlue_ml.voice.align import Alignment, SyllableSpan, TimeSpan


def recording():
    return AVRecording(
        np.full(64000, 0.1, np.float32),
        16000,
        [EncodedVideoFrame(i / 25, bytearray([i % 256])) for i in range(100)],
        {"clock": lip.CLOCK, "hardware_sync_verified": False},
    )


def fake_model(monkeypatch):
    alignment = Alignment(
        (SyllableSpan("bà", 0.1, 1.0), SyllableSpan("mẹ", 1.1, 2.3)), (), (TimeSpan(0.1, 2.3),), ()
    )
    aligner = SimpleNamespace(
        preload=lambda **kw: None,
        align_samples=lambda *a: alignment,
        _backend=SimpleNamespace(model_hashes={}),
    )
    loads = []
    backend = SimpleNamespace(
        preload=lambda **kw: loads.append(True), embed_video=lambda frames: np.array([1.0, 0.0])
    )
    monkeypatch.setattr(lip, "_verified_weights", lambda *a: (None, "unit"))
    monkeypatch.setattr(lip, "speech_bounds", lambda samples: (0, len(samples)))
    monkeypatch.setattr(lip, "_mel_spectrogram", lambda samples: np.zeros((80, 400), np.float32))
    monkeypatch.setattr(
        lip,
        "_audio_offset_embeddings",
        lambda backend, mel, starts: {
            offset: np.tile([1.0, 0.0] if offset == 2 else [0.5, np.sqrt(0.75)], (len(starts), 1))
            for offset in range(-15, 16)
        },
    )
    monkeypatch.setattr(lip, "_face_crop", lambda image, finder: image)
    fakecv = SimpleNamespace(
        IMREAD_COLOR=1, imdecode=lambda data, flag: np.full((2, 2, 3), data[0], np.uint8)
    )
    monkeypatch.setitem(sys.modules, "cv2", fakecv)
    return lip.RamLipSyncDetector(aligner=aligner, finder=object(), backend=backend), loads


def test_raw_ram_sync_is_cached_and_has_no_attack_probability(monkeypatch):
    model, loads = fake_model(monkeypatch)
    take = recording()
    first = model.predict_recording(take, prompt="bà mẹ")
    second = model.predict_recording(take, prompt="bà mẹ")
    assert first.status == second.status == "degraded" and second.gate == "unclear"
    assert second.score is second.prob_attack is None and not second.is_usable
    values = {e.name: e.value for e in second.evidence}
    assert (
        values["av_offset_ms"] == 80
        and values["best_offset_confidence"] > values["sync_confidence"]
    )
    assert loads == [True] and model.provenance()["model_loaded"]
    assert take.frames and take.samples.any()


def test_video_selection_preserves_audio_relative_preroll(monkeypatch):
    model, _ = fake_model(monkeypatch)
    take = recording()
    for frame in take.frames:
        frame.at_s -= 0.2
    windows = lip.read_ram_windows(take, [0], model.finder)
    assert (
        windows[0][0][0, 0, 0] == 5
    )  # PTS 0 is original frame 5, not independently reset frame 0.
    take.frames = [take.frames[0], take.frames[-1]]
    with pytest.raises(lip.SyncNetError):
        lip.read_ram_windows(take, [25], model.finder)


@pytest.mark.parametrize("broken", ["clock", "rate", "nan", "timestamps"])
def test_bad_recording_does_not_load_models(monkeypatch, broken):
    model, loads = fake_model(monkeypatch)
    take = recording()
    if broken == "clock":
        take.metadata["clock"] = "two_independent_recordings"
    if broken == "rate":
        take.sample_rate = 48000
    if broken == "nan":
        take.samples[0] = np.nan
    if broken == "timestamps":
        take.frames[1].at_s = take.frames[0].at_s
    result = model.predict_recording(take, prompt="bà mẹ")
    assert result.status == "error" and result.gate == "unclear"
    assert not loads and not result.evidence


def test_lipsync_failure_preserves_qwen_result_and_wipes_av(monkeypatch):
    model, _ = fake_model(monkeypatch)

    def fail(*a, **kw):
        raise RuntimeError("PRIVATE_LIPSYNC")

    model.predict_recording = fail
    take = recording()
    jpeg = take.frames[0].jpeg
    trial = VoiceTrial(fake_detector(), recorder=lambda *a, **kw: take, lipsync=model)
    trial.start("bà mẹ")
    finish_thread(trial)
    body, error = trial.poll()[-1][1]
    assert error is None and body["result"]["gate"] == "pass"
    assert body["lipsync"]["result"]["status"] == "error"
    assert body["lipsync"]["capture"]["video_sha256"]
    assert not take.samples.any() and not take.frames and not any(jpeg)
    assert "PRIVATE" not in json.dumps(body)


def test_cancel_during_lipsync_discards_output_and_closes_take(monkeypatch):
    model, _ = fake_model(monkeypatch)
    take = recording()
    entered, release = threading.Event(), threading.Event()
    original = model.predict_recording

    def block(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    model.predict_recording = block
    trial = VoiceTrial(fake_detector(), recorder=lambda *a, **kw: take, lipsync=model)
    trial.start("bà mẹ")
    assert entered.wait(5)
    trial.cancel()
    assert not trial.start("overlap")
    release.set()
    finish_thread(trial)
    assert trial.poll() == [("done", (None, None))]
    assert not take.frames and not take.samples.any()


def test_ram_mock_factory_does_not_replace_http_backend():
    from vericlue_ml.common.detector import DetectorInput
    from vericlue_ml.registry import get_detector, get_ram_lipsync

    result = get_ram_lipsync(mock=True).predict(DetectorInput())
    assert result.status == "degraded" and result.gate == "unclear"
    assert get_detector("lipsync", mock=False).__class__.__name__ == "SyncNetDetector"


def test_headless_ui_keeps_offset_as_raw_measurement():
    from vericlue_ml.eval.av_lab import AVLab

    lab = object.__new__(AVLab)
    rendered = []
    lab._lipsync_result = rendered.append
    lab.payload = {
        "lipsync": {
            "result": {
                "status": "degraded",
                "gate": "unclear",
                "latency_ms": 1000,
                "evidence": [
                    {"name": "av_offset_ms", "value": 80},
                    {"name": "sync_confidence", "value": 0.5},
                    {"name": "best_offset_confidence", "value": 0.8},
                ],
            }
        }
    }
    lab.render_lipsync()
    assert "80 ms" in rendered[0] and "không phải xác suất" in rendered[0]
    assert "CHƯA KẾT LUẬN" in rendered[0]


def test_four_checks_share_one_take_and_keep_results_separate(monkeypatch):
    from vericlue_ml.common.result import ModuleResult

    model, _ = fake_model(monkeypatch)
    take = recording()
    observed = []

    def spoof(samples, **kw):
        observed.append(samples)
        return {"result": {"status": "degraded", "gate": "unclear", "score": 0.7}}

    def timing(samples, rate, *, prompt):
        assert samples is observed[0] and prompt == "bà mẹ"
        return ModuleResult(
            module="voice_challenge",
            model_version="unit-timing",
            status="degraded",
            gate="unclear",
            latency_ms=1,
        )

    timing_model = SimpleNamespace(
        predict_samples=timing, provenance=lambda: {"model_version": "unit-timing"}
    )
    trial = VoiceTrial(
        fake_detector(),
        recorder=lambda *a, **kw: take,
        lipsync=model,
        spoof=SimpleNamespace(predict_samples=spoof),
        timing=timing_model,
    )
    trial.start("bà mẹ")
    finish_thread(trial)
    events = trial.poll()
    body, error = events[-1][1]
    assert error is None and body["result"]["gate"] == "pass"
    assert body["voice_spoof"]["result"]["score"] == 0.7
    assert (
        body["reading_timing"]["result"]["gate"] == body["lipsync"]["result"]["gate"] == "unclear"
    )
    assert (
        body["reading_timing"]["pcm_float32_sha256"]
        == body["lipsync"]["capture"]["pcm_float32_sha256"]
        == body["pcm_float32_sha256"]
    )
    assert [kind for kind, _ in events] == [
        "processing",
        "spoof_processing",
        "timing_processing",
        "lipsync_processing",
        "done",
    ]
    assert not take.frames and not observed[0].any()
