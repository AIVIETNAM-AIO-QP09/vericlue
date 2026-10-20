"""FACE-04 — hàm thuần cho notebook tinh chỉnh PAD (`ml/notebooks/finetune_pad_{minifasnet,dinov2}.ipynb`).

File này được `scripts/build_pad_notebook.py` NHÚNG NGUYÊN VĂN vào notebook (bỏ các dòng
`from vericlue_ml…`, vì notebook nhúng luôn `pad.py`/`eval/metrics.py`). Vì vậy:
- chỉ phụ thuộc numpy/cv2 ở mức module; torch, sklearn, onnx nhập bên trong hàm;
- không đọc file cấu hình repo, không gọi mạng.

Nội dung: kiểm kê định dạng, lọc trùng (SHA-256, dHash), gom người (union-find), chia lại theo
nhóm, chặn đọc split `test`, khử lộ đề (cắt mặt y hệt `pad.py` → JPEG lại, không EXIF) và kiểm
lộ đề bằng mô hình chỉ dùng siêu dữ liệu, chỉ số PAD (APCER tại BPCER ≤ 1 %), tăng cường kiểu
camera trước điện thoại rẻ, và chạy đồ thị ONNX của MiniFASNet bằng torch để dạy lại rồi ghi
trọng số ngược vào đúng đồ thị gốc (đầu vào/ra giữ nguyên).
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from types import SimpleNamespace
from typing import Any

import numpy as np

from vericlue_ml.eval.metrics import auc, bpcer, eer
from vericlue_ml.face.pad import (
    PAD_CROP_SCALE,
    SECOND_FACE_AREA_RATIO,
    FaceBox,
    MiniFasNetClassifier,
)

SPLITS = ("train", "calib_fit", "calib_ltt", "test")
FORBIDDEN_SPLIT = "test"
DEFAULT_FRACTIONS = {"train": 0.60, "calib_fit": 0.15, "calib_ltt": 0.10, "test": 0.15}
LABELS = ("live", "not_live")
LEAK_AUC_MAX = 0.6


# ── kiểm kê ──────────────────────────────────────────────────────────────────────────────
def sniff_format(head: bytes) -> str:
    """Định dạng thật theo byte đầu file (không tin đuôi file)."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:2] == b"BM":
        return "bmp"
    return "unknown"


def extension_mismatch(path: str, fmt: str) -> bool:
    """True nếu đuôi file không khớp định dạng thật (ví dụ PNG mang đuôi .jpg)."""
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    expected = {"jpeg": {"jpg", "jpeg", "jpe"}, "png": {"png"}, "gif": {"gif"}}
    return ext not in expected.get(fmt, {fmt})


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── trùng lặp ────────────────────────────────────────────────────────────────────────────
def dhash64(gray: np.ndarray) -> int:
    """dHash 64 bit: thu về 9×8, so từng điểm với điểm bên phải."""
    import cv2

    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA).astype(np.int16)
    bits = (small[:, 1:] > small[:, :-1]).ravel()
    return int(sum(1 << i for i, bit in enumerate(bits) if bit))


def _popcount64(values: np.ndarray) -> np.ndarray:
    if hasattr(np, "bitwise_count"):
        return np.bitwise_count(values).astype(np.int64)
    as_bytes = values.view(np.uint8).reshape(*values.shape, 8)
    table = np.array([bin(i).count("1") for i in range(256)], dtype=np.int64)
    return table[as_bytes].sum(axis=-1)


def hamming_pairs(
    hashes: Sequence[int], max_dist: int, block: int = 512
) -> list[tuple[int, int, int]]:
    """Mọi cặp (i, j, khoảng cách) với i < j và khoảng cách Hamming ≤ max_dist."""
    arr = np.asarray([int(h) & ((1 << 64) - 1) for h in hashes], dtype=np.uint64)
    pairs: list[tuple[int, int, int]] = []
    for start in range(0, len(arr), block):
        dist = _popcount64(arr[start : start + block, None] ^ arr[None, :])
        for left, right in zip(*np.nonzero(dist <= max_dist), strict=True):
            i, j = start + int(left), int(right)
            if i < j:
                pairs.append((i, j, int(dist[left, right])))
    return pairs


class UnionFind:
    """Union-find trên chỉ số 0..n-1 (nén đường đi)."""

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def components(self) -> dict[int, list[int]]:
        out: dict[int, list[int]] = defaultdict(list)
        for i in range(len(self.parent)):
            out[self.find(i)].append(i)
        return dict(out)


