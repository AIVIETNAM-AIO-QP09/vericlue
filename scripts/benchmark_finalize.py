"""Measure HTTP mock finalize on a running API; records machine, commit and every sample."""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import httpx

from vericlue_api.services.provisional_decision import FINALIZE_MODULES
from vericlue_ml.mock import MOCK_DETECTORS

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Generate reproducible latency evidence without model weights or citizen data."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--machine-label", default=platform.node())
    parser.add_argument("--output", type=Path, default=Path("tmp/plat-08-latency.json"))
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True))
    durations = []
    with httpx.Client(base_url=args.api_url, timeout=10) as client:
        health = client.get("/healthz")
        health.raise_for_status()
        assert health.json()["mock_models"] and health.json()["status"] == "ok"
        for _ in range(args.runs):
            created = client.post("/v1/sessions", headers={"X-Mock-Scenario": "genuine"})
            created.raise_for_status()
            body = created.json()
            headers = {"Authorization": "Bearer " + body["token"]}
            prefix = f"/v1/sessions/{body['session_id']}"
            upload = client.post(
                prefix + "/media",
                headers=headers,
                files={"image": ("synthetic.jpg", b"mock-only", "image/jpeg")},
            )
            upload.raise_for_status()
            signal = client.post(
                prefix + "/signals",
                headers=headers,
                json={"color_events": [], "frame_times": []},
            )
            signal.raise_for_status()
            started = perf_counter()
            response = client.post(prefix + "/finalize", headers=headers)
            elapsed = (perf_counter() - started) * 1000
            response.raise_for_status()
            assert response.json() == {"status": "pass"}
            durations.append(elapsed)
    ordered = sorted(durations)
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "commit": commit,
        "dirty": dirty,
        "machine": args.machine_label,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "api_url": args.api_url,
        "scenario": "genuine",
        "api_version": health.json()["version"],
        "model_versions": {str(m): MOCK_DETECTORS[m].version for m in FINALIZE_MODULES},
        "model_versions_source": "mock registry in checkout; API image built from this checkout",
        "runs": args.runs,
        "scope": "HTTP finalize including auth, DB transaction/commit and inference; upload excluded",
        "latency_ms": durations,
        "median_ms": statistics.median(durations),
        "p95_ms": ordered[max(0, (95 * len(ordered) + 99) // 100 - 1)],
        "max_ms": max(durations),
        "all_under_one_second": max(durations) < 1000,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["all_under_one_second"]:
        raise SystemExit("Mock finalize exceeded the one-second acceptance budget")


if __name__ == "__main__":
    main()
