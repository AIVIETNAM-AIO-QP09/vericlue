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
