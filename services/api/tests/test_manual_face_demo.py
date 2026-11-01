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


def full_config(**changes):
    values = dict(
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
    values.update(changes)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "changes",
    [
        {"security_profile": "protected"},
        {"product_mode": "tools"},
        {"router_profile": "full"},
        {"private_credentials": True},
        {"session_face_checks": False},
        {"session_face_models": False},
        {"session_voice_models": False},
        {"identity_card_enabled": False},
        {"identity_face_from_video": False},
        {"identity_consistency_required": False},
        {"identity_voice_continuity": False},
        {"account_enrollment": False},
        {"use_mock_models": False},
        {"result_signing_key_file": "not-opened.pem"},
    ],
)
def test_manual_full_demo_rejects_unsafe_or_incomplete_settings(changes):
    with pytest.raises(ValidationError):
        full_config(**changes)


def test_manual_full_demo_is_blocked_by_security_profile_checks():
    from vericlue_api.core.security_profile import security_profile_checks

    checks = security_profile_checks(full_config())
    assert checks["real_model_mode"] is False
    assert checks["no_manual_demo"] is False


def test_manual_full_demo_supports_enrollment_and_voice_spoof_policy():
    from vericlue_ml.common.result import Evidence

    full = full_config()
    policy = full.manual_demo_policy
    assert policy is not None
    with pytest.raises(ValidationError):
        config(manual_full_demo=True)

    degraded_timeline = ModuleResult(
        module="voice_spoof",
        model_version="nes2net-x@timeline",
        status="degraded",
        gate="unclear",
        quality={"error_windows": 0, "measured_windows": 1, "diagnostic_only": True},
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
    assert not policy.accepts_voice_spoof(degraded_timeline)

    ok_timeline = ModuleResult(
        module="voice_spoof",
        model_version="nes2net-x@timeline",
        status="ok",
        gate="pass",
        quality={
            "diagnostic_only": False,
            "planned_windows": 1,
            "measured_windows": 1,
            "low_quality_windows": 0,
            "error_windows": 0,
            "all_source_samples_measured": True,
        },
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
                            "status": "ok",
                            "gate": "pass",
                            "score": -2.5,
                            "quality": {"diagnostic_only": False},
                            "latency_ms": 10.0,
                        },
                    }
                ],
            )
        ],
        latency_ms=10.0,
    )
    assert policy.accepts_voice_spoof(ok_timeline)


