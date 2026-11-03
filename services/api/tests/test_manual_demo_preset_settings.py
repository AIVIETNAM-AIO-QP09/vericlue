"""A fixed manual preset cannot leak into standard mode or accept conflicting overrides."""

import pytest
from pydantic import ValidationError
from test_manual_face_demo import config, full_config

from vericlue_api.core.config import Settings
from vericlue_api.services.orchestrator import Orchestrator
from vericlue_ml.common.result import Module


def test_preset_uses_effective_values_without_legacy_defaults_overriding_it():
    settings = full_config(manual_demo_preset="phone-demo-fixed-v1")
    policy = settings.manual_demo_policy
    assert policy.model_dump() == dict(
        pad_max=0.70,
        gend_max=0.95,
        match_min=0.30,
        consistency_min=0.30,
        spoof_max=0.70,
        lipsync_max=0.60,
    )
    assert policy.policy_id != full_config(manual_demo_gend_max=0.90).manual_demo_policy.policy_id
    for field, value in policy.model_dump().items():
        assert getattr(settings, "manual_demo_" + field) == value
    with pytest.raises(ValidationError):
        policy.pad_max = 0.99


@pytest.mark.parametrize(
    "field", ["pad_max", "gend_max", "spoof_max", "lipsync_max", "match_min", "consistency_min"]
)
def test_explicit_conflicting_cutoffs_are_rejected(field):
    with pytest.raises(ValidationError, match="conflicts with phone-demo-fixed-v1"):
        full_config(manual_demo_preset="phone-demo-fixed-v1", **{"manual_demo_" + field: 0.40})


def test_equal_explicit_overrides_and_settings_roundtrip_preserve_policy():
    settings = full_config(manual_demo_preset="phone-demo-fixed-v1", manual_demo_pad_max=0.70)
    restored = Settings(_env_file=None, **settings.model_dump())
    assert restored.manual_demo_policy == settings.manual_demo_policy


def test_environment_conflict_is_rejected(monkeypatch):
    monkeypatch.setenv("MANUAL_DEMO_PAD_MAX", "0.50")
    with pytest.raises(ValidationError, match="conflicts with phone-demo-fixed-v1"):
        full_config(manual_demo_preset="phone-demo-fixed-v1")


@pytest.mark.parametrize("factory", [Settings, config])
def test_fixed_preset_requires_explicit_full_manual_mode(factory):
    with pytest.raises(ValidationError, match="MANUAL_FULL_DEMO"):
        factory(manual_demo_preset="phone-demo-fixed-v1")


def test_unknown_preset_rejected_and_custom_legacy_policy_preserved():
    with pytest.raises(ValidationError):
        full_config(manual_demo_preset="unrecognized")
    assert Settings(_env_file=None).manual_demo_policy is None
    custom = full_config(manual_demo_gend_max=0.90).manual_demo_policy
    assert custom.gend_max == 0.90 and custom.pad_max == 0.50


def test_worker_groups_receive_identical_frozen_preset(tmp_path):
    settings = full_config(
        manual_demo_preset="phone-demo-fixed-v1",
        media_dir=str(tmp_path),
        voice_runtime_python="local-python.exe",
        voice_spoof_python="spoof.exe",
    )
    orchestrator = Orchestrator(settings)
    try:
        spoof = orchestrator._default_detector(Module.VOICE_SPOOF)
        lipsync = orchestrator._default_detector(Module.LIPSYNC)
        assert spoof.client.manual_demo == lipsync.client.manual_demo == settings.manual_demo_policy
        assert spoof.client.manual_demo.gend_max == 0.95
    finally:
        orchestrator.close()
