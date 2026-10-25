"""Account storage/security with synthetic verdicts/vectors; not an eKYC accuracy test.

Successful writes inject the future continuity result through a trusted server
test fixture. No HTTP or production path can manufacture this result today.
"""

import base64
import json
import secrets
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select

from vericlue_api.core.config import get_settings
from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import (
    AccessEventRow,
    AccountRow,
    CleanupAuditRow,
    SessionRow,
    aware,
    utcnow,
)
from vericlue_api.main import create_app
from vericlue_api.services.accounts import (
    ACCOUNT_TTL,
    FACE_VOICE_VERSION,
    AccountStore,
)
from vericlue_api.services.audit_log import ChainEvent, verify_chain
from vericlue_api.services.media_proof import manifest, verify_and_consume
from vericlue_api.services.session_privacy import SessionPrivacy
from vericlue_api.services.storage import cleanup_expired
from vericlue_ml.common.result import Evidence, Module, ModuleResult
from vericlue_ml.face.template import FaceTemplate
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION


@pytest.fixture
def private_client(monkeypatch):
    monkeypatch.setenv("SESSION_PRIVACY", "true")
    monkeypatch.setenv("SESSION_MASTER_KEY", base64.b64encode(secrets.token_bytes(32)).decode())
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client


def real_settings(state):
    # Storage only: never enable production/mock-to-real session transitions.
    return state.settings.model_copy(
        update={
            "use_mock_models": False,
            "identity_face_from_video": True,
            "identity_consistency_required": True,
            "session_face_checks": True,
            "session_face_models": True,
            "session_voice_models": True,
            "id_hmac_key": SecretStr("synthetic-test-key-at-least-32-bytes"),
        }
    )


def verdict(module, version="synthetic-storage-test", **changes):
    return ModuleResult(
        **{
            "module": module,
            "model_version": version,
            "status": "ok",
            "gate": "pass",
            "prob_attack": 0.01,
            "latency_ms": 0,
            **changes,
        }
    )


def prepared(state, *, id_hmac="a" * 64):
    from vericlue_api.schemas.session import CreateSessionRequest

    key = ec.generate_private_key(ec.SECP256R1())
    spki = base64.b64encode(
        key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    ).decode()
    created = state.flow.create(
        "genuine",
        CreateSessionRequest(
            purpose="onboarding",
            nonce="synthetic_nonce_12345678",
            device_public_key_spki=spki,
        ),
    )
    session = state.sessions.get(created.session_id)
    session.completed = True
    session.otp_verified = True
    session.phone_hmac = "b" * 64
    session.id_confirmed = True
    session.id_source = "server_qr"
    session.id_number_hmac = session.id_confirmed_number_hmac = id_hmac
    session.accepted_steps = ["media", "signals", "finalize", "voice"]
    session.voice_requested = session.voice_owed = False
    session.results = {
        m: verdict(m)
        for m in (
            Module.QUALITY,
            Module.FACE_PAD,
            Module.FACE_DEEPFAKE,
            Module.CHROMAPULSE,
            Module.CAMPROBE,
            Module.GAZE_TRACKING,
            Module.HEAD_TURN,
            Module.VOICE_CHALLENGE,
            Module.VOICE_SPOOF,
            Module.LIPSYNC,
        )
    }
    template = FaceTemplate(
        session_id=session.session_id,
        challenge_id=session.challenge.challenge_id,
        model_version=VIDEO_MATCH_VERSION,
        preprocessing="arcface112-rgb-minus1to1-v1",
        source_video_sha256="c" * 64,
        pixels_sha256="d" * 64,
        embedding=(1.0, *([0.0] * 511)),
    )
    session.results[Module.FACE_MATCH] = verdict(
        Module.FACE_MATCH,
        VIDEO_MATCH_VERSION,
        quality={"consistency_verified": True},
        evidence=[
            Evidence(type="text", name="source_video_sha256", value=template.source_video_sha256),
            Evidence(
                type="scalar",
                name="selected_frontal_frame",
                value={"pixels_sha256": template.pixels_sha256},
            ),
        ],
    )
    continuity = verdict(
        Module.FACE_MATCH,
        FACE_VOICE_VERSION,
        evidence=[
            Evidence(type="text", name=name, value=value)
            for name, value in {
                "source_video_sha256": template.source_video_sha256,
                "challenge_id": template.challenge_id,
                "voice_challenge_id": session.voice_challenge_id,
            }.items()
        ],
    )
    for stage in ("face", "voice"):
        files = {
            "video": ("synthetic.mp4", b"synthetic-not-biometric"),
            "image" if stage == "face" else "audio": (
                "synthetic.jpg" if stage == "face" else "synthetic.wav",
                b"synthetic",
            ),
        }
        message, _, _ = manifest(session, stage, files)
        signature = base64.b64encode(key.sign(message, ec.ECDSA(hashes.SHA256()))).decode()
        verify_and_consume(state.db, session, stage, signature, files, required=True)
    state.sessions.record_decision(session, "pass", thresholds={}, config_version="synthetic-test")
    return session, template, continuity


