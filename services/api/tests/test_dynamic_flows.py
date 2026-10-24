"""Backend contract and state transitions for model-independent FLOW-01/LIVE-01."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from contract_utils import validate
from fastapi.testclient import TestClient
from sqlalchemy import select

from vericlue_api.core.config import get_settings
from vericlue_api.db.models import DecisionRow, ReviewCaseRow, SessionRow
from vericlue_api.main import create_app
from vericlue_api.services.dynamic_challenge import generate_dynamic_challenge
from vericlue_ml.common.result import Gate, Module, ModuleResult, Status

IMAGE = {"image": ("face.jpg", b"synthetic image", "image/jpeg")}
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


@pytest.mark.parametrize("purpose", ["onboarding", "recovery"])
def test_full_mock_flow_requires_voice_and_uses_preissued_prompt(client, purpose):
    created, auth = create(client, purpose)
    plan = created["challenge"]["dynamic"]
    assert plan["session_id"] == created["session_id"] and plan["nonce"] == NONCE
    assert created["purpose"] == purpose and created["nonce"] == NONCE
    # The prompt is available before the server has received/scored any face media.
    result = submit_face(client, created, auth)
    assert result["status"] == "voice_challenge"
    assert result["voice_prompt"] == plan["voice_prompt"]
    assert result["voice_challenge_id"] == plan["voice_challenge_id"]
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
    color_end = ch["baseline_ms"] + sum(
        x["hold_ms"] + x["transition_ms"] for x in ch["color_sequence"]
    )
    assert 0 <= plan["frontal_capture_at_ms"] < ch["baseline_ms"]
    assert points[0]["at_ms"] == color_end
    assert all(a["at_ms"] < b["at_ms"] for a, b in zip(points, points[1:], strict=False))
    assert plan["head_start_at_ms"] == points[-1]["at_ms"]
    assert set(plan["head_turns"][:2]) == {"left", "right"}
    assert plan["head_turns"][-1] == "center"
    assert plan["voice_start_at_ms"] == plan["head_start_at_ms"] + 6000


def test_challenges_are_distinct_even_with_the_same_caller_nonce(client):
    plans = [create(client)[0]["challenge"] for _ in range(8)]
    assert len({p["challenge_id"] for p in plans}) == 8
    assert len({p["dynamic"]["voice_challenge_id"] for p in plans}) == 8
    assert len({p["dynamic"]["session_id"] for p in plans}) == 8


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
    created, auth = create(client, scenario="genuine")
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


def test_unverified_reauth_requires_recovery_without_staff_case(client):
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
def test_reauth_with_server_verified_context_has_no_review_case(client, scenario, expected):
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
    created, auth = create(client)
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
