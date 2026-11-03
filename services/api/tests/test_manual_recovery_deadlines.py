"""Manual recovery keeps capture deadlines despite successful synthetic model gates.

No native models/media: only inference latency and previously verified account/media
boundaries are replaced; SessionFlow routing, deadlines, and decision storage are real.
"""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_manual_face_demo import full_config

from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import DecisionRow
from vericlue_api.services import session_flow
from vericlue_api.services.dynamic_challenge import generate_dynamic_challenge
from vericlue_ml.common.result import Evidence, Gate, Module, ModuleResult, Status
from vericlue_ml.face.enrolled import recovery_match_version
from vericlue_ml.router.policy import TrustRouter


@pytest.fixture
def recovery_flow(client, monkeypatch, tmp_path):
    @contextmanager
    def configured(*, ttl, face_seconds=3, identity_seconds=6, start_seconds=115):
        settings = full_config(manual_demo_content_backend="qwen17", challenge_ttl_seconds=ttl)
        origin = datetime.now(UTC)

        class Clock(datetime):
            current = origin + timedelta(seconds=start_seconds)

            @classmethod
            def now(cls, tz=None):
                return cls.current if tz is not None else cls.current.replace(tzinfo=None)

        monkeypatch.setattr(session_flow, "datetime", Clock)
        # Signed media/account verification has separate integration coverage. The tests
        # start after those boundaries and exercise timing through the real finalize body.
        monkeypatch.setattr(session_flow, "require_consumed", lambda *a, **k: None)
        with client.app.state.vericlue.transaction() as state:
            flow = state.flow
            flow.settings = settings
            flow.router = TrustRouter(profile="mvp")
            challenge = generate_dynamic_challenge(
                settings, session_id="synthetic", nonce="synthetic-deadline", adaptive_head=True
            )
            session = state.sessions.create(
                scenario="genuine",
                challenge=challenge,
                ttl_seconds=300,
                signer=settings.session_token_signer,
            )
            challenge.dynamic.session_id = session.session_id
            challenge.expires_at = origin + timedelta(seconds=ttl)
            session.token_expires_at = origin + timedelta(seconds=300)
            session.purpose = "recovery"
            session.account_id = "acct_synthetic_deadline"
            session.registered_device_id = "dev_synthetic_deadline"
            session.created_model_mode = "manual_full_demo"
            session.manual_demo_policy_id = settings.manual_demo_policy.policy_id
            session.created_voice_content_version = settings.voice_content_model_version
            session.accepted_steps = ["media", "signals"]
            session.images = [tmp_path / "synthetic-face.jpg"]
            session.video = tmp_path / "synthetic-face.mp4"
            monkeypatch.setattr(
                flow.account_auth, "current", lambda session: SimpleNamespace(template=object())
            )
            policy = settings.manual_demo_policy
            calls = []

            def successful_models(modules, **kwargs):
                identity = Module.FACE_MATCH in modules
                calls.append("identity" if identity else "face")
                Clock.current += timedelta(seconds=identity_seconds if identity else face_seconds)
                output = {}
                for module in modules:
                    manual = module in (Module.FACE_PAD, Module.FACE_DEEPFAKE, Module.FACE_MATCH)
                    version = (
                        recovery_match_version(3) if module == Module.FACE_MATCH else "real-test"
                    )
                    output[module] = ModuleResult(
                        module=module,
                        model_version=version + (policy.version_suffix if manual else ""),
                        status="ok",
                        gate="pass",
                        latency_ms=0,
                        quality={
                            "manual_demo": manual,
                            "demo_policy_id": policy.policy_id,
                            "enrolled_reference": True,
                            "consistency_verified": True,
                        },
                        evidence=[
                            Evidence(
                                type="text", name="reference_account_id", value=session.account_id
                            )
                        ]
                        if module == Module.FACE_MATCH
                        else [],
                    )
                return output

            flow._run = successful_models
            yield SimpleNamespace(
                flow=flow,
                session=session,
                clock=Clock,
                origin=origin,
                calls=calls,
                db=state.db,
            )

    return configured


