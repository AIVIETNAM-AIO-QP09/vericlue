"""VOICE-01: strict Fairseq-to-HF mapping and checksums using tiny CPU fixtures."""

import hashlib

import numpy as np
import pytest

from vericlue_ml.voice.antispoof import (
    IGNORED_PRETRAINING_PREFIXES,
    ModelLoadError,
    convert_state_dict,
    verify_file,
)


@pytest.mark.parametrize(
    "source,target",
    [
        ("encoder.layers.2.self_attn.q_proj.weight", "encoder.layers.2.attention.q_proj.weight"),
        ("encoder.layers.2.self_attn.k_proj.bias", "encoder.layers.2.attention.k_proj.bias"),
        ("encoder.layers.2.self_attn.v_proj.weight", "encoder.layers.2.attention.v_proj.weight"),
        ("encoder.layers.2.self_attn.out_proj.bias", "encoder.layers.2.attention.out_proj.bias"),
        ("encoder.layers.2.fc1.weight", "encoder.layers.2.feed_forward.intermediate_dense.weight"),
        ("encoder.layers.2.fc2.bias", "encoder.layers.2.feed_forward.output_dense.bias"),
        ("encoder.layers.2.self_attn_layer_norm.weight", "encoder.layers.2.layer_norm.weight"),
        ("encoder.layers.2.final_layer_norm.bias", "encoder.layers.2.final_layer_norm.bias"),
        ("encoder.layer_norm.weight", "encoder.layer_norm.weight"),
        ("layer_norm.bias", "feature_projection.layer_norm.bias"),
        ("post_extract_proj.weight", "feature_projection.projection.weight"),
        ("feature_extractor.conv_layers.1.0.weight", "feature_extractor.conv_layers.1.conv.weight"),
        ("feature_extractor.conv_layers.1.0.bias", "feature_extractor.conv_layers.1.conv.bias"),
        (
            "feature_extractor.conv_layers.1.2.1.weight",
            "feature_extractor.conv_layers.1.layer_norm.weight",
        ),
        (
            "feature_extractor.conv_layers.1.2.bias",
            "feature_extractor.conv_layers.1.layer_norm.bias",
        ),
        (
            "encoder.pos_conv.0.weight_g",
            "encoder.pos_conv_embed.conv.parametrizations.weight.original0",
        ),
        (
            "encoder.pos_conv.0.weight_v",
            "encoder.pos_conv_embed.conv.parametrizations.weight.original1",
        ),
        ("encoder.pos_conv.0.weight_g", "encoder.pos_conv_embed.conv.weight_g"),
        ("encoder.pos_conv.0.weight_v", "encoder.pos_conv_embed.conv.weight_v"),
        ("encoder.pos_conv.0.bias", "encoder.pos_conv_embed.conv.bias"),
        ("mask_emb", "masked_spec_embed"),
    ],
)
def test_backbone_key_mapping_preserves_all_values_and_shape(source, target):
    tensor = np.arange(6, dtype=np.float32).reshape(2, 3)
    source, target = "m_ssl.model." + source, "backbone." + target
    mapped, report = convert_state_dict({source: tensor}, {target: tensor.shape})
    assert set(mapped) == {target}
    np.testing.assert_array_equal(mapped[target], tensor)
    assert mapped[target].shape == tensor.shape
    assert report == {
        "missing_keys": [],
        "unexpected_keys": [],
        "ignored_keys": [],
        "mapped_keys": 1,
    }


def test_classifier_and_backbone_are_loaded_together_without_dropping_weights():
    state = {
        "m_ssl.model.encoder.layers.0.self_attn.q_proj.weight": np.full(
            (3, 3), 1.25, dtype=np.float32
        ),
        "proj_fc.weight": np.array([[1.0, 2.0, 3.0], [-1.0, -2.0, -3.0]], dtype=np.float32),
        "proj_fc.bias": np.array([0.5, -0.5], dtype=np.float32),
    }
    targets = {
        "backbone.encoder.layers.0.attention.q_proj.weight": (3, 3),
        "proj_fc.weight": (2, 3),
        "proj_fc.bias": (2,),
    }
    mapped, report = convert_state_dict(state, targets)
    assert set(mapped) == set(targets)
    np.testing.assert_array_equal(mapped["proj_fc.weight"], state["proj_fc.weight"])
    np.testing.assert_array_equal(mapped["proj_fc.bias"], state["proj_fc.bias"])
    assert report["mapped_keys"] == 3 and report["ignored_keys"] == []


