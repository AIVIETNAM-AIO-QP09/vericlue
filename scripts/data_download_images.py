"""Nguồn ảnh/video DATA-01; tải tập con theo video gốc, giữ provenance."""

from __future__ import annotations

import csv
import io
import json
import random
import re
import tarfile
from pathlib import Path
from urllib.parse import quote, urlencode

from data_download_core import (
    Client,
    Dataset,
    Plan,
    RemoteFile,
    SkipDataset,
    check_disk,
    safe_path,
    sample_groups,
)

KAGGLE = "https://www.kaggle.com/api/v1/datasets"
HF = "https://huggingface.co/datasets"
KAGGLE_REPOS = {
    "zalo2022": "hlly34/liveness-detection-zalo-2022",
    "fas_vn": "maihongtng/face-anti-spoofing",
    "rtfs10k": "stplusplus/rtfs-10k",
}
HF_REPOS = {
    "wilddeepfake": "xingjunm/WildDeepfake",
    "vicocktail": "nguyenvulebinh/ViCocktail",
    "vn_celeb_faces": "fptudsc/face-celeb-vietnamese",
}


def _kaggle_files(repo: str, client: Client) -> list[dict]:
    """Đọc hết danh sách file, không tải media hoặc ghi credentials."""
    if not client.kaggle_auth:
        raise SkipDataset(
            "Thiếu Kaggle credentials: đặt KAGGLE_USERNAME/KAGGLE_KEY hoặc "
            "~/.kaggle/kaggle.json; tạo API key trong Kaggle Settings → API."
        )
    items: list[dict] = []
    token = ""
    seen: set[str] = set()
    for _ in range(2000):
        query = urlencode({"pageSize": 200, **({"pageToken": token} if token else {})})
        data = client.json(f"{KAGGLE}/list/{repo}?{query}", auth=client.kaggle_auth)
        items.extend(data.get("datasetFiles", []))
        token = data.get("nextPageToken", "")
        if not token:
            return items
        if token in seen:
            raise SkipDataset("Kaggle trả token phân trang lặp; chưa có inventory đầy đủ.")
        seen.add(token)
    raise SkipDataset("Kaggle inventory quá nhiều trang; không lập kế hoạch thiếu file.")


def _kaggle_remote(repo: str, item: dict) -> RemoteFile:
    path = item["name"]
    return RemoteFile(
        f"{KAGGLE}/download/{repo}/{quote(path, safe='')}", path, int(item["totalBytes"])
    )


def _csv_rows(file: RemoteFile, client: Client) -> list[dict[str, str]]:
    raw = client.get_bytes(file.url, limit=5_000_000, auth=client.kaggle_auth)
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))


