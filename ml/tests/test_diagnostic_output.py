"""Synthetic producer reports must never be written into runtime storage."""

from types import SimpleNamespace

import pytest
from test_nes2net_readiness import balanced_samples, report_fixture
from test_nes2net_utterance import make_manifest, timeline
from test_session_calibration import fake_runtime, write_manifest

from vericlue_ml.eval import nes2net_utterance as voice
from vericlue_ml.eval import session_calibration as face
from vericlue_ml.voice.nes2net import Nes2NetBackend

STORES = ("MODELS_DIR", "DATA_DIR", "CALIBRATORS_DIR")


@pytest.mark.parametrize("store", STORES)
@pytest.mark.parametrize("command", ["readiness", "fit"])
def test_voice_reports_reject_configured_stores_before_fitting(
    tmp_path, monkeypatch, store, command
):
    report, _ = report_fixture(tmp_path, monkeypatch, balanced_samples())
    storage = tmp_path / "configured-store"
    monkeypatch.setenv(store, str(storage))
    output = storage / "must-not-exist.json"
    fits = []

    def fit(*args, **kwargs):
        fits.append(True)
        return SimpleNamespace(model_dump=lambda **_: {"synthetic_test": True})

    monkeypatch.setattr(voice, "fit", fit)
    action = voice.readiness_report if command == "readiness" else voice.fit_report
    with pytest.raises(ValueError, match="storage"):
        action(report, output)
    assert fits == []
    assert not output.exists()


def collector(tmp_path, monkeypatch, kind):
    calls = []
    if kind == "voice":
        manifest, _ = make_manifest(tmp_path)
        detector = timeline(monkeypatch)
        detector.preload = lambda: calls.append("load")
        detector.backend.config = Nes2NetBackend().config
        monkeypatch.setattr(voice, "git_revision", lambda: "c" * 40)

        def collect(output):
            return voice.collect(
                manifest, tmp_path, tmp_path / "explicit-models", output, detector=detector
            )

        return collect, detector, calls
    manifest, _ = write_manifest(tmp_path)
    fake_runtime(monkeypatch)
    model_manifest = tmp_path / "synthetic-model-manifest.yaml"
    model_manifest.write_text("synthetic-model-manifest", encoding="utf-8")
    monkeypatch.setenv("ML_MODELS_MANIFEST", str(model_manifest))
    original = face.make_runtime
    runtime = original("face_pad", tmp_path / "explicit-models", "cpu")

    def load(*args):
        calls.append("load")
        return runtime

    monkeypatch.setattr(face, "make_runtime", load)

    def collect(output):
        return face.collect(manifest, tmp_path, tmp_path / "explicit-models", "face_pad", output)

    return collect, runtime[0], calls


@pytest.mark.parametrize("kind", ["voice", "face"])
@pytest.mark.parametrize("store", STORES)
def test_collectors_reject_configured_stores_before_model_load(tmp_path, monkeypatch, kind, store):
    collect, _, calls = collector(tmp_path, monkeypatch, kind)
    storage = tmp_path / "configured-store"
    monkeypatch.setenv(store, str(storage))
    output = storage / "must-not-exist.json"
    with pytest.raises(ValueError, match="storage"):
        collect(output)
    assert calls == []
    assert not output.exists()


@pytest.mark.parametrize("kind", ["voice", "face"])
def test_collectors_recheck_storage_changed_during_measurement(tmp_path, monkeypatch, kind):
    collect, runtime, calls = collector(tmp_path, monkeypatch, kind)
    method = "predict_samples" if kind == "voice" else "predict_frames"
    original = getattr(runtime, method)

    def changed(*args, **kwargs):
        monkeypatch.setenv("CALIBRATORS_DIR", str(tmp_path))
        return original(*args, **kwargs)

    monkeypatch.setattr(runtime, method, changed)
    output = tmp_path / "must-not-exist.json"
    with pytest.raises(ValueError, match="storage"):
        collect(output)
    assert calls == ["load"]
    assert not output.exists()


@pytest.mark.parametrize("store", STORES)
def test_prepare_rejects_configured_storage_before_reading_audio(tmp_path, monkeypatch, store):
    monkeypatch.setenv(store, str(tmp_path))

    def forbidden(*args, **kwargs):
        pytest.fail("An invalid output must be rejected before reading manifest/audio")

    monkeypatch.setattr(voice, "load_manifest", forbidden)
    output = tmp_path / "must-not-exist.json"
    with pytest.raises(ValueError, match="storage"):
        voice.main(
            [
                "prepare",
                "--manifest",
                str(tmp_path / "unused.json"),
                "--data-root",
                str(tmp_path),
                "--output",
                str(output),
            ]
        )
    assert not output.exists()


@pytest.mark.parametrize(
    "directory", ["ml/configs", "configs", "models", "data", "external", "packages/contracts"]
)
def test_readiness_rejects_repository_storage_after_path_normalization(
    tmp_path, monkeypatch, directory
):
    from vericlue_ml.eval import diagnostic_output

    report, _ = report_fixture(tmp_path, monkeypatch, balanced_samples())
    repository = tmp_path / "synthetic-repository"
    monkeypatch.setattr(diagnostic_output, "ROOT", repository)
    output = repository / directory / "unused" / ".." / "must-not-exist.json"
    with pytest.raises(ValueError, match="storage"):
        voice.readiness_report(report, output)
    assert not output.resolve().exists()
