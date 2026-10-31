"""Manual experimental outcomes cannot become standard verification or enrolled accounts."""

import pytest
from pydantic import ValidationError

from vericlue_api.core.config import Settings
from vericlue_ml.common.result import Module, ModuleResult


def config(**changes):
    values = dict(
        manual_face_demo=True,
        security_profile="synthetic",
        product_mode="ekyc",
        use_mock_models=True,
        session_face_checks=True,
        session_face_models=True,
        identity_card_enabled=True,
        identity_face_from_video=True,
        identity_consistency_required=True,
        router_profile="mvp",
    )
    values.update(changes)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "changes",
    [
        {"security_profile": "protected"},
        {"product_mode": "tools"},
        {"account_enrollment": True},
        {"private_credentials": True},
        {"session_face_checks": False},
        {"session_face_models": False},
        {"identity_face_from_video": False},
        {"identity_consistency_required": False},
        {"use_mock_models": False},
        {"result_signing_key_file": "not-opened.pem"},
    ],
)
def test_manual_mode_rejects_unsafe_or_incomplete_settings(changes):
    with pytest.raises(ValidationError):
        config(**changes)


def test_manual_mode_is_off_by_default_and_valid_profile_is_explicit():
    assert Settings(_env_file=None).manual_demo_policy is None
    assert config().manual_demo_policy.policy_id


def test_manual_mode_requires_runnable_mvp_presence_profile():
    with pytest.raises(ValidationError):
        config(router_profile="full")


@pytest.mark.parametrize(
    "fault", [None, "degraded", "failed", "missing", "mock", "policy", "consistency", "edited"]
)
def test_demo_completion_is_bound_to_all_successful_real_checks(fault):
    from types import SimpleNamespace

    from vericlue_api.services.session_flow import SessionFlow
    from vericlue_ml.router.policy import TrustRouter

    flow = object.__new__(SessionFlow)
    flow.settings = config()
    flow.router = TrustRouter(profile="mvp")
    policy = flow.settings.manual_demo_policy
    results = {}
    for module in (
        Module.QUALITY,
        *flow.router.profile.presence_modules,
        Module.GAZE_TRACKING,
        Module.HEAD_TURN,
        Module.FACE_PAD,
        Module.FACE_DEEPFAKE,
        Module.FACE_MATCH,
    ):
        manual = module in (Module.FACE_PAD, Module.FACE_DEEPFAKE, Module.FACE_MATCH)
        results[module] = ModuleResult(
            module=module,
            model_version="real-test-backend" + (policy.version_suffix if manual else ""),
            status="ok",
            gate="pass",
            latency_ms=0,
            quality={
                "manual_demo": manual,
                "demo_policy_id": policy.policy_id,
                "consistency_verified": True,
                "views_from_video": True,
            },
        )
    session = SimpleNamespace(
        purpose="onboarding",
        account_id=None,
        manual_demo_policy_id=policy.policy_id,
        id_confirmed=True,
        id_edited=[],
        id_source="server_qr",
        id_front="synthetic-reference",
        results=results,
    )
    if fault in ("degraded", "failed", "mock", "policy"):
        result = results[Module.FACE_PAD]
        if fault == "degraded":
            result.status = "degraded"
        if fault == "failed":
            result.gate = "fail"
        if fault == "mock":
            result.model_version = "mock@0.1" + policy.version_suffix
        if fault == "policy":
            result.quality["demo_policy_id"] = "f" * 64
    if fault == "missing":
        results.pop(Module.GAZE_TRACKING)
    if fault == "consistency":
        results[Module.FACE_MATCH].quality["consistency_verified"] = False
    if fault == "edited":
        session.id_edited = ["full_name"]
    assert flow._manual_demo_complete(session) is (fault is None)


@pytest.mark.parametrize("complete", [True, False])
def test_demo_marker_cannot_be_attached_to_real_pass(complete):
    from vericlue_api.schemas.session import FinalizeResponse

    with pytest.raises(ValidationError):
        FinalizeResponse(
            status="pass",
            evaluation_mode="manual_demo",
            demo_policy_id="a" * 64,
            demo_complete=complete,
        )


