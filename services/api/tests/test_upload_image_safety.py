"""SEC-04: real image decoding and transactional storage on synthetic pixels."""

import base64
import io
import secrets
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from conftest import start_session
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr
from sqlalchemy.exc import OperationalError
from synthetic_images import synthetic_image

from vericlue_api.core.errors import ApiError
from vericlue_api.main import create_app
from vericlue_api.services import identity_steps, session_flow, upload_images
from vericlue_api.services.identity_runtime import IdentityRuntime
from vericlue_api.services.session_store import SessionStore
from vericlue_api.services.storage import cleanup_expired

QR = "000000000001||Synthetic Audit|01011995|Nam|Synthetic Address|15062021"


def tagged_image():
    exif = Image.Exif()
    exif[0x010F] = "Synthetic EXIF"
    output = io.BytesIO()
    Image.new("RGB", (64, 64), (100, 120, 140)).save(output, format="JPEG", exif=exif)
    return output.getvalue()


def configure(client, private):
    settings = client.app.state.vericlue.settings
    settings.session_privacy = private
    settings.session_master_key = SecretStr(base64.b64encode(secrets.token_bytes(32)).decode())
    return settings


def card(client, sid, auth, *, image=None):
    image = image or synthetic_image()
    return client.post(
        f"/v1/sessions/{sid}/id-card",
        headers=auth,
        data={"qr": QR},
        files={
            "front": ("front.jpg", image, "image/jpeg"),
            "back": ("back.jpg", image, "image/jpeg"),
        },
    )


def snapshot(client, sid):
    with client.app.state.vericlue.transaction() as state:
        s = state.sessions.get(sid)
        return s.id_front, s.id_back, s.id_scan_count, s.id_scan_bytes


def media_used(client, sid):
    with client.app.state.vericlue.transaction() as state:
        return state.sessions.get(sid).uploaded_media_bytes


def test_total_budget_combines_card_face_video_and_voice(client):
    body, auth = start_session(client, "voice_clone")
    sid = body["session_id"]
    image = synthetic_image()
    assert card(client, sid, auth).status_code == 200
    files = {"image": ("face.bin", image), "video": ("face.webm", b"face video")}
    assert client.post(f"/v1/sessions/{sid}/media", headers=auth, files=files).status_code == 200
    expected = 4 * len(image) + 2 * (len(image) + len(b"face video"))
    assert media_used(client, sid) == expected
    assert (
        client.post(f"/v1/sessions/{sid}/finalize", headers=auth).json()["status"]
        == "voice_challenge"
    )
    files = {"audio": ("voice.wav", b"audio"), "video": ("voice.webm", b"voice video")}
    assert client.post(f"/v1/sessions/{sid}/voice", headers=auth, files=files).status_code == 200
    assert media_used(client, sid) == expected + 2 * (len(b"audio") + len(b"voice video"))


def test_face_refresh_preserves_budget_and_rejected_upload_changes_nothing(client):
    settings = client.app.state.vericlue.settings
    settings.max_session_media_mb = 1
    body, auth = start_session(client)
    sid = body["session_id"]
    image = synthetic_image()
    amount = 2 * len(image)
    with client.app.state.vericlue.transaction() as state:
        state.sessions.get(sid).uploaded_media_bytes = 1024 * 1024 - 2 * amount
    for _ in range(2):
        response = client.post(
            f"/v1/sessions/{sid}/media", headers=auth, files={"image": ("f.bin", image)}
        )
        assert response.status_code == 200
        refreshed = client.post(f"/v1/sessions/{sid}/challenge", headers=auth)
        assert refreshed.status_code == 200
        auth = {"Authorization": "Bearer " + refreshed.json()["token"]}
    assert media_used(client, sid) == 1024 * 1024
    folder = Path(settings.media_dir) / sid
    before = set(folder.iterdir())
    rejected = client.post(
        f"/v1/sessions/{sid}/media", headers=auth, files={"image": ("f.bin", image)}
    )
    assert (
        rejected.status_code == 413
        and rejected.json()["error_code"] == "session_media_quota_exceeded"
    )
    assert media_used(client, sid) == 1024 * 1024 and set(folder.iterdir()) == before


