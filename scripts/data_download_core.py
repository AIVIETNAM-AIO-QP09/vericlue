"""Các tiện ích tải dữ liệu DATA-01; không ghi thông tin đăng nhập ra đĩa."""

from __future__ import annotations

import hashlib
import io
import json
import os
import random
import re
import shutil
import tarfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import httpx

RESERVE_BYTES = 10_000_000_000
CHUNK_BYTES = 1_048_576


class DownloadError(Exception):
    """Lỗi tải có thông báo không chứa URL ký hay token."""


class SkipDataset(DownloadError):
    """Nguồn chưa đủ điều kiện tải an toàn; tiếp tục các bộ khác."""


@dataclass
class Dataset:
    name: str
    source: str
    license: str
    full_bytes: int | None
    budget_bytes: int
    gated: bool = False


@dataclass
class RemoteFile:
    url: str
    path: str
    size: int
    sha256: str | None = None


@dataclass
class Plan:
    dataset: Dataset
    files: list[RemoteFile]
    peak_bytes: int
    revision: str = ""
    notes: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    execute: Callable[[Path, Client], None] | None = None


def safe_path(root: Path, relative: str) -> Path:
    """Chặn đường dẫn thoát thư mục, kể cả đường dẫn Windows trong archive."""
    normalized = relative.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if not parts or normalized.startswith("/") or any(p in ("..", "") or ":" in p for p in parts):
        raise DownloadError("Đường dẫn nguồn không an toàn.")
    target = root.joinpath(*parts).resolve()
    if not target.is_relative_to(root.resolve()):
        raise DownloadError("Đường dẫn nguồn thoát thư mục dữ liệu.")
    return target


def check_disk(root: Path, required: int, reserve: int = RESERVE_BYTES) -> None:
    """Kiểm tra dung lượng ở ổ chứa đích, giữ ít nhất 10 GB trống."""
    if required < 0 or reserve < 0:
        raise DownloadError("Dung lượng dự kiến không hợp lệ.")
    probe = root.resolve()
    while not probe.exists():
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    if free < required + reserve:
        raise DownloadError(
            f"Không đủ ổ đĩa: cần {required / 1e9:.3f} GB + dự phòng {reserve / 1e9:.1f} GB; "
            f"còn {free / 1e9:.3f} GB."
        )


def sample_groups(
    groups: dict[str, list[RemoteFile]], budget: int, seed: int
) -> tuple[list[str], list[RemoteFile]]:
    """Chọn nguyên nhóm nguồn có seed cố định, không cắt nhóm cho vừa hạn mức."""
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)
    chosen: list[str] = []
    files: list[RemoteFile] = []
    used = 0
    for key in keys:
        cost = sum(f.size for f in groups[key])
        if cost < 0 or any(f.size < 0 for f in groups[key]):
            raise DownloadError("Kích thước file chưa xác minh.")
        if groups[key] and used + cost <= budget:
            chosen.append(key)
            files.extend(groups[key])
            used += cost
    return chosen, files


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_required(file: RemoteFile, dest: Path) -> int:
    """Byte đĩa còn cần cho file này; chỉ trừ partial có đúng identity nguồn."""
    resource = hashlib.sha256((file.url + str(file.size) + str(file.sha256)).encode()).hexdigest()
    record = dest.with_name(dest.name + ".verified.json")
    if dest.is_file() and dest.stat().st_size == file.size:
        try:
            stored = json.loads(record.read_text()) if record.exists() else {}
            if not stored or stored.get("resource") == resource:
                return 0
        except (OSError, ValueError):
            pass
    part = dest.with_name(dest.name + ".part")
    part_record = dest.with_name(dest.name + ".part.json")
    if part.is_file() and part_record.is_file():
        try:
            if json.loads(part_record.read_text()).get("resource") == resource:
                return max(0, file.size - min(file.size, part.stat().st_size))
        except (OSError, ValueError):
            pass
    return file.size


def remaining_peak(plan: Plan, dest: Path) -> int:
    """Không cộng lại cache đã nằm trong disk_usage.used khi tải tiếp."""
    known = sum(file.size for file in plan.files)
    return max(0, plan.peak_bytes - known) + sum(
        download_required(file, safe_path(dest, file.path)) for file in plan.files
    )


