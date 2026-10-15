"""TTS preparation is mocked: no service, binary or media download in tests."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "prepare_voice_tts", Path(__file__).parents[1] / "prepare_voice_tts.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_fixed_fixtures_use_pinned_tool_and_explicit_data_path(tmp_path, monkeypatch):
    executable = tmp_path / "tools/espeak-ng.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"mock-executable")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if "--version" in command:
            return SimpleNamespace(stdout="eSpeak NG text-to-speech: 1.52.0 Data at: fixture")
        Path(command[command.index("-w") + 1]).write_bytes(b"mock-not-real-audio")

    monkeypatch.setattr(module.subprocess, "run", run)
    manifest = module.prepare_fixtures(tmp_path, executable)
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(rows) == 2
    assert rows[0]["expected"] == rows[0]["spoken"]
    assert rows[0]["should_match"] is True and rows[1]["should_match"] is False
    assert rows[1]["expected"] != rows[1]["spoken"]
    assert all(f"--path={executable.parent}" in call for call in calls)


def test_wrong_tool_version_is_not_misreported(tmp_path, monkeypatch):
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="eSpeak NG text-to-speech: 9.9.9"),
    )
    with pytest.raises(ValueError, match="1.52.0"):
        module.prepare_fixtures(tmp_path, tmp_path / "espeak-ng.exe")


def test_mms_missing_artifacts_never_downloads_implicitly(tmp_path, monkeypatch):
    monkeypatch.setattr(
        module.httpx, "stream", lambda *args, **kwargs: pytest.fail("Implicit network")
    )
    with pytest.raises(RuntimeError, match="download-model"):
        module.prepare_mms(tmp_path / "data", tmp_path / "models")


def test_mms_corrupted_weights_are_not_loaded(tmp_path, monkeypatch):
    models = tmp_path / "models/mms-tts-vie"
    models.mkdir(parents=True)
    (models / "model.safetensors").write_bytes(b"bad")
    monkeypatch.setattr(module, "MMS_FILES", {"model.safetensors": 3})
    with pytest.raises(RuntimeError, match="SHA-256"):
        module.prepare_mms(tmp_path / "data", tmp_path / "models")
