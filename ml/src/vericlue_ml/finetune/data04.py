"""Hàm thuần dùng chung cho tinh chỉnh GenD trên Kaggle/Colab (FACE-04): chia tập, cổng lộ đề, manifest.

KHÔNG có công cụ tạo giả và KHÔNG lập kế hoạch tạo giả: nhóm không tự tạo deepfake người thật (quyết
định trưởng nhóm 19/10). Mẫu giả chỉ lấy từ bộ nghiên cứu công khai có sẵn. Ở đây chỉ có: đọc từng
file trong ZIP từ xa bằng HTTP Range (VLR, Zenodo 19705466, CC BY 4.0 — chỉ để ĐO chặn nhầm người
Việt), gom người bằng ArcFace (thà gộp nhầm còn hơn tách sót), chia theo nhóm 60/20/20, manifest,
lệnh ffmpeg mã hóa lại dùng chung cho cả hai lớp, đặc trưng thô và cổng kiểm lộ đề.

Quy ước:
- Đơn vị chia tập là **nhóm**: thành phần liên thông của đồ thị "cùng người (cos ArcFace ≥ ngưỡng,
  liên kết đơn trên mọi cặp khung)" ∪ "cùng video nguồn". Mẫu giả luôn cùng nhóm với video thật
  nguồn của nó. Hai mẫu khác tập không bao giờ có cặp khung giống nhau ≥ ngưỡng
  (`cross_split_max_similarity`).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import random
import re
import struct
import time
import zlib
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

SPLITS = ("train", "calib", "test")
SPLIT_RATIOS = (0.6, 0.2, 0.2)
CLIP_SECONDS = 3.0
TARGET_FPS = 25
CLIP_SIZE = 320
# Cổng lộ đề: AUC của bộ phân loại chỉ dùng đặc trưng thô phải nằm trong khoảng này.
LEAK_AUC_RANGE = (0.4, 0.6)
# Ít hơn chừng này mẫu mỗi lớp thì AUC quá nhiễu: chỉ cảnh báo, không chặn (chế độ SMOKE).
LEAK_MIN_PER_CLASS = 40
LEAK_FEATURES = (
    "bitrate_kbps",
    "size_bytes",
    "fps",
    "duration_s",
    "width",
    "height",
    "sharpness",
    "brightness",
)
VLR_RECORD = "19705466"
VLR_URL = "https://zenodo.org/api/records/{record}/files/{part}.zip/content"


# ── ZIP từ xa (HTTP Range) ───────────────────────────────────────────────────────────────
class RemoteZipError(RuntimeError):
    """Không đọc được ZIP từ xa (máy chủ không hỗ trợ Range, mạng lỗi, CRC sai…)."""


def _get_range(
    session, url: str, start: int, end: int, retries: int = 5, allow_short: bool = False
) -> bytes:
    """GET bytes [start, end] (cả hai đầu), thử lại có lùi thời gian; bắt buộc trả 206.
    `allow_short`: chấp nhận ít hơn (đoạn vượt cuối file)."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            response = session.get(url, headers={"Range": f"bytes={start}-{end}"}, timeout=120)
            if response.status_code != 206:
                raise RemoteZipError(f"Máy chủ trả {response.status_code}, không hỗ trợ Range.")
            data = response.content
            if len(data) != end - start + 1 and not (allow_short and data):
                raise RemoteZipError("Nhận thiếu dữ liệu.")
            return data
        except Exception as exc:  # noqa: BLE001 - lỗi mạng thì thử lại
            last = exc
            time.sleep(min(60.0, 2.0**attempt))
    raise RemoteZipError(f"Không tải được bytes {start}-{end}: {last}")


