"""ROUT-02 lazy import and per-application voice matching config regressions."""

import os
import subprocess
import sys
from pathlib import Path

import yaml

from vericlue_api.core.config import Settings
from vericlue_api.services.orchestrator import Orchestrator
from vericlue_ml.common.result import Module
from vericlue_ml.mock.detectors import MockDetector
from vericlue_ml.voice.challenge import VoiceChallengeDetector


def test_voice_module_import_does_not_read_missing_thresholds_config(tmp_path):
    missing = tmp_path / "deployment-config-not-yet-mounted.yaml"
    environment = os.environ | {"THRESHOLDS_CONFIG": str(missing)}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from vericlue_ml.voice.challenge import VoiceChallengeDetector; "
            "from vericlue_ml.voice.challenge import compare_transcripts",
        ],
        env=environment,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert not missing.exists()


def test_cached_voice_wrapper_is_cloned_before_binding_each_application_config(tmp_path):
    class FakeASR:
        version = "synthetic@shared-asr"

        def preload(self, *, models_dir=None, device=None):
            pass

    shared_asr = FakeASR()
    shared_wrapper = VoiceChallengeDetector(asr=shared_asr)
    raw = yaml.safe_load(
        (Path(__file__).parents[3] / "ml/configs/thresholds.yaml").read_text(encoding="utf-8")
    )
    paths = []
    for index, wer in enumerate((0.1, 0.8)):
        raw["voice"]["max_syllable_wer"] = wer
        path = tmp_path / f"app-{index}.yaml"
        path.write_text(yaml.safe_dump(raw), encoding="utf-8")
        paths.append(path)

    def factory(module):
        return shared_wrapper if module == Module.VOICE_CHALLENGE else MockDetector(module)

    first = Orchestrator(Settings(thresholds_config=str(paths[0])), detector_factory=factory)
    second = Orchestrator(Settings(thresholds_config=str(paths[1])), detector_factory=factory)
    try:
        first.start()
        first_voice = first._detectors[Module.VOICE_CHALLENGE]
        assert first_voice.match_config.max_syllable_wer == 0.1
        snapshot_hash = first.router.config.config_version
        second.start()
        second_voice = second._detectors[Module.VOICE_CHALLENGE]
        assert not first.failed_modules and not second.failed_modules
        assert first_voice is not second_voice
        assert first_voice is not shared_wrapper and second_voice is not shared_wrapper
        assert first_voice.asr is second_voice.asr is shared_asr
        assert first_voice.match_config.max_syllable_wer == 0.1
        assert second_voice.match_config.max_syllable_wer == 0.8
        assert first.router.config.config_version == snapshot_hash
        assert first.router.config.config_version != second.router.config.config_version
        assert shared_wrapper.match_config is None
    finally:
        first.close()
        second.close()


def test_dotenv_thresholds_path_is_shared_by_router_and_forensic(tmp_path, monkeypatch):
    from vericlue_api.core.state import AppState
    from vericlue_api.db.database import Database

    monkeypatch.delenv("THRESHOLDS_CONFIG", raising=False)
    raw = yaml.safe_load(
        (Path(__file__).parents[3] / "ml/configs/thresholds.yaml").read_text(encoding="utf-8")
    )
    raw["face"].update(b=0.11, a=0.85)
    config_path = tmp_path / "custom thresholds.yaml"
    config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    env_path = tmp_path / "api.env"
    env_path.write_text(f'THRESHOLDS_CONFIG="{config_path.as_posix()}"\n', encoding="utf-8")
    settings = Settings(_env_file=env_path)
    assert settings.router_config.face.b == 0.11
    assert settings.router_config.face.a == 0.85
    database = Database("sqlite:///:memory:")
    orchestrator = Orchestrator(settings)
    try:
        with database.sessions() as db:
            state = AppState(settings, db, orchestrator)
            assert (state.forensic._b, state.forensic._a) == (0.11, 0.85)
            assert state.flow.router.config is settings.router_config
    finally:
        orchestrator.close()
        database.dispose()