def test_manual_full_demo_binds_policy_and_rejects_mid_session_changes(client, tmp_path):
    from sqlalchemy import select
    from test_dynamic_flows import create, submit_face

    from vericlue_api.db.models import DecisionRow

    root = client.app.state.vericlue
    settings = full_config()
    for name in (
        "manual_full_demo",
        "product_mode",
        "router_profile",
        "session_face_checks",
        "session_face_models",
        "session_voice_models",
        "identity_card_enabled",
        "identity_face_from_video",
        "identity_consistency_required",
    ):
        setattr(root.settings, name, getattr(settings, name))
    root.settings.identity_voice_continuity = False
    root.settings.account_enrollment = False
    policy = root.settings.manual_demo_policy
    assert policy is not None

    class RealManualChecks:
        def __init__(self, module):
            self.module = module

        def predict(self, inp):
            from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION

            current = root.settings.manual_demo_policy
            manual = self.module in (Module.FACE_PAD, Module.FACE_DEEPFAKE, Module.FACE_MATCH)
            base_version = VIDEO_MATCH_VERSION if self.module == Module.FACE_MATCH else "real-test"
            return ModuleResult(
                module=self.module,
                model_version=base_version + (current.version_suffix if manual else ""),
                status="ok",
                gate="pass",
                latency_ms=0,
                quality={
                    "manual_demo": manual,
                    "calibrated": not manual,
                    "demo_policy_id": current.policy_id if manual else None,
                    "consistency_verified": True,
                    "views_from_video": True,
                },
            )

    for module in (
        Module.QUALITY,
        Module.CAMPROBE,
        Module.GAZE_TRACKING,
        Module.HEAD_TURN,
        Module.FACE_PAD,
        Module.FACE_DEEPFAKE,
        Module.FACE_MATCH,
    ):
        root.orchestrator._detectors[module] = RealManualChecks(module)

    created, auth = create(client)
    assert created["evaluation_mode"] == "manual_full_demo"
    assert created["demo_policy_id"] == policy.policy_id
    with root.transaction() as state:
        session = state.sessions.get(created["session_id"])
        assert session.created_model_mode == "manual_full_demo"
        assert session.manual_demo_policy_id == policy.policy_id
        session.id_confirmed = True
        session.id_source = "server_qr"
        session.id_front = tmp_path / "synthetic-reference.jpg"

    # Changing a threshold mid-session invalidates the session before finalize.
    root.settings.manual_demo_pad_max = 0.65
    changed = client.post(
        f"/v1/sessions/{created['session_id']}/signals",
        headers=auth,
        json={
            "challenge_id": created["challenge"]["challenge_id"],
            "color_events": [],
            "frame_times": [],
        },
    )
    assert changed.status_code == 409 and changed.json()["error_code"] == "session_expired"

    # Restoring the original threshold allows the bound session to proceed.
    root.settings.manual_demo_pad_max = policy.pad_max
    result = submit_face(client, created, auth)
    assert result["status"] == "pass"
    assert result["evaluation_mode"] == "manual_full_demo"
    assert result["demo_policy_id"] == policy.policy_id
    with root.database.sessions() as db:
        decision = db.scalars(
            select(DecisionRow).where(DecisionRow.session_id == created["session_id"])
        ).one()
        assert decision.thresholds["evaluation_mode"] == "manual_full_demo"
        assert decision.thresholds["demo_policy_id"] == policy.policy_id
        assert decision.thresholds["calibrated"] is False

    # Turning off manual_full_demo mid-session also invalidates an open session.
    created2, auth2 = create(client)
    root.settings.manual_full_demo = False
    denied = client.post(
        f"/v1/sessions/{created2['session_id']}/signals",
        headers=auth2,
        json={
            "challenge_id": created2["challenge"]["challenge_id"],
            "color_events": [],
            "frame_times": [],
        },
    )
    assert denied.status_code == 409 and denied.json()["error_code"] == "session_expired"


