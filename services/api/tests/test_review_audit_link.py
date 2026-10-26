"""Real signatures/transactions with synthetic media and fake analysis, never accuracy evidence."""

import base64
import hashlib
import io
import json
import secrets
import zipfile
from pathlib import Path

import pytest
from contract_utils import validate
from PIL import Image
from pydantic import SecretStr
from sqlalchemy import delete, func, select, text
from test_forensic_real import DATA
from test_forensic_real import real_client as real_client

from vericlue_api.core.pdf_bundle import verify_archive
from vericlue_api.db.models import ForensicJobRow, ReviewEventRow, SessionRow
from vericlue_api.schemas.review import MediaRef
from vericlue_api.services import forensic_runner
from vericlue_api.services.pdf_renderer import PdfRenderer
from vericlue_api.services.storage import save_upload

CHECK = "/v1/forensic/review-audit/verify"
PDF = b"%PDF-1.4\nSynthetic integrity bytes only\n%%EOF"


def prepare_case(client, *, initial=True, role="face_video", privacy=False):
    root = client.app.state.vericlue
    if privacy:
        root.settings.session_privacy = True
        root.settings.session_master_key = SecretStr(
            base64.b64encode(secrets.token_bytes(32)).decode()
        )
    created = client.post("/v1/sessions").json()
    sid = created["session_id"]
    auth = {"Authorization": "Bearer " + created["token"]}
    jpeg = io.BytesIO()
    Image.new("RGB", (64, 64), "#274867").save(jpeg, format="JPEG")
    response = client.post(
        f"/v1/sessions/{sid}/media",
        headers=auth,
        files={"image": ("face.jpg", jpeg.getvalue()), "video": ("capture.mp4", DATA)},
    )
    assert response.status_code == 200, response.text
    # Fixture creates a review case without pretending synthetic bytes passed a detector.
    with root.transaction() as state:
        session = state.sessions.get(sid)
        if role != "face_video":
            field = "audio" if role == "voice_audio" else "voice_video"
            suffix = ".wav" if role == "voice_audio" else ".mp4"
            setattr(
                session,
                field,
                save_upload(
                    root.settings.media_dir, sid, role, role + suffix, DATA, privacy=state.privacy
                ),
            )
            session.video = None
        case = state.reviews.add(
            session_id=sid,
            priority="normal",
            scenario="synthetic-test-only",
            results={},
            media=[
                MediaRef(
                    kind="face_video" if role == "face_video" else "voice_audio", url="/synthetic"
                )
            ],
        )
        session.case_id = case.case_id
        state.db.get(SessionRow, sid).ever_review = True
        cid = case.case_id
    if initial:
        response = client.post(
            f"/v1/review/cases/{cid}/initial", json={"decision": "reject", "note": "synthetic note"}
        )
        assert response.status_code == 200, response.text
    return cid, sid


def submit(client, cid=None, data=DATA):
    return client.post(
        "/v1/forensic/jobs",
        files={"file": ("material.mp4", data)},
        data={"review_case_id": cid} if cid is not None else {},
    )


def linked(client, **kwargs):
    cid, sid = prepare_case(client, **kwargs)
    response = submit(client, cid)
    assert response.status_code == 200, response.text
    jid = response.json()["job_id"]
    return cid, sid, jid


def material(client, jid, monkeypatch):
    monkeypatch.setattr(PdfRenderer, "render", lambda *a: PDF)
    response = client.get(f"/v1/forensic/jobs/{jid}/report-bundle")
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        raw, sig = archive.read("report.json"), archive.read("report.sig").decode("ascii")
    key = client.app.state.vericlue.settings.report_signer._key.public_key()
    manifest = verify_archive(response.content, key)
    return {"report_json": raw.decode("ascii"), "signature": sig}, manifest


def finalize_review(client, cid):
    code = client.get("/v1/review/reason-codes").json()["items"][0]["code"]
    response = client.post(
        f"/v1/review/cases/{cid}/decision",
        json={
            "decision": "reject",
            "reason_code": code,
            "note": "synthetic final note",
        },
    )
    assert response.status_code == 200, response.text


def allow_test_corruption(client, tmp_path, operation):
    """Model privileged snapshot corruption only in this test's private SQLite DB."""
    engine = client.app.state.vericlue.database.engine
    assert engine.dialect.name == "sqlite"
    assert Path(engine.url.database).resolve().is_relative_to(tmp_path.resolve())
    statement = {
        "update": "DROP TRIGGER review_events_no_update",
        "delete": "DROP TRIGGER review_events_no_delete",
    }[operation]
    with engine.begin() as connection:
        connection.execute(text(statement))


