"""Kiểm chữ ký kết quả bằng khóa công khai được tin cậy và ngữ cảnh bên tích hợp.

Chỉ xác nhận chữ ký/ngữ cảnh/hạn; bên tích hợp phải dùng result_id một lần cùng
giao dịch của họ và kiểm status. Không tải khóa theo URL trong kết quả.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))
from vericlue_api.core.signing import load_public_key, verify_result  # noqa: E402
from vericlue_api.schemas.result import SignedResult  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--public-key", required=True, type=Path)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--audience", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--purpose", required=True, choices=("reauth", "recovery"))
    args = parser.parse_args(argv)
    try:
        if not args.result.is_file() or not 0 < args.result.stat().st_size <= 8192:
            raise ValueError("Invalid input bounds")
        envelope = SignedResult.model_validate_json(args.result.read_bytes())
        claims = verify_result(
            envelope,
            load_public_key(args.public_key),
            issuer=args.issuer,
            audience=args.audience,
            session_id=args.session_id,
            nonce=args.nonce,
            purpose=args.purpose,
            now=int(datetime.now(UTC).timestamp()),
        )
    except Exception:
        print(json.dumps({"valid": False}))
        return 1
    print(
        json.dumps(
            {
                "valid": True,
                "status": claims.status,
                "result_id": claims.result_id,
                "expires_at": claims.expires_at,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
