"""Explicit content selection stays separate from unchanged manual cutoffs."""

import hashlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.manual_demo import ManualDemoThresholds
from vericlue_ml.common.result import ModuleResult
from vericlue_ml.runtime import voice_client, voice_wire, voice_worker
from vericlue_ml.runtime.voice_client import VoiceWorkerClient
from vericlue_ml.voice.asr import ASRError
from vericlue_ml.voice.qwen_asr import VERSION as VERSION06

VERSION17 = (
    "qwen3-asr-17b@bcd2b5b7f32b480ab5790554cfa8347f246a14f3+cpu-fp32-content-v2-assistant-prefix"
)


def test_six_threshold_policy_hash_and_standard_worker_are_unchanged():
    policy = ManualDemoThresholds()
    assert policy.policy_id == "2f7e8becee1dff4d23831acd791adc449af3e12c2e0f314501930b1109b25ca8"
    assert len(policy.model_dump()) == 6
    assert voice_wire.worker_scope() == {}
    assert voice_wire.worker_hello() == {"protocol": voice_wire.PROTOCOL, "ready": True}
    assert voice_wire.expected_version("content") == VERSION06


def test_manual_worker_scope_and_hello_pin_the_selected_content_version():
    policy = ManualDemoThresholds()
    scope = voice_wire.worker_scope(policy, content_backend="qwen17")
    assert scope == {
        "mode": "manual_full_demo",
        "policy_id": policy.policy_id,
        "content_model_version": VERSION17,
    }
    hello = voice_wire.worker_hello(policy, ("content",), content_backend="qwen17")
    assert hello["loaded_versions"] == {"content": VERSION17}
    assert voice_wire.expected_version("content", policy, content_backend="qwen17") == VERSION17


@pytest.mark.parametrize(
    "backend,manual", [("qwen17", None), ("arbitrary", ManualDemoThresholds())]
)
def test_nonmanual_or_unknown_selection_is_rejected_before_start(tmp_path, backend, manual):
    with pytest.raises(ValueError):
        VoiceWorkerClient(
            Path(sys.executable),
            tmp_path,
            tmp_path,
            manual_demo=manual,
            warmup_kinds=("content",),
            content_backend=backend,
        )


def test_worker_uses_the_separate_subfolder_and_caches_one_content_model(monkeypatch, tmp_path):
    from vericlue_ml.voice import qwen17_asr

    calls = []

    class ASR:
        version = VERSION17

        def __init__(self, root):
            calls.append(("root", root))

        def preload(self, **kwargs):
            calls.append(("preload", kwargs))

    monkeypatch.setattr(qwen17_asr, "Qwen17ASR", ASR)
    models = voice_worker.VoiceModels(
        tmp_path, manual_demo=ManualDemoThresholds(), content_backend="qwen17"
    )
    first = models.detector("content")
    assert first is models.detector("content")
    models.preload(("content",))
    assert first.version == VERSION17
    assert calls == [("root", tmp_path / "qwen3-asr-17b-hf"), ("preload", {"device": "cpu"})]


def test_candidate_subfolder_cannot_resolve_outside_the_global_models_root(monkeypatch, tmp_path):
    root = tmp_path / "models"
    child = root / "qwen3-asr-17b-hf"
    outside = tmp_path / "outside"
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        # Simulate a directory junction without requiring Windows symlink privileges.
        return outside if path == child else original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    models = voice_worker.VoiceModels(
        root, manual_demo=ManualDemoThresholds(), content_backend="qwen17"
    )
    with pytest.raises(ValueError, match="outside MODELS_DIR"):
        models.detector("content")


def test_missing_candidate_never_announces_readiness(tmp_path):
    policy = ManualDemoThresholds()
    models = voice_worker.VoiceModels(tmp_path, manual_demo=policy, content_backend="qwen17")
    target = io.BytesIO()
    with pytest.raises(ASRError):
        voice_worker.serve(
            io.BytesIO(),
            target,
            models,
            tmp_path,
            manual_demo=policy,
            warmup_kinds=("content",),
            content_backend="qwen17",
        )
    assert not target.getvalue()


@pytest.mark.parametrize("announced", ["qwen06", "qwen17"])
def test_readiness_rejects_an_old_worker_hello_before_any_request(monkeypatch, tmp_path, announced):
    policy = ManualDemoThresholds()
    client = VoiceWorkerClient(
        Path(sys.executable),
        tmp_path,
        tmp_path,
        manual_demo=policy,
        warmup_kinds=("content",),
        content_backend="qwen17",
    )
    hello = voice_wire.worker_hello(policy, ("content",), content_backend=announced)
    process = SimpleNamespace(
        stdin=io.BytesIO(), stdout=io.BytesIO(voice_wire.canonical(hello) + b"\n")
    )
    commands = []
    monkeypatch.setattr(
        voice_client.subprocess,
        "Popen",
        lambda command, **kwargs: commands.append(command) or process,
    )
    monkeypatch.setattr(client, "_dispose", lambda _: None)
    if announced == "qwen06":
        with pytest.raises(ValueError, match="Invalid worker hello"):
            client.preload()
        assert client._failed
    else:
        client.preload()
        assert not client._failed
    assert commands[0][commands[0].index("--content-backend") + 1] == "qwen17"
    assert not process.stdin.getvalue()


@pytest.mark.parametrize("fault", [None, "scope", "version"])
def test_content_reply_cannot_cross_the_selected_model_boundary(monkeypatch, tmp_path, fault):
    policy = ManualDemoThresholds()
    client = VoiceWorkerClient(
        Path(sys.executable),
        tmp_path,
        tmp_path,
        manual_demo=policy,
        warmup_kinds=("content",),
        content_backend="qwen17",
    )
    audio = tmp_path / "fixture.wav"
    audio.write_bytes(b"synthetic")
    outgoing = []

    def reply(_):
        raw = outgoing[-1].rstrip(b"\n")
        request = json.loads(raw)
        body = {
            "protocol": voice_wire.PROTOCOL,
            **voice_wire.worker_scope(policy, content_backend="qwen17"),
            "request_id": request["request_id"],
            "request_sha256": hashlib.sha256(raw).hexdigest(),
            "sources": request["sources"],
            "result": ModuleResult(
                module="voice_challenge",
                model_version=VERSION06 if fault == "version" else VERSION17,
                status="ok",
                gate="pass",
                latency_ms=0,
            ).to_contract(),
        }
        if fault == "scope":
            del body["content_model_version"]
        return voice_wire.canonical(body) + b"\n"

    process = SimpleNamespace(
        stdin=SimpleNamespace(write=outgoing.append, flush=lambda: None),
        stdout=SimpleNamespace(readline=reply),
    )
    monkeypatch.setattr(client, "_start", lambda _: process)
    monkeypatch.setattr(client, "_dispose", lambda _: None)
    result = client.predict("content", DetectorInput(audio=audio))
    assert result.status == ("ok" if fault is None else "error")
    assert result.gate == ("pass" if fault is None else "unclear")
