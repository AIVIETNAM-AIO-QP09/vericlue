"""Chẩn đoán offline PAD/GenD trên calib_fit bằng calibrator đã khóa.

Artifact chỉ tự mô tả nguồn, không có chữ ký hay chứng thực bên ngoài. Producer
chưa có strata/source crosswalk, runtime identity hoặc các gate chất lượng,
presence/OOD; điểm max không mô phỏng toàn bộ router và không đủ điều kiện LTT.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path

from pydantic import Field, StrictInt

from vericlue_ml.common.calibration import Calibrator
from vericlue_ml.eval import session_calibration as session
from vericlue_ml.eval.report import git_revision

ROOT = Path(__file__).resolve().parents[4]
MAX_BYTES = 32 * 1024 * 1024
MODULES = ("face_pad", "face_deepfake")


class _FitMetadata(session.Record):
    """Exact dataset JSON emitted by session_calibration.fit_report."""

    dataset: str = Field(pattern=session.OPAQUE)
    report_sha256: str = Field(pattern=session.HASH)
    manifest_sha256: str = Field(pattern=session.HASH)
    model_manifest_sha256: str = Field(pattern=session.HASH)
    measurement_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    selected: StrictInt = Field(ge=0)
    usable: StrictInt = Field(ge=0)
    excluded_by_label: dict[str, StrictInt]
    groups: StrictInt = Field(ge=0)


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _snapshot(path: Path) -> tuple[dict, str]:
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Research JSON exceeds 32 MiB")
    body = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_keys)
    if not isinstance(body, dict):
        raise ValueError("Research JSON must be an object")
    return body, hashlib.sha256(raw).hexdigest()


def _output(path: Path, protected: set[Path]) -> Path:
    target = path.resolve()
    forbidden = [
        ROOT / name
        for name in ("ml/configs", "configs", "models", "data", "external", "packages/contracts")
    ]
    forbidden.extend(
        Path(os.environ[key]).resolve()
        for key in ("MODELS_DIR", "DATA_DIR", "CALIBRATORS_DIR")
        if os.environ.get(key)
    )
    if target.exists() or target in protected:
        raise ValueError("Output must be new and must not replace an input")
    if any(target.is_relative_to(folder.resolve()) for folder in forbidden):
        raise ValueError("Output must be outside config/model/data storage")
    return target


def _calibrator(raw: dict, report: session.SessionReport, digest: str) -> tuple[Calibrator, dict]:
    if (
        raw.get("provisional") is not False
        or type(raw.get("n_pos")) is not int
        or type(raw.get("n_neg")) is not int
    ):
        raise ValueError("A nonprovisional fitted calibrator with integer counts is required")
    fitted = Calibrator.model_validate_json(json.dumps(raw), strict=True)
    if not re.fullmatch(r"[0-9a-f]{40}", fitted.commit):
        raise ValueError("Calibrator requires a clean fitting commit")
    metadata_raw = json.loads(fitted.dataset, object_pairs_hook=_unique_keys)
    metadata = _FitMetadata.model_validate(metadata_raw)
    selected = [row for row in report.rows if row.split == "calib_fit"]
    usable = [row for row in selected if row.status == "ok"]
    expected = {
        "dataset": report.dataset,
        "report_sha256": digest,
        "manifest_sha256": report.manifest_sha256,
        "model_manifest_sha256": report.model_manifest_sha256,
        "measurement_commit": report.source_commit,
        "selected": len(selected),
        "usable": len(usable),
        "excluded_by_label": {
            str(label): sum(row.label == label and row.status != "ok" for row in selected)
            for label in (0, 1)
        },
        "groups": len({row.subject_id for row in usable}),
    }
    if (
        fitted.module != report.module
        or fitted.model_version != report.model_version
        or fitted.n_pos != sum(row.label == 1 for row in usable)
        or fitted.n_neg != sum(row.label == 0 for row in usable)
        or metadata.model_dump() != expected
    ):
        raise ValueError("Calibrator differs from linked session report provenance/counts")
    return fitted, metadata.model_dump()


def _probabilities(report: session.SessionReport, fitted: Calibrator) -> dict[str, float]:
    usable = [row for row in report.rows if row.split == "calib_fit" and row.status == "ok"]
    if not usable:
        return {}
    values = fitted.predict([row.score for row in usable])
    probabilities = {}
    for row, value in zip(usable, values, strict=True):
        probability = float(value)
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("Calibrator produced an invalid probability")
        probabilities[row.sample_id] = probability
    return probabilities


def score_report(
    pad_report: Path,
    gend_report: Path,
    pad_calibrator: Path,
    gend_calibrator: Path,
    output: Path,
) -> dict:
    """Score all calib_fit rows with frozen PAD/GenD calibration; never select or fit."""
    commit = git_revision()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("A clean execution commit is required before scoring")
    paths = [
        Path(path).resolve() for path in (pad_report, gend_report, pad_calibrator, gend_calibrator)
    ]
    target = _output(Path(output), set(paths))
    snapshots = {path: _snapshot(path) for path in paths}
    reports, calibrators, metadata = {}, {}, {}
    raw_rows = {}
    for module, report_path, calibrator_path in zip(MODULES, paths[:2], paths[2:], strict=True):
        raw, digest = snapshots[report_path]
        report = session.SessionReport.model_validate(raw)
        if report.module != module:
            raise ValueError("Report module differs from PAD/GenD argument")
        # Check every row, including failures and unused splits, before filtering.
        session._partition(report.rows)
        reports[module] = report
        raw_rows[module] = {row["sample_id"]: row for row in raw["rows"]}
        calibrators[module], metadata[module] = _calibrator(
            snapshots[calibrator_path][0], report, digest
        )
    pad, gend = (reports[module] for module in MODULES)
    if pad.dataset != gend.dataset or pad.manifest_sha256 != gend.manifest_sha256:
        raise ValueError("PAD/GenD dataset or manifest differs")
    alignment = ("sample_id", "subject_id", "split", "label", "video_sha256", "challenge_sha256")
    identities = [
        {row.sample_id: tuple(getattr(row, name) for name in alignment) for row in report.rows}
        for report in (pad, gend)
    ]
    if identities[0] != identities[1]:
        raise ValueError("Every PAD/GenD row must align one-to-one, including unused/failed rows")
    probabilities = {
        module: _probabilities(reports[module], calibrators[module]) for module in MODULES
    }
    rows = []
    for measurement in pad.rows:
        if measurement.split != "calib_fit":
            continue
        key = measurement.sample_id
        values = {module: probabilities[module].get(key) for module in MODULES}
        rows.append(
            {
                "measurements": {module: raw_rows[module][key] for module in MODULES},
                "module_probabilities": values,
                "candidate_probability": max(values.values())
                if all(value is not None for value in values.values())
                else None,
            }
        )
    sources = {}
    for module, report_path, calibrator_path in zip(MODULES, paths[:2], paths[2:], strict=True):
        sources[module] = {
            "report_sha256": snapshots[report_path][1],
            "calibrator_sha256": snapshots[calibrator_path][1],
            "model_version": reports[module].model_version,
            "measurement_commit": reports[module].source_commit,
            "fitting_commit": calibrators[module].commit,
            "model_manifest_sha256": reports[module].model_manifest_sha256,
            "fit_metadata": metadata[module],
        }
    payload = {
        "schema_version": 1,
        "diagnostic_only": True,
        "deployed": False,
        "runtime_eligible": False,
        "ltt_ready": False,
        "source_crosswalk_verified": False,
        "prior_gates_measured": False,
        "runtime_binding_verified": False,
        "external_attestation_verified": False,
        "execution_commit": commit,
        "dataset": pad.dataset,
        "manifest_sha256": pad.manifest_sha256,
        "sources": sources,
        "fusion_policy": "max",
        "split": "calib_fit",
        "sample_count": len(rows),
        "rows": rows,
    }
    serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    for path, (_, digest) in snapshots.items():
        if _snapshot(path)[1] != digest:
            raise ValueError("Input changed during candidate processing")
    target = _output(Path(output), set(paths))
    with target.open("x", encoding="utf-8") as stream:
        stream.write(serialized)
    return payload


def main(argv: list[str] | None = None) -> int:
    """Apply frozen calibration to calib_fit only; no selection/evaluation command."""
    parser = argparse.ArgumentParser(
        description="Offline PAD/GenD calib_fit diagnostics; never enables deployment or LTT."
    )
    for flag in ("pad-report", "gend-report", "pad-calibrator", "gend-calibrator", "output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = score_report(
            args.pad_report,
            args.gend_report,
            args.pad_calibrator,
            args.gend_calibrator,
            args.output,
        )
        print(json.dumps({"sample_count": result["sample_count"], "split": result["split"]}))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