def _source_video(path: str) -> str | None:
    """Tên RTFS chứa YouTube ID 11 ký tự trước mốc thời gian."""
    stem = Path(path).stem
    for prefix in ("inswapper_", "uniface_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix) :]
    match = re.match(r"([A-Za-z0-9_-]{11})_\d+_\d+(?:_|$)", stem)
    return match.group(1) if match else None


def _prepare_rtfs(dataset: Dataset, client: Client, seed: int, subset: str) -> Plan:
    repo = KAGGLE_REPOS[dataset.name]
    inventory = _kaggle_files(repo, client)
    files = [_kaggle_remote(repo, item) for item in inventory]
    metadata = [file for file in files if file.path.endswith(".csv")]
    if {Path(file.path).name for file in metadata} != {
        "videos.csv",
        "photos.csv",
        "inswapper.csv",
        "uniface.csv",
    }:
        raise SkipDataset("RTFS thiếu CSV video/generator/photo để giữ provenance.")
    groups: dict[str, list[RemoteFile]] = {}
    for file in files:
        if not file.path.endswith(".mp4"):
            continue
        original = _source_video(file.path)
        if not original:
            raise SkipDataset("RTFS có filename chưa xác định được video gốc.")
        groups.setdefault(original, []).append(file)
    if any(
        not any(file.path.startswith("original_videos/") for file in group)
        or not any(file.path.startswith(("inswapper/", "uniface/")) for file in group)
        for group in groups.values()
    ):
        raise SkipDataset("RTFS có nhóm nguồn thiếu video thật/fake ghép cặp; không tải cặp thiếu.")
    if subset == "full":
        chosen, selected = sorted(groups), files
    else:
        budget = dataset.budget_bytes - sum(file.size for file in metadata)
        chosen, selected = sample_groups(groups, budget, seed)
        target_groups: list[str] = []
        target_files: list[RemoteFile] = []
        target_fakes = 0
        for group in chosen:
            target_groups.append(group)
            target_files.extend(groups[group])
            target_fakes += sum(
                file.path.startswith(("inswapper/", "uniface/")) for file in groups[group]
            )
            if target_fakes >= 1000:
                break
        chosen, selected = target_groups, target_files + metadata
    if not chosen:
        raise SkipDataset("RTFS không có nhóm video đầy đủ vừa ngân sách small.")
    fake_count = sum(file.path.startswith(("inswapper/", "uniface/")) for file in selected)
    real_count = sum(file.path.startswith("original_videos/") for file in selected)
    if not real_count or not fake_count:
        raise SkipDataset("RTFS subset thiếu cặp video thật và fake.")
    # Metadata is tiny and belongs in preflight: no video is downloaded here.
    metadata_rows = {Path(file.path).name: _csv_rows(file, client) for file in metadata}
    plan = Plan(
        dataset,
        selected,
        sum(file.size for file in selected),
        notes=[
            "Nhóm theo YouTube video ID, giữ mọi clip thật/fake trong nhóm được chọn.",
            f"Inventory chọn {real_count} video thật và {fake_count} video fake; "
            "mục tiêu khoảng 1.000 fake, không cắt bớt nhóm khi vượt mục tiêu.",
            "Gồm cả inswapper và uniface; không phải toàn bộ RTFS là inswapper.",
            "YouTube ID là video gốc, không phải subject_id. CSV giữ donor photo "
            "và source để DATA-03 nối các nhóm trước khi chia theo người.",
            f"CSV metadata: {', '.join(metadata_rows)}.",
        ],
        groups=chosen,
    )
    return plan


def _prepare_fas_zip(dataset: Dataset, client: Client, subset: str) -> Plan:
    """Giữ ZIP toàn bộ FAS-VN để tránh hàng nghìn request ảnh riêng."""
    if not client.kaggle_auth:
        raise SkipDataset("FAS-VN cần KAGGLE_USERNAME/KAGGLE_KEY hoặc ~/.kaggle/kaggle.json.")
    repo = KAGGLE_REPOS[dataset.name]
    metadata = client.json(f"{KAGGLE}/view/{repo}", auth=client.kaggle_auth)
    version = metadata.get("currentVersionNumber")
    if not isinstance(version, int) or version < 1:
        raise SkipDataset("FAS-VN không công bố version để ghim archive tải tiếp.")
    url = f"{KAGGLE}/download/{repo}?{urlencode({'datasetVersionNumber': version})}"
    size = client.head_size(url)
    if size <= 0:
        raise SkipDataset("FAS-VN không xác minh được kích thước ZIP trước preflight.")
    if subset == "small" and size > dataset.budget_bytes:
        raise SkipDataset("ZIP FAS-VN vượt ngân sách small; không tải khi thiếu dung lượng.")
    remote = RemoteFile(url, "face-anti-spoofing.zip", size)
    return Plan(
        dataset,
        [remote],
        size,
        revision=f"kaggle-version-{version}",
        notes=[
            "Small = full: tải một ZIP toàn bộ FAS-VN, không chọn ngẫu nhiên ảnh.",
            "Giữ nguyên ZIP, không giải nén/cache thêm bản sao; tải tiếp dùng version ghim.",
            f"ZIP đã xác minh HTTP size {size} bytes; byte ZIP khác tổng ảnh giải nén.",
            "Nguồn chưa có subject_id đáng tin; UUID filename không được coi là người. "
            "DATA-03 phải xác minh danh tính trước khi chia theo người.",
        ],
    )


def _prepare_kaggle(dataset: Dataset, client: Client, subset: str) -> Plan:
    repo = KAGGLE_REPOS[dataset.name]
    inventory = _kaggle_files(repo, client)
    files = [_kaggle_remote(repo, item) for item in inventory]
    if dataset.name == "zalo2022" and subset == "small":
        # Only labeled training data; test labels are not available.
        files = [
            file
            for file in files
            if "train" in file.path.lower() or file.path.lower().endswith((".csv", ".json", ".txt"))
        ]
        if not any(file.path.lower().endswith(".mp4") for file in files):
            raise SkipDataset("Không tìm được video train Zalo có nhãn trong inventory.")
    peak = sum(file.size for file in files)
    if subset == "small" and peak > dataset.budget_bytes:
        raise SkipDataset(
            "Bộ Kaggle vượt ngân sách small; không chọn ảnh ngẫu nhiên thiếu ID người."
        )
    return Plan(
        dataset,
        files,
        peak,
        notes=[
            "Tải file lẻ, giữ đường dẫn/nhãn gốc; không tải ZIP full và giải nén trùng.",
            "Chưa có subject_id đáng tin: DATA-03 phải xác minh danh tính trước "
            "khi chia theo người; filename/UUID không được tự coi là identity.",
        ],
    )


def _hf_remote(repo: str, revision: str, item: dict) -> RemoteFile:
    path = item["path"]
    lfs = item.get("lfs") or {}
    digest = lfs.get("oid") or lfs.get("sha256")
    if digest and digest.startswith("sha256:"):
        digest = digest.removeprefix("sha256:")
    return RemoteFile(
        f"{HF}/{repo}/resolve/{revision}/{quote(path)}", path, int(item["size"]), digest
    )


def _prepare_celeb(dataset: Dataset, client: Client) -> Plan:
    repo = HF_REPOS[dataset.name]
    revision, inventory = client.hf_files(repo)
    files = [
        _hf_remote(repo, revision, item) for item in inventory if item["path"].endswith(".parquet")
    ]
    if not files:
        raise SkipDataset("HF Vietnamese Celebrity Faces không còn parquet đã xác minh.")
    plan = Plan(
        dataset,
        files,
        sum(file.size for file in files),
        revision=revision,
        notes=[
            "Giữ nguyên parquet: cột image chứa ảnh, label là tên người; "
            "không giải nén thành bản sao và không tự chia train/test.",
            "HF fptudsc ghi Apache-2.0; Kaggle nguồn gốc duongtran1909 ghi Unknown. "
            "Giấy phép nguồn gốc chưa rõ — không phân phối lại.",
        ],
    )

    def download_and_index(dest: Path, downloader: Client) -> None:
        import pyarrow.parquet as pq

        names: set[str] = set()
        for file in files:
            path = safe_path(dest, file.path)
            downloader.download(file, path)
            labels = pq.read_table(path, columns=["label"]).column("label").to_pylist()
            if any(not isinstance(label, str) or not label.strip() for label in labels):
                raise SkipDataset("VN Celebrity: thiếu nhãn người, không tạo ID giả.")
            names.update(labels)
        plan.groups[:] = sorted(names)
        note = f"Đã xác minh {len(names)} nhãn người từ cột label của parquet."
        if note not in plan.notes:
            plan.notes.append(note)

    plan.execute = download_and_index
    plan.peak_bytes += 1_000_000
    return plan


def _prepare_wild(dataset: Dataset, client: Client, seed: int, subset: str) -> Plan:
    repo = HF_REPOS[dataset.name]
    revision, inventory = client.hf_files(repo)
    archives = [
        _hf_remote(repo, revision, item) for item in inventory if item["path"].endswith(".tar.gz")
    ]
    if not archives:
        raise SkipDataset("WildDeepfake không có tar video đã xác minh.")
    if subset == "full":
        files = archives
    else:
        # Retain complete archives and all video frames; balance real/fake train.
        files = []
        rng = random.Random(seed)
        for category in ("fake_train", "real_train"):
            candidates = sorted(
                (file for file in archives if f"/{category}/" in file.path),
                key=lambda file: file.path,
            )
            rng.shuffle(candidates)
            remaining = dataset.budget_bytes * 9 // 20
            for file in candidates:
                if file.size <= remaining:
                    files.append(file)
                    remaining -= file.size
        if not all(
            any(f"/{kind}/" in file.path for file in files) for kind in ("fake_train", "real_train")
        ):
            raise SkipDataset("Không có đủ archive real/fake WildDeepfake trong ngân sách.")
    plan = Plan(
        dataset,
        files,
        sum(file.size for file in files),
        revision=revision,
        notes=[
            "Lưu archive nguyên vẹn, giữ mọi frame của mọi video trong archive; không giải nén trùng.",
            "Nhóm frame theo đường dẫn video bên trong tar; đây là source_video_id, "
            "không khẳng định là subject_id. DATA-03 phải nối danh tính trước khi chia người.",
        ],
    )

    def inspect_archives(dest: Path, _client: Client) -> None:
        groups: set[str] = set()
        records: list[dict] = []
        origin_archives: dict[str, set[str]] = {}
        origin_splits: dict[str, set[str]] = {}
        for file in files:
            archive = safe_path(dest, file.path)
            _client.download(file, archive)
            with tarfile.open(archive, "r:*") as stream:
                for member in stream:
                    if member.isfile() and member.name.lower().endswith((".png", ".jpg", ".jpeg")):
                        # A source group never includes archive name: preserve cross-shard reuse.
                        safe_path(dest, member.name)
                        group = str(Path(member.name).parent).replace("\\", "/")
                        if group in (".", ""):
                            raise SkipDataset("WildDeepfake frame thiếu thư mục video gốc.")
                        split = Path(file.path).parent.name
                        source_id = f"{split}::{group}"
                        groups.add(source_id)
                        origin_archives.setdefault(group, set()).add(file.path)
                        origin_splits.setdefault(group, set()).add(split)
                        records.append(
                            {
                                "archive": file.path,
                                "member": member.name,
                                "source_video_id": source_id,
                                "video_origin_id": group,
                                "source_split": split,
                                "speaker_id": "",
                                "subject_id": "",
                            }
                        )
        if not groups:
            raise SkipDataset("WildDeepfake archives không chứa nhóm frame video có thể xác minh.")
        _write_manifest(dest, records, plan)
        duplicate_origins = sorted(
            origin for origin, archives in origin_archives.items() if len(archives) > 1
        )
        ambiguous_origins = sorted(
            origin for origin, splits in origin_splits.items() if len(splits) > 1
        )
        duplicate_note = (
            f"Kiểm tra parent video thực tế: {len(duplicate_origins)} video_origin_id xuất hiện "
            "trong nhiều archive đã tải; archive name không thuộc ID nhóm. "
            f"{len(ambiguous_origins)} parent ID có nhiều source_split, giữ source_split riêng "
            "vì chưa có ánh xạ danh tính xuyên real/fake hoặc train/test."
        )
        if duplicate_note not in plan.notes:
            plan.notes.append(duplicate_note)
        if duplicate_origins:
            plan.notes.append("Parent video ở nhiều archive: " + ", ".join(duplicate_origins))
        plan.groups[:] = sorted(groups)
        plan.notes.append(
            f"Đã kiểm tra archive: {len(groups)} nhóm video, không lấy frame ngẫu nhiên."
        )

    plan.peak_bytes += max(1_048_576, plan.peak_bytes // 10)
    if subset == "small" and plan.peak_bytes > dataset.budget_bytes:
        raise SkipDataset("Ngân sách WildDeepfake không đủ cho archive và manifest provenance.")
    plan.execute = inspect_archives
    return plan


def _write_manifest(dest: Path, records: list[dict], plan: Plan) -> None:
    """Ghi member → video gốc vào data, giới hạn theo preflight đã duyệt."""
    limit = plan.peak_bytes - sum(file.size for file in plan.files)
    encoded = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records).encode(
        "utf-8"
    )
    output = io.StringIO(newline="")
    columns = [
        "archive",
        "member",
        "members",
        "sample_key",
        "video_origin_id",
        "source_video_id",
        "speaker_id",
        "subject_id",
        "source_split",
    ]
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        row = {column: record.get(column, "") for column in columns}
        row["members"] = json.dumps(record.get("members", []), ensure_ascii=False)
        writer.writerow(row)
    index_payload = output.getvalue().encode("utf-8")
    if len(encoded) + len(index_payload) > limit:
        raise SkipDataset(
            "Manifest/index provenance vượt ngân sách; giữ archive để lần sau kiểm tra."
        )
    check_disk(dest, len(encoded) + len(index_payload))
    dest.mkdir(parents=True, exist_ok=True)
    for name, payload in (("video_groups.jsonl", encoded), ("index.csv", index_payload)):
        check_disk(dest, len(payload))
        temporary = dest / f"{name}.part"
        temporary.write_bytes(payload)
        temporary.replace(dest / name)
    note = "video_groups.jsonl và index.csv giữ archive/member → video_origin_id; speaker/subject rỗng nếu nguồn không công bố."
    if note not in plan.notes:
        plan.notes.append(note)


def _prepare_vicocktail(dataset: Dataset, client: Client, seed: int, subset: str) -> Plan:
    repo = HF_REPOS[dataset.name]
    revision, inventory = client.hf_files(repo)
    archives = [
        _hf_remote(repo, revision, item) for item in inventory if item["path"].endswith(".tar")
    ]
    if subset == "full":
        files = archives
    else:
        candidates = {file.path: [file] for file in archives if "/avvn-train-" in file.path}
        _, files = sample_groups(candidates, dataset.budget_bytes * 9 // 10, seed)
    if not files:
        raise SkipDataset("ViCocktail không có candidate shard train vừa ngân sách.")
    archive_bytes = sum(file.size for file in files)
    plan = Plan(
        dataset,
        files,
        archive_bytes + max(1_048_576, archive_bytes // 10),
        revision=revision,
        notes=[
            "Candidate shards chọn có seed trong ngân sách; giữ mọi utterance và frame "
            "của các video gốc có mặt trong shard đã chọn, không lấy frame ngẫu nhiên.",
            "Phạm vi small giới hạn các candidate shard; một video gốc có thể có clip "
            "ở shard chưa tải. DATA-03 phải dùng source_video_id xuyên shard để tránh rò rỉ.",
            "sample_id bắt đầu bằng YouTube source video ID 11 ký tự; ID video không phải speaker_id.",
            "Lưu archive nguyên vẹn, không giải nén thành bản sao. Giấy phép chưa rõ — không phân phối lại.",
        ],
    )
    if subset == "small" and plan.peak_bytes > dataset.budget_bytes:
        raise SkipDataset("ViCocktail không đủ ngân sách cho archive và manifest provenance.")

    def download_and_index(dest: Path, downloader: Client) -> None:
        records: list[dict] = []
        originals: set[str] = set()
        for file in files:
            archive = safe_path(dest, file.path)
            downloader.download(file, archive)
            identities: dict[str, str] = {}
            speakers: dict[str, str] = {}
            samples: dict[str, list[str]] = {}
            with tarfile.open(archive, "r:*") as stream:
                for member in stream:
                    if not member.isfile():
                        continue
                    safe_path(dest, member.name)
                    key, extension = (
                        member.name.rsplit(".", 1) if "." in member.name else (member.name, "")
                    )
                    samples.setdefault(key, []).append(member.name)
                    if extension not in ("sample_id", "speaker_id", "speakerID"):
                        continue
                    if member.size > 4096:
                        raise SkipDataset("ViCocktail ID vượt giới hạn metadata.")
                    extracted = stream.extractfile(member)
                    if extracted is None:
                        raise SkipDataset("Không đọc được ViCocktail sample_id.")
                    sample_id = extracted.read().decode("utf-8").strip()
                    if extension != "sample_id":
                        if key in speakers and speakers[key] != sample_id:
                            raise SkipDataset(
                                "ViCocktail metadata speaker mâu thuẫn, không đoán người nói."
                            )
                        speakers[key] = sample_id
                        continue
                    match = re.fullmatch(r"([A-Za-z0-9_-]{11})_\d+_.*", sample_id)
                    if not match:
                        raise SkipDataset(
                            "ViCocktail sample_id không khớp source video đã xác minh."
                        )
                    identities[key] = match.group(1)
            for key, members in samples.items():
                if key not in identities:
                    raise SkipDataset("ViCocktail member thiếu sample_id; không bịa provenance.")
                original = identities[key]
                originals.add(original)
                records.append(
                    {
                        "archive": file.path,
                        "member": next(
                            (name for name in members if name.endswith((".video", ".mp4"))), ""
                        ),
                        "members": members,
                        "sample_key": key,
                        "source_video_id": original,
                        "video_origin_id": original,
                        "speaker_id": speakers.get(key, ""),
                        "subject_id": speakers.get(key, ""),
                        "source_split": "train"
                        if "/avvn-train-" in file.path
                        else Path(file.path).stem,
                    }
                )
        if not originals:
            raise SkipDataset("ViCocktail archive không có source video metadata.")
        _write_manifest(dest, records, plan)
        plan.groups[:] = sorted(originals)
        note = f"Đã xác minh {len(originals)} source video từ sample_id trong candidate shards."
        if note not in plan.notes:
            plan.notes.append(note)

    plan.execute = download_and_index
    return plan


def prepare(dataset: Dataset, client: Client, seed: int, subset: str) -> Plan:
    """Lập inventory và ngân sách; không tải media trước kiểm tra dung lượng."""
    if dataset.name == "rtfs10k":
        return _prepare_rtfs(dataset, client, seed, subset)
    if dataset.name == "fas_vn":
        return _prepare_fas_zip(dataset, client, subset)
    if dataset.name == "zalo2022":
        return _prepare_kaggle(dataset, client, subset)
    if dataset.name == "vn_celeb_faces":
        return _prepare_celeb(dataset, client)
    if dataset.name == "wilddeepfake":
        return _prepare_wild(dataset, client, seed, subset)
    if dataset.name == "vicocktail":
        return _prepare_vicocktail(dataset, client, seed, subset)
    if dataset.name == "celeba_spoof":
        raise SkipDataset(
            "CelebA-Spoof Drive gồm ZIP phân mảnh .001…; chưa xác minh HTTP Range "
            "và central-directory identity mapping. Không tải toàn archive trong small. "
            "Dùng gdown sau khi có inventory/dung lượng và mapping người được xác minh."
        )
    if dataset.name == "lavdf":
        if not client.token:
            raise SkipDataset(
                "LAV-DF cần HF_TOKEN (Read) và chấp nhận điều khoản tại "
                "https://huggingface.co/datasets/ControlNet/LAV-DF."
            )
        raise SkipDataset(
            "LAV-DF chỉ có tar 25,6 GB; chưa xác minh HTTP Range và metadata nối "
            "video thật/fake theo video gốc. Bỏ qua riêng bộ, không fallback tải full."
        )
    raise SkipDataset(f"Chưa có adapter ảnh/video cho {dataset.name}.")