@pytest.mark.parametrize("role", ["face_video", "voice_audio", "voice_video"])
@pytest.mark.parametrize("privacy", [False, True])
def test_linked_roles_contract_and_signed_report(real_client, monkeypatch, role, privacy):
    cid, sid, jid = linked(real_client, role=role, privacy=privacy)
    job = real_client.get(f"/v1/forensic/jobs/{jid}").json()
    validate(job, "forensic", "ForensicJob")
    anchor = job["review_audit"]
    assert anchor["case_id"] == cid and anchor["session_id"] == sid
    assert (
        anchor["source_role"] == role
        and anchor["source_sha256"] == hashlib.sha256(DATA).hexdigest()
    )
    assert anchor["event_count"] == 1 and anchor["tail_event_id"] > 0
    report = real_client.get(f"/v1/forensic/jobs/{jid}/report")
    assert report.status_code == 200 and anchor["tail_hash"] in report.text and cid in report.text
    body, manifest = material(real_client, jid, monkeypatch)
    assert manifest.job.review_audit.case_id == cid
    response = real_client.post(CHECK, json=body)
    validate(response.json(), "forensic", "ReviewAuditVerifyResponse")
    assert response.json() == {
        "scope": "signed_json_review_audit",
        "signature_valid": True,
        "ok": True,
        "status": "intact",
        "anchored_count": 1,
        "current_count": 1,
        "appended_count": 0,
    }


def test_independent_job_and_signed_unlinked_result_skip_database(real_client, monkeypatch):
    response = submit(real_client)
    assert response.status_code == 200
    jid = response.json()["job_id"]
    assert real_client.get(f"/v1/forensic/jobs/{jid}").json()["review_audit"] is None
    body, _ = material(real_client, jid, monkeypatch)
    monkeypatch.setattr(
        real_client.app.state.vericlue.database, "sessions", lambda *a: pytest.fail("No DB")
    )
    assert real_client.post(CHECK, json=body).json()["status"] == "unlinked"


@pytest.mark.parametrize(
    "fault",
    [
        "unknown",
        "open",
        "different_file",
        "missing_media",
        "expired_media",
        "bad_chain",
        "mirrored_note",
    ],
)
def test_bad_link_never_creates_job_or_leaks_queue_slot(real_client, fault, tmp_path):
    cid, sid = prepare_case(real_client, initial=fault != "open")
    root = real_client.app.state.vericlue
    if fault == "unknown":
        cid = "case_unknown"
    elif fault == "expired_media":
        from vericlue_api.db.models import utcnow

        with root.database.sessions.begin() as db:
            db.get(SessionRow, sid).media_deleted_at = utcnow()
    elif fault in {"missing_media", "bad_chain", "mirrored_note"}:
        if fault != "missing_media":
            allow_test_corruption(real_client, tmp_path, "update")
        with root.transaction() as state:
            session = state.sessions.get(sid)
            if fault == "missing_media":
                session.video.unlink()
            else:
                row = state.db.scalar(select(ReviewEventRow).where(ReviewEventRow.case_id == cid))
                if fault == "bad_chain":
                    row.hash = "f" * 64  # Test-only tampering in isolated DB.
                else:
                    row.note = "changed mirrored note, original payload untouched"
    before = forensic_runner._PENDING
    response = submit(real_client, cid, DATA + b"changed" if fault == "different_file" else DATA)
    assert response.status_code in {404, 409, 410}, response.text
    assert before == forensic_runner._PENDING
    with root.database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(ForensicJobRow)) == 0
    assert not (Path(root.settings.media_dir) / "forensic").exists()


def test_final_append_is_valid_extension_and_new_report_advances_anchor(real_client, monkeypatch):
    cid, _, jid = linked(real_client)
    first, _ = material(real_client, jid, monkeypatch)
    finalize_review(real_client, cid)
    old = real_client.post(CHECK, json=first).json()
    assert old["ok"] and old["status"] == "extended" and old["appended_count"] == 1
    second, manifest = material(real_client, jid, monkeypatch)
    assert manifest.job.review_audit.event_count == 2
    assert real_client.post(CHECK, json=second).json()["status"] == "intact"
    assert real_client.get(f"/v1/forensic/jobs/{jid}").json()["review_audit"]["event_count"] == 2


