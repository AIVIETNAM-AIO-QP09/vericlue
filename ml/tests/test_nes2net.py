"""NES2Net guards/mapping/CLI without Torch, weights, microphone or speech data."""

import hashlib
import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ModuleResult
from vericlue_ml.registry import get_detector, get_nes2net
from vericlue_ml.voice import nes2net
from vericlue_ml.voice.antispoof import ModelLoadError
from vericlue_ml.voice.asr import DecodeError, SpeechNotFound
from vericlue_ml.voice.nes2net import (
    Nes2NetBackend,
    Nes2NetDetector,
    map_checkpoint,
    prepare_samples,
)


@pytest.fixture
def speech(monkeypatch):
    seen = []
    monkeypatch.setattr(nes2net, "speech_bounds", lambda x: seen.append(x.copy()) or (0, len(x)))
    return seen


@pytest.mark.parametrize("length", [16000, 32000, 64000, 80000])
def test_first_four_seconds_repeat_crop_and_no_normalization(length, speech):
    original = np.linspace(-0.4, 0.8, length, dtype=np.float32)
    output = prepare_samples(original, 16000)
    assert output.shape == (64000,) and output.dtype == np.float32
    assert np.array_equal(output[: min(length, 64000)], original[:64000])
    if length < 64000:
        assert np.array_equal(output[length : 2 * length], original)
    assert np.array_equal(speech[0], output)
    assert not np.shares_memory(original, output)


@pytest.mark.parametrize(
    "samples,rate",
    [
        (np.zeros(16000), 16000),
        (np.zeros((16000, 1), np.float32), 16000),
        (np.zeros(16000, np.float32), 48000),
        (np.zeros(16000, np.float32), True),
        (np.full(16000, np.nan, np.float32), 16000),
        (np.ones(16000, np.float32) * 2, 16000),
        (np.zeros(16000 * 31, np.float32), 16000),
    ],
)
def test_invalid_pcm_never_reaches_model(samples, rate):
    with pytest.raises(DecodeError):
        prepare_samples(samples, rate)


def test_short_and_silent_input_are_not_accepted(monkeypatch):
    with pytest.raises(SpeechNotFound):
        prepare_samples(np.zeros(100, np.float32), 16000)

    def no_speech(_samples):
        raise SpeechNotFound("silent")

    monkeypatch.setattr(nes2net, "speech_bounds", no_speech)
    result = Nes2NetDetector(backend=object()).predict_samples(np.zeros(64000, np.float32))
    assert result.status == "not_applicable" and result.gate == "unclear"
    assert result.prob_attack is None and result.score is None


@pytest.mark.parametrize("logits", [[5, 1], [1, 5]])
def test_raw_margin_direction_and_degraded_always(logits, speech):
    result = Nes2NetDetector(backend=SimpleNamespace(logits=lambda _: logits)).predict_samples(
        np.ones(80000, np.float32) * 0.1
    )
    assert result.score == logits[0] - logits[1]
    assert result.status == "degraded" and result.gate == "unclear" and not result.is_usable
    assert result.prob_attack is None and result.quality["truncated"]
    assert result.quality["frontend_parity_verified"] is False
    assert result.quality["scored_start_s"] == 0 and result.quality["scored_seconds"] == 4


@pytest.mark.parametrize("logits", [[1], [1, 2, 3], [float("nan"), 0], [float("inf"), 0]])
def test_bad_logits_never_look_like_valid_diagnostic(logits, speech):
    result = Nes2NetDetector(backend=SimpleNamespace(logits=lambda _: logits)).predict_samples(
        np.ones(16000, np.float32) * 0.1
    )
    assert result.status == "error" and result.gate == "unclear" and result.score is None


def test_backend_failure_is_sanitized(speech):
    def fail(_):
        raise RuntimeError("PRIVATE_PATH")

    result = Nes2NetDetector(backend=SimpleNamespace(logits=fail)).predict_samples(
        np.ones(16000, np.float32) * 0.1
    )
    assert result.status == "error" and "PRIVATE_PATH" not in result.model_dump_json()


def small_state():
    return {
        "ssl_model.model.layer_norm.weight": np.zeros(4),
        "ssl_model.model.quantizer.vars": np.zeros(3),
        "Nested_Res2Net_TDNN.fc.weight": np.zeros((2, 4)),
    }


def test_mapping_keeps_full_inference_coverage_and_explicit_pretrain_extras():
    backbone, head, report = map_checkpoint(
        small_state(), {"feature_projection.layer_norm.weight": (4,)}, {"fc.weight": (2, 4)}
    )
    assert set(backbone) == {"feature_projection.layer_norm.weight"}
    assert set(head) == {"fc.weight"}
    assert report["missing_keys"] == [] and report["unexpected_keys"] == []
    assert report["ignored_keys"] == ["m_ssl.model.quantizer.vars"]


@pytest.mark.parametrize(
    "change", ["unknown", "missing_front", "missing_head", "shape", "unknown_front"]
)
def test_mapping_rejects_missing_mismatched_and_unexpected_weights(change):
    state = small_state()
    if change == "unknown":
        state["untrusted.module"] = np.zeros(1)
    elif change == "missing_front":
        state.pop("ssl_model.model.layer_norm.weight")
    elif change == "missing_head":
        state.pop("Nested_Res2Net_TDNN.fc.weight")
    elif change == "shape":
        state["Nested_Res2Net_TDNN.fc.weight"] = np.zeros((4, 2))
    else:
        state["ssl_model.model.unexpected.weight"] = np.zeros(1)
    with pytest.raises(ModelLoadError):
        map_checkpoint(state, {"feature_projection.layer_norm.weight": (4,)}, {"fc.weight": (2, 4)})


