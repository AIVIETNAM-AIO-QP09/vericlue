"""SEC-03: synthetic requests test auth/limits before parsing, without loading real models."""

from datetime import timedelta
from pathlib import Path

import pytest
from conftest import start_session
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.formparsers import MultiPartParser
from starlette.requests import Request
from synthetic_images import synthetic_image

from vericlue_api.core.config import get_settings
from vericlue_api.core.session_ingress import QR_MAX_BYTES, SessionMultipartParser
from vericlue_api.core.session_tokens import token_digest
from vericlue_api.db.models import SessionRow, utcnow
from vericlue_api.main import create_app


def multipart(*parts: tuple[str, str | None, bytes], closed: bool = True) -> bytes:
    body = bytearray()
    for name, filename, data in parts:
        body += b'--audit-boundary\r\nContent-Disposition: form-data; name="'
        body += name.encode() + b'"'
        if filename is not None:
            body += b'; filename="' + filename.encode() + b'"'
        body += b"\r\n\r\n" + data + b"\r\n"
    if closed:
        body += b"--audit-boundary--\r\n"
    return bytes(body)


def post_body(client, sid, auth, body):
    return client.post(
        f"/v1/sessions/{sid}/media",
        headers={**auth, "Content-Type": "multipart/form-data; boundary=audit-boundary"},
        content=body,
    )