def test_encrypted_roundtrip_idempotency_and_session_key_independence(private_client):
    root = private_client.app.state.vericlue
    with root.transaction() as state:
        session, template, continuity = prepared(state)
        store = AccountStore(real_settings(state), state.db)
        receipt = store.create(session, template, continuity=continuity)
        assert store.create(session, template, continuity=continuity) == receipt
        identity = store.get(receipt.account_id)
        assert identity.template == template
        assert identity.public_key_spki == session.media_public_key_spki
        row = state.db.get(AccountRow, receipt.account_id)
        assert receipt.expires_at - aware(row.created_at) == ACCOUNT_TTL
        encrypted = row.encrypted_payload
        assert "embedding" not in encrypted and "LVFace" not in encrypted
        assert base64.b64decode(encrypted).startswith(b"VCA1")
        assert "embedding" not in repr(identity) and "embedding" not in repr(template)
        assert not session.device_verified  # Registration does not prove a future L0 challenge.
        assert state.db.scalar(select(func.count()).select_from(AccountRow)) == 1
        settings = real_settings(state)
        sid = session.session_id
    with root.database.sessions.begin() as db:
        SessionPrivacy(root.settings, db).destroy(sid)
        assert AccountStore(settings, db).get(receipt.account_id).template == template


@pytest.mark.parametrize("fault", ["mock", "mixed", "privacy_off", "missing_master", "short_hmac"])
def test_unsafe_configuration_cannot_enroll(private_client, fault):
    with private_client.app.state.vericlue.transaction() as state:
        session, template, continuity = prepared(state)
        settings = real_settings(state)
        changes = {
            "mock": {"use_mock_models": True},
            "mixed": {"use_mock_models": "mixed"},
            "privacy_off": {"session_privacy": False},
            "missing_master": {"session_master_key": None},
            "short_hmac": {"id_hmac_key": SecretStr("short")},
        }[fault]
        with pytest.raises(ApiError) as error:
            AccountStore(settings.model_copy(update=changes), state.db).create(
                session, template, continuity=continuity
            )
        assert error.value.status_code == 503
        assert state.db.scalar(select(func.count()).select_from(AccountRow)) == 0


