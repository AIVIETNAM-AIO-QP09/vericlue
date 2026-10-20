"""FACE-04 (hiệu chỉnh) — hàm thuần cho notebook `ml/notebooks/calibrate_gend.ipynb`.

GenD gốc KHÔNG được dạy lại. Notebook chỉ chấm điểm bằng đúng `face/gend.py` rồi fit calibrator
(`vericlue_ml.common.calibration.fit`, ADR-0010) trên `calib_fit`:
- lớp thật: người Việt thật FAS-VN live và video gốc RTFS-10k (VLR chỉ tham khảo, không fit);
- lớp giả: video ghép mặt RTFS-10k (inswapper, uniface). Không tự tạo deepfake.

Ở đây có: chia RTFS theo video YouTube gốc và ảnh donor (cắt cạnh để các tập không chung donor),
khung cắt vuông quanh mặt và lệnh ffmpeg mã hóa lại DÙNG CHUNG cho mọi nguồn, báo cáo lộ đề nguồn,
tỉ lệ vượt ngưỡng, xác suất ngoài-fold theo nhóm. Không đọc tập test (`assert_no_test`).
"""

from __future__ import annotations

import hashlib
import math
import random
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from vericlue_ml.finetune.data04 import (
    LEAK_FEATURES,
    UnionFind,
    assign_splits,
    cluster_persons,
    group_components,
    univariate_auc,
)

CALIB_SPLITS = ("calib_fit", "calib_ltt", "test")
CALIB_RATIOS = (0.4, 0.3, 0.3)
EXPECTED_MODEL_VERSION = (
    "gend-clip-l14@891ce014+clip@32bd6428+scrfd-10g@bfcc7d48+agg-maxmeantop25-v1"
)
# Ngưỡng tạm của thresholds.yaml (face.b, face.a) — chỉ để BÁO CÁO, không chọn ngưỡng ở đây.
REPORT_THRESHOLDS = {"B": 0.15, "A": 0.60}
CROP_SIZE = 320
CROP_SCALE = 2.5  # cạnh khung vuông = 2,5 × cạnh lớn của hộp mặt (giống khung VLR 320×320)
ENCODE_CRF = 23
ENCODE_FPS = 25
ENCODE_SECONDS = 3.0
SOURCE_LEAK_RANGE = (0.4, 0.6)
# ArcFace MobileFaceNet (uniface, nghiên cứu phi thương mại) — cùng mục với manifest nhánh DATA-03.
# Chỉ để gom người khi chia tập; embedding chỉ nằm trong thư mục nháp, xóa khi xong.
ARCFACE = {
    "id": "arcface-mnet",
    "path": "arcface_mnet.onnx",
    "url": "https://huggingface.co/yakhyo/uniface-weights/resolve/"
    "bfcc7d48ea8412d55de406cecf96b65b3ca720b2/arcface_mnet.onnx?download=true",
    "sha256": "9cc6e4a75f0e2bf0b1aed94578f144d15175f357bdc05e815e5c4a02b319eb4f",
}
VN_SOURCES = ("vlr", "fas_vn")
# Quyết định trưởng nhóm 20/10: fit calibrator CHỈ bằng FAS-VN live + RTFS (thật, giả). VLR chỉ tham khảo.
FIT_SOURCES = ("fas_vn", "rtfs_real", "rtfs_fake")
REFERENCE_SOURCES = ("vlr",)


# ── RTFS-10k: chia theo video YouTube gốc + ảnh donor ────────────────────────────────────
_RTFS_RE = re.compile(r"([A-Za-z0-9_-]{11})_\d+_\d+(?:_|$)")