def test_http_demo_never_returns_verified_pass_or_enrolls(client, tmp_path):
    from sqlalchemy import select
    from test_dynamic_flows import create, submit_face

    from vericlue_api.db.models import AccountRow, DecisionRow

    root = client.app.state.vericlue
    settings = config()
    for name in (
        "manual_face_demo",
        "product_mode",
        "router_profile",
        "session_face_checks",
        "session_face_models",
        "identity_card_enabled",
        "identity_face_from_video",
        "identity_consistency_required",
    ):
        setattr(root.settings, name, getattr(settings, name))
    policy = root.settings.manual_demo_policy

    class RealChecks:
        def __init__(self, module):
            self.module = module

        def predict(self, inp):
            manual = self.module in (Module.FACE_PAD, Module.FACE_DEEPFAKE, Module.FACE_MATCH)
            return ModuleResult(
                module=self.module,
                model_version="real-test" + (policy.version_suffix if manual else ""),
                status="ok",
                gate="pass",
                latency_ms=0,
                quality={
                    "manual_demo": manual,
                    "demo_policy_id": policy.policy_id,
                    "consistency_verified": True,
                    "views_from_video": True,
                },
            )

    for module in (
        Module.QUALITY,
        Module.CHROMAPULSE,
        Module.CAMPROBE,
        Module.GAZE_TRACKING,
        Module.HEAD_TURN,
        Module.FACE_PAD,
        Module.FACE_DEEPFAKE,
        Module.FACE_MATCH,
    ):
        root.orchestrator._detectors[module] = RealChecks(module)
    created, auth = create(client)
    assert created["evaluation_mode"] == "manual_demo"
    with root.transaction() as state:
        session = state.sessions.get(created["session_id"])
        session.id_confirmed = True
        session.id_source = "server_qr"
        session.id_front = tmp_path / "synthetic-reference.jpg"
    result = submit_face(client, created, auth)
    assert result["status"] == "review" and result["demo_complete"] is True
    assert (
        result["evaluation_mode"] == "manual_demo" and result["demo_policy_id"] == policy.policy_id
    )
    with root.database.sessions() as db:
        assert db.scalar(select(AccountRow)) is None
        assert (
            db.scalars(select(DecisionRow).where(DecisionRow.session_id == created["session_id"]))
            .one()
            .action
            == "review"
        )
    # Config changes cannot reinterpret an existing manual session as a standard one.
    root.settings.manual_face_demo = False
    denied = client.post(
        f"/v1/sessions/{created['session_id']}/signals",
        headers=auth,
        json={
            "challenge_id": created["challenge"]["challenge_id"],
            "color_events": [],
            "frame_times": [],
        },
    )
    assert denied.status_code == 409


def test_manual_full_demo_supports_enrollment_and_voice_spoof_policy():
    from vericlue_ml.common.result import Evidence

    full = Settings(
        _env_file=None,
        manual_full_demo=True,
        security_profile="synthetic",
        product_mode="ekyc",
        use_mock_models=True,
        session_face_checks=True,
        session_face_models=True,
        session_voice_models=True,
        identity_card_enabled=True,
        identity_face_from_video=True,
        identity_consistency_required=True,
        identity_voice_continuity=True,
        account_enrollment=True,
        router_profile="mvp",
    )
    policy = full.manual_demo_policy
    assert policy is not None
    with pytest.raises(ValidationError):
        config(manual_full_demo=True)

    bonafide_timeline = ModuleResult(
        module="voice_spoof",
        model_version="nes2net-x@timeline",
        status="degraded",
        gate="unclear",
        quality={"error_windows": 0, "measured_windows": 1},
        evidence=[
            Evidence(
                type="segments",
                name="nes2net_windows",
                value=[
                    {
                        "start_sample": 0,
                        "end_sample": 64000,
                        "start_s": 0.0,
                        "end_s": 4.0,
                        "result": {
                            "module": "voice_spoof",
                            "model_version": "nes2net-x@first4s",
                            "status": "degraded",
                            "gate": "unclear",
                            "score": -2.5,
                            "latency_ms": 10.0,
                        },
                    }
                ],
            )
        ],
        latency_ms=10.0,
    )
    assert policy.accepts_voice_spoof(bonafide_timeline)
    spoof_timeline = bonafide_timeline.model_copy(
        update={
            "evidence": [
                Evidence(
                    type="segments",
                    name="nes2net_windows",
                    value=[
                        {
                            "start_sample": 0,
                            "end_sample": 64000,
                            "start_s": 0.0,
                            "end_s": 4.0,
                            "result": {
                                "module": "voice_spoof",
                                "model_version": "nes2net-x@first4s",
                                "status": "degraded",
                                "gate": "unclear",
                                "score": 4.5,
                                "latency_ms": 10.0,
                            },
                        }
                    ],
                )
            ]
        }
    )
    assert not policy.accepts_voice_spoof(spoof_timeline)
