"""Đối chiếu mọi clip của người ViMD đã chọn với metadata tại commit đã ghim.

Chỉ đọc speakerID/region/filename từ Parquet qua HTTP Range, không tải cột audio.
Cần nhóm dependency data (pyarrow). JSON không chứa transcript hay URL audio.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from data_download_core import Client, DownloadError

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = "nguyendv02/ViMD_Dataset"
PINNED_REVISION = "3a5b30157034e7eadd5c75fae1a820c6f9383398"
EXPECTED_SHARDS = 130
METADATA_COLUMNS = ("speakerID", "region", "filename")
# Identity includes the upstream shard: a repeated filename in two splits is not collapsed.
Record = tuple[str, str, str, str]


def read_selection(path: Path) -> list[Record]:
    """Đọc khóa đối chiếu từ manifest, bỏ hoàn toàn transcript/audio metadata."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("Manifest phải là danh sách mẫu không rỗng.")
    records: list[Record] = []
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError("Mẫu manifest không phải object.")
        values = tuple(row.get(key) for key in (*METADATA_COLUMNS, "shard"))
        if any(not isinstance(value, str) or not value for value in values):
            raise ValueError("Manifest thiếu speakerID/region/filename/shard hợp lệ.")
        if row.get("subject_id", values[0]) != values[0]:
            raise ValueError("subject_id không trùng speakerID.")
        if values[1] not in ("North", "Central", "South"):
            raise ValueError("Manifest có vùng miền chưa biết.")
        records.append(values)
    if len(records) != len(set(records)):
        raise ValueError("Manifest có dòng nguồn trùng, không thể kiểm kê mẫu độc lập.")
    return records


def _record_json(record: Record) -> dict[str, str]:
    return dict(zip((*METADATA_COLUMNS, "shard"), record, strict=True))


def audit(manifest: Path, client: Client, workers: int = 4) -> dict[str, Any]:
    """So sánh người đã chọn với mọi shard ở PINNED_REVISION; không đọc audio."""
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("Cần pyarrow: uv sync --all-packages --group data.") from exc
    local = read_selection(manifest)
    subjects = {row[0] for row in local}
    endpoint = (
        f"https://huggingface.co/api/datasets/{REPOSITORY}/tree/"
        f"{PINNED_REVISION}?recursive=true&limit=1000"
    )
    entries = client.json(endpoint)
    # The pinned tree has only 130 shards. Refuse a potentially paginated tree.
    if not isinstance(entries, list) or len(entries) >= 1000:
        raise ValueError("Cây nguồn quá lớn hoặc không đầy đủ; cần bổ sung pagination.")
    shards = sorted(
        (row for row in entries if row.get("path", "").endswith(".parquet")),
        key=lambda row: row["path"],
    )
    if not shards:
        raise ValueError("Revision đã ghim không có parquet.")

    def scan(shard: dict[str, Any]) -> list[Record]:
        relative = shard["path"]
        url = f"https://huggingface.co/datasets/{REPOSITORY}/resolve/{PINNED_REVISION}/{relative}"
        with client.remote_file(url, shard["size"]) as handle:
            parquet = pq.ParquetFile(handle)
            if not set(METADATA_COLUMNS).issubset(parquet.schema_arrow.names):
                raise ValueError("Parquet thiếu một trong các cột metadata cần kiểm kê.")
            rows = parquet.read(columns=list(METADATA_COLUMNS)).to_pylist()
        return [
            (row["speakerID"], row["region"], row["filename"], relative)
            for row in rows
            if row["speakerID"] in subjects
        ]

    source: list[Record] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for index, records in enumerate(pool.map(scan, shards), start=1):
            source.extend(records)
            if index % 25 == 0 or index == len(shards):
                print(f"Metadata ViMD: {index}/{len(shards)} shards; không đọc audio.", flush=True)
    local_counts = Counter(row[0] for row in local)
    source_counts = Counter(row[0] for row in source)
    source_keys, local_keys = set(source), set(local)
    missing, extra = source_keys - local_keys, local_keys - source_keys
    duplicate_source = len(source) != len(source_keys)
    by_speaker = {
        speaker: {
            "local_count": local_counts[speaker],
            "source_count": source_counts[speaker],
            "missing": [_record_json(row) for row in sorted(missing) if row[0] == speaker],
            "extra": [_record_json(row) for row in sorted(extra) if row[0] == speaker],
        }
        for speaker in sorted(subjects)
    }
    complete = not missing and not extra and not duplicate_source and local_counts == source_counts
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    return {
        "dataset": REPOSITORY,
        "pinned_revision": PINNED_REVISION,
        "audit_commit": commit,
        "audit_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "recorded_at": datetime.now(UTC).isoformat(),
        "columns_read": list(METADATA_COLUMNS),
        "audio_read": False,
        "shards_scanned": len(shards),
        "manifest": str(manifest.resolve()),
        "local_rows": len(local),
        "source_rows_for_selected_speakers": len(source),
        "selected_speakers": len(subjects),
        "local_region_rows": dict(sorted(Counter(row[1] for row in local).items())),
        "source_region_rows": dict(sorted(Counter(row[1] for row in source).items())),
        "speakers": by_speaker,
        "missing": [_record_json(row) for row in sorted(missing)],
        "extra": [_record_json(row) for row in sorted(extra)],
        "source_has_duplicate_keys": duplicate_source,
        "complete": complete,
        "label_note": "Nguồn ViMD là chương trình truyền hình giọng người; metadata không có nhãn anti-spoof genuine.",
    }


def main(argv: list[str] | None = None) -> int:
    """Chạy kiểm kê metadata và lưu JSON ngoài repo theo DATA_DIR."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    data_root = Path(os.environ.get("DATA_DIR", "data")).expanduser()
    if not data_root.is_absolute():
        data_root = ROOT / data_root
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=data_root / "raw/vimd/selected_manifest.json"
    )
    parser.add_argument("--output", type=Path, default=data_root / "eval/VOICE04/completeness.json")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    if args.workers < 1 or args.workers > 8:
        parser.error("--workers phải từ 1 đến 8.")
    if importlib.util.find_spec("pyarrow") is None:
        parser.error("Install pyarrow: uv sync --all-packages --extra voice --group data.")
    client = Client()
    try:
        result = audit(args.manifest, client, args.workers)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_name(args.output.name + ".part")
        temporary.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(args.output)
        print(f"Đã ghi kiểm kê ViMD: {args.output}; complete={result['complete']}")
        return 0 if result["complete"] else 1
    except (OSError, ValueError, RuntimeError, DownloadError, subprocess.SubprocessError) as exc:
        # Do not expose transport exceptions, response contents, or signed URLs.
        print(
            f"Kiểm kê ViMD không hoàn tất ({type(exc).__name__}); không đọc audio.", file=sys.stderr
        )
        return 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
