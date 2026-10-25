"""RAM worker protocol/lifecycle and combined trials; no devices or model weights."""

import hashlib
import io
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.result import ModuleResult
from vericlue_ml.eval.nes2net_client import Nes2NetClient, validate_reply
from vericlue_ml.eval.voice_wire import (
    MAX_HEADER,
    MAX_REPLY,
    PROTOCOL,
    encode_request,
    read_request,
)
from vericlue_ml.voice.nes2net import VERSION


def reply(request_id="a" * 32, checksum="b" * 64):
    return {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "pcm_float32_sha256": checksum,
        "model_version": VERSION,
        "frontend_parity_verified": False,
        "calibrated": False,
        "result": ModuleResult(
            module="voice_spoof",
            model_version=VERSION,
            status="degraded",
            gate="unclear",
            score=1.25,
            latency_ms=1,
        ).to_contract(),
    }


def raw_reply(body):
    return json.dumps(body).encode() + b"\n"


def test_wire_roundtrip_and_consecutive_frames_without_files():
    samples = np.linspace(-0.3, 0.2, 16000, dtype=np.float32)
    data, checksum = encode_request(samples, "a" * 32)
    source = io.BytesIO(data + data)
    for _ in range(2):
        header, received = read_request(source)
        assert header["sha256"] == checksum
        np.testing.assert_array_equal(received, samples)
    assert read_request(source) is None


@pytest.mark.parametrize(
    "kind",
    [
        "large_header",
        "missing_newline",
        "extra_key",
        "huge",
        "boolean_count",
        "rate",
        "hash",
        "truncated",
        "nonfinite",
    ],
)
def test_invalid_frame_is_rejected_before_provider(kind):
    frame, _ = encode_request(np.zeros(16000, np.float32), "a" * 32)
    line, pcm = frame.split(b"\n", 1)
    header = json.loads(line)
    if kind == "large_header":
        frame = b"x" * (MAX_HEADER + 1)
    elif kind == "missing_newline":
        frame = line
    elif kind == "truncated":
        frame = frame[:-4]
    else:
        if kind == "extra_key":
            header["prompt"] = "not permitted"
        elif kind == "huge":
            header["samples"] = 16000 * 1000000
        elif kind == "boolean_count":
            header["samples"] = True
        elif kind == "rate":
            header["sample_rate"] = 48000
        elif kind == "hash":
            header["sha256"] = "f" * 64
        elif kind == "nonfinite":
            pcm = np.full(16000, np.nan, dtype="<f4").tobytes()
            header["sha256"] = hashlib.sha256(pcm).hexdigest()
        frame = json.dumps(header).encode() + b"\n" + pcm
    with pytest.raises(ValueError):
        read_request(io.BytesIO(frame))


@pytest.mark.parametrize(
    "kind",
    [
        "wrong_id",
        "wrong_hash",
        "wrong_version",
        "calibrated",
        "pass",
        "probability",
        "nonfinite",
        "oversized",
        "error_with_score",
    ],
)
def test_reply_cannot_turn_old_or_invalid_output_into_acceptance(kind):
    body = reply()
    if kind == "wrong_id":
        body["request_id"] = "c" * 32
    elif kind == "wrong_hash":
        body["pcm_float32_sha256"] = "c" * 64
    elif kind == "wrong_version":
        body["model_version"] = "other"
    elif kind == "calibrated":
        body["calibrated"] = True
    elif kind == "pass":
        body["result"].update(status="ok", gate="pass")
    elif kind == "probability":
        body["result"]["prob_attack"] = 0.01
    elif kind == "nonfinite":
        body["result"]["score"] = float("nan")
    elif kind == "error_with_score":
        body["result"]["status"] = "error"
    else:
        body["padding"] = "x" * MAX_REPLY
    with pytest.raises(ValueError):
        validate_reply(raw_reply(body), "a" * 32, "b" * 64)


# A real child process, stdlib only: mimics wire behavior without importing a model.
FAKE_CHILD = r"""
import sys, json, time, os
version, mode = sys.argv[1:]
seen = 0
while True:
    line = sys.stdin.buffer.readline()
    if not line: break
    h = json.loads(line)
    data = sys.stdin.buffer.read(h['samples'] * 4)
    if mode == 'hang' or (mode == 'hang_after_one' and seen): time.sleep(20)
    if mode == 'exit': sys.exit(1)
    if mode == 'noise':
        sys.stdout.buffer.write(b'not json\n'); sys.stdout.buffer.flush(); continue
    seen += 1
    body = {'protocol': h['protocol'], 'request_id': h['request_id'],
            'pcm_float32_sha256': h['sha256'], 'model_version': version,
            'frontend_parity_verified': False, 'calibrated': False,
            'load_report': {'requests_seen': seen}, 'worker_pid': os.getpid(),
            'result': {'module': 'voice_spoof', 'model_version': version,
                       'status': 'degraded', 'gate': 'unclear', 'score': 1.25, 'latency_ms': 1}}
    if mode == 'old': body['request_id'] = 'old take'
    sys.stdout.buffer.write(json.dumps(body).encode() + b'\n')
    sys.stdout.buffer.flush()
"""


