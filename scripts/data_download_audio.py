"""Bộ tải âm thanh DATA-01; chỉ metadata được đọc trước kiểm tra dung lượng."""

from __future__ import annotations

import csv
import io
import json
import random
import shutil
import tarfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

try:
    from data_download_core import (
        Client,
        Dataset,
        Plan,
        RemoteFile,
        SkipDataset,
        check_disk,
        safe_extract_tar,
        safe_path,
        sample_groups,
    )
except ModuleNotFoundError:
    from scripts.data_download_core import (
        Client,
        Dataset,
        Plan,
        RemoteFile,
        SkipDataset,
        check_disk,
        safe_extract_tar,
        safe_path,
        sample_groups,
    )

HF = "https://huggingface.co/datasets"
AUDIO_REPOS = {
    "mlaad_vi": "mueller91/MLAAD",
    "vsasv": "hustep-lab/VSASV-Dataset",
    "vimd": "nguyendv02/ViMD_Dataset",
    "vivos": "AILAB-VNUHCM/vivos",
}


def _url(repo: str, revision: str, path: str) -> str:
    return f"{HF}/{repo}/resolve/{revision}/{quote(path, safe='/')}"


def _atomic_bytes(path: Path, payload: bytes) -> None:
    if path.is_file() and path.stat().st_size == len(payload) and path.read_bytes() == payload:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _manifest(dest: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_bytes(
        dest / "selected_manifest.json",
        (json.dumps(rows, ensure_ascii=False, indent=2) + "\n").encode(),
    )


def _vivos(dataset: Dataset, client: Client, seed: int, subset: str) -> Plan:
    repo = AUDIO_REPOS[dataset.name]
    revision, entries = client.hf_files(repo)
    archive = next((row for row in entries if row["path"] == "data/vivos.tar.gz"), None)
    if not archive:
        raise SkipDataset("VIVOS: nguồn không có data/vivos.tar.gz.")
    remote = RemoteFile(
        _url(repo, revision, archive["path"]), ".cache/vivos.tar.gz", archive["size"]
    )
    budget = 250_000_000 if subset == "small" else dataset.budget_bytes

    def execute(dest: Path, download_client: Client) -> None:
        cached = safe_path(dest, remote.path)
        download_client.download(remote, cached)
        with tarfile.open(cached, "r:gz") as tar:
            speakers: dict[str, list[tarfile.TarInfo]] = defaultdict(list)
            for member in tar.getmembers():
                if member.isfile() and member.name.endswith(".wav"):
                    parts = PurePosixPath(member.name).parts
                    if "waves" not in parts:
                        continue
                    position = parts.index("waves")
                    if position + 1 >= len(parts):
                        raise SkipDataset("VIVOS: không xác định được thư mục người nói.")
                    speakers[parts[position + 1]].append(member)
            names = sorted(speakers)
            random.Random(seed).shuffle(names)
            selected, used = [], 0
            for speaker in names:
                size = sum(item.size for item in speakers[speaker])
                if subset == "full" or used + size <= budget:
                    selected.append(speaker)
                    used += size
            if not selected:
                raise SkipDataset("VIVOS: không đủ ngân sách để lấy trọn một người nói.")
            members = [item.name for speaker in selected for item in speakers[speaker]]
            prompts = [
                item
                for item in tar.getmembers()
                if item.isfile() and PurePosixPath(item.name).name == "prompts.txt"
            ]
            used += sum(item.size for item in prompts)
            members.extend(item.name for item in prompts)
            free = shutil.disk_usage(dest).free
            if free < used + 10_000_000_000:
                raise SkipDataset(
                    "VIVOS: tar index cho thấy không đủ chỗ giải nén và dự phòng 10 GB."
                )
            safe_extract_tar(cached, dest, members)
            plan.groups = selected
            _manifest(
                dest,
                [
                    {"path": item.name, "subject_id": speaker, "size": item.size}
                    for speaker in selected
                    for item in speakers[speaker]
                ],
            )

    plan = Plan(
        dataset,
        [remote],
        remote.size + (budget if subset == "small" else 4_000_000_000) + 10_000_000,
        revision=revision,
        notes=[
            "Chọn trọn người nói từ tar index sau preflight; giữ archive để chạy lại.",
            f"Seed {seed}; ngân sách WAV {budget} bytes; full giải nén dự phòng 4 GB.",
        ],
        execute=execute,
    )
    return plan


def _mlaad(dataset: Dataset, client: Client, seed: int, subset: str) -> Plan:
    repo = AUDIO_REPOS[dataset.name]
    revision, entries = client.hf_files(repo, prefix="fake/vi")
    entries = [row for row in entries if row["path"].startswith("fake/vi/")]
    files = {row["path"]: row for row in entries if row.get("type") == "file"}
    metadata = [row for row in files.values() if row["path"].endswith("/meta.csv")]
    if not metadata:
        raise SkipDataset("MLAAD vi: không có meta.csv để nhóm theo câu/người nguồn.")
    grouped: dict[str, list[RemoteFile]] = defaultdict(list)
    records: dict[str, dict[str, Any]] = {}
    for meta in metadata:
        payload = client.get_bytes(_url(repo, revision, meta["path"]), limit=10_000_000)
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")), delimiter="|")
        if not reader.fieldnames or "original_file" not in reader.fieldnames:
            raise SkipDataset(
                "MLAAD vi: meta.csv thiếu original_file; không thể bảo toàn câu nguồn."
            )
        model = PurePosixPath(meta["path"]).parent.name
        for row in reader:
            raw = row.get("path", "")
            candidate = raw.replace("\\", "/").lstrip("./")
            if not candidate.startswith("fake/vi/"):
                candidate = f"fake/vi/{model}/{PurePosixPath(candidate).name}"
            item = files.get(candidate)
            if not item or not candidate.endswith(".wav"):
                continue
            original = row.get("original_file", "").strip()
            if not original:
                raise SkipDataset("MLAAD vi: có câu thiếu original_file; không lấy mẫu ngẫu nhiên.")
            # Group the same source sentence across ALL TTS systems together.
            key = original
            grouped[key].append(
                RemoteFile(_url(repo, revision, candidate), candidate, item["size"])
            )
            records[candidate] = {**row, "path": candidate, "source_group": key, "tts": model}
    if {path for path in files if path.endswith(".wav")} != set(records):
        raise SkipDataset(
            "MLAAD vi: meta.csv không bao phủ mọi WAV; không chọn nhóm thiếu câu nguồn."
        )
    if not grouped:
        raise SkipDataset("MLAAD vi: metadata không khớp danh sách WAV trên nguồn.")
    selected, chosen = sample_groups(
        grouped,
        sum(f.size for group in grouped.values() for f in group)
        if subset == "full"
        else max(0, dataset.budget_bytes - sum(m["size"] for m in metadata) - 10_000_000),
        seed,
    )
    expected = {PurePosixPath(item["path"]).parent.name for item in metadata}
    present = {PurePosixPath(file.path).parent.name for file in chosen}
    if not selected or present != expected:
        raise SkipDataset("MLAAD vi: ngân sách không chứa được nhóm câu nguồn có đủ các hệ TTS.")

    def execute(dest: Path, download_client: Client) -> None:
        for file in chosen:
            download_client.download(file, safe_path(dest, file.path))
        for meta in metadata:
            download_client.download(
                RemoteFile(_url(repo, revision, meta["path"]), meta["path"], meta["size"]),
                safe_path(dest, meta["path"]),
            )
        _manifest(dest, [records[file.path] for file in chosen])

    return Plan(
        dataset,
        chosen,
        sum(file.size for file in chosen) + sum(m["size"] for m in metadata) + 10_000_000,
        revision=revision,
        groups=selected,
        notes=[
            f"Seed {seed}; câu original_file giữ cùng nhóm qua mọi hệ TTS; reference_speaker trong manifest."
        ],
        execute=execute,
    )


def _parquet_audio(dataset: Dataset, client: Client, seed: int, subset: str) -> Plan:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise SkipDataset("Cần cài pyarrow: uv sync --group data.") from exc
    repo = AUDIO_REPOS[dataset.name]
    revision, entries = client.hf_files(repo)
    shards = [row for row in entries if row["path"].endswith(".parquet")]
    if not shards:
        raise SkipDataset(f"{dataset.name}: không có parquet trên nguồn.")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    regions: dict[str, str] = {}
    shard_info: dict[str, tuple[RemoteFile, list[int]]] = {}
    for shard in shards:
        remote = RemoteFile(_url(repo, revision, shard["path"]), shard["path"], shard["size"])
        with client.remote_file(remote.url, remote.size) as handle:
            parquet = pq.ParquetFile(handle)
            columns = parquet.schema_arrow.names
            subject_column = next(
                (
                    key
                    for key in ("speakerID", "speaker_id", "speaker", "subject_id")
                    if key in columns
                ),
                None,
            )
            if subject_column is None or "audio" not in columns:
                raise SkipDataset(
                    f"{dataset.name}: parquet thiếu speaker ID hoặc audio; không chọn shard thay người."
                )
            if dataset.name == "vimd" and "region" not in columns:
                raise SkipDataset("ViMD: parquet thiếu region để cân bằng ba miền.")
            metadata_columns = [subject_column] + [
                key
                for key in ("region", "filename", "path", "gender", "text", "label", "source")
                if key in columns
            ]
            costs = []
            for group_index in range(parquet.num_row_groups):
                footer = parquet.metadata.row_group(group_index)
                costs.append(
                    sum(footer.column(i).total_compressed_size for i in range(footer.num_columns))
                )
                table = parquet.read_row_group(group_index, columns=metadata_columns).to_pylist()
                for index, row in enumerate(table):
                    subject = str(row.get(subject_column, "")).strip()
                    if not subject or subject == "None":
                        raise SkipDataset(f"{dataset.name}: metadata có người nói không xác định.")
                    row.update(
                        {
                            "subject_id": subject,
                            "shard": remote.path,
                            "row_group": group_index,
                            "row": index,
                        }
                    )
                    groups[subject].append(row)
                    if dataset.name == "vimd":
                        region = row.get("region")
                        if region not in ("North", "Central", "South"):
                            raise SkipDataset("ViMD: region khác North/Central/South.")
                        if subject in regions and regions[subject] != region:
                            raise SkipDataset("ViMD: một speakerID thuộc nhiều miền.")
                        regions[subject] = region
            shard_info[remote.path] = remote, costs
    names = sorted(groups)
    random.Random(seed).shuffle(names)
    metadata_allowance = 10_000_000
    cap = (
        dataset.budget_bytes
        if subset == "small"
        else sum(row["size"] for row in shards) * 3 + metadata_allowance
    )
    selected: list[str] = []
    used_groups: set[tuple[str, int]] = set()
    transfer_cost = 0

    def consider(batch: list[str]) -> bool:
        nonlocal transfer_cost
        needed = {(row["shard"], row["row_group"]) for subject in batch for row in groups[subject]}
        additional = needed - used_groups
        cost = sum(shard_info[path][1][index] for path, index in additional)
        # Compressed rowgroup + decoded audio output conservative factor; no shard cache.
        if (transfer_cost + cost) * 3 + metadata_allowance > cap:
            return False
        transfer_cost += cost
        used_groups.update(needed)
        selected.extend(batch)
        return True

    if dataset.name == "vimd":
        by_region = {
            region: [s for s in names if regions[s] == region]
            for region in ("North", "Central", "South")
        }
        if any(not group for group in by_region.values()):
            raise SkipDataset("ViMD: không có metadata đủ ba miền.")
        for batch in zip(*by_region.values(), strict=False):
            consider(list(batch))
    else:
        for subject in names:
            consider([subject])
    if not selected:
        raise SkipDataset(
            f"{dataset.name}: rowgroup quá lớn cho ngân sách; không thể lấy trọn người/ba miền."
        )
    rows = [row for subject in selected for row in groups[subject]]
    by_group: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_group[(row["shard"], row["row_group"])].append(row)

    output_allowance = transfer_cost * 2

    def execute(dest: Path, download_client: Client) -> None:
        manifest: list[dict[str, Any]] = []
        prepared_outputs: list[tuple[Path, bytes]] = []
        output_bytes = 0
        # Validate the complete selected population before writing its first audio.
        # Encoded audio can expand beyond a conservative compressed-rowgroup estimate.
        for (path, group_index), records in sorted(by_group.items()):
            remote = shard_info[path][0]
            with download_client.remote_file(remote.url, remote.size) as handle:
                audio = (
                    pq.ParquetFile(handle)
                    .read_row_group(group_index, columns=["audio"])
                    .to_pylist()
                )
            for row in records:
                payload = audio[row["row"]]["audio"]
                if not isinstance(payload, dict) or not isinstance(payload.get("bytes"), bytes):
                    raise SkipDataset(
                        f"{dataset.name}: audio không chứa bytes, cần adapter URL riêng."
                    )
                blob = payload["bytes"]
                output_bytes += len(blob)
                if output_bytes > output_allowance:
                    raise SkipDataset(
                        f"{dataset.name}: audio vượt chi phí đã preflight; "
                        "chưa ghi file, không cắt nhóm người nói."
                    )
                source = str(payload.get("path") or row.get("filename") or "audio.wav")
                basename = PurePosixPath(source.replace("\\", "/")).name
                filename = f"audio/{row['subject_id']}/{Path(path).stem}_{group_index}_{row['row']}_{basename}"
                prepared_outputs.append((safe_path(dest, filename), blob))
                manifest.append(
                    {**row, "path": filename, "original_path": source, "size": len(blob)}
                )
        manifest_payload = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
        if len(manifest_payload) > metadata_allowance:
            raise SkipDataset(
                f"{dataset.name}: manifest vượt phần dự phòng metadata; chưa ghi audio."
            )
        check_disk(dest, output_bytes + len(manifest_payload))
        for filename, blob in prepared_outputs:
            check_disk(dest, len(blob) + len(manifest_payload))
            _atomic_bytes(filename, blob)
        check_disk(dest, len(manifest_payload))
        _atomic_bytes(dest / "selected_manifest.json", manifest_payload)

    return Plan(
        dataset,
        [],
        peak_bytes=transfer_cost * 3 + metadata_allowance,
        revision=revision,
        groups=selected,
        notes=[
            "Shards nguồn: " + ", ".join(sorted({p for p, _ in used_groups})),
            f"Seed {seed}; metadata tất cả shards, giữ trọn speakerID; HTTP range rowgroups.",
            "ViMD giữ số người bằng nhau ba miền."
            if dataset.name == "vimd"
            else "Bảo toàn nhóm người nói.",
        ],
        execute=execute,
    )


def _vispoof(dataset: Dataset, client: Client, seed: int, subset: str) -> Plan:
    try:
        import gdown
    except ImportError as exc:
        raise SkipDataset("ViSpoofDB cần gdown: uv sync --group data.") from exc
    folder = "https://drive.google.com/drive/folders/1NZWOJi8g9nLfId1fSTkEc9Ay18P0c2LR"
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            listing = gdown.download_folder(
                url=folder, skip_download=True, quiet=True, use_cookies=False
            )
    except Exception:
        raise SkipDataset(
            "ViSpoofDB: gdown không liệt kê được toàn bộ Drive; kiểm tra quyền/quota (không tải danh sách bị cắt)."
        ) from None
    if not listing:
        raise SkipDataset(
            "ViSpoofDB: không đọc được danh sách Drive; cần quyền truy cập public hoặc Google cookie theo gdown."
        )

    def verified_file(item: Any) -> RemoteFile:
        relative = str(item.path).replace("\\", "/")
        # Reject Drive entries that escape the dataset before any download.
        safe_path(Path("."), relative)
        url = (
            "https://drive.usercontent.google.com/download?id="
            + quote(item.id, safe="")
            + "&export=download&authuser=0&confirm=t"
        )
        size = client.head_size(url)
        if size <= 0:
            raise SkipDataset("ViSpoofDB: HEAD không xác minh được byte size.")
        return RemoteFile(url, relative, size)

    # HEAD only: concurrent metadata calls avoid thousands of sequential waits.
    with ThreadPoolExecutor(max_workers=8) as pool:
        chosen = list(pool.map(verified_file, listing))
    total = sum(file.size for file in chosen)
    peak = total + 10_000_000
    if subset == "small" and peak > dataset.budget_bytes:
        raise SkipDataset(
            "ViSpoofDB: toàn bộ test có kích thước xác minh vượt ngân sách small; "
            "không cắt ngẫu nhiên file mất thông tin người nói."
        )

    def execute(dest: Path, download_client: Client) -> None:
        for file in chosen:
            download_client.download(file, safe_path(dest, file.path))
        _manifest(
            dest,
            [
                {
                    "path": file.path,
                    "size": file.size,
                    "subject_id": None,
                    "split_policy": "test_only",
                    "source_file_id": item.id,
                }
                for item, file in zip(listing, chosen, strict=True)
            ],
        )

    return Plan(
        dataset,
        chosen,
        peak,
        groups=["vispoofdb_test_only"],
        notes=[
            "Giữ toàn bộ ViSpoofDB làm test; audio_*.wav không có speaker ID, không chia calib/train.",
            "Danh sách gdown đầy đủ + kích thước HEAD public từng file; không sao chép code nguồn.",
            f"Seed {seed}; toàn bộ test không lấy mẫu.",
        ],
        execute=execute,
    )


def prepare(dataset: Dataset, client: Client, seed: int, subset: str) -> Plan:
    """Chuẩn bị nguồn, nhóm mẫu và chi phí; chưa tải bất kỳ audio nào."""
    if dataset.gated and not client.token:
        raise SkipDataset(
            f"{dataset.name}: cần HF_TOKEN sau khi đồng ý điều khoản tại {dataset.source}; "
            "tạo token read ở https://huggingface.co/settings/tokens."
        )
    adapters = {
        "vivos": _vivos,
        "mlaad_vi": _mlaad,
        "vimd": _parquet_audio,
        "vsasv": _parquet_audio,
        "vispoofdb": _vispoof,
    }
    return adapters[dataset.name](dataset, client, seed, subset)