def local_backend(monkeypatch, tmp_path):
    root = tmp_path / "models"
    path = root / "nes2net-x-xlsr/checkpoint.pth"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic weights")
    config = {
        "revision": nes2net.REVISION,
        "model_subdir": "nes2net-x-xlsr",
        "checkpoint": "checkpoint.pth",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "cpu_threads": 4,
    }
    source = tmp_path / "config.yaml"
    source.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setenv("NES2NET_CONFIG", str(source))
    return Nes2NetBackend(root), path


def test_verified_load_once_and_root_device_guard(monkeypatch, tmp_path):
    backend, path = local_backend(monkeypatch, tmp_path)
    called = []
    backend._load_native = lambda p: called.append(p) or object()
    backend.preload()
    backend.preload()
    assert called == [path] and backend.model_hashes
    with pytest.raises(ModelLoadError):
        backend.preload(device="cuda")
    with pytest.raises(ModelLoadError):
        backend.preload(models_dir=tmp_path / "elsewhere")


@pytest.mark.parametrize("when", ["before", "during"])
def test_hash_failure_prevents_any_load_or_use_until_restart(monkeypatch, tmp_path, when):
    backend, path = local_backend(monkeypatch, tmp_path)
    if when == "before":
        path.write_bytes(b"tampered")
        backend._load_native = lambda _: pytest.fail("hash must precede native loading")
    else:

        def load(_):
            path.write_bytes(b"changed during load")
            return object()

        backend._load_native = load
    with pytest.raises(ModelLoadError):
        backend.preload()
    assert backend._model is None
    with pytest.raises(ModelLoadError):
        backend.preload()


def test_config_cannot_escape_model_root(monkeypatch, tmp_path):
    backend, _ = local_backend(monkeypatch, tmp_path)
    backend.config["model_subdir"] = "../outside"
    with pytest.raises(ModelLoadError):
        backend.preload()


@pytest.mark.parametrize("rate,channels", [(48000, 1), (16000, 2)])
def test_file_recipe_rejects_implicit_resample_or_channel_folding(
    monkeypatch, tmp_path, rate, channels
):
    path = tmp_path / "audio.wav"
    path.write_bytes(b"fixture")
    monkeypatch.setitem(
        sys.modules,
        "soundfile",
        SimpleNamespace(
            info=lambda _: SimpleNamespace(samplerate=rate, channels=channels, frames=64000)
        ),
    )
    result = Nes2NetDetector(backend=object()).predict(DetectorInput(audio=path))
    assert result.status == "error" and result.error_code == "E_DECODE"


def test_factory_preserves_default_backend_and_mock():
    assert isinstance(get_nes2net(), Nes2NetDetector)
    assert get_nes2net(mock=True) is get_detector("voice_spoof", mock=True)
    assert get_detector("voice_spoof", mock=False).version.startswith("mms-300m-antideepfake")


def test_missing_dependency_version_does_not_prevent_failure_report(monkeypatch):
    from vericlue_ml.eval import nes2net_voice

    def missing(name):
        raise nes2net_voice.importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(nes2net_voice.importlib.metadata, "version", missing)
    assert all(value is None for value in nes2net_voice.runtime_versions().values())


@pytest.mark.parametrize("change", [False, True])
def test_cli_records_provenance_and_invalidates_changed_audio(monkeypatch, tmp_path, change):
    from vericlue_ml.eval import nes2net_voice

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"before")
    output = tmp_path / "report.json"
    backend = SimpleNamespace(
        config={"revision": "unit", "checkpoint": "unit", "sha256": "unit"},
        model_hashes={},
        load_report={},
        _model=None,
    )

    def predict(_):
        if change:
            audio.write_bytes(b"changed")
        return ModuleResult(
            module="voice_spoof",
            model_version="unit",
            status="degraded",
            gate="unclear",
            score=1.0,
            latency_ms=0,
        )

    monkeypatch.setattr(
        nes2net_voice,
        "Nes2NetDetector",
        lambda _: SimpleNamespace(backend=backend, version="unit", predict=predict),
    )
    monkeypatch.setattr(nes2net_voice.importlib.metadata, "version", lambda _: "unit")
    code = nes2net_voice.main(
        ["--audio", str(audio), "--models-dir", str(tmp_path / "models"), "--output", str(output)]
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["sample_count"] == 1 and report["commit"]
    assert report["calibrated"] is False and report["frontend_parity_verified"] is False
    assert code == int(change)
    if change:
        assert report["result"]["error_code"] == "E_INTEGRITY"
        assert "score" not in report["result"]


@pytest.mark.parametrize("target", ["audio", "models", "existing"])
def test_cli_output_does_not_overwrite_inputs_models_or_existing_files(tmp_path, target):
    from vericlue_ml.eval.nes2net_voice import main

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"source")
    models = tmp_path / "models"
    existing = tmp_path / "existing.json"
    existing.write_text("keep")
    output = {"audio": audio, "models": models / "weights.json", "existing": existing}[target]
    with pytest.raises(SystemExit):
        main(["--audio", str(audio), "--models-dir", str(models), "--output", str(output)])
    assert audio.read_bytes() == b"source" and existing.read_text() == "keep"
