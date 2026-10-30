"""Export regression checks; tiny networks and synthetic tensors, no real weights."""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.eval.onnx_export import _bundle, _cuda_reference, summarize
from vericlue_ml.eval.onnx_metrics import (
    ATTACK_INDICES,
    compare_outputs,
    inside,
    latency_summary,
    sha256,
    synthetic_inputs,
)


def outputs():
    return {
        "logits": np.array([[1, 2], [-1, 1]], dtype=np.float32),
        "probabilities": np.array([[0.25, 0.75], [0.1, 0.9]], dtype=np.float32),
    }


def test_checks_logits_even_when_argmax_is_unchanged():
    expected = outputs()
    actual = {key: value.copy() for key, value in expected.items()}
    actual["logits"] += 0.1
    result = compare_outputs(expected, actual, atol=1e-5, rtol=1e-4)
    assert not result["passed"] and result["argmax_agreement"] == 1
    assert not result["biometric_accuracy_evaluated"]


@pytest.mark.parametrize("corrupt", ["nan", "shape", "float16", "probability"])
def test_invalid_outputs_cannot_pass(corrupt):
    expected, actual = outputs(), outputs()
    if corrupt == "nan":
        actual["logits"][0, 0] = np.nan
    elif corrupt == "shape":
        actual["logits"] = actual["logits"][:1]
    elif corrupt == "float16":
        actual["logits"] = actual["logits"].astype(np.float16)
    else:
        actual["probabilities"][0, 0] = 2
    with pytest.raises(ValueError):
        compare_outputs(expected, actual, atol=1e-5, rtol=1e-4)


@pytest.mark.parametrize("values", [[], [0], [-1], [np.nan], [np.inf]])
def test_invalid_timings_are_rejected(values):
    with pytest.raises(ValueError):
        latency_summary(values)


def test_changed_bundle_bytes_and_traversal_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        inside(tmp_path, "../elsewhere")
    np.save(tmp_path / "inputs.npy", np.zeros((3, 3, 224, 224), np.float32))
    metadata = {
        "format": 1,
        "model": "fsvfm",
        "dtype": "float32",
        "input_shape": [1, 3, 224, 224],
        "samples": 3,
        "files": {"inputs.npy": sha256(tmp_path / "inputs.npy")},
    }
    (tmp_path / "bundle.json").write_text(json.dumps(metadata))
    assert _bundle(tmp_path)[1].shape == (3, 3, 224, 224)
    (tmp_path / "inputs.npy").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="integrity"):
        _bundle(tmp_path)


@pytest.mark.parametrize("model", ["fsvfm", "gend"])
def test_synthetic_inputs_are_reproducible_and_use_existing_preprocessing(model):
    first = synthetic_inputs(model)
    assert first.shape == (8, 3, 224, 224) and first.dtype == np.float32
    assert np.array_equal(first, synthetic_inputs(model))
    assert not np.array_equal(first, synthetic_inputs(model, seed=7))


def test_summary_rejects_comparing_different_artifacts(tmp_path):
    report = {
        "status": "ok",
        "model": "fsvfm",
        "device": "cpu",
        "dtype": "float32",
        "threads": 4,
        "input_shape": [1, 3, 224, 224],
        "input_sha256": "same",
        "bundle_sha256": "original",
        "warmup": 3,
        "latency": {"runs": 20},
        "parity": {"passed": True},
    }
    (tmp_path / "torch-cpu.json").write_text(json.dumps(report))
    report["bundle_sha256"] = "different"
    (tmp_path / "onnx-cpu.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="settings differ"):
        summarize(SimpleNamespace(bundle=tmp_path, device="cpu"))


def test_cuda_reference_rejects_changed_outputs(tmp_path):
    np.savez(tmp_path / "torch-cuda-outputs.npz", **outputs())
    (tmp_path / "bundle.json").write_text("{}")
    reference = {
        "status": "ok",
        "engine": "torch",
        "device": "cuda",
        "bundle_sha256": sha256(tmp_path / "bundle.json"),
        "input_sha256": "inputs",
        "output_sha256": sha256(tmp_path / "torch-cuda-outputs.npz"),
        "parity": {"passed": True},
    }
    (tmp_path / "torch-cuda.json").write_text(json.dumps(reference))
    metadata = {"files": {"inputs.npy": "inputs"}}
    assert _cuda_reference(tmp_path, metadata)[0]["logits"].shape == (2, 2)
    np.savez(
        tmp_path / "torch-cuda-outputs.npz",
        **{key: value + 0.1 for key, value in outputs().items()},
    )
    with pytest.raises(ValueError, match="reference is required"):
        _cuda_reference(tmp_path, metadata)


def test_small_fas_onnx_retains_unusual_head_and_attack_class(tmp_path):
    torch = pytest.importorskip("torch")
    pytest.importorskip("onnxscript")
    ort = pytest.importorskip("onnxruntime")
    from vericlue_ml.eval.onnx_networks import FasExport
    from vericlue_ml.face.fsvfm import TorchFasClassifier
    from vericlue_ml.face.fsvfm_network import FasNetwork

    torch.manual_seed(71)
    torch.set_num_threads(2)
    network = FasNetwork(width=8, depth=1, heads=2, hidden=4, image_size=16, patch_size=8).eval()
    adapter = FasExport(TorchFasClassifier(network, "cpu")).eval()
    images = torch.randn(1, 3, 16, 16)
    with torch.inference_mode():
        expected = adapter(images)
    previous = torch.backends.mha.get_fastpath_enabled()
    try:
        torch.backends.mha.set_fastpath_enabled(False)
        torch.onnx.export(
            adapter,
            (images,),
            tmp_path / "tiny.onnx",
            input_names=["images"],
            output_names=["logits", "probabilities"],
            dynamo=True,
            opset_version=18,
            optimize=False,
        )
    finally:
        torch.backends.mha.set_fastpath_enabled(previous)
    session = ort.InferenceSession(str(tmp_path / "tiny.onnx"), providers=["CPUExecutionProvider"])
    actual = session.run(None, {"images": images.numpy()})
    for original, exported in zip(expected, actual, strict=True):
        assert np.allclose(original.numpy(), exported, atol=1e-5, rtol=1e-4)
    assert ATTACK_INDICES == {"fsvfm": 0, "gend": 1}


def test_gend_export_keeps_pooling_normalization_and_head():
    torch = pytest.importorskip("torch")
    from vericlue_ml.eval.onnx_networks import GendExport
    from vericlue_ml.face.gend import GendClassifier

    class Vision(torch.nn.Module):
        def forward(self, pixel_values):
            return SimpleNamespace(pooler_output=pixel_values.mean(dim=(2, 3)))

    classifier = GendClassifier(
        Vision(),
        torch.tensor([[1, 2, 3], [-3, 1, 2]], dtype=torch.float32),
        torch.tensor([0.5, -0.5]),
        "cpu",
    )
    adapter = GendExport(classifier)
    inputs = torch.tensor([[[[1.0]], [[2.0]], [[3.0]]]])
    with torch.inference_mode():
        _, probabilities = adapter(inputs)
    assert np.allclose(classifier.p_fake(inputs.numpy()), probabilities[:, 1].numpy())
