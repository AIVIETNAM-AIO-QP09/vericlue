"""Tải model pinned vào MODELS_DIR, ghi/kiểm SHA-256 (DATA-02).

--verify không tải mạng hay sửa manifest. File hoàn chỉnh đúng hash được bỏ qua;
file .part tải lại an toàn, không nhận hash mới để hợp thức hóa file hỏng.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "models" / "manifest.yaml"
CHUNK_SIZE = 1024 * 1024
TIMEOUT_SECONDS = 120
LICENSES = {
    "MIT",
    "Apache-2.0",
    "BSD-3-Clause",
    "BSD-2-Clause",
    "CC-BY-NC-SA-4.0",
    "CC-BY-NC-4.0",
    "OpenRAIL++",
    "research-only (nc)",
    "nghiên cứu phi thương mại",
}


class DownloadError(ValueError):
    """Nguồn/giấy phép/file không hợp lệ, không được tự fallback hay đổi hash."""


def models_dir() -> Path:
    """Biến môi trường ưu tiên; đường dẫn tương đối tính từ gốc checkout."""
    configured = Path(os.getenv("MODELS_DIR", "./models")).expanduser()
    return (configured if configured.is_absolute() else ROOT / configured).resolve()


def sha256(path: Path) -> str:
    """SHA-256 streaming, không nạp trọng số lớn vào RAM."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _destination(root: Path, model_id: str, filename: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", model_id) or model_id in {".", ".."}:
        raise DownloadError("id model không hợp lệ.")
    path = PurePosixPath(filename)
    if (
        not filename
        or "\\" in filename
        or ":" in filename
        or path.is_absolute()
        or ".." in path.parts
        or any(part in {"", "."} for part in path.parts)
    ):
        raise DownloadError(f"Đường dẫn file không hợp lệ: {filename}")
    result = (root / model_id / Path(*path.parts)).resolve()
    if not result.is_relative_to(root) or result == root:
        raise DownloadError("File/symlink thoát khỏi MODELS_DIR.")
    # The partial file is also checked, since it may have been replaced by a symlink.
    partial = result.with_name(result.name + ".part")
    if partial.is_symlink() or not partial.resolve().is_relative_to(root):
        raise DownloadError("File .part không an toàn.")
    return result


def _hash_field(value: Any, field: str) -> None:
    if value is not None and (
        not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
    ):
        raise DownloadError(f"{field} phải là SHA-256 hex hoặc null.")


def _validate(model: dict, root: Path) -> None:
    if model.get("license") not in LICENSES or model.get("license_status") not in {
        "verified",
        "accepted-research",
    }:
        raise DownloadError(f"{model.get('id')}: giấy phép chưa rõ/không được phép, không tải.")
    if not isinstance(model.get("license_url"), str) or not model["license_url"].startswith(
        "https://"
    ):
        raise DownloadError("Thiếu link nguồn giấy phép.")
    source = model.get("source", {})
    if not isinstance(source, dict) or source.get("type") not in {"hf", "http", "gdrive"}:
        raise DownloadError("Nguồn model không hợp lệ.")
    revision = source.get("revision")
    if source["type"] == "hf" and not (
        isinstance(revision, str) and re.fullmatch(r"[0-9a-f]{40}", revision)
    ):
        raise DownloadError("Hugging Face phải pin commit đầy đủ, không dùng main.")
    if source["type"] == "http" and (not revision or revision in {"main", "master", "TODO"}):
        raise DownloadError("URL HTTP cần revision bất biến đã xác định.")
    files = model.get("files")
    if not isinstance(files, list) or not files:
        raise DownloadError("Model cần danh sách file rõ ràng.")
    seen = set()
    for item in files:
        if not isinstance(item, dict):
            raise DownloadError("File entry không hợp lệ.")
        dest = _destination(root, model["id"], item.get("path", ""))
        if dest in seen:
            raise DownloadError("File đích bị trùng trong model.")
        seen.add(dest)
        size = item.get("size_bytes")
        if size is None and source["type"] != "gdrive":
            raise DownloadError("Thiếu kích thước artifact đã xác minh.")
        if size is not None and (isinstance(size, bool) or not isinstance(size, int) or size < 1):
            raise DownloadError("size_bytes phải là số nguyên dương.")
        _hash_field(item.get("sha256"), "sha256")
        _hash_field(item.get("upstream_sha256"), "upstream_sha256")
        url = urllib.parse.urlsplit(item.get("url", ""))
        local_http = url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            not url.hostname
            or url.username
            or url.password
            or (url.scheme != "https" and not local_http)
        ):
            raise DownloadError(
                "Chỉ HTTPS hoặc HTTP server test loopback; không URL chứa mật khẩu."
            )
        if source["type"] == "hf":
            expected = f"/{source.get('repo')}/resolve/{revision}/"
            if url.hostname != "huggingface.co" or not url.path.startswith(expected):
                raise DownloadError("URL file không khớp repo/commit Hugging Face đã pin.")
        if source["type"] == "gdrive" and url.hostname not in {
            "drive.google.com",
            "drive.usercontent.google.com",
        }:
            raise DownloadError("SBI chỉ tải từ nguồn Drive gốc, không mirror.")


