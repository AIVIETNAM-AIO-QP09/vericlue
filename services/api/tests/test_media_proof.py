"""SEC-02 real ephemeral ECDSA keys and synthetic files; never hardware/biometric data."""

import base64
from datetime import datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import func, select

from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import MediaProofUseRow
from vericlue_api.services.media_proof import manifest, verify_and_consume

IMAGE = ("face.jpg", b"synthetic image")
VIDEO = ("face.mp4", b"synthetic video")
AUDIO = ("voice.wav", b"synthetic audio")


def create(client, *, key=None, scenario="genuine", purpose="onboarding"):
    key = key or ec.generate_private_key(ec.SECP256R1())
    spki = base64.b64encode(
        key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    ).decode()
    response = client.post(
        "/v1/sessions",
        json={
            "purpose": purpose,
            "nonce": "synthetic_client_nonce_12345678",
            "device_public_key_spki": spki,
        },
        headers={"X-Mock-Scenario": scenario},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    return result, {"Authorization": "Bearer " + result["token"]}, key


def sign(client, created, key, stage="face", files=None, offset=None):
    files = files or {"image": IMAGE, "video": VIDEO}
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(created["session_id"])
        payload, _, _ = manifest(session, stage, files, audio_offset_ms=offset)
    return base64.b64encode(key.sign(payload, ec.ECDSA(hashes.SHA256()))).decode()


def send_face(client, created, auth, proof, *, image=IMAGE, video=VIDEO):
    data = {"challenge_id": created["challenge"]["challenge_id"]}
    if proof is not None:
        data["media_signature"] = proof
    return client.post(
        f"/v1/sessions/{created['session_id']}/media",
        headers=auth,
        data=data,
        files={"image": image, "video": video},
    )


def face_outcome(client, created, auth):
    root = f"/v1/sessions/{created['session_id']}"
    cid = created["challenge"]["challenge_id"]
    assert (
        client.post(
            root + "/signals",
            headers=auth,
            json={"challenge_id": cid, "color_events": [], "frame_times": []},
        ).status_code
        == 200
    )
    response = client.post(root + "/finalize", headers=auth, json={"challenge_id": cid})
    assert response.status_code == 200, response.text
    return response.json()


def test_signed_face_voice_full_mock_flow_and_durable_nullifiers(client):
    # Recovery always reads a sentence; onboarding only when the face is unclear.
    created, auth, key = create(client, purpose="recovery")
    assert len(created["challenge"]["media_nonce"]) == 64
    assert send_face(client, created, auth, sign(client, created, key)).status_code == 200
    result = face_outcome(client, created, auth)
    assert result["status"] == "voice_challenge"
    proof = sign(client, created, key, "voice", {"audio": AUDIO, "video": VIDEO}, 600)
    response = client.post(
        f"/v1/sessions/{created['session_id']}/voice",
        headers=auth,
        data={
            "voice_challenge_id": result["voice_challenge_id"],
            "media_signature": proof,
            "audio_offset_ms": "600",
        },
        files={"audio": AUDIO, "video": VIDEO},
    )
    assert response.status_code == 200 and response.json() == {"status": "pass"}, response.text
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(created["session_id"])
        assert not session.device_verified  # No self-asserted key becomes an enrolled device.
        used = list(
            state.db.scalars(
                select(MediaProofUseRow).where(MediaProofUseRow.session_id == created["session_id"])
            )
        )
        assert {r.stage for r in used} == {"face", "voice"}
        assert len({r.nonce_hash for r in used}) == 2


@pytest.mark.parametrize(
    "fault", ["missing", "wrong_key", "image", "video", "suffix", "session", "bad_base64"]
)
def test_rejected_signature_writes_no_media_or_nullifier(client, fault):
    created, auth, key = create(client)
    proof = sign(
        client, created, ec.generate_private_key(ec.SECP256R1()) if fault == "wrong_key" else key
    )
    image, video = IMAGE, VIDEO
    if fault == "missing":
        proof = None
    elif fault == "image":
        image = (IMAGE[0], b"changed image")
    elif fault == "video":
        video = (VIDEO[0], b"changed video")
    elif fault == "suffix":
        video = ("video.webm", VIDEO[1])
    elif fault == "bad_base64":
        proof = "!!!"
    elif fault == "session":
        created, auth, _ = create(client, key=key)
    response = send_face(client, created, auth, proof, image=image, video=video)
    assert response.status_code == 409 and response.json()["error_code"] == "media_not_accepted"
    root = client.app.state.vericlue
    assert not (Path(root.settings.media_dir) / created["session_id"]).exists()
    with root.database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(MediaProofUseRow)) == 0


