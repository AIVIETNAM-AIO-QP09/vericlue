"""ROUT-01 calibration runner tests use local manifests and a fake registry detector."""

from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

from vericlue_ml.common.calibration import CalibrationStore
from vericlue_ml.common.result import Module, ModuleResult

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def implementation() -> ModuleType:
    """Import lazily so the calibration runner can be implemented independently."""
    return importlib.import_module("fit_calibrators")


@pytest.fixture(autouse=True)
def reproducible_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = implementation()
    monkeypatch.setattr(
        runner.subprocess,
        "check_output",
        lambda args, **kwargs: "a" * 40 if args[1] == "rev-parse" else "",
    )
    # run() chooses these environment variables; keep its changes isolated per test.
    monkeypatch.setenv("DEVICE", "cpu")
    monkeypatch.setenv("MODELS_DIR", "models")


def manifest(data_dir: Path, dataset: str, rows: list[dict[str, str]]) -> None:
    folder = data_dir / "splits" / dataset
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "calib_fit.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["path", "label", "attack_type", "subject_id", "group_id"]
        )
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        media = data_dir / row["path"]
        media.parent.mkdir(parents=True, exist_ok=True)
        media.touch()


def row(name: str, label: int, attack: str, group: str) -> dict[str, str]:
    return {
        "path": f"raw/audio/{name}.wav",
        "label": str(label),
        "attack_type": attack,
        "subject_id": "",
        "group_id": group,
    }


def fitting_data(data_dir: Path) -> None:
    rows = [
        row(f"{kind}_{group}", label, attack, f"identity-{group}")
        for group in range(6)
        for kind, label, attack in [("real", 0, "bonafide"), ("fake", 1, "tts")]
    ]
    manifest(data_dir, "fixture", rows)


class FakeVoice:
    name = "voice_spoof"
    version = "actual-detector@123+recipe-v1"

    def __init__(self, *, status: str = "ok", version: str | None = None) -> None:
        self.status = status
        self.result_version = version or self.version
        self.preloads: list[Path | None] = []
        self.paths: list[Path] = []

    def preload(self, *, models_dir: Path | None = None) -> None:
        self.preloads.append(models_dir)

    def predict(self, inp) -> ModuleResult:
        self.paths.append(inp.audio)
        return ModuleResult(
            module=self.name,
            model_version=self.result_version,
            status=self.status,
            score=0.9 if inp.audio.stem.startswith("fake") else 0.1,
            prob_attack=None,
            latency_ms=1,
        )


def test_voice_reads_only_calib_fit_and_excludes_replay(tmp_path: Path) -> None:
    runner = implementation()
    manifest(
        tmp_path,
        "fixture",
        [
            row("tts", 1, "tts", "shared-source"),
            row("vc", 1, "vc", "shared-source"),
            row("real", 0, "bonafide", "real-person"),
            row("replay", 1, "replay", "replayed-person"),
        ],
    )
    for split in ("calib_ltt", "test"):
        (tmp_path / "splits" / "fixture" / f"{split}.csv").write_text(
            "INVALID,DO NOT READ\n", encoding="utf-8"
        )
    samples, _ = runner.load_samples(tmp_path, Module.VOICE_SPOOF, ["fixture"])
    assert {sample.path.stem for sample in samples} == {"tts", "vc", "real"}
    assert [sample.label for sample in samples].count(1) == 2
    assert samples[0].group_id == samples[1].group_id
    assert samples[0].group_id != samples[2].group_id


def test_runner_rejects_missing_identity_group(tmp_path: Path) -> None:
    runner = implementation()
    manifest(tmp_path, "fixture", [row("tts", 1, "tts", "")])
    with pytest.raises((ValueError, RuntimeError)):
        runner.load_samples(tmp_path, Module.VOICE_SPOOF, ["fixture"])


def test_runner_rejects_media_outside_data_dir(tmp_path: Path) -> None:
    runner = implementation()
    entry = row("tts", 1, "tts", "source-group")
    entry["path"] = "../outside.wav"
    data_dir = tmp_path / "data"
    manifest(data_dir, "fixture", [entry])
    with pytest.raises((ValueError, RuntimeError)):
        runner.load_samples(data_dir, Module.VOICE_SPOOF, ["fixture"])


def test_runner_uses_real_registry_version_and_saves_provisional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = implementation()
    fitting_data(tmp_path)
    detector = FakeVoice()
    calls = []

    def get_detector(module, *, mock=None):
        calls.append((module, mock))
        return detector

    monkeypatch.setattr(runner, "get_detector", get_detector)
    output = tmp_path / "artifacts"
    runner.run(
        module=Module.VOICE_SPOOF,
        data_dir=tmp_path,
        models_dir=tmp_path / "models",
        output_dir=output,
        datasets=["fixture"],
        n_splits=3,
    )
    assert calls == [(Module.VOICE_SPOOF, False)]
    assert len(detector.preloads) == 1
    assert len(detector.paths) == 12
    artifact = CalibrationStore(output).load(Module.VOICE_SPOOF, detector.version)
    assert artifact.model_version == detector.version
    assert artifact.n_pos == artifact.n_neg == 6
    assert artifact.method == "platt"
    assert artifact.provisional is True
    assert artifact.split == "calib_fit"
    assert artifact.commit


@pytest.mark.parametrize("status", ["error", "degraded", "not_applicable"])
def test_runner_fails_closed_on_unusable_detector_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    runner = implementation()
    fitting_data(tmp_path)
    monkeypatch.setattr(runner, "get_detector", lambda *args, **kwargs: FakeVoice(status=status))
    output = tmp_path / "artifacts"
    with pytest.raises((ValueError, RuntimeError)):
        runner.run(
            module=Module.VOICE_SPOOF,
            data_dir=tmp_path,
            models_dir=tmp_path / "models",
            output_dir=output,
            datasets=["fixture"],
        )
    assert not list(output.rglob("*.json"))


def test_runner_rejects_result_model_version_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = implementation()
    fitting_data(tmp_path)
    monkeypatch.setattr(
        runner, "get_detector", lambda *args, **kwargs: FakeVoice(version="unexpected-version")
    )
    output = tmp_path / "artifacts"
    with pytest.raises((ValueError, RuntimeError)):
        runner.run(
            module=Module.VOICE_SPOOF,
            data_dir=tmp_path,
            models_dir=tmp_path / "models",
            output_dir=output,
            datasets=["fixture"],
        )
    assert not list(output.rglob("*.json"))


def test_runner_requires_committed_code_before_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = implementation()
    fitting_data(tmp_path)
    monkeypatch.setattr(
        runner.subprocess,
        "check_output",
        lambda args, **kwargs: "a" * 40 if args[1] == "rev-parse" else " M scripts/runner.py",
    )

    def forbidden_detector(*args, **kwargs):
        raise AssertionError("Dirty checkout must fail before loading model weights")

    monkeypatch.setattr(runner, "get_detector", forbidden_detector)
    with pytest.raises(ValueError, match="Commit implementation"):
        runner.run(
            module=Module.VOICE_SPOOF,
            data_dir=tmp_path,
            models_dir=tmp_path / "models",
            output_dir=tmp_path / "artifacts",
            datasets=["fixture"],
        )