def test_pretraining_ignore_allowlist_is_exact():
    assert set(IGNORED_PRETRAINING_PREFIXES) == {
        "m_ssl.model.quantizer.",
        "m_ssl.model.project_q.",
        "m_ssl.model.final_proj.",
    }


def test_only_documented_pretraining_heads_are_ignored_and_reported():
    extras = [
        "m_ssl.model.quantizer.vars",
        "m_ssl.model.project_q.weight",
        "m_ssl.model.final_proj.bias",
    ]
    state = {"proj_fc.weight": np.zeros((2, 3), dtype=np.float32)}
    state.update({key: np.ones((2,), dtype=np.float32) for key in extras})
    mapped, report = convert_state_dict(state, {"proj_fc.weight": (2, 3)})
    assert set(mapped) == {"proj_fc.weight"}
    assert set(report["ignored_keys"]) == set(extras)
    assert report["missing_keys"] == report["unexpected_keys"] == []
    assert report["mapped_keys"] == 1


def test_mask_embedding_can_be_ignored_only_when_target_architecture_omits_it():
    state = {"proj_fc.bias": np.zeros((2,)), "m_ssl.model.mask_emb": np.ones((3,))}
    mapped, report = convert_state_dict(state, {"proj_fc.bias": (2,)})
    assert set(mapped) == {"proj_fc.bias"}
    assert report["ignored_keys"] == ["m_ssl.model.mask_emb"]
    mapped, report = convert_state_dict(
        state, {"proj_fc.bias": (2,), "backbone.masked_spec_embed": (3,)}
    )
    np.testing.assert_array_equal(mapped["backbone.masked_spec_embed"], np.ones((3,)))
    assert report["ignored_keys"] == [] and report["mapped_keys"] == 2


@pytest.mark.parametrize(
    "missing", ["proj_fc.weight", "proj_fc.bias", "backbone.masked_spec_embed"]
)
def test_missing_required_target_key_is_an_error(missing):
    targets = {"proj_fc.weight": (2, 3), "proj_fc.bias": (2,), "backbone.masked_spec_embed": (3,)}
    source_for_target = {
        "proj_fc.weight": "proj_fc.weight",
        "proj_fc.bias": "proj_fc.bias",
        "backbone.masked_spec_embed": "m_ssl.model.mask_emb",
    }
    state = {
        source_for_target[key]: np.zeros(shape) for key, shape in targets.items() if key != missing
    }
    with pytest.raises(ModelLoadError):
        convert_state_dict(state, targets)


@pytest.mark.parametrize(
    "unknown",
    [
        "m_ssl.model.unknown.weight",
        "m_ssl.model.mask_emb.extra",
        "proj_fc.extra",
        "m_ssl.model.quantizer_extra.weight",
        "totally_unexpected.weight",
    ],
)
def test_unknown_weights_are_not_silently_ignored(unknown):
    with pytest.raises(ModelLoadError):
        convert_state_dict(
            {"proj_fc.bias": np.zeros((2,)), unknown: np.zeros((3,))}, {"proj_fc.bias": (2,)}
        )


@pytest.mark.parametrize("source_shape", [(3, 2), (2, 2), (6,), ()])
def test_shape_mismatch_never_reshapes_or_drops_checkpoint_weight(source_shape):
    with pytest.raises(ModelLoadError):
        convert_state_dict({"proj_fc.weight": np.zeros(source_shape)}, {"proj_fc.weight": (2, 3)})


def test_norm_aliases_cannot_overwrite_the_same_target_parameter():
    state = {
        "m_ssl.model.feature_extractor.conv_layers.0.2.weight": np.ones((3,)),
        "m_ssl.model.feature_extractor.conv_layers.0.2.1.weight": np.zeros((3,)),
    }
    with pytest.raises(ModelLoadError):
        convert_state_dict(
            state, {"backbone.feature_extractor.conv_layers.0.layer_norm.weight": (3,)}
        )


def test_mask_embedding_shape_is_checked_when_target_requires_it():
    with pytest.raises(ModelLoadError):
        convert_state_dict(
            {"m_ssl.model.mask_emb": np.ones((4,))}, {"backbone.masked_spec_embed": (3,)}
        )


def test_verify_file_accepts_exact_sha256_for_tiny_fixture(tmp_path):
    data = b"synthetic checksum fixture, not model weights"
    path = tmp_path / "tiny-fixture.bin"
    path.write_bytes(data)
    assert verify_file(path, hashlib.sha256(data).hexdigest()) is None