def fake_spawn(monkeypatch, mode):
    original = subprocess.Popen
    launched = []
    spawned = threading.Event()

    def launch(args, **kwargs):
        if str(args[0]).lower().endswith("taskkill.exe"):
            return original(args, **kwargs)
        assert "vericlue_ml.eval.nes2net_worker" in args
        assert kwargs["shell"] is False and kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        process = original([sys.executable, "-u", "-c", FAKE_CHILD, VERSION, mode[0]], **kwargs)
        launched.append(process)
        spawned.set()
        return process

    monkeypatch.setattr(subprocess, "Popen", launch)
    return launched, spawned


def test_child_is_lazy_reused_and_closed(monkeypatch, tmp_path):
    launched, _ = fake_spawn(monkeypatch, ["healthy"])
    client = Nes2NetClient(Path(sys.executable), tmp_path)
    assert not launched
    try:
        for index in (1, 2):
            body = client.predict_samples(np.zeros(16000, np.float32), cancelled=threading.Event())
            assert body["worker_available"] and body["result"]["status"] == "degraded"
            assert body["load_report"]["requests_seen"] == index
        assert len(launched) == 1
    finally:
        client.close()
    launched[0].wait(timeout=5)


@pytest.mark.parametrize("mode", ["hang", "exit", "noise", "old"])
def test_timeout_crash_or_wrong_take_is_unclear_and_restarts(monkeypatch, tmp_path, mode):
    modes = [mode]
    launched, _ = fake_spawn(monkeypatch, modes)
    client = Nes2NetClient(Path(sys.executable), tmp_path, timeout=0.25 if mode == "hang" else 5)
    try:
        body = client.predict_samples(np.zeros(16000, np.float32), cancelled=threading.Event())
        assert body["result"]["status"] == "error" and body["result"]["gate"] == "unclear"
        assert body["result"]["error_code"] == ("E_TIMEOUT" if mode == "hang" else "E_INTERNAL")
        assert body["round_trip_ms"] > 0 and body["request_id"]
        assert (
            body["pcm_float32_sha256"]
            == hashlib.sha256(np.zeros(16000, dtype="<f4").tobytes()).hexdigest()
        )
        launched[0].wait(timeout=5)
        modes[0] = "healthy"
        client.timeout = 5
        body = client.predict_samples(np.zeros(16000, np.float32), cancelled=threading.Event())
        assert body["worker_available"] and len(launched) == 2
    finally:
        client.close()


def test_cancel_terminates_child_and_discards_waiting_response(monkeypatch, tmp_path):
    launched, spawned = fake_spawn(monkeypatch, ["hang"])
    client = Nes2NetClient(Path(sys.executable), tmp_path, timeout=10)
    cancel = threading.Event()
    results = []
    thread = threading.Thread(
        target=lambda: results.append(
            client.predict_samples(np.zeros(16000, np.float32), cancelled=cancel)
        )
    )
    thread.start()
    assert spawned.wait(5)
    cancel.set()
    client.close()
    thread.join(timeout=5)
    assert not thread.is_alive() and results[0]["result"]["gate"] == "unclear"
    launched[0].wait(timeout=5)
    assert (
        client.predict_samples(np.zeros(16000, np.float32), cancelled=threading.Event())["result"][
            "status"
        ]
        == "error"
    )
    assert len(launched) == 1


def test_invalid_pcm_and_pre_cancel_never_spawn(monkeypatch, tmp_path):
    launched, _ = fake_spawn(monkeypatch, ["healthy"])
    client = Nes2NetClient(Path(sys.executable), tmp_path)
    assert (
        client.predict_samples(np.zeros(16000), cancelled=threading.Event())["result"]["status"]
        == "error"
    )
    stop = threading.Event()
    stop.set()
    assert (
        client.predict_samples(np.zeros(16000, np.float32), cancelled=stop)["result"]["gate"]
        == "unclear"
    )
    assert not launched