def test_proof_cannot_be_replayed_after_client_reconnect(client):
    created, auth, key = create(client)
    proof = sign(client, created, key)
    assert send_face(client, created, auth, proof).status_code == 200
    with pytest.raises(ApiError), client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(created["session_id"])
        verify_and_consume(state.db, session, "face", proof, {"image": IMAGE, "video": VIDEO})


def test_refresh_rotates_nonce_and_rejects_old_signature(client):
    created, auth, key = create(client)
    proof = sign(client, created, key)
    refreshed = client.post(f"/v1/sessions/{created['session_id']}/challenge", headers=auth)
    assert refreshed.status_code == 200
    updated = refreshed.json()
    assert updated["challenge"]["media_nonce"] != created["challenge"]["media_nonce"]
    created.update(challenge=updated["challenge"], token=updated["token"])
    auth = {"Authorization": "Bearer " + updated["token"]}
    assert send_face(client, created, auth, proof).status_code == 409
    assert send_face(client, created, auth, sign(client, created, key)).status_code == 200


def test_retry_rotates_nonce(client):
    created, auth, key = create(client, scenario="low_quality")
    assert send_face(client, created, auth, sign(client, created, key)).status_code == 200
    result = face_outcome(client, created, auth)
    assert result["status"] == "retry"
    assert result["challenge"]["media_nonce"] != created["challenge"]["media_nonce"]


@pytest.mark.parametrize("fault", ["offset", "audio", "missing"])
def test_voice_signature_binds_audio_and_offset(client, fault):
    created, auth, key = create(client, purpose="recovery")
    assert send_face(client, created, auth, sign(client, created, key)).status_code == 200
    result = face_outcome(client, created, auth)
    proof = sign(client, created, key, "voice", {"audio": AUDIO, "video": VIDEO}, 600)
    response = client.post(
        f"/v1/sessions/{created['session_id']}/voice",
        headers=auth,
        data={
            "voice_challenge_id": result["voice_challenge_id"],
            "media_signature": proof if fault != "missing" else "",
            "audio_offset_ms": "700" if fault == "offset" else "600",
        },
        files={"audio": (AUDIO[0], b"changed") if fault == "audio" else AUDIO, "video": VIDEO},
    )
    assert response.status_code == 409
    with client.app.state.vericlue.database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(MediaProofUseRow)) == 1


def test_required_mode_has_no_unsigned_legacy_path(client, monkeypatch):
    monkeypatch.setattr(client.app.state.vericlue.settings, "require_media_proof", True)
    assert client.post("/v1/sessions").status_code == 409
    assert (
        client.post(
            "/v1/sessions", json={"purpose": "onboarding", "nonce": "synthetic_nonce_1234"}
        ).status_code
        == 409
    )


def test_new_key_cannot_claim_reauthentication_device(client):
    key = ec.generate_private_key(ec.SECP256R1())
    spki = base64.b64encode(
        key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    ).decode()
    response = client.post(
        "/v1/sessions",
        json={"purpose": "reauth", "nonce": "synthetic_nonce_1234", "device_public_key_spki": spki},
    )
    assert response.status_code == 503


def test_shared_android_canonical_vector_and_signature():
    import json
    from types import SimpleNamespace

    from vericlue_api.services.media_proof import public_key

    root = Path(__file__).resolve().parents[3]
    vector = json.loads((root / "packages/contracts/test-vectors/media-proof-v1.json").read_text())
    session = SimpleNamespace(
        session_id="ses_golden",
        purpose="onboarding",
        nonce="synthetic_nonce_1234",
        voice_challenge_id=None,
        challenge=SimpleNamespace(challenge_id="ch_golden", media_nonce=vector["seed"]),
    )
    data, _, _ = manifest(session, "face", {"image": ("face.jpg", b"abc")})
    assert data.decode("ascii") == vector["canonical"]
    public_key(vector["public_key_spki"]).verify(
        base64.b64decode(vector["signature"]), data, ec.ECDSA(hashes.SHA256())
    )


