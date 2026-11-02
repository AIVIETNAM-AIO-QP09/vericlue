"""Compare opt-in Android numbers with the same encrypted server attempt, without exporting media."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for relative in ("services/api/src", "ml/src"):
    sys.path.insert(0, str(ROOT / relative))

import numpy as np  # noqa: E402
from sqlalchemy import select  # noqa: E402

from vericlue_api.core.config import Settings  # noqa: E402
from vericlue_api.core.retention import ensure_session_retained  # noqa: E402
from vericlue_api.db.database import Database  # noqa: E402
from vericlue_api.db.models import SessionRow  # noqa: E402
from vericlue_api.services.session_privacy import SessionPrivacy  # noqa: E402
from vericlue_ml.presence.gaze import GAZE_VERSION  # noqa: E402
from vericlue_ml.presence.head_turn import (  # noqa: E402
    HEAD_VERSION,  # noqa: E402
    MAX_PITCH_ROLL_DEG,
    TURN_MAX_DEG,
)
from vericlue_ml.presence.landmarks import FaceObservation, FaceObservationReader  # noqa: E402


def match_attempt(trace: dict, payloads: list[dict]) -> dict:
    """An absent/ambiguous digest never falls back to the latest attempt."""
    digest = trace.get("attempt_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("Missing diagnostic attempt binding")
    matches = []
    for payload in payloads:
        identifier = payload.get("challenge", {}).get("challenge_id")
        if (
            isinstance(identifier, str)
            and hashlib.sha256(identifier.encode()).hexdigest() == digest
        ):
            matches.append(payload)
    if len(matches) != 1:
        raise ValueError("Diagnostic attempt not found or ambiguous")
    return matches[0]


def _finite(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def compare_observations(trace: dict, rows: list[FaceObservation], dynamic: dict) -> dict:
    """Report raw disagreements only; these aggregates never decide verification."""
    events = trace.get("events", [])
    deltas, age, dot_errors, pair_offsets = [], [], [], []
    outside = no_face = 0

    def nearest(event):
        timestamp = event.get("frame_ms")
        if not rows or not _finite(timestamp):
            return None
        row = min(rows, key=lambda r: abs(r.at_ms - timestamp))
        return row if abs(row.at_ms - timestamp) <= 100 else None

    marks = dynamic.get("gaze_points", [])
    for event in events:
        if event.get("kind") == "face":
            if _finite(event.get("age_ms")):
                age.append(event["age_ms"])
            row = nearest(event)
            if row and row.face_count == 1 and _finite(row.yaw_deg) and _finite(event.get("yaw")):
                deltas.append(event["yaw"] - row.yaw_deg)
                pair_offsets.append(abs(row.at_ms - event["frame_ms"]))
        elif event.get("kind") == "guidance" and event.get("state") in {"Hold", "Completed"}:
            row = nearest(event)
            if row:
                if row.face_count != 1:
                    no_face += 1
                elif all(_finite(v) for v in (row.yaw_deg, row.pitch_deg, row.roll_deg)):
                    outside += int(
                        abs(row.yaw_deg) > TURN_MAX_DEG
                        or abs(row.pitch_deg) > MAX_PITCH_ROLL_DEG
                        or abs(row.roll_deg) > MAX_PITCH_ROLL_DEG
                    )
        elif event.get("kind") == "dot" and len(marks) >= 2:
            at = event.get("at_ms")
            if not all(_finite(event.get(k)) for k in ("at_ms", "x", "y")):
                continue
            if marks[0]["at_ms"] <= at <= marks[-1]["at_ms"]:
                expected = [
                    float(np.interp(at, [m["at_ms"] for m in marks], [m[axis] for m in marks]))
                    for axis in ("x", "y")
                ]
                dot_errors.append(max(abs(event["x"] - expected[0]), abs(event["y"] - expected[1])))
    return {
        "pose_pairs": len(deltas),
        "median_yaw_delta_deg": round(float(np.median(deltas)), 3) if deltas else None,
        "max_pose_pair_offset_ms": round(max(pair_offsets), 2) if pair_offsets else None,
        "stale_client_samples": sum(a > 300 for a in age),
        "max_client_age_ms": max(age) if age else None,
        "green_outside_server_pose": outside,
        "green_without_server_face": no_face,
        "rendered_dot_samples": len(dot_errors),
        "max_dot_plan_error": max(dot_errors) if dot_errors else None,
    }


def open_retained_payload(settings: Settings, privacy: SessionPrivacy, row: SessionRow) -> dict:
    """Honor the API's retention boundary before decrypting any diagnostic payload."""
    ensure_session_retained(settings, row)
    return privacy.open_json(row.session_id, "session", row.payload)


def compare_private_video(
    settings: Settings,
    privacy: SessionPrivacy,
    payload: dict,
    trace: dict,
    reader_factory=FaceObservationReader,
) -> dict:
    """Keep the temporary lease bounded even if reader construction/loading fails."""
    dynamic = payload["challenge"]["dynamic"]
    paths, lease = privacy.prepare(payload["session_id"], {"video": Path(payload["video"])})
    try:
        return _compare_prepared_video(settings, paths["video"], dynamic, trace, reader_factory)
    finally:
        if lease:
            lease.release()


def _compare_prepared_video(
    settings: Settings,
    video: Path,
    dynamic: dict,
    trace: dict,
    reader_factory=FaceObservationReader,
) -> dict:
    """Run native work on detached media; no database or privacy service is needed."""
    reader = None
    try:
        reader = reader_factory()
        reader.preload(models_dir=Path(settings.models_dir))
        rows = reader.extract(
            video,
            start_ms=dynamic["gaze_points"][0]["at_ms"],
            end_ms=dynamic["head_start_at_ms"] + dynamic["head_duration_ms"],
        )
        return compare_observations(trace, rows, dynamic)
    finally:
        if reader is not None:
            reader.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--server-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not 0 < args.trace.stat().st_size <= 1_048_576:
        raise ValueError("Diagnostic input too large")
    trace = json.loads(args.trace.read_text(encoding="utf-8-sig"))
    if (
        trace.get("schema_version") != 1
        or not isinstance(trace.get("events"), list)
        or len(trace["events"]) > 1024
    ):
        raise ValueError("Invalid diagnostic schema")
    previous = Path.cwd()
    database = None
    lease = None
    try:
        os.chdir(args.server_dir)
        settings = Settings()
        database = Database(settings.database_url)
        with database.sessions() as db:
            privacy = SessionPrivacy(settings, db)
            candidates = []
            for row in db.scalars(
                select(SessionRow).order_by(SessionRow.created_at.desc()).limit(50)
            ):
                try:
                    payload = open_retained_payload(settings, privacy, row)
                except Exception:
                    continue  # Expired/erased sessions cannot be reconstructed.
                candidates.append(payload)
            payload = match_attempt(trace, candidates)
            paths, lease = privacy.prepare(payload["session_id"], {"video": Path(payload["video"])})
        report = _compare_prepared_video(
            settings, paths["video"], payload["challenge"]["dynamic"], trace
        )
    finally:
        try:
            if lease:
                lease.release()
        finally:
            try:
                if database is not None:
                    database.dispose()
            finally:
                os.chdir(previous)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    provenance = {
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        ),
        "gaze_version": GAZE_VERSION,
        "head_version": HEAD_VERSION,
        "trace_sha256": hashlib.sha256(args.trace.read_bytes()).hexdigest(),
    }
    args.output.write_text(
        json.dumps(
            {"schema_version": 1, "matched_attempt": True, **provenance, **report}, indent=2
        ),
        encoding="utf-8",
    )
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
