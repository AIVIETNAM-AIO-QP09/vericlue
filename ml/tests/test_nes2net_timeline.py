"""Whole-utterance coverage, raw-only IPC and UI; synthetic PCM, no devices/weights."""

import io
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.eval.nes2net_client import Nes2NetClient, validate_reply
from vericlue_ml.eval.nes2net_worker import serve
from vericlue_ml.eval.voice_wire import MAX_REPLY, encode_request
from vericlue_ml.voice.asr import SpeechNotFound
from vericlue_ml.voice.nes2net_timeline import (
    VERSION,
    Nes2NetTimelineDetector,
    validate_timeline,
    window_bounds,
)


class Backend:
    def __init__(self):
        self.seen = []
        self.config = {"revision": "unit", "checkpoint": "unit", "sha256": "unit"}
        self.model_hashes = self.load_report = {}
        self._model = None

    def logits(self, window):
        self.seen.append(window.copy())
        return np.array([float(window.mean()), -1.0])


@pytest.fixture
def detector(monkeypatch):
    from vericlue_ml.voice import nes2net

    def vad(window):
        if not np.any(window):
            raise SpeechNotFound("synthetic silence")
        return 0, len(window)

    monkeypatch.setattr(nes2net, "speech_bounds", vad)
    return Nes2NetTimelineDetector(backend=Backend())


def rows(result):
    return result.evidence[0].value


@pytest.mark.parametrize("count", [1, 15999, 16000, 63999, 64000, 64001, 80000, 128000, 480000])
def test_windows_cover_source_without_gaps_and_have_a_bounded_tail(count):
    bounds = window_bounds(count)
    assert len(bounds) <= 8 and bounds[0][0] == 0 and bounds[-1][1] == count
    end = 0
    for start, stop in bounds:
        assert start <= end and 0 < stop - start <= 64000
        assert stop - start == min(count, 64000)
        end = stop


def test_later_audio_is_scored_with_exact_sample_boundaries_and_no_overlap_double_count(detector):
    samples = np.concatenate([np.full(64000, 0.1), np.full(16000, 0.8)]).astype(np.float32)
    original = samples.copy()
    result = detector.predict_samples(samples)
    assert result.status == "degraded" and result.gate == "unclear"
    assert result.score is None and result.prob_attack is None
    assert result.quality["measured_seconds"] == 5
    assert result.quality["measured_fraction"] == 1 and result.quality["measured_windows"] == 2
    assert [row["start_sample"] for row in rows(result)] == [0, 16000]
    assert rows(result)[0]["result"]["score"] != rows(result)[1]["result"]["score"]
    for (start, end), observed in zip(
        window_bounds(len(samples)), detector.backend.seen, strict=True
    ):
        np.testing.assert_array_equal(observed, samples[start:end])
    np.testing.assert_array_equal(samples, original)
    validate_timeline(result, len(samples))


def test_short_source_repeat_keeps_original_duration(detector):
    samples = np.linspace(-0.1, 0.2, 16000, dtype=np.float32)
    result = detector.predict_samples(samples)
    assert result.quality["measured_seconds"] == 1
    assert result.quality["repeated_to_four_seconds"]
    np.testing.assert_array_equal(detector.backend.seen[0], np.tile(samples, 4))
    validate_timeline(result, len(samples))


def test_silent_first_window_does_not_hide_later_speech_or_inflate_coverage(detector):
    samples = np.concatenate([np.zeros(64000), np.ones(64000) * 0.1]).astype(np.float32)
    result = detector.predict_samples(samples)
    assert result.quality["measured_seconds"] == 4
    assert result.quality["measured_fraction"] == 0.5
    assert not result.quality["all_source_samples_measured"]
    assert rows(result)[0]["result"]["status"] == "not_applicable"
    assert rows(result)[1]["result"]["status"] == "degraded"
    validate_timeline(result, len(samples))


def test_one_backend_failure_keeps_later_measurements_but_aggregate_stays_error(detector):
    original = detector.backend.logits

    def logits(window):
        if window[0] > 0.5:
            raise RuntimeError("PRIVATE_ERROR")
        return original(window)

    detector.backend.logits = logits
    samples = np.concatenate([np.ones(64000), np.ones(64000) * 0.1]).astype(np.float32)
    result = detector.predict_samples(samples)
    assert result.status == "error" and result.score is None
    assert result.quality["measured_seconds"] == 4 and result.quality["error_windows"] == 1
    assert "PRIVATE_ERROR" not in result.model_dump_json()
    validate_timeline(result, len(samples))


def test_all_silence_is_unmeasured_and_model_never_called(detector):
    result = detector.predict_samples(np.zeros(160000, np.float32))
    assert result.status == "not_applicable" and result.quality["measured_samples"] == 0
    assert not detector.backend.seen
    validate_timeline(result, 160000)


