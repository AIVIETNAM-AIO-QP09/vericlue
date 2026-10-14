"""Đọc predictions, bootstrap theo người và báo cáo Markdown truy vết được (EVAL-01)."""

from __future__ import annotations

import argparse
import csv
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vericlue_ml.common.calibration import brier_score, ece
from vericlue_ml.common.result import Module, Status
from vericlue_ml.eval import metrics

CORE_COLUMNS = frozenset(
    {
        "sample_id",
        "subject_id",
        "label",
        "attack_type",
        "prob_attack",
        "status",
        "module",
        "model_version",
    }
)
DEFAULT_SEED = 42
DEFAULT_BOOTSTRAP = 2000
MIN_SUBJECTS = 10
TARGET_APCER = 0.05


class EvaluationError(ValueError):
    """Dữ liệu/nguồn gốc không hợp lệ: không im lặng bỏ mẫu hoặc fallback."""


class Prediction(BaseModel):
    """Một kết quả; probability bắt buộc cho status ok, không fit từ score trong eval."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    sample_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    label: Literal[0, 1]
    attack_type: str
    prob_attack: float | None = Field(ge=0, le=1)
    status: Status
    module: Module
    model_version: str = Field(min_length=1)
    path: str | None = None
    source: str | None = None
    region: str | None = None
    score: float | None = None
    compression: str | None = None

    @field_validator("sample_id", "subject_id", "model_version")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Định danh không được trống.")
        return value.strip()

    @field_validator("attack_type")
    @classmethod
    def canonical_attack_type(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def usable_probability(self) -> Prediction:
        if self.status == Status.OK and self.prob_attack is None:
            raise ValueError("status=ok cần prob_attack đã hiệu chỉnh; không dùng score thay thế.")
        if self.label == 1 and not self.attack_type.strip():
            raise ValueError("Mẫu tấn công cần attack_type.")
        if self.label == 1 and self.attack_type == "bona_fide":
            raise ValueError("attack_type bona_fide dành cho nhãn 0.")
        if self.label == 0 and self.attack_type not in {"", "bona_fide"}:
            raise ValueError("Nhãn 0 chỉ chấp nhận attack_type rỗng hoặc bona_fide.")
        return self


class ReferenceThreshold(BaseModel):
    """Ngưỡng benchmark khóa từ calib_fit, không phải ngưỡng vận hành LTT."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    threshold: float = Field(ge=0, le=1)
    module: Module
    model_version: str = Field(min_length=1)
    commit: str = Field(min_length=1)
    dataset: str = Field(min_length=1)
    subject_ids: tuple[str, ...]
    attack_types: tuple[str, ...]
    split: Literal["calib_fit"] = "calib_fit"
    target_apcer: Literal[0.05] = TARGET_APCER

    @field_validator("subject_ids")
    @classmethod
    def canonical_subjects(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        # Match Prediction normalization before checking split independence.
        return tuple(sorted({value.strip() for value in values}))

    @field_validator("attack_types")
    @classmethod
    def canonical_attack_types(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        result = tuple(sorted({value.strip() for value in values}))
        if not result or any(not value or value == "bona_fide" for value in result):
            raise ValueError("Reference cần danh sách attack_type tấn công không rỗng.")
        return result

    @model_validator(mode="after")
    def provenance(self) -> ReferenceThreshold:
        if not self.subject_ids or any(not s.strip() for s in self.subject_ids):
            raise ValueError("Ngưỡng tham chiếu cần subject_ids của calib_fit.")
        if not self.commit.strip() or not self.dataset.strip() or not self.model_version.strip():
            raise ValueError("Ngưỡng tham chiếu thiếu nguồn gốc.")
        return self


@dataclass(frozen=True)
class Estimate:
    value: float | None
    ci_low: float | None
    ci_high: float | None
    n_valid: int
    cp_low: float | None = None
    cp_high: float | None = None


@dataclass(frozen=True)
class ExclusionGroup:
    group: str
    total: int
    excluded: int

    @property
    def rate(self) -> float:
        """Tỷ lệ loại trên tất cả dòng đầu vào của nhóm, không trên dòng còn lại."""
        return self.excluded / self.total if self.total else 0.0


@dataclass(frozen=True)
class GroupReport:
    module: str
    model_version: str
    n_total: int
    n_used: int
    n_subjects: int
    excluded: list[ExclusionGroup]
    estimates: dict[str, Estimate]
    threshold: float
    reference: ReferenceThreshold | None
    warnings: list[str]
    threshold_source: Literal["default", "caller"] = "caller"


@dataclass(frozen=True)
class EvaluationReport:
    commit: str
    dataset: str
    seed: int
    n_bootstrap: int
    groups: list[GroupReport]


def git_revision(repo: Path | None = None) -> str:
    """Lấy HEAD thật và hậu tố -dirty cho thay đổi tracked/untracked, không nhận hash tự nhập."""
    root = repo if repo is not None else Path(__file__).resolve().parents[4]
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise EvaluationError("Không lấy được commit từ Git; truyền repo hợp lệ.") from exc
    return revision + ("-dirty" if status else "")


def read_predictions(path: Path) -> list[Prediction]:
    """CSV có đủ core columns; chỉ đọc trường số, không đọc ảnh/âm thanh từ path."""
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        if len(set(headers)) != len(headers) or not set(headers) >= CORE_COLUMNS:
            raise EvaluationError(
                f"CSV thiếu cột bắt buộc hoặc trùng header: {sorted(CORE_COLUMNS)}"
            )
        for line, raw in enumerate(reader, 2):
            try:
                if None in raw or any(value is None for value in raw.values()):
                    raise ValueError("Số cột không khớp header.")
                values = dict(raw)
                values["label"] = int(raw["label"])
                values["prob_attack"] = (
                    float(raw["prob_attack"]) if raw["prob_attack"].strip() else None
                )
                if "score" in values:
                    values["score"] = float(raw["score"]) if raw["score"].strip() else None
                rows.append(Prediction.model_validate(values))
            except ValueError as exc:
                raise EvaluationError(f"CSV dòng {line} không hợp lệ: {exc}") from exc
    if not rows:
        raise EvaluationError("CSV không có mẫu.")
    return _validate_rows(rows)


def _validate_rows(rows: list[Prediction]) -> list[Prediction]:
    if not rows:
        raise EvaluationError("Không có mẫu đánh giá.")
    seen = set()
    normalized = []
    for row in rows:
        if not isinstance(row, Prediction):
            raise EvaluationError("Đầu vào phải là các Prediction đã kiểm tra.")
        # Revalidate even if a caller used model_copy(update=...) without validation.
        row = Prediction.model_validate(row.model_dump())
        key = (row.sample_id, row.module, row.model_version, row.compression)
        if key in seen:
            raise EvaluationError(
                f"Trùng sample_id trong cùng module/version/compression: {row.sample_id}"
            )
        seen.add(key)
        normalized.append(row)
    return normalized


def select_reference_threshold(
    calib_fit: list[Prediction],
    *,
    dataset: str,
    repo: Path | None = None,
    split: str = "calib_fit",
) -> ReferenceThreshold:
    """Ngưỡng lớn nhất thỏa APCER max <=5% trên calib_fit; không chia tie."""
    if split != "calib_fit":
        raise EvaluationError(
            "Chỉ được chọn ngưỡng tham chiếu trên calib_fit, không calib_ltt/test."
        )
    calib_fit = _validate_rows(calib_fit)
    identities = {(r.module, r.model_version) for r in calib_fit}
    if len(identities) != 1 or any(r.status != Status.OK for r in calib_fit):
        raise EvaluationError("calib_fit phải cùng module/model_version và tất cả status=ok.")
    y = np.array([r.label for r in calib_fit])
    p = np.array([r.prob_attack for r in calib_fit], dtype=float)
    attacks = np.array([r.attack_type for r in calib_fit])
    if np.unique(y).size != 2:
        raise EvaluationError("calib_fit cần cả hai lớp.")
    limits = []
    for kind in sorted(set(attacks[y == 1])):
        scores = np.sort(p[(y == 1) & (attacks == kind)])
        allowed = int(np.floor(TARGET_APCER * scores.size))
        limits.append(float(scores[allowed]))
    threshold = min(limits)
    module, version = next(iter(identities))
    return ReferenceThreshold(
        threshold=threshold,
        module=module,
        model_version=version,
        dataset=dataset,
        commit=git_revision(repo),
        subject_ids=tuple(sorted({r.subject_id for r in calib_fit})),
        attack_types=tuple(sorted(set(attacks[y == 1]))),
    )


def _points(
    y: np.ndarray,
    p: np.ndarray,
    attack_types: np.ndarray,
    threshold: float,
    reference: ReferenceThreshold | None,
) -> dict[str, float | None]:
    if not y.size:
        return dict.fromkeys(
            [
                "apcer_max",
                "bpcer",
                "auc",
                "eer",
                "ece",
                "brier",
                "bpcer_at_apcer5_locked",
                "apcer_max_at_reference",
                "bpcer_at_apcer5_descriptive",
            ]
        )
    by_attack = metrics.apcer_by_attack(y, p, attack_types, threshold)
    values = {f"apcer:{name}": rate for name, rate in by_attack.items()}
    values.update(
        apcer_max=max(by_attack.values()) if by_attack else None,
        bpcer=metrics.bpcer(y, p, threshold),
        auc=metrics.auc(y, p),
        eer=metrics.eer(y, p),
        ece=ece(y, p),
        brier=brier_score(y, p),
        bpcer_at_apcer5_descriptive=metrics.descriptive_bpcer_at_apcer(y, p),
        bpcer_at_apcer5_locked=None,
        apcer_max_at_reference=None,
    )
    if reference is not None:
        values["bpcer_at_apcer5_locked"] = metrics.bpcer(y, p, reference.threshold)
        rates = metrics.apcer_by_attack(y, p, attack_types, reference.threshold)
        values["apcer_max_at_reference"] = max(rates.values()) if rates else None
    return values


def _subject_clusters(subjects: np.ndarray) -> tuple[np.ndarray, ...]:
    # Stable row indices, once per group, in the same sorted-subject order as np.unique.
    _, inverse = np.unique(subjects, return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    boundaries = np.cumsum(np.bincount(inverse))[:-1]
    return tuple(np.split(order, boundaries)) if subjects.size else ()


def _cluster_indices(
    subjects: np.ndarray,
    rng: np.random.Generator,
    *,
    clusters: tuple[np.ndarray, ...] | None = None,
) -> np.ndarray:
    # Compatibility for direct callers; the bootstrap loop always supplies cached clusters.
    if clusters is None:
        clusters = _subject_clusters(subjects)
    chosen = rng.choice(len(clusters), size=len(clusters), replace=True)
    return np.concatenate([clusters[index] for index in chosen])


def _group_report(
    rows: list[Prediction],
    *,
    threshold: float,
    reference: ReferenceThreshold | None,
    seed: int,
    n_bootstrap: int,
    threshold_source: Literal["default", "caller"] = "caller",
) -> GroupReport:
    usable = [r for r in rows if r.status == Status.OK]
    subjects = np.array([r.subject_id for r in usable])
    y = np.array([r.label for r in usable])
    p = np.array([r.prob_attack for r in usable], dtype=float)
    kinds = np.array([r.attack_type for r in usable])
    group_names = sorted({"bona_fide" if r.label == 0 else r.attack_type for r in rows})
    excluded = []
    for name in group_names:
        members = [r for r in rows if ("bona_fide" if r.label == 0 else r.attack_type) == name]
        excluded.append(
            ExclusionGroup(name, len(members), sum(r.status != Status.OK for r in members))
        )
    points = _points(y, p, kinds, threshold, reference)
    for name in group_names:
        if name != "bona_fide":
            points.setdefault(f"apcer:{name}", None)
    if any(points.get(f"apcer:{name}") is None for name in group_names if name != "bona_fide"):
        points["apcer_max"] = None
        points["apcer_max_at_reference"] = None
    draws: dict[str, list[float]] = {key: [] for key in points}
    rng = np.random.default_rng(seed)
    if usable:
        clusters = _subject_clusters(subjects)
        for _ in range(n_bootstrap):
            indices = _cluster_indices(subjects, rng, clusters=clusters)
            sampled = _points(y[indices], p[indices], kinds[indices], threshold, reference)
            for key in draws:
                value = sampled.get(key)
                # APCER max is undefined if a whole original attack group vanished.
                if key in {"apcer_max", "apcer_max_at_reference"} and any(
                    name != "bona_fide" and not np.any((y[indices] == 1) & (kinds[indices] == name))
                    for name in group_names
                ):
                    value = None
                if value is not None and np.isfinite(value):
                    draws[key].append(value)
    estimates = {}
    for key, value in points.items():
        valid = draws[key]
        low, high = np.quantile(valid, [0.025, 0.975]).tolist() if valid else [None, None]
        cp = None
        if key == "bpcer":
            cp = metrics.clopper_pearson(
                int(np.sum((y == 0) & (p >= threshold))), int(np.sum(y == 0))
            )
        elif key.startswith("apcer:"):
            mask = (y == 1) & (kinds == key.removeprefix("apcer:"))
            cp = metrics.clopper_pearson(int(np.sum(mask & (p < threshold))), int(mask.sum()))
        elif key == "bpcer_at_apcer5_locked" and reference is not None:
            cp = metrics.clopper_pearson(
                int(np.sum((y == 0) & (p >= reference.threshold))), int(np.sum(y == 0))
            )
        estimates[key] = Estimate(
            value, low, high, len(valid), cp[0] if cp else None, cp[1] if cp else None
        )
    n_subjects = int(np.unique(subjects).size)
    warnings = []
    if n_subjects < MIN_SUBJECTS:
        warnings.append(
            f"Chỉ có {n_subjects} subject (<10): khoảng tin cậy không đáng tin; cần thêm người."
        )
    if len(usable) < len(rows):
        warnings.append(
            "Đã loại mẫu không ok theo exclude_non_ok=True; chỉ số có điều kiện trên mẫu còn lại."
        )
    if not usable:
        warnings.append("Không có mẫu ok; tất cả chỉ số không khả dụng.")
    if reference is None:
        warnings.append(
            "BPCER@APCER 5% khóa không khả dụng: thiếu ngưỡng tham chiếu calib_fit có nguồn gốc."
        )
    if reference is not None:
        novel_attacks = sorted(set(group_names) - {"bona_fide"} - set(reference.attack_types))
        if novel_attacks:
            warnings.append(
                "Tập đánh giá có attack_type không có trong calib_fit: "
                + ", ".join(novel_attacks)
                + "; ngưỡng tham chiếu chưa được kiểm trên các loại này."
            )
    if any(e.n_valid < n_bootstrap for e in estimates.values() if e.value is not None):
        warnings.append(
            "Một số lần bootstrap thiếu lớp/loại tấn công; xem số lần hợp lệ của từng chỉ số."
        )
    return GroupReport(
        str(rows[0].module),
        rows[0].model_version,
        len(rows),
        len(usable),
        n_subjects,
        excluded,
        estimates,
        threshold,
        reference,
        warnings,
        threshold_source=threshold_source,
    )


def evaluate(
    rows: list[Prediction],
    *,
    dataset: str,
    threshold: float | None = None,
    reference: ReferenceThreshold | None = None,
    exclude_non_ok: bool = False,
    seed: int = DEFAULT_SEED,
    n_bootstrap: int = DEFAULT_BOOTSTRAP,
    repo: Path | None = None,
) -> EvaluationReport:
    """Đo ở ngưỡng caller đã khóa; bootstrap subject, không fit/chọn bằng dữ liệu đánh giá."""
    rows = _validate_rows(rows)
    threshold_source = "default" if threshold is None else "caller"
    threshold = 0.5 if threshold is None else threshold
    if not dataset.strip():
        raise EvaluationError("Cần tên bộ dữ liệu.")
    metrics._threshold(threshold)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise EvaluationError("seed phải là số nguyên không âm.")
    if isinstance(n_bootstrap, bool) or not isinstance(n_bootstrap, int) or n_bootstrap < 1:
        raise EvaluationError("n_bootstrap phải là số nguyên dương.")
    if not isinstance(exclude_non_ok, bool):
        raise EvaluationError("exclude_non_ok phải được bật bằng boolean.")
    if not exclude_non_ok and any(r.status != Status.OK for r in rows):
        raise EvaluationError(
            "Có status khác ok; bật exclude_non_ok=True để loại và báo số/tỷ lệ loại."
        )
    groups = defaultdict(list)
    for row in rows:
        groups[(row.module, row.model_version)].append(row)
    if reference is not None:
        reference = ReferenceThreshold.model_validate(reference.model_dump())
        if (reference.module, reference.model_version) not in groups:
            raise EvaluationError("Ngưỡng tham chiếu sai module/model_version.")
        if set(reference.subject_ids) & {r.subject_id for r in rows}:
            raise EvaluationError(
                "Subject calib_fit và tập đánh giá bị trùng; ngưỡng phải khóa độc lập."
            )
    reports = []
    for identity, members in sorted(groups.items()):
        ref = (
            reference
            if reference and (reference.module, reference.model_version) == identity
            else None
        )
        reports.append(
            _group_report(
                members,
                threshold=threshold,
                reference=ref,
                seed=seed,
                n_bootstrap=n_bootstrap,
                threshold_source=threshold_source,
            )
        )
    return EvaluationReport(git_revision(repo), dataset.strip(), seed, n_bootstrap, reports)


def _text(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ").replace("`", "'")


def _number(value: float | None) -> str:
    return "không khả dụng" if value is None else f"{value:.6f}"


def render_markdown(result: EvaluationReport) -> str:
    """Hai dòng BPCER riêng; tuyệt đối không có ngưỡng mô tả trong artifact/bảng."""
    lines = [
        "# Báo cáo đánh giá VeriClue",
        "",
        f"Commit: `{_text(result.commit)}`",
        f"Bộ dữ liệu: {_text(result.dataset)}",
        f"Bootstrap theo subject_id: seed={result.seed}, số lần={result.n_bootstrap}; CI percentile 95%.",
        "",
        "Quy ước: 0 = bona fide, 1 = tấn công; prob_attack >= ngưỡng => từ chối.",
        "Clopper–Pearson (CP) là CI nhị thức theo số dòng, giả định độc lập; không thay CI bootstrap theo người.",
        "EER và BPCER mô tả nội suy đường cong, không dùng để chọn ngưỡng vận hành.",
        "",
    ]
    labels = {
        "apcer_max": "APCER max",
        "bpcer": "BPCER",
        "auc": "AUC",
        "eer": "EER (mô tả)",
        "ece": "ECE",
        "brier": "Brier",
        "bpcer_at_apcer5_locked": "BPCER@APCER 5% (ngưỡng khóa từ calib_fit; APCER max)",
        "apcer_max_at_reference": "APCER max thực đạt trên tập đánh giá tại ngưỡng tham chiếu",
        "bpcer_at_apcer5_descriptive": "BPCER@APCER 5% (mô tả, theo đường cong trên tập đánh giá; APCER gộp)",
    }
    for group in result.groups:
        lines.extend(
            [
                f"## {_text(group.module)} / {_text(group.model_version)}",
                "",
                f"Số mẫu: đầu vào={group.n_total}, dùng={group.n_used}; số người dùng={group.n_subjects}.",
                (
                    "Ngưỡng đánh giá: mặc định 0.5, không do caller cung cấp."
                    if group.threshold_source == "default"
                    else f"Ngưỡng đánh giá đã khóa do caller cung cấp: {group.threshold:.8g}."
                ),
                "",
            ]
        )
        if group.reference is not None:
            ref = group.reference
            lines.extend(
                [
                    f"Ngưỡng tham chiếu calib_fit: {ref.threshold:.8g}; bộ dữ liệu {_text(ref.dataset)}; "
                    f"commit `{_text(ref.commit)}`; {len(set(ref.subject_ids))} người; mục tiêu APCER max ≤5%. "
                    f"Loại trong calib_fit: {_text(', '.join(ref.attack_types))}.",
                    "",
                ]
            )
        lines.extend(f"> Cảnh báo: {_text(warning)}" for warning in group.warnings)
        lines.extend(
            [
                "",
                "### Mẫu bị loại do status khác ok",
                "",
                "| Nhóm | Tổng đầu vào | Số bị loại | Tỷ lệ bị loại |",
                "|---|---:|---:|---:|",
            ]
        )
        for exclusion in group.excluded:
            lines.append(
                f"| {_text(exclusion.group)} | {exclusion.total} | {exclusion.excluded} | {exclusion.rate:.2%} |"
            )
        lines.extend(
            [
                "",
                "### Chỉ số (tỷ lệ trong [0,1])",
                "",
                "| Chỉ số | Giá trị | CI bootstrap 95% | Lần hợp lệ / yêu cầu | CP 95% |",
                "|---|---:|---|---:|---|",
            ]
        )
        for key, estimate in group.estimates.items():
            label = (
                f"APCER {_text(key.removeprefix('apcer:'))}"
                if key.startswith("apcer:")
                else labels[key]
            )
            interval = (
                "không khả dụng"
                if estimate.ci_low is None
                else f"[{estimate.ci_low:.6f}, {estimate.ci_high:.6f}]"
            )
            cp = (
                "—"
                if estimate.cp_low is None
                else f"[{estimate.cp_low:.6f}, {estimate.cp_high:.6f}]"
            )
            lines.append(
                f"| {label} | {_number(estimate.value)} | {interval} | {estimate.n_valid}/{result.n_bootstrap} | {cp} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def write_report(result: EvaluationReport, destination: Path) -> None:
    """Ghi đúng báo cáo đã tính; không đọc dữ liệu ngoài đường dẫn caller đưa."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_markdown(result), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """CLI sinh Markdown; tham chiếu chỉ qua --reference đã khóa hoặc --calib-fit riêng."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo", type=Path)
    parser.add_argument(
        "--threshold", type=float, help="Ngưỡng caller đã khóa; bỏ trống dùng mặc định 0.5"
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--n-bootstrap", type=int, default=DEFAULT_BOOTSTRAP)
    parser.add_argument("--exclude-non-ok", action="store_true")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--reference", type=Path, help="JSON ngưỡng benchmark chọn trước từ calib_fit"
    )
    selection.add_argument(
        "--calib-fit", type=Path, help="CSV calib_fit riêng, không phải calib_ltt/test"
    )
    parser.add_argument("--calib-dataset", help="Tên bộ dữ liệu calib_fit")
    args = parser.parse_args(argv)
    try:
        reference = None
        if args.reference:
            reference = ReferenceThreshold.model_validate_json(
                args.reference.read_text(encoding="utf-8")
            )
        elif args.calib_fit:
            if not args.calib_dataset:
                raise EvaluationError("--calib-fit cần --calib-dataset.")
            reference = select_reference_threshold(
                read_predictions(args.calib_fit), dataset=args.calib_dataset, repo=args.repo
            )
        result = evaluate(
            read_predictions(args.predictions),
            dataset=args.dataset,
            threshold=args.threshold,
            reference=reference,
            exclude_non_ok=args.exclude_non_ok,
            seed=args.seed,
            n_bootstrap=args.n_bootstrap,
            repo=args.repo,
        )
        write_report(result, args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
