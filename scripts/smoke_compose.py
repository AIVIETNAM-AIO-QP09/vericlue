"""PLAT-05: smoke a real mock API/web + DB, optionally restarting the API container."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values
from sqlalchemy import func, select

from vericlue_api.db.database import Database
from vericlue_api.db.models import DecisionRow, ModuleResultRow, SessionRow

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--web-url", default="http://localhost:3000")
    parser.add_argument("--restart-api", action="store_true")
    parser.add_argument("--report", type=Path, default=ROOT / "tmp/plat-05-smoke.json")
    args = parser.parse_args()
    started = time.perf_counter()
    with httpx.Client(base_url=args.api_url, timeout=30) as client:
        health = client.get("/healthz")
        health.raise_for_status()
        assert health.json()["mock_models"] is True, "Smoke script requires USE_MOCK_MODELS=true"
        web = httpx.get(args.web_url, timeout=30)
        assert web.status_code == 200
        created = client.post("/v1/sessions", headers={"X-Mock-Scenario": "genuine"})
        created.raise_for_status()
        body = created.json()
        sid = body["session_id"]
        auth = {"Authorization": "Bearer " + body["token"]}
        upload = client.post(
            f"/v1/sessions/{sid}/media",
            headers=auth,
            files={"image": ("face.jpg", b"synthetic mock smoke", "image/jpeg")},
        )
        upload.raise_for_status()
        signals = client.post(
            f"/v1/sessions/{sid}/signals",
            headers=auth,
            json={"color_events": [], "frame_times": []},
        )
        signals.raise_for_status()
        finalized = client.post(f"/v1/sessions/{sid}/finalize", headers=auth)
        finalized.raise_for_status()
        assert finalized.json() == {"status": "pass"}
        database_url = os.environ.get("DATABASE_URL") or dotenv_values(ROOT / ".env").get(
            "DATABASE_URL"
        )
        if not database_url:
            raise ValueError("DATABASE_URL must be set in local .env for host-side DB verification")
        database = Database(database_url)
        try:
            with database.sessions() as db:
                row = db.get(SessionRow, sid)
                assert row is not None and row.status == "pass" and row.decided_at is not None
                assert row.payload["images"] and row.payload["signals"] == {
                    "color_events": [],
                    "frame_times": [],
                }
                modules = db.scalar(
                    select(func.count())
                    .select_from(ModuleResultRow)
                    .where(ModuleResultRow.session_id == sid)
                )
                decisions = db.scalar(
                    select(func.count())
                    .select_from(DecisionRow)
                    .where(DecisionRow.session_id == sid)
                )
                assert modules > 0 and decisions == 1
            if args.restart_api:
                subprocess.run(["docker", "compose", "restart", "api"], cwd=ROOT, check=True)
                deadline = time.monotonic() + 60
                while True:
                    try:
                        if client.get("/healthz").is_success:
                            break
                    except httpx.HTTPError:
                        pass
                    if time.monotonic() > deadline:
                        raise TimeoutError("API did not restart")
                    time.sleep(1)
                restored = client.post(
                    f"/v1/sessions/{sid}/signals",
                    headers=auth,
                    json={"color_events": [], "frame_times": []},
                )
                restored.raise_for_status()
        finally:
            database.dispose()
    report = {
        "session_id": sid,
        "web_status": web.status_code,
        "api_status": health.status_code,
        "outcome": "pass",
        "persisted_modules": modules,
        "persisted_decisions": decisions,
        "survived_restart": args.restart_api,
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
