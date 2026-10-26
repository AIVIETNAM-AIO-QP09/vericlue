"""Các ràng buộc quan trọng của schema (ADR-0011, luật 'không lộ điểm')."""

from __future__ import annotations

import pytest
from contract_utils import validate
from jsonschema import ValidationError

STEP = {"rgb": "#ffcc73", "hold_ms": 500, "transition_ms": 150}


def test_color_step_ok():
    validate(STEP, "session", "ColorStep")


@pytest.mark.parametrize(
    "patch",
    [
        {"hold_ms": 399},
        {"hold_ms": 651},
        {"transition_ms": 0},
        {"transition_ms": 149},
        {"rgb": "red"},
    ],
)
def test_color_step_rejects_unsafe_timing(patch):
    with pytest.raises(ValidationError):
        validate({**STEP, **patch}, "session", "ColorStep")


@pytest.mark.parametrize("def_name", ["FinalizeResponse", "VoiceResponse"])
@pytest.mark.parametrize("extra", ["score", "prob_attack", "gate"])
def test_citizen_responses_reject_score_fields(def_name, extra):
    with pytest.raises(ValidationError):
        validate({"status": "review", extra: 0.5}, "session", def_name)


def test_review_case_rejects_score_fields():
    base = {
        "case_id": "c1",
        "session_id": "s1",
        "status": "open",
        "priority": "normal",
        "created_at": "2026-10-15T08:00:00Z",
        "media": [],
    }
    validate(base, "review", "ReviewCase")
    for extra in ("score", "prob_attack", "modules"):
        with pytest.raises(ValidationError):
            validate({**base, extra: 0.5}, "review", "ReviewCase")


@pytest.mark.parametrize("extra", ["embedding", "public_key_spki", "phone", "score"])
def test_account_receipt_cannot_expose_private_fields(extra):
    receipt = {
        "account_id": "acct_" + "a" * 32,
        "device_id": "dev_" + "b" * 32,
        "expires_at": "2026-10-27T00:00:00Z",
    }
    validate(receipt, "session", "AccountReceipt")
    validate({"status": "pass", "account": receipt}, "session", "VoiceResponse")
    with pytest.raises(ValidationError):
        validate({**receipt, extra: "private"}, "session", "AccountReceipt")