@pytest.mark.parametrize("kind", ["wrong_curve", "malformed", "trailing_data"])
def test_key_validation_rejects_unsupported_or_noncanonical_keys(client, kind):
    key = ec.generate_private_key(ec.SECP384R1() if kind == "wrong_curve" else ec.SECP256R1())
    raw = key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    if kind == "trailing_data":
        raw += b"trailing"
    value = "!!!" if kind == "malformed" else base64.b64encode(raw).decode()
    response = client.post(
        "/v1/sessions",
        json={
            "purpose": "onboarding",
            "nonce": "synthetic_nonce_1234",
            "device_public_key_spki": value,
        },
    )
    assert response.status_code == 409


def test_signature_is_verified_before_exif_removal_and_encryption(client, monkeypatch):
    import io
    import secrets

    from PIL import Image
    from pydantic import SecretStr

    root = client.app.state.vericlue
    monkeypatch.setattr(root.settings, "session_privacy", True)
    monkeypatch.setattr(
        root.settings,
        "session_master_key",
        SecretStr(base64.b64encode(secrets.token_bytes(32)).decode()),
    )
    output = io.BytesIO()
    exif = Image.Exif()
    exif[0x010F] = "Synthetic device"
    Image.new("RGB", (64, 64)).save(output, format="JPEG", exif=exif)
    image = ("face.jpg", output.getvalue())
    created, auth, key = create(client)
    proof = sign(client, created, key, files={"image": image, "video": VIDEO})
    assert send_face(client, created, auth, proof, image=image).status_code == 200
    with root.transaction() as state:
        session = state.sessions.get(created["session_id"])
        assert session.images[0].read_bytes().startswith(b"VCL1")
        prepared, lease = state.privacy.prepare(session.session_id, {"images": session.images})
        try:
            with Image.open(prepared["images"][0]) as decoded:
                assert not decoded.getexif()
        finally:
            lease.release()
    assert face_outcome(client, created, auth)["status"] == "pass"  # clear face: no sentence


def test_enabling_required_mode_does_not_accept_already_uploaded_unsigned_session(
    client, monkeypatch
):
    created = client.post("/v1/sessions").json()
    auth = {"Authorization": "Bearer " + created["token"]}
    assert (
        client.post(
            f"/v1/sessions/{created['session_id']}/media", headers=auth, files={"image": IMAGE}
        ).status_code
        == 200
    )
    monkeypatch.setattr(client.app.state.vericlue.settings, "require_media_proof", True)
    response = client.post(f"/v1/sessions/{created['session_id']}/finalize", headers=auth)
    assert response.status_code == 409 and response.json()["error_code"] == "media_not_accepted"


@pytest.mark.parametrize("stage", ["face", "voice"])
def test_storage_failure_rolls_back_nonce_and_allows_exact_signed_retry(client, monkeypatch, stage):
    """A proof must not be consumed if the request fails before media is stored."""
    from vericlue_api.services import session_flow

    created, auth, key = create(client)
    if stage == "voice":
        assert send_face(client, created, auth, sign(client, created, key)).status_code == 200
        voice = face_outcome(client, created, auth)
        proof = sign(client, created, key, "voice", {"audio": AUDIO})

        def send():
            return client.post(
                f"/v1/sessions/{created['session_id']}/voice",
                headers=auth,
                data={"voice_challenge_id": voice["voice_challenge_id"], "media_signature": proof},
                files={"audio": AUDIO},
            )
    else:
        proof = sign(client, created, key)

        def send():
            return send_face(client, created, auth, proof)

    original = session_flow.save_upload

    def fail_storage(*args, **kwargs):
        raise ApiError(503, "storage_unavailable", "Chưa thể lưu bản ghi.")

    monkeypatch.setattr(session_flow, "save_upload", fail_storage)
    response = send()
    assert response.status_code == 503, response.text
    root = client.app.state.vericlue
    with root.database.sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(MediaProofUseRow)
                .where(MediaProofUseRow.stage == stage)
            )
            == 0
        )
    with root.transaction() as state:
        session = state.sessions.get(created["session_id"])
        assert ("media" if stage == "face" else "voice") not in session.accepted_steps
    monkeypatch.setattr(session_flow, "save_upload", original)
    assert send().status_code == 200


