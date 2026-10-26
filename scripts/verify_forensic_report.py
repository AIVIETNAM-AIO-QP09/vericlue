"""Verify exact downloaded HTML bytes with a separately trusted Ed25519 public PEM.

Save X-VeriClue-Signature to a small text file. Do not choose the trusted key from
the HTML itself; a valid signature does not certify the model verdict or source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api" / "src"))
from vericlue_api.core.report_signing import verify_report_digest  # noqa: E402
from vericlue_api.core.signing import load_public_key, public_key_fingerprint  # noqa: E402

MAX_REPORT_BYTES = 64 * 1024 * 1024


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--signature-file", type=Path, required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if not 0 < args.report.stat().st_size <= MAX_REPORT_BYTES:
            raise ValueError("Report size out of bounds")
        if not 0 < args.signature_file.stat().st_size <= 160:
            raise ValueError("Signature size out of bounds")
        signature = args.signature_file.read_text(encoding="ascii").strip()
        digest = hashlib.sha256()
        total = 0
        with args.report.open("rb") as report:
            while chunk := report.read(64 * 1024):
                total += len(chunk)
                if total > MAX_REPORT_BYTES:
                    raise ValueError("Report size out of bounds")
                digest.update(chunk)
        key = load_public_key(args.public_key)
        report_sha256 = digest.hexdigest()
        if total == 0 or not verify_report_digest(report_sha256, signature, key):
            raise ValueError("Report not verified")
    except Exception:
        print(json.dumps({"valid": False}))
        return 1
    print(
        json.dumps(
            {"valid": True, "report_sha256": report_sha256, "key_id": public_key_fingerprint(key)}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