def test_concurrent_card_and_face_share_total_budget(client, monkeypatch):
    settings = client.app.state.vericlue.settings
    settings.max_session_media_mb = 1
    body, auth = start_session(client)
    sid = body["session_id"]
    image = synthetic_image()
    amount = 4 * len(image)
    with client.app.state.vericlue.transaction() as state:
        state.sessions.get(sid).uploaded_media_bytes = 1024 * 1024 - amount
    card_locked, release_card, face_started = Event(), Event(), Event()
    original_save = identity_steps.save_upload

    def hold_card_write(*args, **kwargs):
        if args[2].startswith("id_front"):
            card_locked.set()
            assert release_card.wait(5)
        return original_save(*args, **kwargs)

    monkeypatch.setattr(identity_steps, "save_upload", hold_card_write)

    def send_face():
        face_started.set()
        return client.post(
            f"/v1/sessions/{sid}/media",
            headers=auth,
            files={"image": ("f.bin", image), "video": ("v.webm", image)},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        scanned = pool.submit(card, client, sid, auth)
        try:
            assert card_locked.wait(5)
            face = pool.submit(send_face)
            assert face_started.wait(5)
        finally:
            release_card.set()
        assert scanned.result().status_code == 200
        assert face.result().status_code == 413
    assert media_used(client, sid) == 1024 * 1024
    assert len(list((Path(settings.media_dir) / sid).iterdir())) == 2


def test_refresh_cannot_restore_stale_counter_during_sqlite_upload(client, monkeypatch):
    body, auth = start_session(client)
    sid = body["session_id"]
    paused, release, refresh_started, stale_read = Event(), Event(), Event(), Event()
    original_save, original_get = session_flow.save_upload, SessionStore.get

    def pause_save(*args, **kwargs):
        paused.set()
        assert release.wait(5)
        return original_save(*args, **kwargs)

    def observe_get(*args, **kwargs):
        result = original_get(*args, **kwargs)
        if paused.is_set() and not release.is_set():
            stale_read.set()
        return result

    def refresh():
        refresh_started.set()
        return client.post(f"/v1/sessions/{sid}/challenge", headers=auth)

    monkeypatch.setattr(session_flow, "save_upload", pause_save)
    monkeypatch.setattr(SessionStore, "get", observe_get)
    with ThreadPoolExecutor(max_workers=2) as pool:
        upload = pool.submit(
            client.post,
            f"/v1/sessions/{sid}/media",
            headers=auth,
            files={"image": ("face.bin", synthetic_image())},
        )
        try:
            assert paused.wait(5)
            refreshed = pool.submit(refresh)
            assert refresh_started.wait(5)
            assert not stale_read.wait(0.3)
        finally:
            release.set()
        assert upload.result().status_code == 200
        assert refreshed.result().status_code == 200
    assert media_used(client, sid) == 2 * len(synthetic_image())


def test_signed_raw_image_is_verified_before_normalization_and_invalid_image_rolls_back_nonce(
    client,
):
    from sqlalchemy import func, select
    from test_media_proof import VIDEO, create, send_face, sign

    from vericlue_api.db.models import MediaProofUseRow

    body, auth, key = create(client)
    image = ("face.bin", b"invalid synthetic image")
    proof = sign(client, body, key, files={"image": image, "video": VIDEO})
    rejected = send_face(client, body, auth, proof, image=image)
    assert rejected.status_code == 422
    with client.app.state.vericlue.database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(MediaProofUseRow)) == 0
    assert media_used(client, body["session_id"]) == 0
    image = ("face.bin", tagged_image())
    proof = sign(client, body, key, files={"image": image, "video": VIDEO})
    assert send_face(client, body, auth, proof, image=image).status_code == 200
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(body["session_id"])
        assert not Image.open(session.images[0]).getexif()