def test_verify_file_rejects_wrong_sha256(tmp_path):
    path = tmp_path / "tiny-fixture.bin"
    path.write_bytes(b"corrupted synthetic fixture")
    with pytest.raises(ModelLoadError):
        verify_file(path, hashlib.sha256(b"original synthetic fixture").hexdigest())


def test_verify_file_rejects_missing_file(tmp_path):
    with pytest.raises(ModelLoadError):
        verify_file(tmp_path / "absent.bin", "a" * 64)


def backend_fixture(tmp_path, monkeypatch):
    import yaml

    from vericlue_ml.voice.antispoof import TorchAntiDeepfakeBackend

    root = tmp_path / "synthetic-model-root"
    folder = root / "tiny-antideepfake"
    folder.mkdir(parents=True)
    files = {"config.json": b'{"hidden_size":3}', "model.safetensors": b"not real model weights"}
    configuration = {
        "antispoof": {
            "model_subdir": folder.name,
            "sha256": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
        }
    }
    config_path = tmp_path / "synthetic-models.yaml"
    config_path.write_text(yaml.safe_dump(configuration), encoding="utf-8")
    monkeypatch.setenv("ML_MODELS_CONFIG", str(config_path))
    return TorchAntiDeepfakeBackend(models_dir=root), folder, files


@pytest.mark.parametrize("filename", ["config.json", "model.safetensors"])
@pytest.mark.parametrize("failure", ["missing", "wrong_sha"])
def test_preload_rejects_local_files_before_importing_heavy_runtime(
    tmp_path, monkeypatch, filename, failure
):
    import builtins

    backend, folder, files = backend_fixture(tmp_path, monkeypatch)
    for name, data in files.items():
        (folder / name).write_bytes(data)
    if failure == "missing":
        (folder / filename).unlink()
    else:
        (folder / filename).write_bytes(b"corrupted tiny fixture")
    imports = []
    original_import = builtins.__import__

    def reject_heavy_import(name, *args, **kwargs):
        if name.split(".")[0] in {"torch", "transformers", "safetensors"}:
            imports.append(name)
            raise AssertionError("Invalid local files must fail before heavy runtime imports")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_heavy_import)
    for _attempt in range(2):
        with pytest.raises(ModelLoadError):
            backend.preload()
    assert imports == []
    assert backend.model is None


def test_preload_failure_is_sticky_and_does_not_retry_load(tmp_path, monkeypatch):
    backend, _folder, _files = backend_fixture(tmp_path, monkeypatch)
    calls = []

    def fail_load():
        calls.append("load")
        raise RuntimeError("synthetic dependency failure")

    monkeypatch.setattr(backend, "_load", fail_load)
    with pytest.raises(ModelLoadError):
        backend.preload()
    with pytest.raises(ModelLoadError):
        backend.preload()
    assert calls == ["load"]
    assert backend.model is None


def test_successful_preload_is_reused_without_reloading(tmp_path, monkeypatch):
    backend, _folder, _files = backend_fixture(tmp_path, monkeypatch)
    calls = []
    sentinel_model = object()

    def load_once():
        calls.append("load")
        backend.model = sentinel_model

    monkeypatch.setattr(backend, "_load", load_once)
    backend.preload()
    backend.preload()
    assert calls == ["load"]
    assert backend.model is sentinel_model


@pytest.mark.parametrize(
    "unapproved_key",
    [
        "m_ssl.model.quantizer",
        "m_ssl.model.quantizerx.weight",
        "m_ssl.model.project_qx.weight",
        "m_ssl.model.final_projx.weight",
    ],
)
def test_pretraining_prefix_allowlist_does_not_accept_lookalikes(unapproved_key):
    state = {"proj_fc.bias": np.zeros((2,)), unapproved_key: np.zeros((2,))}
    with pytest.raises(ModelLoadError):
        convert_state_dict(state, {"proj_fc.bias": (2,)})


@pytest.mark.parametrize(
    "source,target",
    [
        (
            "m_ssl.model.feature_extractorXconv_layersY1Z0Wweight",
            "backbone.feature_extractor.conv_layers.1.conv.weight",
        ),
        (
            "m_ssl.model.encoderXlayersY0Zself_attn.q_proj.weight",
            "backbone.encoder.layers.0.attention.q_proj.weight",
        ),
    ],
)
def test_mapping_requires_literal_dot_separators_in_checkpoint_names(source, target):
    with pytest.raises(ModelLoadError):
        convert_state_dict({source: np.zeros((2, 3))}, {target: (2, 3)})
