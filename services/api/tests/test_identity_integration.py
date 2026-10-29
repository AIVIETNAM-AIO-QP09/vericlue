"""Synthetic QR/OCR and fail-closed face threshold integration; no model downloads."""

from types import SimpleNamespace

import pytest
from conftest import start_session
from synthetic_images import synthetic_image

from vericlue_api.core.config import Settings
from vericlue_api.services.identity_runtime import IdentityRuntime
from vericlue_api.services.session_flow import SessionFlow
from vericlue_ml.common.result import Gate, Module, ModuleResult, Status
from vericlue_ml.face.match import MATCH_VERSION
from vericlue_ml.router.policy import Decision

QR = "001099012345||Nguyễn Văn An|01011995|Nam|12 Phố Huế|15062021"
FILES = {
    "front": ("a.jpg", synthetic_image(b"front"), "image/jpeg"),
    "back": ("b.jpg", synthetic_image(b"back"), "image/jpeg"),
}


def enable(client, monkeypatch, payload):
    client.app.state.vericlue.settings.identity_lab_url = "http://127.0.0.1:8010"
    monkeypatch.setattr(IdentityRuntime, "scan", lambda self, front, back: payload)
    body, auth = start_session(client)
    return body["session_id"], auth


def test_server_qr_wins_over_forged_client_qr(client, monkeypatch):
    sid, auth = enable(client, monkeypatch, {"qr_values": [QR], "fields": {"name": "wrong"}})
    response = client.post(
        f"/v1/sessions/{sid}/id-card",
        headers=auth,
        files=FILES,
        data={"qr": QR.replace("001099012345", "001099999999")},
    )
    assert response.status_code == 200
    assert response.json()["fields"]["id_number"] == "001099012345"
    with client.app.state.vericlue.transaction() as state:
        assert state.sessions.get(sid).id_source == "server_qr"


def test_ocr_partial_fields_can_be_corrected_and_persisted(client, monkeypatch):
    sid, auth = enable(client, monkeypatch, {"qr_values": [], "fields": {"name": "An"}})
    assert client.post(f"/v1/sessions/{sid}/id-card", headers=auth, files=FILES).json()[
        "fields"
    ] == {"full_name": "An"}
    endpoint = f"/v1/sessions/{sid}/id-card/confirm"
    assert client.post(endpoint, headers=auth, json={"full_name": "An"}).status_code == 422
    given = {
        "full_name": "Nguyễn Văn An",
        "id_number": "001099012345",
        "date_of_birth": "1995-01-01",
        "sex": "Nam",
        "address": "12 Phố Huế",
    }
    assert client.post(endpoint, headers=auth, json=given).status_code == 200
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(sid)
        assert session.id_confirmed and session.id_fields["full_name"] == "An"
        assert session.id_confirmed_fields["full_name"] == given["full_name"]
        assert "id_number" in session.id_edited
        assert "001099012345" not in repr(session)
    # Rescan invalidates earlier confirmation, even when it returns retry.
    monkeypatch.setattr(IdentityRuntime, "scan", lambda *args: {"qr_values": [], "fields": {}})
    assert (
        client.post(f"/v1/sessions/{sid}/id-card", headers=auth, files=FILES).json()["status"]
        == "retry"
    )
    with client.app.state.vericlue.transaction() as state:
        assert not state.sessions.get(sid).id_confirmed


def test_conflicting_qr_is_not_arbitrarily_selected(client, monkeypatch):
    sid, auth = enable(
        client,
        monkeypatch,
        {"qr_values": [QR, QR.replace("001099012345", "001099999999")], "fields": {}},
    )
    assert (
        client.post(f"/v1/sessions/{sid}/id-card", headers=auth, files=FILES).json()["status"]
        == "retry"
    )


@pytest.mark.parametrize(
    ("confirmed", "edited", "status", "gate", "expected"),
    [
        (True, [], Status.OK, Gate.PASS, "pass"),
        (False, [], Status.OK, Gate.PASS, "review"),
        (True, ["full_name"], Status.OK, Gate.PASS, "review"),
        (True, [], Status.ERROR, Gate.PASS, "review"),
        (True, [], Status.DEGRADED, Gate.PASS, "review"),
        (True, [], Status.OK, Gate.FAIL, "review"),
    ],
)
def test_identity_gate_cannot_bypass_confirmation_or_errors(
    confirmed, edited, status, gate, expected
):
    flow = object.__new__(SessionFlow)
    flow.settings = Settings()
    session = SimpleNamespace(
        id_confirmed=confirmed,
        account_id=None,
        id_edited=edited,
        id_source="ocr",
        results={
            Module.FACE_MATCH: ModuleResult(
                module=Module.FACE_MATCH,
                model_version=MATCH_VERSION,
                status=status,
                gate=gate,
                latency_ms=0,
            )
        },
    )
    assert flow._identity_gate(session, Decision(status="pass")).status == expected
    assert flow._identity_gate(session, Decision(status="review")).status == "review"
    assert flow._identity_gate(session, Decision(status="retry")).status == "retry"


def test_finalize_does_not_leak_face_score(client, monkeypatch):
    sid, auth = enable(client, monkeypatch, {"qr_values": [QR], "fields": {}})
    fields = client.post(f"/v1/sessions/{sid}/id-card", headers=auth, files=FILES).json()["fields"]
    client.post(f"/v1/sessions/{sid}/id-card/confirm", headers=auth, json=fields)

    class SyntheticMatcher:
        def predict(self, inp):
            assert inp.reference_image is not None
            assert inp.image_roles == ["front"] and len(inp.images) == 1
            return ModuleResult(
                module=Module.FACE_MATCH,
                model_version=MATCH_VERSION,
                status=Status.DEGRADED,
                score=0.39,
                gate=Gate.UNCLEAR,
                latency_ms=0,
            )

    client.app.state.vericlue.orchestrator._detectors[Module.FACE_MATCH] = SyntheticMatcher()
    client.post(
        f"/v1/sessions/{sid}/media",
        headers=auth,
        files={"image": ("face.jpg", synthetic_image(b"synthetic"), "image/jpeg")},
    )
    response = client.post(f"/v1/sessions/{sid}/finalize", headers=auth)
    assert response.status_code == 200
    assert response.json()["status"] == "review"
    assert "0.39" not in response.text and "cosine" not in response.text
    with client.app.state.vericlue.transaction() as state:
        assert state.sessions.get(sid).results[Module.FACE_MATCH].score == 0.39


def test_saved_adaface_result_cannot_authorize_a_voice_step_after_migration():
    flow = object.__new__(SessionFlow)
    flow.settings = Settings()
    session = SimpleNamespace(
        id_confirmed=True,
        account_id=None,
        id_edited=[],
        id_source="server_qr",
        results={
            Module.FACE_MATCH: ModuleResult(
                module=Module.FACE_MATCH,
                model_version="adaface-ir18-context@identity-lab-v1",
                status=Status.OK,
                gate=Gate.PASS,
                quality={"threshold_cosine": 0.4},
                latency_ms=0,
            )
        },
    )
    result = flow._identity_gate(session, Decision(status="pass"))
    assert result.status == "review"
    assert "identity_face_cosine" not in result.thresholds