@pytest.mark.parametrize("fault", ["missing", "invalid", "wrong_session", "duplicate", "expired"])
def test_rejected_token_never_parses_or_receives_body(client, monkeypatch, fault):
    session, auth = start_session(client)
    sid = session["session_id"]
    if fault == "missing":
        headers = {"Authorization": ""}
    elif fault == "invalid":
        headers = {"Authorization": "Bearer invalid"}
    elif fault == "wrong_session":
        other, _ = start_session(client)
        sid = other["session_id"]
        headers = auth
    elif fault == "duplicate":
        headers = [("Authorization", auth["Authorization"])] * 2
    else:
        with client.app.state.vericlue.transaction() as state:
            state.sessions.get(sid).token_expires_at = utcnow() - timedelta(seconds=1)
        headers = auth

    called = []
    original = MultiPartParser.parse

    async def spy(self):
        called.append(True)
        return await original(self)

    monkeypatch.setattr(MultiPartParser, "parse", spy)
    response = client.post(
        f"/v1/sessions/{sid}/media",
        headers=headers,
        files={"image": ("synthetic.jpg", b"a" * (1100 * 1024), "image/jpeg")},
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "unauthorized"
    assert response.headers["Cache-Control"] == "no-store"
    assert called == []


def test_refreshed_token_is_rejected_before_parser(client, monkeypatch):
    session, auth = start_session(client)
    sid = session["session_id"]
    refreshed = client.post(f"/v1/sessions/{sid}/challenge", headers=auth)
    assert refreshed.status_code == 200

    async def must_not_parse(self):
        raise AssertionError("Revoked token reached the multipart parser")

    monkeypatch.setattr(SessionMultipartParser, "parse", must_not_parse)
    response = client.post(
        f"/v1/sessions/{sid}/media", headers=auth, files={"image": ("face.jpg", b"synthetic")}
    )
    assert response.status_code == 401


@pytest.mark.parametrize("change", ["expire", "replace"])
def test_preflight_releases_db_and_handler_rechecks_after_stream(client, monkeypatch, change):
    session, auth = start_session(client)
    sid = session["session_id"]
    body = multipart(("image", "face.jpg", synthetic_image()))
    changed = []
    parsing = []
    original = SessionMultipartParser.parse

    async def trace(self):
        parsing.append(True)
        return await original(self)

    monkeypatch.setattr(SessionMultipartParser, "parse", trace)

    def stream():
        # Called only when the route starts receiving, after its preflight read.
        assert parsing == [True]
        with client.app.state.vericlue.transaction() as state:
            current = state.sessions.get(sid)
            if change == "expire":
                current.token_expires_at = utcnow() - timedelta(seconds=1)
            else:
                current.token_hash = token_digest("a-replacement-token")
        changed.append(True)
        yield body

    response = post_body(client, sid, auth, stream())
    assert changed == [True]
    assert response.status_code == 401
    assert not (Path(client.app.state.vericlue.settings.media_dir) / sid).exists()


def test_valid_upload_reuses_the_parsed_form_and_does_not_change_filename(client, monkeypatch):
    session, auth = start_session(client)
    sid = session["session_id"]
    counts = []
    filenames = []
    original = MultiPartParser.parse

    async def spy(self):
        counts.append(True)
        form = await original(self)
        filenames.extend((form["image"].filename, form["video"].filename))
        return form

    monkeypatch.setattr(MultiPartParser, "parse", spy)
    response = client.post(
        f"/v1/sessions/{sid}/media",
        headers=auth,
        files={
            "image": ("face.jpg", synthetic_image(b"ingress-valid")),
            "video": ("face.mp4", b"synthetic-video"),
        },
    )
    assert response.status_code == 200
    assert counts == [True]
    assert filenames == ["face.jpg", "face.mp4"]
    with client.app.state.vericlue.transaction() as state:
        stored = state.sessions.get(sid)
        assert stored.images[0].suffix == ".png"
        assert stored.images[0].read_bytes() == synthetic_image(b"ingress-valid")
        assert stored.video.read_bytes() == b"synthetic-video"


@pytest.mark.parametrize(
    "parts",
    [
        [("image", "a.jpg", b"a"), ("image", "b.jpg", b"b")],
        [("image", "a.jpg", b"a"), ("unexpected", "b.bin", b"b")],
        [("image", "a.jpg", b"a"), ("qr", None, b"not-for-face")],
        [("image", None, b"not-a-file")],
        [("image", "a.jpg", b"a"), ("challenge_id", None, b"a"), ("challenge_id", None, b"b")],
    ],
)
def test_duplicate_unexpected_or_wrong_kind_parts_rejected_and_temp_closed(
    client, monkeypatch, parts
):
    import starlette.formparsers as parser_module

    session, auth = start_session(client)
    sid = session["session_id"]
    allocated = []
    original = parser_module.SpooledTemporaryFile

    def temporary(*args, **kwargs):
        file = original(*args, **kwargs)
        allocated.append(file)
        return file

    monkeypatch.setattr(parser_module, "SpooledTemporaryFile", temporary)
    response = post_body(client, sid, auth, multipart(*parts))
    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_multipart"
    assert all(file.closed for file in allocated)
    assert not (Path(client.app.state.vericlue.settings.media_dir) / sid).exists()


def test_file_limit_is_enforced_during_parser_not_after_file_is_spooled(client, monkeypatch):
    session, auth = start_session(client)
    sid = session["session_id"]
    client.app.state.vericlue.settings.max_upload_mb = 1
    writes = []

    async def no_file_write(self, data):
        writes.append(len(data))
        raise AssertionError("Oversize part was passed to UploadFile.write")

    monkeypatch.setattr("starlette.datastructures.UploadFile.write", no_file_write)
    response = post_body(
        client, sid, auth, multipart(("image", "face.jpg", b"a" * (1024 * 1024 + 1)))
    )
    assert response.status_code == 413
    assert response.json()["error_code"] == "upload_too_large"
    assert writes == []


@pytest.mark.parametrize(
    "name,data", [("media_signature", b"a" * 161), ("challenge_id", b"a" * 257)]
)
def test_text_field_byte_limits_apply_before_handler(client, name, data):
    session, auth = start_session(client)
    response = post_body(
        client,
        session["session_id"],
        auth,
        multipart(("image", "face.jpg", b"a"), (name, None, data)),
    )
    assert response.status_code == 413


def test_id_card_qr_limit_and_temporary_file_cleanup(client, monkeypatch):
    session, auth = start_session(client)
    sid = session["session_id"]
    response = client.post(
        f"/v1/sessions/{sid}/id-card",
        headers=auth,
        files={"front": ("front.jpg", b"a"), "back": ("back.jpg", b"b")},
        data={"qr": "x" * (QR_MAX_BYTES + 1)},
    )
    assert response.status_code == 413
    assert not (Path(client.app.state.vericlue.settings.media_dir) / sid).exists()


def test_truncated_multipart_closes_partial_files(client, monkeypatch):
    import starlette.formparsers as parser_module

    session, auth = start_session(client)
    files = []
    original = parser_module.SpooledTemporaryFile

    def temporary(*args, **kwargs):
        f = original(*args, **kwargs)
        files.append(f)
        return f

    monkeypatch.setattr(parser_module, "SpooledTemporaryFile", temporary)
    response = post_body(
        client,
        session["session_id"],
        auth,
        multipart(("image", "face.jpg", b"synthetic"), closed=False),
    )
    assert response.status_code == 400
    assert files and all(file.closed for file in files)


def test_preflight_read_does_not_touch_activity_or_save_snapshot(client):
    from vericlue_api.core.security import preflight_session

    session, auth = start_session(client)
    sid = session["session_id"]
    root = client.app.state.vericlue
    with root.database.sessions() as db:
        row = db.get(SessionRow, sid)
        before = (row.last_activity_at, row.payload, row.media_deleted_at)
    scope = {
        "type": "http",
        "app": client.app,
        "method": "POST",
        "path": f"/v1/sessions/{sid}/media",
        "headers": [(b"authorization", auth["Authorization"].encode())],
    }
    preflight_session(Request(scope), sid)
    with root.database.sessions() as db:
        row = db.get(SessionRow, sid)
        assert (row.last_activity_at, row.payload, row.media_deleted_at) == before


def test_encrypted_session_preflight_rejects_destroyed_key_without_parsing(monkeypatch):
    import base64
    import secrets

    from vericlue_api.db.models import SessionKeyRow

    monkeypatch.setenv("SESSION_PRIVACY", "true")
    monkeypatch.setenv("SESSION_MASTER_KEY", base64.b64encode(secrets.token_bytes(32)).decode())
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        session, auth = start_session(client)
        sid = session["session_id"]
        with client.app.state.vericlue.database.sessions.begin() as db:
            row = db.scalar(select(SessionKeyRow).where(SessionKeyRow.session_id == sid))
            row.wrapped_key, row.destroyed_at = None, utcnow()

        async def must_not_parse(self):
            raise AssertionError("Destroyed key reached parser")

        monkeypatch.setattr(SessionMultipartParser, "parse", must_not_parse)
        response = client.post(
            f"/v1/sessions/{sid}/media", headers=auth, files={"image": ("face.jpg", b"synthetic")}
        )
        assert response.status_code == 410
