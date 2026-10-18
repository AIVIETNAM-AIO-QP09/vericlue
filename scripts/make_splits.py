"""Chia local audio theo nhóm nguồn/người; không tải mạng, không sửa audio."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parent.parent
DATASETS = ("mlaad_vi", "vsasv", "vimd", "vivos", "vispoofdb")
SPLITS = ("train", "calib_fit", "calib_ltt", "test")
FIELDS = (
    "path",
    "label",
    "attack_type",
    "subject_id",
    "source",
    "region",
    "source_group",
    "reference_group",
    "tts",
    "group_id",
)
AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg"}
Row = dict[str, str]
SplitMap = dict[str, dict[str, list[Row]]]


class UnionFind:
    def __init__(self) -> None:
        self.parents: dict[str, str] = {}

    def find(self, key: str) -> str:
        self.parents.setdefault(key, key)
        if self.parents[key] != key:
            self.parents[key] = self.find(self.parents[key])
        return self.parents[key]

    def union(self, left: str, right: str) -> None:
        a, b = sorted((self.find(left), self.find(right)))
        self.parents[b] = a


def reference_identity(reference: str) -> str:
    """Nhóm rủi ro theo thư mục reader M-AILABS, không tự tạo subject ID."""
    parts = PurePosixPath(reference.replace("\\", "/")).parts
    if "by_book" in parts:
        index = parts.index("by_book")
        if len(parts) > index + 2:
            return "/".join(parts[: index + 3])
    return reference.replace("\\", "/")


def _load(data_dir: Path, name: str) -> list[Row]:
    data_dir = data_dir.resolve()
    folder = (data_dir / "raw" / name).resolve()
    records = json.loads((folder / "selected_manifest.json").read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError(f"{name}: manifest phải là danh sách")
    rows: list[Row] = []
    paths: set[str] = set()
    for item in records:
        relative = str(item["path"]).replace("\\", "/")
        if PurePosixPath(relative).suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        path = (folder / relative).resolve()
        if not path.is_relative_to(folder) or not path.is_file():
            raise ValueError(f"{name}: audio thiếu hoặc đường dẫn không hợp lệ: {relative}")
        if str(path) in paths:
            raise ValueError(f"{name}: đường dẫn trùng: {relative}")
        paths.add(str(path))
        row = dict.fromkeys(FIELDS, "")
        row.update(
            path=path.relative_to(data_dir).as_posix(),
            source=name,
            subject_id=str(item.get("subject_id") or ""),
            region=str(item.get("region") or ""),
        )
        if name == "mlaad_vi":
            original = str(item.get("original_file") or "")
            if not original:
                raise ValueError("MLAAD thiếu original_file: cần chạy lại DATA-01")
            reference = str(item.get("reference_speaker") or "").strip()
            if reference.lower() in {"none", "null", "nan", "unknown", "n/a"}:
                reference = ""
            row.update(
                label="1",
                attack_type="tts",
                source_group=original,
                reference_group=reference_identity(reference) if reference else "",
                tts=str(item.get("tts") or item.get("model_name") or ""),
            )
            if not row["tts"]:
                raise ValueError("MLAAD thiếu hệ TTS")
        elif name == "vsasv":
            if item.get("source_label") and str(item["source_label"]) != row["subject_id"]:
                raise ValueError("VSASV subject_id không khớp source_label")
            original = str(item.get("original_path") or item.get("file") or "")
            source_person = PurePosixPath(original).parts[0] if original else ""
            if source_person.startswith("id") and source_person != row["subject_id"]:
                raise ValueError("VSASV subject_id không khớp đường dẫn gốc")
            kind = str(item.get("utt_type") or "")
            if kind not in {"bonafide", "replay"}:
                raise ValueError(f"VSASV utt_type chưa hỗ trợ: {kind}")
            row.update(label="0" if kind == "bonafide" else "1", attack_type=kind)
        elif name == "vispoofdb":
            parts = PurePosixPath(relative).parts
            if parts[0] == "real":
                row.update(label="0", attack_type="bonafide")
            elif len(parts) >= 3 and parts[0] == "fake":
                row.update(label="1", attack_type="tts", tts=parts[1])
            else:
                raise ValueError(f"ViSpoofDB không rõ nhãn: {relative}")
        else:
            row.update(label="0", attack_type="bonafide")
        if name == "vimd":
            if item.get("speakerID") and str(item["speakerID"]) != row["subject_id"]:
                raise ValueError("ViMD subject_id không khớp speakerID")
            if row["region"] not in {"North", "Central", "South"}:
                raise ValueError("ViMD region phải là North/Central/South")
        if name in {"vsasv", "vimd", "vivos"} and not row["subject_id"]:
            raise ValueError(f"{name}: thiếu subject_id")
        rows.append(row)
    if not rows:
        raise ValueError(f"{name}: không có audio")
    return sorted(rows, key=lambda r: r["path"])


def _groups(rows: list[Row]) -> list[list[Row]]:
    uf = UnionFind()
    for row in rows:
        key = "file:" + row["path"]
        for field in ("subject_id", "source_group", "reference_group"):
            if row[field]:
                uf.union(key, field + ":" + row[field])
    groups: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        groups[uf.find("file:" + row["path"])].append(row)
    result = sorted(groups.values(), key=lambda group: group[0]["path"])
    for group in result:
        # Opaque component ID is NOT a person ID.
        identity = group[0]["source"] + "\n" + "\n".join(row["path"] for row in group)
        group_id = hashlib.sha256(identity.encode()).hexdigest()[:20]
        for row in group:
            row["group_id"] = group_id
    return result


def _partition(groups: list[list[Row]], seed: int) -> dict[str, list[Row]]:
    rng = random.Random(seed)
    ordered = list(groups)
    rng.shuffle(ordered)
    # Keep the largest connected component in train. Ratios target GROUP counts;
    # large components can make sample ratios very different (reported, never cut).
    ordered.sort(key=len, reverse=True)
    count = len(ordered)
    fit = max(1, round(count * 0.1)) if count >= 4 else 0
    ltt = fit
    test = max(1, round(count * 0.2)) if count >= 4 else 0
    sizes = (count - fit - ltt - test, fit, ltt, test)
    result = {name: [] for name in SPLITS}
    capacities = dict(zip(SPLITS, sizes, strict=True))
    used = Counter()
    system_groups = Counter(
        system for group in ordered for system in {row["tts"] for row in group if row["tts"]}
    )
    system_used: dict[str, Counter] = {split: Counter() for split in SPLITS}
    for group in ordered:
        systems = {row["tts"] for row in group if row["tts"]}
        available = [split for split in SPLITS if used[split] < capacities[split]]

        def deficit(split: str, systems: set[str] = systems) -> float:
            target = capacities[split]
            score = (target - used[split]) / target
            for system in sorted(systems):
                desired = system_groups[system] * target / count
                score += (desired - system_used[split][system]) / max(1, desired)
            return score

        # Largest component belongs to train; then stratify TTS at group level.
        split = "train" if not any(used.values()) else max(available, key=deficit)
        result[split].extend(group)
        used[split] += 1
        system_used[split].update(systems)
    return result


def fill_calibration_quotas(splits: SplitMap, seed: int = 42) -> None:
    """Dồn nguyên component từ train: LTT ≥60/attack, rồi fit ≥100/lớp.

    Không lấy test/fit cho LTT; không lấy LTT/test cho fit. Giữ nguyên ViMD
    để không phá một người/miền/tập. Nhóm nhỏ ưu tiên, hòa chọn bằng seed.
    """
    candidates: dict[str, list[tuple[str, Row]]] = defaultdict(list)
    for source, part in splits.items():
        for row in part["train"]:
            candidates[row["group_id"]].append((source, row))
    keys = sorted(candidates)
    random.Random(seed).shuffle(keys)
    # Sorting is stable: seeded shuffle breaks equal-size ties reproducibly.
    keys.sort(key=lambda key: len(candidates[key]))
    eligible = [
        key
        for key in keys
        if all(source not in {"vimd", "vivos", "vispoofdb"} for source, _ in candidates[key])
    ]
    attacks = sorted(
        {
            row["attack_type"]
            for part in splits.values()
            for rows in part.values()
            for row in rows
            if row["label"] == "1"
        }
    )
    for destination, field, targets, minimum in (
        ("calib_ltt", "attack_type", attacks, 60),
        ("calib_fit", "label", ["0", "1"], 100),
    ):
        counts = Counter(
            row[field]
            for part in splits.values()
            for row in part[destination]
            if destination != "calib_ltt" or row["label"] == "1"
        )
        for target in targets:
            for key in list(eligible):
                if counts[target] >= minimum:
                    break
                group = candidates[key]
                if not any(
                    row[field] == target and (destination != "calib_ltt" or row["label"] == "1")
                    for _, row in group
                ):
                    continue
                for source, row in group:
                    splits[source][destination].append(row)
                    if destination != "calib_ltt" or row["label"] == "1":
                        counts[row[field]] += 1
                for source in {source for source, _ in group}:
                    splits[source]["train"] = [
                        row for row in splits[source]["train"] if row["group_id"] != key
                    ]
                eligible.remove(key)


def resolve_audio(data_dir: Path, row: Row) -> Path:
    """Ghép audio tương đối với DATA_DIR và kiểm tra file local."""
    return _resolve_audio(data_dir.resolve(), row)


def _resolve_audio(root: Path, row: Row) -> Path:
    """Ghép path tương đối DATA_DIR; từ chối absolute, traversal, symlink ra ngoài."""
    relative = PurePosixPath(row["path"])
    expected = ("raw", row["source"])
    if (
        relative.is_absolute()
        or PureWindowsPath(row["path"]).drive
        or ".." in relative.parts
        or "\\" in row["path"]
        or relative.parts[:2] != expected
    ):
        raise ValueError(f"Đường dẫn audio phải tương đối DATA_DIR: {row['path']}")
    path = (root / relative).resolve()
    if not path.is_relative_to(root / "raw" / row["source"]) or not path.is_file():
        raise ValueError(f"Audio thiếu hoặc nằm ngoài DATA_DIR: {row['path']}")
    return path


def validate_splits(splits: SplitMap, data_dir: Path, *, check_files: bool = True) -> None:
    """Từ chối tách người/nhóm nguồn/reference đã biết hoặc rò bộ test-only."""
    data_dir = data_dir.resolve()
    global_groups: dict[str, str] = {}
    for source, partition in splits.items():
        seen: dict[tuple[str, str], str] = {}
        paths: set[str] = set()
        for split, rows in partition.items():
            if source in {"vivos", "vispoofdb"} and split != "test" and rows:
                raise ValueError(f"{source}: phải test-only")
            for row in rows:
                if check_files:
                    _resolve_audio(data_dir, row)
                if row["path"] in paths:
                    raise ValueError("Audio xuất hiện nhiều lần")
                paths.add(row["path"])
                if row["group_id"]:
                    previous = global_groups.setdefault(row["group_id"], split)
                    if previous != split:
                        raise ValueError("Tách nhóm đã liên kết xuyên bộ")
                for field in ("subject_id", "source_group", "reference_group", "group_id"):
                    value = row[field]
                    if value:
                        key = (field, value)
                        if key in seen and seen[key] != split:
                            raise ValueError(f"{source}: tách nhóm {field}")
                        seen[key] = split


def _apply_identity_links(splits: SplitMap, path: Path) -> None:
    """Crosswalk do người dùng xác minh: source,kind,identity,canonical_id."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        links = list(csv.DictReader(stream))
    uf = UnionFind()
    lookup: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    rows: list[tuple[str, str, Row]] = []
    for source, part in splits.items():
        for split, values in part.items():
            for row in values:
                component = source + ":" + row["group_id"]
                rows.append((source, split, row))
                for field in ("subject_id", "reference_group"):
                    if row[field]:
                        lookup[(source, field, row[field])].append(component)
    for link in links:
        source, kind, identity, canonical = (
            link.get(field, "").strip() for field in ("source", "kind", "identity", "canonical_id")
        )
        if kind not in {"subject_id", "reference_group"} or not canonical:
            raise ValueError("Crosswalk thiếu kind/canonical_id hợp lệ")
        matches = lookup.get((source, kind, identity), [])
        if not matches:
            raise ValueError(f"Crosswalk không khớp dữ liệu: {source}/{kind}/{identity}")
        for component in matches:
            uf.union(component, "canonical:" + canonical)
    connected: dict[str, list[tuple[str, str, Row]]] = defaultdict(list)
    for source, split, row in rows:
        connected[uf.find(source + ":" + row["group_id"])].append((source, split, row))
    for source in splits:
        splits[source] = {split: [] for split in SPLITS}
    for component_rows in connected.values():
        if any(source in {"vivos", "vispoofdb"} for source, _, _ in component_rows):
            destination = "test"
        else:
            counts = Counter(split for _, split, _ in component_rows)
            destination = max(SPLITS, key=lambda split: counts[split])
        global_id = hashlib.sha256(
            "\n".join(
                sorted({source + ":" + row["group_id"] for source, _, row in component_rows})
            ).encode()
        ).hexdigest()[:20]
        for source, _, row in component_rows:
            row["group_id"] = global_id
            splits[source][destination].append(row)


