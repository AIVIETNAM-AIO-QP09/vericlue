"""SEC-02 real ephemeral ECDSA keys and synthetic files; never hardware/biometric data."""

import base64
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


def create(client, *, key=None, scenario="genuine"):
    key = key or ec.generate_private_key(ec.SECP256R1())
    spki = base64.b64encode(
        key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    ).decode()
    response = client.post(
        "/v1/sessions",
        json={
            "purpose": "onboarding",
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
    created, auth, key = create(client)
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
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(created["session_id"])
        with pytest.raises(ApiError):
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
    created, auth, key = create(client)
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
