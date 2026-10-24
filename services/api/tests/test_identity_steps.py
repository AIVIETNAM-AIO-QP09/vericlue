"""FLOW-02 (OTP mô phỏng) và FLOW-03 (nhận CCCD, xác nhận thông tin): chỉ dữ liệu tổng hợp."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest
from conftest import start_session
from contract_utils import validate

from vericlue_api.services.identity_steps import parse_cccd_qr

OTP = "/v1/sessions/{sid}/otp"
VERIFY = "/v1/sessions/{sid}/otp/verify"
ID_CARD = "/v1/sessions/{sid}/id-card"
CONFIRM = "/v1/sessions/{sid}/id-card/confirm"
FINALIZE = "/v1/sessions/{sid}/finalize"
# Dữ liệu bịa, không phải thẻ thật.
QR = "001099012345|123456789|Nguyễn Văn An|01011995|Nam|12 Phố Huế, Hà Nội|15062021"
FILES = {
    "front": ("front.jpg", b"synthetic front", "image/jpeg"),
    "back": ("back.jpg", b"synthetic back", "image/jpeg"),
}


def _session(client, scenario="genuine"):
    body, auth = start_session(client, scenario)
    return body["session_id"], auth


def _code(sms: str) -> str:
    return re.search(r"\b(\d{6})\b", sms).group(1)


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 10**6:06d}"


# --- OTP -----------------------------------------------------------------------------------------
def test_otp_pass_with_the_right_code(client):
    sid, auth = _session(client)
    sent = client.post(OTP.format(sid=sid), headers=auth, json={"phone": "0912345678"})
    assert sent.status_code == 200, sent.text
    validate(sent.json(), "session", "OtpSent")
    res = client.post(
        VERIFY.format(sid=sid), headers=auth, json={"code": _code(sent.json()["simulated_sms"])}
    )
    assert res.json() == {"status": "pass", "attempts_left": 5}


def test_otp_wrong_code_counts_down_then_locks(client):
    sid, auth = _session(client)
    code = _code(
        client.post(OTP.format(sid=sid), headers=auth, json={"phone": "0912345678"}).json()[
            "simulated_sms"
        ]
    )
    for left in (4, 3, 2, 1, 0):
        res = client.post(VERIFY.format(sid=sid), headers=auth, json={"code": _wrong(code)})
        assert res.json() == {"status": "retry", "attempts_left": left}
    locked = client.post(VERIFY.format(sid=sid), headers=auth, json={"code": code})
    assert locked.status_code == 409 and locked.json()["error_code"] == "otp_locked"


def test_otp_expired(client):
    sid, auth = _session(client)
    code = _code(
        client.post(OTP.format(sid=sid), headers=auth, json={"phone": "0912345678"}).json()[
            "simulated_sms"
        ]
    )
    with client.app.state.vericlue.transaction() as state:
        state.sessions.get(sid).otp_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    res = client.post(VERIFY.format(sid=sid), headers=auth, json={"code": code})
    assert res.status_code == 409 and res.json()["error_code"] == "otp_expired"


def test_otp_code_is_single_use(client):
    sid, auth = _session(client)
    code = _code(
        client.post(OTP.format(sid=sid), headers=auth, json={"phone": "0912345678"}).json()[
            "simulated_sms"
        ]
    )
    assert client.post(VERIFY.format(sid=sid), headers=auth, json={"code": code}).status_code == 200
    again = client.post(VERIFY.format(sid=sid), headers=auth, json={"code": code})
    assert again.status_code == 409 and again.json()["error_code"] == "otp_already_verified"


def test_otp_not_requested(client):
    sid, auth = _session(client)
    res = client.post(VERIFY.format(sid=sid), headers=auth, json={"code": "123456"})
    assert res.status_code == 409 and res.json()["error_code"] == "otp_not_requested"


@pytest.mark.parametrize("phone", ["123", "1912345678", "09123456789"])
def test_otp_rejects_bad_phone(client, phone):
    sid, auth = _session(client)
    assert client.post(OTP.format(sid=sid), headers=auth, json={"phone": phone}).status_code == 422


def test_phone_and_code_are_not_stored_in_clear(client):
    sid, auth = _session(client)
    sms = client.post(OTP.format(sid=sid), headers=auth, json={"phone": "0912345678"}).json()[
        "simulated_sms"
    ]
    with client.app.state.vericlue.transaction() as state:
        s = state.sessions.get(sid)
        stored = repr(s.__dict__)
    assert "0912345678" not in stored and _code(sms) not in stored


# --- CCCD ----------------------------------------------------------------------------------------
def test_id_card_ok_returns_fields_from_qr(client):
    sid, auth = _session(client)
    res = client.post(ID_CARD.format(sid=sid), headers=auth, files=FILES, data={"qr": QR})
    assert res.status_code == 200, res.text
    out = res.json()
    validate(out, "session", "IdCardResponse")
    assert out["status"] == "ok"
    assert out["fields"]["id_number"] == "001099012345"
    assert out["fields"]["date_of_birth"] == "1995-01-01"


@pytest.mark.parametrize(
    ("qr", "hint"),
    [(None, "QR_UNREADABLE"), ("", "QR_UNREADABLE"), ("not a card", "QR_INVALID")],
)
def test_id_card_bad_qr_is_a_retry_about_the_photo(client, qr, hint):
    sid, auth = _session(client)
    data = {} if qr is None else {"qr": qr}
    out = client.post(ID_CARD.format(sid=sid), headers=auth, files=FILES, data=data).json()
    assert out == {"status": "retry", "retry_hint": hint}


def test_edited_fields_become_a_note_for_the_reviewer(client):
    sid, auth = _session(client, "print")  # kịch bản mock đi vào bàn duyệt
    client.post(ID_CARD.format(sid=sid), headers=auth, files=FILES, data={"qr": QR})
    res = client.post(
        CONFIRM.format(sid=sid),
        headers=auth,
        json={"full_name": "Nguyễn Văn Ân", "id_number": "001099012345"},
    )
    assert res.json() == {"received": True}
    client.post(
        f"/v1/sessions/{sid}/media", headers=auth, files={"image": ("f.jpg", b"x", "image/jpeg")}
    )
    client.post(FINALIZE.format(sid=sid), headers=auth)
    cases = client.get("/v1/review/cases").json()["items"]
    case_id = next(c["case_id"] for c in cases if c["session_id"] == sid)
    notes = client.get(f"/v1/review/cases/{case_id}").json()["capture_notes"]
    assert any("full_name" in n for n in notes)


def test_confirm_before_id_card_is_409(client):
    sid, auth = _session(client)
    res = client.post(CONFIRM.format(sid=sid), headers=auth, json={"full_name": "A"})
    assert res.status_code == 409 and res.json()["error_code"] == "id_card_not_received"


def test_parse_rejects_wrong_formats():
    assert parse_cccd_qr(QR).sex == "Nam"
    assert parse_cccd_qr("12345|x|A|01011995|Nam|HN") is None  # số CCCD không đủ 12 số
    assert parse_cccd_qr("001099012345|x|A|31021995|Nam|HN") is None  # ngày sinh không có thật
    assert parse_cccd_qr("001099012345|x|A|01011995|Khác|HN") is None
