"""Nhật ký băm nối chuỗi cho `review_events` (chỉ ghi thêm, mỗi ca một chuỗi).

Định nghĩa băm (ký hiệu "‖" là NỐI CHUỖI KÝ TỰ, không có dấu phân cách):

    hash = sha256( prev_hash ‖ canonical_json(payload) ).hexdigest()

- `prev_hash`: chuỗi hex 64 ký tự của sự kiện trước trong CÙNG ca; sự kiện đầu dùng GENESIS_HASH.
- `canonical_json(payload)`: `json.dumps(payload, sort_keys=True, ensure_ascii=False,
  separators=(",", ":"))`, mã hóa UTF-8 trước khi băm.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

GENESIS_HASH = "0" * 64


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_hash(prev_hash: str, payload: Mapping[str, Any]) -> str:
    """sha256(prev_hash ‖ canonical_json(payload))."""
    return hashlib.sha256((prev_hash + canonical_json(payload)).encode()).hexdigest()


@dataclass(frozen=True)
class ChainEvent:
    """Một sự kiện như đã LƯU (payload đọc lại từ DB, không dựng lại từ trường rời)."""

    prev_hash: str
    hash: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class ChainCheck:
    ok: bool
    checked: int
    bad_index: int | None = None  # vị trí (từ 0) của sự kiện sai đầu tiên
    reason: str | None = None  # prev_hash_mismatch | hash_mismatch


def verify_chain(events: Sequence[ChainEvent]) -> ChainCheck:
    """Duyệt theo thứ tự ghi; trả về sự kiện sai đầu tiên.

    Bắt được: sửa nội dung (hash lệch), sửa prev_hash, xóa/đảo thứ tự/cắt đoạn giữa
    (prev_hash không khớp hash của sự kiện trước). Cắt cụt phần ĐUÔI không phát hiện được bằng
    chuỗi riêng — cần neo hash cuối ở nơi khác (ngoài phạm vi REV-01).
    """
    expected_prev = GENESIS_HASH
    for i, event in enumerate(events):
        if event.prev_hash != expected_prev:
            return ChainCheck(False, i, i, "prev_hash_mismatch")
        if compute_hash(event.prev_hash, event.payload) != event.hash:
            return ChainCheck(False, i, i, "hash_mismatch")
        expected_prev = event.hash
    return ChainCheck(True, len(events))
