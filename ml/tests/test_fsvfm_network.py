"""Small mathematical reference checks; torch is optional in regular CI."""

import numpy as np
import pytest

torch = pytest.importorskip("torch")
from vericlue_ml.face.fsvfm_network import FasNetwork, checkpoint_state  # noqa: E402


def test_standard_transformer_matches_explicit_attention_and_mlp():
    torch.manual_seed(123)
    model = FasNetwork(width=8, depth=1, heads=2, hidden=5, image_size=8, patch_size=4).eval()
    layer = model.layers[0]
    tokens = torch.randn(2, 5, 8)
    with torch.inference_mode():
        normalized = layer.norm1(tokens)
        q, k, v = torch.nn.functional.linear(
            normalized, layer.self_attn.in_proj_weight, layer.self_attn.in_proj_bias
        ).chunk(3, dim=-1)
        q, k, v = [x.reshape(2, 5, 2, 4).transpose(1, 2) for x in (q, k, v)]
        attention = ((q @ k.transpose(-2, -1)) / 2).softmax(-1) @ v
        expected = tokens + layer.self_attn.out_proj(attention.transpose(1, 2).reshape(2, 5, 8))
        expected = expected + layer.linear2(
            torch.nn.functional.gelu(layer.linear1(layer.norm2(expected)))
        )
        torch.testing.assert_close(layer(tokens), expected, atol=1e-6, rtol=1e-5)


def test_head_matches_numpy_reference_including_patch_pool_and_token_axis():
    torch.manual_seed(32)
    model = FasNetwork(width=8, depth=1, heads=2, hidden=5, image_size=8, patch_size=4).eval()
    tokens = torch.randn(2, 5, 8)

    def array(t):
        return t.detach().numpy()

    value = array(tokens).copy()
    pool = value[:, 1:].mean(1)
    pool = (pool - pool.mean(-1, keepdims=True)) / np.sqrt(pool.var(-1, keepdims=True) + 1e-6)
    value[:, 0] = pool * array(model.pool_norm.weight) + array(model.pool_norm.bias)
    features = np.maximum(
        value @ array(model.bottleneck.weight).T + array(model.bottleneck.bias), 0
    )
    features /= np.sqrt(
        np.maximum(np.linalg.norm(features, axis=1, keepdims=True), 1e-12)
    ) * np.sqrt(2)
    weight = array(model.classifier.weight)
    weight = weight / np.linalg.norm(weight, axis=0, keepdims=True)
    expected = features[:, 0] @ weight.T + array(model.classifier.bias)
    with torch.inference_mode():
        np.testing.assert_allclose(
            array(model.classify_tokens(tokens)), expected, atol=2e-6, rtol=2e-5
        )
    # All patch tokens affect the denominator, even with an unchanged pooled token.
    changed = tokens.clone()
    changed[:, 1] += 1
    changed[:, 2] -= 1
    assert not torch.allclose(model.classify_tokens(changed), model.classify_tokens(tokens))


def test_checkpoint_translation_consumes_every_key_and_validates_aliases():
    # Minimal depth-zero checkpoint isolates metadata/alias checks from encoder math.
    model = FasNetwork(width=8, depth=0, heads=2, hidden=5, image_size=8, patch_size=4)
    pairs = {
        "cls_token": "cls",
        "pos_embed": "position",
        "patch_embed.proj.weight": "patch.weight",
        "patch_embed.proj.bias": "patch.bias",
        "fc_norm.weight": "pool_norm.weight",
        "fc_norm.bias": "pool_norm.bias",
    }
    state = model.state_dict()
    source = {"backbone.vit." + old: state[new] for old, new in pairs.items()}
    for suffix in ("weight", "bias"):
        source["embedder.bottleneck_layer_fc." + suffix] = state["bottleneck." + suffix]
        source["embedder.bottleneck_layer.0." + suffix] = state["bottleneck." + suffix].clone()
        source["classifier.classifier_layer." + suffix] = state["classifier." + suffix]
    translated = checkpoint_state(source, depth=0)
    model.load_state_dict(translated, strict=True)
    with pytest.raises(ValueError, match="Unexpected"):
        checkpoint_state({**source, "unexpected": torch.zeros(1)}, depth=0)
    with pytest.raises(ValueError, match="Conflicting"):
        checkpoint_state({**source, "embedder.bottleneck_layer.0.bias": torch.ones(5)}, depth=0)
    with pytest.raises(KeyError):
        checkpoint_state({}, depth=0)


def test_classifier_reports_fake_class_zero_not_real_class_one():
    from vericlue_ml.face.fsvfm import TorchFasClassifier

    class FixedLogits(torch.nn.Module):
        def forward(self, x):
            return torch.tensor([[3.0, -2.0]])

    classifier = TorchFasClassifier(FixedLogits(), "cpu")
    scores = classifier.p_fake(np.zeros((3, 3, 224, 224), np.float32))
    assert len(scores) == 3 and all(p == pytest.approx(1 / (1 + np.exp(-5))) for p in scores)


def test_checkpoint_rejects_unsupported_pickle_without_loading_network(monkeypatch, tmp_path):
    from pathlib import Path

    from vericlue_ml.face import fsvfm

    path = tmp_path / "unsafe.pth"
    stats = tmp_path / "stats.txt"
    import json

    stats.write_text(json.dumps({"mean": fsvfm.MEAN, "std": fsvfm.STD}))
    torch.save({"state_dict": {}, "unexpected": Path("unused")}, path)
    monkeypatch.setattr(
        fsvfm,
        "_verified_weights",
        lambda root, model, name: (path if name == fsvfm.CHECKPOINT_FILE else stats, "test"),
    )
    with pytest.raises(fsvfm.PadError) as error:
        fsvfm.load_classifier(tmp_path, "cpu")
    assert error.value.code == "E_INTEGRITY"