@pytest.mark.parametrize("private", [False, True])
@pytest.mark.parametrize("suffix", [".jpg", ".bin", ".mp4"])
def test_image_content_is_sanitized_regardless_name_and_storage_mode(client, private, suffix):
    configure(client, private)
    body, auth = start_session(client)
    sid = body["session_id"]
    response = client.post(
        f"/v1/sessions/{sid}/media",
        headers=auth,
        files={"image": ("face" + suffix, tagged_image(), "application/octet-stream")},
    )
    assert response.status_code == 200, response.text
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(sid)
        assert session.images[0].suffix == ".jpg"
        prepared, lease = state.privacy.prepare(sid, {"images": session.images})
        try:
            with Image.open(prepared["images"][0]) as actual:
                assert actual.size == (64, 64) and not actual.getexif()
        finally:
            if lease:
                lease.release()


@pytest.mark.parametrize("data", [b"not an image", b"GIF89a", b"%PDF-1.7"])
def test_invalid_card_is_rejected_before_ocr_or_storage(client, monkeypatch, data):
    client.app.state.vericlue.settings.identity_lab_url = "http://127.0.0.1:8010"
    seen = []
    monkeypatch.setattr(IdentityRuntime, "scan", lambda *_: seen.append(True))
    body, auth = start_session(client)
    response = card(client, body["session_id"], auth, image=data)
    assert response.status_code == 422 and response.json()["error_code"] == "invalid_image"
    assert not seen
    assert not (Path(client.app.state.vericlue.settings.media_dir) / body["session_id"]).exists()


def test_side_and_pixel_bounds_are_checked_before_decoding_full_image(monkeypatch):
    output = io.BytesIO()
    Image.new("RGB", (4097, 1)).save(output, format="PNG")
    with pytest.raises(ApiError, match="Ảnh"):
        upload_images.prepare_image(output.getvalue())
    monkeypatch.setattr(upload_images, "MAX_IMAGE_PIXELS", 1024)
    with pytest.raises(ApiError):
        upload_images.prepare_image(tagged_image())


def test_orientation_is_applied_and_animated_images_are_rejected():
    output = io.BytesIO()
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.new("RGB", (3, 2), (100, 120, 140)).save(output, format="JPEG", exif=exif)
    prepared = upload_images.prepare_image(output.getvalue())
    with Image.open(io.BytesIO(prepared.data)) as actual:
        assert actual.size == (2, 3) and not actual.getexif()
    output = io.BytesIO()
    Image.new("RGB", (3, 2), "red").save(
        output, format="PNG", save_all=True, append_images=[Image.new("RGB", (3, 2), "blue")]
    )
    with pytest.raises(ApiError):
        upload_images.prepare_image(output.getvalue())


@pytest.mark.parametrize("private", [False, True])
def test_ocr_and_storage_share_same_sanitized_card(client, monkeypatch, private):
    configure(client, private)
    client.app.state.vericlue.settings.identity_lab_url = "http://127.0.0.1:8010"
    seen = []

    def scan(_, front, back):
        seen.append((front, back))
        assert all(not Image.open(io.BytesIO(p)).getexif() for p in (front, back))
        return {"qr_values": [QR], "fields": {}}

    monkeypatch.setattr(IdentityRuntime, "scan", scan)
    body, auth = start_session(client)
    sid = body["session_id"]
    response = card(client, sid, auth, image=tagged_image())
    assert response.status_code == 200
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(sid)
        prepared, lease = state.privacy.prepare(
            sid, {"images": [session.id_front, session.id_back]}
        )
        try:
            assert tuple(p.read_bytes() for p in prepared["images"]) == seen[0]
        finally:
            if lease:
                lease.release()


