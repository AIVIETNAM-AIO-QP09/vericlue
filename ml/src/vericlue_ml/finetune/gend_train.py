"""FACE-04 — hàm thuần cho tinh chỉnh GenD (chỉ LayerNorm + đầu tuyến tính, như bài báo GenD).

Notebook `ml/notebooks/finetune_gend.ipynb` nhúng nguyên văn file này cùng `face/gend.py`, `face/pad.py`,
`face/frames.py`, nên khung, dò mặt, căn mặt và chuẩn hóa GIỐNG HỆT hệ thống đang chạy.

Nguồn (chép lại, giữ giấy phép — xem `third_party/README.md`):
- yermandy/GenD (MIT, Copyright (c) 2025 Andy), commit 387a42266dd385fbe8f7626c5d3aa03eea3bfaab:
  `src/exp/wacv_rebuttal.py` (lớp được mở: `pre_layrnorm`, `layer_norm1`, `layer_norm2`,
  `post_layernorm`; loss CE 1,0 + uniformity 0,5 + alignment 0,1), `src/losses/unifalign.py`
  (`alignment`, `uniformity`), `src/config.py` (AdamW, cosine, weight decay 0).

Luật: tập test KHÔNG được đọc khi dạy hay chọn checkpoint (`rows_for`, `assert_no_test`).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

# Tên lớp được mở khóa (đúng `unfreeze_layers` của GenD cho CLIP).
TRAINABLE_LAYER_NAMES = ("pre_layrnorm", "layer_norm1", "layer_norm2", "post_layernorm")
GEND_VISION_PREFIX = "feature_extractor.vision_model."
HF_VISION_PREFIX = "vision_model."
HEAD_WEIGHT_KEY = "model.linear.weight"
HEAD_BIAS_KEY = "model.linear.bias"
LOSS_WEIGHTS = {"ce": 1.0, "uniformity": 0.5, "alignment": 0.1}
TEST_CONFIRMATION = "TOI-LA-TRUONG-NHOM-CHAY-TEST-MOT-LAN"


# ── chặn tập test ────────────────────────────────────────────────────────────────────────
class TestSplitAccessError(RuntimeError):
    """Có mã định đọc tập test khi dạy hoặc chọn checkpoint."""


def assert_no_test(rows: Iterable[dict[str, Any]]) -> None:
    """Ném lỗi nếu có dòng nào thuộc tập test (theo cột `split` hoặc đường dẫn `/test/`)."""
    for row in rows:
        path = str(row.get("path", "")).replace("\\", "/")
        if row.get("split") == "test" or "/test/" in f"/{path}":
            raise TestSplitAccessError(
                f"Không được dùng tập test khi dạy/chọn mô hình: {row.get('sample_id') or path}"
            )


def rows_for(rows: Iterable[dict[str, Any]], splits: Sequence[str]) -> list[dict[str, Any]]:
    """Lọc manifest theo tập; xin tập test ở đây là lỗi (test chỉ đọc qua hàm test riêng)."""
    if "test" in splits:
        raise TestSplitAccessError("rows_for không bao giờ trả tập test.")
    chosen = [r for r in rows if r.get("split") in splits]
    assert_no_test(chosen)
    return chosen


def check_test_unlocked(run_test: bool, confirmation: str) -> None:
    """Hàm test chỉ chạy khi trưởng nhóm bật cờ VÀ gõ đúng câu xác nhận."""
    if not run_test or confirmation != TEST_CONFIRMATION:
        raise TestSplitAccessError(
            "Hàm test đang TẮT. Chỉ trưởng nhóm bật RUN_TEST=True và gõ đúng câu xác nhận, "
            "một lần duy nhất sau khi đã chốt mô hình."
        )


# ── tham số được dạy và xuất trọng số ────────────────────────────────────────────────────
def is_trainable(name: str) -> bool:
    """Tham số của CLIPVisionModel có thuộc LayerNorm được mở không."""
    return any(part in TRAINABLE_LAYER_NAMES for part in name.split("."))


def to_gend_key(name: str) -> str:
    """`vision_model.x` (HF CLIPVisionModel) → `feature_extractor.vision_model.x` (checkpoint GenD)."""
    if not name.startswith(HF_VISION_PREFIX):
        raise ValueError(f"Tên tham số lạ: {name}")
    return GEND_VISION_PREFIX + name[len(HF_VISION_PREFIX) :]


def delta_state(vision_state: dict[str, Any], head_weight, head_bias) -> dict[str, Any]:
    """Chỉ phần được dạy (LayerNorm + đầu), đặt tên đúng như checkpoint GenD để ghép lại được."""
    out = {to_gend_key(k): v for k, v in vision_state.items() if is_trainable(k)}
    if not out:
        raise ValueError("Không tìm thấy tham số LayerNorm nào.")
    out[HEAD_WEIGHT_KEY] = head_weight
    out[HEAD_BIAS_KEY] = head_bias
    return out


def merge_delta(base: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    """Ghép delta vào checkpoint GenD gốc → state đầy đủ mà `face/gend.py` nạp được nguyên trạng.
    Chỉ cho thay LayerNorm và đầu tuyến tính; khóa/kích thước phải khớp."""
    merged = dict(base)
    for key, value in delta.items():
        allowed = key in (HEAD_WEIGHT_KEY, HEAD_BIAS_KEY) or (
            key.startswith(GEND_VISION_PREFIX) and is_trainable(key[len("feature_extractor.") :])
        )
        if not allowed:
            raise ValueError(f"Delta chứa tham số không được phép thay: {key}")
        if key not in base:
            raise ValueError(f"Checkpoint gốc không có {key}")
        if tuple(base[key].shape) != tuple(value.shape):
            raise ValueError(f"Kích thước {key} không khớp.")
        merged[key] = value
    return merged


# ── tăng cường (cho CẢ HAI lớp) ──────────────────────────────────────────────────────────
@dataclass(frozen=True)
class AugConfig:
    p_flip: float = 0.5
    p_downscale: float = 0.3
    downscale_side: tuple[int, int] = (64, 224)
    p_blur: float = 0.2
    blur_sigma: tuple[float, float] = (0.1, 2.0)
    p_jpeg: float = 0.5
    jpeg_quality: tuple[int, int] = (30, 95)
    crf_range: tuple[int, int] = (23, 40)
    crf_side: tuple[int, int] = (160, 320)


def augment_crop(crop_bgr: np.ndarray, rng: np.random.Generator, cfg: AugConfig) -> np.ndarray:
    """Tăng cường trên mặt đã căn (trước `to_tensor`): lật, thu nhỏ rồi để CLIP phóng lại, mờ, JPEG."""
    import cv2

    image = np.ascontiguousarray(crop_bgr)
    if rng.random() < cfg.p_flip:
        image = np.ascontiguousarray(image[:, ::-1])
    if rng.random() < cfg.p_downscale:
        side = int(rng.integers(cfg.downscale_side[0], cfg.downscale_side[1] + 1))
        if side < max(image.shape[:2]):
            image = cv2.resize(image, (side, side), interpolation=cv2.INTER_AREA)
    if rng.random() < cfg.p_blur:
        sigma = float(rng.uniform(*cfg.blur_sigma))
        image = cv2.GaussianBlur(image, (0, 0), sigmaX=sigma)
    if rng.random() < cfg.p_jpeg:
        quality = int(rng.integers(cfg.jpeg_quality[0], cfg.jpeg_quality[1] + 1))
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if ok:
            image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    return image


def crf_variant_cmd(
    ffmpeg: str, src: str | Path, dst: str | Path, *, crf: int, side: int, fps: int = 25
) -> list[str]:
    """Tăng cường mức video: mã hóa lại H.264 với CRF và cỡ khung cho trước (cả hai lớp)."""
    return [
        ffmpeg,
        "-nostdin",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-an",
        "-map_metadata",
        "-1",
        "-vf",
        f"scale={side}:{side}:flags=bicubic,fps={fps},format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        str(int(crf)),
        str(dst),
    ]


def pad_border(image: np.ndarray, ratio: float = 0.5, value: int = 128) -> np.ndarray:
    """Thêm viền xám mỗi phía (ảnh đã cắt sát mặt thì SCRFD cần viền mới thấy mặt)."""
    import cv2

    height, width = image.shape[:2]
    top, side = int(round(height * ratio)), int(round(width * ratio))
    return cv2.copyMakeBorder(
        image, top, top, side, side, cv2.BORDER_CONSTANT, value=(value, value, value)
    )


# ── lấy mặt đúng như face/gend.py ────────────────────────────────────────────────────────
def aligned_faces(
    detector,
    *,
    video: Path | None = None,
    images: Sequence[Path] | None = None,
    count: int | None = None,
) -> tuple[int, list[tuple[int, np.ndarray]]]:
    """(số khung yêu cầu, [(chỉ số khung, mặt BGR đã căn)]) theo đúng `FaceDeepfakeDetector`:
    `sample_video`/`sample_images` → mặt lớn nhất (SCRFD, chia 128, đảo RGB) → `align_face` (1,3)."""
    from vericlue_ml.face.frames import sample_images, sample_video
    from vericlue_ml.face.gend import EKYC_FRAMES, GendError, align_face

    count = count or EKYC_FRAMES
    if video is not None:
        requested, frames = sample_video(Path(video), count)
    elif images:
        requested, frames = sample_images(list(images), count)
    else:
        raise ValueError("Cần video hoặc ảnh.")
    out: list[tuple[int, np.ndarray]] = []
    for index, frame in frames:
        face = detector._largest_face(frame)
        if face is None:
            continue
        try:
            out.append((index, align_face(frame, np.array(face.landmarks))))
        except GendError:
            continue
    return requested, out


# ── điểm và chỉ số theo clip ─────────────────────────────────────────────────────────────
def clip_score(p_fake: Sequence[float]) -> float:
    """Điểm clip đúng như `face/gend.py`: max(mean, top25_mean)."""
    from vericlue_ml.face.gend import video_scores

    mean, top = video_scores(list(p_fake))
    return max(mean, top)


def clip_metrics(labels: Sequence[int], scores: Sequence[float]) -> dict[str, Any]:
    """AUC và EER theo clip (nhãn 1 = giả) bằng `vericlue_ml.eval.metrics`."""
    from vericlue_ml.eval.metrics import auc, eer

    y = np.asarray(labels, dtype=int)
    return {
        "auc": auc(y, scores),
        "eer": eer(y, scores),
        "n_real": int((y == 0).sum()),
        "n_fake": int((y == 1).sum()),
    }


def threshold_at_eer(labels: Sequence[int], scores: Sequence[float]) -> float | None:
    """Ngưỡng tại điểm EER trên calib (chỉ để đo chặn nhầm FAS-VN, KHÔNG phải ngưỡng sản phẩm)."""
    from sklearn.metrics import roc_curve

    y = np.asarray(labels, dtype=int)
    if np.unique(y).size < 2:
        return None
    fpr, tpr, thresholds = roc_curve(y, np.asarray(scores, dtype=float))
    index = int(np.nanargmin(np.abs((1 - tpr) - fpr)))
    return float(min(thresholds[index], 1.0))


def false_block_rate(live_scores: Sequence[float], threshold: float | None) -> float | None:
    """Tỉ lệ ảnh người thật (FAS-VN live) bị coi là giả ở ngưỡng cho trước."""
    if threshold is None or len(live_scores) == 0:
        return None
    return float(np.mean(np.asarray(live_scores, dtype=float) >= threshold))


def select_checkpoint(history: Sequence[dict[str, Any]], max_fbr_increase: float = 0.05) -> dict:
    """Chọn checkpoint CHỈ trên calib: AUC calib cao nhất trong các checkpoint không làm tỉ lệ chặn
    nhầm FAS-VN live tăng quá `max_fbr_increase` so với GenD gốc (epoch 0). Hòa → EER thấp hơn
    → epoch sớm hơn. GenD gốc cũng là ứng viên (tinh chỉnh không tốt hơn thì giữ gốc)."""
    if not history:
        raise ValueError("Chưa có checkpoint nào.")
    base = next((h for h in history if h["epoch"] == 0), history[0])
    base_fbr = base.get("fasvn_fbr")

    def allowed(entry: dict) -> bool:
        fbr = entry.get("fasvn_fbr")
        return base_fbr is None or fbr is None or fbr <= base_fbr + max_fbr_increase

    pool = [h for h in history if allowed(h) and h.get("calib_auc") is not None] or [
        h for h in history if h.get("calib_auc") is not None
    ]
    if not pool:
        return base
    return sorted(
        pool,
        key=lambda h: (-h["calib_auc"], h.get("calib_eer") or 1.0, h["epoch"]),
    )[0]


# ── loss của GenD (torch, nạp lười) ──────────────────────────────────────────────────────
def alignment_loss(embeddings, labels, alpha: float = 2.0):
    """Alignment theo nhãn trên embedding đã chuẩn hóa L2 (GenD `unifalign.alignment`)."""
    import torch

    if embeddings.size(0) < 2:
        return torch.tensor(0.0, device=embeddings.device)
    mask = (labels[:, None] == labels[None, :]).triu(diagonal=1)
    pairs = torch.nonzero(mask, as_tuple=False)
    if pairs.numel() == 0:
        return torch.tensor(0.0, device=embeddings.device)
    x, y = embeddings[pairs[:, 0]], embeddings[pairs[:, 1]]
    return (x - y).norm(p=2, dim=1).pow(alpha).mean()


def uniformity_loss(embeddings, t: float = 2.0, clip_value: float = 1e-6):
    """Uniformity (GenD `unifalign.uniformity`)."""
    import torch

    if embeddings.size(0) < 2:
        return torch.tensor(0.0, device=embeddings.device)
    return torch.pdist(embeddings, p=2).pow(2).mul(-t).exp().mean().clamp(min=clip_value).log()
