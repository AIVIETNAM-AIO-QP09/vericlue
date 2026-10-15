"""Bộ tải âm thanh DATA-01; chỉ metadata được đọc trước kiểm tra dung lượng."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import re
import shutil
import tarfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

from data_download_core import (
    Client,
    Dataset,
    DownloadError,
    Plan,
    RemoteFile,
    SkipDataset,
    check_disk,
    safe_extract_tar,
    safe_path,
    sample_groups,
)

HF = "https://huggingface.co/datasets"
VIMD_SMALL_SPEAKERS_PER_REGION = 4
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
            "giọng thật của ViSpoofDB lấy từ VIVOS — DATA-03 phải chia theo người xuyên hai bộ, chống rò rỉ người nói",
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
    wavs = {path for path in files if path.endswith(".wav")}
    excluded: dict[str, str] = {}
    for meta in metadata:
        payload = client.get_bytes(_url(repo, revision, meta["path"]), limit=10_000_000)
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")), delimiter="|")
        model = PurePosixPath(meta["path"]).parent.name
        if not reader.fieldnames or "original_file" not in reader.fieldnames:
            excluded.update(
                (path, "missing_original_file_column")
                for path in wavs
                if PurePosixPath(path).parent == PurePosixPath(meta["path"]).parent
            )
            continue
        for row in reader:
            raw = row.get("path") or ""
            candidate = raw.replace("\\", "/").lstrip("./")
            if not candidate.startswith("fake/vi/"):
                candidate = f"fake/vi/{model}/{PurePosixPath(candidate).name}"
            if candidate not in wavs or candidate in excluded:
                continue
            original = (row.get("original_file") or "").strip()
            if not original or original.casefold() in {"none", "null", "nan", "unknown"}:
                excluded[candidate] = "missing_original_file"
                records.pop(candidate, None)
                continue
            record = {**row, "path": candidate, "source_group": original, "tts": model}
            if candidate in records and records[candidate] != record:
                excluded[candidate] = "metadata_conflict"
                records.pop(candidate, None)
                continue
            records[candidate] = record
    for path in wavs - records.keys():
        excluded.setdefault(path, "no_metadata")
    for candidate, row in records.items():
        grouped[row["source_group"]].append(
            RemoteFile(_url(repo, revision, candidate), candidate, files[candidate]["size"])
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
    expected = {row["tts"] for row in records.values()}
    present = {PurePosixPath(file.path).parent.name for file in chosen}
    if not selected or present != expected:
        raise SkipDataset("MLAAD vi: ngân sách không chứa được nhóm câu nguồn có đủ các hệ TTS.")

    def execute(dest: Path, download_client: Client) -> None:
        def download_one(file: RemoteFile) -> None:
            download_client.download(file, safe_path(dest, file.path))

        with ThreadPoolExecutor(max_workers=8) as pool:
            for start in range(0, len(chosen), 8):
                list(pool.map(download_one, chosen[start : start + 8]))
        for meta in metadata:
            download_client.download(
                RemoteFile(_url(repo, revision, meta["path"]), meta["path"], meta["size"]),
                safe_path(dest, meta["path"]),
            )
        _manifest(dest, [records[file.path] for file in chosen])

    reasons: dict[str, int] = defaultdict(int)
    excluded_tts: dict[str, int] = defaultdict(int)
    for path, reason in excluded.items():
        reasons[reason] += 1
        excluded_tts[PurePosixPath(path).parent.name] += 1
    return Plan(
        dataset,
        chosen,
        sum(file.size for file in chosen) + sum(m["size"] for m in metadata) + 10_000_000,
        revision=revision,
        groups=selected,
        notes=[
            f"Seed {seed}; câu original_file giữ cùng nhóm qua mọi hệ TTS; reference_speaker trong manifest.",
            f"WAV nguồn {len(wavs)}; WAV có nhóm hợp lệ {len(records)}; bỏ {len(excluded)} WAV: "
            + json.dumps(dict(reasons), ensure_ascii=False),
            "WAV bị bỏ theo hệ TTS: " + json.dumps(dict(excluded_tts), ensure_ascii=False),
            "no_metadata: không có dòng meta.csv; không suy câu nguồn từ basename.",
            "DATA-03: kiểm trùng người xuyên bộ qua original_file và đường dẫn reference_speaker; "
            "reference là đường dẫn âm thanh tham chiếu, không tự tạo subject_id hoặc suy ID người.",
        ],
        execute=execute,
    )


def _parquet_footer(handle: Any, size: int) -> Any:
    """Read only the exact Parquet footer, avoiding the default 64-KiB audio tail."""
    import pyarrow.parquet as pq

    if size < 12:
        raise DownloadError("Parquet quá ngắn.")
    handle.seek(size - 8)
    trailer = handle.read(8)
    if len(trailer) != 8 or trailer[4:] != b"PAR1":
        raise DownloadError("Parquet footer không hợp lệ.")
    length = int.from_bytes(trailer[:4], "little")
    if not 0 < length <= min(size - 12, 16 * 1024 * 1024):
        raise DownloadError("Kích thước Parquet footer không hợp lệ.")
    handle.seek(size - 8 - length)
    footer = handle.read(length)
    if len(footer) != length:
        raise DownloadError("Parquet footer chưa đủ byte.")
    return pq.read_metadata(io.BytesIO(b"PAR1" + footer + trailer))


def _float32_wav(samples: Any, sample_rate: int) -> bytes:
    """Encode mono IEEE float32 WAV at the source rate, without resampling/clipping."""
    import numpy as np
    from scipy.io import wavfile

    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or sample_rate <= 0:
        raise DownloadError("VSASV: sampling_rate phải là số nguyên dương.")
    with np.errstate(over="ignore", invalid="ignore"):
        values = np.asarray(samples, dtype=np.float32)
    if values.ndim != 1 or not values.size or not np.isfinite(values).all():
        raise DownloadError("VSASV: waveform mono rỗng hoặc có giá trị không hữu hạn.")
    buffer = io.BytesIO()
    wavfile.write(buffer, sample_rate, values)
    return buffer.getvalue()


def _vsasv_receipt(path: Path, identity: str) -> dict[str, Any] | None:
    try:
        receipt = json.loads(
            path.with_name(path.name + ".verified.json").read_text(encoding="utf-8")
        )
        if receipt["identity"] != identity or path.stat().st_size != receipt["size"]:
            return None
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != receipt["sha256"]:
            return None
        if (
            not isinstance(receipt["sampling_rate"], int)
            or receipt["sampling_rate"] <= 0
            or not isinstance(receipt["n_samples"], int)
            or receipt["n_samples"] <= 0
        ):
            return None
        return receipt
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _vsasv(dataset: Dataset, client: Client, seed: int, subset: str) -> Plan:
    """VSASV label is a speaker identity; only verified bonafide/replay scope."""
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise SkipDataset("VSASV cần pyarrow: uv sync --all-packages --group data.") from exc
    repo = AUDIO_REPOS[dataset.name]
    revision, entries = client.hf_files(repo)
    shards = sorted(
        (item for item in entries if item["path"].endswith(".parquet")), key=lambda x: x["path"]
    )
    if not shards:
        raise SkipDataset("VSASV: không có Parquet trên nguồn.")

    def inspect(shard: dict[str, Any]) -> tuple[RemoteFile, Any, list[dict], list[tuple[int, int]]]:
        remote = RemoteFile(_url(repo, revision, shard["path"]), shard["path"], shard["size"])
        rows, costs = [], []
        with client.remote_file(remote.url, remote.size) as handle:
            metadata = _parquet_footer(handle, remote.size)
            columns = metadata.schema.to_arrow_schema().names
            if not {"file", "label", "utt_type", "audio"}.issubset(columns):
                return remote, metadata, [], []
            parquet = pq.ParquetFile(handle, metadata=metadata, pre_buffer=False, buffer_size=0)
            for group_index in range(metadata.num_row_groups):
                group = metadata.row_group(group_index)
                compressed = sum(
                    group.column(i).total_compressed_size for i in range(group.num_columns)
                )
                audio_columns = [
                    group.column(i)
                    for i in range(group.num_columns)
                    if group.column(i).path_in_schema == "audio.array.list.element"
                ]
                if len(audio_columns) != 1:
                    return remote, metadata, [], []
                costs.append((compressed, audio_columns[0].num_values * 4))
                table = parquet.read_row_group(
                    group_index, columns=["file", "label", "utt_type"], use_threads=False
                )
                rows.extend(
                    {**row, "row_group": group_index, "row": index}
                    for index, row in enumerate(table.to_pylist())
                )
        return remote, metadata, rows, costs

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_info: dict[str, tuple[RemoteFile, Any, list[tuple[int, int]]]] = {}
    excluded: dict[str, int] = defaultdict(int)
    total = 0
    paths: set[str] = set()
    with ThreadPoolExecutor(max_workers=8) as pool:
        for index, (remote, metadata, rows, costs) in enumerate(pool.map(inspect, shards), start=1):
            total += metadata.num_rows
            source_info[remote.path] = remote, metadata, costs
            if not costs:
                excluded["missing_required_columns"] += metadata.num_rows
                continue
            for row in rows:
                kind, subject, source = row.get("utt_type"), row.get("label"), row.get("file")
                if kind not in {"bonafide", "replay"}:
                    excluded[str(kind) if isinstance(kind, str) else "missing_utt_type"] += 1
                    continue
                if (
                    not isinstance(subject, str)
                    or re.fullmatch(r"id[0-9]{5}", subject) is None
                    or not isinstance(source, str)
                    or not source.startswith(subject + "/")
                ):
                    excluded["missing_or_inconsistent_speaker"] += 1
                    continue
                try:
                    safe_path(Path("."), source)
                except DownloadError:
                    excluded["unsafe_source_path"] += 1
                    continue
                if source in paths:
                    raise DownloadError("VSASV: file nguồn trùng; không ghi đè hoặc cắt nhóm.")
                paths.add(source)
                groups[subject].append(
                    {
                        **row,
                        "source_label": subject,
                        "subject_id": subject,
                        "source_group": subject,
                        "label": 0 if kind == "bonafide" else 1,
                        "shard": remote.path,
                    }
                )
            if index % 32 == 0 or index == len(shards):
                print(f"VSASV metadata: {index}/{len(shards)} shards; chưa tải audio.", flush=True)
    if not groups:
        raise SkipDataset("VSASV: không còn nhóm người có metadata hợp lệ.")
    names = sorted(groups)
    random.Random(seed).shuffle(names)
    # Reserve space for replay populations before filling with bonafide-only people.
    names = [s for s in names if any(r["utt_type"] == "replay" for r in groups[s])] + [
        s for s in names if all(r["utt_type"] != "replay" for r in groups[s])
    ]
    cap = (
        dataset.budget_bytes
        if subset == "small"
        else sum(item["size"] for item in shards) * 8 + 10_000_000
    )
    selected: list[str] = []
    used: set[tuple[str, int]] = set()
    compressed, float_bytes, row_count = 0, 0, 0
    metadata_allowance = 10_000_000
    metadata_cost = 0
    # Reserve manifests AND verified receipts; long paths are counted per row.
    overhead = {
        subject: sum(
            len(json.dumps(row, ensure_ascii=False).encode()) + 2 * len(row["file"].encode()) + 2048
            for row in records
        )
        for subject, records in groups.items()
    }
    for subject in names:
        batch = groups[subject]
        needed = {(row["shard"], row["row_group"]) for row in batch}
        additional = needed - used
        extra_compressed = sum(source_info[path][2][g][0] for path, g in additional)
        extra_float = sum(source_info[path][2][g][1] for path, g in additional)
        allowance = max(10_000_000, metadata_cost + overhead[subject])
        peak = (
            max((compressed + extra_compressed) * 3, float_bytes + extra_float)
            + (row_count + len(batch)) * 128
            + allowance
        )
        if peak <= cap:
            selected.append(subject)
            used.update(needed)
            compressed += extra_compressed
            float_bytes += extra_float
            row_count += len(batch)
            metadata_cost += overhead[subject]
            metadata_allowance = allowance
    if not selected:
        raise SkipDataset("VSASV: không đủ ngân sách để giữ trọn một nhóm người hợp lệ.")
    rows = [row for subject in selected for row in groups[subject]]
    by_group: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_group[(row["shard"], row["row_group"])].append(row)
    output_allowance = float_bytes + len(rows) * 128

    def execute(dest: Path, download_client: Client) -> None:
        manifest, used_bytes = [], 0
        receipt_bytes = 0
        for (shard, group_index), records in sorted(by_group.items()):
            remote, metadata, _ = source_info[shard]
            pending = []
            for row in records:
                filename = "audio/" + row["file"]
                target = safe_path(dest, filename)
                identity = hashlib.sha256(
                    json.dumps(
                        [revision, shard, group_index, row["row"], row["file"], "float32-wav-v1"]
                    ).encode()
                ).hexdigest()
                receipt = _vsasv_receipt(target, identity)
                if receipt is None:
                    pending.append((row, target, identity))
                else:
                    used_bytes += receipt["size"]
                    receipt_bytes += target.with_name(target.name + ".verified.json").stat().st_size
                    if receipt_bytes > metadata_allowance:
                        raise DownloadError("VSASV: biên nhận vượt dự phòng metadata.")
                    manifest.append(
                        {
                            **row,
                            "path": filename,
                            "original_path": row["file"],
                            **{k: receipt[k] for k in ("size", "sampling_rate", "n_samples")},
                        }
                    )
            if not pending:
                continue
            with download_client.remote_file(remote.url, remote.size) as handle:
                table = pq.ParquetFile(
                    handle, metadata=metadata, pre_buffer=False, buffer_size=0
                ).read_row_group(group_index, columns=["audio"], use_threads=False)
            for row, target, identity in pending:
                payload = table.column("audio")[row["row"]]
                if (
                    not payload.is_valid
                    or not payload["array"].is_valid
                    or not payload["sampling_rate"].is_valid
                ):
                    raise DownloadError(
                        "VSASV: audio hoặc sampling_rate thiếu; giữ file đã xác minh để tải tiếp."
                    )
                samples = payload["array"].values.to_numpy(zero_copy_only=False)
                rate = payload["sampling_rate"].as_py()
                blob = _float32_wav(samples, rate)
                used_bytes += len(blob)
                if used_bytes > output_allowance:
                    raise DownloadError("VSASV: audio vượt preflight; không cắt nhóm người.")
                receipt = {
                    "identity": identity,
                    "size": len(blob),
                    "sha256": hashlib.sha256(blob).hexdigest(),
                    "sampling_rate": rate,
                    "n_samples": len(samples),
                }
                receipt_payload = json.dumps(receipt).encode()
                receipt_bytes += len(receipt_payload)
                if receipt_bytes > metadata_allowance:
                    raise DownloadError("VSASV: biên nhận vượt dự phòng metadata.")
                check_disk(dest, len(blob) + metadata_allowance)
                _atomic_bytes(target, blob)
                _atomic_bytes(target.with_name(target.name + ".verified.json"), receipt_payload)
                manifest.append(
                    {
                        **row,
                        "path": "audio/" + row["file"],
                        "original_path": row["file"],
                        "size": len(blob),
                        "sampling_rate": rate,
                        "n_samples": len(samples),
                    }
                )
            del table
        if used_bytes > output_allowance:
            raise DownloadError("VSASV: output đã có vượt giới hạn preflight.")
        manifest.sort(key=lambda r: (r["shard"], r["row_group"], r["row"]))
        payload = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
        if len(payload) + receipt_bytes > metadata_allowance:
            raise DownloadError("VSASV: manifest và biên nhận vượt dự phòng metadata.")
        check_disk(dest, len(payload))
        _atomic_bytes(dest / "selected_manifest.json", payload)

    return Plan(
        dataset,
        [],
        max(compressed * 3, float_bytes) + len(rows) * 128 + metadata_allowance,
        revision=revision,
        groups=selected,
        notes=[
            f"Seed {seed}; ID người = label công bố, xác minh khớp thư mục file; giữ trọn nhóm hợp lệ xuyên shard.",
            f"Dòng nguồn {total}; hợp lệ {sum(map(len, groups.values()))}; loại {sum(excluded.values())}: "
            + json.dumps(dict(excluded), ensure_ascii=False),
            "Loại voice_conversion và adversarial_attack vì không xác minh được người nguồn — quyết định trưởng nhóm 16/10.",
            "Phạm vi DATA-01 chỉ bonafide + replay, kể cả khi yêu cầu full; full là toàn bộ phần hợp lệ này.",
            "WAV IEEE float32; giữ nguyên sampling_rate, không resample, không clipping; label manifest 0=thật/1=phát lại, source_label giữ mã người gốc.",
            f"Range rowgroups dự kiến {compressed} bytes mạng (gồm metadata cột); WAV upper bound {output_allowance} bytes; không cache parquet đĩa.",
            "DATA-03: kiểm trùng người xuyên bộ VSASV ↔ VIVOS/ViMD; subject_id chỉ là mã nội bộ VSASV, chưa phải danh tính xuyên bộ.",
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
    for shard_index, shard in enumerate(shards, start=1):
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
        if dataset.name == "vimd" and (shard_index % 10 == 0 or shard_index == len(shards)):
            print(f"ViMD metadata: {shard_index}/{len(shards)} shards; chưa tải audio.", flush=True)
    names = sorted(groups)
    random.Random(seed).shuffle(names)
    metadata_allowance = 10_000_000
    bounded_vimd = dataset.name == "vimd" and subset == "small"
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
        if not bounded_vimd and (transfer_cost + cost) * 3 + metadata_allowance > cap:
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
        if bounded_vimd:
            # Four disjoint sets in DATA-03 need at least four speakers per region.
            per_region = min(
                VIMD_SMALL_SPEAKERS_PER_REGION, *(len(group) for group in by_region.values())
            )
            for index in range(per_region):
                consider([by_region[region][index] for region in ("North", "Central", "South")])
        else:
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

    output_allowance = cap - metadata_allowance if bounded_vimd else transfer_cost * 2
    if output_allowance <= 0:
        raise SkipDataset("ViMD: ngân sách không đủ phần dự phòng metadata và audio.")
    if bounded_vimd:
        print(
            f"ViMD: {len(selected) // 3} người/miền, trọn mọi clip; Range rowgroups dự kiến {transfer_cost / 1e9:.3f} GB mạng, không cache đĩa.",
            flush=True,
        )

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
        peak_bytes=output_allowance + metadata_allowance
        if bounded_vimd
        else transfer_cost * 3 + metadata_allowance,
        revision=revision,
        groups=selected,
        notes=[
            "Shards nguồn: " + ", ".join(sorted({p for p, _ in used_groups})),
            f"Range rowgroups: dự kiến {transfer_cost} bytes mạng; không lưu parquet/cache trên đĩa.",
            f"Ngân sách audio output {output_allowance} bytes + metadata {metadata_allowance} bytes; xác minh toàn bộ trước ghi.",
            f"Seed {seed}; metadata tất cả shards, giữ trọn speakerID; HTTP range rowgroups.",
            "ViMD giữ số người bằng nhau ba miền, small tối đa 4 người/miền để DATA-03 chia bốn tập."
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
        network_context = (
            client.measured_network() if hasattr(client, "measured_network") else nullcontext()
        )
        with network_context, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
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
        chosen = []
        for index, file in enumerate(pool.map(verified_file, listing), start=1):
            chosen.append(file)
            if index % 1000 == 0 or index == len(listing):
                print(f"ViSpoofDB HEAD: {index}/{len(listing)} file; chưa tải audio.", flush=True)
    if len({file.path.casefold() for file in chosen}) != len(chosen):
        raise SkipDataset(
            "ViSpoofDB: đường dẫn Drive bị trùng; không tải đồng thời file cùng đích."
        )
    total = sum(file.size for file in chosen)
    peak = total + 10_000_000
    if subset == "small" and peak > dataset.budget_bytes:
        raise SkipDataset(
            "ViSpoofDB: toàn bộ test có kích thước xác minh vượt ngân sách small; "
            "không cắt ngẫu nhiên file mất thông tin người nói."
        )

    def execute(dest: Path, download_client: Client) -> None:
        # Resolve and validate all destinations serially before workers create dirs.
        destinations = {file.path: safe_path(dest, file.path) for file in chosen}

        def download_one(file: RemoteFile) -> None:
            download_client.download(file, destinations[file.path])

        with ThreadPoolExecutor(max_workers=8) as pool:
            # Only queue one batch: failures stop without scheduling thousands more.
            for start in range(0, len(chosen), 8):
                for _ in pool.map(download_one, chosen[start : start + 8]):
                    pass
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
            "giọng thật của ViSpoofDB lấy từ VIVOS — DATA-03 phải chia theo người xuyên hai bộ, chống rò rỉ người nói",
            "Danh sách gdown đầy đủ + kích thước HEAD public từng file; không sao chép code nguồn.",
            f"Seed {seed}; toàn bộ test không lấy mẫu.",
            f"Drive liệt kê {len(chosen)} file; dùng số file tải thực, không dùng số mẫu README thay cho kiểm kê.",
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
        "vsasv": _vsasv,
        "vispoofdb": _vispoof,
    }
    return adapters[dataset.name](dataset, client, seed, subset)