class Client:
    """HTTP có kiểm tra kích thước, Range và ghi file nguyên tử."""

    def __init__(self, token: str = "", kaggle_auth: tuple[str, str] | None = None):
        self.token = token
        self.kaggle_auth = kaggle_auth
        self._http = httpx.Client(follow_redirects=True, timeout=httpx.Timeout(120, connect=30))

    def close(self) -> None:
        """Đóng kết nối HTTP."""
        self._http.close()

    def _kwargs(self, url: str, kwargs: dict | None = None) -> dict:
        options = dict(kwargs or {})
        headers = dict(options.pop("headers", {}))
        headers.setdefault("Accept-Encoding", "identity")
        host = urlsplit(url).hostname or ""
        if host in ("huggingface.co", "datasets-server.huggingface.co") and self.token:
            headers.setdefault("Authorization", f"Bearer {self.token}")
        if host in ("www.kaggle.com", "kaggle.com") and self.kaggle_auth:
            options.setdefault("auth", self.kaggle_auth)
        options["headers"] = headers
        return options

    def get_bytes(self, url: str, limit: int = 10_000_000, **kwargs) -> bytes:
        """Đọc metadata có giới hạn; không xuất nội dung lỗi HTTP."""
        try:
            with self._http.stream("GET", url, **self._kwargs(url, kwargs)) as response:
                self._check_status(response)
                result = bytearray()
                for chunk in response.iter_bytes(CHUNK_BYTES):
                    result.extend(chunk)
                    if len(result) > limit:
                        raise DownloadError("Metadata vượt giới hạn đọc.")
                return bytes(result)
        except httpx.HTTPError:
            raise DownloadError(
                "Không kết nối được nguồn tải (kiểm tra mạng/quyền truy cập)."
            ) from None

    def json(self, url: str, **kwargs):
        """Đọc JSON metadata từ nguồn."""
        try:
            return json.loads(self.get_bytes(url, **kwargs))
        except (ValueError, UnicodeError):
            raise DownloadError("Nguồn trả metadata không phải JSON hợp lệ.") from None

    @staticmethod
    def _check_status(response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise SkipDataset(
                "Nguồn từ chối truy cập: kiểm tra token và chấp nhận điều khoản trên trang bộ dữ liệu."
            )
        if response.status_code == 429:
            raise SkipDataset("Nguồn hết quota/giới hạn lượt tải; thử lại sau.")
        if response.status_code >= 400:
            raise DownloadError(f"Nguồn tải trả HTTP {response.status_code}.")

    def hf_files(self, repo: str, prefix: str = "") -> tuple[str, list[dict]]:
        """Liệt kê cây HF có pagination, ghim revision để tránh đổi nguồn giữa lượt tải."""
        metadata = self.json(f"https://huggingface.co/api/datasets/{repo}")
        revision = metadata["sha"]
        url = f"https://huggingface.co/api/datasets/{repo}/tree/{revision}/{prefix}?recursive=true&limit=1000"
        entries: list[dict] = []
        while url:
            try:
                response = self._http.get(url, **self._kwargs(url))
                self._check_status(response)
                entries.extend(response.json())
                url = response.links.get("next", {}).get("url", "")
            except (httpx.HTTPError, ValueError):
                raise DownloadError("Không đọc được danh sách file HF.") from None
        return revision, entries

    def head_size(self, url: str) -> int:
        """Đọc kích thước HTTP mà không tải body; từ chối HTML/quota page."""
        try:
            response = self._http.head(url, **self._kwargs(url))
            self._check_status(response)
            if "text/html" in response.headers.get("Content-Type", ""):
                raise SkipDataset("Nguồn trả trang HTML/quota, không phải dữ liệu.")
            size = int(response.headers.get("Content-Length", "-1"))
            if size < 0:
                raise SkipDataset("Nguồn không công bố kích thước file để preflight.")
            return size
        except (httpx.HTTPError, ValueError):
            raise DownloadError("Không xác minh được kích thước nguồn.") from None

    def remote_file(self, url: str, size: int) -> HTTPRangeFile:
        """Mở file seekable, chỉ đọc byte ranges cho metadata Parquet/TAR."""
        return HTTPRangeFile(self, url, size)

    def download(self, file: RemoteFile, dest: Path) -> None:
        """Tải tiếp .part; chỉ đổi tên khi đúng kích thước và checksum nếu có."""
        if file.size < 0:
            raise DownloadError("Kích thước file chưa xác minh.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        record = dest.with_name(dest.name + ".verified.json")
        resource = hashlib.sha256(
            (file.url + str(file.size) + str(file.sha256)).encode()
        ).hexdigest()
        if dest.exists() and dest.stat().st_size == file.size:
            stored = json.loads(record.read_text()) if record.exists() else {}
            expected = file.sha256 or stored.get("sha256")
            if expected and _sha256(dest) != expected:
                raise DownloadError("Checksum file đã tải không khớp; cần kiểm tra/xóa file lỗi.")
            if not stored or stored.get("resource") == resource:
                return
        part = dest.with_name(dest.name + ".part")
        part_record = dest.with_name(dest.name + ".part.json")
        if part.exists():
            try:
                same = json.loads(part_record.read_text()).get("resource") == resource
            except (OSError, ValueError):
                same = False
            if not same or part.stat().st_size > file.size:
                part.unlink()
        part_record.write_text(json.dumps({"resource": resource}), encoding="utf-8")
        start = part.stat().st_size if part.exists() else 0
        check_disk(dest.parent, max(0, file.size - start))
        if start < file.size:
            headers = {"Range": f"bytes={start}-"} if start else {}
            try:
                with self._http.stream(
                    "GET", file.url, **self._kwargs(file.url, {"headers": headers})
                ) as response:
                    self._check_status(response)
                    if response.status_code == 206:
                        match = re.fullmatch(
                            r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", "")
                        )
                        if not match or int(match[1]) != start or int(match[3]) != file.size:
                            raise DownloadError(
                                "HTTP Range không khớp file; không nối dữ liệu sai."
                            )
                        if int(match[2]) != file.size - 1:
                            raise DownloadError("HTTP Range trả thiếu phần cuối file.")
                    elif response.status_code == 200:
                        start = 0
                        check_disk(dest.parent, file.size)
                    else:
                        raise DownloadError("Nguồn không trả nội dung tải hợp lệ.")
                    if response.headers.get("Content-Encoding", "identity") != "identity":
                        raise DownloadError(
                            "Nguồn nén HTTP ngoài dự kiến; không thể xác minh byte range."
                        )
                    written = start
                    reported = start
                    with part.open("ab" if start else "wb") as stream:
                        for chunk in response.iter_bytes(CHUNK_BYTES):
                            written += len(chunk)
                            if written > file.size:
                                raise DownloadError("Nội dung tải vượt kích thước nguồn công bố.")
                            stream.write(chunk)
                            if written - reported >= 64 * CHUNK_BYTES:
                                stream.flush()
                                print(
                                    f"  Tải dữ liệu: {written / 1e6:.0f}/{file.size / 1e6:.0f} MB",
                                    flush=True,
                                )
                                reported = written
            except httpx.HTTPError:
                raise DownloadError("Tải bị ngắt; chạy lại để tiếp tục file .part.") from None
        if not part.exists() or part.stat().st_size != file.size:
            raise DownloadError("Tải chưa đủ kích thước; giữ .part để chạy lại.")
        digest = _sha256(part)
        if file.sha256 and digest != file.sha256:
            raise DownloadError("Checksum nguồn không khớp; không sử dụng file tải.")
        os.replace(part, dest)
        record.write_text(json.dumps({"resource": resource, "sha256": digest}), encoding="utf-8")
        part_record.unlink(missing_ok=True)


class HTTPRangeFile(io.RawIOBase):
    """File seekable đọc Range nghiêm ngặt; không fallback tải toàn file."""

    def __init__(self, client: Client, url: str, size: int):
        self.client, self.url, self.size, self.position = client, url, size, 0
        self.transferred = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = 0) -> int:
        target = offset + (self.position if whence == 1 else self.size if whence == 2 else 0)
        if target < 0:
            raise ValueError("Negative seek")
        self.position = target
        return target

    def read(self, size: int = -1) -> bytes:
        length = self.size - self.position if size < 0 else min(size, self.size - self.position)
        if length <= 0:
            return b""
        # Do not permit unbounded read of a large source as a small fallback.
        if size < 0 and length > 64 * CHUNK_BYTES:
            raise SkipDataset(
                "Nguồn cần đọc hơn 64 MiB/lượt; chưa hỗ trợ tải chọn lọc trong small."
            )
        if length > 64 * CHUNK_BYTES:
            chunks = []
            remaining = length
            while remaining:
                chunk = self.read(min(remaining, 64 * CHUNK_BYTES))
                chunks.append(chunk)
                remaining -= len(chunk)
            return b"".join(chunks)
        start, end = self.position, self.position + length - 1
        try:
            with self.client._http.stream(
                "GET",
                self.url,
                **self.client._kwargs(self.url, {"headers": {"Range": f"bytes={start}-{end}"}}),
            ) as response:
                self.client._check_status(response)
                expected = f"bytes {start}-{end}/{self.size}"
                if response.status_code != 206 or response.headers.get("Content-Range") != expected:
                    raise SkipDataset(
                        "Nguồn không hỗ trợ HTTP Range chính xác; bỏ qua small, không tải full."
                    )
                if response.headers.get("Content-Encoding", "identity") != "identity":
                    raise DownloadError("HTTP Range không trả byte gốc.")
                result = bytearray()
                for chunk in response.iter_bytes(CHUNK_BYTES):
                    result.extend(chunk)
                    if len(result) > length:
                        raise DownloadError("HTTP Range trả vượt số byte.")
                if len(result) != length:
                    raise DownloadError("HTTP Range trả sai số byte.")
                self.position += length
                self.transferred += length
                return bytes(result)
        except httpx.HTTPError:
            raise DownloadError("Đọc HTTP Range bị gián đoạn.") from None

    def readinto(self, buffer) -> int:
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)


