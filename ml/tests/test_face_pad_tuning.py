"""FACE-04 — hàm thuần của notebook tinh chỉnh PAD (không cần GPU hay trọng số thật)."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.face import pad_tuning as T
from vericlue_ml.face.pad import FaceBox, MiniFasNetClassifier

cv2 = pytest.importorskip("cv2")


def _image(seed: int, size: int = 64) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = cv2.resize(rng.integers(0, 255, (8, 8, 3), dtype=np.uint8), (size, size))
    return base


# ── kiểm kê ──────────────────────────────────────────────────────────────────────────────
def test_sniff_format_ignores_extension():
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    assert T.sniff_format(png) == "png"
    assert T.sniff_format(b"\xff\xd8\xff\xe0" + b"\x00" * 12) == "jpeg"
    assert T.sniff_format(b"GIF89a" + b"\x00" * 10) == "gif"
    assert T.extension_mismatch("a/b/photo.jpg", "png")
    assert not T.extension_mismatch("a/b/photo.JPEG", "jpeg")


# ── trùng lặp ────────────────────────────────────────────────────────────────────────────
def test_exact_duplicates_drop_conflicting_labels_entirely():
    shas = ["x", "x", "y", "y", "y", "z"]
    labels = ["live", "not_live", "live", "live", "live", "live"]
    drops = T.exact_duplicates(shas, labels)
    assert drops == {0: "sha_conflict", 1: "sha_conflict", 3: "sha_dup", 4: "sha_dup"}


def test_dhash_and_hamming_pairs():
    a = _image(1)
    b = a.copy()
    b[0, 0] = 255 - b[0, 0]  # thay đổi rất nhỏ
    c = _image(2)
    hashes = [T.dhash64(a), T.dhash64(b), T.dhash64(c)]
    assert hashes[0] == hashes[1]
    pairs = T.hamming_pairs(hashes, 4)
    assert (0, 1, 0) in pairs
    assert all(i < j for i, j, _ in pairs)
    assert T.hamming_pairs([0b1011, 0b0000], 3) == [(0, 1, 3)]
    assert T.hamming_pairs([0b1011, 0b0000], 2) == []


def test_near_duplicates_only_drop_same_label():
    hashes = [0, 1, 3, (1 << 40) - 1]
    labels = ["live", "live", "not_live", "live"]
    drops = T.near_duplicate_drops(hashes, labels, range(4), max_dist=4)
    # 0 và 1 cùng nhãn → bỏ 1; 2 khác nhãn (cặp gốc/chụp lại) → giữ.
    assert drops == {1: "dhash_dup"}


def test_link_groups_transitive_and_stable():
    keys = ["a", "b", "c", "d", "e"]
    g1 = T.link_groups(keys, [(0, 1), (1, 2)])
    assert g1[0] == g1[1] == g1[2] != g1[3] != g1[4]
    assert T.link_groups(keys, [(1, 2), (0, 1)]) == g1


def test_embedding_pairs_skip_missing_faces():
    emb = np.array([[1, 0], [0.9, 0.1], [0, 1], [np.nan, np.nan]], dtype=np.float32)
    assert T.embedding_pairs(emb, 0.9) == [(0, 1)]


# ── chia theo nhóm ───────────────────────────────────────────────────────────────────────
def _toy_groups(n_groups: int = 200):
    rng = np.random.default_rng(0)
    groups, labels = [], []
    for g in range(n_groups):
        for _ in range(int(rng.integers(1, 6))):
            groups.append(f"g{g}")
            labels.append("live" if rng.random() < 0.65 else "not_live")
    return groups, labels


def test_assign_splits_keeps_groups_whole_and_balanced():
    groups, labels = _toy_groups()
    split_of = T.assign_splits(groups, labels, seed=7)
    splits = [split_of[g] for g in groups]
    T.check_split_integrity(groups, splits)
    for s, frac in T.DEFAULT_FRACTIONS.items():
        share = splits.count(s) / len(splits)
        assert abs(share - frac) < 0.03, (s, share)
    assert T.assign_splits(groups, labels, seed=7) == split_of
    assert set(split_of.values()) == set(T.SPLITS)


def test_check_split_integrity_rejects_group_in_two_splits():
    with pytest.raises(AssertionError):
        T.check_split_integrity(["g1", "g1"], ["train", "test"])
    with pytest.raises(ValueError):
        T.check_split_integrity(["g1"], ["val"])


def test_assert_not_test_blocks_test_split():
    T.assert_not_test(["train", "calib_fit"])
    with pytest.raises(AssertionError, match="test"):
        T.assert_not_test(["train", "test"], "unit")
    rows = [{"split": "train"}, {"split": "test"}]
    assert T.rows_of_split(rows, "train") == [{"split": "train"}]
    with pytest.raises(AssertionError):
        T.rows_of_split(rows, "test")


# ── mặt và cắt ───────────────────────────────────────────────────────────────────────────
def test_largest_face_follows_pad_rules():
    big = FaceBox(0, 0, 100, 100, 0.9)
    small = FaceBox(0, 0, 40, 40, 0.9)
    near = FaceBox(0, 0, 90, 90, 0.9)
    assert T.largest_face([]) == (None, "no_face")
    assert T.largest_face([small, big]) == (big, "ok")
    assert T.largest_face([big, near])[1] == "multi_face"
    assert T.largest_face([FaceBox(0, 0, 1, 1, 0.9)])[1] == "tiny_face"


def test_detect_face_pads_border_and_maps_back():
    class Finder:
        calls = 0

        def find(self, image):
            self.calls += 1
            if self.calls == 1:
                return []
            h, w = image.shape[:2]  # ảnh đã đệm: mặt nằm ở giữa, tràn ra ngoài ảnh gốc
            marks = tuple((w / 2.0, h / 2.0) for _ in range(5))
            return [FaceBox(w * 0.2, h * 0.2, w * 0.8, h * 0.8, 0.8, marks)]

    image = np.zeros((100, 60, 3), np.uint8)
    box, status, padded, n = T.detect_face(Finder(), image, 0.33)
    assert (status, padded, n) == ("ok", True, 1)
    assert 0 <= box.x1 < box.x2 <= 59 and 0 <= box.y1 < box.y2 <= 99
    assert box.landmarks[0] == pytest.approx((30.0, 50.0), abs=1)


def test_pad_crop_is_exactly_pad_py_crop():
    image = _image(3, 200)
    box = FaceBox(50, 60, 120, 150, 0.9)
    session = SimpleNamespace(
        get_inputs=lambda: [SimpleNamespace(name="input", shape=["b", 3, 80, 80])],
        get_outputs=lambda: [SimpleNamespace(name="output")],
    )
    expected = MiniFasNetClassifier(session)._crop(image, box)
    np.testing.assert_array_equal(T.pad_crop(image, box, 80), expected)
    assert T.pad_crop(image, box, 224).shape == (224, 224, 3)


def test_arcface_align_identity_template():
    template = [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ]
    image = _image(4, 112)
    np.testing.assert_allclose(T.arcface_align(image, template), image, atol=2)


# ── khử lộ đề ────────────────────────────────────────────────────────────────────────────
def test_jpeg_roundtrip_strips_exif_and_meta_features():
    crop, data = T.jpeg_roundtrip(_image(5, 80), 90)
    assert crop.shape == (80, 80, 3)
    feats = T.meta_features(data)
    assert feats["is_jpeg"] == 1 and feats["has_exif"] == 0
    assert (feats["width"], feats["height"]) == (80, 80)
    assert feats["qtable_sum"] > 0
    exif = b"\xff\xd8" + b"\xff\xe1\x00\x10Exif\x00\x00" + b"\x00" * 8 + data[2:]
    assert T.meta_features(exif)["has_exif"] == 1


def test_univariate_auc():
    assert T.univariate_auc([1, 2, 3, 4], [0, 0, 1, 1]) == 1.0
    assert T.univariate_auc([4, 3, 2, 1], [0, 0, 1, 1]) == 1.0  # đảo chiều vẫn là lộ đề
    assert T.univariate_auc([1, 1, 1, 1], [0, 1, 0, 1]) == 0.5


def test_leak_auc_flags_metadata_shortcut_only():
    pytest.importorskip("sklearn")
    rng = np.random.default_rng(0)
    n = 400
    y = (rng.random(n) < 0.4).astype(int)
    groups = [f"g{i // 2}" for i in range(n)]
    clean = [{"width": 80.0, "has_exif": 0.0, "file_bytes": float(rng.normal(3000, 50))} for _ in y]
    leaky = [{"width": 2448.0 if t else 900.0, "has_exif": float(t)} for t in y]
    assert T.leak_auc(clean, y, groups)["model_auc"] < T.LEAK_AUC_MAX
    assert T.leak_auc(leaky, y, groups)["model_auc"] > 0.95


# ── chỉ số ───────────────────────────────────────────────────────────────────────────────
def test_threshold_at_bpcer_and_pad_metrics():
    labels = [0] * 100 + [1] * 50
    scores = list(np.linspace(0.0, 0.5, 100)) + list(np.linspace(0.3, 1.0, 50))
    t = T.threshold_at_bpcer(labels, scores, 0.01)
    live = np.array(scores[:100])
    assert np.mean(live >= t) <= 0.01
    m = T.pad_metrics(labels, scores, [f"g{i % 30}" for i in range(150)], 0.01, n_boot=20)
    assert m["bpcer"] <= 0.01 and 0 <= m["apcer"] <= 1
    assert m["n_live"] == 100 and m["n_attack"] == 50 and m["n_groups"] == 30
    assert m["apcer_ci95"][0] <= m["apcer"] <= m["apcer_ci95"][1] + 1e-9
    better = T.selection_key({"apcer": 0.1, "eer": 0.2, "auc": 0.9})
    assert better < T.selection_key({"apcer": 0.2, "eer": 0.1, "auc": 0.99})


def test_phone_camera_augment_shape_and_determinism():
    img = _image(6, 80)
    a = T.phone_camera_augment(img, np.random.default_rng((1, 2, 3)))
    b = T.phone_camera_augment(img, np.random.default_rng((1, 2, 3)))
    assert a.shape == img.shape and a.dtype == np.uint8
    np.testing.assert_array_equal(a, b)


def test_aux_label_from_path():
    assert T.aux_label_from_path("axon_display_replay", "Sample/Real/1.jpg") == (
        "live",
        "bona_fide",
    )
    assert (
        T.aux_label_from_path("axon_display_replay", "Sample/Screen/2.mp4")[1] == "display_replay"
    )
    assert T.aux_label_from_path("axon_cutprint", "104.MOV") == ("not_live", "cutout_print")
    assert T.aux_label_from_path("axon_print", "print_1.mp4") == ("not_live", "print")
    assert T.aux_label_from_path("axon_3dpaper", "a3d.mp4") == ("not_live", "paper_mask_3d")
    assert T.aux_label_from_path("axon_replay_mobile", "x/Pixel7/1.mp4")[1] == "mobile_replay"
    assert T.aux_label_from_path("axon_selfies", "Selfies/Selfie_1.jpg")[0] == "live"
    assert T.aux_label_from_path("unidata_asian", "files/1/video.mp4")[0] == "live"
    assert T.aux_label_from_path("something", "x/3dfile.jpg") is None


# ── ONNX ↔ torch ─────────────────────────────────────────────────────────────────────────
def _toy_ir() -> dict:
    rng = np.random.default_rng(0)
    return {
        "inputs": ["x"],
        "outputs": ["out"],
        "initializers": {
            "w": rng.normal(size=(4, 3, 3, 3)).astype(np.float32),
            "b": rng.normal(size=(4,)).astype(np.float32),
            "slope": np.full((4, 1, 1), 0.25, np.float32),
            "fc": rng.normal(size=(4 * 4 * 4, 3)).astype(np.float32),
        },
        "nodes": [
            {
                "op": "Conv",
                "inputs": ["x", "w", "b"],
                "outputs": ["c"],
                "attrs": {"pads": [1, 1, 1, 1], "strides": [2, 2], "group": 1},
            },
            {"op": "PRelu", "inputs": ["c", "slope"], "outputs": ["p"], "attrs": {}},
            {"op": "Flatten", "inputs": ["p"], "outputs": ["f"], "attrs": {"axis": 1}},
            {"op": "MatMul", "inputs": ["f", "fc"], "outputs": ["out"], "attrs": {}},
        ],
    }


def test_build_torch_graph_matches_reference_and_trains():
    torch = pytest.importorskip("torch")
    ir = _toy_ir()
    model = T.build_torch_graph(ir)
    x = torch.randn(2, 3, 8, 8)
    ref_conv = torch.nn.functional.conv2d(
        x,
        torch.from_numpy(ir["initializers"]["w"]),
        torch.from_numpy(ir["initializers"]["b"]),
        2,
        1,
    )
    ref = torch.where(ref_conv >= 0, ref_conv, 0.25 * ref_conv).flatten(1)
    ref = ref @ torch.from_numpy(ir["initializers"]["fc"])
    torch.testing.assert_close(model(x), ref)
    loss = T.binary_live_loss(model(x), torch.tensor([1, 0]))
    loss.backward()
    assert all(p.grad is not None for p in model.parameters())
    arrays = model.initializer_arrays()
    assert set(arrays) == set(ir["initializers"])


def test_build_torch_graph_rejects_unknown_ops():
    pytest.importorskip("torch")
    ir = _toy_ir()
    ir["nodes"].append({"op": "Resize", "inputs": ["out"], "outputs": ["r"], "attrs": {}})
    with pytest.raises(NotImplementedError):
        T.build_torch_graph(ir)


def test_binary_live_loss_prefers_correct_class():
    torch = pytest.importorskip("torch")
    good = torch.tensor([[-5.0, 5.0, -5.0], [5.0, -5.0, 0.0]])
    bad = torch.tensor([[5.0, -5.0, 0.0], [-5.0, 5.0, -5.0]])
    y = torch.tensor([1, 0])
    assert T.binary_live_loss(good, y) < T.binary_live_loss(bad, y)


# ── gộp MiniFASNet + DINOv2 (ADR-0015) ───────────────────────────────────────────────────
def test_combo_max_matches_router_max_fusion():
    np.testing.assert_allclose(T.combo_max([0.1, 0.9, 0.4], [0.3, 0.2, 0.4]), [0.3, 0.9, 0.4])
    with pytest.raises(ValueError):
        T.combo_max()


def test_recommend_combo_or_best_single():
    singles = {
        "mini": {"apcer": 0.30, "auc": 0.95},
        "dino": {"apcer": 0.20, "auc": 0.93},
    }
    win = T.recommend(singles, {"apcer": 0.10, "auc": 0.96})
    assert win["choice"] == "combo" and win["best_single"] == "dino"
    tie = T.recommend(singles, {"apcer": 0.20, "auc": 0.97})
    assert tie["choice"] == "combo" and "AUC" in tie["reason_vi"]
    lose = T.recommend(singles, {"apcer": 0.25, "auc": 0.99})
    assert lose["choice"] == "dino" and "KHÔNG" in lose["reason_vi"]
    assert T.recommend({"mini": singles["mini"]}, None)["choice"] == "mini"


def test_leak_auc_constant_features_random_labels_is_half():
    pytest.importorskip("sklearn")
    rng = np.random.default_rng(1)
    y = (rng.random(300) < 0.3).astype(int)
    groups = [f"g{i // 3}" for i in range(300)]
    const = [{"width": 80.0, "height": 80.0, "has_exif": 0.0} for _ in y]
    out = T.leak_auc(const, y, groups)
    assert out["model_auc"] == 0.5 and out["used_features"] == []
    noise = [{"width": 80.0, "noise": float(v)} for v in rng.normal(size=300)]
    assert abs(T.leak_auc(noise, y, groups)["model_auc"] - 0.5) < 0.12


# ── hồi quy: nối chuỗi nhóm người (lỗi prep_pad trên FAS-VN đầy đủ, 20/10) ───────────────
def _chain_embeddings(n_people: int = 40, per: int = 3, step_cos: float = 0.43, seed: int = 0):
    rng = np.random.default_rng(seed)
    d = 256
    centers = [rng.normal(size=d)]
    centers[0] /= np.linalg.norm(centers[0])
    for _ in range(n_people - 1):
        u = rng.normal(size=d)
        u -= (u @ centers[-1]) * centers[-1]
        u /= np.linalg.norm(u)
        centers.append(step_cos * centers[-1] + np.sqrt(1 - step_cos**2) * u)
    emb, truth = [], []
    for k, c in enumerate(centers):
        for _ in range(per):
            v = c + 0.005 * rng.normal(size=d)
            emb.append(v / np.linalg.norm(v))
            truth.append(k)
    return np.array(emb, dtype=np.float32), truth


def test_loose_arcface_threshold_chains_people_validated_threshold_does_not():
    emb, truth = _chain_embeddings()
    keys = [f"img{i}" for i in range(len(emb))]
    loose = T.group_size_stats(T.link_groups(keys, T.embedding_pairs(emb, 0.40)))
    assert loose["n_groups"] == 1 and loose["max_share"] == 1.0  # nối chuỗi: tất cả thành 1 nhóm
    groups = T.link_groups(keys, T.embedding_pairs(emb, 0.45))
    tight = T.group_size_stats(groups)
    assert tight["n_groups"] == 40 and tight["max"] == 3
    # ảnh cùng người (cặp gốc/chụp lại) vẫn chung nhóm
    for k in range(40):
        assert len({groups[i] for i, t in enumerate(truth) if t == k}) == 1


def test_group_size_stats_empty_and_basic():
    assert T.group_size_stats([])["n_groups"] == 0
    s = T.group_size_stats(["a", "a", "b", "c", "c", "c"])
    assert (s["n_groups"], s["max"]) == (3, 3) and s["max_share"] == 0.5
