"""Bounded private IPC with synthetic bytes/results; no model, device or network."""

import hashlib
import io
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ModuleResult
from vericlue_ml.runtime.voice_client import VoiceWorkerClient
from vericlue_ml.runtime.voice_wire import (
    KINDS,
    PROTOCOL,
    canonical,
    expected_version,
    source_hashes,
)
from vericlue_ml.runtime.voice_worker import serve


def request(tmp_path, kind="content", request_id="a" * 32):
    audio = tmp_path / "synthetic.wav"
    audio.write_bytes(b"synthetic audio only")
    inp = DetectorInput(
        session_id="ses_synthetic",
        audio=audio,
        metadata={"prompt": "một hai ba", "voice_challenge_id": "vc_current"},
    )
    body = {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "kind": kind,
        "input": inp.model_dump(mode="json"),
        "sources": source_hashes(inp, tmp_path, kind),
    }
    return inp, body


@pytest.mark.parametrize("kind", ["content", "timing", "spoof"])
def test_worker_replies_are_bound_and_raw_kinds_cannot_pass(tmp_path, kind):
    inp, body = request(tmp_path, kind)
    calls = []

    class Models:
        def detector(self, actual):
            assert actual == kind

            def predict(actual_input):
                calls.append(actual_input)
                return ModuleResult(
                    module=KINDS[kind],
                    model_version=expected_version(kind),
                    status="ok",
                    gate="pass",
                    score=0.1,
                    latency_ms=0,
                )

            return SimpleNamespace(predict=predict)

    target = io.BytesIO()
    raw = canonical(body)
    serve(io.BytesIO(raw + b"\n"), target, Models(), tmp_path)
    ready, reply = [json.loads(line) for line in target.getvalue().splitlines()]
    assert ready == {"protocol": PROTOCOL, "ready": True}
    assert reply["request_id"] == body["request_id"]
    assert reply["request_sha256"] == hashlib.sha256(raw).hexdigest()
    assert calls[0].metadata == inp.metadata
    if kind != "content":
        assert reply["result"]["status"] == "degraded" and reply["result"]["gate"] == "unclear"


def test_changed_source_discards_inference_and_does_not_emit_score(tmp_path):
    inp, body = request(tmp_path)

    def predict(_):
        inp.audio.write_bytes(b"changed source")
        return ModuleResult(
            module="voice_challenge",
            model_version=expected_version("content"),
            status="ok",
            gate="pass",
            score=0,
            latency_ms=0,
        )

    target = io.BytesIO()
    serve(
        io.BytesIO(canonical(body) + b"\n"),
        target,
        SimpleNamespace(detector=lambda _: SimpleNamespace(predict=predict)),
        tmp_path,
    )
    result = json.loads(target.getvalue().splitlines()[1])["result"]
    assert result["status"] == "error" and result.get("score") is None


def test_paths_outside_media_root_never_reach_models(tmp_path):
    audio = tmp_path / "outside.wav"
    audio.write_bytes(b"synthetic")
    inside = tmp_path / "media"
    inside.mkdir()
    with pytest.raises(ValueError):
        source_hashes(DetectorInput(audio=audio), inside, "content")