@pytest.mark.parametrize(
    "phase,face_seconds,identity_seconds", [("face", 6, 3), ("identity", 3, 6)]
)
@pytest.mark.parametrize("ttl,expected", [(120, "review"), (180, "voice_challenge")])
def test_all_passing_adaptive_recovery_still_obeys_issued_deadline(
    recovery_flow, phase, face_seconds, identity_seconds, ttl, expected
):
    with recovery_flow(
        ttl=ttl, face_seconds=face_seconds, identity_seconds=identity_seconds
    ) as case:
        assert (
            case.flow.settings.manual_demo_policy
            == full_config(
                manual_demo_content_backend="qwen17", challenge_ttl_seconds=120
            ).manual_demo_policy
        )
        token_expiry = case.session.token_expires_at
        result = case.flow.finalize(case.session, case.session.challenge.challenge_id)
        assert result.status == expected
        assert case.calls == ["face", "identity"]
        assert case.clock.current == case.origin + timedelta(seconds=124)
        assert set(case.session.results) == {
            Module.QUALITY,
            Module.CAMPROBE,
            Module.GAZE_TRACKING,
            Module.HEAD_TURN,
            Module.FACE_PAD,
            Module.FACE_DEEPFAKE,
            Module.FACE_MATCH,
        }
        assert all(
            r.status == Status.OK and r.gate == Gate.PASS for r in case.session.results.values()
        )
        assert case.session.challenge.dynamic.head_mode == "adaptive"
        assert (
            case.session.created_voice_content_version
            == case.flow.settings.voice_content_model_version
        )
        assert case.session.token_expires_at == token_expiry == case.origin + timedelta(seconds=300)
        assert case.session.completed is (expected == "review")
        assert case.session.voice_requested is (expected == "voice_challenge")
        assert case.session.voice_owed is (expected == "voice_challenge")
        decisions = list(
            case.db.scalars(
                select(DecisionRow).where(DecisionRow.session_id == case.session.session_id)
            )
        )
        assert [d.action for d in decisions] == [expected]
        assert (
            decisions[0].thresholds["manual_thresholds"]
            == case.flow.settings.manual_demo_policy.model_dump()
        )
        if expected == "voice_challenge":
            # The shared setting also applies to a future voice challenge. It cannot
            # extend the signed session token, which remains the effective upper bound.
            assert case.session.voice_expires_at == case.clock.current + timedelta(seconds=180)
            case.clock.current = token_expiry - timedelta(microseconds=1)
            assert case.flow._valid_time(case.session, voice_challenge=True)
            case.clock.current = token_expiry
            assert not case.flow._valid_time(case.session, voice_challenge=True)


@pytest.mark.parametrize("issued_ttl,configured_ttl", [(120, 120), (120, 180), (180, 180)])
def test_expired_capture_request_is_not_revived_by_future_demo_ttl(
    recovery_flow, issued_ttl, configured_ttl
):
    with recovery_flow(ttl=issued_ttl, start_seconds=issued_ttl) as case:
        original_deadline = case.session.challenge.expires_at
        case.flow.settings.challenge_ttl_seconds = configured_ttl
        with pytest.raises(ApiError) as caught:
            case.flow.finalize(case.session, case.session.challenge.challenge_id)
        assert caught.value.error_code == "challenge_expired"
        assert case.session.challenge.expires_at == original_deadline
        assert not case.calls
        assert not case.session.completed
        assert not case.session.voice_requested and not case.session.voice_owed
        assert "finalize" not in case.session.accepted_steps
        assert (
            list(
                case.db.scalars(
                    select(DecisionRow).where(DecisionRow.session_id == case.session.session_id)
                )
            )
            == []
        )