def rtfs_youtube_id(filename: str) -> str | None:
    """YouTube ID 11 ký tự trong tên file RTFS (bỏ tiền tố inswapper_/uniface_)."""
    stem = Path(filename).stem
    for prefix in ("inswapper_", "uniface_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix) :]
    match = _RTFS_RE.match(stem)
    return match.group(1) if match else None


@dataclass
class RtfsSplit:
    real: dict[str, tuple[str, str]]  # tên video gốc → (tập, nhóm)
    fake: dict[str, tuple[str, str]]  # tên video giả giữ lại → (tập, nhóm)
    dropped: list[str]  # video giả bị bỏ vì donor thuộc tập khác
    report: dict[str, Any] = field(default_factory=dict)


def split_rtfs(
    videos: Sequence[Mapping[str, str]],
    fakes: Sequence[Mapping[str, str]],
    *,
    seed: int,
    ratios: Sequence[float] = CALIB_RATIOS,
    names: Sequence[str] = CALIB_SPLITS,
) -> RtfsSplit:
    """Chia RTFS sao cho video gốc (YouTube ID) VÀ ảnh donor không vắt qua hai tập.

    Đồ thị video–donor của RTFS liên thông thành MỘT khối (mỗi ảnh donor dùng cho nhiều video), nên
    không chia nguyên khối được. Cách làm: chia video YouTube theo tỉ lệ; mỗi ảnh donor theo tập
    chiếm đa số trong các video giả dùng nó (hòa → theo thứ tự `names`); video giả có donor khác tập
    với video gốc thì BỎ. `videos`: dòng videos.csv (`filename`), `fakes`: dòng inswapper/uniface.csv
    (`video`, `photo`, `filename`)."""
    yt_of = {}
    for row in videos:
        yid = rtfs_youtube_id(row["filename"])
        if yid is None:
            raise ValueError(f"Không đọc được YouTube ID: {row['filename']}")
        yt_of[row["filename"]] = yid
    for row in fakes:
        if row["video"] not in yt_of:
            raise ValueError(f"Video giả {row['filename']} trỏ tới video gốc lạ {row['video']}")
    # Báo cáo khối liên thông trước khi cắt.
    nodes = sorted({f"v:{y}" for y in yt_of.values()} | {f"p:{r['photo']}" for r in fakes})
    index = {n: i for i, n in enumerate(nodes)}
    uf = UnionFind(len(nodes))
    for row in fakes:
        uf.union(index[f"v:{yt_of[row['video']]}"], index[f"p:{row['photo']}"])
    labels = uf.labels()
    comp_videos = Counter(labels[index[f"v:{y}"]] for y in set(yt_of.values()))
    split_of_yt = assign_splits(
        dict.fromkeys(sorted(set(yt_of.values())), 1), ratios, seed=seed, names=names
    )
    votes: dict[str, Counter] = defaultdict(Counter)
    for row in fakes:
        votes[row["photo"]][split_of_yt[yt_of[row["video"]]]] += 1
    order = {n: i for i, n in enumerate(names)}
    photo_split = {
        p: sorted(c.items(), key=lambda kv: (-kv[1], order[kv[0]]))[0][0] for p, c in votes.items()
    }
    real = {f: (split_of_yt[y], f"rtfs:yt:{y}") for f, y in yt_of.items()}
    fake: dict[str, tuple[str, str]] = {}
    dropped: list[str] = []
    for row in sorted(fakes, key=lambda r: r["filename"]):
        yid = yt_of[row["video"]]
        split = split_of_yt[yid]
        if photo_split[row["photo"]] == split:
            fake[row["filename"]] = (split, f"rtfs:yt:{yid}")
        else:
            dropped.append(row["filename"])
    report = {
        "youtube_videos": len(set(yt_of.values())),
        "donor_photos": len(votes),
        "components_before_cut": len(comp_videos),
        "largest_component_video_share": max(comp_videos.values())
        / max(1, len(set(yt_of.values()))),
        "fakes_total": len(fakes),
        "fakes_kept": len(fake),
        "fakes_dropped": len(dropped),
        "kept_by_split": dict(Counter(s for s, _ in fake.values())),
        "real_by_split": dict(Counter(s for s, _ in real.values())),
    }
    check_rtfs_split(real, fake, fakes)
    return RtfsSplit(real, fake, dropped, report)


def check_rtfs_split(
    real: Mapping[str, tuple[str, str]],
    fake: Mapping[str, tuple[str, str]],
    fakes: Sequence[Mapping[str, str]],
) -> None:
    """Video giả cùng tập với video gốc; một ảnh donor chỉ ở một tập."""
    photo_seen: dict[str, str] = {}
    for row in fakes:
        if row["filename"] not in fake:
            continue
        split = fake[row["filename"]][0]
        if real[row["video"]][0] != split:
            raise ValueError(f"Video giả {row['filename']} khác tập với video gốc.")
        if photo_seen.setdefault(row["photo"], split) != split:
            raise ValueError(f"Ảnh donor {row['photo']} nằm ở hai tập.")


# ── nhóm người cho VLR / FAS-VN ──────────────────────────────────────────────────────────
def person_groups(
    embeddings: Sequence[np.ndarray],
    sources: Sequence[str],
    videos: Sequence[str],
    *,
    threshold: float,
) -> tuple[list[str], dict[str, Any]]:
    """Nhóm chia tập = (cùng người theo ArcFace, gom lỏng, liên kết đơn) ∪ (cùng video nguồn).
    Mẫu không có embedding (mảng rỗng) chỉ nối theo video. Trả (group_id, báo cáo phân bố)."""
    if not (len(embeddings) == len(sources) == len(videos)):
        raise ValueError("embeddings, sources, videos phải cùng độ dài.")
    persons = cluster_persons(
        [e if np.size(e) else np.zeros((0, 1), np.float32) for e in embeddings], threshold
    )
    groups = group_components(persons, list(videos))
    sizes = Counter(groups)
    group_ids = [f"vn:g{g}" for g in groups]
    report = {
        "samples": len(groups),
        "persons": len(set(persons)),
        "groups": len(sizes),
        "largest_group_share": max(sizes.values()) / len(groups) if groups else 0.0,
        "group_size_top5": [n for _, n in sizes.most_common(5)],
        "by_source": dict(Counter(sources)),
    }
    return group_ids, report


def split_groups(
    group_ids: Sequence[str], *, seed: int, ratios: Sequence[float] = CALIB_RATIOS
) -> dict[str, str]:
    """Gán nhóm (trọng số = số mẫu) vào calib_fit / calib_ltt / test."""
    return assign_splits(dict(Counter(group_ids)), ratios, seed=seed, names=CALIB_SPLITS)


# ── khung cắt vuông quanh mặt + mã hóa lại dùng chung ────────────────────────────────────
def square_crop_box(
    boxes: Sequence[Sequence[float]], width: int, height: int, scale: float = CROP_SCALE
) -> tuple[int, int, int]:
    """(x, y, cạnh) chẵn của khung vuông quanh hợp các hộp mặt, nằm trọn trong ảnh."""
    if not boxes:
        raise ValueError("Không có hộp mặt.")
    array = np.asarray(boxes, dtype=float)
    x1, y1 = array[:, 0].min(), array[:, 1].min()
    x2, y2 = array[:, 2].max(), array[:, 3].max()
    side = max(x2 - x1, y2 - y1) * scale
    side = int(min(side, width, height)) // 2 * 2
    if side < 2:
        raise ValueError("Khung cắt quá nhỏ.")
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    x = int(round(min(max(cx - side / 2, 0), width - side))) // 2 * 2
    y = int(round(min(max(cy - side / 2, 0), height - side))) // 2 * 2
    return x, y, side


def crop_encode_cmd(
    ffmpeg: str,
    src: str | Path,
    dst: str | Path,
    box: tuple[int, int, int],
    *,
    still: bool = False,
    size: int = CROP_SIZE,
    crf: int = ENCODE_CRF,
    fps: int = ENCODE_FPS,
    seconds: float = ENCODE_SECONDS,
) -> list[str]:
    """Một lệnh ffmpeg cho MỌI nguồn (thật/giả, video/ảnh): cắt vuông → 320×320 → H.264 CRF 23,
    25 fps, bỏ âm thanh và metadata. Ảnh tĩnh thành video 1 khung cùng cấu hình."""
    x, y, side = box
    vf = f"crop={side}:{side}:{x}:{y},scale={size}:{size}:flags=bicubic"
    cmd = [str(ffmpeg), "-nostdin", "-y", "-loglevel", "error", "-i", str(src)]
    if still:
        cmd += ["-frames:v", "1"]
    else:
        cmd += ["-t", f"{seconds:.3f}"]
        vf += f",fps={fps}"
    vf += ",format=yuv420p"
    cmd += [
        "-an",
        "-sn",
        "-dn",
        "-map_metadata",
        "-1",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        str(int(crf)),
        "-g",
        str(2 * fps),
        "-bf",
        "2",
        "-r",
        str(fps),
        "-fflags",
        "+bitexact",
        "-flags:v",
        "+bitexact",
        "-movflags",
        "+faststart",
        str(dst),
    ]
    return cmd


# ── FAS-VN: chỉ ảnh live, bỏ trùng byte và ảnh trùng với not_live ────────────────────────
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fas_live_files(root: Path) -> tuple[list[Path], dict[str, int]]:
    """Ảnh `**/live/*` của FAS-VN, bỏ bản trùng byte và ảnh có byte trùng một ảnh `not_live`."""
    root = Path(root)
    suffixes = {".jpg", ".jpeg", ".png"}
    live = sorted(
        p for p in root.rglob("*") if p.suffix.lower() in suffixes and p.parent.name == "live"
    )
    spoof = [p for p in root.rglob("*") if p.suffix.lower() in suffixes and p.parent.name != "live"]
    spoof_hashes = {sha256_bytes(p.read_bytes()) for p in spoof}
    seen: set[str] = set()
    keep: list[Path] = []
    counts = Counter()
    for path in live:
        digest = sha256_bytes(path.read_bytes())
        if digest in spoof_hashes:
            counts["live_equal_to_spoof"] += 1
            continue
        if digest in seen:
            counts["duplicate"] += 1
            continue
        seen.add(digest)
        keep.append(path)
    counts["live_kept"] = len(keep)
    counts["spoof_files_scanned"] = len(spoof)
    return keep, dict(counts)


# ── lộ đề nguồn ──────────────────────────────────────────────────────────────────────────
def source_leak_report(
    features: Sequence[Mapping[str, float]],
    labels: Sequence[int],
    auc_range: tuple[float, float] = SOURCE_LEAK_RANGE,
    feature_names: Sequence[str] = LEAK_FEATURES,
    pair_vi: str = "thật (VLR/FAS-VN) và giả (RTFS)",
) -> dict[str, Any]:
    """AUC đơn biến từng đặc trưng thô (nhãn 1 = giả) giữa hai nhóm `pair_vi`. Ngoài khoảng →
    CẢNH BÁO (không dừng): calibrator chỉ là hàm 1 chiều của điểm GenD, nhưng nếu thật và giả khác
    nguồn thì calibrator có thể học 'nguồn' chứ không phải 'giả'."""
    low, high = auc_range
    aucs = {}
    for name in feature_names:
        values = [float(f[name]) for f in features]
        if np.ptp(values) == 0:
            aucs[name] = 0.5
            continue
        aucs[name] = univariate_auc(values, labels)
    flagged = {k: v for k, v in aucs.items() if v is not None and not low <= v <= high}
    n_pos = int(np.sum(np.asarray(labels) == 1))
    counts = f"{len(labels) - n_pos} thật / {n_pos} giả"
    if flagged:
        worst = max(flagged, key=lambda k: abs(flagged[k] - 0.5))
        message = (
            f"CẢNH BÁO LỘ ĐỀ NGUỒN ({counts}): {len(flagged)} đặc trưng thô tách được {pair_vi} "
            f"(mạnh nhất: {worst} AUC {flagged[worst]:.3f}, ngoài [{low}; {high}]). Calibrator có "
            "thể học 'nguồn' thay vì 'giả'. Đã ghi vào card.md."
        )
    else:
        message = f"Lộ đề nguồn ({counts}): mọi đặc trưng thô có AUC trong [{low}; {high}]."
    return {"auc": aucs, "flagged": flagged, "warning": bool(flagged), "message_vi": message}


# ── báo cáo điểm ─────────────────────────────────────────────────────────────────────────
def exceed_rates(
    probabilities: Sequence[float], thresholds: Mapping[str, float] = REPORT_THRESHOLDS
) -> dict[str, float | None]:
    """Tỉ lệ mẫu có xác suất ≥ từng ngưỡng (None khi rỗng)."""
    p = np.asarray(probabilities, dtype=float)
    return {k: (float(np.mean(p >= t)) if p.size else None) for k, t in thresholds.items()}


def score_summary(rows: Iterable[Mapping[str, Any]], key: str = "score") -> dict[str, dict]:
    """Phân bố điểm theo `source`/`label`: n, trung bình, p10/p50/p90."""
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        buckets[f"{row['source']}|{'gia' if int(row['label']) else 'that'}"].append(float(row[key]))
    out = {}
    for name, values in sorted(buckets.items()):
        v = np.asarray(values)
        out[name] = {
            "n": int(v.size),
            "mean": float(v.mean()),
            "p10": float(np.percentile(v, 10)),
            "p50": float(np.percentile(v, 50)),
            "p90": float(np.percentile(v, 90)),
        }
    return out


def oof_probabilities(calibrator, scores: Sequence[float], labels, groups) -> np.ndarray:
    """Xác suất ngoài-fold theo nhóm (GroupKFold như lúc fit, cùng phương pháp đã chọn) — để báo tỉ
    lệ vượt ngưỡng 'sau hiệu chỉnh' trên calib_fit mà không dùng chính mẫu đã fit."""
    from sklearn.model_selection import GroupKFold

    from vericlue_ml.common.calibration import _fit_parameters, _predict

    x = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=float)
    g = np.asarray(groups)
    out = np.empty_like(x)
    for train, valid in GroupKFold(n_splits=calibrator.cv_folds).split(x, y, g):
        params = _fit_parameters(calibrator.method, x[train], y[train])
        out[valid] = _predict(calibrator.method, params, x[valid], calibrator.epsilon)
    return out


def subset(rows: Sequence[Mapping[str, Any]], **where: Any) -> list[Mapping[str, Any]]:
    """Lọc dòng theo trường = giá trị (giá trị có thể là tuple các lựa chọn)."""
    out = []
    for row in rows:
        if all((row[k] in v) if isinstance(v, tuple) else row[k] == v for k, v in where.items()):
            out.append(row)
    return out


def sample_rows(items: Sequence[Any], n: int | None, seed: int) -> list[Any]:
    """Lấy ngẫu nhiên xác định ≤ n phần tử (None = tất cả), giữ thứ tự gốc."""
    if n is None or n >= len(items):
        return list(items)
    chosen = sorted(random.Random(seed).sample(range(len(items)), n))
    return [items[i] for i in chosen]


def eta_text(done: int, total: int, seconds: float) -> str:
    """'đã x/y, còn khoảng z phút' cho ô in tiến độ."""
    if done <= 0:
        return f"0/{total}"
    left = (total - done) * seconds / done
    return f"{done}/{total}, {seconds / 60:.1f} phút, còn khoảng {math.ceil(left / 60)} phút"
