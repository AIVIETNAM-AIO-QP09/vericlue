"""Offline session-view measurement and group-aware fitting; never enables eKYC guards.

Saved server-response files are trusted local research fixtures, not proof of a
server signature. Predictions and fitted artifacts remain outside Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from vericlue_ml.common.calibration import CalibFit, CalibrationStore, fit
from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Module
from vericlue_ml.eval.diagnostic_output import check_diagnostic_output
from vericlue_ml.eval.report import git_revision
from vericlue_ml.face.fsvfm import FsvfmPadDetector
from vericlue_ml.face.gend import FaceDeepfakeDetector
from vericlue_ml.presence.head_protocol import head_protocol_version, session_model_version
from vericlue_ml.presence.head_turn import parse_head_plan
from vericlue_ml.presence.landmarks import FaceObservationReader, LandmarkError
from vericlue_ml.presence.session_views import session_views

ROOT = Path(__file__).resolve().parents[4]
SUFFIX = "+session-video-v1"
HASH = r"^[0-9a-f]{64}$"
OPAQUE = r"^[A-Za-z0-9._:-]{1,120}$"


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class SessionSample(Record):
    sample_id: str = Field(pattern=OPAQUE)
    subject_id: str = Field(pattern=OPAQUE)
    split: Literal["calib_fit", "calib_ltt", "test"]
    label: StrictInt = Field(ge=0, le=1)
    video: str
    server_response: str


class Manifest(Record):
    schema_version: StrictInt = Field(ge=1, le=1)
    dataset: str = Field(pattern=OPAQUE)
    samples: list[SessionSample] = Field(min_length=1)


class Measurement(Record):
    sample_id: str = Field(pattern=OPAQUE)
    subject_id: str = Field(pattern=OPAQUE)
    split: Literal["calib_fit", "calib_ltt", "test"]
    label: StrictInt = Field(ge=0, le=1)
    video_sha256: str = Field(pattern=HASH)
    challenge_sha256: str = Field(pattern=HASH)
    status: Literal["ok", "degraded", "error", "not_applicable"]
    error_code: str | None
    score: float | None = Field(ge=0, le=1)

    @model_validator(mode="after")
    def usable_score(self):
        if self.status == "ok":
            if self.score is None or self.error_code is not None:
                raise ValueError("An ok measurement needs a score and no error")
        elif self.score is not None:
            raise ValueError("Failed measurements cannot retain usable scores")
        if self.error_code is not None:
            ErrorCode(self.error_code)
        return self


class SessionReport(Record):
    schema_version: StrictInt = Field(ge=1, le=1)
    dataset: str = Field(pattern=OPAQUE)
    module: Literal["face_pad", "face_deepfake"]
    model_version: str
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    manifest_sha256: str = Field(pattern=HASH)
    model_manifest_sha256: str = Field(pattern=HASH)
    rows: list[Measurement] = Field(min_length=1)

    @field_validator("model_version")
    @classmethod
    def session_version(cls, value):
        if not value.endswith(
            (SUFFIX, "+session-video-v2", "+session-video-v3-adaptive")
        ) or value.startswith("mock@"):
            raise ValueError("Exact session-view model version required")
        return value


def _read(path: Path) -> dict:
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Research JSON exceeds 32 MiB")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _source(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or PureWindowsPath(name).drive or ".." in relative.parts:
        raise ValueError("Only relative paths within data root are permitted")
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError("Missing source or path escapes data root")
    return resolved


def _input(sample: SessionSample, root: Path) -> DetectorInput:
    body = _read(_source(root, sample.server_response))
    try:
        inp = DetectorInput(
            session_id=body["session_id"],
            video=_source(root, sample.video),
            metadata={
                "challenge_id": body["challenge"]["challenge_id"],
                "expected_challenge": body["challenge"],
            },
        )
        parse_head_plan(inp)
    except (KeyError, LandmarkError, TypeError) as exc:
        raise ValueError("Invalid server challenge context") from exc
    return inp


def _partition(rows) -> None:
    seen_ids, seen_videos, subjects = set(), set(), {}
    for row in rows:
        if row.sample_id in seen_ids or row.video_sha256 in seen_videos:
            raise ValueError("Duplicate sample ID or video content")
        seen_ids.add(row.sample_id)
        seen_videos.add(row.video_sha256)
        if subjects.setdefault(row.subject_id, row.split) != row.split:
            raise ValueError("Subject/source group appears in multiple splits")


def load_manifest(path: Path, data_root: Path) -> list[SessionSample]:
    manifest = Manifest.model_validate(_read(path))
    checks = []
    for sample in manifest.samples:
        video = _source(data_root, sample.video)
        if video.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("Session video exceeds decoder limit")
        _input(sample, data_root)
        checks.append(SimpleNamespace(**sample.model_dump(), video_sha256=_sha(video)))
    _partition(checks)
    return manifest.samples


def make_runtime(module: str, models_dir: Path, device: str):
    reader = FaceObservationReader()
    try:
        reader.preload(models_dir=models_dir)
        backend = FsvfmPadDetector() if module == "face_pad" else FaceDeepfakeDetector()
        backend.preload(models_dir=models_dir, device=device)
        return backend, reader
    except Exception:
        reader.close()
        raise


def _output(path: Path, protected: set[Path], models_dir: Path | None = None) -> None:
    target = path.resolve()
    if target in {p.resolve() for p in protected} or target.exists():
        raise ValueError("Output must be new and must not replace an input")
    if models_dir is not None and target.is_relative_to(models_dir.resolve()):
        raise ValueError("Reports cannot be written into model storage")


def collect(
    manifest: Path,
    data_root: Path,
    models_dir: Path,
    module: Module,
    output: Path,
    device: str = "cpu",
) -> dict:
    module = Module(module)
    if module not in {Module.FACE_PAD, Module.FACE_DEEPFAKE}:
        raise ValueError("Only session face PAD/GenD are supported")
    check_diagnostic_output(output, protected=[manifest], models_dir=models_dir)
    before = _sha(manifest)
    samples = load_manifest(manifest, data_root)
    challenges = {
        sample.sample_id: _source(data_root, sample.server_response) for sample in samples
    }
    challenge_hashes = {key: _sha(path) for key, path in challenges.items()}
    protocols = {head_protocol_version(_input(sample, data_root)) for sample in samples}
    if len(protocols) != 1:
        raise ValueError("A measurement report must contain exactly one capture protocol")
    protocol = protocols.pop()
    info = Manifest.model_validate(_read(manifest))
    protected = (
        {manifest}
        | {_source(data_root, s.video) for s in samples}
        | {_source(data_root, s.server_response) for s in samples}
    )
    check_diagnostic_output(output, protected=protected, models_dir=models_dir)
    commit = git_revision()
    if len(commit) != 40 or commit.endswith("-dirty"):
        raise ValueError("Commit implementation before collecting real measurements")
    model_manifest = Path(os.environ.get("ML_MODELS_MANIFEST") or ROOT / "models/manifest.yaml")
    model_manifest_hash = _sha(model_manifest)
    backend, reader = make_runtime(module.value, models_dir, device)
    rows = []
    try:
        if backend.name != module:
            raise ValueError("Backend module differs")
        version = session_model_version(backend.frames_version, protocol)
        for sample in samples:
            video, challenge = (
                _source(data_root, sample.video),
                _source(data_root, sample.server_response),
            )
            video_hash, challenge_hash = _sha(video), _sha(challenge)
            if challenge_hash != challenge_hashes[sample.sample_id]:
                raise ValueError("Server challenge changed after preflight")
            inp = _input(sample, data_root)
            if head_protocol_version(inp) != protocol or _sha(challenge) != challenge_hash:
                raise ValueError("Server challenge protocol changed after preflight")
            status, error, score = "error", "E_INTERNAL", None
            try:
                frames, selected_hash = session_views(inp, reader)
                result = backend.predict_frames(inp, frames)
                if result.module != module or result.model_version != backend.frames_version:
                    raise LandmarkError(ErrorCode.E_INTEGRITY)
                if (
                    selected_hash != video_hash
                    or _sha(video) != video_hash
                    or _sha(challenge) != challenge_hash
                ):
                    raise LandmarkError(ErrorCode.E_INTEGRITY)
                status, error = result.status, result.error_code
                if (
                    status == "ok"
                    and error is None
                    and result.score is not None
                    and math.isfinite(result.score)
                    and 0 <= result.score <= 1
                ):
                    score = result.score
                elif status == "ok":
                    status, error = "error", "E_INTERNAL"
            except LandmarkError as exc:
                status, error = exc.status, exc.code
            except Exception:
                status, error = "error", "E_INTERNAL"
            rows.append(
                Measurement(
                    sample_id=sample.sample_id,
                    subject_id=sample.subject_id,
                    split=sample.split,
                    label=sample.label,
                    video_sha256=video_hash,
                    challenge_sha256=challenge_hash,
                    status=str(status),
                    error_code=error,
                    score=score,
                )
            )
    finally:
        reader.close()
    if _sha(manifest) != before:
        raise ValueError("Manifest changed during collection")
    if any(_sha(path) != challenge_hashes[key] for key, path in challenges.items()):
        raise ValueError("Server challenge changed during collection")
    if _sha(model_manifest) != model_manifest_hash:
        raise ValueError("Model manifest changed during collection")
    _partition(rows)
    report = SessionReport(
        schema_version=1,
        dataset=info.dataset,
        module=module.value,
        model_version=version,
        source_commit=commit,
        manifest_sha256=before,
        model_manifest_sha256=model_manifest_hash,
        rows=rows,
    )
    target = check_diagnostic_output(
        output, protected=protected | {model_manifest}, models_dir=models_dir
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        stream.write(report.model_dump_json(indent=2) + "\n")
    return report.model_dump(mode="json")


def fit_report(report: Path, output_dir: Path, n_splits: int = 5) -> dict:
    before = _sha(report)
    parsed = SessionReport.model_validate(_read(report))
    _partition(parsed.rows)  # Check failures too, before selecting usable calib_fit rows.
    selected = [r for r in parsed.rows if r.split == "calib_fit"]
    usable = [r for r in selected if r.status == "ok"]
    excluded = {
        str(label): sum(r.label == label and r.status != "ok" for r in selected) for label in (0, 1)
    }
    store = CalibrationStore(output_dir)
    target = store.path(parsed.module, parsed.model_version)
    _output(target, {report}, ROOT / "models")
    metadata = {
        "dataset": parsed.dataset,
        "report_sha256": before,
        "manifest_sha256": parsed.manifest_sha256,
        "model_manifest_sha256": parsed.model_manifest_sha256,
        "measurement_commit": parsed.source_commit,
        "selected": len(selected),
        "usable": len(usable),
        "excluded_by_label": excluded,
        "groups": len({r.subject_id for r in usable}),
    }
    artifact = fit(
        CalibFit(
            scores=[r.score for r in usable],
            labels=[r.label for r in usable],
            subject_ids=[r.subject_id for r in usable],
            dataset=json.dumps(metadata, sort_keys=True),
        ),
        module=parsed.module,
        model_version=parsed.model_version,
        commit=git_revision(),
        n_splits=n_splits,
    )
    if len(artifact.commit) != 40 or _sha(report) != before:
        raise ValueError("Clean source commit and stable report required")
    output_dir.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        stream.write(artifact.model_dump_json(indent=2) + "\n")
    return {
        "artifact": str(target),
        "module": parsed.module,
        "model_version": parsed.model_version,
        "n_pos": artifact.n_pos,
        "n_neg": artifact.n_neg,
        "method": artifact.method,
        **metadata,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    measure = sub.add_parser("collect")
    for flag in ("manifest", "data-root", "models-dir", "output"):
        measure.add_argument("--" + flag, type=Path, required=True)
    measure.add_argument("--module", choices=("face_pad", "face_deepfake"), required=True)
    measure.add_argument("--device", choices=("cpu", "cuda", "auto"), default="cpu")
    fitter = sub.add_parser("fit")
    fitter.add_argument("--report", type=Path, required=True)
    fitter.add_argument("--output-dir", type=Path, required=True)
    fitter.add_argument("--n-splits", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        result = (
            collect(
                args.manifest,
                args.data_root,
                args.models_dir,
                args.module,
                args.output,
                args.device,
            )
            if args.command == "collect"
            else fit_report(args.report, args.output_dir, args.n_splits)
        )
        print(
            json.dumps(
                {"rows": len(result["rows"]), "model_version": result["model_version"]}
                if args.command == "collect"
                else result,
                ensure_ascii=False,
            )
        )
        return 0
    except (ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
