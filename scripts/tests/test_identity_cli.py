"""ADR-0012 identity generation uses only temporary output and tracked configuration."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from vericlue_ml.common.calibration import CalibrationError, CalibrationStore
from vericlue_ml.common.result import Module

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
COMMIT = "a" * 40


@pytest.fixture
def generator(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    implementation = importlib.import_module("create_identity_calibrator")

    def source_commit(args, *, cwd, text):
        assert args == ["git", "rev-parse", "HEAD"]
        assert cwd == ROOT and text is True
        return COMMIT + "\n"

    monkeypatch.setattr(implementation.subprocess, "check_output", source_commit)
    return implementation


@pytest.mark.parametrize("module", [Module.FACE_PAD, Module.FACE_DEEPFAKE, Module.VOICE_SPOOF])
def test_generator_preserves_exact_version_and_marks_untrained_artifact(
    tmp_path: Path, generator: ModuleType, module: Module
) -> None:
    version = "detector@exact-revision+recipe/v2"
    output = tmp_path / "artifacts"
    path = generator.run(module, version, output)
    assert path == output / module.value / "detector@exact-revision%2Brecipe%2Fv2.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["module"] == module.value
    assert payload["model_version"] == version
    assert payload["commit"] == COMMIT
    assert payload["method"] == "identity"
    assert payload["provisional"] is True
    assert payload["note"] == "MVP — không dùng cho báo cáo"
    assert payload["n_pos"] == payload["n_neg"] == 0
    assert payload["dataset"] == "not_fitted"
    assert payload["split"] == "none"
    assert payload["metrics_scope"] == "not_evaluated"
    assert not {
        "before",
        "after",
        "before_reliability",
        "after_reliability",
        "cv_folds",
        "cv_log_loss",
        "baseline",
    }.intersection(payload)
    artifact = CalibrationStore(output).load(module, version)
    assert artifact.model_version == version
    assert artifact.predict([-1, 0.3, 2]).tolist() == [0.0001, 0.3, 0.9999]
    with pytest.raises(CalibrationError, match="prior"):
        _ = artifact.prior_attack


def test_generator_preserves_existing_tracked_voice_platt(
    tmp_path: Path, generator: ModuleType
) -> None:
    tracked = ROOT / "ml" / "configs" / "calibrators" / "voice_spoof"
    sources = [
        path
        for path in tracked.glob("*.json")
        if json.loads(path.read_text(encoding="utf-8"))["method"] == "platt"
    ]
    assert sources, "Expected a tracked voice Platt calibrator configuration"
    original = sources[0].read_bytes()
    payload = json.loads(original)
    assert payload["method"] == "platt"
    version = payload["model_version"]
    output = tmp_path / "artifacts"
    store = CalibrationStore(output)
    destination = store.path(Module.VOICE_SPOOF, version)
    destination.parent.mkdir(parents=True)
    destination.write_bytes(original)
    with pytest.raises(CalibrationError, match="Refusing to replace"):
        generator.run(Module.VOICE_SPOOF, version, output)
    assert destination.read_bytes() == original
    artifact = CalibrationStore(output).load(Module.VOICE_SPOOF, version)
    assert artifact.method == "platt"
    assert artifact.n_pos == payload["n_pos"]
    assert artifact.n_neg == payload["n_neg"]


def test_generator_can_regenerate_valid_identity(tmp_path: Path, generator: ModuleType) -> None:
    output = tmp_path / "artifacts"
    version = "face@verified-revision+preprocessing-v1"
    first = generator.run(Module.FACE_PAD, version, output)
    second = generator.run(Module.FACE_PAD, version, output)
    assert second == first
    assert list(output.rglob("*.json")) == [first]
    artifact = CalibrationStore(output).load(Module.FACE_PAD, version)
    assert artifact.method == "identity"
    assert artifact.provisional is True
    assert artifact.commit == COMMIT
    assert artifact.model_version == version
