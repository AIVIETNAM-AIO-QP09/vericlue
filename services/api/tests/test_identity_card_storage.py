"""A rejected/failed rescan must preserve committed identity data and image bytes."""

from pathlib import Path

import pytest
from conftest import start_session
from sqlalchemy.exc import OperationalError
from synthetic_images import synthetic_image

from vericlue_api.core.errors import ApiError
from vericlue_api.services import identity_steps
from vericlue_api.services.identity_runtime import IdentityRuntime
from vericlue_ml.common.result import Gate, Module, ModuleResult, Status

QR = "001099012345||Test Person|01011995|Nam|Synthetic Address|15062021"
FILES = {
    "front": ("front.jpg", synthetic_image(b"original front"), "image/jpeg"),
    "back": ("back.jpg", synthetic_image(b"original back"), "image/jpeg"),
}
REPLACEMENT = {
    "front": ("front.jpg", synthetic_image(b"replacement front"), "image/jpeg"),
    "back": ("back.jpg", synthetic_image(b"replacement back"), "image/jpeg"),
}


def snapshot(client, sid):
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(sid)
        return {
            **{key: value for key, value in vars(session).items() if key.startswith("id_")},
            "results": session.results,
            "front_bytes": session.id_front.read_bytes(),
            "back_bytes": session.id_back.read_bytes(),
        }


def confirmed_card(client, monkeypatch):
    client.app.state.vericlue.settings.identity_lab_url = "http://127.0.0.1:8010"
    monkeypatch.setattr(IdentityRuntime, "scan", lambda *_: {"qr_values": [QR], "fields": {}})
    created, auth = start_session(client)
    sid = created["session_id"]
    endpoint = f"/v1/sessions/{sid}/id-card"
    response = client.post(endpoint, headers=auth, files=FILES)
    assert response.status_code == 200
    assert (
        client.post(endpoint + "/confirm", headers=auth, json=response.json()["fields"]).status_code
        == 200
    )
    with client.app.state.vericlue.transaction() as state:
        state.sessions.get(sid).results[Module.FACE_MATCH] = ModuleResult(
            module=Module.FACE_MATCH,
            model_version="synthetic",
            status=Status.OK,
            gate=Gate.PASS,
            latency_ms=0,
        )
    return sid, auth, endpoint


@pytest.mark.parametrize("stage", ["media", "signals", "face_scored"])
def test_rejected_card_change_does_not_scan_or_write(client, monkeypatch, stage):
    sid, auth, endpoint = confirmed_card(client, monkeypatch)
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(sid)
        if stage == "face_scored":
            session.face_scored = True
        else:
            session.accepted_steps = [stage]
    before = snapshot(client, sid)
    files_before = set(before["id_front"].parent.iterdir())

    def unexpected_scan(*_):
        pytest.fail("A rejected request must not reach the model runtime")

    monkeypatch.setattr(IdentityRuntime, "scan", unexpected_scan)
    response = client.post(endpoint, headers=auth, files=REPLACEMENT)
    assert response.status_code == 409
    assert response.json()["error_code"] == "step_not_allowed"
    assert snapshot(client, sid) == before
    assert set(before["id_front"].parent.iterdir()) == files_before


@pytest.mark.parametrize("failure", ["runtime", "payload", "second_write", "commit"])
def test_failed_rescan_preserves_confirmed_identity_and_both_images(client, monkeypatch, failure):
    sid, auth, endpoint = confirmed_card(client, monkeypatch)
    before = snapshot(client, sid)
    with monkeypatch.context() as patch:
        if failure == "runtime":

            def unavailable(*_):
                raise ApiError(503, "identity_unavailable", "Synthetic runtime failure")

            patch.setattr(IdentityRuntime, "scan", unavailable)
        elif failure == "payload":
            patch.setattr(IdentityRuntime, "scan", lambda *_: {"qr_values": "invalid"})
        elif failure == "second_write":
            original_save = identity_steps.save_upload

            def fail_back(media_dir, folder, stem, filename, data, **kwargs):
                if stem.startswith("id_back"):
                    raise OSError("Synthetic storage failure")
                return original_save(media_dir, folder, stem, filename, data, **kwargs)

            patch.setattr(identity_steps, "save_upload", fail_back)
        else:

            def fail_commit(*_):
                raise OperationalError("COMMIT", {}, RuntimeError("Synthetic commit failure"))

            patch.setattr(
                client.app.state.vericlue.database.engine.dialect, "do_commit", fail_commit
            )

        if failure == "second_write":
            with pytest.raises(OSError, match="Synthetic storage failure"):
                client.post(endpoint, headers=auth, files=REPLACEMENT)
        else:
            response = client.post(endpoint, headers=auth, files=REPLACEMENT)
            assert response.status_code == 503
    assert snapshot(client, sid) == before


@pytest.mark.parametrize("scan_status", ["ok", "retry"])
def test_completed_rescan_uses_new_files_and_invalidates_prior_confirmation(
    client, monkeypatch, scan_status
):
    sid, auth, endpoint = confirmed_card(client, monkeypatch)
    before = snapshot(client, sid)
    if scan_status == "retry":
        monkeypatch.setattr(IdentityRuntime, "scan", lambda *_: {"qr_values": [], "fields": {}})
    response = client.post(endpoint, headers=auth, files=REPLACEMENT)
    assert response.status_code == 200
    assert response.json()["status"] == scan_status
    after = snapshot(client, sid)
    assert not after["id_confirmed"]
    assert after["id_confirmed_fields"] is None
    assert after["id_confirmed_number_hmac"] is None
    assert Module.FACE_MATCH not in after["results"]
    for side in ("front", "back"):
        assert after[f"id_{side}"] != before[f"id_{side}"]
        assert after[f"{side}_bytes"] == REPLACEMENT[side][1]
        assert not Path(before[f"id_{side}"]).exists()
