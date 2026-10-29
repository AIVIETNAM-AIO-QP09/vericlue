"""Verify the signed PDF/JSON ZIP using a separately pinned public PEM; never extract/render."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api" / "src"))
from vericlue_api.core.pdf_bundle import MAX_ZIP_BYTES, verify_archive  # noqa: E402
from vericlue_api.core.signing import load_public_key  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--public-key", required=True, type=Path)
    parser.add_argument("--expected-job-id")
    args = parser.parse_args(argv)
    try:
        if not 0 < args.bundle.stat().st_size <= MAX_ZIP_BYTES:
            raise ValueError("Archive bounds")
        with args.bundle.open("rb") as source:
            raw = source.read(MAX_ZIP_BYTES + 1)
        manifest = verify_archive(
            raw, load_public_key(args.public_key), expected_job_id=args.expected_job_id
        )
    except Exception:
        print(json.dumps({"valid": False}))
        return 1
    print(
        json.dumps(
            {
                "valid": True,
                "job_id": manifest.job.job_id,
                "file_sha256": manifest.job.file_sha256,
                "pdf_sha256": manifest.pdf_sha256,
                "key_id": manifest.key_id,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