def build_splits(data_dir: Path, seed: int = 42, identity_links: Path | None = None) -> SplitMap:
    """Chia năm bộ local theo chính sách DATA-03 âm thanh được duyệt."""
    result: SplitMap = {}
    for name in DATASETS:
        rows = _load(data_dir, name)
        groups = _groups(rows)
        if name in {"vivos", "vispoofdb"}:
            result[name] = {split: rows if split == "test" else [] for split in SPLITS}
        elif name == "vimd":
            by_region: dict[str, list[list[Row]]] = defaultdict(list)
            for group in groups:
                regions = {row["region"] for row in group}
                if len(regions) != 1 or not next(iter(regions)):
                    raise ValueError("ViMD: mỗi người phải có đúng một miền")
                by_region[next(iter(regions))].append(group)
            if len(by_region) != 3 or any(len(g) != 4 for g in by_region.values()):
                raise ValueError("ViMD audio small cần đúng 3 miền, 4 người/miền")
            result[name] = {split: [] for split in SPLITS}
            rng = random.Random(seed)
            for region in sorted(by_region):
                region_groups = by_region[region]
                rng.shuffle(region_groups)
                for split, group in zip(SPLITS, region_groups, strict=True):
                    result[name][split].extend(group)
        else:
            result[name] = _partition(groups, seed)
        for rows_in_split in result[name].values():
            rows_in_split.sort(key=lambda row: row["path"])
    if identity_links is not None:
        _apply_identity_links(result, identity_links)
        for part in result.values():
            for values in part.values():
                values.sort(key=lambda row: row["path"])
    validate_splits(result, data_dir, check_files=False)
    fill_calibration_quotas(result, seed)
    for part in result.values():
        for values in part.values():
            values.sort(key=lambda row: row["path"])
    validate_splits(result, data_dir, check_files=False)
    return result


