"""PII-redacted diagnostic and artifact-readiness CLI for Android presence sessions."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for _rel in ("services/api/src", "ml/src"):
    _candidate = str(REPO_ROOT / _rel)
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

import numpy as np  # noqa: E402
from sqlalchemy import select  # noqa: E402

from vericlue_api.core.config import Settings  # noqa: E402
from vericlue_api.db.database import Database  # noqa: E402
from vericlue_api.db.models import SessionRow  # noqa: E402
from vericlue_api.services.session_privacy import SessionPrivacy  # noqa: E402
from vericlue_ml.common.calibration import (  # noqa: E402
    CalibrationError,
    CalibrationStore,
    Calibrator,
)
from vericlue_ml.face.match import MatchThreshold  # noqa: E402
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION  # noqa: E402
from vericlue_ml.presence.gaze import GAZE_VERSION  # noqa: E402
from vericlue_ml.presence.head_turn import (  # noqa: E402
    BASELINE_HOLD_MS,
    BASELINE_MS,
    HEAD_VERSION,
    MAX_GAP_MS,
    direction,
)
from vericlue_ml.presence.landmarks import FaceObservationReader  # noqa: E402

PAD_VIDEO_V2_VERSION = (
    "fs-vfm-vit-l-fas@59f7b50a+scrfd@bfcc7d48+scrfd128-align224-rgb-v1"
    "+headturn-3views-max-v1+session-video-v2"
)
DEEPFAKE_VIDEO_V2_VERSION = (
    "gend-clip-l14@891ce014+clip@32bd6428+scrfd-10g@bfcc7d48"
    "+agg-maxmeantop25-v1+headturn-3views-v1+session-video-v2"
)
MATCH_VIDEO_V2_VERSION = VIDEO_MATCH_VERSION + "+head12s-v2"

_ALLOWED_DIAGNOSTIC_KEYS = frozenset(
    {
        "valid_samples",
        "coverage",
        "head_deviation_deg",
        "iris_span_x",
        "iris_span_y",
        "correlation_x",
        "correlation_y",
        "lag_ms",
    }
)


def _git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, stderr=subprocess.DEVNULL, text=True
        ).strip()
        return out or "unknown"
    except Exception:
        return "unknown"


def _check_calibrator(store: CalibrationStore, module: str, version: str) -> dict[str, str]:
    try:
        artifact = store.load(module, version)
    except CalibrationError:
        state = "unavailable"
    else:
        if isinstance(artifact, Calibrator) and not artifact.provisional:
            state = "ready"
        elif getattr(artifact, "provisional", False):
            state = "provisional_rejected"
        else:
            state = "invalid"
    return {
        "module": module,
        "exact_model_version": version,
        "artifact_state": state,
    }


def _check_match_threshold(path_str: str | None, expected_version: str) -> str:
    if not path_str or not str(path_str).strip():
        return "unavailable"
    try:
        threshold = MatchThreshold.model_validate_json(Path(path_str).read_text(encoding="utf-8"))
    except Exception:
        return "unavailable"
    return "ready" if threshold.model_version == expected_version else "version_mismatch"


def check_artifact_readiness(
    settings: Settings, *, calibrators_dir: Path | None = None
) -> dict[str, Any]:
    store = CalibrationStore(root=calibrators_dir)
    calibrators = [
        _check_calibrator(store, "face_pad", PAD_VIDEO_V2_VERSION),
        _check_calibrator(store, "face_deepfake", DEEPFAKE_VIDEO_V2_VERSION),
    ]
    face_cal = _check_match_threshold(settings.identity_face_calibration, MATCH_VIDEO_V2_VERSION)
    consistency_cal = _check_match_threshold(
        settings.identity_consistency_calibration,
        MATCH_VIDEO_V2_VERSION + "+view-consistency-v1",
    )
    all_calibrators_ready = all(item["artifact_state"] == "ready" for item in calibrators)
    return {
        "calibrators": calibrators,
        "identity_face_calibration": face_cal,
        "identity_consistency_calibration": consistency_cal,
        "account_enrollment": bool(settings.account_enrollment),
        "full_flow_ready": bool(
            all_calibrators_ready
            and face_cal == "ready"
            and (not settings.identity_consistency_required or consistency_cal == "ready")
        ),
    }


def _redact_module(raw_mod: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    diagnostics: dict[str, float] = {}
    quality = raw_mod.get("quality")
    if isinstance(quality, dict):
        for k, v in quality.items():
            if (
                k in _ALLOWED_DIAGNOSTIC_KEYS
                and isinstance(v, (int, float))
                and not isinstance(v, bool)
            ):
                diagnostics[k] = float(v)
    for ev in raw_mod.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        name = ev.get("name")
        val = ev.get("value")
        if name in {"gaze_reason", "head_reason"} and isinstance(val, str):
            reasons.append(val)
        elif name == "gaze_diagnostics" and isinstance(val, dict):
            for k, v in val.items():
                if (
                    k in _ALLOWED_DIAGNOSTIC_KEYS
                    and isinstance(v, (int, float))
                    and not isinstance(v, bool)
                ):
                    diagnostics[k] = float(v)
    entry: dict[str, Any] = {
        "module": str(raw_mod.get("module", "")),
        "model_version": str(raw_mod.get("model_version", "")),
        "status": str(raw_mod.get("status", "")),
        "gate": str(raw_mod.get("gate", "")),
        "reason": reasons,
    }
    if raw_mod.get("error_code") is not None:
        entry["error_code"] = str(raw_mod["error_code"])
    if diagnostics:
        entry["diagnostics"] = diagnostics
    return entry


def _summarize_head_video(
    rows: list[Any], *, head_start_ms: float, head_end_ms: float
) -> dict[str, Any]:
    window = [r for r in rows if head_start_ms - BASELINE_MS <= r.at_ms <= head_end_ms]
    valid = [
        r
        for r in window
        if r.face_count == 1
        and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v)
            for v in (r.yaw_deg, r.pitch_deg, r.roll_deg)
        )
    ]
    no_face = sum(1 for r in window if r.face_count == 0)
    multi_face = sum(1 for r in window if r.face_count > 1)
    gaps_over_limit: list[dict[str, float]] = []
    max_gap_ms = 0.0
    if len(valid) >= 2:
        times = np.asarray([r.at_ms for r in valid], dtype=float)
        diffs = np.diff(times)
        max_gap_ms = float(diffs.max())
        for idx, gap in enumerate(diffs):
            if gap > MAX_GAP_MS:
                gaps_over_limit.append(
                    {
                        "start_rel_ms": round(float(valid[idx].at_ms - head_start_ms), 1),
                        "end_rel_ms": round(float(valid[idx + 1].at_ms - head_start_ms), 1),
                        "gap_ms": round(float(gap), 1),
                        "yaw_before_deg": round(float(valid[idx].yaw_deg), 2),
                        "yaw_after_deg": round(float(valid[idx + 1].yaw_deg), 2),
                    }
                )
    baseline = [r for r in valid if r.at_ms < head_start_ms]
    baseline_ok = bool(
        baseline
        and baseline[-1].at_ms - baseline[0].at_ms >= BASELINE_HOLD_MS
        and all(direction(r) == "center" for r in baseline)
    )
    return {
        "state": "ok",
        "total_samples": len(window),
        "valid_pose_samples": len(valid),
        "no_face_samples": no_face,
        "multi_face_samples": multi_face,
        "max_gap_ms": round(max_gap_ms, 1),
        "gaps_over_300ms": gaps_over_limit,
        "min_yaw_deg": round(min((float(r.yaw_deg) for r in valid), default=0.0), 2),
        "max_yaw_deg": round(max((float(r.yaw_deg) for r in valid), default=0.0), 2),
        "max_abs_pitch_deg": round(max((abs(float(r.pitch_deg)) for r in valid), default=0.0), 2),
        "max_abs_roll_deg": round(max((abs(float(r.roll_deg)) for r in valid), default=0.0), 2),
        "baseline_samples": len(baseline),
        "baseline_center_ok": baseline_ok,
    }


def build_diagnostic_report(
    *,
    settings: Settings,
    session_ids: list[str] | None = None,
    latest: int = 4,
    calibrators_dir: Path | None = None,
    extract_video: bool = True,
    reader_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    db = Database(settings.database_url)
    sessions_out: list[dict[str, Any]] = []
    reader = None
    try:
        with db.sessions() as orm:
            privacy = SessionPrivacy(settings, orm)
            if session_ids:
                row_map = {
                    r.session_id: r
                    for r in orm.scalars(
                        select(SessionRow).where(SessionRow.session_id.in_(session_ids))
                    ).all()
                }
                rows = [row_map[sid] for sid in session_ids if sid in row_map]
            else:
                rows = list(
                    orm.scalars(
                        select(SessionRow).order_by(SessionRow.created_at.desc()).limit(latest)
                    ).all()
                )
            for idx, row in enumerate(rows):
                created_iso = row.created_at.isoformat() if row.created_at else None
                if row.media_deleted_at is not None:
                    sessions_out.append(
                        {
                            "session_index": idx,
                            "created_utc": created_iso,
                            "status": row.status,
                            "state": "unavailable",
                        }
                    )
                    continue
                try:
                    data = (
                        privacy.open_json(row.session_id, "session", row.payload)
                        if privacy.enabled
                        else dict(row.payload)
                    )
                except Exception:
                    sessions_out.append(
                        {
                            "session_index": idx,
                            "created_utc": created_iso,
                            "status": row.status,
                            "state": "unavailable",
                        }
                    )
                    continue

                challenge = data.get("challenge") or {}
                dynamic = challenge.get("dynamic") or {}
                results_dict = data.get("results") or {}
                modules = [
                    _redact_module(mod) for mod in results_dict.values() if isinstance(mod, dict)
                ]
                head_start = dynamic.get("head_start_at_ms")
                head_duration = dynamic.get("head_duration_ms")
                head_summary: dict[str, Any] = {"state": "skipped"}
                video_rel = data.get("video")
                if (
                    extract_video
                    and video_rel
                    and isinstance(head_start, int)
                    and isinstance(head_duration, int)
                ):
                    lease = None
                    try:
                        prepared, lease = privacy.prepare(
                            row.session_id, {"video": Path(video_rel)}
                        )
                        if reader is None:
                            if reader_factory is not None:
                                reader = reader_factory()
                            else:
                                reader = FaceObservationReader()
                                reader.preload(models_dir=Path(settings.models_dir))
                        obs = reader.extract(
                            Path(prepared["video"]),
                            start_ms=float(head_start - BASELINE_MS),
                            end_ms=float(head_start + head_duration),
                        )
                        head_summary = _summarize_head_video(
                            obs,
                            head_start_ms=float(head_start),
                            head_end_ms=float(head_start + head_duration),
                        )
                    except Exception as exc:
                        head_summary = {
                            "state": "reader_error" if lease is not None else "media_unavailable",
                            "error_type": type(exc).__name__,
                        }
                    finally:
                        if lease is not None:
                            lease.release()

                sessions_out.append(
                    {
                        "session_index": idx,
                        "created_utc": created_iso,
                        "status": row.status,
                        "state": "ok",
                        "protocol": dynamic.get("version"),
                        "head_start_at_ms": head_start,
                        "head_duration_ms": head_duration,
                        "head_turns": list(dynamic.get("head_turns") or []),
                        "modules": modules,
                        "head_observations": head_summary,
                    }
                )
    finally:
        db.dispose()

    return {
        "schema_version": 1,
        "source_commit": _git_commit(),
        "module_versions": {
            "gaze_tracking": GAZE_VERSION,
            "head_turn": HEAD_VERSION,
            "face_pad": PAD_VIDEO_V2_VERSION,
            "face_deepfake": DEEPFAKE_VIDEO_V2_VERSION,
            "face_match": MATCH_VIDEO_V2_VERSION,
        },
        "artifact_readiness": check_artifact_readiness(settings, calibrators_dir=calibrators_dir),
        "sessions": sessions_out,
    }


def main(argv: list[str] | None = None, *, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose presence sessions without PII.")
    parser.add_argument("--session-id", action="append", dest="session_ids")
    parser.add_argument("--latest", type=int, default=4)
    parser.add_argument("--server-dir", type=Path, default=None)
    parser.add_argument("--calibrators-dir", type=Path, default=None)
    parser.add_argument("--no-video-extract", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    prev_cwd = Path.cwd()
    try:
        if settings is None:
            if args.server_dir is not None:
                os.chdir(args.server_dir)
            settings = Settings()
        report = build_diagnostic_report(
            settings=settings,
            session_ids=args.session_ids,
            latest=args.latest,
            calibrators_dir=args.calibrators_dir,
            extract_video=not args.no_video_extract,
        )
    finally:
        os.chdir(prev_cwd)

    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
