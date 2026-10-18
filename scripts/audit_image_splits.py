"""Kiểm độc lập CSV chia ảnh; chỉ đọc metadata và kiểm sự tồn tại của media."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath, PureWindowsPath

DATASETS = ("zalo2022", "wilddeepfake", "fas_vn", "rtfs10k", "vicocktail", "vn_celeb_faces")
SPLITS = ("train", "calib_fit", "calib_ltt", "test")
REQUIRED_FIELDS = {
    "path",
    "label",
    "attack_type",
    "subject_id",
    "source",
    "source_group",
    "reference_group",
    "group_id",
}
Row = dict[str, str]


def audit(data_dir: Path, datasets: tuple[str, ...] = DATASETS) -> dict:
    """Trả số lượng, vi phạm rò rỉ/đường dẫn và cảnh báo quota từ CSV local."""
    data_dir = data_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    summary: list[dict] = []
    quotas: list[dict] = []
    memberships: dict[tuple[str, ...], set[str]] = defaultdict(set)
    locations: dict[tuple[str, ...], set[str]] = defaultdict(set)
    rows_by_dataset: dict[str, dict[str, list[Row]]] = {}

    for dataset in datasets:
        source_root = data_dir / "raw" / dataset
        partitions: dict[str, list[Row]] = {}
        rows_by_dataset[dataset] = partitions
        for split in SPLITS:
            csv_path = data_dir / "splits" / dataset / f"{split}.csv"
            partitions[split] = []
            if not csv_path.is_file():
                errors.append(f"Thiếu CSV: {dataset}/{split}.csv")
                continue
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                missing = REQUIRED_FIELDS - set(reader.fieldnames or ())
                if missing:
                    errors.append(f"{dataset}/{split}: thiếu cột {', '.join(sorted(missing))}")
                    continue
                for line, row in enumerate(reader, 2):
                    location = f"{dataset}/{split}:{line}"
                    if None in row or any(value is None for value in row.values()):
                        errors.append(f"{location}: số cột không khớp header")
                        continue
                    partitions[split].append(row)
                    if row["source"] != dataset:
                        errors.append(f"{location}: source không khớp thư mục CSV")
                    if row["label"] not in {"0", "1"}:
                        errors.append(f"{location}: label phải là 0 hoặc 1")
                    if not row["group_id"]:
                        errors.append(f"{location}: thiếu group_id")
                    if dataset == "zalo2022" and row["subject_id"]:
                        errors.append(f"{location}: Zalo subject_id phải để trống")
                    if dataset == "wilddeepfake" and not row["source_group"]:
                        errors.append(f"{location}: thiếu nhóm video WildDeepfake")
                    if dataset in {"fas_vn", "rtfs10k"} and split != "test":
                        errors.append(f"{location}: {dataset} chỉ được ở test")
                    if dataset == "wilddeepfake" and split == "train":
                        errors.append(f"{location}: WildDeepfake không có train")

                    relative = row["path"]
                    normalized = relative.replace("\\", "/")
                    resolved = (data_dir / normalized).resolve()
                    if (
                        not normalized
                        or "\\" in relative
                        or PurePosixPath(normalized).is_absolute()
                        or PureWindowsPath(relative).drive
                        or ".." in PurePosixPath(normalized).parts
                        or not resolved.is_relative_to(data_dir)
                    ):
                        errors.append(f"{location}: path không tương đối DATA_DIR: {relative}")
                    elif PurePosixPath(relative).parts[:2] != (
                        "raw",
                        dataset,
                    ) or not resolved.is_relative_to(source_root):
                        errors.append(f"{location}: path phải nằm trong raw/{dataset}/: {relative}")
                    elif not resolved.is_file():
                        errors.append(f"{location}: media không tồn tại: {relative}")
                    path_key = ("path", str(resolved).casefold())
                    if locations[path_key]:
                        errors.append(
                            f"{location}: path trùng với {sorted(locations[path_key])[0]}"
                        )
                    locations[path_key].add(location)

                    keys = [("group_id", row["group_id"])] if row["group_id"] else []
                    keys.extend(
                        (field, row["source"], row[field])
                        for field in ("subject_id", "source_group", "reference_group")
                        if row[field]
                    )
                    for key in keys:
                        memberships[key].add(split)
                        locations[key].add(location)

            split_rows = partitions[split]
            counts = Counter((row["label"], row["attack_type"]) for row in split_rows)
            summary.append(
                {
                    "dataset": dataset,
                    "split": split,
                    "samples": len(split_rows),
                    "groups": len({row["group_id"] for row in split_rows if row["group_id"]}),
                    "video_groups": len(
                        {row["source_group"] for row in split_rows if row["source_group"]}
                    ),
                    "subjects": len({row["subject_id"] for row in split_rows if row["subject_id"]}),
                    "counts": [
                        {"label": label, "attack_type": attack, "samples": count}
                        for (label, attack), count in sorted(counts.items())
                    ],
                }
            )

    for key, splits in sorted(memberships.items()):
        if len(splits) > 1:
            errors.append(
                f"Rò rỉ {'/'.join(key)} qua {', '.join(sorted(splits))}: "
                + ", ".join(sorted(locations[key]))
            )

    for dataset in datasets:
        if dataset not in {"zalo2022", "wilddeepfake"}:
            continue
        partitions = rows_by_dataset[dataset]
        attacks = sorted(
            {
                row["attack_type"]
                for rows in partitions.values()
                for row in rows
                if row["label"] == "1"
            }
        )
        requirements = [("calib_fit", "label", label, 100) for label in ("0", "1")]
        if dataset == "wilddeepfake":
            requirements.extend(("calib_ltt", "label", label, 60) for label in ("0", "1"))
        requirements.extend(("calib_ltt", "attack_type", attack, 60) for attack in attacks)
        for split, field, value, minimum in requirements:
            count = sum(row[field] == value for row in partitions[split])
            donors = [row for row in partitions["train"] if row[field] == value]
            record = {
                "dataset": dataset,
                "split": split,
                "field": field,
                "value": value,
                "samples": count,
                "minimum": minimum,
                "deficit": max(0, minimum - count),
                "train_donor_samples": len(donors),
                "train_donor_groups": len({row["group_id"] for row in donors}),
            }
            quotas.append(record)
            if count < minimum:
                message = (
                    f"{dataset}/{split} {field}={value}: {count}/{minimum}, "
                    f"thiếu {minimum - count}; train còn {len(donors)} mẫu trong "
                    f"{record['train_donor_groups']} nhóm"
                )
                if count + len(donors) >= minimum:
                    errors.append("Quota chưa dồn đủ nhóm train: " + message)
                else:
                    warnings.append("Quota thiếu, không đủ nhóm train hợp lệ: " + message)

    return {"errors": errors, "warnings": warnings, "summary": summary, "quotas": quotas}


def main() -> int:
    """Audit CSV hiện có; exit 1 nếu có lỗi, quota bất khả thi chỉ cảnh báo."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("DATA_DIR", "data")))
    parser.add_argument("--only", nargs="+", choices=DATASETS)
    args = parser.parse_args()
    datasets = (
        tuple(args.only)
        if args.only
        else tuple(name for name in DATASETS if (args.data_dir / "splits" / name).is_dir())
    )
    if not datasets:
        parser.error("Không tìm thấy thư mục split ảnh; chọn --data-dir hoặc --only")
    report = audit(args.data_dir, datasets)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