def quota_report(splits: SplitMap) -> list[str]:
    """Đếm thiếu quota toàn pool; số lượng không đồng nghĩa đủ chứng nhận."""
    fit = Counter(row["label"] for part in splits.values() for row in part["calib_fit"])
    messages = [
        f"calib_fit lớp {label}: {fit[label]}/100; thiếu {max(0, 100 - fit[label])}"
        for label in ("0", "1")
    ]
    attack_types = sorted(
        {
            row["attack_type"]
            for part in splits.values()
            for rows in part.values()
            for row in rows
            if row["label"] == "1"
        }
    )
    ltt = Counter(
        row["attack_type"]
        for part in splits.values()
        for row in part["calib_ltt"]
        if row["label"] == "1"
    )
    for attack in attack_types:
        messages.append(f"calib_ltt {attack}: {ltt[attack]}/60; thiếu {max(0, 60 - ltt[attack])}")
    tts = sorted(
        {
            f"{source}/{row['tts']}"
            for source, part in splits.items()
            for rows in part.values()
            for row in rows
            if row["tts"]
        }
    )
    counts = Counter(
        f"{source}/{row['tts']}"
        for source, part in splits.items()
        for row in part["calib_ltt"]
        if row["tts"]
    )
    for system in tts:
        messages.append(
            f"calib_ltt hệ {system}: {counts[system]}/60; thiếu {max(0, 60 - counts[system])}"
        )
    return messages


