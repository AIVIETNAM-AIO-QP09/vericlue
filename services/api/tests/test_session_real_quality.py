"""Session diagnostic opt-in must not silently keep quality/probe mocks."""

import pytest

from vericlue_api.core.config import Settings
from vericlue_api.services.orchestrator import Orchestrator
from vericlue_ml.common.result import Module
from vericlue_ml.face.quality import QualityDetector
from vericlue_ml.presence.camprobe import CamProbeDetector


@pytest.mark.parametrize(
    ("module", "real_type"),
    [(Module.QUALITY, QualityDetector), (Module.CAMPROBE, CamProbeDetector)],
)
def test_session_models_use_real_quality_and_probe_even_with_synthetic_otp(module, real_type):
    settings = Settings(_env_file=None, use_mock_models=True, session_face_models=True)
    orchestrator = Orchestrator(settings)
    assert isinstance(orchestrator._default_detector(module), real_type)


@pytest.mark.parametrize("module", [Module.QUALITY, Module.CAMPROBE])
def test_disabled_opt_in_preserves_legacy_mock_selection(module):
    settings = Settings(_env_file=None, use_mock_models=True, session_face_models=False)
    assert "mock" in type(Orchestrator(settings)._default_detector(module)).__module__
