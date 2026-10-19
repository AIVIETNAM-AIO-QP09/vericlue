"""FACE-04: hàm thuần cho tinh chỉnh GenD (chặn test, tham số được dạy, delta, chọn checkpoint)."""

from __future__ import annotations

import numpy as np
import pytest

from vericlue_ml.finetune import gend_train as g


def test_assert_no_test_blocks_test_rows_and_paths():
    g.assert_no_test([{"split": "train", "path": "clips/c23/train/real/a.mp4"}])
    with pytest.raises(g.TestSplitAccessError):
        g.assert_no_test([{"split": "test", "path": "x.mp4"}])
    with pytest.raises(g.TestSplitAccessError):
        g.assert_no_test([{"split": "train", "path": "clips/c23/test/fake/a.mp4"}])
    with pytest.raises(g.TestSplitAccessError):
        g.assert_no_test([{"split": "calib", "path": "clips\\c23\\test\\a.mp4"}])


def test_rows_for_never_returns_test():
    rows = [{"split": s, "path": f"{s}/x"} for s in ("train", "calib", "test")]
    assert [r["split"] for r in g.rows_for(rows, ("train", "calib"))] == ["train", "calib"]
    with pytest.raises(g.TestSplitAccessError):
        g.rows_for(rows, ("calib", "test"))


def test_test_function_locked_by_default():
    with pytest.raises(g.TestSplitAccessError):
        g.check_test_unlocked(False, g.TEST_CONFIRMATION)
    with pytest.raises(g.TestSplitAccessError):
        g.check_test_unlocked(True, "yes")
    g.check_test_unlocked(True, g.TEST_CONFIRMATION)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("vision_model.pre_layrnorm.weight", True),
        ("vision_model.encoder.layers.3.layer_norm1.bias", True),
        ("vision_model.encoder.layers.23.layer_norm2.weight", True),
        ("vision_model.post_layernorm.weight", True),
        ("vision_model.encoder.layers.3.self_attn.q_proj.weight", False),
        ("vision_model.embeddings.patch_embedding.weight", False),
    ],
)
def test_is_trainable(name, expected):
    assert g.is_trainable(name) is expected


def _base():
    return {
        "feature_extractor.vision_model.pre_layrnorm.weight": np.ones(4),
        "feature_extractor.vision_model.encoder.layers.0.layer_norm1.weight": np.ones(4),
        "feature_extractor.vision_model.encoder.layers.0.mlp.fc1.weight": np.ones((4, 4)),
        g.HEAD_WEIGHT_KEY: np.zeros((2, 4)),
        g.HEAD_BIAS_KEY: np.zeros(2),
    }


def test_delta_and_merge_roundtrip():
    vision = {
        "vision_model.pre_layrnorm.weight": np.full(4, 2.0),
        "vision_model.encoder.layers.0.layer_norm1.weight": np.full(4, 3.0),
        "vision_model.encoder.layers.0.mlp.fc1.weight": np.full((4, 4), 9.0),
    }
    delta = g.delta_state(vision, np.ones((2, 4)), np.ones(2))
    assert "feature_extractor.vision_model.encoder.layers.0.mlp.fc1.weight" not in delta
    merged = g.merge_delta(_base(), delta)
    assert merged["feature_extractor.vision_model.pre_layrnorm.weight"][0] == 2.0
    assert merged["feature_extractor.vision_model.encoder.layers.0.mlp.fc1.weight"][0, 0] == 1.0
    assert merged[g.HEAD_WEIGHT_KEY].sum() == 8


def test_merge_rejects_non_layernorm_and_shape_mismatch():
    with pytest.raises(ValueError, match="không được phép"):
        g.merge_delta(
            _base(),
            {"feature_extractor.vision_model.encoder.layers.0.mlp.fc1.weight": np.ones((4, 4))},
        )
    with pytest.raises(ValueError, match="Kích thước"):
        g.merge_delta(_base(), {g.HEAD_BIAS_KEY: np.ones(3)})


def test_select_checkpoint_uses_calib_and_false_block_guard():
    history = [
        {"epoch": 0, "calib_auc": 0.70, "calib_eer": 0.35, "fasvn_fbr": 0.05},
        {"epoch": 1, "calib_auc": 0.90, "calib_eer": 0.15, "fasvn_fbr": 0.30},  # chặn nhầm tăng
        {"epoch": 2, "calib_auc": 0.85, "calib_eer": 0.20, "fasvn_fbr": 0.08},
        {"epoch": 3, "calib_auc": 0.85, "calib_eer": 0.18, "fasvn_fbr": 0.07},
    ]
    assert g.select_checkpoint(history)["epoch"] == 3
    worse = [history[0], {"epoch": 1, "calib_auc": 0.6, "calib_eer": 0.4, "fasvn_fbr": 0.05}]
    assert g.select_checkpoint(worse)["epoch"] == 0  # giữ GenD gốc nếu không tốt hơn


def test_threshold_and_false_block_rate():
    labels = [0, 0, 0, 1, 1, 1]
    scores = [0.1, 0.2, 0.3, 0.7, 0.8, 0.9]
    thr = g.threshold_at_eer(labels, scores)
    assert thr is not None and 0.3 < thr <= 0.7
    assert g.false_block_rate([0.1, 0.9], thr) == 0.5
    assert g.false_block_rate([], thr) is None


def test_augment_crop_keeps_bgr_uint8():
    pytest.importorskip("cv2")
    rng = np.random.default_rng(0)
    crop = np.random.default_rng(1).integers(0, 255, (180, 180, 3), dtype=np.uint8)
    cfg = g.AugConfig(p_flip=1, p_downscale=1, p_blur=1, p_jpeg=1)
    out = g.augment_crop(crop, rng, cfg)
    assert out.dtype == np.uint8 and out.ndim == 3 and out.shape[2] == 3
    assert max(out.shape[:2]) <= 180


def test_pad_border_size():
    pytest.importorskip("cv2")
    out = g.pad_border(np.zeros((224, 224, 3), dtype=np.uint8), ratio=0.5)
    assert out.shape == (448, 448, 3) and out[0, 0, 0] == 128


def test_clip_score_matches_gend_aggregation():
    from vericlue_ml.face.gend import video_scores

    values = [0.1, 0.2, 0.9, 0.95]
    mean, top = video_scores(values)
    assert g.clip_score(values) == max(mean, top)


def test_crf_variant_cmd():
    cmd = g.crf_variant_cmd("ffmpeg", "a.mp4", "b.mp4", crf=35, side=200)
    assert cmd[cmd.index("-crf") + 1] == "35" and "-an" in cmd and "scale=200:200" in " ".join(cmd)