@pytest.mark.parametrize(
    "fault",
    [
        "otp",
        "card",
        "edited",
        "review",
        "not_pass",
        "expired",
        "missing_voice",
        "mock_model",
        "degraded",
        "error",
        "unclear",
        "uncalibrated",
        "wrong_template",
        "different_pixels",
        "different_video",
        "no_consistency",
        "no_continuity",
        "old_continuity",
        "wrong_voice_attempt",
        "changed_key",
        "new_attempt",
        "invalid_vector",
        "nonfinite_probability",
    ],
)
def test_missing_or_mismatched_verification_never_writes_account(private_client, fault):
    with private_client.app.state.vericlue.transaction() as state:
        session, template, continuity = prepared(state)
        if fault == "otp":
            session.otp_verified = False
        elif fault == "card":
            session.id_confirmed_number_hmac = "f" * 64
        elif fault == "edited":
            session.id_edited = ["full_name"]
        elif fault == "review":
            state.db.get(SessionRow, session.session_id).ever_review = True
        elif fault == "not_pass":
            state.db.get(SessionRow, session.session_id).status = "incomplete"
        elif fault == "expired":
            session.token_expires_at = utcnow() - timedelta(seconds=1)
        elif fault == "missing_voice":
            session.accepted_steps.remove("voice")
        elif fault == "mock_model":
            session.results[Module.FACE_PAD].model_version = "mock-face-pad"
        elif fault in {"degraded", "error"}:
            session.results[Module.VOICE_SPOOF].status = fault
        elif fault == "unclear":
            session.results[Module.LIPSYNC].gate = "unclear"
        elif fault == "uncalibrated":
            session.results[Module.FACE_PAD].prob_attack = None
        elif fault == "wrong_template":
            template = template.model_copy(update={"session_id": "ses_other"})
        elif fault in {"different_pixels", "different_video"}:
            field = "pixels_sha256" if fault == "different_pixels" else "source_video_sha256"
            template = template.model_copy(update={field: "e" * 64})
        elif fault == "no_consistency":
            session.results[Module.FACE_MATCH].quality["consistency_verified"] = False
        elif fault == "no_continuity":
            continuity = None
        elif fault == "old_continuity":
            continuity.model_version = VIDEO_MATCH_VERSION
        elif fault == "wrong_voice_attempt":
            session.voice_challenge_id = "vc_other"
        elif fault == "changed_key":
            key = ec.generate_private_key(ec.SECP256R1())
            session.media_public_key_spki = base64.b64encode(
                key.public_key().public_bytes(
                    serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
                )
            ).decode()
        elif fault == "invalid_vector":
            template = template.model_copy(update={"embedding": (1.0,)})
        elif fault == "nonfinite_probability":
            session.results[Module.FACE_PAD].prob_attack = float("nan")
        else:
            session.challenge.media_nonce = secrets.token_hex(32)
        with pytest.raises(ApiError):
            AccountStore(real_settings(state), state.db).create(
                session, template, continuity=continuity
            )
        assert state.db.scalar(select(func.count()).select_from(AccountRow)) == 0


@pytest.mark.parametrize(
    "fault", ["ciphertext", "dek", "account", "device", "identity", "ttl", "master"]
)
def test_tampered_account_never_falls_back_to_plaintext(private_client, fault):
    with private_client.app.state.vericlue.transaction() as state:
        session, template, continuity = prepared(state)
        settings = real_settings(state)
        store = AccountStore(settings, state.db)
        receipt = store.create(session, template, continuity=continuity)
        row = state.db.get(AccountRow, receipt.account_id)
        if fault in {"ciphertext", "dek"}:
            field = "encrypted_payload" if fault == "ciphertext" else "wrapped_key"
            raw = bytearray(base64.b64decode(getattr(row, field)))
            raw[-1] ^= 1
            setattr(row, field, base64.b64encode(raw).decode())
        elif fault == "account":
            row.source_session_id = "ses_wrong"
        elif fault == "device":
            row.device_id = "dev_wrong"
        elif fault == "identity":
            row.id_number_hmac = "f" * 64
        elif fault == "ttl":
            row.expires_at += timedelta(hours=24)
        else:
            store = AccountStore(
                settings.model_copy(
                    update={
                        "session_master_key": SecretStr(
                            base64.b64encode(secrets.token_bytes(32)).decode()
                        )
                    }
                ),
                state.db,
            )
        with pytest.raises(ApiError) as error:
            store.get(receipt.account_id)
        assert error.value.status_code == 503