class HttpRangeFile(io.RawIOBase):
    """File chỉ-đọc trên HTTP, mỗi lần `read` là một yêu cầu Range (đủ để `zipfile` đọc mục lục)."""

    def __init__(self, url: str, session=None) -> None:
        import requests

        self.session = session or requests.Session()
        head = self.session.head(url, allow_redirects=True, timeout=60)
        head.raise_for_status()
        self.url = head.url
        self.size = int(head.headers["Content-Length"])
        self.pos = 0
        self.fetched = 0

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def readinto(self, buffer) -> int:
        if self.pos >= self.size or len(buffer) == 0:
            return 0
        end = min(self.size, self.pos + len(buffer)) - 1
        data = _get_range(self.session, self.url, self.pos, end)
        buffer[: len(data)] = data
        self.pos += len(data)
        self.fetched += len(data)
        return len(data)


@dataclass(frozen=True)
class ZipMember:
    name: str
    header_offset: int
    compress_size: int
    file_size: int
    compress_type: int
    crc: int


def list_remote_zip(url: str, session=None) -> list[ZipMember]:
    """Đọc mục lục (central directory) của ZIP từ xa; chỉ tải vài MB cuối file."""
    import zipfile

    raw = HttpRangeFile(url, session)
    with zipfile.ZipFile(io.BufferedReader(raw, buffer_size=1 << 20)) as archive:
        return [
            ZipMember(
                i.filename, i.header_offset, i.compress_size, i.file_size, i.compress_type, i.CRC
            )
            for i in archive.infolist()
            if not i.is_dir()
        ]


def parse_local_header(header: bytes) -> int:
    """Độ dài phần đầu cục bộ (30 + tên + extra) của một mục ZIP."""
    if len(header) < 30 or header[:4] != b"PK\x03\x04":
        raise RemoteZipError("Sai chữ ký local header.")
    name_len, extra_len = struct.unpack("<HH", header[26:30])
    return 30 + name_len + extra_len


def decode_member(member: ZipMember, payload: bytes) -> bytes:
    """Giải nén dữ liệu thô của một mục (stored hoặc deflate) và kiểm CRC-32."""
    if member.compress_type == 0:
        data = payload
    elif member.compress_type == 8:
        data = zlib.decompressobj(-15).decompress(payload)
    else:
        raise RemoteZipError(f"Kiểu nén {member.compress_type} chưa hỗ trợ.")
    if len(data) != member.file_size or (zlib.crc32(data) & 0xFFFFFFFF) != member.crc:
        raise RemoteZipError(f"CRC/kích thước sai: {member.name}")
    return data


def fetch_member(url: str, member: ZipMember, session=None) -> bytes:
    """Tải đúng một mục trong ZIP từ xa (1–2 yêu cầu Range). An toàn khi gọi song song (mỗi luồng một session)."""
    if session is None:
        import requests

        session = requests.Session()
    guess = 30 + len(member.name.encode()) + 256
    end = member.header_offset + guess + member.compress_size - 1
    blob = _get_range(session, url, member.header_offset, end, allow_short=True)
    start = parse_local_header(blob[:30])
    stop = start + member.compress_size
    if stop > len(blob):
        blob += _get_range(
            session, url, member.header_offset + len(blob), member.header_offset + stop - 1
        )
    return decode_member(member, blob[start:stop])


# ── VLR: tên file → nguồn ────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class VlrClip:
    member: str  # đường dẫn trong ZIP, ví dụ part4/HAVEA12/MOICH251/MOICH251_1.mp4
    part: str
    playlist: str
    video: str  # thư mục video YouTube (đơn vị "cùng nguồn")
    clip_id: str  # part4__HAVEA12__MOICH251__MOICH251_1
    index: int
    size: int = 0


_VLR_RE = re.compile(r"^(part\d+)/([^/]+)/([^/]+)/([^/]+?)_(\d+)\.mp4$")


def parse_vlr_member(name: str, size: int = 0) -> VlrClip | None:
    """`partN/PLAYLIST/VIDEO/VIDEO_k.mp4` → VlrClip; file khác (csv, thư mục) → None."""
    match = _VLR_RE.match(name)
    if not match:
        return None
    part, playlist, video, _, index = match.groups()
    clip_id = "__".join(name[: -len(".mp4")].split("/"))
    return VlrClip(name, part, playlist, video, clip_id, int(index), size)


