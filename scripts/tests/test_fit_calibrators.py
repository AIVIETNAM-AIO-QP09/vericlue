"""ROUT-01 calibration runner tests use local manifests and a fake registry detector."""

from __future__ import annotations

import csv
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from vericlue_ml.common.calibration import CalibrationStore
from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Module, ModuleResult

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


@pytest.mark.parametrize(
    ("status", "reason", "score", "version"),
    [
        ("error", ErrorCode.E_LOW_QUALITY, None, FakeVoice.version),
        ("degraded", ErrorCode.E_LOW_QUALITY, None, FakeVoice.version),
        ("not_applicable", None, None, FakeVoice.version),
        ("not_applicable", ErrorCode.E_LOW_QUALITY, 0.2, FakeVoice.version),
        ("not_applicable", ErrorCode.E_LOW_QUALITY, None, "unexpected-version"),
    ],
)
def test_quality_exclusion_does_not_hide_other_unusable_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    reason: ErrorCode | None,
    score: float | None,
    version: str,
) -> None:
    runner = implementation()
    fitting_data(tmp_path)
    detector = FakeVoice()

    def predict(inp: DetectorInput) -> ModuleResult:
        return ModuleResult(
            module=Module.VOICE_SPOOF,
            model_version=version,
            status=status,
            error_code=reason,
            score=score,
            latency_ms=1,
        )

    monkeypatch.setattr(detector, "predict", predict)
    monkeypatch.setattr(runner, "get_detector", lambda *args, **kwargs: detector)
    output = tmp_path / "artifacts"
    with pytest.raises(ValueError):
        runner.run(
            module=Module.VOICE_SPOOF,
            data_dir=tmp_path,
            models_dir=tmp_path / "models",
            output_dir=output,
            datasets=["fixture"],
        )
    assert not list(output.rglob("*.json"))


def test_no_score_low_quality_exclusion_preserves_actual_fit_counts_and_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = implementation()
    rows = [
        row(f"{kind}_{group}", label, attack, f"identity-{group}")
        for group in range(6)
        for kind, label, attack in [("real", 0, "bonafide"), ("fake", 1, "tts")]
    ]
    rows.extend(
        [
            row("low_quality_real", 0, "bonafide", "short-real-person"),
            row("low_quality_fake", 1, "tts", "short-fake-source"),
        ]
    )
    manifest(tmp_path, "fixture", rows)

    class QualityAwareVoice(FakeVoice):
        def predict(self, inp: DetectorInput) -> ModuleResult:
            if not inp.audio.stem.startswith("low_quality_"):
                return super().predict(inp)
            self.paths.append(inp.audio)
            return ModuleResult(
                module=self.name,
                model_version=self.version,
                status="not_applicable",
                error_code=ErrorCode.E_LOW_QUALITY,
                score=None,
                latency_ms=1,
            )

    detector = QualityAwareVoice()
    monkeypatch.setattr(runner, "get_detector", lambda *args, **kwargs: detector)
    output = tmp_path / "artifacts"
    summary = runner.run(
        module=Module.VOICE_SPOOF,
        data_dir=tmp_path,
        models_dir=tmp_path / "models",
        output_dir=output,
        datasets=["fixture"],
        n_splits=3,
    )
    assert len(detector.paths) == 14
    artifact = CalibrationStore(output).load(Module.VOICE_SPOOF, detector.version)
    assert artifact.n_pos == artifact.n_neg == 6
    assert summary["n_pos"] == summary["n_neg"] == 6
    assert summary["selection"]["n_pos"] == summary["selection"]["n_neg"] == 7
    provenance = json.loads(artifact.dataset)
    assert provenance["selection"] == summary["selection"]
    assert provenance["excluded_quality"] == {
        "fixture:label=0:E_LOW_QUALITY": 1,
        "fixture:label=1:E_LOW_QUALITY": 1,
    }
    assert summary["excluded_quality"] == provenance["excluded_quality"]


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