def test_duplicate_identity_is_atomic_and_expiration_allows_new_session(private_client):
    with private_client.app.state.vericlue.transaction() as state:
        store = AccountStore(real_settings(state), state.db)
        session, template, continuity = prepared(state)
        first = store.create(session, template, continuity=continuity)
        other, other_template, other_continuity = prepared(state)
        with pytest.raises(ApiError) as error:
            store.create(other, other_template, continuity=other_continuity)
        assert error.value.status_code == 409
        assert state.db.scalar(select(func.count()).select_from(AccountRow)) == 1
        # Simulate passage of time for shredding, not a changed authenticated record.
        assert store.expire(now=first.expires_at) == 1
        second = store.create(other, other_template, continuity=other_continuity)
        assert first.account_id != second.account_id
        with pytest.raises(ApiError) as error:
            store.create(session, template, continuity=continuity)
        assert error.value.status_code == 410  # A source session never revives a tombstone.


def test_cleanup_shreds_account_without_master_key_and_is_idempotent(private_client):
    root = private_client.app.state.vericlue
    with root.transaction() as state:
        session, template, continuity = prepared(state)
        receipt = AccountStore(real_settings(state), state.db).create(
            session, template, continuity=continuity
        )
        sid = session.session_id
    # Delay session retention so this cleanup exercises the independent account TTL only.
    cleanup_settings = root.settings.model_copy(
        update={"session_master_key": None, "media_ttl_pass_hours": 100}
    )
    for _ in range(2):
        cleanup_expired(root.database, cleanup_settings, now=receipt.expires_at)
    with root.database.sessions() as db:
        row = db.get(AccountRow, receipt.account_id)
        assert row.destroyed_at is not None
        assert row.wrapped_key is row.encrypted_payload is None
        assert row.id_number_hmac is row.phone_hmac is None
        assert db.get(SessionRow, sid).media_deleted_at is None
        counts = [r.details["expired_accounts"] for r in db.scalars(select(CleanupAuditRow))]
        assert counts[-2:] == [1, 0]


def test_lookup_checks_ttl_even_before_cleanup(private_client, monkeypatch):
    with private_client.app.state.vericlue.transaction() as state:
        session, template, continuity = prepared(state)
        store = AccountStore(real_settings(state), state.db)
        receipt = store.create(session, template, continuity=continuity)
        monkeypatch.setattr("vericlue_api.services.accounts.utcnow", lambda: receipt.expires_at)
        with pytest.raises(ApiError) as error:
            store.get(receipt.account_id)
        assert error.value.status_code == 410


def test_no_public_embedding_or_account_creation_route(private_client):
    text = json.dumps(private_client.get("/openapi.json").json())
    assert "FaceTemplate" not in text and "embedding" not in text
    assert not any("/enroll" in p for p in private_client.app.openapi()["paths"])


def test_account_reads_and_deletion_have_pii_free_append_only_chain(private_client):
    root = private_client.app.state.vericlue
    with root.transaction() as state:
        session, template, continuity = prepared(state)
        store = AccountStore(real_settings(state), state.db)
        receipt = store.create(session, template, continuity=continuity)
        store.get(receipt.account_id)
        store.expire(now=receipt.expires_at)
        events = list(
            state.db.scalars(
                select(AccessEventRow)
                .where(AccessEventRow.scope == "account:" + receipt.account_id)
                .order_by(AccessEventRow.id)
            )
        )
        assert [e.action for e in events] == [
            "account_created",
            "template_read",
            "account_key_destroyed",
        ]
        assert verify_chain([ChainEvent(e.prev_hash, e.hash, e.payload) for e in events]).ok
        serialized = json.dumps([e.payload for e in events])
        assert not any(
            value in serialized for value in ("embedding", "public_key", "phone", "id_number")
        )