def audit_hashes(splits: SplitMap, data_dir: Path) -> list[str]:
    """Hash file có cùng size: bằng chứng yếu, không xác minh danh tính."""
    data_dir = data_dir.resolve()
    rows = {
        source: [row for values in part.values() for row in values]
        for source, part in splits.items()
    }
    target: dict[int, list[Path]] = defaultdict(list)
    for row in rows["vispoofdb"]:
        path = _resolve_audio(data_dir, row)
        target[path.stat().st_size].append(path)
    assignment = {
        row["path"]: split
        for part in splits.values()
        for split, values in part.items()
        for row in values
    }
    cache: dict[Path, str] = {}

    def digest(path: Path) -> str:
        if path not in cache:
            with path.open("rb") as stream:
                cache[path] = hashlib.file_digest(stream, "sha256").hexdigest()
        return cache[path]

    lines = []
    for source in ("vivos", "vsasv", "vimd"):
        matches = 0
        sizes: dict[int, set[str]] = {}
        for row in rows[source]:
            path = _resolve_audio(data_dir, row)
            size = path.stat().st_size
            if size not in target:
                continue
            if size not in sizes:
                sizes[size] = {digest(p) for p in target[size]}
            if digest(path) in sizes[size]:
                matches += 1
                if assignment[row["path"]] != "test":
                    raise ValueError(
                        f"Audio trùng byte {source} với ViSpoofDB test: cần crosswalk để giữ cùng tập"
                    )
        lines.append(f"{source} ↔ vispoofdb: {matches} audio nguồn trùng byte (SHA-256).")
    lines.append(
        f"Đã hash {len(cache)} file, {sum(p.stat().st_size for p in cache)} byte; lọc ứng viên theo size trước hash."
    )
    return lines


