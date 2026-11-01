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


def _load_parity_script():
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts" / "parity_nes2net.py"
    spec = importlib.util.spec_from_file_location("parity_nes2net", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parity_reads_native_wav_and_keeps_exact_scored_samples(tmp_path, speech):
    import wave

    pytest.importorskip("soundfile")
    parity = _load_parity_script()
    t = np.arange(64000, dtype=np.float32) / 16000
    pcm = (np.sin(2 * np.pi * 220 * t) * 10000).astype("<i2")
    audio = tmp_path / "native.wav"
    with wave.open(str(audio), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(pcm.tobytes())
    records, windows = parity.prepare_window_records(audio_files=[audio])
    assert windows.shape == (1, 64000)
    np.testing.assert_array_equal(windows[0], pcm.astype(np.float32) / 32768)
    assert records[0]["synthetic"] is False
    assert records[0]["source_sha256"] == records[0]["window_sha256"]


def test_parity_compare_logits_enforces_tolerance_sign_and_sample_count():
    parity = _load_parity_script()
    converted = [
        {"window_index": i, "logits": [1.5 + 0.01 * i, -0.5], "margin_score": 2.0 + 0.01 * i}
        for i in range(32)
    ]
    reference = [[1.5 + 0.01 * i + 2e-5, -0.5 - 1e-5] for i in range(32)]
    passed = parity.compare_logits(converted, reference, synthetic=False)
    assert passed["status"] == "PASS" and passed["sign_agreement"] == 1.0

    # Synthetic or < 32 clips must remain UNVERIFIED even when numerically identical.
    assert parity.compare_logits(converted, reference, synthetic=True)["status"] == "UNVERIFIED"
    assert (
        parity.compare_logits(converted[:8], reference[:8], synthetic=False)["status"]
        == "UNVERIFIED"
    )

    # Duplicate clips/windows must not count as 32 independent samples for PASS.
    unique_records = [
        {
            "clip_id": f"clip_{i}.wav",
            "audio_sha256": f"{i:064x}",
            "source_sha256": f"{i + 100:064x}",
            "window_sha256": f"{i + 200:064x}",
        }
        for i in range(32)
    ]
    assert (
        parity.compare_logits(converted, reference, synthetic=False, records=unique_records)[
            "status"
        ]
        == "PASS"
    )
    duplicated_records = [dict(unique_records[i % 16]) for i in range(32)]
    dup_cmp = parity.compare_logits(
        converted, reference, synthetic=False, records=duplicated_records
    )
    assert dup_cmp["status"] == "UNVERIFIED"
    assert dup_cmp["independent_sample_count"] == 16
    assert dup_cmp["diversity"]["all_unique"] is False

    # Exceeding logit tolerance or flipping margin sign must FAIL.
    drifted = [[row[0] + 5e-4, row[1]] for row in reference]
    assert parity.compare_logits(converted, drifted, synthetic=False)["status"] == "FAIL"
    flipped = [{"window_index": 0, "logits": [1e-6, 0.0], "margin_score": 1e-6}] * 32
    flipped_ref = [[-1e-6, 0.0]] * 32
    assert parity.compare_logits(flipped, flipped_ref, synthetic=False)["status"] == "FAIL"


def test_parity_cli_without_reference_stays_unverified_with_exit_code_two(monkeypatch, tmp_path):
    parity = _load_parity_script()

    class StubBackend:
        def __init__(self, _root):
            self.model_hashes = {"nes2net-x-xlsr/checkpoint.pth": "a" * 64}
            self.load_report = {"missing_keys": [], "unexpected_keys": [], "ignored_keys": []}
            self.config = {"model_subdir": "nes2net-x-xlsr", "checkpoint": "checkpoint.pth"}

        def preload(self):
            pass

        def logits(self, window):
            assert window.shape == (64000,) and window.dtype == np.float32
            return np.array([float(window[0]), -float(window[0])], dtype=np.float32)

    monkeypatch.setattr(parity.nes2net, "Nes2NetBackend", StubBackend)
    out = tmp_path / "parity.json"
    code = parity.main(["--models-dir", str(tmp_path), "--synthetic-smoke", "--output", str(out)])
    report = json.loads(out.read_text(encoding="utf-8"))
    assert code == 2
    assert report["status"] == "UNVERIFIED"
    assert report["reference_runtime"] is None
    assert len(report["windows"]) == 4


def test_parity_reference_worker_executes_upstream_wav2vec2_nes2net_contract(monkeypatch, tmp_path):
    import hashlib
    import pickle
    from pathlib import Path

    parity = _load_parity_script()
    upstream_dir = tmp_path / "upstream"
    (upstream_dir / "model_scripts").mkdir(parents=True)
    xlsr_path = tmp_path / "xlsr2_300m.pt"
    xlsr_path.write_bytes(b"xlsr-stub")
    ckpt_path = tmp_path / "checkpoint.pth"

    # Provide a numpy-backed torch stub inside upstream_dir so this subprocess contract test
    # runs both in lightweight CI venvs (without torch) and in full ML venvs.
    torch_pkg = upstream_dir / "torch"
    torch_pkg.mkdir()
    (torch_pkg / "__init__.py").write_text(
        """from contextlib import nullcontext
import pickle
import numpy as np
from . import nn

__version__ = "1.13.1+stub"
float16 = "float16"
float32 = "float32"
threads = None
seed = None

def set_num_threads(n):
    global threads
    threads = n

def manual_seed(s):
    global seed
    seed = s

def no_grad():
    return nullcontext()

def inference_mode():
    return nullcontext()

class Tensor:
    def __init__(self, arr, device="cpu", dtype=float32):
        np_dtype = np.float16 if dtype == float16 else np.float32
        self._arr = np.asarray(arr, dtype=np_dtype)
        self.device = device
        self.dtype = dtype

    def to(self, device=None, dtype=None):
        return Tensor(
            self._arr,
            device=self.device if device is None else device,
            dtype=self.dtype if dtype is None else dtype,
        )

    def unsqueeze(self, axis=0):
        return Tensor(np.expand_dims(self._arr, axis=axis), self.device, self.dtype)

    def squeeze(self, axis=-1):
        if self._arr.shape[axis] == 1:
            return Tensor(np.squeeze(self._arr, axis=axis), self.device, self.dtype)
        return self

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self._arr

def from_numpy(arr):
    return Tensor(arr, device="cpu", dtype=float32)

def load(path, map_location="cpu", weights_only=True):
    with open(path, "rb") as fh:
        raw = pickle.load(fh)
    return {k: Tensor(v, device=map_location, dtype=float32) for k, v in raw.items()}
""",
        encoding="utf-8",
    )
    (torch_pkg / "nn.py").write_text(
        """import numpy as np

class Module:
    def __init__(self):
        self.training = True

    def _children(self):
        for val in self.__dict__.values():
            if isinstance(val, Module):
                yield val

    def parameters(self):
        for key, val in self.__dict__.items():
            if hasattr(val, "dtype") and hasattr(val, "device"):
                yield val
        for child in self._children():
            yield from child.parameters()

    def to(self, device=None, dtype=None):
        for key, val in list(self.__dict__.items()):
            if hasattr(val, "to") and not isinstance(val, Module):
                setattr(self, key, val.to(device=device, dtype=dtype))
        for child in self._children():
            child.to(device=device, dtype=dtype)
        return self

    def train(self, mode=True):
        self.training = bool(mode)
        for child in self._children():
            child.train(mode)
        return self

    def eval(self):
        return self.train(False)

    def __call__(self, *args, **kwargs):
        return self.forward(*args, **kwargs)
""",
        encoding="utf-8",
    )

    # Minimal Fairseq + upstream wav2vec2_Nes2Net_no_Res_w_allT contract matching
    # Liu-Tianchi/Nes2Net_ASVspoof_ITW/model_scripts/wav2vec2_Nes2Net_X.py:
    # - SSLModel calls fairseq.checkpoint_utils.load_model_ensemble_and_task(['xlsr2_300m.pt'])
    # - extract_feat flips self.model.train() if parameter dtype/device != input_data
    # - wav2vec2_Nes2Net_no_Res_w_allT reads args.n_output_logits, Nes_ratio, dilation, pool_func, SE_ratio
    fairseq_pkg = upstream_dir / "fairseq"
    fairseq_pkg.mkdir()
    (fairseq_pkg / "__init__.py").write_text(
        '__version__ = "0.12.2"\nfrom . import checkpoint_utils\n',
        encoding="utf-8",
    )
    task_pkg = fairseq_pkg / "tasks"
    task_pkg.mkdir()
    (task_pkg / "__init__.py").write_text("", encoding="utf-8")
    (task_pkg / "audio_pretraining.py").write_text(
        """class AudioPretrainingConfig:
    pass

class AudioPretrainingTask:
    def __init__(self, cfg):
        self.cfg = cfg
""",
        encoding="utf-8",
    )
    (fairseq_pkg / "checkpoint_utils.py").write_text(
        """import numpy as np
import torch
import torch.nn as nn

class _DummyW2V(nn.Module):
    def __init__(self):
        super().__init__()
        # Start in float16 to verify worker casts to float32 before load_state_dict/extract_feat
        self.weight = torch.Tensor(np.zeros((8, 4), dtype=np.float16), dtype=torch.float16)
        self.bias = torch.Tensor(np.zeros(8, dtype=np.float16), dtype=torch.float16)

    def forward(self, x, mask=False, features_only=True):
        arr = x.numpy().reshape(x.numpy().shape[0], -1, 4)
        out = arr @ self.weight.numpy().T + self.bias.numpy()
        return {"x": torch.Tensor(out, device=x.device, dtype=x.dtype)}

def load_model_ensemble_and_task(filenames, arg_overrides=None, **kwargs):
    assert filenames and ("/" in filenames[0] or "\\\\" in filenames[0])
    # XLS-R's legacy dataset config cannot be merged by Fairseq 0.12.2.
    # The worker must pass an inference-only task while preserving model config/weights.
    assert kwargs.get("task") is not None
    assert torch.threads == 4
    return [_DummyW2V()], None, None
""",
        encoding="utf-8",
    )
    upstream_script = upstream_dir / "model_scripts" / "wav2vec2_Nes2Net_X.py"
    script_text = """import numpy as np
import torch
import torch.nn as nn
import fairseq

class SSLModel(nn.Module):
    def __init__(self, device):
        super().__init__()
        cp_path = "xlsr2_300m.pt"
        model, cfg, task = fairseq.checkpoint_utils.load_model_ensemble_and_task([cp_path])
        self.model = model[0]
        self.device = device
        self.out_dim = 8

    def extract_feat(self, input_data):
        if (
            next(self.model.parameters()).device != input_data.device
            or next(self.model.parameters()).dtype != input_data.dtype
        ):
            self.model.to(input_data.device, dtype=input_data.dtype)
            self.model.train()
        return self.model(input_data, mask=False, features_only=True)["x"]

class wav2vec2_Nes2Net_no_Res_w_allT(nn.Module):
    def __init__(self, args, device):
        super().__init__()
        self.device = device
        self.n_output_logits = args.n_output_logits
        assert args.Nes_ratio == [8, 8]
        assert args.dilation == 2
        assert args.pool_func == "mean"
        assert args.SE_ratio == [1]
        self.ssl_model = SSLModel(self.device)
        self.head_weight = torch.Tensor(np.zeros((self.n_output_logits, 8), dtype=np.float32))
        self.head_bias = torch.Tensor(np.zeros(self.n_output_logits, dtype=np.float32))

    def load_state_dict(self, state, strict=True):
        expected = {
            "ssl_model.model.weight",
            "ssl_model.model.bias",
            "Nested_Res2Net_TDNN.weight",
            "Nested_Res2Net_TDNN.bias",
        }
        missing = sorted(expected - set(state.keys()))
        unexpected = sorted(set(state.keys()) - expected)
        if strict and (missing or unexpected):
            raise RuntimeError(f"missing={missing}, unexpected={unexpected}")
        self.ssl_model.model.weight = state["ssl_model.model.weight"]
        self.ssl_model.model.bias = state["ssl_model.model.bias"]
        self.head_weight = state["Nested_Res2Net_TDNN.weight"]
        self.head_bias = state["Nested_Res2Net_TDNN.bias"]
        return missing, unexpected

    def forward(self, x):
        feat = self.ssl_model.extract_feat(x.squeeze(-1))
        pooled = feat.numpy().mean(axis=1)
        logits = pooled @ self.head_weight.numpy().T + self.head_bias.numpy()
        return torch.Tensor(logits, device=feat.device, dtype=feat.dtype)
"""
    upstream_script.write_text(script_text, encoding="utf-8")
    monkeypatch.setattr(
        parity,
        "UPSTREAM_MODEL_SHA256",
        hashlib.sha256(upstream_script.read_bytes()).hexdigest(),
    )

    state = {
        "module.ssl_model.model.weight": np.full((8, 4), 0.25, dtype=np.float32),
        "module.ssl_model.model.bias": np.zeros(8, dtype=np.float32),
        "module.Nested_Res2Net_TDNN.weight": np.array([[1.0] * 8, [-0.5] * 8], dtype=np.float32),
        "module.Nested_Res2Net_TDNN.bias": np.array([0.1, -0.2], dtype=np.float32),
    }
    with ckpt_path.open("wb") as fh:
        pickle.dump(state, fh)

    windows = np.ones((2, parity.nes2net.WINDOW_SAMPLES), dtype=np.float32) * 0.5
    out = parity._run_reference_python(
        Path(sys.executable),
        upstream_dir,
        xlsr_path,
        ckpt_path,
        windows,
    )
    assert out["fairseq_version"] == "0.12.2"
    assert len(out["window_logits"]) == 2
    assert out["window_logits"][0] == pytest.approx([4.1, -2.2], abs=1e-5)