@pytest.mark.parametrize("count", [True, 0, -1, 480001, 1.5])
def test_invalid_count_rejected(count):
    with pytest.raises(ValueError):
        window_bounds(count)


@pytest.mark.parametrize(
    "samples,rate",
    [
        (np.zeros(16000, np.int16), 16000),
        (np.zeros((16000, 1), np.float32), 16000),
        (np.full(16000, np.nan, np.float32), 16000),
        (np.zeros(16000, np.float32), 48000),
        (np.ones(16000, np.float32) * 2, 16000),
        (np.zeros(480001, np.float32), 16000),
    ],
)
def test_bad_input_does_not_touch_backend(detector, samples, rate):
    result = detector.predict_samples(samples, rate)
    assert result.status == "error" and result.error_code == "E_DECODE"
    assert not result.evidence and not detector.backend.seen


def worker_reply(detector, count=80000):
    samples = np.full(count, 0.1, np.float32)
    frame, checksum = encode_request(samples, "a" * 32)
    target = io.BytesIO()
    serve(io.BytesIO(frame), target, detector)
    raw = target.getvalue()
    assert len(raw) < MAX_REPLY
    return json.loads(raw), checksum


def validate(body, checksum):
    return validate_reply(
        json.dumps(body).encode() + b"\n",
        "a" * 32,
        checksum,
        expected_version=VERSION,
        sample_count=80000,
    )


def test_worker_binds_timeline_to_same_request_and_reuses_one_backend(detector):
    body, checksum = worker_reply(detector)
    validated = validate(body, checksum)
    assert validated["worker_available"] and validated["received_samples"] == 80000
    assert body["model_version"] == VERSION and len(detector.backend.seen) == 2