def write_splits(
    data_dir: Path, splits: SplitMap, seed: int = 42, hash_audit: list[str] | None = None
) -> Path:
    """Ghi CSV và báo cáo ngoài repo; chạy lại cùng input cho cùng nội dung."""
    validate_splits(splits, data_dir)
    output = data_dir / "splits"
    output.mkdir(parents=True, exist_ok=True)
    commit = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
        ).stdout.strip()
        or "unknown"
    )
    mlaad_test_tts = sorted({row["tts"] for row in splits["mlaad_vi"]["test"] if row["tts"]})
    other_tts = {
        row["tts"]
        for split, rows in splits["mlaad_vi"].items()
        if split != "train"
        for row in rows
        if row["tts"]
    }
    train_only_tts = sorted(
        {row["tts"] for row in splits["mlaad_vi"]["train"] if row["tts"]} - other_tts
    )
    lines = [
        "# DATA-03 — chia tập âm thanh",
        "",
        f"Seed: {seed}; commit: `{commit}`.",
        f"Script SHA-256: `{hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}`.",
        "Chỉ xử lý local; không dùng mô hình/trọng số, không chọn ngưỡng.",
        "",
        "## Chính sách và giới hạn",
        "",
        "Quyết định trưởng nhóm 16/10: VIVOS + ViSpoofDB cùng test do bằng chứng chung nguồn người.",
        "VSASV và ViMD GIẢ ĐỊNH độc lập với nhau và với VIVOS/ViSpoofDB; chưa xác minh danh tính xuyên bộ.",
        "Rủi ro: cùng người có thể mang ID khác nhau; namespace khác không chứng minh khác người.",
        "MLAAD union câu original_file ∪ reference theo thư mục reader M-AILABS (nhóm rủi ro, chưa xác minh danh tính).",
        "Reference khác cấu trúc dùng nguyên đường dẫn; mẫu thiếu reference CHỈ nhóm theo câu nguồn, không gom vixTTS.",
        "Chưa có crosswalk reference MLAAD sang bộ khác trong dữ liệu nguồn; dùng --identity-links cho liên kết đã xác minh, nhóm liên kết với VIVOS/ViSpoofDB phải theo test.",
        "CSV path tương đối DATA_DIR (raw/<bộ>/...), ghép DATA_DIR/path khi đọc; không phụ thuộc ổ đĩa của người sinh CSV.",
        "Rủi ro VOICE-01/03: vixTTS thiếu reference có thể dùng chung giọng mặc định; nhóm theo câu nguồn có thể để cùng giọng tổng hợp ở cả bốn tập. Không chứng minh độc lập người cho phần này.",
        f"VOICE-01/03: test MLAAD hiện có TTS={mlaad_test_tts}; hệ chỉ có trong train={train_only_tts}. Không tự coi đây là test hệ TTS chưa thấy.",
        "subject_id để trống khi nguồn không có ID; group_id/reference_group không phải ID người giả.",
        "VSASV/MLAAD mục tiêu 60/10/10/20 theo số nhóm; nhóm lớn nhất ưu tiên train; seed cố định và thứ tự ổn định.",
        "Phân tầng TTS theo số nhóm trong giới hạn liên kết; TTS được thống kê theo từng tập; không bảo đảm giữ riêng một TTS chưa thấy. Nhóm liên kết ưu tiên hơn tỷ lệ/TTS.",
        "Dồn quota mọi loại tấn công chính từ train sang calib_ltt ≥60, rồi từ train sang calib_fit ≥100/lớp; ưu tiên nhóm nhỏ, tie seed cấu hình, không tách nhóm/người, không đổi ViMD.",
        "ViMD mục tiêu một người/miền/tập (25% người mỗi tập), rất nhỏ; crosswalk đã xác minh có thể ưu tiên hơn cân bằng miền. Đã dùng 19 câu báo cáo VOICE-04, không chỉnh ngưỡng.",
        "ViSpoofDB loại corpus.txt; giữ WAV và MP3. Dữ liệu test không dùng chọn mô hình/ngưỡng.",
        "DATA-03 còn doing: chưa có phần ảnh; quota còn thiếu sau khi dồn phải ghi rõ, không tự chứng nhận LTT.",
        "",
        "## Kiểm hash",
        "",
        *(hash_audit or ["Chưa chạy; dùng --audit-hashes để đo local."]),
        "Không có file trùng byte chỉ là bằng chứng yếu; không chứng minh khác người (có thể cắt/mã hóa lại).",
        "",
        "## Số mẫu",
        "",
        "| Bộ | Tập | Mẫu | Thật | Giả | Người có ID | Nhóm liên kết |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    details: list[str] = []
    for source, partition in splits.items():
        folder = output / source
        folder.mkdir(parents=True, exist_ok=True)
        for split in SPLITS:
            rows = partition[split]
            with (folder / f"{split}.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            labels = Counter(row["label"] for row in rows)
            people = {row["subject_id"] for row in rows if row["subject_id"]}
            groups = {row["group_id"] for row in rows}
            lines.append(
                f"| {source} | {split} | {len(rows)} | {labels['0']} | {labels['1']} | {len(people)} | {len(groups)} |"
            )
        details += ["", f"### {source}: chi tiết", ""]
        for split, rows in partition.items():
            attacks = dict(sorted(Counter(row["attack_type"] for row in rows).items()))
            systems = dict(sorted(Counter(row["tts"] for row in rows if row["tts"]).items()))
            regions = dict(sorted(Counter(row["region"] for row in rows if row["region"]).items()))
            region_people = {
                region: len({row["subject_id"] for row in rows if row["region"] == region})
                for region in sorted({row["region"] for row in rows if row["region"]})
            }
            subjects = sorted({row["subject_id"] for row in rows if row["subject_id"]})
            details.append(
                f"- {split}: attack={attacks}; TTS={systems}; mẫu/miền={regions}; người/miền={region_people}; subject_id={subjects}"
            )
        manifest = data_dir / "raw" / source / "selected_manifest.json"
        details.append(f"- manifest SHA-256: {hashlib.sha256(manifest.read_bytes()).hexdigest()}")
        source_doc = data_dir / "raw" / source / "SOURCE.md"
        if source_doc.exists():
            revision = [
                line
                for line in source_doc.read_text(encoding="utf-8").splitlines()
                if "Revision:" in line or "Nguồn:" in line
            ]
            details.extend(revision)
        details.append("")
    lines += [
        "",
        "## Tỷ lệ calib thực tế (fit + LTT)",
        "",
        "Tỷ lệ sau dồn quota; tỷ lệ mục tiêu theo nhóm không tương đương tỷ lệ mẫu.",
    ]
    for source, part in splits.items():
        rows = [row for values in part.values() for row in values]
        calib = part["calib_fit"] + part["calib_ltt"]
        people = {row["subject_id"] for row in rows if row["subject_id"]}
        calib_people = {row["subject_id"] for row in calib if row["subject_id"]}
        ratio = len(calib) / len(rows) * 100
        lines.append(f"- {source}: calib {len(calib)}/{len(rows)} mẫu = {ratio:.2f}%.")
        if people:
            person_ratio = len(calib_people) / len(people) * 100
            lines.append(f"  Người: {len(calib_people)}/{len(people)} = {person_ratio:.2f}%.")
        if source == "vsasv":
            lines.append(
                "  Baseline audio small 16 người trước dồn: 4/16 = 25.00%; dồn từ train sang fit/LTT có thể tăng tỷ lệ thực tế ở trên."
            )
    lines += details
    lines += [
        "## Quota toàn pool",
        "",
        *("- " + item for item in quota_report(splits)),
        "",
        "Đếm theo hệ TTS là kiểm bổ sung, không tự coi mọi TTS là một loại tấn công độc lập.",
        "Số mẫu đạt không tự bảo đảm chứng nhận LTT hay độc lập người xuyên bộ.",
    ]
    lines += [
        "",
        *(f"- Ảnh: [{path.name}]({path.name})" for path in sorted(output.glob("SUMMARY-*.md"))),
    ]
    summary = output / "SUMMARY.md"
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--only", nargs="+", help="Chọn bộ ảnh; mặc định giữ luồng âm thanh đã có")
    parser.add_argument("--models-dir", type=Path, help="Kho ArcFace/SCRFD local cho DATA-03 ảnh")
    parser.add_argument(
        "--identity-links",
        type=Path,
        help="CSV crosswalk danh tính đã xác minh (không suy từ ID namespace)",
    )
    parser.add_argument("--audit-hashes", action="store_true", help="Kiểm SHA-256 local xuyên bộ")
    args = parser.parse_args(argv)
    if (ROOT / ".env").exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(ROOT / ".env", override=False)
        except ImportError:
            print(
                "CẢNH BÁO: thiếu python-dotenv, không đọc .env; đặt DATA_DIR hoặc --data-dir, hoặc cài --group data.",
                file=sys.stderr,
            )
    folder = args.data_dir or Path(os.environ.get("DATA_DIR", "./data"))
    if not folder.is_absolute():
        folder = ROOT / folder
    folder = folder.resolve()
    start = time.perf_counter()
    try:
        if args.only:
            from make_image_splits import IMAGE_DATASETS, run_images

            if set(args.only) - set(IMAGE_DATASETS):
                raise ValueError(f"--only ảnh hỗ trợ: {IMAGE_DATASETS}")
            if args.identity_links or args.audit_hashes:
                raise ValueError("--identity-links/--audit-hashes chỉ áp dụng luồng âm thanh")
            models = args.models_dir or Path(os.environ.get("MODELS_DIR", "./models"))
            if not models.is_absolute():
                models = ROOT / models
            run_images(folder, models.resolve(), args.only, args.seed)
            return 0
        print("Đọc manifest và chia nhóm local...", flush=True)
        splits = build_splits(folder, args.seed, args.identity_links)
        print(f"Chia nhóm: {time.perf_counter() - start:.3f}s; audit hash local...", flush=True)
        hashes = audit_hashes(splits, folder) if args.audit_hashes else None
        print(
            f"Đã audit: {time.perf_counter() - start:.3f}s tính từ đầu; ghi CSV/SUMMARY...",
            flush=True,
        )
        summary = write_splits(folder, splits, args.seed, hashes)
        if args.identity_links:
            with summary.open("a", encoding="utf-8") as stream:
                stream.write(
                    "\nCrosswalk đã áp dụng SHA-256: "
                    + hashlib.sha256(args.identity_links.read_bytes()).hexdigest()
                    + "\n"
                )
                stream.write(
                    "Liên kết đã xác minh ưu tiên hơn tỷ lệ/cân bằng miền; test-only lan truyền qua toàn nhóm.\n"
                )
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"Lỗi chia tập: {error}", file=sys.stderr)
        return 1
    print(f"DATA_DIR: {folder}\nSUMMARY: {summary}\nThời gian: {time.perf_counter() - start:.3f}s")
    for item in quota_report(splits):
        print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
