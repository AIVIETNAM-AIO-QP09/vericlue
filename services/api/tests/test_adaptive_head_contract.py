"""Adaptive contracts preserve legacy wire timing and reject unbounded plans."""

import pytest
from pydantic import ValidationError

from vericlue_api.schemas.session import DynamicChallenge
from vericlue_api.services.dynamic_challenge import generate_dynamic_challenge


@pytest.mark.parametrize(
    "patch",
    [
        {"head_mode": "adaptive", "head_timeout_ms": None},
        {"head_mode": None, "head_timeout_ms": 6000},
        {"head_mode": "adaptive", "head_timeout_ms": 29500},
        {"head_mode": "adaptive", "head_timeout_ms": True},
    ],
)
def test_schema_rejects_unpaired_or_overlong_adaptive_budget(client, patch):
    plan = generate_dynamic_challenge(
        client.app.state.vericlue.settings, session_id="ses_unit", nonce="synthetic"
    ).dynamic.model_dump()
    plan.update(patch)
    with pytest.raises(ValidationError):
        DynamicChallenge.model_validate(plan)


def test_adaptive_keeps_nominal_v2_timing_and_uses_separate_eof_budget(client):
    plan = generate_dynamic_challenge(
        client.app.state.vericlue.settings,
        session_id="ses_unit",
        nonce="synthetic",
        adaptive_head=True,
    ).dynamic
    assert plan.version == 2 and plan.head_duration_ms == 12000
    assert plan.voice_start_at_ms == plan.head_start_at_ms + 12000
    assert plan.head_start_at_ms + plan.head_timeout_ms == 30000


@pytest.mark.parametrize(
    "suffix,status,outcome,expected",
    [
        ("+head12s-v2", "ok", "pass", "review"),
        ("+head-adaptive-v1", "ok", "pass", "pass"),
        ("+head-adaptive-v1", "error", "pass", "review"),
        ("+head-adaptive-v1", "degraded", "pass", "review"),
        ("+head-adaptive-v1", "ok", "review", "review"),
    ],
)
def test_manual_identity_gate_binds_adaptive_mode_and_never_upgrades_failure(
    suffix, status, outcome, expected
):
    from types import SimpleNamespace

    from test_manual_face_demo import full_config

    from vericlue_api.services.session_flow import Outcome, SessionFlow
    from vericlue_ml.common.result import Module, ModuleResult
    from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION

    flow = object.__new__(SessionFlow)
    flow.settings = full_config()
    policy = flow.settings.manual_demo_policy
    match = ModuleResult(
        module="face_match",
        model_version=VIDEO_MATCH_VERSION + suffix + policy.version_suffix,
        status=status,
        gate="pass",
        quality={
            "manual_demo": True,
            "demo_policy_id": policy.policy_id,
            "consistency_verified": True,
        },
        latency_ms=0,
    )
    plan = {
        "version": 2,
        "head_start_at_ms": 12000,
        "head_duration_ms": 12000,
        "head_mode": "adaptive",
        "head_timeout_ms": 18000,
    }
    session = SimpleNamespace(
        account_id=None,
        purpose="onboarding",
        challenge=SimpleNamespace(
            dynamic=SimpleNamespace(head_mode="adaptive", model_dump=lambda: plan)
        ),
        results={Module.FACE_MATCH: match},
        id_confirmed=True,
        id_edited=False,
        id_source="server_qr",
        manual_demo_policy_id=policy.policy_id,
    )
    result = flow._identity_gate(session, Outcome(outcome, results=session.results, thresholds={}))
    assert result.status == expected