def _save_manifest(path: Path, data: dict) -> None:
    # Same-directory temporary file gives atomic replace on both Windows/Linux.
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(
                "# DATA-02: pin nguồn; sha256 ghi sau tải/kiểm byte thực. Không commit weights.\n"
            )
            yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _check(path: Path, item: dict) -> str:
    if not path.is_file() or not item.get("sha256"):
        raise DownloadError(f"Thiếu file hoặc SHA-256 đã pin: {path}")
    if item.get("size_bytes") is not None and path.stat().st_size != item["size_bytes"]:
        raise DownloadError(f"Sai kích thước: {path}")
    digest = sha256(path)
    if digest != item["sha256"] or (
        item.get("upstream_sha256") and digest != item["upstream_sha256"]
    ):
        raise DownloadError(f"SHA-256 lệch: {path}; không tự đổi hash hay ghi đè file.")
    return digest


def _download(path: Path, item: dict, stats: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    request = urllib.request.Request(item["url"], headers={"User-Agent": "VeriClue-DATA-02/1.0"})
    digest = hashlib.sha256()
    received = 0
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" in content_type:
            raise DownloadError(
                "Nguồn trả HTML/login/Drive confirmation, không phải artifact; không ghi hash."
            )
        content_length = response.headers.get("Content-Length")
        with partial.open("wb") as stream:
            while chunk := response.read(CHUNK_SIZE):
                if not received and chunk.lstrip()[:30].lower().startswith(
                    (b"<!doctype html", b"<html")
                ):
                    raise DownloadError(
                        "Nguồn trả trang HTML; cần lấy quyền truy cập từ nguồn gốc."
                    )
                stream.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                stats["downloaded_bytes"] += len(chunk)
            stream.flush()
            os.fsync(stream.fileno())
    if received == 0 or (content_length and received != int(content_length)):
        raise DownloadError("File rỗng/bị ngắt, không đủ Content-Length.")
    if item.get("size_bytes") is not None and received != item["size_bytes"]:
        raise DownloadError(f"Sai kích thước artifact: nhận {received}, cần {item['size_bytes']}.")
    actual = digest.hexdigest()
    for field in ("sha256", "upstream_sha256"):
        if item.get(field) and actual != item[field]:
            raise DownloadError(f"SHA-256 tải về lệch {field}; không ghi nhận file hay đổi hash.")
    partial.replace(path)
    return actual


def run(
    manifest: Path, *, only: str | None = None, verify: bool = False, report: Path | None = None
) -> dict:
    """Thực thi manifest, trả số byte/thời gian; verify không thay artifact/manifest."""
    started = perf_counter()
    root = models_dir()
    data = yaml.safe_load(manifest.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        raise DownloadError("Manifest cần models là danh sách.")
    models = data["models"]
    if any(not isinstance(model, dict) or not isinstance(model.get("id"), str) for model in models):
        raise DownloadError("Model entry cần id hợp lệ.")
    if len({model["id"] for model in models}) != len(models):
        raise DownloadError("id model bị trùng.")
    if only and only not in {model["id"] for model in models}:
        raise DownloadError(f"Không có model: {only}")
    protected = {manifest.resolve(), (ROOT / "models" / "README.md").resolve()}
    artifacts = set()
    for model in models:
        if not isinstance(model.get("files"), list):
            raise DownloadError("Model cần danh sách files.")
        for item in model["files"]:
            if not isinstance(item, dict):
                raise DownloadError("File entry không hợp lệ.")
            dest = _destination(root, model["id"], item.get("path", ""))
            partial = dest.with_name(dest.name + ".part").resolve()
            if (
                dest in protected
                or partial in protected
                or dest in artifacts
                or partial in artifacts
            ):
                raise DownloadError(
                    "Đích artifact/.part trùng manifest/README hoặc file model khác."
                )
            artifacts.update({dest, partial})
    if report is not None and report.resolve() in protected | artifacts:
        raise DownloadError("Đích report trùng manifest/README/artifact/.part; không ghi đè.")
    selected = []
    deferred = []
    for model in models:
        if only and model["id"] != only:
            continue
        if model.get("status") not in {"ready", "deferred", "blocked"}:
            raise DownloadError("Trạng thái model không hợp lệ.")
        if model["status"] == "blocked" and only:
            raise DownloadError(f"{only}: {model.get('note', 'chờ xác minh quyền trọng số')}")
        if not only and model["status"] != "ready":
            deferred.append(model["id"])
            print(f"! {model['id']}: {model.get('note', model['status'])}", flush=True)
            continue
        _validate(model, root)
        selected.append(model)
    if not selected:
        raise DownloadError("Không có model hợp lệ được chọn.")
    stats = {
        "mode": "verify" if verify else "download",
        "models_dir": str(root),
        "models": [m["id"] for m in selected],
        "deferred": deferred,
        "downloaded_bytes": 0,
        "installed_bytes": 0,
        "downloaded_files": 0,
        "skipped_files": 0,
    }
    for model in selected:
        for item in model["files"]:
            destination = _destination(root, model["id"], item["path"])
            if verify or (destination.exists() and item.get("sha256")):
                _check(destination, item)
                stats["skipped_files"] += 1
                print(f"✓ {model['id']}/{item['path']} đúng SHA-256", flush=True)
            else:
                print(
                    f"→ {model['id']}/{item['path']} ({item.get('size_bytes')} bytes)", flush=True
                )
                actual = _download(destination, item, stats)
                item["sha256"] = actual
                item["size_bytes"] = destination.stat().st_size
                _save_manifest(manifest, data)
                stats["downloaded_files"] += 1
                print(f"✓ SHA-256 {actual}", flush=True)
            stats["installed_bytes"] += destination.stat().st_size
    stats.update(elapsed_seconds=perf_counter() - started, date_utc=datetime.now(UTC).isoformat())
    return stats


def main(argv: list[str] | None = None) -> int:
    """CLI rõ lỗi/nonzero, không nạp mô hình hay chạm token người dùng."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--only", help="chỉ một id trong manifest, không tự tải dependency")
    parser.add_argument(
        "--verify", action="store_true", help="chỉ kiểm local SHA-256, không tải mạng"
    )
    parser.add_argument("--report", type=Path, help="ghi JSON thống kê lượt chạy khi thành công")
    args = parser.parse_args(argv)
    try:
        stats = run(args.manifest, only=args.only, verify=args.verify, report=args.report)
        serialized = json.dumps(stats, ensure_ascii=False, indent=2)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(serialized + "\n", encoding="utf-8")
        print(serialized, flush=True)
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        yaml.YAMLError,
        http.client.HTTPException,
    ) as exc:
        print(f"LỖI DATA-02: {exc}", file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        print(
            "Đã ngắt; file hoàn chỉnh giữ nguyên, .part chưa được ghi hash. Chạy lại cùng lệnh.",
            file=sys.stderr,
        )
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
