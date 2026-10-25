"""Opt-in RAM demux + real SyncNet functional test; generated patterns, zero humans/devices."""

import io
import os
import shutil
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


@pytest.mark.slow
def test_synthetic_container_and_real_syncnet_cpu():
    root = os.getenv("AV_LIPSYNC_MODELS_DIR")
    ffmpeg = shutil.which("ffmpeg")
    if not root or not ffmpeg:
        pytest.skip("Set AV_LIPSYNC_MODELS_DIR and install FFmpeg in the separate A/V runtime")
    from vericlue_ml.eval.av_capture import read_av
    from vericlue_ml.face.pad import ScrfdFaceFinder, shared_scrfd_session
    from vericlue_ml.voice import av_lipsync as lip
    from vericlue_ml.voice.align import Alignment, SyllableSpan, TimeSpan
    from vericlue_ml.voice.asr import speech_bounds

    raw = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x240:rate=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=180:sample_rate=16000",
            "-t",
            "4",
            "-c:v",
            "mjpeg",
            "-q:v",
            "3",
            "-threads",
            "2",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-f",
            "matroska",
            "pipe:1",
        ],
        capture_output=True,
        timeout=20,
        check=True,
    ).stdout
    assert len(raw) < 8 * 1024 * 1024
    take = read_av(io.BytesIO(raw))
    assert len(take.frames) == 100 and len(take.samples) == 64000
    speech_bounds(take.samples)  # Actual VAD dependency, never a recording from a microphone.
    session, _ = shared_scrfd_session(Path(root), "cpu")
    assert ScrfdFaceFinder(session).find(np.zeros((240, 320, 3), np.uint8)) == []
    # Inject forced spans and a synthetic full-frame box to exercise native SyncNet on patterns.
    alignment = Alignment(
        (SyllableSpan("bà", 0.1, 1), SyllableSpan("mẹ", 1.1, 2.3)), (), (TimeSpan(0.1, 2.3),), ()
    )
    aligner = SimpleNamespace(preload=lambda **kw: None, align_samples=lambda *a: alignment)
    box = SimpleNamespace(x1=0, y1=0, x2=320, y2=240, area=76800)
    finder = SimpleNamespace(find=lambda frame: [box])
    model = lip.RamLipSyncDetector(Path(root), aligner=aligner, finder=finder)
    try:
        result = model.predict_recording(take, prompt="bà mẹ")
        assert result.status == "degraded" and result.gate == "unclear"
        assert result.score is result.prob_attack is None
        values = {e.name: e.value for e in result.evidence}
        assert all(
            np.isfinite(values[name])
            for name in ("av_offset_ms", "sync_confidence", "best_offset_confidence")
        )
        assert abs(values["av_offset_ms"]) <= 600 and model.provenance()["verified_model_hashes"]
        cached = model.backend.model
        model.preload()
        assert model.backend.model is cached
    finally:
        take.wipe()


@pytest.mark.slow
def test_real_ffmpeg_synthetic_capture_stops_and_reaps_without_devices(monkeypatch):
    if not os.getenv("AV_LIPSYNC_MODELS_DIR") or os.name != "nt" or not shutil.which("ffmpeg"):
        pytest.skip("Opt-in Windows FFmpeg/PyAV capture lifecycle test")
    from vericlue_ml.eval import av_capture as cap

    binary = cap.ffmpeg_path()
    args = [
        str(binary),
        "-hide_banner",
        "-loglevel",
        "error",
        "-re",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=320x240:rate=25",
        "-re",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=180:sample_rate=16000",
        "-t",
        "20",
        "-c:v",
        "mjpeg",
        "-q:v",
        "3",
        "-threads",
        "2",
        "-c:a",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-f",
        "matroska",
        "pipe:1",
    ]
    monkeypatch.setattr(cap, "capture_args", lambda *a: args)
    original = cap.subprocess.Popen
    processes = []

    def spawn(*a, **kw):
        process = original(*a, **kw)
        processes.append(process)
        return process

    monkeypatch.setattr(cap.subprocess, "Popen", spawn)
    stop = threading.Event()
    timer = threading.Timer(2, stop.set)
    recorder = cap.AVRecorder(binary)
    try:
        take = recorder(stop, started=timer.start)
        assert take.frames and 1 < len(take.samples) / 16000 < 20
        assert all(p.poll() is not None and p.stdin.closed and p.stdout.closed for p in processes)
        assert recorder.preview.qsize() == 1
        take.wipe()
    finally:
        timer.cancel()
