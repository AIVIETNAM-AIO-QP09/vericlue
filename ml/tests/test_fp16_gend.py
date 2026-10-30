"""Numerical-budget and dtype regression checks, no real weights or GPU."""

from __future__ import annotations

import numpy as np
import pytest

from vericlue_ml.eval.fp16_gend import POLICY, parity


def output():
    return {
        "logits": np.array([[1.0, 2.0], [3.0, -1.0]], dtype=np.float32),
        "probabilities": np.array([[0.25, 0.75], [0.9, 0.1]], dtype=np.float32),
    }


def test_small_probability_error_is_measured_with_a_fixed_budget():
    expected, actual = output(), output()
    actual["probabilities"][0] += [0.0001, -0.0001]
    result = parity(expected, actual)
    assert result["passed"] and result["policy"] == POLICY
    assert not result["biometric_accuracy_evaluated"]


def test_loose_logit_budget_does_not_hide_probability_drift():
    expected, actual = output(), output()
    actual["probabilities"][0] += [0.002, -0.002]
    assert not parity(expected, actual)["passed"]


@pytest.mark.parametrize("corruption", ["nan", "half_output", "flipped_label", "sample_count"])
def test_invalid_or_changed_outputs_are_not_accepted(corruption):
    expected, actual = output(), output()
    if corruption == "nan":
        actual["logits"][0, 0] = np.nan
    elif corruption == "half_output":
        actual["probabilities"] = actual["probabilities"].astype(np.float16)
    elif corruption == "sample_count":
        expected["probabilities"] = expected["probabilities"][:1]
        actual["probabilities"] = actual["probabilities"][:1]
    else:
        expected["logits"][0] = [1, 1.00001]
        actual["logits"][0] = [1.00001, 1]
        assert not parity(expected, actual)["passed"]
        return
    with pytest.raises(ValueError):
        parity(expected, actual)


