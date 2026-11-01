"""Prepare a pinned DNU bona-fide bundle on Colab/Kaggle; never fits a model.

Keep the publisher's original speaker partitions, choose by a fixed ID hash,
and audit unchanged native WAVs. Public release does not grant a new consent
scope for cloning or authenticating the participants. No clone is generated.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import urllib.request
import uuid
import wave
import zipfile
from collections import Counter, defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import quote

REPOSITORY = "TrangLe2108/DNU-ViSpeech"
REVISION = "33b2a469901cb71b243403254d3cfef25170526c"
BASE = f"https://huggingface.co/datasets/{REPOSITORY}/resolve/{REVISION}/"
VERSION = "dnu-bonafide-native16k-readonly-v1"
SPLITS = {"train": "calib_fit", "validation": "calib_ltt", "test": "test"}
MAX_FETCH_BYTES = 64 * 1024 * 1024


def _relative(name: str) -> str:
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or PureWindowsPath(name).drive
        or ".." in path.parts
        or "\\" in name
        or "\x00" in name
    ):
        raise ValueError("Unsafe relative data path")
    return path.as_posix()


def select_samples(metadata: dict[str, bytes], *, per_speaker: int, seed: int) -> list[dict]:
    """Choose before inference; reject malformed provenance or overlapping people."""
    if type(per_speaker) is not int or not 1 <= per_speaker <= 1000 or type(seed) is not int:
        raise ValueError("Explicit bounded sample count and integer seed required")
    if set(metadata) != set(SPLITS):
        raise ValueError("All publisher metadata splits are required")
    memberships, seen_ids, selected = {}, set(), []
    for original, target in SPLITS.items():
        groups = defaultdict(list)
        reader = csv.DictReader(io.StringIO(metadata[original].decode("utf-8-sig")))
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("Missing or duplicate metadata columns")
        for row in reader:
            try:
                name = _relative(row["file_name"])
                subject, sample = row["speaker_id"], row["audio_id"]
                digest = row["checksum_sha256"]
                if (
                    re.fullmatch(r"speaker[0-9]{3}", subject) is None
                    or re.fullmatch(r"[A-Za-z0-9._-]{1,120}", sample) is None
                    or not sample.startswith(subject + "_")
                    or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                    or row["split"]
                    not in ({"validation", "dev"} if original == "validation" else {original})
                ):
                    raise ValueError("Invalid publisher provenance")
                if sample in seen_ids or memberships.setdefault(subject, original) != original:
                    raise ValueError("Duplicate sample or subject across publisher splits")
                seen_ids.add(sample)
                eligible = (
                    row["review_status"] == "accepted"
                    and row["qc_status"] == "passed"
                    and int(row["sample_rate"]) == 16000
                    and int(row["num_channels"]) == 1
                    and 1 <= float(row["duration"]) <= 30
                )
                if eligible:
                    groups[subject].append((sample, name, digest))
            except (KeyError, TypeError) as exc:
                raise ValueError("Incomplete publisher metadata") from exc
        if not groups:
            raise ValueError("Publisher split has no eligible recordings")
        for subject, candidates in sorted(groups.items()):
            candidates.sort(
                key=lambda item: hashlib.sha256(f"{seed}:{item[0]}".encode()).hexdigest()
            )
            for sample, name, digest in candidates[:per_speaker]:
                selected.append(
                    {
                        "sample_id": "DNU:" + sample,
                        "subject_ids": ["DNU:" + subject],
                        "source_group": "DNU:" + sample,
                        "split": target,
                        "label": 0,
                        "attack_type": "bonafide",
                        "audio": f"DNU-ViSpeech/data/{original}/{name}",
                        "audio_sha256": digest,
                        "source_dataset": REPOSITORY,
                        "source_revision": REVISION,
                        "rights_reference": f"https://huggingface.co/datasets/{REPOSITORY}/blob/{REVISION}/LICENSE; research use, no cloning authorization asserted",
                        "usage": "test_only" if target == "test" else "calibration_evaluation",
                    }
                )
    return selected


def fetch_bytes(url: str) -> bytes:
    """Bound HTTPS transfers from the pinned publisher; no account token required."""
    if not url.startswith(BASE):
        raise ValueError("Only the pinned publisher revision is allowed")
    request = urllib.request.Request(url, headers={"User-Agent": "VeriClue-data-preparation/1"})
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read(MAX_FETCH_BYTES + 1)
    if len(raw) > MAX_FETCH_BYTES:
        raise ValueError("Publisher file exceeds download budget")
    return raw


def _write_once(path: Path, raw: bytes, *, root: Path) -> None:
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Evidence output escapes bundle storage")
    if path.exists():
        if not path.is_file() or path.read_bytes() != raw:
            raise ValueError("Existing evidence differs; never overwrite it")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)


def _wav_identity(raw: bytes) -> dict:
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Native WAV exceeds recording limit")
    try:
        with wave.open(io.BytesIO(raw), "rb") as reader:
            count = reader.getnframes()
            if (
                reader.getnchannels() != 1
                or reader.getsampwidth() != 2
                or reader.getframerate() != 16000
                or reader.getcomptype() != "NONE"
                or not 16000 <= count <= 480000
            ):
                raise ValueError("Expected unchanged mono16k PCM16,1..30seconds")
            pcm = reader.readframes(count)
            if len(pcm) != count * 2:
                raise ValueError("Truncated PCM")
    except (wave.Error, EOFError) as exc:
        raise ValueError("Invalid native WAV") from exc
    return {"input_samples": count, "pcm_s16le_sha256": hashlib.sha256(pcm).hexdigest()}


def prepare(
    root: Path,
    *,
    per_speaker: int,
    seed: int,
    commit: str,
    fetch: Callable[[str], bytes] = fetch_bytes,
    workers: int = 4,
) -> dict:
    """Prepare bona-fide data only; preserve failed/altered files and expose missing attacks."""
    if (
        re.fullmatch(r"[0-9a-f]{40}", commit) is None
        or type(workers) is not int
        or not 1 <= workers <= 8
    ):
        raise ValueError("Clean source commit and bounded workers required")
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    evidence = {}
    metadata = {}
    for name in (
        "LICENSE",
        "PUBLIC_RELEASE_APPROVAL.md",
        *(f"data/{split}/metadata.csv" for split in SPLITS),
    ):
        raw = fetch(BASE + quote(name, safe="/"))
        _write_once(root / "source" / name, raw, root=root)
        evidence[name] = hashlib.sha256(raw).hexdigest()
        if name.endswith("metadata.csv"):
            metadata[name.split("/")[1]] = raw
    if b"CC BY-NC 4.0" not in (root / "source/LICENSE").read_bytes():
        raise ValueError("Publisher license requires review")
    samples = select_samples(metadata, per_speaker=per_speaker, seed=seed)
    manifest = {"schema_version": 1, "dataset": "DNU-ViSpeech-bonafide-only-v1", "samples": samples}
    encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    _write_once(root / "manifest.json", encoded, root=root)

    def download(sample):
        base = {"sample_id": sample["sample_id"], "audio_sha256": sample["audio_sha256"]}
        try:
            target = (root / _relative(sample["audio"])).resolve()
            if not target.is_relative_to(root):
                raise ValueError("Audio output escapes bundle")
            reused = target.exists()
            raw = (
                target.read_bytes()
                if reused
                else fetch(BASE + quote(sample["audio"].removeprefix("DNU-ViSpeech/"), safe="/"))
            )
            if hashlib.sha256(raw).hexdigest() != sample["audio_sha256"]:
                raise ValueError("Changed publisher bytes")
            identity = _wav_identity(raw)
            if not reused:
                _write_once(target, raw, root=root)
            return {**base, **identity, "status": "verified", "reused": reused}
        except Exception as exc:
            return {**base, "status": "error", "error_type": type(exc).__name__}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(download, samples))
    errors = [row for row in rows if row["status"] == "error"]
    seen_pcm, seen_files = set(), set()
    for row in rows:
        if row["status"] != "verified":
            continue
        pcm, digest = row["pcm_s16le_sha256"], row["audio_sha256"]
        if pcm in seen_pcm or digest in seen_files:
            errors.append({"sample_id": row["sample_id"], "error_type": "DuplicatePCMOrFile"})
        seen_pcm.add(pcm)
        seen_files.add(digest)
    report = {
        "preparation_version": VERSION,
        "source_commit": commit,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "publisher": REPOSITORY,
        "publisher_revision": REVISION,
        "source_hashes": evidence,
        "manifest_sha256": hashlib.sha256(encoded).hexdigest(),
        "seed": seed,
        "per_speaker": per_speaker,
        "sample_count": len(samples),
        "split_counts": dict(Counter(s["split"] for s in samples)),
        "speaker_counts": {
            split: len({s["subject_ids"][0] for s in samples if s["split"] == split})
            for split in SPLITS.values()
        },
        "downloaded_audio_files": sum(r["status"] == "verified" and not r["reused"] for r in rows),
        "reused_audio_files": sum(r["status"] == "verified" and r["reused"] for r in rows),
        "pcm_duplicate_check": "failed_or_incomplete" if errors else "passed",
        "state": "incomplete" if errors else "bonafide_only",
        "calibration_ready": False,
        "missing": ["attack_data"],
        "clone_scope_confirmed": False,
        "errors": errors,
        "rows": rows,
    }
    reports = root / "runs"
    reports.mkdir(exist_ok=True)
    name = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8] + ".json"
    _write_once(
        reports / name,
        (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode(),
        root=root,
    )
    return report


def archive_bundle(root: Path, output: Path) -> str:
    """Export a new bundle without replacing existing archives or including itself."""
    root, output = root.resolve(), output.resolve()
    if output.is_relative_to(root):
        raise ValueError("Archive must be outside bundle storage")
    reports = list((root / "runs").glob("*.json"))
    latest = max(reports, key=lambda p: p.stat().st_mtime_ns) if reports else None
    report = json.loads(latest.read_text("utf-8")) if latest else {}
    if report.get("state") != "bonafide_only" or report.get("errors"):
        raise ValueError("Cannot archive incomplete preparation")
    manifest_raw = (root / "manifest.json").read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest() != report["manifest_sha256"]:
        raise ValueError("Manifest changed after preparation")
    manifest = json.loads(manifest_raw)
    expected = {
        "manifest.json": report["manifest_sha256"],
        latest.relative_to(root).as_posix(): hashlib.sha256(latest.read_bytes()).hexdigest(),
    }
    expected |= {
        "source/" + _relative(name): digest for name, digest in report["source_hashes"].items()
    }
    expected |= {
        _relative(sample["audio"]): sample["audio_sha256"] for sample in manifest["samples"]
    }
    for name, digest in expected.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Bundle evidence changed before archive")
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as target:
        for name, digest in sorted(expected.items()):
            raw = (root / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError("Bundle evidence changed during archive")
            target.writestr(name, raw)
    with output.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--per-speaker", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args(argv)
    report = prepare(
        args.output_root,
        per_speaker=args.per_speaker,
        seed=args.seed,
        commit=args.source_commit,
        workers=args.workers,
    )
    if args.archive and not report["errors"]:
        report["archive_sha256"] = archive_bundle(args.output_root, args.archive)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "rows"}, ensure_ascii=False
        )
    )
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