@pytest.mark.parametrize("stage", ["face", "voice"])
@pytest.mark.parametrize("expire_during_read", [False, True])
def test_signed_upload_expiry_rejected_without_writes_or_consumption(
    client, monkeypatch, stage, expire_during_read
):
    """Exercise HTTP guards before and after reading multipart file contents, with no sleep."""
    from vericlue_api.routers import sessions as routes
    from vericlue_api.services import session_flow

    created, auth, key = create(client)
    if stage == "voice":
        assert send_face(client, created, auth, sign(client, created, key)).status_code == 200
        voice = face_outcome(client, created, auth)
        proof = sign(client, created, key, "voice", {"audio": AUDIO})
    else:
        proof = sign(client, created, key)
    root = client.app.state.vericlue
    with root.transaction() as state:
        session = state.sessions.get(created["session_id"])
        expires = session.voice_expires_at if stage == "voice" else session.challenge.expires_at
    directory = Path(root.settings.media_dir) / created["session_id"]
    before = {p.name: p.read_bytes() for p in directory.iterdir()} if directory.exists() else {}

    class Clock(datetime):
        expired = not expire_during_read

        @classmethod
        def now(cls, tz=None):
            return expires if cls.expired else datetime.now(tz)

    monkeypatch.setattr(session_flow, "datetime", Clock)
    original = routes.read_limited

    async def expire_read(*args, **kwargs):
        data = await original(*args, **kwargs)
        Clock.expired = True
        return data

    monkeypatch.setattr(routes, "read_limited", expire_read)
    if stage == "face":
        response = send_face(client, created, auth, proof)
    else:
        response = client.post(
            f"/v1/sessions/{created['session_id']}/voice",
            headers=auth,
            data={"voice_challenge_id": voice["voice_challenge_id"], "media_signature": proof},
            files={"audio": AUDIO},
        )
    assert response.status_code == 409 and response.json()["error_code"] == "challenge_expired"
    after = {p.name: p.read_bytes() for p in directory.iterdir()} if directory.exists() else {}
    assert after == before
    with root.database.sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(MediaProofUseRow)
                .where(MediaProofUseRow.stage == stage)
            )
            == 0
        )


def test_retry_rejects_previous_proof_even_when_relabelled_as_current_attempt(client):
    created, auth, key = create(client, scenario="low_quality")
    old_proof = sign(client, created, key)
    assert send_face(client, created, auth, old_proof).status_code == 200
    result = face_outcome(client, created, auth)
    assert result["status"] == "retry"
    updated = {**created, "challenge": result["challenge"]}
    assert send_face(client, updated, auth, old_proof).json()["error_code"] == "media_not_accepted"
    assert send_face(client, updated, auth, sign(client, updated, key)).status_code == 200


def test_voice_reread_rejects_old_id_and_old_proof_with_new_id(client):
    from vericlue_ml.common.result import Gate, Module, ModuleResult, Status

    created, auth, key = create(client)
    assert send_face(client, created, auth, sign(client, created, key)).status_code == 200
    voice = face_outcome(client, created, auth)
    old_proof = sign(client, created, key, "voice", {"audio": AUDIO})
    root = client.app.state.vericlue

    class WrongPhraseDetector:
        def predict(self, inp):
            return ModuleResult(
                module=Module.VOICE_CHALLENGE,
                model_version="mock@wrong-phrase",
                status=Status.OK,
                gate=Gate.FAIL,
                latency_ms=0,
            )

    original = root.orchestrator._detectors[Module.VOICE_CHALLENGE]
    root.orchestrator._detectors[Module.VOICE_CHALLENGE] = WrongPhraseDetector()

    def send(attempt, proof):
        return client.post(
            f"/v1/sessions/{created['session_id']}/voice",
            headers=auth,
            data={"voice_challenge_id": attempt, "media_signature": proof},
            files={"audio": AUDIO},
        )

    response = send(voice["voice_challenge_id"], old_proof)
    assert response.status_code == 200, response.text
    reread = response.json()
    assert reread["status"] == "voice_challenge"
    assert reread["voice_challenge_id"] != voice["voice_challenge_id"]
    assert send(voice["voice_challenge_id"], old_proof).json()["error_code"] == "challenge_mismatch"
    assert (
        send(reread["voice_challenge_id"], old_proof).json()["error_code"] == "media_not_accepted"
    )
    root.orchestrator._detectors[Module.VOICE_CHALLENGE] = original
    new_proof = sign(client, created, key, "voice", {"audio": AUDIO})
    response = send(reread["voice_challenge_id"], new_proof)
    assert response.status_code == 200 and response.json() == {"status": "pass"}


