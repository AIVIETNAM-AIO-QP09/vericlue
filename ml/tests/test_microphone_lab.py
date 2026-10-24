"""Synthetic capture/model and headless GUI state tests; never open a microphone."""

import threading
from types import SimpleNamespace

import numpy as np
import pytest
from test_voice_matching import fake_match_libraries as fake_match_libraries

from vericlue_ml.eval.microphone import Recording, RecordingError, record_microphone
from vericlue_ml.eval.voice_trial import VoiceTrial
from vericlue_ml.voice.asr import ASRError, DecodeError, SpeechNotFound
from vericlue_ml.voice.qwen_asr import QwenASR, QwenVoiceChallengeDetector


class FakeStream:
    def __init__(self, *, stop=None, overflow=False, broken=False, cleanup_error=False):
        self.stop = stop
        self.overflow = overflow
        self.broken = broken
        self.cleanup_error = cleanup_error
        self.started = self.aborted = self.closed = False
        self.count = 0

    def start(self):
        self.started = True

    def read(self, count):
        self.count += count
        if self.stop:
            self.stop.set()
        if self.broken:
            raise RuntimeError("private device details")
        return np.ones((count, 1), np.float32) * 0.1, self.overflow

    def abort(self):
        self.aborted = True
        if self.cleanup_error:
            raise RuntimeError("abort failed")

    def close(self):
        self.closed = True


def backend_for(stream, rate=48000):
    calls = []

    def open_stream(**kwargs):
        calls.append(kwargs)
        return stream

    return SimpleNamespace(
        query_devices=lambda *_args: {"default_samplerate": rate}, InputStream=open_stream
    ), calls