def test_close_during_slow_spawn_does_not_block_or_leave_a_child(monkeypatch, tmp_path):
    original = subprocess.Popen
    spawning, release, closed = threading.Event(), threading.Event(), threading.Event()
    processes = []

    def launch(_args, **kwargs):
        if str(_args[0]).lower().endswith("taskkill.exe"):
            return original(_args, **kwargs)
        spawning.set()
        assert release.wait(5)
        process = original([sys.executable, "-u", "-c", FAKE_CHILD, VERSION, "healthy"], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", launch)
    client = Nes2NetClient(Path(sys.executable), tmp_path)
    outcomes = []
    request = threading.Thread(
        target=lambda: outcomes.append(
            client.predict_samples(np.zeros(16000, np.float32), cancelled=threading.Event())
        )
    )
    request.start()
    assert spawning.wait(5)
    closer = threading.Thread(target=lambda: (client.close(), closed.set()))
    closer.start()
    try:
        assert closed.wait(2), "close cannot wait for OS process creation"
    finally:
        release.set()
    request.join(timeout=5)
    closer.join(timeout=5)
    assert not request.is_alive() and outcomes[0]["result"]["status"] == "error"
    processes[0].wait(timeout=5)


@pytest.mark.skipif(os.name != "nt", reason="Windows venv launcher process tree")
def test_windows_timeout_stops_real_python_child_not_only_venv_launcher(monkeypatch, tmp_path):
    import ctypes
    from ctypes import wintypes

    fake_spawn(monkeypatch, ["hang_after_one"])
    client = Nes2NetClient(Path(sys.executable), tmp_path, timeout=5)
    first = client.predict_samples(np.zeros(16000, np.float32), cancelled=threading.Event())
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = api.OpenProcess(0x00100000, False, first["worker_pid"])
    assert handle
    try:
        client.timeout = 0.25
        failed = client.predict_samples(np.zeros(16000, np.float32), cancelled=threading.Event())
        assert failed["result"]["error_code"] == "E_TIMEOUT"
        assert api.WaitForSingleObject(handle, 5000) == 0
    finally:
        api.CloseHandle(handle)
        client.close()


def test_server_reuses_detector_wipes_samples_and_keeps_stdout_protocol_clean():
    from vericlue_ml.eval.nes2net_worker import serve

    seen = []

    def predict(samples, _rate):
        seen.append(samples)
        print("provider progress, not protocol")
        return ModuleResult.model_validate(reply()["result"])

    backend = SimpleNamespace(
        config={"revision": "unit", "checkpoint": "unit", "sha256": "unit"},
        model_hashes={},
        load_report={},
        _model=None,
    )
    detector = SimpleNamespace(predict_samples=predict, backend=backend, version=VERSION)
    frame, checksum = encode_request(np.ones(16000, np.float32) * 0.1, "a" * 32)
    target = io.BytesIO()
    serve(io.BytesIO(frame + frame), target, detector)
    lines = target.getvalue().splitlines(keepends=True)
    assert len(seen) == 2 and len(lines) == 2
    assert all(np.all(x == 0) for x in seen)
    for line in lines:
        assert validate_reply(line, "a" * 32, checksum)["sample_count"] == 1


@pytest.mark.parametrize("content_gate", ["pass", "fail", "unclear"])
@pytest.mark.parametrize("worker_fails", [False, True])
def test_combined_trial_preserves_content_and_wipes_both_buffers(content_gate, worker_fails):
    from test_microphone_lab import fake_detector, finish_thread

    from vericlue_ml.eval.microphone import Recording
    from vericlue_ml.eval.voice_trial import VoiceTrial

    captured = np.ones(48000, np.float32) * 0.1
    received = []

    def content(*_args, **_kwargs):
        return ModuleResult(
            module="voice_challenge",
            model_version="synthetic@unit",
            status="error" if content_gate == "unclear" else "ok",
            gate=content_gate,
            latency_ms=0,
        )

    def spoof(samples, *, cancelled):
        assert samples.dtype == np.float32 and samples.shape == (16000,)
        received.append(samples)
        if worker_fails:
            raise RuntimeError("PRIVATE_PATH")
        return reply()

    trial = VoiceTrial(
        fake_detector(content),
        recorder=lambda *_a, **_kw: Recording(captured, 48000),
        spoof=SimpleNamespace(predict_samples=spoof),
    )
    assert trial.start("tôi xác nhận")
    finish_thread(trial)
    payload, error = trial.poll()[-1][1]
    assert not error and payload["result"]["gate"] == content_gate
    assert payload["voice_spoof"]["result"]["gate"] == "unclear"
    assert payload["voice_spoof"]["result"]["status"] == ("error" if worker_fails else "degraded")
    assert np.all(captured == 0) and np.all(received[0] == 0)
    assert "PRIVATE_PATH" not in json.dumps(payload)


def test_ui_never_labels_nes_score_as_authenticity_pass():
    from vericlue_ml.eval.voice_lab import VoiceLab

    lab = object.__new__(VoiceLab)
    rendered = []
    lab._spoof_result = rendered.append
    lab.payload = {"voice_spoof": reply()}
    lab.render_spoof()
    assert "CHƯA KẾT LUẬN" in rendered[0] and "1.2500" in rendered[0]
    assert "Chỉ chấm 4 giây đầu" in rendered[0] and "degraded / unclear" in rendered[0]
