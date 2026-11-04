import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "stage_a_smoke", Path(__file__).parents[1] / "smoke_android_stage_a.py"
)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


@pytest.mark.parametrize(
    "override",
    [
        {"SIMULATED_OTP": "false"},
        {"SIMULATED_OTP": None},
        {"PRIVACY_POLICY_VERSION": "remote-test-v1"},
        {"SECURITY_PROFILE": "protected"},
        {"IDENTITY_CARD_ENABLED": "false"},
    ],
)
def test_preflight_rejects_broken_or_non_demo_profile_before_network(override):
    config = {
        "SECURITY_PROFILE": "synthetic",
        "SIMULATED_OTP": "true",
        "PRIVACY_POLICY_VERSION": "demo-v1",
        "IDENTITY_CARD_ENABLED": "true",
    }
    with pytest.raises(ValueError):
        smoke.check_profile(config | override)


@pytest.mark.parametrize(
    "override",
    [{"evaluation_mode": "standard"}, {"demo_policy_id": "old"}, {}],
)
def test_running_session_must_bind_expected_manual_preset(override):
    from vericlue_ml.common.manual_demo import PHONE_DEMO_FIXED_V1

    session = {
        "evaluation_mode": "manual_full_demo",
        "demo_policy_id": PHONE_DEMO_FIXED_V1.policy_id,
    }
    if override:
        with pytest.raises(ValueError):
            smoke.check_manual_session(session | override)
    else:
        smoke.check_manual_session(session)