def plan_candidates(
    clips: Iterable[VlrClip], videos_per_part: int, clips_per_video: int, seed: int
) -> list[VlrClip]:
    """Chọn clip ứng viên: xen kẽ playlist (đa dạng), trong mỗi video lấy clip cách đều nhau."""
    by_video: dict[tuple[str, str, str], list[VlrClip]] = defaultdict(list)
    for clip in clips:
        by_video[(clip.part, clip.playlist, clip.video)].append(clip)
    rng = random.Random(seed)
    chosen: list[VlrClip] = []
    for part in sorted({key[0] for key in by_video}):
        playlists: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        for key in sorted(k for k in by_video if k[0] == part):
            playlists[key[1]].append(key)
        for keys in playlists.values():
            rng.shuffle(keys)
        order = sorted(playlists)
        rng.shuffle(order)
        videos: list[tuple[str, str, str]] = []
        while len(videos) < videos_per_part and any(playlists[p] for p in order):
            for name in order:
                if playlists[name] and len(videos) < videos_per_part:
                    videos.append(playlists[name].pop())
        for key in videos:
            items = sorted(by_video[key], key=lambda c: c.index)
            if len(items) <= clips_per_video:
                chosen.extend(items)
            else:
                positions = np.linspace(0, len(items) - 1, clips_per_video).round().astype(int)
                chosen.extend(items[int(i)] for i in sorted(set(positions.tolist())))
    return chosen


# ── ArcFace (gom người nói) ──────────────────────────────────────────────────────────────
# Mốc đích chuẩn của ArcFace 112×112 (insightface `face_align.arcface_dst`).
ARCFACE_DST = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


