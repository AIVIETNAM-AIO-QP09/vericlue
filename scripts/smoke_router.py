"""ROUT-02 mock smoke: seven scenarios, citizen privacy and persisted policy metadata.

Run against an already-started Compose stack. DATABASE_URL is read from env/.env;
use ROUTER_SMOKE_DATABASE_PORT for an isolated Compose host port.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values
from sqlalchemy import select
from sqlalchemy.engine import make_url

from vericlue_api.db.database import Database
from vericlue_api.db.models import DecisionRow, ModuleResultRow


def main() -> None:
    """Run against local mock containers; raise on any policy/audit mismatch."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--web-url", default="http://localhost:3000")
    parser.add_argument("--report", type=Path, default=Path("tmp/rout02-compose-smoke.json"))
    args = parser.parse_args()
    url = os.getenv("DATABASE_URL") or dotenv_values(".env").get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL required for host-side audit verification")
    parsed = make_url(url)
    if port := os.getenv("ROUTER_SMOKE_DATABASE_PORT"):
        parsed = parsed.set(host="127.0.0.1", port=int(port))
    url = parsed.render_as_string(hide_password=False)
    database = Database(url)
    from vericlue_ml.router.config import load_config

    expected_hash = load_config().config_version
    private = {
        "score",
        "prob_attack",
        "evidence",
        "reason",
        "thresholds",
        "config_version",
        "recognized_text",
        "expected_text",
    }

    def check(payload: object) -> None:
        """Reject private fields recursively in citizen responses."""
        if isinstance(payload, dict):
            if private.intersection(payload):
                raise RuntimeError("Private field in citizen response")
            for value in payload.values():
                check(value)
        elif isinstance(payload, list):
            for value in payload:
                check(value)
        elif isinstance(payload, str) and "giả mạo" in payload.lower():
            raise RuntimeError("Forbidden citizen text")

    records = []
    versions = set()
    with httpx.Client(base_url=args.api_url, timeout=10) as client:
        health = client.get("/healthz")
        health.raise_for_status()
        if not health.json().get("mock_models"):
            raise RuntimeError("Mock only smoke")
        web = httpx.get(args.web_url)
        web.raise_for_status()
        for scenario, expected in [
            ("genuine", ["pass"]),
            ("print", ["review"]),
            ("replay", ["review"]),
            ("virtual_cam", ["review"]),
            ("faceswap", ["review"]),
            ("voice_clone", ["voice_challenge", "review"]),
            ("low_quality", ["retry", "retry", "review"]),
        ]:
            created = client.post("/v1/sessions", headers={"X-Mock-Scenario": scenario})
            created.raise_for_status()
            body = created.json()
            check(body)
            sid = body["session_id"]
            auth = {"Authorization": "Bearer " + body["token"]}
            observed = []
            latencies = []
            while len(observed) < len(expected):
                start = time.perf_counter()
                if observed and observed[-1] == "voice_challenge":
                    response = client.post(
                        f"/v1/sessions/{sid}/voice",
                        headers=auth,
                        files={"audio": ("voice.wav", b"synthetic mock smoke", "audio/wav")},
                    )
                else:
                    response = client.post(f"/v1/sessions/{sid}/finalize", headers=auth)
                latencies.append((time.perf_counter() - start) * 1000)
                response.raise_for_status()
                payload = response.json()
                check(payload)
                observed.append(payload["status"])
            if observed != expected:
                raise RuntimeError(f"{scenario}: {observed} != {expected}")
            with database.sessions() as db:
                versions.update(
                    db.scalars(
                        select(ModuleResultRow.model_version).where(
                            ModuleResultRow.session_id == sid
                        )
                    ).all()
                )
                decisions = db.scalars(
                    select(DecisionRow)
                    .where(DecisionRow.session_id == sid)
                    .order_by(DecisionRow.id)
                ).all()
                if len(decisions) != len(expected):
                    raise RuntimeError("Missing decision audit")
                if any(
                    d.config_version != expected_hash
                    or not d.thresholds.get("provisional")
                    or d.thresholds["fusion"]["method"] != "max"
                    for d in decisions
                ):
                    raise RuntimeError("Wrong audit snapshot/hash")
            records.append(
                {
                    "scenario": scenario,
                    "decisions": observed,
                    "latency_ms": latencies,
                    "persisted_decisions": len(decisions),
                    "metadata_verified": True,
                }
            )
    database.dispose()
    report = {
        "client_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        + (
            "-dirty"
            if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
            else ""
        ),
        "machine": platform.node(),
        "platform": platform.platform(),
        "model_versions": sorted(versions),
        "thresholds_config_version": expected_hash,
        "scenarios": records,
        "n_scenarios": len(records),
        "n_decisions": sum(len(r["decisions"]) for r in records),
        "web_http_status": web.status_code,
        "citizen_privacy_verified": True,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