def fake_cv2(
    monkeypatch: pytest.MonkeyPatch,
    *,
    length: int,
    readable: bool = True,
    writable: bool = True,
) -> list[tuple]:
    """Record video operations without importing OpenCV or allocating image arrays."""
    events = []
    frame = object()
    cv2 = ModuleType("cv2")
    cv2.CAP_PROP_FRAME_COUNT = 7
    cv2.CAP_PROP_POS_FRAMES = 1

    class Capture:
        def __init__(self, path: str) -> None:
            events.append(("open", path))

        def get(self, prop: int) -> int:
            assert prop == cv2.CAP_PROP_FRAME_COUNT
            return length

        def set(self, prop: int, index: int) -> None:
            assert prop == cv2.CAP_PROP_POS_FRAMES
            events.append(("seek", index))

        def read(self) -> tuple[bool, object]:
            events.append(("read",))
            return readable, frame

        def release(self) -> None:
            events.append(("release",))

    def imwrite(path: str, image: object) -> bool:
        assert image is frame
        events.append(("write", path))
        return writable

    cv2.VideoCapture = Capture
    cv2.imwrite = imwrite
    monkeypatch.setitem(sys.modules, "cv2", cv2)
    return events


@pytest.mark.parametrize("length", [10, 11])
def test_middle_frame_seeks_middle_writes_and_releases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, length: int
) -> None:
    events = fake_cv2(monkeypatch, length=length)
    video, target = tmp_path / "input.mp4", tmp_path / "middle.png"
    implementation().middle_frame(video, target)
    assert events == [
        ("open", str(video)),
        ("seek", length // 2),
        ("read",),
        ("write", str(target)),
        ("release",),
    ]


@pytest.mark.parametrize(
    ("length", "readable", "writable"), [(0, True, True), (10, False, True), (10, True, False)]
)
def test_middle_frame_fails_closed_and_releases_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    length: int,
    readable: bool,
    writable: bool,
) -> None:
    events = fake_cv2(monkeypatch, length=length, readable=readable, writable=writable)
    with pytest.raises(ValueError, match="Cannot"):
        implementation().middle_frame(tmp_path / "input.mp4", tmp_path / "middle.png")
    assert events[-1] == ("release",)
    if length < 1:
        assert not any(event[0] in {"seek", "read", "write"} for event in events)
    elif not readable:
        assert not any(event[0] == "write" for event in events)


def test_face_pad_runner_calibrates_middle_frame_images_from_videos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = implementation()
    rows = [
        row(f"{kind}_{group}", label, attack, f"identity-{group}")
        for group in range(6)
        for kind, label, attack in [("real", 0, "bonafide"), ("fake", 1, "print")]
    ]
    for entry in rows:
        entry["path"] = str(Path(entry["path"]).with_suffix(".mp4"))
    manifest(tmp_path, "zalo2022", rows)
    converted = []

    def extract(video: Path, target: Path) -> None:
        converted.append(video)
        target.write_text(video.stem, encoding="utf-8")

    class FakePad(FakeVoice):
        name = "face_pad"
        version = "actual-pad@456+recipe-v1"

        def predict(self, inp: DetectorInput) -> ModuleResult:
            assert inp.video is None and inp.audio is None
            assert len(inp.images) == 1
            image = inp.images[0]
            assert image.suffix == ".png"
            self.paths.append(image)
            return ModuleResult(
                module=self.name,
                model_version=self.version,
                status="ok",
                score=0.9 if image.read_text(encoding="utf-8").startswith("fake") else 0.1,
                prob_attack=None,
                latency_ms=1,
            )

    detector = FakePad()

    def real_pad(module: Module, *, mock: bool) -> FakePad:
        assert module == Module.FACE_PAD and mock is False
        return detector

    monkeypatch.setattr(runner, "middle_frame", extract)
    monkeypatch.setattr(runner, "get_detector", real_pad)
    output = tmp_path / "artifacts"
    runner.run(
        module=Module.FACE_PAD,
        data_dir=tmp_path,
        models_dir=tmp_path / "models",
        output_dir=output,
        datasets=["zalo2022"],
        n_splits=3,
    )
    assert converted == [(tmp_path / entry["path"]).resolve() for entry in rows]
    assert len(detector.paths) == len(rows)
    assert len(detector.preloads) == 1
    artifact = CalibrationStore(output).load(Module.FACE_PAD, detector.version)
    assert artifact.n_pos == artifact.n_neg == 6
    assert artifact.provisional is True
    assert "middle frame" in artifact.dataset
