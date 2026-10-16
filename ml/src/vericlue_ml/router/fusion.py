"""Strict probability fusion and future logistic training restricted to calib_fit."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, model_validator
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from vericlue_ml.common.result import Module, ModuleResult, Status


class FusionError(ValueError):
    """A mandatory feature is missing or unusable."""


def max_probability(results: dict[Module, ModuleResult], modules: tuple[Module, ...]) -> float:
    """Use every required calibrated probability; no raw-score or missing-feature fallback."""
    probabilities = []
    for module in modules:
        result = results.get(module)
        if (
            result is None
            or result.module != module
            or module == Module.VOICE_CHALLENGE
            or result.status != Status.OK
            or result.prob_attack is None
            or not np.isfinite(result.prob_attack)
            or not 0 <= result.prob_attack <= 1
        ):
            raise FusionError(f"Missing usable probability: {module}")
        probabilities.append(result.prob_attack)
    if not probabilities:
        raise FusionError("No required probability modules")
    return max(probabilities)


def _validate_features(names: list[str], versions: dict[str, str]) -> None:
    if not names or len(set(names)) != len(names):
        raise ValueError("Unique feature names required")
    for name in names:
        parts = name.split(":")
        if len(parts) not in (2, 3) or parts[0] not in {"prob_attack", "quality"}:
            raise ValueError("Only explicit probability or quality features are accepted")
        module = Module(parts[1])
        if module == Module.VOICE_CHALLENGE or (
            parts[0] == "prob_attack"
            and module
            not in {Module.FACE_PAD, Module.FACE_DEEPFAKE, Module.VOICE_SPOOF, Module.LIPSYNC}
        ):
            raise ValueError("WER is not an attack probability")
        if (parts[0] == "prob_attack" and len(parts) != 2) or (
            parts[0] == "quality" and len(parts) != 3
        ):
            raise ValueError("Invalid feature name")
    for name in names:
        module = name.split(":")[1]
        if not versions.get(module, "").strip():
            raise ValueError(f"Missing model version for feature module {module}")


class FusionFit(BaseModel):
    """Caller supplies subject-separated calib_fit; calib_ltt and test are forbidden."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    features: list[list[float]]
    labels: list[int]
    subject_ids: list[str]
    feature_names: list[str]
    model_versions: dict[str, str]
    dataset: str
    split: Literal["calib_fit"] = "calib_fit"

    @model_validator(mode="after")
    def valid_training_data(self):
        n = len(self.labels)
        if not n or len(self.features) != n or len(self.subject_ids) != n:
            raise ValueError("Feature/label/subject row counts must match")
        if set(self.labels) != {0, 1} or any(not s.strip() for s in self.subject_ids):
            raise ValueError("Both binary classes and nonempty subject IDs are required")
        names = self.feature_names
        _validate_features(names, self.model_versions)
        if any(len(row) != len(names) for row in self.features):
            raise ValueError("Features must be rectangular and match feature names")
        values = np.asarray(self.features)
        if not np.isfinite(values).all():
            raise ValueError("Nonfinite feature")
        for i, name in enumerate(names):
            if name.startswith("prob_attack:") and (
                (values[:, i] < 0).any() or (values[:, i] > 1).any()
            ):
                raise ValueError("Probabilities must be in [0,1]")
        if not self.dataset.strip() or not self.model_versions:
            raise ValueError("Dataset and model version provenance required")
        return self


class LogisticFusion(BaseModel):
    """Explicit feature order, scaler and provenance; never auto-activated by the API."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    method: Literal["logistic"] = "logistic"
    split: Literal["calib_fit"] = "calib_fit"
    feature_names: list[str]
    model_versions: dict[str, str]
    mean: list[float]
    scale: list[float]
    coefficients: list[float]
    intercept: float
    dataset: str
    n_pos: int
    n_neg: int
    commit: str
    date: str

    @model_validator(mode="after")
    def valid_parameters(self):
        _validate_features(self.feature_names, self.model_versions)
        if (
            not self.dataset.strip()
            or not self.commit.strip()
            or not self.date.strip()
            or self.n_pos <= 0
            or self.n_neg <= 0
        ):
            raise ValueError("Incomplete learned fusion provenance/classes")
        n = len(self.feature_names)
        if (
            not n
            or any(len(v) != n for v in (self.mean, self.scale, self.coefficients))
            or any(s <= 0 for s in self.scale)
        ):
            raise ValueError("Invalid logistic parameter dimensions/scale")
        return self

    def predict(self, features) -> np.ndarray:
        """Predict using the recorded feature order; reject missing/nonfinite columns."""
        from scipy.special import expit

        x = np.asarray(features, dtype=float)
        if x.ndim != 2 or x.shape[1] != len(self.feature_names) or not np.isfinite(x).all():
            raise ValueError("Invalid fusion feature dimensions/values")
        for i, name in enumerate(self.feature_names):
            if name.startswith("prob_attack:") and ((x[:, i] < 0).any() or (x[:, i] > 1).any()):
                raise ValueError("Probabilities must be in [0,1]")
        return expit(
            ((x - self.mean) / self.scale) @ np.asarray(self.coefficients) + self.intercept
        )

    def save(self, path: str | Path) -> None:
        """Save to an explicit caller-owned artifact path."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> LogisticFusion:
        """Validate serialized logistic metadata."""
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


def fit(calib_fit: FusionFit, *, commit: str) -> LogisticFusion:
    """Fit fixed logistic settings only on calib_fit; no threshold or model selection."""
    calib_fit = FusionFit.model_validate(calib_fit.model_dump())
    if not commit.strip():
        raise ValueError("Training commit required")
    x = np.asarray(calib_fit.features)
    scaler = StandardScaler().fit(x)
    model = LogisticRegression(random_state=0).fit(scaler.transform(x), calib_fit.labels)
    return LogisticFusion(
        feature_names=calib_fit.feature_names,
        model_versions=calib_fit.model_versions,
        mean=scaler.mean_.tolist(),
        scale=scaler.scale_.tolist(),
        coefficients=model.coef_[0].tolist(),
        intercept=float(model.intercept_[0]),
        dataset=calib_fit.dataset,
        n_pos=sum(calib_fit.labels),
        n_neg=len(calib_fit.labels) - sum(calib_fit.labels),
        commit=commit,
        date=datetime.now(UTC).isoformat(),
    )