def exact_duplicates(shas: Sequence[str], labels: Sequence[str]) -> dict[int, str]:
    """Ảnh phải bỏ vì trùng byte: {chỉ số: lý do}.

    Cùng SHA-256 mà mang 2 nhãn → bỏ TẤT CẢ bản ("sha_conflict"); cùng nhãn → giữ bản có chỉ số
    nhỏ nhất, bỏ phần còn lại ("sha_dup").
    """
    by_sha: dict[str, list[int]] = defaultdict(list)
    for i, sha in enumerate(shas):
        by_sha[sha].append(i)
    drops: dict[int, str] = {}
    for members in by_sha.values():
        if len(members) < 2:
            continue
        if len({labels[i] for i in members}) > 1:
            drops.update({i: "sha_conflict" for i in members})
        else:
            drops.update({i: "sha_dup" for i in sorted(members)[1:]})
    return drops


def near_duplicate_drops(
    hashes: Sequence[int], labels: Sequence[str], candidates: Iterable[int], max_dist: int = 4
) -> dict[int, str]:
    """Gần trùng CÙNG NHÃN (dHash ≤ max_dist): mỗi cụm giữ 1 ảnh (chỉ số nhỏ nhất).

    Cặp gần trùng KHÁC nhãn là cặp "ảnh gốc / ảnh chụp lại màn hình" — giữ cả hai, chỉ gom
    chung nhóm (xem `link_groups`).
    """
    idx = sorted(set(candidates))
    local = [hashes[i] for i in idx]
    uf = UnionFind(len(idx))
    for a, b, _ in hamming_pairs(local, max_dist):
        if labels[idx[a]] == labels[idx[b]]:
            uf.union(a, b)
    drops: dict[int, str] = {}
    for members in uf.components().values():
        for m in sorted(members)[1:]:
            drops[idx[m]] = "dhash_dup"
    return drops


def embedding_pairs(
    embeddings: np.ndarray, threshold: float, block: int = 1024
) -> list[tuple[int, int]]:
    """Cặp (i < j) có cosine ≥ threshold. Hàng NaN (không có mặt) bị bỏ qua."""
    emb = np.asarray(embeddings, dtype=np.float32)
    valid = np.isfinite(emb).all(axis=1)
    index = np.flatnonzero(valid)
    mat = emb[valid]
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    mat = mat / np.maximum(norms, 1e-12)
    pairs: list[tuple[int, int]] = []
    for start in range(0, len(mat), block):
        sims = mat[start : start + block] @ mat.T
        for left, right in zip(*np.nonzero(sims >= threshold), strict=True):
            i, j = int(index[start + int(left)]), int(index[int(right)])
            if i < j:
                pairs.append((i, j))
    return pairs


def link_groups(keys: Sequence[str], pairs: Iterable[tuple[int, ...]]) -> list[str]:
    """Gom thành phần liên thông ("thà gộp nhầm còn hơn tách sót"); id nhóm ổn định theo keys."""
    uf = UnionFind(len(keys))
    for pair in pairs:
        uf.union(int(pair[0]), int(pair[1]))
    group_of = [""] * len(keys)
    for members in uf.components().values():
        gid = hashlib.sha1("\n".join(sorted(keys[m] for m in members)).encode()).hexdigest()[:16]
        for m in members:
            group_of[m] = gid
    return group_of


# ── chia tập theo nhóm ────────────────────────────────────────────────────────────────────
def assign_splits(
    groups: Sequence[str],
    labels: Sequence[str],
    fractions: dict[str, float] | None = None,
    seed: int = 42,
) -> dict[str, str]:
    """Gán mỗi nhóm vào đúng MỘT split, cân theo số ảnh từng nhãn. Trả {group_id: split}.

    Nhóm lớn xếp trước (trộn ngẫu nhiên theo seed rồi sắp ổn định theo cỡ), mỗi nhóm vào split
    đang thiếu nhiều nhất tính theo số ảnh của từng nhãn trong nhóm.
    """
    fractions = fractions or DEFAULT_FRACTIONS
    if set(fractions) != set(SPLITS) or not math.isclose(sum(fractions.values()), 1.0):
        raise ValueError("fractions phải có đủ 4 split và tổng bằng 1.")
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    totals: dict[str, int] = defaultdict(int)
    for g, lab in zip(groups, labels, strict=True):
        counts[g][lab] += 1
        totals[lab] += 1
    order = sorted(counts)
    rng = np.random.default_rng(seed)
    rng.shuffle(order)
    order.sort(key=lambda g: -sum(counts[g].values()))
    current = {s: defaultdict(float) for s in SPLITS}
    out: dict[str, str] = {}
    for g in order:
        best, best_gain = SPLITS[0], -math.inf
        for s in SPLITS:
            gain = sum(
                (fractions[s] * totals[lab] - current[s][lab]) * n / max(totals[lab], 1)
                for lab, n in counts[g].items()
            )
            if gain > best_gain + 1e-12:
                best, best_gain = s, gain
        out[g] = best
        for lab, n in counts[g].items():
            current[best][lab] += n
    return out


