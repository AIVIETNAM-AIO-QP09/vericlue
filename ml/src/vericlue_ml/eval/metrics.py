"""Chỉ số nhị phân: 1 = tấn công; probability >= threshold bị từ chối.

ROC mô tả không xuất ngưỡng. Nguồn: sklearn.metrics.roc_curve/roc_auc_score;
Clopper-Pearson dùng scipy.stats.binomtest(...).proportion_ci(method="exact").
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.stats import binomtest
from sklearn.metrics import roc_auc_score, roc_curve

from vericlue_ml.common.calibration import brier_score, ece

__all__ = [
    "apcer_by_attack",
    "auc",
    "bpcer",
    "brier_score",
    "clopper_pearson",
    "descriptive_bpcer_at_apcer",
    "ece",
    "eer",
]


def _vectors(labels: ArrayLike, probabilities: ArrayLike) -> tuple[NDArray, NDArray]:
    y, p = np.asarray(labels), np.asarray(probabilities, dtype=float)
    if y.ndim != 1 or p.ndim != 1 or y.shape != p.shape or not y.size:
        raise ValueError("Nhãn và xác suất phải là vector không rỗng, cùng chiều.")
    if not np.isin(y, [0, 1]).all() or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError("Nhãn phải là 0/1, xác suất hữu hạn trong [0,1].")
    return y, p


def _threshold(threshold: float) -> None:
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Ngưỡng xác suất phải nằm trong [0,1].")


def apcer_by_attack(
    labels: ArrayLike,
    probabilities: ArrayLike,
    attack_types: Sequence[str],
    threshold: float,
) -> dict[str, float]:
    """Tỷ lệ tấn công được chấp nhận theo từng attack_type; bỏ lớp thật khỏi mẫu số."""
    y, p = _vectors(labels, probabilities)
    _threshold(threshold)
    attacks = np.asarray(attack_types)
    if attacks.shape != y.shape or any(not isinstance(a, str) for a in attack_types):
        raise ValueError("attack_types phải là vector chuỗi cùng chiều.")
    if any(not str(a).strip() for a in attacks[y == 1]):
        raise ValueError("Mẫu tấn công phải có attack_type.")
    attacks = np.array([str(a).strip() for a in attacks])
    return {
        str(kind): float(np.mean(p[(y == 1) & (attacks == kind)] < threshold))
        for kind in sorted(set(attacks[y == 1]))
    }


def bpcer(labels: ArrayLike, probabilities: ArrayLike, threshold: float) -> float | None:
    """Tỷ lệ người thật bị từ chối; None khi không có mẫu thật."""
    y, p = _vectors(labels, probabilities)
    _threshold(threshold)
    return float(np.mean(p[y == 0] >= threshold)) if np.any(y == 0) else None


def auc(labels: ArrayLike, probabilities: ArrayLike) -> float | None:
    """ROC AUC mô tả; None khi thiếu một lớp."""
    y, p = _vectors(labels, probabilities)
    return float(roc_auc_score(y, p)) if np.unique(y).size == 2 else None


def eer(labels: ArrayLike, probabilities: ArrayLike) -> float | None:
    """EER nội suy tuyến tính trên ROC, chỉ trả chỉ số; không chọn/xuất ngưỡng."""
    y, p = _vectors(labels, probabilities)
    if np.unique(y).size < 2:
        return None
    fpr, tpr = roc_curve(y, p, drop_intermediate=False)[:2]
    difference = 1 - tpr - fpr
    right = int(np.flatnonzero(difference <= 0)[0])
    if difference[right] == 0:
        return float(fpr[right])
    left = right - 1
    fraction = difference[left] / (difference[left] - difference[right])
    return float(fpr[left] + fraction * (fpr[right] - fpr[left]))


def descriptive_bpcer_at_apcer(
    labels: ArrayLike,
    probabilities: ArrayLike,
    target: float = 0.05,
) -> float | None:
    """BPCER nội suy ở APCER gộp target trên ROC đánh giá; chỉ trả scalar.

    Nội suy là mô tả, có thể tương ứng trộn quyết định ở điểm đồng hạng, không
    phải ngưỡng triển khai. Không lưu hoặc trả bất cứ ngưỡng nào của đường cong.
    """
    y, p = _vectors(labels, probabilities)
    if not np.isfinite(target) or not 0 <= target <= 1:
        raise ValueError("target phải nằm trong [0,1].")
    if np.unique(y).size < 2:
        return None
    fpr, tpr = roc_curve(y, p, drop_intermediate=False)[:2]
    fnr = 1 - tpr
    exact = np.flatnonzero(np.isclose(fnr, target, rtol=0, atol=8 * np.finfo(float).eps))
    if exact.size:
        return float(fpr[exact].min())
    # Preserve every corner of the ROC; collapsing duplicate FNR before
    # interpolation would shortcut horizontal segments and understate BPCER.
    right = int(np.flatnonzero(fnr < target)[0])
    left = right - 1
    fraction = (fnr[left] - target) / (fnr[left] - fnr[right])
    return float(fpr[left] + fraction * (fpr[right] - fpr[left]))


def clopper_pearson(
    successes: int,
    total: int,
    confidence: float = 0.95,
) -> tuple[float, float] | None:
    """CI nhị thức exact hai phía; số dòng độc lập là giả định, total=0 => None."""
    if (
        isinstance(successes, bool)
        or isinstance(total, bool)
        or not isinstance(successes, (int, np.integer))
        or not isinstance(total, (int, np.integer))
        or not 0 <= successes <= total
        or not 0 < confidence < 1
    ):
        raise ValueError("Cần số đếm nguyên 0 <= successes <= total và confidence trong (0,1).")
    if total == 0:
        return None
    interval = binomtest(successes, total).proportion_ci(
        confidence_level=confidence, method="exact"
    )
    return float(interval.low), float(interval.high)
