"""Hiệu chỉnh trên calib_fit, tách người khi chọn Platt/isotonic (ROUT-01).

Nguồn thuật toán: scikit-learn GroupKFold, LogisticRegression, IsotonicRegression.
Không fit/chọn bằng calib_ltt hay test. Nhãn 1 = tấn công, score tăng = tấn công.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import quote

import numpy as np
from numpy.typing import ArrayLike, NDArray
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

from vericlue_ml.common.result import Module, ModuleResult, Status

EPSILON = 1e-4
MIN_ISOTONIC_CLASS = 100
MIN_RELATIVE_IMPROVEMENT = 0.02
PLATT_C = 1e6
PLATT_MAX_ITER = 2000
PLATT_TOL = 1e-8
REQUIRED_MODULES = frozenset(
    {Module.FACE_PAD, Module.FACE_DEEPFAKE, Module.VOICE_SPOOF, Module.LIPSYNC}
)
FloatArray = NDArray[np.float64]


class CalibrationError(ValueError):
    """Không được dùng điểm thô thay cho calibrator thiếu/hỏng/sai phiên bản."""


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


def _vector(values: ArrayLike, name: str) -> FloatArray:
    result = np.asarray(values, dtype=float)
    if result.ndim != 1 or not result.size or not np.isfinite(result).all():
        raise CalibrationError(f"{name} phải là vector không rỗng, hữu hạn.")
    return result


def _pairs(labels: ArrayLike, probabilities: ArrayLike) -> tuple[FloatArray, FloatArray]:
    y, p = _vector(labels, "labels"), _vector(probabilities, "probabilities")
    if y.shape != p.shape or not np.isin(y, [0, 1]).all():
        raise CalibrationError("Nhãn phải là 0/1 và cùng chiều với xác suất.")
    if np.any((p < 0) | (p > 1)):
        raise CalibrationError("Xác suất phải nằm trong [0, 1].")
    return y, p


class ReliabilityBin(_Record):
    lower: float
    upper: float
    count: int
    mean_probability: float | None
    attack_rate: float | None


def reliability_table(
    labels: ArrayLike, probabilities: ArrayLike, *, n_bins: int = 10
) -> list[ReliabilityBin]:
    """Bin đều [lower, upper); bin cuối gồm 1, giữ bin rỗng với giá trị None."""
    y, p = _pairs(labels, probabilities)
    if isinstance(n_bins, bool) or not isinstance(n_bins, int) or n_bins < 1:
        raise CalibrationError("n_bins phải là số nguyên dương.")
    indices = np.minimum((p * n_bins).astype(int), n_bins - 1)
    rows = []
    for i in range(n_bins):
        mask = indices == i
        count = int(mask.sum())
        rows.append(
            ReliabilityBin(
                lower=i / n_bins,
                upper=(i + 1) / n_bins,
                count=count,
                mean_probability=float(p[mask].mean()) if count else None,
                attack_rate=float(y[mask].mean()) if count else None,
            )
        )
    return rows


def ece(labels: ArrayLike, probabilities: ArrayLike, *, n_bins: int = 10) -> float:
    """ECE nhị phân: trung bình có trọng số |P(tấn công) - tỷ lệ tấn công|."""
    rows = reliability_table(labels, probabilities, n_bins=n_bins)
    total = sum(row.count for row in rows)
    return (
        sum(
            row.count * abs(row.mean_probability - row.attack_rate)
            for row in rows
            if row.count and row.mean_probability is not None and row.attack_rate is not None
        )
        / total
    )


def brier_score(labels: ArrayLike, probabilities: ArrayLike) -> float:
    """Brier nhị phân, không chia thêm cho hai."""
    y, p = _pairs(labels, probabilities)
    return float(np.mean((p - y) ** 2))


def log_loss(labels: ArrayLike, probabilities: ArrayLike, *, epsilon: float = EPSILON) -> float:
    """Log-loss nhị phân với cắt xác suất hữu hạn."""
    y, p = _pairs(labels, probabilities)
    if not 0 < epsilon < 0.5:
        raise CalibrationError("epsilon phải nằm trong (0, 0.5).")
    p = np.clip(p, epsilon, 1 - epsilon)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log1p(-p)))


class CalibrationMetrics(_Record):
    log_loss: float = Field(ge=0)
    ece: float = Field(ge=0, le=1)
    brier: float = Field(ge=0, le=1)


def _metrics(y: FloatArray, p: FloatArray, epsilon: float) -> CalibrationMetrics:
    return CalibrationMetrics(
        log_loss=log_loss(y, p, epsilon=epsilon), ece=ece(y, p), brier=brier_score(y, p)
    )


class CalibFit(_Record):
    """Dữ liệu một module/phiên bản; caller chịu trách nhiệm chọn đúng calib_fit."""

    scores: list[float]
    labels: list[int]
    subject_ids: list[str]
    dataset: str = Field(min_length=1)
    split: Literal["calib_fit"] = "calib_fit"


class Parameters(_Record):
    slope: float | None = None
    intercept: float | None = None
    x: list[float] = Field(default_factory=list)
    y: list[float] = Field(default_factory=list)


class Calibrator(_Record):
    """Artifact JSON, tham số thuần số; không pickle hay tải trọng số mô hình."""

    module: Module
    model_version: str = Field(min_length=1)
    method: Literal["platt", "isotonic"]
    parameters: Parameters
    epsilon: Literal[0.0001] = EPSILON
    n_pos: int = Field(gt=0)
    n_neg: int = Field(gt=0)
    before: CalibrationMetrics
    after: CalibrationMetrics
    before_reliability: list[ReliabilityBin]
    after_reliability: list[ReliabilityBin]
    date: datetime
    commit: str = Field(min_length=1)
    dataset: str = Field(min_length=1)
    split: Literal["calib_fit"] = "calib_fit"
    cv_folds: int = Field(ge=2)
    cv_log_loss: dict[Literal["platt", "isotonic"], float]
    metrics_scope: Literal["group_oof"] = "group_oof"
    baseline: Literal["clipped_raw_score"] = "clipped_raw_score"

    @model_validator(mode="after")
    def validate_parameters(self) -> Calibrator:
        p = self.parameters
        if self.method == "platt":
            if p.slope is None or p.intercept is None or p.x or p.y or p.slope < 0:
                raise ValueError("Tham số Platt không hợp lệ hoặc ngược chiều.")
        elif (
            p.slope is not None
            or p.intercept is not None
            or not p.x
            or len(p.x) != len(p.y)
            or np.any(np.diff(p.x) <= 0)
            or np.any(np.diff(p.y) < 0)
            or np.any((np.asarray(p.y) < 0) | (np.asarray(p.y) > 1))
        ):
            raise ValueError("Tham số isotonic không hợp lệ.")
        if "platt" not in self.cv_log_loss or any(v < 0 for v in self.cv_log_loss.values()):
            raise ValueError("Thiếu/sai log-loss kiểm định chéo.")
        if self.method == "isotonic" and not _choose_isotonic(
            self.n_pos, self.n_neg, self.cv_log_loss
        ):
            raise ValueError("Isotonic không đạt điều kiện chọn.")
        return self

    @property
    def prior_attack(self) -> float:
        """Tiền nghiệm π trên calib_fit cho FOR-04; không phải tỷ lệ ngoài thực tế."""
        return self.n_pos / (self.n_pos + self.n_neg)

    def predict(self, scores: ArrayLike) -> FloatArray:
        """P(tấn công), luôn được cắt theo epsilon của artifact."""
        return _predict(self.method, self.parameters, _vector(scores, "scores"), self.epsilon)


def _fit_parameters(method: str, x: FloatArray, y: FloatArray) -> Parameters:
    if method == "isotonic":
        model = IsotonicRegression(increasing=True, out_of_bounds="clip").fit(x, y)
        return Parameters(x=model.X_thresholds_.tolist(), y=model.y_thresholds_.tolist())
    scaler = StandardScaler().fit(x.reshape(-1, 1))
    model = LogisticRegression(C=PLATT_C, solver="lbfgs", max_iter=PLATT_MAX_ITER, tol=PLATT_TOL)
    model.fit(scaler.transform(x.reshape(-1, 1)), y)
    slope = float(model.coef_[0, 0] / scaler.scale_[0])
    return Parameters(slope=slope, intercept=float(model.intercept_[0] - slope * scaler.mean_[0]))


def _predict(method: str, p: Parameters, scores: FloatArray, epsilon: float) -> FloatArray:
    if method == "isotonic":
        probabilities = np.interp(scores, p.x, p.y)
    else:
        z = p.slope * scores + p.intercept
        # Stable sigmoid without overflow for extreme raw scores.
        probabilities = np.exp(-np.logaddexp(0, -z))
    return np.clip(probabilities, epsilon, 1 - epsilon)


def _choose_isotonic(n_pos: int, n_neg: int, losses: dict[str, float]) -> bool:
    return (
        min(n_pos, n_neg) >= MIN_ISOTONIC_CLASS
        and "isotonic" in losses
        and losses["isotonic"] <= losses["platt"] * (1 - MIN_RELATIVE_IMPROVEMENT)
    )


def fit(
    calib_fit: CalibFit,
    *,
    module: str | Module,
    model_version: str,
    commit: str,
    n_splits: int = 5,
    epsilon: float = EPSILON,
) -> Calibrator:
    """Chọn bằng GroupKFold OOF log-loss, rồi fit phương pháp thắng trên toàn calib_fit."""
    x = _vector(calib_fit.scores, "scores")
    y, _ = _pairs(calib_fit.labels, np.clip(x, 0, 1))
    groups = np.asarray(calib_fit.subject_ids)
    if groups.shape != x.shape or any(not s.strip() for s in calib_fit.subject_ids):
        raise CalibrationError("subject_ids phải không rỗng và cùng chiều với scores.")
    if np.unique(y).size != 2:
        raise CalibrationError("calib_fit phải có cả hai lớp.")
    if not isinstance(n_splits, int) or isinstance(n_splits, bool) or n_splits < 2:
        raise CalibrationError("GroupKFold cần ít nhất hai phần.")
    if epsilon != EPSILON:
        raise CalibrationError("Fit phải dùng epsilon=1e-4.")
    if roc_auc_score(y, x) < 0.5:
        raise CalibrationError("AUC < 0.5: nghi score ngược chiều tấn công.")
    folds = min(n_splits, np.unique(groups).size)
    if folds < 2:
        raise CalibrationError("GroupKFold cần ít nhất hai subject.")
    splits = list(GroupKFold(n_splits=folds).split(x, y, groups))
    if any(np.unique(y[train]).size != 2 for train, _ in splits):
        raise CalibrationError("Một fold fit thiếu lớp; cần thêm subject hoặc đổi n_splits.")
    n_pos, n_neg = int(y.sum()), int((1 - y).sum())
    methods = ["platt", "isotonic"] if min(n_pos, n_neg) >= MIN_ISOTONIC_CLASS else ["platt"]
    losses: dict[str, float] = {}
    predictions: dict[str, FloatArray] = {}
    for method in methods:
        oof = np.empty_like(x)
        for train, valid in splits:
            parameters = _fit_parameters(method, x[train], y[train])
            oof[valid] = _predict(method, parameters, x[valid], epsilon)
        predictions[method] = oof
        losses[method] = log_loss(y, oof, epsilon=epsilon)
    method = "isotonic" if _choose_isotonic(n_pos, n_neg, losses) else "platt"
    return Calibrator(
        module=Module(module),
        model_version=model_version,
        method=method,
        parameters=_fit_parameters(method, x, y),
        epsilon=epsilon,
        n_pos=n_pos,
        n_neg=n_neg,
        before=_metrics(y, np.clip(x, epsilon, 1 - epsilon), epsilon),
        after=_metrics(y, predictions[method], epsilon),
        before_reliability=reliability_table(y, np.clip(x, epsilon, 1 - epsilon)),
        after_reliability=reliability_table(y, predictions[method]),
        date=datetime.now(UTC),
        commit=commit,
        dataset=calib_fit.dataset,
        cv_folds=folds,
        cv_log_loss=losses,
    )


def reliability_markdown(rows: Sequence[ReliabilityBin]) -> str:
    """Bảng reliability Markdown từ dữ liệu bin, không tự tạo số liệu."""
    lines = ["| Bin | Số mẫu | Xác suất trung bình | Tỷ lệ tấn công |", "|---|---:|---:|---:|"]
    for row in rows:
        mean = "—" if row.mean_probability is None else f"{row.mean_probability:.6f}"
        rate = "—" if row.attack_rate is None else f"{row.attack_rate:.6f}"
        closing = "]" if row.upper == 1 else ")"
        lines.append(
            f"| [{row.lower:.3f}, {row.upper:.3f}{closing} | {row.count} | {mean} | {rate} |"
        )
    return "\n".join(lines) + "\n"


def plot_reliability(rows: Sequence[ReliabilityBin], destination: Path) -> None:
    """Xuất PNG khi đã cài extra eval; matplotlib chỉ được import lúc gọi."""
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise CalibrationError("Xuất PNG cần cài extra eval của vericlue-ml.") from exc
    populated = [r for r in rows if r.count]
    fig, ax = plt.subplots()
    try:
        ax.plot([0, 1], [0, 1], linestyle="--", color="gray")
        ax.plot([r.mean_probability for r in populated], [r.attack_rate for r in populated], "o-")
        ax.set(
            xlim=(0, 1),
            ylim=(0, 1),
            xlabel="Xác suất tấn công trung bình",
            ylabel="Tỷ lệ tấn công",
            title="Reliability",
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(destination, format="png", bbox_inches="tight")
    finally:
        plt.close(fig)


class CalibrationStore:
    """Nạp một lần theo module/version; root truyền vào hoặc CALIBRATORS_DIR."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (
            root
            if root is not None
            else Path(
                os.getenv(
                    "CALIBRATORS_DIR",
                    str(Path(__file__).resolve().parents[3] / "configs" / "calibrators"),
                )
            )
        )
        self._cache: dict[tuple[Module, str], Calibrator] = {}

    def path(self, module: str | Module, model_version: str) -> Path:
        """Đường dẫn portable: percent-encode ký tự không hợp lệ, không cho traversal."""
        if not model_version.strip() or model_version in {".", ".."}:
            raise CalibrationError("model_version không hợp lệ.")
        return self.root / Module(module).value / f"{quote(model_version, safe='@-_.')}.json"

    def save(self, calibrator: Calibrator) -> Path:
        """Lưu JSON đã kiểm tra, rồi cập nhật cache của store này."""
        calibrator = Calibrator.model_validate_json(calibrator.model_dump_json())
        path = self.path(calibrator.module, calibrator.model_version)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(calibrator.model_dump_json(indent=2) + "\n", encoding="utf-8")
        self._cache[(calibrator.module, calibrator.model_version)] = calibrator
        return path

    def load(self, module: str | Module, model_version: str) -> Calibrator:
        """Thiếu/hỏng/sai phiên bản => CalibrationError, tuyệt đối không fallback."""
        key = (Module(module), model_version)
        if key not in self._cache:
            path = self.path(*key)
            try:
                artifact = Calibrator.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise CalibrationError(
                    f"Không nạp được calibrator {key[0].value}/{model_version}: {path}"
                ) from exc
            if (artifact.module, artifact.model_version) != key:
                raise CalibrationError(f"Calibrator sai module/model_version: {path}")
            self._cache[key] = artifact
        return self._cache[key]

    def apply(self, result: ModuleResult) -> ModuleResult:
        """Caller bắt CalibrationError để trả status=error; không sửa result gốc."""
        if (
            result.model_version.startswith("mock@")
            or Module(result.module) not in REQUIRED_MODULES
        ):
            return result
        if result.status != Status.OK:
            # Do not manufacture usable probability from error/degraded/not_applicable.
            return result.model_copy(update={"prob_attack": None})
        calibrator = self.load(result.module, result.model_version)
        if result.score is None:
            raise CalibrationError(f"Thiếu score cho {result.module}/{result.model_version}.")
        probability = float(calibrator.predict([result.score])[0])
        return result.model_copy(update={"prob_attack": probability})
