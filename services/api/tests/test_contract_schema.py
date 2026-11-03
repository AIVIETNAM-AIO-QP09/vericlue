"""Các ràng buộc quan trọng của schema (ADR-0011, luật 'không lộ điểm')."""

from __future__ import annotations

import pytest
from contract_utils import validate
from jsonschema import ValidationError


def head_plan(version=2, duration=12000, **patch):
    import json

    from contract_utils import EXAMPLES_DIR

    value = json.loads((EXAMPLES_DIR / "session.CreateSessionResponse.dynamic.json").read_text())[
        "challenge"
    ]["dynamic"]
    value.update(version=version, head_duration_ms=duration)
    value["voice_start_at_ms"] = value["head_start_at_ms"] + duration
    return {**value, **patch}


@pytest.mark.parametrize("version,duration", [(1, 6000), (2, 12000)])
def test_head_protocol_contract_accepts_exact_pairs(version, duration):
    from vericlue_api.schemas.session import DynamicChallenge

    value = head_plan(version, duration)
    validate(value, "session", "DynamicChallenge")
    assert DynamicChallenge.model_validate(value).head_duration_ms == duration


@pytest.mark.parametrize(
    "version,duration", [(1, 12000), (2, 6000), (3, 12000), (True, 6000), (2, 8000)]
)
def test_head_protocol_contract_rejects_crossed_pairs(version, duration):
    from pydantic import ValidationError as ModelError

    from vericlue_api.schemas.session import DynamicChallenge

    value = head_plan(version, duration)
    with pytest.raises(ValidationError):
        validate(value, "session", "DynamicChallenge")
    with pytest.raises(ModelError):
        DynamicChallenge.model_validate(value)


@pytest.mark.parametrize(
    "patch", [{"head_start_at_ms": 19000, "voice_start_at_ms": 31000}, {"voice_start_at_ms": 1}]
)
def test_head_protocol_model_rejects_invalid_end(patch):
    from pydantic import ValidationError as ModelError

    from vericlue_api.schemas.session import DynamicChallenge

    with pytest.raises(ModelError):
        DynamicChallenge.model_validate(head_plan(**patch))


@pytest.mark.parametrize(
    "patch",
    [
        {"head_mode": "adaptive"},
        {"head_mode": "adaptive", "head_timeout_ms": None},
        {"head_mode": None, "head_timeout_ms": 6000},
        {"head_timeout_ms": 6000},
    ],
)
def test_adaptive_contract_requires_paired_mode_and_budget(patch):
    with pytest.raises(ValidationError):
        validate(head_plan(**patch), "session", "DynamicChallenge")


@pytest.mark.parametrize(
    "patch",
    [
        {},
        {"head_mode": None, "head_timeout_ms": None},
        {"head_mode": "adaptive", "head_timeout_ms": 18000},
    ],
)
def test_adaptive_contract_preserves_timed_and_bounded_adaptive(patch):
    validate(head_plan(**patch), "session", "DynamicChallenge")


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