def test_rescans_only_keep_committed_pair_and_account_both_input_and_canonical_bytes(client):
    body, auth = start_session(client)
    sid = body["session_id"]
    image = synthetic_image()
    one_scan = len(image) * 4
    for index in range(3):
        assert card(client, sid, auth).status_code == 200
        front, back, count, used = snapshot(client, sid)
        assert set(front.parent.iterdir()) == {front, back}
        assert count == index + 1 and used == one_scan * count


@pytest.mark.parametrize("failure", ["second_write", "commit"])
def test_rollback_keeps_old_pair_and_quota_and_removes_new_files(client, monkeypatch, failure):
    body, auth = start_session(client)
    sid = body["session_id"]
    assert card(client, sid, auth).status_code == 200
    before = snapshot(client, sid)
    before_total = media_used(client, sid)
    original_files = set(before[0].parent.iterdir())
    with monkeypatch.context() as patch:
        if failure == "second_write":
            original = identity_steps.save_upload

            def fail_back(*args, **kwargs):
                if args[2].startswith("id_back"):
                    raise ApiError(503, "storage_unavailable", "Synthetic storage failure")
                return original(*args, **kwargs)

            patch.setattr(identity_steps, "save_upload", fail_back)
        else:

            def fail_commit(*_):
                raise OperationalError("COMMIT", {}, RuntimeError("Synthetic failure"))

            patch.setattr(
                client.app.state.vericlue.database.engine.dialect, "do_commit", fail_commit
            )
        assert card(client, sid, auth, image=synthetic_image(b"replacement")).status_code == 503
    assert snapshot(client, sid) == before
    assert media_used(client, sid) == before_total
    assert set(before[0].parent.iterdir()) == original_files


def test_quota_rejection_does_not_mutate_previous_state_or_create_files(client):
    settings = client.app.state.vericlue.settings
    body, auth = start_session(client)
    sid = body["session_id"]
    assert card(client, sid, auth).status_code == 200
    before = snapshot(client, sid)
    settings.max_id_card_scans = 1
    assert card(client, sid, auth).status_code == 409
    assert snapshot(client, sid) == before
    settings.max_id_card_scans = 5
    with client.app.state.vericlue.transaction() as state:
        state.sessions.get(sid).id_scan_bytes = 1024 * 1024
    settings.max_id_card_total_mb = 1
    before = snapshot(client, sid)
    assert card(client, sid, auth).status_code == 413
    assert snapshot(client, sid) == before
    assert set(before[0].parent.iterdir()) == {before[0], before[1]}


def test_two_concurrent_sqlite_rescans_do_not_exceed_last_slot(client):
    settings = client.app.state.vericlue.settings
    settings.max_id_card_scans = 2
    body, auth = start_session(client)
    sid = body["session_id"]
    assert card(client, sid, auth).status_code == 200
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: card(client, sid, auth).status_code, range(2)))
    assert sorted(statuses) == [200, 409]
    front, back, count, _ = snapshot(client, sid)
    assert count == 2 and set(front.parent.iterdir()) == {front, back}
    with TestClient(create_app()) as restarted:
        assert card(restarted, sid, auth).status_code == 409


def test_postcommit_cleanup_error_does_not_turn_success_into_retry(client, monkeypatch, caplog):
    body, auth = start_session(client)
    sid = body["session_id"]
    assert card(client, sid, auth).status_code == 200
    old = set(snapshot(client, sid)[:2])
    original = Path.unlink

    def cannot_remove(path, *args, **kwargs):
        if path in old:
            raise PermissionError("Synthetic cleanup failure")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", cannot_remove)
        assert card(client, sid, auth).status_code == 200
    front, back, count, _ = snapshot(client, sid)
    assert count == 2 and front.exists() and back.exists()
    assert "upload_cleanup_deferred" in caplog.text
    # The session TTL remains the fallback if cleanup failed after a durable commit.
    from datetime import timedelta

    from vericlue_api.db.models import utcnow

    root = client.app.state.vericlue
    cleanup_expired(root.database, settings=root.settings, now=utcnow() + timedelta(hours=25))
    assert not front.parent.exists()