def test_deleted_tail_is_detected_even_when_remaining_hash_chain_passes(
    real_client, monkeypatch, tmp_path
):
    cid, _, jid = linked(real_client)
    finalize_review(real_client, cid)
    body, manifest = material(real_client, jid, monkeypatch)
    allow_test_corruption(real_client, tmp_path, "delete")
    with real_client.app.state.vericlue.database.sessions.begin() as db:
        # Deliberate corruption of synthetic test DB only; production code never deletes events.
        db.execute(
            delete(ReviewEventRow).where(
                ReviewEventRow.id == manifest.job.review_audit.tail_event_id
            )
        )
    assert real_client.get(f"/v1/review/cases/{cid}/audit/verify").json()["ok"]
    result = real_client.post(CHECK, json=body).json()
    assert result["signature_valid"] and not result["ok"] and result["status"] == "tail_truncated"
    for suffix in ("report", "report-bundle"):
        response = real_client.get(f"/v1/forensic/jobs/{jid}/{suffix}")
        assert (
            response.status_code == 409 and response.json()["error_code"] == "review_audit_invalid"
        )
    assert real_client.get(f"/v1/forensic/jobs/{jid}").json()["review_audit"]["event_count"] == 2


def test_mock_link_is_not_supported_and_bad_case_id_is_rejected(client):
    response = submit(client, "case_unknown")
    assert (
        response.status_code == 409 and response.json()["error_code"] == "review_link_unavailable"
    )
    assert submit(client, "../case_bad").status_code == 422


def test_stale_sqlite_export_cannot_regress_a_newer_checkpoint(real_client, monkeypatch):
    cid, _, jid = linked(real_client)
    root = real_client.app.state.vericlue
    from vericlue_api.core.errors import ApiError

    with pytest.raises(ApiError, match="vừa được cập nhật") as error, root.transaction() as old:
        previous = old.forensic.get(jid)
        previous_row = old.db.get(ForensicJobRow, jid)
        assert previous.review_audit.event_count == 1
        finalize_review(real_client, cid)
        _, newest = material(real_client, jid, monkeypatch)
        assert newest.job.review_audit.event_count == 2
        old.review_audit.refresh(previous, previous_row)
    assert error.value.error_code == "report_conflict"
    assert real_client.get(f"/v1/forensic/jobs/{jid}").json()["review_audit"]["event_count"] == 2


@pytest.mark.parametrize("fault", ["tail_hash", "tail_id", "session_id", "source_hash"])
def test_even_signed_mismatched_anchors_do_not_verify(real_client, monkeypatch, fault):
    _, _, jid = linked(real_client)
    _, manifest = material(real_client, jid, monkeypatch)
    anchor = manifest.job.review_audit
    if fault == "tail_hash":
        anchor.tail_hash = "a" * 64
    elif fault == "tail_id":
        anchor.tail_event_id += 1000
    elif fault == "session_id":
        anchor.session_id = "ses_different"
    else:
        anchor.source_sha256 = "e" * 64
        # The canonical signer revalidates semantic hash binding before signing.
        with pytest.raises(ValueError):
            real_client.app.state.vericlue.settings.report_signer.sign_bundle(manifest)
        return
    raw, sig = real_client.app.state.vericlue.settings.report_signer.sign_bundle(manifest)
    result = real_client.post(
        CHECK, json={"report_json": raw.decode("ascii"), "signature": sig}
    ).json()
    assert result["signature_valid"] and not result["ok"]
    assert result["status"] == ("case_unavailable" if fault == "session_id" else "anchor_mismatch")


@pytest.mark.parametrize("fault", ["json", "sig", "unicode", "noncanonical", "wrong_key"])
def test_invalid_signed_json_does_not_touch_db_or_start_models(real_client, monkeypatch, fault):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from vericlue_api.core.report_signing import ReportSigner

    _, _, jid = linked(real_client)
    body, manifest = material(real_client, jid, monkeypatch)
    if fault == "json":
        body["report_json"] += " "
    elif fault == "sig":
        body["signature"] = "MOCK-" + "a" * 64
    elif fault == "unicode":
        body["report_json"] = "é"
    elif fault == "noncanonical":
        body["report_json"] = json.dumps(json.loads(body["report_json"]), indent=2)
    else:
        signer = ReportSigner(Ed25519PrivateKey.generate())
        manifest.key_id = signer.key_id
        raw, sig = signer.sign_bundle(manifest)
        body = {"report_json": raw.decode("ascii"), "signature": sig}
    root = real_client.app.state.vericlue
    monkeypatch.setattr(root, "initialize", lambda: pytest.fail("No model startup"))
    monkeypatch.setattr(root.database, "sessions", lambda *a: pytest.fail("No DB"))
    assert real_client.post(CHECK, json=body).json() == {
        "scope": "signed_json_review_audit",
        "signature_valid": False,
        "ok": False,
        "status": "invalid_signature",
    }
    real_client.headers.clear()
    assert real_client.post(CHECK, json=body).status_code == 401
