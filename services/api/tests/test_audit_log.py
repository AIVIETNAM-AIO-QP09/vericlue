"""Test thuần cho nhật ký băm nối chuỗi (không DB)."""

from __future__ import annotations

import hashlib
import json

from vericlue_api.services.audit_log import (
    GENESIS_HASH,
    ChainEvent,
    compute_hash,
    verify_chain,
)


def _chain(n: int = 4) -> list[ChainEvent]:
    events: list[ChainEvent] = []
    prev = GENESIS_HASH
    for i in range(n):
        payload = {"case_id": "case_x", "action": f"a{i}", "note": f"ghi chú {i}", "n": i}
        digest = compute_hash(prev, payload)
        events.append(ChainEvent(prev, digest, payload))
        prev = digest
    return events


def test_empty_chain_ok():
    check = verify_chain([])
    assert check.ok and check.checked == 0 and check.bad_index is None


def test_valid_chain_ok():
    check = verify_chain(_chain())
    assert check.ok and check.checked == 4
    assert check.bad_index is None and check.reason is None


def test_tamper_payload_in_middle():
    events = _chain()
    mid = events[2]
    events[2] = ChainEvent(mid.prev_hash, mid.hash, {**mid.payload, "note": "đã sửa"})
    check = verify_chain(events)
    assert not check.ok
    assert (check.bad_index, check.reason) == (2, "hash_mismatch")


def test_tamper_prev_hash():
    events = _chain()
    e = events[1]
    events[1] = ChainEvent("f" * 64, e.hash, e.payload)
    check = verify_chain(events)
    assert (check.ok, check.bad_index, check.reason) == (False, 1, "prev_hash_mismatch")


def test_delete_middle_event():
    events = _chain()
    del events[1]
    check = verify_chain(events)
    assert (check.ok, check.bad_index, check.reason) == (False, 1, "prev_hash_mismatch")


def test_reorder_events():
    events = _chain()
    events[1], events[2] = events[2], events[1]
    check = verify_chain(events)
    assert (check.ok, check.bad_index, check.reason) == (False, 1, "prev_hash_mismatch")


def test_delete_first_event():
    events = _chain()[1:]
    assert events[0].prev_hash != GENESIS_HASH
    check = verify_chain(events)
    assert (check.ok, check.bad_index, check.reason) == (False, 0, "prev_hash_mismatch")


def test_compute_hash_matches_manual_definition():
    payload = {"b": 1, "a": "Khuôn mặt không khớp giấy tờ", "note": None}
    prev = "ab" * 32
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert "Khuôn mặt" in canonical  # ensure_ascii=False: giữ nguyên tiếng Việt
    expected = hashlib.sha256((prev + canonical).encode("utf-8")).hexdigest()
    assert compute_hash(prev, payload) == expected
    # thứ tự khóa không ảnh hưởng
    assert compute_hash(prev, dict(reversed(list(payload.items())))) == expected