def test_signed_upload_replay_guard_survives_application_restart(client):
    from fastapi.testclient import TestClient

    from vericlue_api.main import create_app

    created, auth, key = create(client)
    proof = sign(client, created, key)
    assert send_face(client, created, auth, proof).status_code == 200
    with TestClient(create_app()) as restarted:
        response = send_face(restarted, created, auth, proof)
        assert response.status_code == 409
        assert response.json()["error_code"] == "step_already_received"
    with client.app.state.vericlue.database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(MediaProofUseRow)) == 1


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("genuine", "pass"),
        ("low_quality", "review"),
        ("print", "review"),
        ("replay", "review"),
        ("virtual_cam", "review"),
        ("faceswap", "review"),
        ("voice_clone", "review"),
        ("error", "review"),
    ],
)
def test_signed_mock_scenarios_close_once_and_keep_all_nonce_claims(client, scenario, expected):
    """Full API transactions, real crypto and mock detectors; never biometric accuracy evidence."""
    from vericlue_api.db.models import DecisionRow

    created, auth, key = create(client, scenario=scenario)
    root = f"/v1/sessions/{created['session_id']}"
    face_attempts = 0
    while True:
        proof = sign(client, created, key)
        assert send_face(client, created, auth, proof).status_code == 200
        face_attempts += 1
        outcome = face_outcome(client, created, auth)
        if outcome["status"] != "retry":
            break
        assert face_attempts <= 2
        created = {**created, "challenge": outcome["challenge"]}
    voice_attempts = 0
    if outcome["status"] == "voice_challenge":
        voice_attempts = 1
        proof = sign(client, created, key, "voice", {"audio": AUDIO})
        response = client.post(
            root + "/voice",
            headers=auth,
            data={"voice_challenge_id": outcome["voice_challenge_id"], "media_signature": proof},
            files={"audio": AUDIO},
        )
        assert response.status_code == 200, response.text
        outcome = response.json()
    assert outcome == {"status": expected}
    assert face_attempts == (3 if scenario == "low_quality" else 1)
    assert voice_attempts == (1 if scenario in {"genuine", "voice_clone"} else 0)
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(created["session_id"])
        assert session.completed
        assert not session.device_verified
        claims = list(
            state.db.scalars(
                select(MediaProofUseRow).where(MediaProofUseRow.session_id == session.session_id)
            )
        )
        assert len(claims) == face_attempts + voice_attempts
        decision_count = state.db.scalar(
            select(func.count())
            .select_from(DecisionRow)
            .where(DecisionRow.session_id == session.session_id)
        )
    for step, kwargs in [
        ("media", {"files": {"image": IMAGE}}),
        ("finalize", {"json": {"challenge_id": created["challenge"]["challenge_id"]}}),
        ("voice", {"files": {"audio": AUDIO}}),
    ]:
        # Include the current IDs so the state guard, rather than the binding guard, rejects.
        if step == "media":
            kwargs["data"] = {"challenge_id": created["challenge"]["challenge_id"]}
        if step == "voice":
            with client.app.state.vericlue.transaction() as state:
                current = state.sessions.get(created["session_id"])
                kwargs["data"] = {"voice_challenge_id": current.voice_challenge_id}
        response = client.post(root + "/" + step, headers=auth, **kwargs)
        assert response.status_code == 409, response.text
    with client.app.state.vericlue.database.sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(DecisionRow)
                .where(DecisionRow.session_id == created["session_id"])
            )
            == decision_count
        )