def test_manual_full_demo_requires_lipsync_in_recovery_and_protects_existing_accounts(
    monkeypatch,
):
    import base64
    import secrets

    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from test_accounts import prepared, real_settings, verdict

    from vericlue_api.core.config import get_settings
    from vericlue_api.core.errors import ApiError
    from vericlue_api.db.models import AccountRow, SessionRow
    from vericlue_api.main import create_app
    from vericlue_api.services.accounts import AccountStore
    from vericlue_ml.common.result import Evidence
    from vericlue_ml.face.continuity import FACE_VOICE_VERSION
    from vericlue_ml.face.enrolled import RECOVERY_MATCH_VERSION
    from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION

    monkeypatch.setenv("SESSION_PRIVACY", "true")
    monkeypatch.setenv("SESSION_MASTER_KEY", base64.b64encode(secrets.token_bytes(32)).decode())
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        root = client.app.state.vericlue
        with root.transaction() as state:
            session, template, continuity = prepared(state)
            demo_settings = full_config(
                session_privacy=True,
                session_master_key=state.settings.session_master_key,
                id_hmac_key=SecretStr("synthetic-test-key-at-least-32-bytes"),
            )
            policy = demo_settings.manual_demo_policy
            suffix = policy.version_suffix
            session.created_model_mode = "manual_full_demo"
            session.manual_demo_policy_id = policy.policy_id
            for mod in (Module.FACE_PAD, Module.FACE_DEEPFAKE):
                session.results[mod] = verdict(
                    mod,
                    "real-attack" + suffix,
                    prob_attack=None,
                    quality={
                        "manual_demo": True,
                        "calibrated": False,
                        "demo_policy_id": policy.policy_id,
                    },
                )
            session.results[Module.FACE_MATCH] = session.results[Module.FACE_MATCH].model_copy(
                update={
                    "model_version": VIDEO_MATCH_VERSION + suffix,
                    "prob_attack": None,
                    "quality": {
                        "consistency_verified": True,
                        "manual_demo": True,
                        "calibrated": False,
                        "demo_policy_id": policy.policy_id,
                    },
                }
            )
            continuity = continuity.model_copy(
                update={
                    "model_version": FACE_VOICE_VERSION + suffix,
                    "prob_attack": None,
                    "quality": {
                        "manual_demo": True,
                        "calibrated": False,
                        "demo_policy_id": policy.policy_id,
                    },
                }
            )
            session.results[Module.FACE_CONTINUITY] = continuity

            store = AccountStore(demo_settings, state.db)

            # 1. Degraded or unclear lipsync must be rejected for voiced account enrollment.
            degraded_lipsync = verdict(Module.LIPSYNC, status="degraded", gate="unclear")
            session.results[Module.LIPSYNC] = degraded_lipsync
            with pytest.raises(ApiError) as caught:
                store.create(session, template, continuity=continuity)
            assert caught.value.error_code == "enrollment_not_available"

            # 2. Degraded voice_spoof must be rejected for voiced account enrollment.
            session.results[Module.LIPSYNC] = verdict(Module.LIPSYNC)
            session.results[Module.VOICE_SPOOF] = verdict(
                Module.VOICE_SPOOF, status="degraded", gate="unclear", prob_attack=None
            )
            with pytest.raises(ApiError) as caught:
                store.create(session, template, continuity=continuity)
            assert caught.value.error_code == "enrollment_not_available"

            # 3. Valid OK+PASS lipsync and OK voice_spoof succeeds.
            session.results[Module.VOICE_SPOOF] = verdict(Module.VOICE_SPOOF)
            receipt = store.create(session, template, continuity=continuity)
            first_row = state.db.get(AccountRow, receipt.account_id)
            assert first_row is not None and first_row.destroyed_at is None

            # 4. Experimental account is isolated from calibrated standard AccountStore.
            standard_store = AccountStore(real_settings(state), state.db)
            with pytest.raises(ApiError):
                standard_store.get(receipt.account_id)

            # 5. Re-registration with the same CCCD must NOT destroy the existing account.
            session2, template2, continuity2 = prepared(state, id_hmac=session.id_number_hmac)
            session2.created_model_mode = "manual_full_demo"
            session2.manual_demo_policy_id = policy.policy_id
            for mod in (Module.FACE_PAD, Module.FACE_DEEPFAKE):
                session2.results[mod] = session.results[mod]
            session2.results[Module.FACE_MATCH] = session2.results[Module.FACE_MATCH].model_copy(
                update={
                    "model_version": VIDEO_MATCH_VERSION + suffix,
                    "prob_attack": None,
                    "quality": {
                        "consistency_verified": True,
                        "manual_demo": True,
                        "calibrated": False,
                        "demo_policy_id": policy.policy_id,
                    },
                }
            )
            continuity2 = continuity2.model_copy(
                update={
                    "model_version": FACE_VOICE_VERSION + suffix,
                    "prob_attack": None,
                    "quality": {
                        "manual_demo": True,
                        "calibrated": False,
                        "demo_policy_id": policy.policy_id,
                    },
                }
            )
            session2.results[Module.FACE_CONTINUITY] = continuity2
            with pytest.raises(ApiError) as dup_err:
                store.create(session2, template2, continuity=continuity2)
            assert dup_err.value.error_code == "enrollment_not_available"
            state.db.refresh(first_row)
            assert first_row.destroyed_at is None
            assert store.get(receipt.account_id).receipt.account_id == receipt.account_id

            # 6. Recovery in manual_full_demo also requires OK+PASS lipsync.
            rec_session, _, rec_continuity = prepared(state, id_hmac="e" * 64)
            rec_session.purpose = "recovery"
            rec_session.account_id = receipt.account_id
            rec_session.registered_device_id = receipt.device_id
            rec_session.created_model_mode = "manual_full_demo"
            rec_session.manual_demo_policy_id = policy.policy_id
            for mod in (Module.FACE_PAD, Module.FACE_DEEPFAKE):
                rec_session.results[mod] = session.results[mod]
            rec_session.results[Module.FACE_MATCH] = rec_session.results[
                Module.FACE_MATCH
            ].model_copy(
                update={
                    "model_version": RECOVERY_MATCH_VERSION + suffix,
                    "prob_attack": None,
                    "quality": {
                        "consistency_verified": True,
                        "enrolled_reference": True,
                        "manual_demo": True,
                        "calibrated": False,
                        "demo_policy_id": policy.policy_id,
                    },
                    "evidence": [
                        *rec_session.results[Module.FACE_MATCH].evidence,
                        Evidence(
                            type="text", name="reference_account_id", value=receipt.account_id
                        ),
                    ],
                }
            )
            rec_continuity = rec_continuity.model_copy(
                update={
                    "model_version": FACE_VOICE_VERSION + suffix,
                    "prob_attack": None,
                    "quality": {
                        "manual_demo": True,
                        "calibrated": False,
                        "demo_policy_id": policy.policy_id,
                    },
                }
            )
            rec_session.results[Module.FACE_CONTINUITY] = rec_continuity
            rec_session.results[Module.LIPSYNC] = degraded_lipsync
            with pytest.raises(ApiError) as rec_err:
                store.recover(rec_session)
            assert rec_err.value.error_code == "enrollment_not_available"

            rec_session.results[Module.LIPSYNC] = verdict(Module.LIPSYNC)
            recovered = store.recover(rec_session)
            assert recovered.account_id == receipt.account_id
            assert recovered.device_id != receipt.device_id

            # SessionFlow.voice() in recovery downgrades to review when lipsync is degraded or splice_flags > 0.
            state.flow.settings = demo_settings
            state.accounts.settings = demo_settings
            voice_session, _, _ = prepared(state, id_hmac="f" * 64)
            voice_session.purpose = "recovery"
            voice_session.account_id = receipt.account_id
            voice_session.registered_device_id = recovered.device_id
            voice_session.created_model_mode = "manual_full_demo"
            voice_session.manual_demo_policy_id = policy.policy_id
            voice_session.completed = False
            voice_session.voice_requested = voice_session.voice_owed = True
            voice_session.voice_expires_at = session.token_expires_at
            voice_session.accepted_steps.remove("voice")
            state.db.get(SessionRow, voice_session.session_id).status = "incomplete"
            voice_session.results[Module.FACE_MATCH] = rec_session.results[Module.FACE_MATCH]
            state.flow._run = lambda modules, **kwargs: {
                Module.VOICE_CHALLENGE: verdict(Module.VOICE_CHALLENGE),
                Module.VOICE_SPOOF: verdict(Module.VOICE_SPOOF),
                Module.LIPSYNC: degraded_lipsync,
                Module.FACE_CONTINUITY: rec_continuity.model_copy(
                    update={
                        "evidence": [
                            Evidence(
                                type="text",
                                name="source_video_sha256",
                                value="c" * 64,
                            ),
                            Evidence(
                                type="text",
                                name="challenge_id",
                                value=voice_session.challenge.challenge_id,
                            ),
                            Evidence(
                                type="text",
                                name="voice_challenge_id",
                                value=voice_session.voice_challenge_id,
                            ),
                        ]
                    }
                ),
            }
            voice_out = state.flow.voice(voice_session)
            assert voice_out.status == "review"
            assert state.db.get(AccountRow, receipt.account_id).device_id == recovered.device_id

            # Explicit scoped manual demo reset destroys only manual_full_demo accounts.
            assert store.destroy_manual_demo_account(account_id=receipt.account_id) == 1
            assert state.db.get(AccountRow, receipt.account_id).destroyed_at is not None
