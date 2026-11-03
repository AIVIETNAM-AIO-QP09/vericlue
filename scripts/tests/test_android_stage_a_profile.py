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
