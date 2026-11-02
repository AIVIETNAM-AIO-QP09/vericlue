"""ASR version pinning must not change account cutoff-policy identity."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from test_manual_face_demo import full_config, manual_voice_result

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.services.session_flow import SessionFlow
from vericlue_ml.common.result import Module, ModuleResult
from vericlue_ml.router.policy import TrustRouter
from vericlue_ml.voice.qwen_asr import VERSION as VERSION06

VERSION17 = (
    "qwen3-asr-17b@bcd2b5b7f32b480ab5790554cfa8347f246a14f3+cpu-fp32-content-v2-assistant-prefix"
)


def flow_for(settings):
    flow = object.__new__(SessionFlow)
    flow.settings, flow.router = settings, TrustRouter(profile="mvp")
    return flow


def session_for(settings, pin):
    return SimpleNamespace(
        purpose="recovery",
        manual_demo_policy_id=settings.manual_demo_policy.policy_id,
        created_model_mode="manual_full_demo",
        created_voice_content_version=pin,
        voice_rereads_used=0,
    )


def test_default_and_optin_share_the_exact_six_cutoff_policy():
    original, selected = full_config(), full_config(manual_demo_content_backend="qwen17")
    assert original.manual_demo_content_backend == "qwen06"
    assert original.voice_content_model_version == VERSION06
    assert selected.voice_content_model_version == VERSION17
    assert (
        original.manual_demo_policy.model_dump_json()
        == selected.manual_demo_policy.model_dump_json()
    )
    assert original.manual_demo_policy.policy_id == selected.manual_demo_policy.policy_id


def test_standard_settings_cannot_enable_candidate():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, manual_demo_content_backend="qwen17")
    with pytest.raises(ValidationError):
        full_config(manual_demo_content_backend="unrecognized")


@pytest.mark.parametrize("pin", [None, VERSION06, "unrecognized"])
def test_candidate_rejects_old_or_unpinned_inflight_sessions_without_backfill(pin):
    settings = full_config(manual_demo_content_backend="qwen17")
    session = session_for(settings, pin)
    with pytest.raises(ApiError) as error:
        flow_for(settings)._ensure_evaluation_binding(session)
    assert error.value.error_code == "session_expired"
    assert session.created_voice_content_version == pin


def test_pinned_candidate_session_survives_same_selection_and_rejects_rollback():
    selected = full_config(manual_demo_content_backend="qwen17")
    session = session_for(selected, VERSION17)
    flow_for(selected)._ensure_evaluation_binding(session)
    with pytest.raises(ApiError):
        flow_for(full_config())._ensure_evaluation_binding(session)


@pytest.mark.parametrize(
    "version,status,expected",
    [
        (VERSION17, "ok", "pass"),
        (VERSION06, "ok", "review"),
        (VERSION17, "degraded", "review"),
        (VERSION17, "error", "review"),
    ],
)
def test_manual_decision_requires_selected_content_and_keeps_failure_states(
    version, status, expected
):
    settings = full_config(manual_demo_content_backend="qwen17")
    policy = settings.manual_demo_policy
    results = {
        mod: manual_voice_result(policy, mod) for mod in (Module.LIPSYNC, Module.VOICE_SPOOF)
    }
    results[Module.VOICE_CHALLENGE] = ModuleResult(
        module="voice_challenge",
        model_version=version,
        status=status,
        gate="pass" if status == "ok" else "unclear",
        latency_ms=0,
    )
    outcome = flow_for(settings)._manual_full_demo_voice(
        session_for(settings, VERSION17), results, session_valid=True
    )
    assert outcome.status == expected


def test_new_session_content_pin_roundtrips_only_inside_encrypted_snapshot(monkeypatch):
    import base64
    import json
    import secrets

    from fastapi.testclient import TestClient

    from vericlue_api.core.config import get_settings
    from vericlue_api.db.models import SessionRow
    from vericlue_api.main import create_app

    monkeypatch.setenv("SESSION_PRIVACY", "true")
    monkeypatch.setenv("SESSION_MASTER_KEY", base64.b64encode(secrets.token_bytes(32)).decode())
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        root = client.app.state.vericlue
        with root.transaction() as state:
            state.flow.settings = full_config(manual_demo_content_backend="qwen17")
            created = state.flow.create("genuine")
            stored = state.sessions.get(created.session_id)
            assert stored.created_voice_content_version == VERSION17
            assert "created_voice_content_version" not in created.model_dump()
            session_id = created.session_id
        with root.transaction() as state:
            assert state.sessions.get(session_id).created_voice_content_version == VERSION17
            payload = state.db.get(SessionRow, session_id).payload
            assert VERSION17 not in json.dumps(payload)
