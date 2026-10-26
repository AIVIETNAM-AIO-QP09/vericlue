"""Optional server motion modules are mandatory signals when enabled, independent of UI."""

import pytest
from test_dynamic_flows import create, submit_face

from vericlue_ml.common.result import Module, ModuleResult


@pytest.mark.parametrize(
    "status,gate,expected",
    [
        ("ok", "pass", "pass"),  # onboarding with a clear face: no sentence
        ("degraded", "pass", "review"),
        ("error", "pass", "review"),
        ("ok", "fail", "review"),
        ("ok", "unclear", "review"),
    ],
)
def test_motion_failures_cannot_be_accepted(client, status, gate, expected):
    root = client.app.state.vericlue
    root.settings.session_face_checks = True
    seen = []

    class Motion:
        def __init__(self, module):
            self.module = module

        def predict(self, inp):
            assert inp.metadata["expected_challenge"]["dynamic"]["session_id"] == inp.session_id
            assert (
                inp.metadata["challenge_id"] == inp.metadata["expected_challenge"]["challenge_id"]
            )
            seen.append(self.module)
            return ModuleResult(
                module=self.module,
                model_version="synthetic-motion",
                status=status,
                gate=gate,
                latency_ms=0,
            )

    for module in (Module.GAZE_TRACKING, Module.HEAD_TURN):
        root.orchestrator._detectors[module] = Motion(module)
    created, auth = create(client)
    result = submit_face(client, created, auth)
    assert result["status"] == expected
    assert set(seen) == {Module.GAZE_TRACKING, Module.HEAD_TURN}
    with root.transaction() as state:
        assert {Module.GAZE_TRACKING, Module.HEAD_TURN} <= state.sessions.get(
            created["session_id"]
        ).results.keys()