def check_split_integrity(groups: Sequence[str], splits: Sequence[str]) -> None:
    """Mỗi nhóm người chỉ được nằm ở MỘT split; sai thì ném lỗi."""
    seen: dict[str, str] = {}
    for g, s in zip(groups, splits, strict=True):
        if s not in SPLITS:
            raise ValueError(f"Split lạ: {s!r}")
        if seen.setdefault(g, s) != s:
            raise AssertionError(f"Nhóm {g} nằm ở cả {seen[g]} và {s}.")


def assert_not_test(splits: Iterable[str], context: str = "") -> None:
    """Chặn mọi bước của notebook đọc split `test` (chỉ trưởng nhóm chạy test, một lần)."""
    if any(s == FORBIDDEN_SPLIT for s in splits):
        raise AssertionError(
            f"CẤM dùng split 'test' trong notebook ({context}). Test chỉ chạy một lần sau khi chốt."
        )


def rows_of_split(rows: Sequence[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    """Lọc hàng theo split; gọi với 'test' là lỗi."""
    assert_not_test([split], f"rows_of_split({split!r})")
    out = [r for r in rows if r.get("split") == split]
    assert_not_test((r.get("split") for r in out), "rows_of_split")
    return out


# ── mặt và cắt (y hệt pad.py) ────────────────────────────────────────────────────────────
def largest_face(faces: Sequence[FaceBox]) -> tuple[FaceBox | None, str]:
    """Quy tắc của `FacePadDetector.predict`: không mặt / 2 mặt cỡ tương đương / mặt quá nhỏ."""
    if not faces:
        return None, "no_face"
    ordered = sorted(faces, key=lambda f: f.area, reverse=True)
    top = ordered[0]
    if len(ordered) > 1 and ordered[1].area >= SECOND_FACE_AREA_RATIO * top.area:
        return None, "multi_face"
    if top.x2 - top.x1 < 2 or top.y2 - top.y1 < 2:
        return None, "tiny_face"
    return top, "ok"


def shift_clip_box(box: FaceBox, dx: float, dy: float, width: int, height: int) -> FaceBox:
    """Đưa hộp từ ảnh đã đệm viền về toạ độ ảnh gốc và kẹp trong ảnh."""

    def cx(v: float) -> float:
        return float(min(max(v - dx, 0.0), width - 1))

    def cy(v: float) -> float:
        return float(min(max(v - dy, 0.0), height - 1))

    marks = None
    if box.landmarks is not None:
        marks = tuple((x - dx, y - dy) for x, y in box.landmarks)
    return FaceBox(cx(box.x1), cy(box.y1), cx(box.x2), cy(box.y2), box.confidence, marks)


def detect_face(
    finder: Any, image: np.ndarray, pad_ratio: float = 0.33
) -> tuple[FaceBox | None, str, bool, int]:
    """SCRFD như pad.py; trượt thì đệm viền đen `pad_ratio` mỗi cạnh rồi dò lại.

    Trả (hộp trong toạ độ ảnh gốc | None, trạng thái, đã_đệm, số_mặt).
    """
    import cv2

    faces = finder.find(image)
    box, status = largest_face(faces)
    if status != "no_face" or pad_ratio <= 0:
        return box, status, False, len(faces)
    height, width = image.shape[:2]
    px, py = int(round(width * pad_ratio)), int(round(height * pad_ratio))
    padded = cv2.copyMakeBorder(image, py, py, px, px, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    faces = finder.find(padded)
    box, status = largest_face(faces)
    if box is not None:
        box = shift_clip_box(box, px, py, width, height)
        if box.x2 - box.x1 < 2 or box.y2 - box.y1 < 2:
            return None, "tiny_face", True, len(faces)
    return box, status, True, len(faces)


def pad_crop(image: np.ndarray, box: FaceBox, size: int, scale: float = PAD_CROP_SCALE):
    """Cắt mặt bằng ĐÚNG `MiniFasNetClassifier._crop` của pad.py, chỉ đổi cỡ đầu ra."""
    shim = SimpleNamespace(_size=(int(size), int(size)), _scale=scale)
    return MiniFasNetClassifier._crop(shim, image, box)


def arcface_align(image: np.ndarray, landmarks: Sequence[Sequence[float]]) -> np.ndarray:
    """Căn 5 mốc về mẫu ArcFace 112×112 (similarity bình phương tối thiểu, như DATA-03)."""
    import cv2

    target = np.array(
        [
            [38.2946, 51.6963],
            [73.5318, 51.5014],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.2041],
        ],
        dtype=np.float64,
    )
    x, y = np.asarray(landmarks, dtype=np.float64).T
    design = np.zeros((10, 4), dtype=np.float64)
    design[0::2] = np.column_stack((x, -y, np.ones(5), np.zeros(5)))
    design[1::2] = np.column_stack((y, x, np.zeros(5), np.ones(5)))
    a, b, tx, ty = np.linalg.lstsq(design, target.ravel(), rcond=None)[0]
    transform = np.array([[a, -b, tx], [b, a, ty]], dtype=np.float32)
    return cv2.warpAffine(image, transform, (112, 112), borderValue=0.0)


# ── khử lộ đề ────────────────────────────────────────────────────────────────────────────
def jpeg_roundtrip(image: np.ndarray, quality: int = 90) -> tuple[np.ndarray, bytes]:
    """Nén JPEG lại cùng chất lượng (cv2 không ghi EXIF) rồi giải mã. Trả (ảnh, byte JPEG)."""
    import cv2

    ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise ValueError("Không nén được JPEG.")
    data = buf.tobytes()
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR), data


def meta_features(data: bytes) -> dict[str, float]:
    """Siêu dữ liệu của file ảnh (KHÔNG nhìn điểm ảnh): định dạng, cỡ, EXIF, bảng lượng tử."""
    fmt = sniff_format(data[:16])
    feats = {
        "is_jpeg": float(fmt == "jpeg"),
        "is_png": float(fmt == "png"),
        "file_bytes": float(len(data)),
        "width": 0.0,
        "height": 0.0,
        "has_exif": float(b"Exif\x00\x00" in data[:65536]),
        "n_app_segments": 0.0,
        "qtable_sum": 0.0,
        "progressive": 0.0,
    }
    if fmt == "png" and len(data) >= 24:
        feats["width"] = float(int.from_bytes(data[16:20], "big"))
        feats["height"] = float(int.from_bytes(data[20:24], "big"))
    if fmt != "jpeg":
        return feats
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            break
        marker = data[pos + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        length = int.from_bytes(data[pos + 2 : pos + 4], "big")
        body = data[pos + 4 : pos + 2 + length]
        if 0xE0 <= marker <= 0xEF:
            feats["n_app_segments"] += 1
        elif marker == 0xDB and feats["qtable_sum"] == 0 and len(body) >= 65:
            precision = body[0] >> 4
            table = body[1 : 1 + 64 * (2 if precision else 1)]
            feats["qtable_sum"] = float(sum(table))
        elif marker in (0xC0, 0xC1, 0xC2) and len(body) >= 5:
            feats["height"] = float(int.from_bytes(body[1:3], "big"))
            feats["width"] = float(int.from_bytes(body[3:5], "big"))
            feats["progressive"] = float(marker == 0xC2)
        elif marker == 0xDA:
            break
        pos += 2 + length
    return feats


def univariate_auc(values: Sequence[float], labels: Sequence[int]) -> float:
    """max(AUC, 1 − AUC) của một đặc trưng; hằng số → 0,5."""
    x = np.asarray(values, dtype=float)
    y = np.asarray(labels, dtype=int)
    if np.unique(y).size < 2 or np.unique(x).size < 2:
        return 0.5
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=float)
    sorted_x = x[order]
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and sorted_x[j + 1] == sorted_x[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2 + 1
        i = j + 1
    n_pos, n_neg = int(y.sum()), int((1 - y).sum())
    value = (ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return float(max(value, 1 - value))


def leak_auc(
    features: Sequence[dict[str, float]],
    labels: Sequence[int],
    groups: Sequence[str],
    seed: int = 42,
    folds: int = 5,
) -> dict[str, Any]:
    """AUC của mô hình CHỈ dùng siêu dữ liệu (GroupKFold theo nhóm người, lấy mô hình tốt hơn
    trong hồi quy logistic và cây tăng cường). Kèm AUC đơn biến từng đặc trưng."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    names = sorted({k for f in features for k in f})
    x = np.array([[f.get(k, 0.0) for k in names] for f in features], dtype=float)
    y = np.asarray(labels, dtype=int)
    g = np.asarray(groups)
    per_feature = {k: univariate_auc(x[:, i], y) for i, k in enumerate(names)}
    result: dict[str, Any] = {"n": int(len(y)), "per_feature": per_feature, "models": {}}
    n_splits = min(folds, len(set(g)))
    if np.unique(y).size < 2 or n_splits < 2:
        result["model_auc"] = 0.5
        return result
    models: dict[str, Callable[[], Any]] = {
        "logistic": lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "hgb": lambda: HistGradientBoostingClassifier(max_iter=100, random_state=seed),
    }
    for name, factory in models.items():
        scores = np.full(len(y), np.nan)
        for train_idx, test_idx in GroupKFold(n_splits=n_splits).split(x, y, g):
            if np.unique(y[train_idx]).size < 2:
                scores[test_idx] = 0.5
                continue
            model = factory().fit(x[train_idx], y[train_idx])
            scores[test_idx] = model.predict_proba(x[test_idx])[:, 1]
        result["models"][name] = univariate_auc(scores, y)
    result["model_auc"] = max(result["models"].values())
    return result


# ── chỉ số PAD (1 = tấn công, điểm ≥ ngưỡng thì từ chối) ─────────────────────────────────
def threshold_at_bpcer(
    labels: Sequence[int], attack_scores: Sequence[float], max_bpcer: float = 0.01
) -> float:
    """Ngưỡng nhỏ nhất sao cho tỉ lệ người thật bị từ chối (điểm ≥ ngưỡng) ≤ max_bpcer."""
    y = np.asarray(labels, dtype=int)
    p = np.asarray(attack_scores, dtype=float)
    live = np.sort(p[y == 0])[::-1]
    if live.size == 0:
        raise ValueError("Cần ít nhất một mẫu thật để chọn ngưỡng.")
    allowed = int(math.floor(max_bpcer * live.size + 1e-9))
    if allowed >= live.size:
        return 0.0
    return float(min(np.nextafter(live[allowed], np.inf), 1.0))


def pad_metrics(
    labels: Sequence[int],
    attack_scores: Sequence[float],
    groups: Sequence[str] | None = None,
    max_bpcer: float = 0.01,
    n_boot: int = 200,
    seed: int = 0,
) -> dict[str, Any]:
    """AUC, EER, ngưỡng tại BPCER ≤ max_bpcer và APCER ở ngưỡng đó; CI 95 % bootstrap theo nhóm."""
    y = np.asarray(labels, dtype=int)
    p = np.clip(np.asarray(attack_scores, dtype=float), 0.0, 1.0)
    t = threshold_at_bpcer(y, p, max_bpcer)
    out: dict[str, Any] = {
        "n_live": int((y == 0).sum()),
        "n_attack": int((y == 1).sum()),
        "auc": auc(y, p),
        "eer": eer(y, p),
        "threshold_at_bpcer": t,
        "bpcer": bpcer(y, p, t),
        "apcer": float(np.mean(p[y == 1] < t)) if np.any(y == 1) else None,
    }
    if groups is None or n_boot <= 0:
        return out
    g = np.asarray(groups)
    unique = np.unique(g)
    out["n_groups"] = int(unique.size)
    members = {k: np.flatnonzero(g == k) for k in unique}
    rng = np.random.default_rng(seed)
    apcers, aucs = [], []
    for _ in range(n_boot):
        pick = rng.choice(unique, size=unique.size, replace=True)
        idx = np.concatenate([members[k] for k in pick])
        yb, pb = y[idx], p[idx]
        if np.unique(yb).size < 2:
            continue
        tb = threshold_at_bpcer(yb, pb, max_bpcer)
        apcers.append(float(np.mean(pb[yb == 1] < tb)))
        aucs.append(float(auc(yb, pb)))
    if apcers:
        out["apcer_ci95"] = [float(np.percentile(apcers, 2.5)), float(np.percentile(apcers, 97.5))]
        out["auc_ci95"] = [float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5))]
    return out


def selection_key(metrics: dict[str, Any]) -> tuple[float, float, float]:
    """Khóa chọn mô hình/checkpoint trên calib_fit: APCER thấp, rồi EER thấp, rồi AUC cao."""

    def val(name: str, default: float) -> float:
        v = metrics.get(name)
        return default if v is None or not np.isfinite(v) else float(v)

    return (val("apcer", 1.0), val("eer", 1.0), -val("auc", 0.0))


def rank_key(metrics: dict[str, Any]) -> tuple[float, float]:
    """Khóa so sánh đơn lẻ vs gộp (ADR-0015, trưởng nhóm 20/10): APCER@BPCER≤1 % rồi AUC cao."""

    def val(name: str, default: float) -> float:
        v = metrics.get(name)
        return default if v is None or not np.isfinite(v) else float(v)

    return (val("apcer", 1.0), -val("auc", 0.0))


def combo_max(*attack_probabilities: Sequence[float]) -> np.ndarray:
    """Gộp như TrustRouter `fusion.method = max`: xác suất tấn công ĐÃ hiệu chỉnh lớn nhất."""
    if not attack_probabilities:
        raise ValueError("Cần ít nhất một vector xác suất.")
    stacked = np.vstack([np.asarray(p, dtype=float) for p in attack_probabilities])
    return stacked.max(axis=0)


def recommend(singles: dict[str, dict[str, Any]], combo: dict[str, Any] | None) -> dict[str, Any]:
    """Khuyến nghị: COMBO hơn đơn lẻ tốt nhất (APCER, hòa thì AUC) → "dùng cả hai";
    ngược lại dùng đơn lẻ tốt nhất. Trả {choice, best_single, reason_vi}."""
    if not singles:
        raise ValueError("Cần ít nhất một mô hình đơn lẻ.")
    best = min(singles, key=lambda k: rank_key(singles[k]))
    b = singles[best]
    if combo is not None and rank_key(combo) < rank_key(b):
        reason = (
            f"Gộp max thắng: APCER {combo['apcer']:.4f} so với {b['apcer']:.4f} của {best}"
            if combo["apcer"] != b["apcer"]
            else f"Gộp max hòa APCER ({combo['apcer']:.4f}) nhưng AUC cao hơn: "
            f"{combo['auc']:.4f} so với {b['auc']:.4f} của {best}"
        )
        return {"choice": "combo", "best_single": best, "reason_vi": reason}
    if combo is None:
        reason = f"Không có mô hình thứ hai để gộp; {best} tốt nhất."
    else:
        reason = (
            f"Gộp max KHÔNG hơn {best}: APCER {combo['apcer']:.4f} so với {b['apcer']:.4f}, "
            f"AUC {combo['auc']:.4f} so với {b['auc']:.4f} — thêm mô hình thứ hai không đáng."
        )
    return {"choice": best, "best_single": best, "reason_vi": reason}


# ── tăng cường giống camera trước điện thoại rẻ (cùng cho cả 2 lớp) ──────────────────────
def phone_camera_augment(image: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Lật, tối/thiếu sáng, thu nhỏ rồi phóng lại, mờ, nhiễu cảm biến, nén JPEG 30–95."""
    import cv2

    out = image
    if rng.random() < 0.5:
        out = out[:, ::-1]
    out = out.astype(np.float32)
    if rng.random() < 0.4:  # thiếu sáng (gamma) + lệch độ tương phản
        gamma = rng.uniform(1.2, 2.2)
        out = 255.0 * (out / 255.0) ** gamma
    if rng.random() < 0.5:
        out = out * rng.uniform(0.7, 1.25) + rng.uniform(-20, 20)
    out = np.clip(out, 0, 255).astype(np.uint8)
    h, w = out.shape[:2]
    if rng.random() < 0.3:
        f = rng.uniform(0.35, 0.9)
        small = cv2.resize(
            out, (max(8, int(w * f)), max(8, int(h * f))), interpolation=cv2.INTER_AREA
        )
        out = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    if rng.random() < 0.3:
        k = int(rng.choice([3, 5]))
        out = cv2.GaussianBlur(out, (k, k), 0)
    if rng.random() < 0.4:
        noise = rng.normal(0, rng.uniform(2, 12), out.shape)
        out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    if rng.random() < 0.5:
        out, _ = jpeg_roundtrip(np.ascontiguousarray(out), int(rng.integers(30, 96)))
    return np.ascontiguousarray(out)


# ── dữ liệu test phụ ─────────────────────────────────────────────────────────────────────
def aux_label_from_path(dataset: str, rel_path: str) -> tuple[str, str] | None:
    """Nhãn (live|not_live, loại tấn công) của ảnh/video Axon hoặc UniData.

    `dataset` là tên thư mục bộ dữ liệu (ví dụ `axon_print`, `print-attack-dataset`); loại tấn
    công chỉ suy từ tên bộ và tên thư mục, KHÔNG từ tên file (tránh khớp nhầm chuỗi ngẫu nhiên).
    """
    parts = [x for x in rel_path.replace("\\", "/").lower().split("/") if x]
    folders, filename = parts[:-1], (parts[-1] if parts else "")
    key = dataset.lower()
    if any(x in ("real", "live", "selfies", "selfie") for x in folders) or "selfie" in filename:
        return "live", "bona_fide"
    if any(x in key for x in ("unique", "asian", "unidata")):
        return "live", "bona_fide"
    p = "/".join([key, *folders])
    rules = (
        ("cut", "cutout_print"),
        ("3d", "paper_mask_3d"),
        ("mask", "paper_mask_3d"),
        ("print", "print"),
        ("display", "display_replay"),
        ("screen", "display_replay"),
        ("mobile", "mobile_replay"),
        ("replay", "mobile_replay"),
    )
    for word, attack in rules:
        if word in p:
            return "not_live", attack
    return None


def video_frames(path: str, fractions: Sequence[float] = (0.15, 0.5, 0.85)) -> list[np.ndarray]:
    """Lấy vài khung đều nhau trong video (để đo test phụ)."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    frames: list[np.ndarray] = []
    try:
        count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not cap.isOpened() or not math.isfinite(count) or count < 1:
            return frames
        for fraction in fractions:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(max(0, count - 1) * fraction))
            ok, frame = cap.read()
            if ok and frame is not None:
                frames.append(frame)
    finally:
        cap.release()
    return frames


# ── đồ thị ONNX ↔ torch (MiniFASNet: dạy lại mà giữ nguyên đồ thị) ───────────────────────
def onnx_to_ir(model: Any) -> dict[str, Any]:
    """Đọc đồ thị ONNX thành dạng trung gian thuần Python: nút, thuộc tính, initializer."""
    from onnx import helper, numpy_helper

    inits = {t.name: numpy_helper.to_array(t).copy() for t in model.graph.initializer}
    nodes = []
    for node in model.graph.node:
        attrs = {}
        for a in node.attribute:
            value = helper.get_attribute_value(a)
            attrs[a.name] = value.decode() if isinstance(value, bytes) else value
        nodes.append(
            {
                "op": node.op_type,
                "inputs": list(node.input),
                "outputs": list(node.output),
                "attrs": attrs,
            }
        )
    return {
        "inputs": [i.name for i in model.graph.input if i.name not in inits],
        "outputs": [o.name for o in model.graph.output],
        "initializers": inits,
        "nodes": nodes,
    }


def build_torch_graph(ir: dict[str, Any]) -> Any:
    """nn.Module chạy đúng đồ thị IR. Initializer số thực là tham số học được, trừ trung bình
    và phương sai của BatchNormalization (buffer, luôn ở chế độ eval)."""
    import torch
    import torch.nn.functional as F  # noqa: N812
    from torch import nn

    frozen = set()
    for node in ir["nodes"]:
        if node["op"] == "BatchNormalization":
            frozen.update(node["inputs"][3:5])
    supported = {
        "Conv", "PRelu", "Add", "MatMul", "Flatten", "BatchNormalization", "Relu", "Gemm",
        "Mul", "Sigmoid", "GlobalAveragePool", "Reshape",
    }  # fmt: skip
    unknown = {n["op"] for n in ir["nodes"]} - supported
    if unknown:
        raise NotImplementedError(f"Chưa hỗ trợ toán tử ONNX: {sorted(unknown)}")

    class OnnxGraphModule(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.ir_nodes = ir["nodes"]
            self.ir_inputs = ir["inputs"]
            self.ir_outputs = ir["outputs"]
            self.key_of: dict[str, str] = {}
            self.params = nn.ParameterDict()
            for i, (name, arr) in enumerate(ir["initializers"].items()):
                key = f"t{i}"
                self.key_of[name] = key
                tensor = torch.from_numpy(np.ascontiguousarray(arr))
                if np.issubdtype(arr.dtype, np.floating) and name not in frozen:
                    self.params[key] = nn.Parameter(tensor.float())
                else:
                    self.register_buffer(key, tensor)

        def _get(self, env: dict[str, Any], name: str) -> Any:
            if name in env:
                return env[name]
            key = self.key_of[name]
            return self.params[key] if key in self.params else getattr(self, key)

        def forward(self, *xs: Any) -> Any:
            env = dict(zip(self.ir_inputs, xs, strict=True))
            for node in self.ir_nodes:
                ins = [self._get(env, n) if n else None for n in node["inputs"]]
                a, op = node["attrs"], node["op"]
                if op == "Conv":
                    pads = list(a.get("pads", [0, 0, 0, 0]))
                    x = ins[0]
                    if pads[0] != pads[2] or pads[1] != pads[3]:
                        x = F.pad(x, (pads[1], pads[3], pads[0], pads[2]))
                        pads = [0, 0, 0, 0]
                    y = F.conv2d(
                        x,
                        ins[1],
                        ins[2] if len(ins) > 2 else None,
                        stride=tuple(a.get("strides", [1, 1])),
                        padding=(pads[0], pads[1]),
                        dilation=tuple(a.get("dilations", [1, 1])),
                        groups=int(a.get("group", 1)),
                    )
                elif op == "PRelu":
                    y = torch.where(ins[0] >= 0, ins[0], ins[0] * ins[1])
                elif op == "Add":
                    y = ins[0] + ins[1]
                elif op == "Mul":
                    y = ins[0] * ins[1]
                elif op == "MatMul":
                    y = torch.matmul(ins[0], ins[1])
                elif op == "Gemm":
                    left = ins[0].t() if a.get("transA", 0) else ins[0]
                    right = ins[1].t() if a.get("transB", 0) else ins[1]
                    y = a.get("alpha", 1.0) * (left @ right)
                    if len(ins) > 2 and ins[2] is not None:
                        y = y + a.get("beta", 1.0) * ins[2]
                elif op == "Flatten":
                    axis = int(a.get("axis", 1))
                    y = ins[0].reshape(int(np.prod(ins[0].shape[:axis])), -1)
                elif op == "BatchNormalization":
                    y = F.batch_norm(
                        ins[0], ins[3], ins[4], ins[1], ins[2], False, 0.0, a.get("epsilon", 1e-5)
                    )
                elif op == "Relu":
                    y = torch.relu(ins[0])
                elif op == "Sigmoid":
                    y = torch.sigmoid(ins[0])
                elif op == "GlobalAveragePool":
                    y = ins[0].mean(dim=(2, 3), keepdim=True)
                else:  # Reshape
                    y = ins[0].reshape([int(v) for v in ins[1].tolist()])
                env[node["outputs"][0]] = y
            outs = [env[n] for n in self.ir_outputs]
            return outs[0] if len(outs) == 1 else tuple(outs)

        def initializer_arrays(self) -> dict[str, np.ndarray]:
            out = {}
            for name, key in self.key_of.items():
                t = self.params[key] if key in self.params else getattr(self, key)
                out[name] = t.detach().cpu().numpy()
            return out

    return OnnxGraphModule()


def write_onnx_weights(model: Any, arrays: dict[str, np.ndarray]) -> Any:
    """Bản sao đồ thị ONNX gốc với initializer thay bằng trọng số mới (giữ kiểu dữ liệu)."""
    import copy

    from onnx import numpy_helper

    new = copy.deepcopy(model)
    for i, tensor in enumerate(new.graph.initializer):
        if tensor.name in arrays:
            old = numpy_helper.to_array(tensor)
            arr = np.asarray(arrays[tensor.name]).astype(old.dtype).reshape(old.shape)
            new.graph.initializer[i].CopyFrom(numpy_helper.from_array(arr, tensor.name))
    return new


def binary_live_loss(logits: Any, is_live: Any, class_weight: Sequence[float] = (1.0, 1.0)) -> Any:
    """CE nhị phân trên đầu 3 lớp của MiniFASNet: lớp 1 = thật, gộp (logsumexp) các lớp còn lại
    thành "giả" — giữ nguyên đầu ra 3 lớp để pad.py đọc softmax[:, 1] như cũ."""
    import torch

    log_p = torch.log_softmax(logits, dim=1)
    log_real = log_p[:, 1]
    others = torch.cat([log_p[:, :1], log_p[:, 2:]], dim=1)
    log_fake = torch.logsumexp(others, dim=1)
    target = is_live.float()
    weight = torch.where(
        target > 0.5,
        torch.full_like(target, float(class_weight[0])),
        torch.full_like(target, float(class_weight[1])),
    )
    loss = -(target * log_real + (1 - target) * log_fake)
    return (weight * loss).sum() / weight.sum()