@pytest.mark.parametrize(
    "fault", [None, "request_id", "digest", "sources", "version", "module", "nan", "truncated"]
)
def test_client_rejects_stale_or_invalid_results(tmp_path, monkeypatch, fault):
    inp, _ = request(tmp_path)
    client = VoiceWorkerClient(Path(sys.executable), tmp_path, tmp_path, timeout=1)
    outgoing = []

    def reply(_):
        raw = outgoing[-1].rstrip(b"\n")
        sent = json.loads(raw)
        body = {
            "protocol": PROTOCOL,
            "request_id": sent["request_id"],
            "request_sha256": hashlib.sha256(raw).hexdigest(),
            "sources": sent["sources"],
            "result": ModuleResult(
                module="voice_challenge",
                model_version=expected_version("content"),
                status="ok",
                gate="pass",
                score=0,
                latency_ms=0,
            ).to_contract(),
        }
        if fault == "request_id":
            body["request_id"] = "old"
        elif fault == "digest":
            body["request_sha256"] = "old"
        elif fault == "sources":
            body["sources"] = {}
        elif fault == "version":
            body["result"]["model_version"] = "other-model"
        elif fault == "module":
            body["result"]["module"] = "voice_spoof"
        elif fault == "nan":
            body["result"]["score"] = float("nan")
        encoded = json.dumps(body).encode() + b"\n"
        return encoded[:-1] if fault == "truncated" else encoded

    process = SimpleNamespace(
        stdin=SimpleNamespace(write=lambda raw: outgoing.append(raw), flush=lambda: None),
        stdout=SimpleNamespace(readline=reply),
    )
    monkeypatch.setattr(client, "_start", lambda _: process)
    result = client.predict("content", inp)
    assert result.gate == ("pass" if fault is None else "unclear")
    assert result.status == ("ok" if fault is None else "error")


def test_invalid_input_does_not_disable_worker_for_next_session(tmp_path):
    client = VoiceWorkerClient(Path(sys.executable), tmp_path, tmp_path)
    result = client.predict("content", DetectorInput())
    assert result.status == "error" and not client._failed and not client._closed


def test_queue_timeout_does_not_kill_other_session(tmp_path):
    inp, _ = request(tmp_path)
    client = VoiceWorkerClient(Path(sys.executable), tmp_path, tmp_path, timeout=0.02)
    ready, release = threading.Event(), threading.Event()

    def occupied():
        with client._lock:
            ready.set()
            release.wait(2)

    thread = threading.Thread(target=occupied)
    thread.start()
    try:
        assert ready.wait(1)
        result = client.predict("content", inp)
        assert result.error_code == "E_TIMEOUT"
        assert not client._failed and not client._closed
    finally:
        release.set()
        thread.join(2)


def test_transport_timeout_is_sticky_until_restart(tmp_path, monkeypatch):
    import queue

    inp, _ = request(tmp_path)
    client = VoiceWorkerClient(Path(sys.executable), tmp_path, tmp_path)
    monkeypatch.setattr(client, "_start", lambda _: None)
    monkeypatch.setattr(client, "_line", lambda *_: (_ for _ in ()).throw(queue.Empty()))
    result = client.predict("content", inp)
    assert result.error_code == "E_TIMEOUT" and result.gate == "unclear"
    assert client._failed and client._closed


@pytest.mark.parametrize("change_audio", [False, True])
def test_content_and_forced_timing_are_distinct_bound_results(tmp_path, change_audio):
    from vericlue_ml.router.config import load_config
    from vericlue_ml.voice.session import SessionVoiceDetector

    inp, _ = request(tmp_path)
    calls = []
    config = load_config().voice

    def predict(kind, actual, **_):
        calls.append(kind)
        assert actual.metadata["voice_match_config"] == config.model_dump(mode="json")
        if kind == "timing" and change_audio:
            inp.audio.write_bytes(b"another recording")
        return ModuleResult(
            module="voice_challenge",
            model_version=expected_version(kind),
            status="ok" if kind == "content" else "error",
            gate="pass" if kind == "content" else "unclear",
            latency_ms=0,
        )

    client = SimpleNamespace(media_root=tmp_path, timeout=1, predict=predict)
    result = SessionVoiceDetector(client, "content", match_config=config).predict(inp)
    assert calls == ["content", "timing"]
    if change_audio:
        assert result.status == "error" and result.gate == "unclear"
    else:
        # Forced alignment failure cannot overwrite independently recognized content;
        # it is an advisory result, never proof that the sentence was read correctly.
        assert result.status == "ok" and result.gate == "pass"
        assert result.quality["reading_timing_status"] == "error"
        assert result.evidence[-1].value["status"] == "error"