def safe_extract_tar(archive: Path, dest: Path, members: list[str] | None = None) -> None:
    """Giải nén file thường; cấm traversal, link và file thiết bị."""
    wanted = set(members) if members is not None else None
    with tarfile.open(archive) as source:
        selected = [m for m in source.getmembers() if wanted is None or m.name in wanted]
        for member in selected:
            safe_path(dest, member.name)
            if not (member.isfile() or member.isdir()):
                raise DownloadError("Archive chứa link hoặc file đặc biệt; không giải nén.")
        needed = sum(
            m.size
            for m in selected
            if m.isfile()
            and (
                not safe_path(dest, m.name).exists()
                or safe_path(dest, m.name).stat().st_size != m.size
            )
        )
        check_disk(dest, needed)
        for member in selected:
            target = safe_path(dest, member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if target.exists() and target.stat().st_size == member.size:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            check_disk(dest, member.size)
            stream = source.extractfile(member)
            if stream is None:
                raise DownloadError("Archive thiếu nội dung file.")
            partial = target.with_name(target.name + ".extract.part")
            with stream, partial.open("wb") as output:
                shutil.copyfileobj(stream, output, CHUNK_BYTES)
            if partial.stat().st_size != member.size:
                raise DownloadError("File giải nén thiếu byte.")
            os.replace(partial, target)


def write_source(plan: Plan, dest: Path, seed: int, status: str, reason: str = "") -> Path:
    """Ghi provenance và inventory thực tế; SOURCE luôn nằm ngoài Git."""
    dest.mkdir(parents=True, exist_ok=True)
    entries = sorted(
        p
        for p in dest.rglob("*")
        if p.is_file()
        and p.name != "SOURCE.md"
        and not p.name.endswith((".part", ".part.json", ".verified.json"))
    )
    license_text = plan.dataset.license
    restrictions = "chỉ dùng nghiên cứu, không phân phối lại"
    if "chưa rõ" in license_text or "Không ghi" in license_text:
        restrictions += "\ngiấy phép chưa rõ — không phân phối lại"
    if "ND" in license_text:
        restrictions += "\nkhông phân phối bản phái sinh (ví dụ biến thể nén ở DATA-05)"
    lines = [
        f"# Nguồn dữ liệu: {plan.dataset.name}",
        "",
        f"- Nguồn: {plan.dataset.source}",
        f"- Ngày ghi: {datetime.now(timezone(timedelta(hours=7))).isoformat()}",
        f"- Revision: {plan.revision or 'nguồn không công bố revision'}",
        f"- Giấy phép: {license_text}",
        f"- Trạng thái: {status}",
        f"- Seed: {seed}",
        f"- Số file lưu: {len(entries)} (bao gồm metadata/archive, không coi là số mẫu)",
        f"- Số byte lưu: {sum(p.stat().st_size for p in entries)}",
        "",
        restrictions,
        "",
    ]
    if reason:
        lines.extend([f"Lý do: {reason}", ""])
    lines.extend(plan.notes)
    lines.extend(["", "## Nhóm nguồn được giữ", ""])
    lines.extend(f"- `{group}`" for group in sorted(set(plan.groups)))
    lines.extend(["", "## Danh sách file thực tế", ""])
    lines.extend(
        f"- `{p.relative_to(dest).as_posix()}` — {p.stat().st_size} bytes" for p in entries
    )
    result = dest / "SOURCE.md"
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    check_disk(dest, len(payload))
    temporary = dest / "SOURCE.md.part"
    temporary.write_bytes(payload)
    os.replace(temporary, result)
    return result
