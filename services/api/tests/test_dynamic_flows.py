"""Backend contract and state transitions for model-independent FLOW-01/LIVE-01."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from contract_utils import validate
from fastapi.testclient import TestClient
from sqlalchemy import select
from synthetic_images import synthetic_image

from vericlue_api.core.config import get_settings
from vericlue_api.db.models import DecisionRow, ReviewCaseRow, SessionRow
from vericlue_api.main import create_app
from vericlue_api.services.dynamic_challenge import generate_dynamic_challenge
from vericlue_ml.common.result import Gate, Module, ModuleResult, Status

IMAGE = {"image": ("face.jpg", synthetic_image(b"synthetic image"), "image/jpeg")}
AUDIO = {"audio": ("voice.wav", b"synthetic audio", "audio/wav")}
NONCE = "integration_nonce_12345678"


def create(client, purpose="onboarding", scenario="genuine"):
    response = client.post(
        "/v1/sessions",
        json={"purpose": purpose, "nonce": NONCE},
        headers={"X-Mock-Scenario": scenario},
    )
    assert response.status_code == 200, response.text
    validate(response.json(), "session", "CreateSessionResponse")
    body = response.json()
    return body, {"Authorization": "Bearer " + body["token"]}


def url(created, step):
    return f"/v1/sessions/{created['session_id']}/{step}"


def submit_face(client, created, auth, challenge=None):
    challenge = challenge or created["challenge"]
    cid = challenge["challenge_id"]
    assert (
        client.post(
            url(created, "media"), headers=auth, data={"challenge_id": cid}, files=IMAGE
        ).status_code
        == 200
    )
    assert (
        client.post(
            url(created, "signals"),
            headers=auth,
            json={"challenge_id": cid, "color_events": [], "frame_times": []},
        ).status_code
        == 200
    )
    response = client.post(url(created, "finalize"), headers=auth, json={"challenge_id": cid})
    assert response.status_code == 200, response.text
    validate(response.json(), "session", "FinalizeResponse")
    return response.json()


def submit_voice(client, created, auth, result):
    return client.post(
        url(created, "voice"),
        headers=auth,
        data={"voice_challenge_id": result["voice_challenge_id"]},
        files=AUDIO,
    )


def edit_session(client, created, **patch):
    with client.app.state.vericlue.database.sessions.begin() as db:
        row = db.get(SessionRow, created["session_id"])
        row.payload = {**row.payload, **patch}


def test_onboarding_with_a_clear_face_passes_without_a_sentence(client):
    created, auth = create(client, "onboarding", scenario="genuine")
    result = submit_face(client, created, auth)
    assert result == {"status": "pass"}
    response = submit_voice(client, created, auth, created["challenge"]["dynamic"])
    assert response.status_code == 409  # nothing to read: no shortcut through /voice
    with client.app.state.vericlue.database.sessions() as db:
        actions = db.scalars(
            select(DecisionRow.action).where(DecisionRow.session_id == created["session_id"])
        ).all()
        assert actions == ["pass"]


@pytest.mark.parametrize("purpose", ["onboarding", "recovery"])
def test_full_mock_flow_requires_voice_and_uses_preissued_prompt(client, purpose):
    # Onboarding reads only when the face is unclear (voice_clone: B < face < A); recovery always.
    scenario = "voice_clone" if purpose == "onboarding" else "genuine"
    created, auth = create(client, purpose, scenario=scenario)
    plan = created["challenge"]["dynamic"]
    assert plan["session_id"] == created["session_id"] and plan["nonce"] == NONCE
    assert created["purpose"] == purpose and created["nonce"] == NONCE
    # The prompt is available before the server has received/scored any face media.
    result = submit_face(client, created, auth)
    assert result["status"] == "voice_challenge"
    assert result["voice_prompt"] == plan["voice_prompt"]
    assert result["voice_challenge_id"] == plan["voice_challenge_id"]
    if purpose == "onboarding":
        edit_session(client, created, scenario="genuine")  # ambiguous face, then a genuine voice
    response = submit_voice(client, created, auth, result)
    validate(response.json(), "session", "VoiceResponse")
    assert response.json() == {"status": "pass"}
    assert submit_voice(client, created, auth, result).status_code == 409
    with client.app.state.vericlue.database.sessions() as db:
        actions = db.scalars(
            select(DecisionRow.action).where(DecisionRow.session_id == created["session_id"])
        ).all()
        assert actions == ["voice_challenge", "pass"]


def test_gaze_head_schedule_is_after_safe_color_sequence(client):
    created, _ = create(client)
    ch = created["challenge"]
    plan = ch["dynamic"]
    points = plan["gaze_points"]
    assert all(
        max(p[axis] for p in points) - min(p[axis] for p in points) >= 0.30 for axis in ("x", "y")
    )
    color_end = ch["baseline_ms"] + sum(
        x["hold_ms"] + x["transition_ms"] for x in ch["color_sequence"]
    )
    assert 0 <= plan["frontal_capture_at_ms"] < ch["baseline_ms"]
    assert points[0]["at_ms"] == color_end
    assert all(a["at_ms"] < b["at_ms"] for a, b in zip(points, points[1:], strict=False))
    assert plan["head_start_at_ms"] == points[-1]["at_ms"]
    assert set(plan["head_turns"][:2]) == {"left", "right"}
    assert plan["head_turns"][-1] == "center"
    assert plan["version"] == 2
    assert plan["head_duration_ms"] == 12000
    assert plan["voice_start_at_ms"] == plan["head_start_at_ms"] + 12000
    assert plan["voice_start_at_ms"] <= 30000


def test_challenges_are_distinct_even_with_the_same_caller_nonce(client):
    plans = [create(client)[0]["challenge"] for _ in range(8)]
    assert len({p["challenge_id"] for p in plans}) == 8
    assert len({p["dynamic"]["voice_challenge_id"] for p in plans}) == 8
    assert len({p["dynamic"]["session_id"] for p in plans}) == 8


@pytest.mark.parametrize("hold_ms", [400, 650])
def test_long_head_schedule_fits_video_at_color_duration_extremes(client, monkeypatch, hold_ms):
    from vericlue_api.services import dynamic_challenge as schedule

    settings = client.app.state.vericlue.settings
    base = schedule.generate_challenge(settings)
    for step in base.color_sequence:
        step.hold_ms = hold_ms
    monkeypatch.setattr(schedule, "generate_challenge", lambda _: base.model_copy(deep=True))
    plan = schedule.generate_dynamic_challenge(
        settings, session_id="ses_bounds", nonce=NONCE
    ).dynamic
    assert plan.version == 2
    assert plan.head_duration_ms == 12000
    assert plan.voice_start_at_ms == plan.head_start_at_ms + 12000 <= 30000


@pytest.mark.parametrize("value", [None, "old_challenge", "ký_tự_khác"])
def test_wrong_binding_rejected_before_writing_media(client, tmp_path, value):
    created, auth = create(client)
    data = {} if value is None else {"challenge_id": value}
    response = client.post(url(created, "media"), headers=auth, data=data, files=IMAGE)
    assert response.status_code == 409 and response.json()["error_code"] == "challenge_mismatch"
    assert not (tmp_path / "media" / created["session_id"]).exists()


def test_other_session_plan_and_missing_steps_are_rejected(client):
    first, auth = create(client)
    second, _ = create(client)
    response = client.post(
        url(first, "signals"),
        headers=auth,
        json={
            "challenge_id": second["challenge"]["challenge_id"],
            "color_events": [],
            "frame_times": [],
        },
    )
    assert response.status_code == 409
    assert client.post(url(first, "finalize"), headers=auth).status_code == 409
    response = client.post(
        url(first, "finalize"),
        headers=auth,
        json={"challenge_id": first["challenge"]["challenge_id"]},
    )
    assert response.status_code == 409 and response.json()["error_code"] == "steps_incomplete"


def test_face_retry_rotates_every_challenge_and_rejects_old_data(client):
    created, auth = create(client, scenario="low_quality")
    first = submit_face(client, created, auth)
    assert first["status"] == "retry"
    old, new = created["challenge"], first["challenge"]
    assert old["challenge_id"] != new["challenge_id"]
    assert old["dynamic"]["voice_challenge_id"] != new["dynamic"]["voice_challenge_id"]
    response = client.post(
        url(created, "media"), headers=auth, data={"challenge_id": old["challenge_id"]}, files=IMAGE
    )
    assert response.status_code == 409
    second = submit_face(client, created, auth, new)
    assert second["status"] == "retry" and second["attempts_left"] == 0
    assert submit_face(client, created, auth, second["challenge"])["status"] == "review"


def test_reread_rotates_prompt_and_id_and_is_limited(client):
    created, auth = create(client, "recovery", scenario="genuine")
    result = submit_face(client, created, auth)

    class WrongPhraseDetector:
        def predict(self, inp):
            return ModuleResult(
                module=Module.VOICE_CHALLENGE,
                model_version="mock@wrong-phrase",
                status=Status.OK,
                gate=Gate.FAIL,
                latency_ms=0,
            )

    client.app.state.vericlue.orchestrator._detectors[Module.VOICE_CHALLENGE] = (
        WrongPhraseDetector()
    )
    response = submit_voice(client, created, auth, result)
    assert response.status_code == 200, response.text
    reread = response.json()
    assert reread["status"] == "voice_challenge" and reread["attempts_left"] == 0
    assert reread["voice_prompt"] != result["voice_prompt"]
    assert reread["voice_challenge_id"] != result["voice_challenge_id"]
    assert submit_voice(client, created, auth, result).status_code == 409
    assert submit_voice(client, created, auth, reread).json() == {"status": "review"}


@pytest.mark.parametrize("scenario", ["print", "replay", "faceswap", "virtual_cam", "error"])
def test_voice_cannot_clear_face_review(client, scenario):
    created, auth = create(client, scenario=scenario)
    result = submit_face(client, created, auth)
    assert result == {"status": "review"}
    assert submit_voice(client, created, auth, created["challenge"]["dynamic"]).status_code == 409


@pytest.mark.parametrize("identity_runtime", [False, True])
def test_unverified_reauth_requires_recovery_without_staff_case(
    client, identity_runtime, monkeypatch
):
    if identity_runtime:
        client.app.state.vericlue.settings.identity_card_enabled = True

    def unexpected_match(*_):
        pytest.fail("Reauth must not use the card/selfie runtime")

    monkeypatch.setattr("vericlue_ml.face.match.FaceMatchDetector.predict", unexpected_match)
    created, auth = create(client, purpose="reauth")
    assert "dynamic" not in created["challenge"]
    result = submit_face(client, created, auth)
    assert result == {"status": "recovery_required"}
    with client.app.state.vericlue.database.sessions() as db:
        assert (
            db.scalar(
                select(ReviewCaseRow).where(ReviewCaseRow.session_id == created["session_id"])
            )
            is None
        )
    assert (
        client.post(
            url(created, "finalize"),
            headers=auth,
            json={"challenge_id": created["challenge"]["challenge_id"]},
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "scenario,expected",
    [("genuine", "pass"), ("print", "deny"), ("error", "deny"), ("voice_clone", "voice_challenge")],
)
@pytest.mark.parametrize("identity_runtime", [False, True])
def test_reauth_with_server_verified_context_has_no_review_case(
    client, scenario, expected, identity_runtime, monkeypatch
):
    if identity_runtime:
        client.app.state.vericlue.settings.identity_card_enabled = True

    def unexpected_match(*_):
        pytest.fail("Reauth must not use the card/selfie runtime")

    monkeypatch.setattr("vericlue_ml.face.match.FaceMatchDetector.predict", unexpected_match)
    created, auth = create(client, purpose="reauth", scenario=scenario)
    # Until SEC-02 exists, only a server-owned test fixture can grant this context.
    edit_session(client, created, device_verified=True)
    result = submit_face(client, created, auth)
    assert result["status"] == expected
    if expected == "voice_challenge":
        assert submit_voice(client, created, auth, result).json() == {"status": "deny"}
    with client.app.state.vericlue.database.sessions() as db:
        assert (
            db.scalar(
                select(ReviewCaseRow).where(ReviewCaseRow.session_id == created["session_id"])
            )
            is None
        )


@pytest.mark.parametrize("identity_runtime", [False, True])
def test_reauth_genuine_voice_after_escalation_does_not_require_a_card(client, identity_runtime):
    if identity_runtime:
        client.app.state.vericlue.settings.identity_card_enabled = True
    created, auth = create(client, purpose="reauth", scenario="voice_clone")
    edit_session(client, created, device_verified=True)
    result = submit_face(client, created, auth)
    assert result["status"] == "voice_challenge"
    # Server-owned fixture: ambiguous face, followed by genuine voice model results.
    edit_session(client, created, scenario="genuine")
    response = submit_voice(client, created, auth, result)
    assert response.json() == {"status": "pass"}
    with client.app.state.vericlue.database.sessions() as db:
        assert (
            db.scalar(
                select(ReviewCaseRow).where(ReviewCaseRow.session_id == created["session_id"])
            )
            is None
        )


@pytest.mark.parametrize(
    "extra",
    [
        {"device_verified": True},
        {"reference_image_id": "../../private"},
        {"nonce": "short"},
        {"purpose": "typo"},
    ],
)
def test_creation_rejects_untrusted_or_invalid_context(client, extra):
    response = client.post("/v1/sessions", json={"purpose": "onboarding", "nonce": NONCE, **extra})
    assert response.status_code == 422


@pytest.mark.parametrize("mode", [False, "mixed"])
def test_new_flows_fail_closed_in_real_or_mixed_mode(client, mode):
    settings = client.app.state.vericlue.settings
    settings.use_mock_models = mode
    response = client.post("/v1/sessions", json={"purpose": "onboarding", "nonce": NONCE})
    assert response.status_code == 503 and response.json()["error_code"] == "flow_unavailable"


def test_mock_session_cannot_be_reused_after_switching_to_real(client):
    created, auth = create(client)
    client.app.state.vericlue.settings.use_mock_models = False
    response = client.post(
        url(created, "media"),
        headers=auth,
        data={"challenge_id": created["challenge"]["challenge_id"]},
        files=IMAGE,
    )
    assert response.status_code == 503


def test_expired_challenge_does_not_receive_media(client):
    created, auth = create(client)
    ch = {
        **created["challenge"],
        "expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    }
    edit_session(client, created, challenge=ch)
    response = client.post(
        url(created, "media"), headers=auth, data={"challenge_id": ch["challenge_id"]}, files=IMAGE
    )
    assert response.status_code == 409 and response.json()["error_code"] == "challenge_expired"


def test_persistence_across_api_restart_and_no_scores_in_plan(client):
    created, auth = create(client, "recovery")
    encoded = json.dumps(created, ensure_ascii=False).lower()
    assert all(word not in encoded for word in ('"score"', '"prob_attack"', "giả mạo"))
    with TestClient(create_app()) as restarted:
        result = submit_face(restarted, created, auth)
        assert result["voice_prompt"] == created["challenge"]["dynamic"]["voice_prompt"]


def test_generator_retains_original_color_safety_config(client):
    settings = get_settings()
    plan = generate_dynamic_challenge(settings, session_id="ses_unit", nonce=NONCE)
    validate(plan.model_dump(mode="json", exclude_none=True), "session", "Challenge")
    assert len(plan.color_sequence) == 8
    assert all(step.hold_ms + step.transition_ms >= 550 for step in plan.color_sequence)


def _setup_ready_real_env(client, tmp_path):
    import base64
    import secrets
    from types import SimpleNamespace

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from pydantic import SecretStr

    from vericlue_api.services.media_proof import manifest
    from vericlue_ml.common.calibration import CalibFit, CalibrationStore, fit
    from vericlue_ml.common.result import Evidence
    from vericlue_ml.face.continuity import FACE_VOICE_VERSION
    from vericlue_ml.face.enrolled import REAUTH_MATCH_VERSION, RECOVERY_MATCH_VERSION
    from vericlue_ml.face.match import MatchThreshold
    from vericlue_ml.face.template import FaceTemplate
    from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION, VideoFaceMatchDetector

    root = client.app.state.vericlue
    calib_dir = tmp_path / "calibrators"
    store = CalibrationStore(calib_dir)
    root.orchestrator.router.calibrators = store

    def save_fitted(mod: Module, ver: str) -> None:
        artifact = fit(
            CalibFit(
                scores=[0.05, 0.95] * 8,
                labels=[0, 1] * 8,
                subject_ids=[f"subj-{i // 2}" for i in range(16)],
                dataset="synthetic-unit-test",
            ),
            module=mod,
            model_version=ver,
            commit="0" * 40,
            n_splits=3,
        )
        store.save(artifact)

    pad_base = "fs-vfm-vit-l-fas@11111111+scrfd@22222222+scrfd128-align224-rgb-v1"
    pad_frames = pad_base + "+headturn-3views-max-v1"
    gend_base = "gend-clip-l14@33333333+clip@44444444+scrfd-10g@22222222+agg-maxmeantop25-v1"
    gend_frames = gend_base + "+headturn-3views-v1"
    spoof_ver = "nes2net-x@c9fe1177+calibrated-test-v1"
    lipsync_ver = "stable-syncnet@c42c7e6c+ctc-aligner@49402e95+scrfd-10g@bfcc7d48+voice05-v2+session-offset-v1"

    save_fitted(Module.FACE_PAD, f"{pad_frames}+session-video-v2")
    save_fitted(Module.FACE_PAD, pad_base)
    save_fitted(Module.FACE_DEEPFAKE, f"{gend_frames}+session-video-v2")
    save_fitted(Module.FACE_DEEPFAKE, f"{gend_base}+single-frame-v1")
    save_fitted(Module.VOICE_SPOOF, spoof_ver)
    save_fitted(Module.LIPSYNC, lipsync_ver)

    def write_match_threshold(name: str, ver: str) -> str:
        path = tmp_path / name
        mt = MatchThreshold(
            model_version=ver,
            preprocessing="arcface112-rgb-minus1to1-v1",
            threshold=0.35,
            split="calib_ltt",
            dataset="synthetic-unit-test",
            pairs=20,
            subjects=10,
            source_commit="0" * 40,
            predictions_sha256="a" * 64,
        )
        path.write_text(mt.model_dump_json(), encoding="utf-8")
        return str(path)

    face_cal = write_match_threshold("face.json", VIDEO_MATCH_VERSION + "+head12s-v2")
    cons_cal = write_match_threshold(
        "cons.json", VIDEO_MATCH_VERSION + "+head12s-v2+view-consistency-v1"
    )
    voice_cal = write_match_threshold("voice.json", FACE_VOICE_VERSION)
    acct_cal = write_match_threshold("acct.json", REAUTH_MATCH_VERSION)
    rec_cal = write_match_threshold("rec.json", RECOVERY_MATCH_VERSION)

    root.settings = root.settings.model_copy(
        update={
            "security_profile": "synthetic",
            "simulated_otp": True,
            "use_mock_models": False,
            "manual_face_demo": False,
            "manual_full_demo": False,
            "require_privacy_consent": True,
            "privacy_policy_version": "demo-v1",
            "session_privacy": True,
            "session_master_key": SecretStr(base64.b64encode(secrets.token_bytes(32)).decode()),
            "id_hmac_key": SecretStr(secrets.token_urlsafe(32)),
            "session_signing_secret": SecretStr(secrets.token_urlsafe(32)),
            "require_media_proof": True,
            "account_enrollment": True,
            "identity_card_enabled": True,
            "identity_face_from_video": True,
            "identity_consistency_required": True,
            "identity_voice_continuity": True,
            "session_face_checks": True,
            "session_face_models": True,
            "session_voice_models": True,
            "identity_face_calibration": face_cal,
            "identity_consistency_calibration": cons_cal,
            "identity_voice_calibration": voice_cal,
            "identity_account_calibration": acct_cal,
            "identity_recovery_calibration": rec_cal,
        }
    )
    root.orchestrator.settings = root.settings

    class FakeSessionAttack:
        def __init__(self, mod: Module, base_ver: str, frames_ver: str):
            self.name = mod.value
            self.version = f"{frames_ver}+session-video-v2"
            self.manual_demo = None
            self.backend = SimpleNamespace(version=base_ver, frames_version=frames_ver)

        def predict(self, inp):
            ver = (
                (
                    self.backend.version
                    if self.name == Module.FACE_PAD.value
                    else f"{self.backend.version}+single-frame-v1"
                )
                if inp.metadata.get("purpose") == "reauth"
                else self.version
            )
            return ModuleResult(
                module=self.name,
                model_version=ver,
                status=Status.OK,
                score=0.05,
                prob_attack=0.02,
                gate=Gate.UNCLEAR,
                latency_ms=1.0,
                quality={"session_video": True, "calibrated": True, "depth_verified": False},
            )

    class FakeSimpleDetector:
        def __init__(self, mod: Module, ver: str, *, gate=Gate.PASS, score=0.05):
            self.name = mod.value
            self.version = ver
            self._gate = gate
            self._score = score

        def predict(self, inp):
            return ModuleResult(
                module=self.name,
                model_version=self.version,
                status=Status.OK,
                gate=self._gate,
                score=self._score,
                latency_ms=1.0,
            )

    class FakeMatcher(VideoFaceMatchDetector):
        name = Module.FACE_MATCH.value
        version = VIDEO_MATCH_VERSION + "+head12s-v2"

        def __init__(self):
            self.manual_demo = None

        def predict(self, inp):
            purpose = inp.metadata.get("purpose")
            acct = inp.metadata.get("account_id")
            ver = (
                RECOVERY_MATCH_VERSION
                if purpose == "recovery" and acct
                else REAUTH_MATCH_VERSION
                if purpose == "reauth" and acct
                else VIDEO_MATCH_VERSION + "+head12s-v2"
            )
            ev = [
                Evidence(type="text", name="source_video_sha256", value="c" * 64),
                Evidence(
                    type="scalar",
                    name="selected_frontal_frame",
                    value={"target_ms": 500, "at_ms": 500, "pixels_sha256": "d" * 64},
                ),
            ]
            if acct:
                ev.append(Evidence(type="text", name="reference_account_id", value=acct))
            return ModuleResult(
                module=Module.FACE_MATCH,
                model_version=ver,
                status=Status.OK,
                gate=Gate.PASS,
                score=0.1,
                latency_ms=1.0,
                quality={
                    "threshold_available": True,
                    "threshold_cosine": 0.35,
                    "consistency_verified": True,
                    "views_from_video": True,
                    "enrolled_reference": bool(acct),
                },
                evidence=ev,
            )

        def enrollment_template(self, inp, approved):
            return FaceTemplate(
                session_id=inp.session_id,
                challenge_id=inp.metadata["expected_challenge"]["challenge_id"],
                model_version=VIDEO_MATCH_VERSION,
                preprocessing="arcface112-rgb-minus1to1-v1",
                source_video_sha256="c" * 64,
                pixels_sha256="d" * 64,
                embedding=(1.0, *([0.0] * 511)),
            )

    class FakeContinuity:
        name = Module.FACE_CONTINUITY.value
        version = FACE_VOICE_VERSION

        def predict(self, inp):
            return ModuleResult(
                module=Module.FACE_CONTINUITY,
                model_version=FACE_VOICE_VERSION,
                status=Status.OK,
                gate=Gate.PASS,
                score=0.1,
                latency_ms=1.0,
                quality={"threshold_available": True, "threshold_cosine": 0.35},
                evidence=[
                    Evidence(type="text", name="source_video_sha256", value="c" * 64),
                    Evidence(
                        type="text",
                        name="challenge_id",
                        value=inp.metadata["expected_challenge"]["challenge_id"],
                    ),
                    Evidence(
                        type="text",
                        name="voice_challenge_id",
                        value=inp.metadata["expected_voice_challenge_id"],
                    ),
                ],
            )

    matcher = FakeMatcher()
    root.orchestrator._identity_matcher = matcher
    root.orchestrator._failed.clear()
    root.orchestrator._detectors = {
        Module.QUALITY: FakeSimpleDetector(Module.QUALITY, "quality@real-v1"),
        Module.CHROMAPULSE: FakeSimpleDetector(Module.CHROMAPULSE, "chromapulse@real-v1"),
        Module.CAMPROBE: FakeSimpleDetector(Module.CAMPROBE, "camprobe@real-v1"),
        Module.GAZE_TRACKING: FakeSimpleDetector(Module.GAZE_TRACKING, "gaze@real-v1"),
        Module.HEAD_TURN: FakeSimpleDetector(Module.HEAD_TURN, "head@real-v1"),
        Module.FACE_PAD: FakeSessionAttack(Module.FACE_PAD, pad_base, pad_frames),
        Module.FACE_DEEPFAKE: FakeSessionAttack(Module.FACE_DEEPFAKE, gend_base, gend_frames),
        Module.FACE_MATCH: matcher,
        Module.FACE_CONTINUITY: FakeContinuity(),
        Module.VOICE_CHALLENGE: FakeSimpleDetector(Module.VOICE_CHALLENGE, "qwen-asr@real-v1"),
        Module.VOICE_SPOOF: FakeSimpleDetector(
            Module.VOICE_SPOOF, spoof_ver, gate=Gate.UNCLEAR, score=0.05
        ),
        Module.LIPSYNC: FakeSimpleDetector(Module.LIPSYNC, lipsync_ver, gate=None, score=0.05),
    }

    def make_key():
        k = ec.generate_private_key(ec.SECP256R1())
        s = base64.b64encode(
            k.public_key().public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        ).decode()
        return k, s

    def sign_bytes(k, data: bytes) -> str:
        return base64.b64encode(k.sign(data, ec.ECDSA(hashes.SHA256()))).decode()

    def sign_stage(sid: str, k, stage: str, files: dict, *, offset_ms: int | None = None) -> str:
        with root.transaction() as state:
            sess = state.sessions.get(sid)
            msg, _, _ = manifest(sess, stage, files, audio_offset_ms=offset_ms)
            return sign_bytes(k, msg)

    def verify_otp(sid: str, auth_headers: dict[str, str], phone: str = "0901234567") -> None:
        import re

        sent = client.post(
            f"/v1/sessions/{sid}/otp",
            headers=auth_headers,
            json={"phone": phone},
        )
        assert sent.status_code == 200, sent.text
        sms = sent.json().get("simulated_sms")
        assert isinstance(sms, str) and sms.startswith("VeriClue: Mã xác minh của bạn là ")
        match = re.search(r"\b(\d{6})\b", sms)
        assert match is not None
        verified = client.post(
            f"/v1/sessions/{sid}/otp/verify",
            headers=auth_headers,
            json={"code": match.group(1)},
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["status"] == "pass"

    return SimpleNamespace(
        root=root,
        store=store,
        make_key=make_key,
        sign_bytes=sign_bytes,
        sign_stage=sign_stage,
        verify_otp=verify_otp,
        pad_frames=pad_frames,
        spoof_ver=spoof_ver,
        lipsync_ver=lipsync_ver,
    )


def test_standard_real_flows_succeed_when_all_prerequisites_are_ready(
    client, tmp_path, monkeypatch
):
    import base64

    from vericlue_api.routers import privacy
    from vericlue_api.services import orchestrator as orch_mod
    from vericlue_api.services.identity_steps import _digest

    if not any(
        getattr(r, "path", "") == "/v1/sessions/{session_id}/privacy" for r in client.app.routes
    ):
        client.app.include_router(privacy.router)
    env = _setup_ready_real_env(client, tmp_path)
    monkeypatch.setattr(
        orch_mod,
        "match_enrolled",
        lambda matcher, inp, template, cal_path: matcher.predict(inp),
    )

    # 1. Onboarding with calibrated real models + consent + enrollment
    dev_key, dev_spki = env.make_key()
    resp = client.post(
        "/v1/sessions",
        json={
            "purpose": "onboarding",
            "nonce": NONCE,
            "device_public_key_spki": dev_spki,
        },
    )
    assert resp.status_code == 200, resp.text
    created = resp.json()
    sid = created["session_id"]
    auth = {"Authorization": "Bearer " + created["token"]}
    assert "evaluation_mode" not in created

    consent_resp = client.post(
        f"/v1/sessions/{sid}/privacy/consent",
        headers=auth,
        json={
            "policy_version": "demo-v1",
            "categories": ["contact", "id_document", "face_biometrics", "voice_biometrics"],
            "consent": True,
        },
    )
    assert consent_resp.status_code == 200, consent_resp.text

    acct_consent_resp = client.post(
        f"/v1/sessions/{sid}/privacy/account-template/consent",
        headers=auth,
        json={
            "policy_version": "account-template-v1",
            "purpose": "account_template",
            "consent": True,
        },
    )
    assert acct_consent_resp.status_code == 200, acct_consent_resp.text
    assert acct_consent_resp.json()["status"] == "granted"

    env.root.orchestrator.settings = env.root.settings
    env.verify_otp(sid, auth, "0901234567")
    hmac_key = env.root.settings.id_hmac_key.get_secret_value()
    img_bytes = IMAGE["image"][1]
    vid_bytes = b"\x00\x00\x00\x18ftypmp42synthetic-video"
    with env.root.transaction() as state:
        from vericlue_api.services.uploads import save_upload

        sess = state.sessions.get(sid)
        assert sess.otp_verified is True
        assert sess.phone_hmac == _digest(hmac_key, "0901234567")
        sess.id_confirmed = True
        sess.id_source = "server_qr"
        sess.id_number_hmac = sess.id_confirmed_number_hmac = _digest(hmac_key, "012345678901")
        sess.id_front = save_upload(
            state.settings.media_dir,
            sid,
            "id_front",
            "front.jpg",
            img_bytes,
            privacy=state.privacy,
        )
    sig_face = env.sign_stage(
        sid,
        dev_key,
        "face",
        {"image": ("face.jpg", img_bytes), "video": ("face.mp4", vid_bytes)},
    )
    assert (
        client.post(
            url(created, "media"),
            headers=auth,
            data={
                "challenge_id": created["challenge"]["challenge_id"],
                "media_signature": sig_face,
            },
            files={
                "image": ("face.jpg", img_bytes, "image/jpeg"),
                "video": ("face.mp4", vid_bytes, "video/mp4"),
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            url(created, "signals"),
            headers=auth,
            json={
                "challenge_id": created["challenge"]["challenge_id"],
                "color_events": [],
                "frame_times": [],
            },
        ).status_code
        == 200
    )
    fin = client.post(
        url(created, "finalize"),
        headers=auth,
        json={"challenge_id": created["challenge"]["challenge_id"]},
    )
    assert fin.status_code == 200, fin.text
    assert fin.json() == {"status": "pass"}

    acct_resp = client.get(f"/v1/sessions/{sid}/account", headers=auth)
    assert acct_resp.status_code == 200, acct_resp.text
    receipt = acct_resp.json()

    # 2. Reauth with L0 signature + calibrated single-frame face checks + enrolled match
    reauth_resp = client.post(
        "/v1/sessions",
        json={
            "purpose": "reauth",
            "nonce": NONCE,
            "account_id": receipt["account_id"],
            "device_id": receipt["device_id"],
        },
    )
    assert reauth_resp.status_code == 200, reauth_resp.text
    reauth_created = reauth_resp.json()
    rsid = reauth_created["session_id"]
    rauth = {"Authorization": "Bearer " + reauth_created["token"]}

    assert (
        client.post(
            f"/v1/sessions/{rsid}/privacy/consent",
            headers=rauth,
            json={
                "policy_version": "demo-v1",
                "categories": ["face_biometrics"],
                "consent": True,
            },
        ).status_code
        == 200
    )
    dev_msg = base64.b64decode(reauth_created["device_challenge"]["message"])
    assert (
        client.post(
            f"/v1/sessions/{rsid}/device-proof",
            headers=rauth,
            json={"signature": env.sign_bytes(dev_key, dev_msg)},
        ).status_code
        == 200
    )
    sig_reauth = env.sign_stage(
        rsid,
        dev_key,
        "face",
        {"image": ("face.jpg", img_bytes), "video": ("face.mp4", vid_bytes)},
    )
    assert (
        client.post(
            url(reauth_created, "media"),
            headers=rauth,
            data={
                "challenge_id": reauth_created["challenge"]["challenge_id"],
                "media_signature": sig_reauth,
            },
            files={
                "image": ("face.jpg", img_bytes, "image/jpeg"),
                "video": ("face.mp4", vid_bytes, "video/mp4"),
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            url(reauth_created, "signals"),
            headers=rauth,
            json={
                "challenge_id": reauth_created["challenge"]["challenge_id"],
                "color_events": [],
                "frame_times": [],
            },
        ).status_code
        == 200
    )
    rfin = client.post(
        url(reauth_created, "finalize"),
        headers=rauth,
        json={"challenge_id": reauth_created["challenge"]["challenge_id"]},
    )
    assert rfin.status_code == 200, rfin.text
    assert rfin.json() == {"status": "pass"}

    # 3. Recovery with new device key + calibrated face/voice/lipsync/continuity
    rec_key, rec_spki = env.make_key()
    rec_resp = client.post(
        "/v1/sessions",
        json={
            "purpose": "recovery",
            "nonce": NONCE,
            "account_id": receipt["account_id"],
            "device_public_key_spki": rec_spki,
        },
    )
    assert rec_resp.status_code == 200, rec_resp.text
    rec_created = rec_resp.json()
    ksid = rec_created["session_id"]
    kauth = {"Authorization": "Bearer " + rec_created["token"]}

    assert (
        client.post(
            f"/v1/sessions/{ksid}/privacy/consent",
            headers=kauth,
            json={
                "policy_version": "demo-v1",
                "categories": ["contact", "face_biometrics", "voice_biometrics"],
                "consent": True,
            },
        ).status_code
        == 200
    )
    env.verify_otp(ksid, kauth, "0901234567")

    sig_rec_face = env.sign_stage(
        ksid,
        rec_key,
        "face",
        {"image": ("face.jpg", img_bytes), "video": ("face.mp4", vid_bytes)},
    )
    assert (
        client.post(
            url(rec_created, "media"),
            headers=kauth,
            data={
                "challenge_id": rec_created["challenge"]["challenge_id"],
                "media_signature": sig_rec_face,
            },
            files={
                "image": ("face.jpg", img_bytes, "image/jpeg"),
                "video": ("face.mp4", vid_bytes, "video/mp4"),
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            url(rec_created, "signals"),
            headers=kauth,
            json={
                "challenge_id": rec_created["challenge"]["challenge_id"],
                "color_events": [],
                "frame_times": [],
            },
        ).status_code
        == 200
    )
    kfin = client.post(
        url(rec_created, "finalize"),
        headers=kauth,
        json={"challenge_id": rec_created["challenge"]["challenge_id"]},
    )
    assert kfin.status_code == 200, kfin.text
    kfin_body = kfin.json()
    assert kfin_body["status"] == "voice_challenge"

    wav_bytes = b"RIFF$\x00\x00\x00WAVEfmt "
    vvid_bytes = b"\x00\x00\x00\x18ftypmp42voice-video"
    sig_rec_voice = env.sign_stage(
        ksid,
        rec_key,
        "voice",
        {"audio": ("voice.wav", wav_bytes), "video": ("voice.mp4", vvid_bytes)},
        offset_ms=40,
    )
    kvoice = client.post(
        url(rec_created, "voice"),
        headers=kauth,
        data={
            "voice_challenge_id": kfin_body["voice_challenge_id"],
            "media_signature": sig_rec_voice,
            "audio_offset_ms": "40",
        },
        files={
            "audio": ("voice.wav", wav_bytes, "audio/wav"),
            "video": ("voice.mp4", vvid_bytes, "video/mp4"),
        },
    )
    assert kvoice.status_code == 200, kvoice.text
    kvoice_body = kvoice.json()
    assert kvoice_body["status"] == "pass"
    assert kvoice_body["account"]["account_id"] == receipt["account_id"]
    assert kvoice_body["account"]["device_id"] != receipt["device_id"]


@pytest.mark.parametrize(
    "missing",
    [
        "mixed_mode",
        "consent_disabled",
        "failed_detector",
        "mock_detector_version",
        "diagnostic_nes2net_timeline",
        "provisional_pad_calibrator",
        "missing_spoof_calibrator",
        "missing_lipsync_calibrator",
        "missing_face_match_calibration",
        "missing_consistency_calibration",
        "missing_voice_continuity_calibration",
    ],
)
def test_standard_real_onboarding_fails_closed_when_any_condition_is_missing(
    client, tmp_path, missing
):
    from vericlue_ml.common.calibration import identity
    from vericlue_ml.voice.nes2net_timeline import VERSION as NES2NET_TIMELINE_VERSION

    env = _setup_ready_real_env(client, tmp_path)
    _, dev_spki = env.make_key()

    if missing == "mixed_mode":
        env.root.settings.use_mock_models = "mixed"
    elif missing == "consent_disabled":
        env.root.settings.require_privacy_consent = False
    elif missing == "failed_detector":
        env.root.orchestrator._failed.add(Module.FACE_PAD)
    elif missing == "mock_detector_version":
        env.root.orchestrator._detectors[Module.QUALITY].version = "mock@0.1"
    elif missing == "diagnostic_nes2net_timeline":
        env.root.orchestrator._detectors[Module.VOICE_SPOOF].version = NES2NET_TIMELINE_VERSION
    elif missing == "provisional_pad_calibrator":
        env.store.save(
            identity(
                module=Module.FACE_PAD,
                model_version=f"{env.pad_frames}+session-video-v2",
                commit="0" * 40,
            )
        )
    elif missing == "missing_spoof_calibrator":
        env.store.path(Module.VOICE_SPOOF, env.spoof_ver).unlink()
        env.store._cache.clear()
    elif missing == "missing_lipsync_calibrator":
        env.store.path(Module.LIPSYNC, env.lipsync_ver).unlink()
        env.store._cache.clear()
    elif missing == "missing_face_match_calibration":
        env.root.settings.identity_face_calibration = None
    elif missing == "missing_consistency_calibration":
        env.root.settings.identity_consistency_calibration = None
    elif missing == "missing_voice_continuity_calibration":
        env.root.settings.identity_voice_calibration = None

    resp = client.post(
        "/v1/sessions",
        json={
            "purpose": "onboarding",
            "nonce": NONCE,
            "device_public_key_spki": dev_spki,
        },
    )
    assert resp.status_code == 503
    assert resp.json()["error_code"] == "flow_unavailable"


@pytest.mark.parametrize(
    "fault",
    [
        "onboarding_missing_account_template_consent",
        "reauth_missing_account_calibration",
        "reauth_missing_single_frame_deepfake_calibrator",
        "recovery_missing_recovery_calibration",
        "recovery_unverified_otp",
    ],
)
def test_standard_real_account_flows_fail_closed_when_prerequisites_missing(
    client, tmp_path, fault, monkeypatch
):
    import base64

    from vericlue_api.routers import privacy
    from vericlue_api.services import orchestrator as orch_mod
    from vericlue_api.services.identity_steps import _digest

    if not any(
        getattr(r, "path", "") == "/v1/sessions/{session_id}/privacy" for r in client.app.routes
    ):
        client.app.include_router(privacy.router)
    env = _setup_ready_real_env(client, tmp_path)
    monkeypatch.setattr(
        orch_mod,
        "match_enrolled",
        lambda matcher, inp, template, cal_path: matcher.predict(inp),
    )

    # Enroll an account first
    dev_key, dev_spki = env.make_key()
    created = client.post(
        "/v1/sessions",
        json={"purpose": "onboarding", "nonce": NONCE, "device_public_key_spki": dev_spki},
    ).json()
    sid = created["session_id"]
    auth = {"Authorization": "Bearer " + created["token"]}
    client.post(
        f"/v1/sessions/{sid}/privacy/consent",
        headers=auth,
        json={
            "policy_version": "demo-v1",
            "categories": ["contact", "id_document", "face_biometrics", "voice_biometrics"],
            "consent": True,
        },
    )
    if fault != "onboarding_missing_account_template_consent":
        client.post(
            f"/v1/sessions/{sid}/privacy/account-template/consent",
            headers=auth,
            json={
                "policy_version": "account-template-v1",
                "purpose": "account_template",
                "consent": True,
            },
        )
    env.verify_otp(sid, auth, "0901234567")
    hmac_key = env.root.settings.id_hmac_key.get_secret_value()
    img_bytes = IMAGE["image"][1]
    vid_bytes = b"\x00\x00\x00\x18ftypmp42synthetic-video"
    with env.root.transaction() as state:
        from vericlue_api.services.uploads import save_upload

        sess = state.sessions.get(sid)
        sess.id_confirmed = True
        sess.id_source = "server_qr"
        sess.id_number_hmac = sess.id_confirmed_number_hmac = _digest(hmac_key, "012345678901")
        sess.id_front = save_upload(
            state.settings.media_dir,
            sid,
            "id_front",
            "front.jpg",
            img_bytes,
            privacy=state.privacy,
        )
    sig_face = env.sign_stage(
        sid,
        dev_key,
        "face",
        {"image": ("face.jpg", img_bytes), "video": ("face.mp4", vid_bytes)},
    )
    client.post(
        url(created, "media"),
        headers=auth,
        data={"challenge_id": created["challenge"]["challenge_id"], "media_signature": sig_face},
        files={
            "image": ("face.jpg", img_bytes, "image/jpeg"),
            "video": ("face.mp4", vid_bytes, "video/mp4"),
        },
    )
    client.post(
        url(created, "signals"),
        headers=auth,
        json={
            "challenge_id": created["challenge"]["challenge_id"],
            "color_events": [],
            "frame_times": [],
        },
    )
    fin_resp = client.post(
        url(created, "finalize"),
        headers=auth,
        json={"challenge_id": created["challenge"]["challenge_id"]},
    )
    if fault == "onboarding_missing_account_template_consent":
        assert fin_resp.status_code == 409
        assert fin_resp.json()["error_code"] == "account_template_consent_required"
        return
    assert fin_resp.json()["status"] == "pass"
    receipt = client.get(f"/v1/sessions/{sid}/account", headers=auth).json()

    if fault.startswith("reauth_"):
        reauth_created = client.post(
            "/v1/sessions",
            json={
                "purpose": "reauth",
                "nonce": NONCE,
                "account_id": receipt["account_id"],
                "device_id": receipt["device_id"],
            },
        ).json()
        rsid = reauth_created["session_id"]
        rauth = {"Authorization": "Bearer " + reauth_created["token"]}
        client.post(
            f"/v1/sessions/{rsid}/privacy/consent",
            headers=rauth,
            json={
                "policy_version": "demo-v1",
                "categories": ["face_biometrics"],
                "consent": True,
            },
        )
        dev_msg = base64.b64decode(reauth_created["device_challenge"]["message"])
        assert (
            client.post(
                f"/v1/sessions/{rsid}/device-proof",
                headers=rauth,
                json={"signature": env.sign_bytes(dev_key, dev_msg)},
            ).status_code
            == 200
        )
        if fault == "reauth_missing_account_calibration":
            env.root.settings.identity_account_calibration = None
        else:
            gend_base = env.root.orchestrator._detectors[Module.FACE_DEEPFAKE].backend.version
            env.store.path(Module.FACE_DEEPFAKE, f"{gend_base}+single-frame-v1").unlink()
            env.store._cache.clear()
        res = client.post(
            url(reauth_created, "signals"),
            headers=rauth,
            json={
                "challenge_id": reauth_created["challenge"]["challenge_id"],
                "color_events": [],
                "frame_times": [],
            },
        )
        assert res.status_code == 503
        assert res.json()["error_code"] == "flow_unavailable"
    else:
        _, rec_spki = env.make_key()
        rec_created = client.post(
            "/v1/sessions",
            json={
                "purpose": "recovery",
                "nonce": NONCE,
                "account_id": receipt["account_id"],
                "device_public_key_spki": rec_spki,
            },
        ).json()
        ksid = rec_created["session_id"]
        kauth = {"Authorization": "Bearer " + rec_created["token"]}
        client.post(
            f"/v1/sessions/{ksid}/privacy/consent",
            headers=kauth,
            json={
                "policy_version": "demo-v1",
                "categories": ["contact", "face_biometrics", "voice_biometrics"],
                "consent": True,
            },
        )
        if fault == "recovery_missing_recovery_calibration":
            env.verify_otp(ksid, kauth, "0901234567")
            env.root.settings.identity_recovery_calibration = None
        res = client.post(
            url(rec_created, "signals"),
            headers=kauth,
            json={
                "challenge_id": rec_created["challenge"]["challenge_id"],
                "color_events": [],
                "frame_times": [],
            },
        )
        assert res.status_code == 503
        assert res.json()["error_code"] == "flow_unavailable"


def test_standard_real_simulated_otp_endpoints_and_error_cases(client, tmp_path):
    import re
    from datetime import UTC, datetime, timedelta

    from vericlue_api.core.errors import ApiError
    from vericlue_api.core.security_profile import (
        security_profile_checks,
        validate_security_profile,
    )
    from vericlue_api.routers import privacy

    if not any(
        getattr(r, "path", "") == "/v1/sessions/{session_id}/privacy" for r in client.app.routes
    ):
        client.app.include_router(privacy.router)
    env = _setup_ready_real_env(client, tmp_path)

    def create_consented_onboarding() -> tuple[str, dict[str, str]]:
        _, spki = env.make_key()
        created = client.post(
            "/v1/sessions",
            json={"purpose": "onboarding", "nonce": NONCE, "device_public_key_spki": spki},
        ).json()
        sid = created["session_id"]
        auth = {"Authorization": "Bearer " + created["token"]}
        res = client.post(
            f"/v1/sessions/{sid}/privacy/consent",
            headers=auth,
            json={
                "policy_version": "demo-v1",
                "categories": ["contact", "id_document", "face_biometrics", "voice_biometrics"],
                "consent": True,
            },
        )
        assert res.status_code == 200
        return sid, auth

    # 1. Default off: disabling simulated_otp in real mode rejects /otp with 503 otp_unavailable
    sid_off, auth_off = create_consented_onboarding()
    env.root.settings = env.root.settings.model_copy(update={"simulated_otp": False})
    off_resp = client.post(
        f"/v1/sessions/{sid_off}/otp", headers=auth_off, json={"phone": "0901234567"}
    )
    assert off_resp.status_code == 503 and off_resp.json()["error_code"] == "otp_unavailable"
    assert "simulated_sms" not in off_resp.text

    # 2. Protected profile strictly rejects simulated_otp in both profile validation and /otp
    protected_with_sim = env.root.settings.model_copy(
        update={
            "security_profile": "protected",
            "product_mode": "ekyc",
            "simulated_otp": True,
        }
    )
    assert security_profile_checks(protected_with_sim)["no_simulated_otp"] is False
    with pytest.raises(ApiError) as caught:
        validate_security_profile(protected_with_sim)
    assert caught.value.status_code == 503
    assert caught.value.error_code == "security_profile_unavailable"

    env.root.settings = protected_with_sim
    prot_resp = client.post(
        f"/v1/sessions/{sid_off}/otp", headers=auth_off, json={"phone": "0901234567"}
    )
    assert prot_resp.status_code == 503 and prot_resp.json()["error_code"] == "otp_unavailable"
    assert "simulated_sms" not in prot_resp.text

    # Re-enable synthetic + simulated_otp for endpoint behavior checks
    env.root.settings = env.root.settings.model_copy(
        update={"security_profile": "synthetic", "simulated_otp": True}
    )

    # 3. Wrong code counts down attempts_left and locks after 5 failed attempts
    sid_lock, auth_lock = create_consented_onboarding()
    sent = client.post(
        f"/v1/sessions/{sid_lock}/otp", headers=auth_lock, json={"phone": "0901234567"}
    )
    assert sent.status_code == 200
    sms = sent.json()["simulated_sms"]
    assert sms.startswith("VeriClue: Mã xác minh của bạn là ")
    code = re.search(r"\b(\d{6})\b", sms).group(1)
    wrong_code = f"{(int(code) + 1) % 10**6:06d}"

    for expected_left in (4, 3, 2, 1, 0):
        retry = client.post(
            f"/v1/sessions/{sid_lock}/otp/verify",
            headers=auth_lock,
            json={"code": wrong_code},
        )
        assert retry.status_code == 200
        assert retry.json() == {"status": "retry", "attempts_left": expected_left}

    locked_verify = client.post(
        f"/v1/sessions/{sid_lock}/otp/verify", headers=auth_lock, json={"code": code}
    )
    assert locked_verify.status_code == 409
    assert locked_verify.json()["error_code"] == "otp_locked"

    locked_send = client.post(
        f"/v1/sessions/{sid_lock}/otp", headers=auth_lock, json={"phone": "0901234567"}
    )
    assert locked_send.status_code == 409
    assert locked_send.json()["error_code"] == "otp_locked"

    # 4. Expired OTP returns 409 otp_expired
    sid_exp, auth_exp = create_consented_onboarding()
    sent_exp = client.post(
        f"/v1/sessions/{sid_exp}/otp", headers=auth_exp, json={"phone": "0901234567"}
    )
    assert sent_exp.status_code == 200
    code_exp = re.search(r"\b(\d{6})\b", sent_exp.json()["simulated_sms"]).group(1)
    with env.root.transaction() as state:
        state.sessions.get(sid_exp).otp_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    expired = client.post(
        f"/v1/sessions/{sid_exp}/otp/verify", headers=auth_exp, json={"code": code_exp}
    )
    assert expired.status_code == 409 and expired.json()["error_code"] == "otp_expired"

    # 5. Send limit (otp_max_sends=3) returns 409 otp_too_many on 4th send
    sid_many, auth_many = create_consented_onboarding()
    for _ in range(3):
        res_send = client.post(
            f"/v1/sessions/{sid_many}/otp", headers=auth_many, json={"phone": "0901234567"}
        )
        assert res_send.status_code == 200
    too_many = client.post(
        f"/v1/sessions/{sid_many}/otp", headers=auth_many, json={"phone": "0901234567"}
    )
    assert too_many.status_code == 409 and too_many.json()["error_code"] == "otp_too_many"


def test_standard_real_reauth_does_not_require_voice_or_onboarding_calibrators(
    client, tmp_path, monkeypatch
):
    import base64

    from vericlue_api.routers import privacy
    from vericlue_api.services import orchestrator as orch_mod
    from vericlue_api.services.identity_steps import _digest
    from vericlue_ml.voice.nes2net_timeline import VERSION as NES2NET_TIMELINE_VERSION

    if not any(
        getattr(r, "path", "") == "/v1/sessions/{session_id}/privacy" for r in client.app.routes
    ):
        client.app.include_router(privacy.router)
    env = _setup_ready_real_env(client, tmp_path)
    monkeypatch.setattr(
        orch_mod,
        "match_enrolled",
        lambda matcher, inp, template, cal_path: matcher.predict(inp),
    )

    # Enroll an account first
    dev_key, dev_spki = env.make_key()
    created = client.post(
        "/v1/sessions",
        json={"purpose": "onboarding", "nonce": NONCE, "device_public_key_spki": dev_spki},
    ).json()
    sid = created["session_id"]
    auth = {"Authorization": "Bearer " + created["token"]}
    client.post(
        f"/v1/sessions/{sid}/privacy/consent",
        headers=auth,
        json={
            "policy_version": "demo-v1",
            "categories": ["contact", "id_document", "face_biometrics", "voice_biometrics"],
            "consent": True,
        },
    )
    client.post(
        f"/v1/sessions/{sid}/privacy/account-template/consent",
        headers=auth,
        json={
            "policy_version": "account-template-v1",
            "purpose": "account_template",
            "consent": True,
        },
    )
    env.verify_otp(sid, auth, "0901234567")
    hmac_key = env.root.settings.id_hmac_key.get_secret_value()
    img_bytes = IMAGE["image"][1]
    vid_bytes = b"\x00\x00\x00\x18ftypmp42synthetic-video"
    with env.root.transaction() as state:
        from vericlue_api.services.uploads import save_upload

        sess = state.sessions.get(sid)
        sess.id_confirmed = True
        sess.id_source = "server_qr"
        sess.id_number_hmac = sess.id_confirmed_number_hmac = _digest(hmac_key, "012345678901")
        sess.id_front = save_upload(
            state.settings.media_dir,
            sid,
            "id_front",
            "front.jpg",
            img_bytes,
            privacy=state.privacy,
        )
    sig_face = env.sign_stage(
        sid,
        dev_key,
        "face",
        {"image": ("face.jpg", img_bytes), "video": ("face.mp4", vid_bytes)},
    )
    client.post(
        url(created, "media"),
        headers=auth,
        data={"challenge_id": created["challenge"]["challenge_id"], "media_signature": sig_face},
        files={
            "image": ("face.jpg", img_bytes, "image/jpeg"),
            "video": ("face.mp4", vid_bytes, "video/mp4"),
        },
    )
    client.post(
        url(created, "signals"),
        headers=auth,
        json={
            "challenge_id": created["challenge"]["challenge_id"],
            "color_events": [],
            "frame_times": [],
        },
    )
    assert (
        client.post(
            url(created, "finalize"),
            headers=auth,
            json={"challenge_id": created["challenge"]["challenge_id"]},
        ).json()["status"]
        == "pass"
    )
    receipt = client.get(f"/v1/sessions/{sid}/account", headers=auth).json()

    # Now disable voice/onboarding/recovery prerequisites while keeping reauth face + L0 ready
    env.store.path(Module.VOICE_SPOOF, env.spoof_ver).unlink()
    env.store.path(Module.LIPSYNC, env.lipsync_ver).unlink()
    env.store._cache.clear()
    env.root.orchestrator._detectors[Module.VOICE_SPOOF].version = NES2NET_TIMELINE_VERSION
    env.root.settings = env.root.settings.model_copy(
        update={
            "session_voice_models": False,
            "identity_card_enabled": False,
            "identity_consistency_required": False,
            "session_face_checks": False,
            "identity_voice_continuity": False,
            "identity_face_calibration": None,
            "identity_consistency_calibration": None,
            "identity_voice_calibration": None,
            "identity_recovery_calibration": None,
        }
    )

    reauth_resp = client.post(
        "/v1/sessions",
        json={
            "purpose": "reauth",
            "nonce": NONCE,
            "account_id": receipt["account_id"],
            "device_id": receipt["device_id"],
        },
    )
    assert reauth_resp.status_code == 200, reauth_resp.text
    reauth_created = reauth_resp.json()
    rsid = reauth_created["session_id"]
    rauth = {"Authorization": "Bearer " + reauth_created["token"]}

    assert (
        client.post(
            f"/v1/sessions/{rsid}/privacy/consent",
            headers=rauth,
            json={
                "policy_version": "demo-v1",
                "categories": ["face_biometrics"],
                "consent": True,
            },
        ).status_code
        == 200
    )
    dev_msg = base64.b64decode(reauth_created["device_challenge"]["message"])
    assert (
        client.post(
            f"/v1/sessions/{rsid}/device-proof",
            headers=rauth,
            json={"signature": env.sign_bytes(dev_key, dev_msg)},
        ).status_code
        == 200
    )
    sig_reauth = env.sign_stage(
        rsid,
        dev_key,
        "face",
        {"image": ("face.jpg", img_bytes), "video": ("face.mp4", vid_bytes)},
    )
    assert (
        client.post(
            url(reauth_created, "media"),
            headers=rauth,
            data={
                "challenge_id": reauth_created["challenge"]["challenge_id"],
                "media_signature": sig_reauth,
            },
            files={
                "image": ("face.jpg", img_bytes, "image/jpeg"),
                "video": ("face.mp4", vid_bytes, "video/mp4"),
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            url(reauth_created, "signals"),
            headers=rauth,
            json={
                "challenge_id": reauth_created["challenge"]["challenge_id"],
                "color_events": [],
                "frame_times": [],
            },
        ).status_code
        == 200
    )
    rfin = client.post(
        url(reauth_created, "finalize"),
        headers=rauth,
        json={"challenge_id": reauth_created["challenge"]["challenge_id"]},
    )
    assert rfin.status_code == 200, rfin.text
    assert rfin.json() == {"status": "pass"}