def test_mixed_half_preserves_original_fp32_norm_weights_and_io():
    torch = pytest.importorskip("torch")
    from types import SimpleNamespace

    from vericlue_ml.eval.fp16_networks import Float32LayerNorm, GendMixedHalf

    class Vision(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.linear = torch.nn.Linear(3, 3)
            self.norm = torch.nn.LayerNorm(3)

        def forward(self, pixel_values):
            return SimpleNamespace(pooler_output=self.norm(self.linear(pixel_values.mean((2, 3)))))

    vision = Vision().eval()
    with torch.no_grad():
        vision.norm.weight.fill_(1.000123)
    original = vision.norm.weight.detach().clone()
    classifier = SimpleNamespace(_vision=vision, _weight=torch.ones(2, 3), _bias=torch.zeros(2))
    model = GendMixedHalf(classifier).eval()
    assert isinstance(model.vision.norm, Float32LayerNorm)
    assert torch.equal(model.vision.norm.weight, original)
    assert model.vision.linear.weight.dtype == torch.float16
    assert model.vision.norm.weight.dtype == model.head_weight.dtype == torch.float32
    with torch.inference_mode():
        logits, probs = model(torch.randn(1, 3, 4, 4, dtype=torch.float32))
    assert logits.dtype == probs.dtype == torch.float32
    assert torch.isfinite(logits).all() and probs.sum().item() == pytest.approx(1)


def test_tiny_mixed_model_exports_fp32_io_and_fp16_initializers(tmp_path):
    torch = pytest.importorskip("torch")
    onnx = pytest.importorskip("onnx")
    pytest.importorskip("onnxscript")
    from types import SimpleNamespace

    from vericlue_ml.eval.fp16_networks import GendMixedHalf

    class Vision(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.linear = torch.nn.Linear(3, 3)
            self.norm = torch.nn.LayerNorm(3)

        def forward(self, pixel_values):
            return SimpleNamespace(pooler_output=self.norm(self.linear(pixel_values.mean((2, 3)))))

    model = GendMixedHalf(
        SimpleNamespace(_vision=Vision(), _weight=torch.ones(2, 3), _bias=torch.zeros(2))
    ).eval()
    with torch.inference_mode():
        torch.onnx.export(
            model,
            (torch.randn(1, 3, 4, 4),),
            str(tmp_path / "tiny.onnx"),
            dynamo=True,
            opset_version=18,
            optimize=False,
            input_names=["images"],
            output_names=["logits", "probabilities"],
        )
    graph = onnx.load(str(tmp_path / "tiny.onnx"))
    onnx.checker.check_model(graph)
    assert graph.graph.input[0].type.tensor_type.elem_type == onnx.TensorProto.FLOAT
    assert all(
        value.type.tensor_type.elem_type == onnx.TensorProto.FLOAT for value in graph.graph.output
    )
    assert onnx.TensorProto.FLOAT16 in {value.data_type for value in graph.graph.initializer}
    assert onnx.TensorProto.FLOAT in {value.data_type for value in graph.graph.initializer}


@pytest.mark.parametrize("preserve_residuals", [False, True])
def test_preserved_embedding_is_not_rounded_and_enters_half_encoder(preserve_residuals):
    torch = pytest.importorskip("torch")
    from types import SimpleNamespace

    from vericlue_ml.eval.fp16_networks import GendMixedHalf

    class Vision(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.vision_model = torch.nn.Module()
            self.vision_model.embeddings = torch.nn.Linear(3, 3)
            self.vision_model.pre_layrnorm = torch.nn.LayerNorm(3)
            self.vision_model.encoder = torch.nn.Linear(3, 3)

        def forward(self, pixel_values):
            core = self.vision_model
            value = core.embeddings(pixel_values.mean((2, 3)))
            return SimpleNamespace(pooler_output=core.encoder(core.pre_layrnorm(value)))

    vision = Vision()
    original = vision.vision_model.embeddings.weight.detach().clone()
    model = GendMixedHalf(
        SimpleNamespace(_vision=vision, _weight=torch.ones(2, 3), _bias=torch.zeros(2)),
        preserve_embeddings=True,
        preserve_residuals=preserve_residuals,
    ).eval()
    core = model.vision.vision_model
    assert torch.equal(core.embeddings.weight, original)
    assert core.embeddings.weight.dtype == torch.float32
    assert core.encoder.weight.dtype == torch.float16
    assert core.pre_layrnorm.half_output is not preserve_residuals
    with torch.inference_mode():
        logits, probabilities = model(torch.randn(1, 3, 4, 4))
    assert logits.dtype == probabilities.dtype == torch.float32
    assert torch.isfinite(logits).all()


@pytest.mark.parametrize("corruption", ["budget", "missing_hash", "changed_input", "changed_file"])
def test_bundle_rejects_changed_budget_or_integrity(tmp_path, corruption):
    import json

    from vericlue_ml.eval.fp16_gend import PRECISIONS, load_bundle
    from vericlue_ml.eval.onnx_metrics import sha256

    np.save(tmp_path / "inputs.npy", np.zeros((1, 3, 224, 224), np.float32))
    np.savez(tmp_path / "fp32-reference.npz", **output())
    (tmp_path / "model.onnx").write_bytes(b"placeholder, no runtime load")
    hashes = {
        name: sha256(tmp_path / name) for name in ["inputs.npy", "fp32-reference.npz", "model.onnx"]
    }
    metadata = {
        "format": 1,
        "model": "gend",
        "variant": "encoder",
        "precision": PRECISIONS["encoder"],
        "policy": POLICY.copy(),
        "samples": 1,
        "files": hashes,
        "source_input_sha256": hashes["inputs.npy"],
    }
    if corruption == "budget":
        metadata["policy"]["probability_atol"] = 1
    elif corruption == "missing_hash":
        del metadata["files"]["model.onnx"]
    elif corruption == "changed_input":
        metadata["source_input_sha256"] = "wrong"
    else:
        (tmp_path / "model.onnx").write_bytes(b"changed artifact")
    (tmp_path / "fp16-bundle.json").write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError):
        load_bundle(tmp_path)


@pytest.mark.parametrize("shape", [(2, 4), (1, 3, 4)])
@pytest.mark.parametrize("bias", [False, True])
def test_half_gemm_keeps_torch_linear_rounding(shape, bias):
    torch = pytest.importorskip("torch")
    from vericlue_ml.eval.fp16_networks import HalfLinearFloatOutput

    original = torch.nn.Linear(4, 3, bias=bias).half().eval()
    model = HalfLinearFloatOutput(original)
    values = torch.randn(shape, dtype=torch.float32)
    with torch.inference_mode():
        expected = torch.nn.functional.linear(values.half(), original.weight, original.bias).float()
        assert torch.equal(model(values), expected)


@pytest.mark.parametrize("tamper", [None, "latency", "reference", "parity"])
def test_report_checks_benchmark_evidence_before_aggregation(tmp_path, monkeypatch, tamper):
    import json

    from vericlue_ml.eval import fp16_report
    from vericlue_ml.eval.onnx_metrics import latency_summary, sha256

    (tmp_path / "fp16-bundle.json").write_text("{}", encoding="utf-8")
    metadata = {"source_input_sha256": "input", "source_reference_output_sha256": "reference"}
    monkeypatch.setattr(fp16_report, "load_bundle", lambda _: (metadata, None, None))
    report = {
        "engine": "torch16",
        "status": "ok",
        "parity": {"passed": True},
        "fp16_bundle_sha256": sha256(tmp_path / "fp16-bundle.json"),
        "input_sha256": "input",
        "reference_output_sha256": "reference",
        "latency_trials_ms": [1.0, 2.0, 3.0],
        "latency": latency_summary([1.0, 2.0, 3.0]),
    }
    if tamper == "latency":
        report["latency"]["p50_ms"] = 0
    elif tamper == "reference":
        report["reference_output_sha256"] = "other"
    elif tamper == "parity":
        report["parity"]["passed"] = False
    (tmp_path / "torch16.json").write_text(json.dumps(report), encoding="utf-8")
    if tamper is None:
        assert fp16_report.collect(tmp_path)["engines"]["torch16"] == report
    else:
        with pytest.raises(ValueError):
            fp16_report.collect(tmp_path)
