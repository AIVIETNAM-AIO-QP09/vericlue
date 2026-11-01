"""Offline NES2Net max-margin protocol; no decision, threshold or automatic deployment.

The four-second grid/tail is VOICE-13's recipe. Max margin is a separately
versioned candidate requiring its own subject/source-disjoint evaluation.
Local manifests/reports are research inputs, not signed dataset attestations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path, PureWindowsPath
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from sklearn.model_selection import GroupKFold

from vericlue_ml.common.calibration import MIN_ISOTONIC_CLASS, CalibFit, fit
from vericlue_ml.common.result import ModuleResult
from vericlue_ml.eval.report import git_revision
from vericlue_ml.voice.nes2net import Nes2NetDetector
from vericlue_ml.voice.nes2net_parity import (
    implementation_identity,
    runtime_identity,
    validate_parity_claim,
)
from vericlue_ml.voice.nes2net_timeline import VERSION as TIMELINE_VERSION
from vericlue_ml.voice.nes2net_timeline import Nes2NetTimelineDetector, validate_timeline

VERSION = TIMELINE_VERSION.replace("timeline4s-tail-v1", "timeline4s-tail-maxmargin-v1")
PROTOCOL = "all_windows_required_max_spoof_minus_bonafide_margin_v1"
SPLITS = ("calib_fit", "calib_ltt", "test")
HASH = r"^[0-9a-f]{64}$"
ID = r"^[A-Za-z0-9._:/-]{1,180}$"


def aggregate_timeline(timeline: ModuleResult, count: int) -> ModuleResult:
    """Retain every window; only a fully measured take has a whole-utterance score."""
    validate_timeline(timeline, count)
    full = timeline.quality.get("all_source_samples_measured") is True
    rows = timeline.evidence[0].value if timeline.evidence else []
    complete = full and all(row["result"]["status"] == "degraded" for row in rows)
    score = max(row["result"]["score"] for row in rows) if complete else None
    quality = {
        **timeline.quality,
        "aggregation": PROTOCOL,
        "aggregation_complete": complete,
        "diagnostic_only": True,
        "calibrated": False,
    }
    # A processing/quality failure must not retain a whole-recording parity claim.
    if not complete:
        quality["frontend_parity_verified"] = False
        quality.pop("parity_report_sha256", None)
    return timeline.model_copy(
        update={"model_version": VERSION, "score": score, "quality": quality}
    )


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Sample(Record):
    sample_id: str = Field(pattern=ID)
    subject_ids: list[str] = Field(min_length=1)
    source_group: str = Field(pattern=ID)
    split: Literal["calib_fit", "calib_ltt", "test"]
    label: StrictInt = Field(ge=0, le=1)
    attack_type: str = Field(min_length=1)
    audio: str = Field(min_length=1)
    audio_sha256: str = Field(pattern=HASH)
    source_dataset: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    rights_reference: str = Field(min_length=1)
    usage: Literal["calibration_evaluation", "test_only"]

    @model_validator(mode="after")
    def declared_provenance(self):
        if (
            len(set(self.subject_ids)) != len(self.subject_ids)
            or any(re.fullmatch(ID, item) is None for item in self.subject_ids)
            or any(
                not value.strip()
                for value in (
                    self.rights_reference,
                    self.source_revision,
                    self.source_dataset,
                    self.attack_type,
                )
            )
        ):
            raise ValueError("Explicit subject/source/rights provenance required")
        if (
            self.usage == "test_only" or "vivos" in self.source_dataset.casefold()
        ) and self.split != "test":
            raise ValueError("Test-only/parity data cannot enter calibration")
        if (self.label == 0) != (self.attack_type == "bonafide"):
            raise ValueError("Label and attack type disagree")
        return self


class Manifest(Record):
    schema_version: Literal[1]
    dataset: str = Field(min_length=1)
    samples: list[Sample] = Field(min_length=1)

    @model_validator(mode="after")
    def no_vivos_calibration(self):
        if "vivos" in self.dataset.casefold() and any(s.split != "test" for s in self.samples):
            raise ValueError("VIVOS parity/test data cannot enter calibration")
        return self


class MeasurementReport(Record):
    schema_version: StrictInt = Field(ge=1, le=1)
    protocol: Literal[PROTOCOL]
    model_version: Literal[VERSION]
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    manifest_sha256: str = Field(pattern=HASH)
    manifest: Manifest
    dataset: str = Field(min_length=1)
    checkpoint_sha256: str = Field(pattern=HASH)
    parity_report_sha256: str = Field(pattern=HASH)
    numerical_binding: dict
    runtime: dict
    sample_count: StrictInt = Field(ge=1)
    audit: dict
    rows: list[dict] = Field(min_length=1)


def _read(path: Path) -> dict:
    return _snapshot(path)[0]


def _snapshot(path: Path) -> tuple[dict, str]:
    with path.open("rb") as stream:
        raw = stream.read(32 * 1024 * 1024 + 1)
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("Research report exceeds 32 MiB")
    return json.loads(raw.decode("utf-8-sig")), hashlib.sha256(raw).hexdigest()


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _audio(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or PureWindowsPath(name).drive or ".." in relative.parts:
        raise ValueError("Audio must be relative to the data root")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Missing audio or escaping data root")
    return path


def _partition(samples: list[Sample], checks: list[dict]) -> dict[str, str]:
    """Join all declared identities and original-source families for CV as well as splits."""
    parents, splits, seen_ids, seen_bytes, seen_pcm = {}, {}, set(), set(), set()

    def find(key):
        parents.setdefault(key, key)
        if parents[key] != key:
            parents[key] = find(parents[key])
        return parents[key]

    entities = {}
    for sample, check in zip(samples, checks, strict=True):
        if (
            sample.sample_id in seen_ids
            or sample.audio_sha256 in seen_bytes
            or check["pcm_sha256"] in seen_pcm
        ):
            raise ValueError("Duplicate sample ID, file or decoded PCM")
        seen_ids.add(sample.sample_id)
        seen_bytes.add(sample.audio_sha256)
        seen_pcm.add(check["pcm_sha256"])
        keys = ["subject:" + key for key in sample.subject_ids] + ["source:" + sample.source_group]
        entities[sample.sample_id] = keys[0]
        for key in keys:
            if splits.setdefault(key, sample.split) != sample.split:
                raise ValueError("Subject or source family appears in multiple splits")
            left, right = find(keys[0]), find(key)
            parents[max(left, right)] = min(left, right)
    return {sample_id: find(key) for sample_id, key in entities.items()}


def load_manifest(path: Path, data_root: Path) -> tuple[Manifest, list[dict]]:
    """Check labels/provenance, file integrity, native PCM and global split separation."""
    manifest = Manifest.model_validate(_read(path))
    checks = []
    for sample in manifest.samples:
        audio = _audio(data_root, sample.audio)
        if _sha(audio) != sample.audio_sha256:
            raise ValueError("Audio differs from the pinned manifest")
        pcm = Nes2NetDetector._read_file(audio)
        try:
            checks.append(
                {
                    "pcm_sha256": hashlib.sha256(pcm.astype("<f4").tobytes()).hexdigest(),
                    "input_samples": len(pcm),
                }
            )
        finally:
            pcm.fill(0)
    groups = _partition(manifest.samples, checks)
    for sample, check in zip(manifest.samples, checks, strict=True):
        check["group_id"] = groups[sample.sample_id]
    return manifest, checks


def _audit_samples(
    samples: list[Sample], groups: dict[str, str], expected_attack_types: Sequence[str]
) -> dict:
    if isinstance(expected_attack_types, str) or any(
        not isinstance(kind, str) or not kind.strip() or kind == "bonafide"
        for kind in expected_attack_types
    ):
        raise ValueError("Expected attack types must be explicit non-empty attack names")
    expected_types = list(dict.fromkeys(expected_attack_types))
    counts = {split: {"bonafide": 0, "attack": 0} for split in SPLITS}
    attacks: dict[str, Counter] = {split: Counter() for split in SPLITS}
    split_groups: dict[str, set[str]] = {split: set() for split in SPLITS}
    for sample in samples:
        counts[sample.split]["attack" if sample.label else "bonafide"] += 1
        split_groups[sample.split].add(groups[sample.sample_id])
        if sample.label:
            attacks[sample.split][sample.attack_type] += 1
    warnings = [
        f"{split}: missing {label}"
        for split in SPLITS
        for label, n in counts[split].items()
        if n == 0
    ]
    for label, n in counts["calib_fit"].items():
        if n < MIN_ISOTONIC_CLASS:
            warnings.append(
                f"calib_fit: {label} has {n}/{MIN_ISOTONIC_CLASS} samples for isotonic eligibility"
            )
    missing_types = {
        split: [kind for kind in expected_types if not attacks[split][kind]] for split in SPLITS
    }
    warnings.extend(
        f"{split}: missing expected attack type {kind}"
        for split, missing in missing_types.items()
        for kind in missing
    )
    fit_samples = [sample for sample in samples if sample.split == "calib_fit"]
    group_count = len(split_groups["calib_fit"])
    folds = min(5, group_count)
    both_classes = {sample.label for sample in fit_samples} == {0, 1}
    train_both = False
    reasons = [f"missing_{label}_class" for label, n in counts["calib_fit"].items() if not n]
    if folds < 2:
        reasons.append("fewer_than_two_connected_groups")
    elif both_classes:
        splits = GroupKFold(n_splits=folds).split(
            [0] * len(fit_samples), groups=[groups[s.sample_id] for s in fit_samples]
        )
        train_both = all({fit_samples[i].label for i in train} == {0, 1} for train, _ in splits)
        if not train_both:
            reasons.append("training_fold_missing_class")
    return {
        "sample_count": len(samples),
        "group_count": len({groups[s.sample_id] for s in samples}),
        "split_counts": counts,
        "split_group_counts": {split: len(values) for split, values in split_groups.items()},
        "split_attack_type_counts": {split: dict(values) for split, values in attacks.items()},
        "expected_attack_types": expected_types,
        "missing_attack_types": missing_types,
        "cv": {
            "n_splits": folds,
            "groups": group_count,
            "both_classes": both_classes,
            "train_folds_have_both_classes": train_both,
            "feasible": both_classes and folds >= 2 and train_both,
            "reasons": reasons,
        },
        "isotonic_sample_eligible": min(counts["calib_fit"].values()) >= MIN_ISOTONIC_CLASS,
        "structural_only": True,
        "calibration_ready": False,
        "calibration_fitted": False,
        "warnings": warnings,
    }


def audit(
    manifest: Manifest, checks: list[dict], *, expected_attack_types: Sequence[str] = ()
) -> dict:
    """Describe declared class/group coverage, without fitting or certifying readiness."""
    return _audit_samples(
        manifest.samples, _partition(manifest.samples, checks), expected_attack_types
    )


def _write(
    output: Path, payload: dict, *, protected: list[Path], models_dir: Path | None = None
) -> None:
    target = output.resolve()
    if (
        target.exists()
        or target in {p.resolve() for p in protected}
        or (models_dir is not None and target.is_relative_to(models_dir.resolve()))
    ):
        raise ValueError("Output must be new and outside input/model storage")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def collect(
    manifest: Path, data_root: Path, models_dir: Path, output: Path, *, detector=None
) -> dict:
    """Run the fixed protocol on every declared sample; preserve partial and failed takes."""
    source_hash = _sha(manifest)
    info, checks = load_manifest(manifest, data_root)
    commit = git_revision()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("Commit implementation before collecting real measurements")
    runtime = detector if detector is not None else Nes2NetTimelineDetector(models_dir)
    runtime.preload()
    digest = runtime.backend.parity_sha256
    if not isinstance(digest, str) or re.fullmatch(HASH, digest) is None:
        raise ValueError("Runtime-bound numerical parity required before collection")
    rows = []
    for sample, check in zip(info.samples, checks, strict=True):
        audio = _audio(data_root, sample.audio)
        pcm = Nes2NetDetector._read_file(audio)
        try:
            if _sha(audio) != sample.audio_sha256:
                raise ValueError("Audio changed before measurement")
            timeline = runtime.predict_samples(pcm)
            if _sha(audio) != sample.audio_sha256:
                timeline = ModuleResult(
                    module="voice_spoof",
                    model_version=TIMELINE_VERSION,
                    status="error",
                    gate="unclear",
                    error_code="E_INTEGRITY",
                    latency_ms=timeline.latency_ms,
                )
            aggregate = aggregate_timeline(timeline, len(pcm))
            rows.append(
                {
                    "sample": sample.model_dump(),
                    **check,
                    "timeline": timeline.to_contract(),
                    "aggregate": aggregate.to_contract(),
                }
            )
        finally:
            pcm.fill(0)
    if _sha(manifest) != source_hash:
        raise ValueError("Manifest changed during measurement")
    payload = {
        "schema_version": 1,
        "protocol": PROTOCOL,
        "model_version": VERSION,
        "source_commit": commit,
        "manifest_sha256": source_hash,
        "manifest": info.model_dump(),
        "dataset": info.dataset,
        "checkpoint_sha256": runtime.backend.config["sha256"],
        "parity_report_sha256": digest,
        "numerical_binding": implementation_identity(runtime.backend.config),
        "runtime": runtime_identity(),
        "sample_count": len(rows),
        "audit": audit(info, checks),
        "rows": rows,
    }
    _write(
        output,
        payload,
        protected=[manifest] + [_audio(data_root, s.audio) for s in info.samples],
        models_dir=models_dir,
    )
    return payload


def _validated_measurement(
    report: Path,
) -> tuple[MeasurementReport, str, list[tuple[Sample, dict, ModuleResult]]]:
    body, checksum = _snapshot(report)
    header = MeasurementReport.model_validate(body)
    config = yaml.safe_load(
        (Path(__file__).resolve().parents[4] / "ml/configs/nes2net.yaml").read_text("utf-8")
    )
    if (
        header.sample_count != len(header.rows)
        or header.dataset != header.manifest.dataset
        or header.checkpoint_sha256 != config["sha256"]
        or header.numerical_binding != implementation_identity(config)
    ):
        raise ValueError("Wrong measurement provenance/count")
    rows = body["rows"]
    samples = [Sample.model_validate(row["sample"]) for row in rows]
    if samples != header.manifest.samples:
        raise ValueError("Labels or splits differ from the source manifest")
    if any(
        type(row["input_samples"]) is not int
        or not isinstance(row["pcm_sha256"], str)
        or re.fullmatch(HASH, row["pcm_sha256"]) is None
        for row in rows
    ):
        raise ValueError("Invalid PCM provenance")
    groups = _partition(samples, rows)
    measured = []
    for sample, row in zip(samples, rows, strict=True):
        timeline = ModuleResult.model_validate(row["timeline"])
        expected = aggregate_timeline(timeline, row["input_samples"])
        actual = ModuleResult.model_validate(row["aggregate"])
        if actual != expected or row["group_id"] != groups[sample.sample_id]:
            raise ValueError("Changed measurement or subject/source group")
        validate_parity_claim(actual)
        if (
            actual.score is not None
            and actual.quality.get("parity_report_sha256") != body["parity_report_sha256"]
        ):
            raise ValueError("Mixed or missing parity binding")
        measured.append((sample, row, actual))
    return header, checksum, measured


def readiness_report(
    report: Path, output: Path, *, expected_attack_types: Sequence[str] = ()
) -> dict:
    """Audit validated measurements and exclusions; never fit or upgrade module results."""
    header, checksum, measured = _validated_measurement(report)
    audit_commit = git_revision()
    if re.fullmatch(r"[0-9a-f]{40}", audit_commit) is None:
        raise ValueError("Commit audit implementation before auditing real measurements")
    groups = {sample.sample_id: row["group_id"] for sample, row, _ in measured}
    usable = []
    excluded = {
        split: {
            "count": 0,
            "by_status": {},
            "by_class": {"bonafide": 0, "attack": 0},
            "by_attack_type": {},
        }
        for split in SPLITS
    }
    for sample, _, result in measured:
        if result.score is not None:
            usable.append(sample)
            continue
        entry = excluded[sample.split]
        entry["count"] += 1
        entry["by_class"]["attack" if sample.label else "bonafide"] += 1
        for key, value in (
            ("by_status", str(result.status)),
            ("by_attack_type", sample.attack_type),
        ):
            entry[key][value] = entry[key].get(value, 0) + 1
    payload = {
        "schema_version": 1,
        "measurement_report_sha256": checksum,
        "measurement_commit": header.source_commit,
        "audit_commit": audit_commit,
        "dataset": header.dataset,
        "model_version": VERSION,
        "declared": _audit_samples(header.manifest.samples, groups, expected_attack_types),
        # Keep full-manifest components even if a removed row linked multiple people.
        "usable": _audit_samples(usable, groups, expected_attack_types),
        "excluded": excluded,
        "calibration_fitted": False,
        "calibration_ready": False,
        "deployed": False,
    }
    if _sha(report) != checksum:
        raise ValueError("Measurement report changed during readiness audit")
    _write(output, payload, protected=[report])
    return payload


def fit_report(report: Path, output: Path) -> dict:
    """Fit the existing Calibrator on complete calib_fit rows only; never install it."""
    header, checksum, measured = _validated_measurement(report)
    fit_commit = git_revision()
    if re.fullmatch(r"[0-9a-f]{40}", fit_commit) is None:
        raise ValueError("Commit fitting implementation before fitting real data")
    usable, excluded = [], Counter()
    for sample, row, result in measured:
        if sample.split == "calib_fit":
            if result.score is None:
                excluded[str(result.status)] += 1
            else:
                usable.append((sample, row, result))
    artifact = fit(
        CalibFit(
            scores=[r.score for _, _, r in usable],
            labels=[s.label for s, _, _ in usable],
            subject_ids=[r["group_id"] for _, r, _ in usable],
            dataset=header.dataset,
        ),
        module="voice_spoof",
        model_version=VERSION,
        commit=fit_commit,
    )
    if _sha(report) != checksum:
        raise ValueError("Measurement report changed during fitting")
    payload = {
        "artifact": artifact.model_dump(mode="json"),
        "measurement_report_sha256": checksum,
        "measurement_commit": header.source_commit,
        "fitting_commit": fit_commit,
        "protocol": PROTOCOL,
        "excluded_calib_fit": dict(excluded),
        "deployed": False,
    }
    _write(output, payload, protected=[report])
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "collect"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--manifest", required=True, type=Path)
        cmd.add_argument("--data-root", required=True, type=Path)
        cmd.add_argument("--output", required=True, type=Path)
        if name == "collect":
            cmd.add_argument("--models-dir", required=True, type=Path)
    fitting = sub.add_parser("fit")
    fitting.add_argument("--report", required=True, type=Path)
    fitting.add_argument("--output", required=True, type=Path)
    readiness = sub.add_parser("readiness")
    readiness.add_argument("--report", required=True, type=Path)
    readiness.add_argument("--output", required=True, type=Path)
    readiness.add_argument("--expected-attack-type", action="append", default=[])
    args = parser.parse_args(argv)
    if args.command == "prepare":
        manifest, checks = load_manifest(args.manifest, args.data_root)
        _write(
            args.output,
            audit(manifest, checks),
            protected=[args.manifest] + [_audio(args.data_root, s.audio) for s in manifest.samples],
        )
    elif args.command == "collect":
        collect(args.manifest, args.data_root, args.models_dir, args.output)
    elif args.command == "readiness":
        readiness_report(args.report, args.output, expected_attack_types=args.expected_attack_type)
    else:
        fit_report(args.report, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