def test_capture_is_bounded_and_uses_native_rate_without_saving(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stream = FakeStream()
    backend, calls = backend_for(stream)
    result = record_microphone(threading.Event(), backend=backend)
    assert len(result.samples) == 48000 * 20 and result.sample_rate == 48000
    assert result.samples.dtype == np.float32
    assert stream.started and stream.aborted and stream.closed
    assert calls[0]["channels"] == 1 and calls[0]["dtype"] == "float32"
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("overflow,broken", [(True, False), (False, True)])
def test_bad_recording_is_rejected_and_stream_released(overflow, broken):
    stream = FakeStream(overflow=overflow, broken=broken)
    backend, _ = backend_for(stream)
    with pytest.raises(RecordingError):
        record_microphone(threading.Event(), backend=backend)
    assert stream.closed and stream.aborted


def test_stop_returns_bounded_take_and_pre_cancel_never_opens():
    stop = threading.Event()
    stream = FakeStream(stop=stop)
    backend, calls = backend_for(stream)
    result = record_microphone(stop, backend=backend)
    assert len(result.samples) == 2400 and len(calls) == 1
    with pytest.raises(RecordingError):
        record_microphone(stop, backend=backend)
    assert len(calls) == 1


def test_abort_failure_still_closes_and_never_yields_a_valid_take():
    stream = FakeStream(cleanup_error=True, stop=threading.Event())
    backend, _ = backend_for(stream)
    with pytest.raises(RuntimeError):
        record_microphone(stream.stop, backend=backend)
    assert stream.closed


def test_cancel_during_open_closes_without_starting():
    stop = threading.Event()
    stream = FakeStream()

    def opening(**_kwargs):
        stop.set()
        return stream

    backend = SimpleNamespace(
        query_devices=lambda *_: {"default_samplerate": 16000}, InputStream=opening
    )
    with pytest.raises(RecordingError):
        record_microphone(stop, backend=backend)
    assert stream.closed and not stream.started


@pytest.mark.parametrize("rate", [0, 7999, 48000.5, 192001, float("nan")])
def test_invalid_rate_never_opens_microphone(rate):
    backend, calls = backend_for(FakeStream(), rate=rate)
    with pytest.raises(RecordingError):
        record_microphone(threading.Event(), backend=backend)
    assert not calls


@pytest.mark.parametrize(
    "samples,rate",
    [
        (np.zeros(100, np.int16), 16000),
        (np.zeros((16000, 1)), 16000),
        (np.full(16000, np.nan), 16000),
        (np.ones(16000) * 2, 16000),
        (np.zeros(16000), True),
        (np.zeros(16000 * 31), 16000),
    ],
)
def test_ram_asr_rejects_invalid_pcm_before_inference(samples, rate):
    provider = QwenASR()
    provider._infer = lambda *args, **kwargs: pytest.fail("must reject before inference")
    with pytest.raises(DecodeError):
        provider.transcribe_samples(samples, rate)


def test_ram_asr_resamples_then_uses_same_vad_and_count_only_budget(monkeypatch):
    from vericlue_ml.voice import qwen_asr

    observed = []
    provider = QwenASR()
    samples = np.ones(48000, np.float32) * 0.1

    def trim(audio, *, mode):
        assert audio.shape == (16000,) and mode == 1
        return audio

    monkeypatch.setattr(qwen_asr, "trim_silence", trim)
    provider._infer = lambda audio, **kwargs: observed.append(kwargs) or "tôi xác nhận"
    assert provider.transcribe_samples(samples, 48000, expected_syllable_count=12) == "tôi xác nhận"
    assert observed == [{"token_budget": 112}]
    assert np.all(samples == np.float32(0.1))


@pytest.mark.parametrize("kind", ["correct", "wrong", "silent", "decode", "backend"])
def test_ram_content_gate_fails_closed_like_file_path(kind, fake_match_libraries):
    def transcribe(samples, rate, *, expected_syllable_count):
        assert rate == 16000 and expected_syllable_count == 3
        if kind in ("silent", "decode", "backend"):
            raise {"silent": SpeechNotFound, "decode": DecodeError, "backend": ASRError}[kind](
                "private details"
            )
        return "tôi xác nhận" if kind == "correct" else "hôm nay trời đẹp"

    detector = QwenVoiceChallengeDetector(
        SimpleNamespace(version="synthetic@unit", transcribe_samples=transcribe)
    )
    result = detector.predict_samples(np.zeros(16000, np.float32), 16000, prompt="tôi xác nhận")
    assert result.gate == (
        "pass" if kind == "correct" else "fail" if kind == "wrong" else "unclear"
    )
    assert result.prob_attack is None and result.quality["diagnostic_only"]
    assert "private" not in result.model_dump_json()


def fake_detector(predict=None):
    from vericlue_ml.common.result import ModuleResult

    def result(*_args, **_kwargs):
        return ModuleResult(
            module="voice_challenge",
            model_version="synthetic@unit",
            status="ok",
            gate="pass",
            latency_ms=1,
        )

    return SimpleNamespace(
        version="synthetic@unit",
        predict_samples=predict or result,
        asr=SimpleNamespace(config={"revision": "synthetic"}, model_hashes={}, _model=None),
    )


def finish_thread(trial):
    trial.thread.join(timeout=5)
    assert not trial.thread.is_alive()


def test_trial_has_no_auto_record_keeps_one_job_and_wipes_audio():
    entered, released = threading.Event(), threading.Event()
    samples = np.ones(16000, np.float32) * 0.1

    def recorder(stop, *, device, started):
        entered.set()
        assert released.wait(5)
        started()
        return Recording(samples, 16000)

    trial = VoiceTrial(fake_detector(), recorder=recorder)
    assert not entered.is_set() and not trial.active
    assert trial.start("tôi xác nhận") and entered.wait(5)
    assert not trial.start("another phrase")
    released.set()
    finish_thread(trial)
    events = trial.poll()
    payload, error = events[-1][1]
    assert not error and payload["sample_count"] == 1
    assert payload["prompt_source"] == "local_random_not_server_authenticated"
    assert payload["result"]["gate"] == "pass"
    assert np.all(samples == 0) and not trial.active
    assert not any(key in payload for key in ("samples", "audio", "waveform"))


@pytest.mark.parametrize("stage", ["capture", "inference", "queued_result"])
def test_cancel_discards_even_already_queued_matching_result(stage):
    entered, released = threading.Event(), threading.Event()
    samples = np.ones(16000, np.float32) * 0.1
    detector = fake_detector()

    def barrier():
        entered.set()
        assert released.wait(5)

    def recorder(*_args, **kwargs):
        if stage == "capture":
            barrier()
        kwargs["started"]()
        return Recording(samples, 16000)

    original = detector.predict_samples

    def infer(*args, **kwargs):
        if stage == "inference":
            barrier()
        return original(*args, **kwargs)

    detector.predict_samples = infer
    trial = VoiceTrial(detector, recorder=recorder)
    trial.start("tôi xác nhận")
    if stage == "queued_result":
        finish_thread(trial)
    else:
        assert entered.wait(5)
    trial.cancel()
    assert not trial.start("overlapping")
    released.set()
    finish_thread(trial)
    assert trial.poll() == [("done", (None, None))]
    assert not trial.active and np.all(samples == 0)


def test_close_requests_stop_and_never_accepts_new_take():
    entered = threading.Event()

    def recorder(stop, **_kwargs):
        entered.set()
        assert stop.wait(5)
        raise RecordingError("private")

    trial = VoiceTrial(fake_detector(), recorder=recorder)
    trial.start("tôi xác nhận")
    assert entered.wait(5)
    trial.close()
    finish_thread(trial)
    assert trial.poll() == [("done", (None, None))]
    assert not trial.start("new take")


def test_capture_failure_does_not_run_detector_or_leak_error():
    def fail(*args, **kwargs):
        raise RecordingError("PRIVATE_DEVICE_IDENTIFIER")

    trial = VoiceTrial(
        fake_detector(lambda *args, **kwargs: pytest.fail("invalid capture cannot be scored")),
        recorder=fail,
    )
    trial.start("tôi xác nhận")
    finish_thread(trial)
    payload, error = trial.poll()[-1][1]
    assert payload is None and "PRIVATE_DEVICE_IDENTIFIER" not in error


def test_ui_preview_and_closed_window_never_start_capture_or_schedule_callbacks():
    from vericlue_ml.eval.voice_lab import VoiceLab

    lab = object.__new__(VoiceLab)
    lab.preview = True
    lab.closed = True
    lab.trial = SimpleNamespace(start=lambda *_: pytest.fail("preview cannot record"))
    lab.start()
    lab.tick()


def test_ui_renders_content_metrics_without_calling_it_voice_authenticity():
    from vericlue_ml.eval.voice_lab import VoiceLab

    lab = object.__new__(VoiceLab)
    rendered = []
    lab._result = rendered.append
    lab.payload = {
        "result": {
            "status": "ok",
            "gate": "pass",
            "latency_ms": 2000,
            "evidence": [{"name": "recognized_text", "value": "tôi xác nhận"}],
            "quality": {"syllable_error_rate": 0.0, "unaccented_similarity": 1.0},
        }
    }
    lab.render_result()
    assert "KHỚP CÂU" in rendered[0] and "Máy nghe: tôi xác nhận" in rendered[0]
    assert "WER): 0.000" in rendered[0] and "2.00 giây" in rendered[0]
    lab.payload["result"].update(status="error", gate="unclear", quality={}, evidence=[])
    lab.render_result()
    assert "CHƯA THỂ KIỂM CÂU" in rendered[1] and "KHỚP CÂU" not in rendered[1]


def test_ui_does_not_change_prompt_while_active():
    from vericlue_ml.eval.voice_lab import VoiceLab

    lab = object.__new__(VoiceLab)
    lab.trial = SimpleNamespace(active=True)
    lab.prompt = "original"
    lab.new_prompt()
    assert lab.prompt == "original"


def test_export_rejects_existing_file_and_model_folder(tmp_path):
    import json

    from vericlue_ml.eval.voice_lab import write_report

    models = tmp_path / "models"
    models.mkdir()
    report = tmp_path / "report.json"
    payload = {"expected_text": "tôi xác nhận", "sample_count": 1}
    write_report(report, payload, models_dir=models)
    assert json.loads(report.read_text(encoding="utf-8")) == payload
    with pytest.raises(FileExistsError):
        write_report(report, {"changed": True}, models_dir=models)
    with pytest.raises(ValueError):
        write_report(models / "weights.json", payload, models_dir=models)
    assert json.loads(report.read_text(encoding="utf-8")) == payload
    assert not list(models.iterdir())


def test_ram_silence_never_loads_real_model(monkeypatch):
    from vericlue_ml.voice import qwen_asr

    def silent(*args, **kwargs):
        raise SpeechNotFound("none")

    monkeypatch.setattr(qwen_asr, "trim_silence", silent)
    provider = QwenASR()
    provider._infer = lambda *args, **kwargs: pytest.fail("silence should skip inference")
    with pytest.raises(SpeechNotFound):
        provider.transcribe_samples(np.zeros(16000, np.float32), 16000)