def arcface_crop(image: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
    """Căn mặt về 112×112 theo 5 mốc (như `norm_crop` của insightface/uniface)."""
    import cv2

    matrix = cv2.estimateAffinePartial2D(
        np.asarray(landmarks, dtype=np.float32), ARCFACE_DST, method=cv2.LMEDS
    )[0]
    if matrix is None:
        raise ValueError("Không căn được mặt cho ArcFace.")
    return cv2.warpAffine(image, matrix, (112, 112), borderValue=0.0)


def arcface_blob(crops: Sequence[np.ndarray]) -> np.ndarray:
    """BGR 112×112 → NCHW float32, RGB, (x − 127,5)/127,5 (tiền xử lý của uniface ArcFace)."""
    batch = np.stack([np.asarray(c, dtype=np.float32)[:, :, ::-1] for c in crops])
    return np.ascontiguousarray(((batch - 127.5) / 127.5).transpose(0, 3, 1, 2))


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def labels(self) -> list[int]:
        """Nhãn thành phần 0..K-1, đánh số theo phần tử nhỏ nhất (ổn định)."""
        roots: dict[int, int] = {}
        out = []
        for item in range(len(self.parent)):
            root = self.find(item)
            out.append(roots.setdefault(root, len(roots)))
        return out


def _union_similar(uf: UnionFind, embeddings: Sequence[np.ndarray], threshold: float) -> None:
    owners: list[int] = []
    vectors: list[np.ndarray] = []
    for owner, rows in enumerate(embeddings):
        for row in np.atleast_2d(np.asarray(rows, dtype=np.float32)):
            owners.append(owner)
            vectors.append(row)
    if not vectors:
        return
    matrix = l2_normalize(np.stack(vectors))
    owner_array = np.asarray(owners)
    for start in range(0, len(matrix), 512):
        sims = matrix[start : start + 512] @ matrix.T
        for left, right in zip(*np.nonzero(sims >= threshold), strict=True):
            a, b = int(owner_array[start + int(left)]), int(owner_array[int(right)])
            if a != b:
                uf.union(a, b)


def cluster_persons(embeddings: Sequence[np.ndarray], threshold: float) -> list[int]:
    """Nhãn người cho từng clip: liên kết đơn trên MỌI cặp khung (cos ≥ ngưỡng) rồi lấy bao đóng
    bắc cầu. Ngưỡng thấp = gộp mạnh tay (thà gộp nhầm còn hơn tách sót). Mỗi phần tử của
    `embeddings` là mảng [k, D] (k khung của một clip)."""
    uf = UnionFind(len(embeddings))
    _union_similar(uf, embeddings, threshold)
    return uf.labels()


def group_components(person_of: Sequence[Any], video_of: Sequence[Any]) -> list[int]:
    """Nhóm chia tập: clip cùng người HOẶC cùng video nguồn thì chung nhóm (bắc cầu)."""
    if len(person_of) != len(video_of):
        raise ValueError("person_of và video_of phải cùng độ dài.")
    uf = UnionFind(len(person_of))
    first: dict[tuple[str, Any], int] = {}
    for i, (person, video) in enumerate(zip(person_of, video_of, strict=True)):
        for key in (("p", person), ("v", video)):
            if key in first:
                uf.union(first[key], i)
            else:
                first[key] = i
    return uf.labels()


def select_persons(
    person_of: Sequence[int],
    clip_ids: Sequence[str],
    *,
    max_persons: int,
    max_clips_per_person: int,
    min_clips_per_person: int,
    seed: int,
    video_of: Sequence[str] | None = None,
) -> dict[int, list[str]]:
    """Chọn ≤ `max_persons` người (ưu tiên người nhiều clip), mỗi người ≤ `max_clips_per_person` clip,
    xen kẽ các video khác nhau. Trả {nhãn người: [clip_id]} theo thứ tự xác định."""
    clips_by_person: dict[int, list[int]] = defaultdict(list)
    for i, person in enumerate(person_of):
        clips_by_person[int(person)].append(i)
    rng = random.Random(seed)
    eligible = sorted(
        p for p, items in clips_by_person.items() if len(items) >= min_clips_per_person
    )
    rng.shuffle(eligible)
    eligible.sort(key=lambda p: -min(len(clips_by_person[p]), max_clips_per_person))
    chosen: dict[int, list[str]] = {}
    for person in eligible[:max_persons]:
        items = sorted(clips_by_person[person], key=lambda i: clip_ids[i])
        if video_of is not None:
            by_video: dict[str, list[int]] = defaultdict(list)
            for i in items:
                by_video[video_of[i]].append(i)
            queues = [by_video[v] for v in sorted(by_video)]
            items = []
            while any(queues):
                for queue in queues:
                    if queue:
                        items.append(queue.pop(0))
        chosen[person] = [clip_ids[i] for i in items[:max_clips_per_person]]
    return dict(sorted(chosen.items()))


def assign_splits(
    group_weights: dict[str, int],
    ratios: Sequence[float] = SPLIT_RATIOS,
    seed: int = 0,
    names: Sequence[str] = SPLITS,
) -> dict[str, str]:
    """Gán từng nhóm (trọng số = số người) vào train/calib/test, tham lam theo phần thiếu hụt
    tương đối; nhóm lớn xếp trước. Xác định hoàn toàn theo (nhóm, seed)."""
    if len(ratios) != len(names) or not math.isclose(sum(ratios), 1.0, abs_tol=1e-6):
        raise ValueError("ratios phải khớp số tập và có tổng 1.")
    order = sorted(group_weights)
    random.Random(seed).shuffle(order)
    order.sort(key=lambda g: -group_weights[g])
    total = sum(group_weights.values())
    filled = dict.fromkeys(names, 0)
    out: dict[str, str] = {}
    for group in order:
        target = {n: r * total for n, r in zip(names, ratios, strict=True)}
        best = max(
            names,
            key=lambda n: (target[n] - filled[n]) / target[n] if target[n] else -math.inf,
        )
        out[group] = best
        filled[best] += group_weights[group]
    return out


def cross_split_max_similarity(embeddings: Sequence[np.ndarray], split_of: Sequence[str]) -> float:
    """Cos lớn nhất giữa hai khung thuộc hai tập khác nhau (phải < ngưỡng gom người)."""
    best = -1.0
    labelled = [
        (l2_normalize(np.atleast_2d(e)), s) for e, s in zip(embeddings, split_of, strict=True)
    ]
    for name in sorted(set(split_of)):
        inside = [e for e, s in labelled if s == name]
        outside = [e for e, s in labelled if s != name]
        if not inside or not outside:
            continue
        best = max(best, float((np.vstack(inside) @ np.vstack(outside).T).max()))
    return best


def split_summary(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Đếm người, nhóm, clip theo tập (để in phân bố)."""
    persons: dict[str, set] = defaultdict(set)
    groups: dict[str, set] = defaultdict(set)
    clips: dict[str, int] = defaultdict(int)
    for row in rows:
        persons[row["split"]].add(row["person_id"])
        groups[row["split"]].add(row["group_id"])
        clips[row["split"]] += 1
    return {
        s: {"persons": len(persons[s]), "groups": len(groups[s]), "clips": clips[s]}
        for s in SPLITS
        if s in clips
    }


# ── manifest ─────────────────────────────────────────────────────────────────────────────
MANIFEST_FIELDS = (
    "sample_id",
    "path",
    "variant",
    "split",
    "label",
    "dataset",
    "method",
    "person_id",
    "group_id",
    "source_clip",
    "source_url",
    "license",
    "encode",
    "sha256",
)


def validate_manifest(rows: Sequence[dict[str, str]]) -> None:
    """Kiểm manifest: trường đủ, tập/nhãn hợp lệ, người và nhóm không vắt qua hai tập, mẫu giả có
    phương pháp giả; mẫu giả có video thật nguồn trong manifest thì nguồn phải cùng tập."""
    person_split: dict[str, str] = {}
    group_split: dict[str, str] = {}
    real_split: dict[tuple[str, str], str] = {}
    for row in rows:
        missing = [f for f in MANIFEST_FIELDS if f not in row]
        if missing:
            raise ValueError(f"Manifest thiếu trường {missing}")
        if row["split"] not in SPLITS:
            raise ValueError(f"Tập lạ: {row['split']}")
        if row["label"] not in ("real", "fake"):
            raise ValueError(f"Nhãn lạ: {row['label']}")
        for key, seen in (("person_id", person_split), ("group_id", group_split)):
            if not row[key]:
                continue
            previous = seen.setdefault(row[key], row["split"])
            if previous != row["split"]:
                raise ValueError(f"{key} {row[key]} nằm ở hai tập {previous}/{row['split']}.")
        if row["label"] == "real" and row["source_clip"]:
            real_split[(row["source_clip"], row["variant"])] = row["split"]
    for row in rows:
        if row["label"] != "fake":
            continue
        if not row["method"]:
            raise ValueError(f"Mẫu giả thiếu phương pháp giả: {row['sample_id']}")
        source = real_split.get((row["source_clip"], row["variant"]))
        if source is not None and source != row["split"]:
            raise ValueError(f"Mẫu giả {row['sample_id']} khác tập với video thật nguồn.")


def write_manifest(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    rows = sorted(rows, key=lambda r: (r["variant"], r["split"], r["label"], r["sample_id"]))
    tmp = Path(str(path) + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(MANIFEST_FIELDS))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {k: ("" if row.get(k) is None else row.get(k)) for k in MANIFEST_FIELDS}
            )
    os.replace(tmp, path)


def read_manifest(path: Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ── tiến độ (chạy tiếp khi phiên 12 giờ hết) ─────────────────────────────────────────────
@dataclass
class Progress:
    """Ghi danh sách việc đã xong/lỗi vào JSON (ghi nguyên tử) sau MỖI việc."""

    path: Path
    done: dict[str, dict[str, Any]] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Progress:
        path = Path(path)
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(path, dict(data.get("done", {})), dict(data.get("failed", {})))
        return cls(path)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(str(self.path) + ".tmp")
        tmp.write_text(
            json.dumps({"done": self.done, "failed": self.failed}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    def is_done(self, key: str) -> bool:
        return key in self.done

    def mark_done(self, key: str, info: dict[str, Any] | None = None) -> None:
        self.done[key] = info or {}
        self.failed.pop(key, None)
        self.save()

    def mark_failed(self, key: str, reason: str) -> None:
        self.failed[key] = reason[-500:]
        self.save()


# ── ffmpeg: một lệnh mã hóa lại dùng chung cho thật và giả ───────────────────────────────
ENCODE_PROFILES: dict[str, dict[str, Any]] = {
    # bản trung gian gần như không mất mát
    "mid": {"crf": 12, "size": CLIP_SIZE},
    # bản phát hành: cả hai lớp cùng một lệnh
    "c23": {"crf": 23, "size": CLIP_SIZE},
    # bản nén mạnh cho cả hai lớp (giống mức c40 của DATA-05)
    "c40": {"crf": 40, "size": CLIP_SIZE},
}


def encode_cmd(
    ffmpeg: str,
    src: str | Path,
    dst: str | Path,
    *,
    profile: str,
    seconds: float = CLIP_SECONDS,
    start: float = 0.0,
    fps: int = TARGET_FPS,
    metadata: dict[str, str] | None = None,
) -> list[str]:
    """Lệnh ffmpeg cố định: bỏ âm thanh, xóa metadata nguồn, cùng kích thước/fps/GOP/x264 preset."""
    spec = ENCODE_PROFILES[profile]
    size = int(spec["size"])
    cmd = [ffmpeg, "-nostdin", "-y", "-loglevel", "error"]
    if start > 0:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += [
        "-i",
        str(src),
        "-t",
        f"{seconds:.3f}",
        "-an",
        "-sn",
        "-dn",
        "-map_metadata",
        "-1",
        "-vf",
        f"scale={size}:{size}:flags=bicubic,fps={fps},format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        str(int(spec["crf"])),
        "-g",
        str(2 * fps),
        "-bf",
        "2",
        "-fflags",
        "+bitexact",
        "-flags:v",
        "+bitexact",
    ]
    for key, value in sorted((metadata or {}).items()):
        cmd += ["-metadata", f"{key}={value}"]
    cmd += ["-movflags", "+faststart", str(dst)]
    return cmd


# ── đặc trưng thô và cổng lộ đề ──────────────────────────────────────────────────────────
def video_features(path: Path, max_frames: int = 90) -> dict[str, float]:
    """Đặc trưng thô KHÔNG nhìn nội dung mặt: bitrate, kích thước file, fps, thời lượng, khung
    hình, độ nét (phương sai Laplacian) và độ sáng trung bình."""
    import cv2

    capture = cv2.VideoCapture(str(path))
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        width = float(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0.0)
        height = float(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0.0)
        sharp: list[float] = []
        bright: list[float] = []
        frames = 0
        while frames < 10_000:
            ok, frame = capture.read()
            if not ok:
                break
            if frames < max_frames:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                sharp.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
                bright.append(float(gray.mean()))
            frames += 1
    finally:
        capture.release()
    size = float(Path(path).stat().st_size)
    duration = frames / fps if fps > 0 else 0.0
    return {
        "bitrate_kbps": size * 8 / 1000 / duration if duration > 0 else 0.0,
        "size_bytes": size,
        "fps": fps,
        "duration_s": duration,
        "width": width,
        "height": height,
        "sharpness": float(np.mean(sharp)) if sharp else 0.0,
        "brightness": float(np.mean(bright)) if bright else 0.0,
    }


def univariate_auc(values: Sequence[float], labels: Sequence[int]) -> float | None:
    """AUC đơn biến (nhãn 1 = giả); None khi thiếu một lớp."""
    from sklearn.metrics import roc_auc_score

    y = np.asarray(labels)
    if np.unique(y).size < 2:
        return None
    return float(roc_auc_score(y, np.asarray(values, dtype=float)))


def leak_auc(
    features: Sequence[dict[str, float]],
    labels: Sequence[int],
    groups: Sequence[str],
    seed: int = 0,
    n_splits: int = 5,
) -> float | None:
    """AUC ngoài-fold của hồi quy logistic trên đặc trưng thô, chia fold THEO NHÓM (thật và giả
    cùng clip nguồn luôn cùng fold). None khi thiếu lớp hoặc < 2 nhóm."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    y = np.asarray(labels, dtype=int)
    groups_array = np.asarray(groups)
    n_groups = np.unique(groups_array).size
    if np.unique(y).size < 2 or n_groups < 2:
        return None
    x = np.asarray([[float(f[name]) for name in LEAK_FEATURES] for f in features], dtype=float)
    x = np.log1p(np.abs(x)) * np.sign(x)
    # Đổi tên nhóm theo seed để thứ tự fold không phụ thuộc tên.
    rng = np.random.default_rng(seed)
    names = np.unique(groups_array)
    mapping = dict(zip(names, rng.permutation(len(names)), strict=True))
    coded = np.asarray([mapping[g] for g in groups_array])
    scores = np.zeros(len(y), dtype=float)
    folds = GroupKFold(n_splits=min(n_splits, n_groups))
    for train_idx, test_idx in folds.split(x, y, coded):
        if np.unique(y[train_idx]).size < 2:
            scores[test_idx] = 0.5
            continue
        model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
        model.fit(x[train_idx], y[train_idx])
        scores[test_idx] = model.predict_proba(x[test_idx])[:, 1]
    return float(roc_auc_score(y, scores))


@dataclass(frozen=True)
class LeakVerdict:
    ok: bool  # được phép đi tiếp
    enforced: bool  # đủ mẫu để cổng có hiệu lực
    auc: float | None
    message_vi: str


def leak_verdict(
    auc_value: float | None,
    n_real: int,
    n_fake: int,
    auc_range: tuple[float, float] = LEAK_AUC_RANGE,
    min_per_class: int = LEAK_MIN_PER_CLASS,
) -> LeakVerdict:
    """Cổng lộ đề. Đủ mẫu mà AUC ngoài khoảng → DỪNG. Ít mẫu (SMOKE) → chỉ cảnh báo."""
    low, high = auc_range
    enforced = min(n_real, n_fake) >= min_per_class
    if auc_value is None:
        return LeakVerdict(
            not enforced,
            enforced,
            None,
            "Không tính được AUC lộ đề (thiếu một lớp hoặc thiếu nhóm).",
        )
    inside = low <= auc_value <= high
    if inside:
        return LeakVerdict(
            True, enforced, auc_value, f"Lộ đề ĐẠT: AUC {auc_value:.3f} nằm trong [{low}; {high}]."
        )
    if not enforced:
        return LeakVerdict(
            True,
            False,
            auc_value,
            f"CẢNH BÁO: AUC lộ đề {auc_value:.3f} ngoài [{low}; {high}], nhưng mới có "
            f"{n_real} thật / {n_fake} giả (< {min_per_class} mỗi lớp) nên chưa kết luận được.",
        )
    return LeakVerdict(
        False,
        True,
        auc_value,
        f"DỪNG: AUC lộ đề {auc_value:.3f} nằm ngoài [{low}; {high}]. Bộ phân loại chỉ nhìn "
        "bitrate/kích thước/fps/thời lượng/độ nét/độ sáng đã tách được thật và giả, nên mô hình "
        "học trên dữ liệu này có thể học mẹo thay vì dấu vết giả mạo. KHÔNG dùng để dạy; gửi "
        "leak_report.json cho trưởng nhóm.",
    )