def test_client_timeline_flag_roundtrips_in_real_child_without_model(
    monkeypatch, tmp_path, detector
):
    template, _ = worker_reply(detector)
    original = subprocess.Popen
    processes = []
    source = """
import json, sys
template = json.loads(sys.argv[1])
for line in sys.stdin.buffer:
    header = json.loads(line)
    data = sys.stdin.buffer.read(header['samples'] * 4)
    body = dict(template, request_id=header['request_id'],
                pcm_float32_sha256=header['sha256'], received_samples=header['samples'])
    sys.stdout.buffer.write(json.dumps(body).encode() + b'\\n')
    sys.stdout.buffer.flush()
"""

    def spawn(args, **kwargs):
        if str(args[0]).lower().endswith("taskkill.exe"):
            return original(args, **kwargs)
        assert "--whole-utterance" in args and kwargs["shell"] is False
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        process = original([sys.executable, "-u", "-c", source, json.dumps(template)], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", spawn)
    client = Nes2NetClient(Path(sys.executable), tmp_path, whole_utterance=True)
    try:
        for _ in range(2):
            result = client.predict_samples(
                np.full(80000, 0.1, np.float32), cancelled=threading.Event()
            )
            assert result["worker_available"] and result["model_version"] == VERSION
            assert result["result"]["quality"]["measured_seconds"] == 5
        assert len(processes) == 1
    finally:
        client.close()
    processes[0].wait(timeout=5)


@pytest.mark.parametrize("changed", [False, True])
def test_cli_selects_timeline_protocol_and_drops_measurements_if_file_changed(
    detector, monkeypatch, tmp_path, changed
):
    from vericlue_ml.eval import nes2net_voice
    from vericlue_ml.voice import nes2net_timeline

    audio, output = tmp_path / "input.wav", tmp_path / "output.json"
    audio.write_bytes(b"synthetic input for hash only")
    sample_result = detector.predict_samples(np.full(80000, 0.1, np.float32))

    def predict(inp):
        assert inp.audio == audio
        if changed:
            audio.write_bytes(b"different input")
        return sample_result

    monkeypatch.setattr(
        nes2net_timeline,
        "Nes2NetTimelineDetector",
        lambda _root: type(
            "FakeDetector",
            (),
            {"version": VERSION, "backend": detector.backend, "predict": staticmethod(predict)},
        )(),
    )
    code = nes2net_voice.main(
        [
            "--whole-utterance",
            "--audio",
            str(audio),
            "--output",
            str(output),
            "--models-dir",
            str(tmp_path / "models"),
        ]
    )
    body = json.loads(output.read_text(encoding="utf-8"))
    assert body["protocol"] == "timeline_4s_end_anchored_tail_no_aggregation_v1"
    assert body["model_version"] == VERSION and code == int(changed)
    if changed:
        assert body["result"]["error_code"] == "E_INTEGRITY"
        assert not body["result"].get("evidence")
    else:
        assert body["result"]["quality"]["measured_seconds"] == 5


@pytest.mark.parametrize(
    "kind",
    [
        "count",
        "coverage",
        "missing",
        "shifted",
        "nan",
        "pass",
        "probability",
        "window_score",
        "nested_pass",
        "nested_probability",
        "nested_latency",
        "wrong_version",
        "false_error",
    ],
)
def test_forged_or_incomplete_timeline_cannot_claim_coverage(detector, kind):
    body, checksum = worker_reply(detector)
    result = body["result"]
    segments = result["evidence"][0]["value"]
    if kind == "count":
        body["received_samples"] = 64000
    elif kind == "coverage":
        result["quality"]["measured_samples"] = 160000
    elif kind == "missing":
        segments.pop()
    elif kind == "shifted":
        segments[1]["start_sample"] += 1
    elif kind == "nan":
        segments[1]["start_s"] = float("nan")
    elif kind == "pass":
        result.update(status="ok", gate="pass")
    elif kind == "probability":
        result["prob_attack"] = 0.01
    elif kind == "window_score":
        segments[0]["result"]["score"] = -500
    elif kind == "nested_pass":
        segments[0]["result"].update(status="ok", gate="pass")
    elif kind == "nested_probability":
        segments[0]["result"]["prob_attack"] = 0.01
    elif kind == "nested_latency":
        segments[0]["result"]["latency_ms"] = float("inf")
    elif kind == "wrong_version":
        from vericlue_ml.voice.nes2net import VERSION as OLD_VERSION

        body["model_version"] = result["model_version"] = OLD_VERSION
    elif kind == "false_error":
        result.update(status="error", error_code="E_INTERNAL")
    with pytest.raises(ValueError):
        validate(body, checksum)


def test_mock_and_factory_do_not_change_http_backend():
    from vericlue_ml.registry import get_detector, get_nes2net_timeline
    from vericlue_ml.voice.antispoof import AntiDeepfakeDetector

    result = get_nes2net_timeline(mock=True).predict(DetectorInput())
    assert result.status == "degraded" and result.gate == "unclear" and result.score is None
    assert isinstance(get_detector("voice_spoof", mock=False), AntiDeepfakeDetector)
    first = get_nes2net_timeline()
    assert first is get_nes2net_timeline() and first.backend._model is None


def test_gui_text_keeps_error_and_unmeasured_regions_visible(detector):
    from vericlue_ml.eval.voice_lab import VoiceLab

    samples = np.concatenate([np.zeros(64000), np.ones(64000) * 0.1]).astype(np.float32)
    lab = object.__new__(VoiceLab)
    lab.payload = {"voice_spoof": {"result": detector.predict_samples(samples).to_contract()}}
    text = []
    lab._spoof_result = text.append
    lab.render_spoof()
    assert "4.00/8.00" in text[0] and "thiếu tiếng nói" in text[0]
    assert "4.00 → 8.00" in text[0] and "Còn vùng chưa đo" in text[0]
    assert "CHƯA KẾT LUẬN" in text[0] and "không phải xác suất" in text[0]


def test_timeline_client_preserves_expected_version_on_timeout(monkeypatch, tmp_path):
    from test_voice_worker import fake_spawn

    processes, _ = fake_spawn(monkeypatch, ["hang"])
    client = Nes2NetClient(Path(sys.executable), tmp_path, timeout=0.25, whole_utterance=True)
    try:
        result = client.predict_samples(np.zeros(80000, np.float32), cancelled=threading.Event())
        assert result["result"]["error_code"] == "E_TIMEOUT"
        assert result["result"]["model_version"] == VERSION
        assert result["result"].get("score") is None
    finally:
        client.close()
    processes[0].wait(timeout=5)


@pytest.mark.slow
def test_real_cpu_timeline_reuses_backend_on_synthetic_pcm(monkeypatch):
    root = os.getenv("NES2NET_MODELS_DIR")
    if not root:
        pytest.skip("Set NES2NET_MODELS_DIR in the pinned NES2Net runtime")
    from vericlue_ml.voice import nes2net

    # Isolate native model execution from VAD accuracy; no people, mic or files.
    monkeypatch.setattr(nes2net, "speech_bounds", lambda window: (0, len(window)))
    detector = Nes2NetTimelineDetector(Path(root))
    samples = np.random.default_rng(13).normal(0, 0.02, 80000).astype(np.float32)
    original = samples.copy()
    result = detector.predict_samples(samples)
    validate_timeline(result, len(samples))
    assert result.quality["measured_seconds"] == 5 and len(rows(result)) == 2
    loaded = detector.backend._model
    detector.preload()
    assert loaded is detector.backend._model and detector.backend.model_hashes
    assert detector.backend.load_report["missing_keys"] == []
    np.testing.assert_array_equal(original, samples)
