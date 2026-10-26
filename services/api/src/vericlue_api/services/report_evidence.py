"""Bounded illustrations from a hash-checked source snapshot, never model explanations."""

from __future__ import annotations

import base64
import hashlib
import math
import os
import re
import stat
import struct
import subprocess
import tempfile
import zlib
from dataclasses import dataclass
from html import escape
from pathlib import Path
from threading import BoundedSemaphore
from time import perf_counter
from typing import Literal

from vericlue_api.core.config import Settings
from vericlue_api.db.models import ForensicJobRow
from vericlue_api.schemas.forensic import ForensicJob
from vericlue_api.services.pdf_renderer import worker_environment

VERSION = "report-illustrations-v1"
MAX_SOURCE = 64 * 1024 * 1024
MAX_PNG = 384 * 1024
MAX_INTERVALS = 3
MAX_WINDOW = 3.0
TOTAL_SECONDS = 20.0
TOOL_SECONDS = 4.0
FORMATS = "mov,matroska,webm,wav,mp3,ogg,flac,aac"
_SLOT = BoundedSemaphore(1)


@dataclass(frozen=True)
class Illustration:
    caption: str
    png: bytes
    kind: Literal["frame", "spectrum"] = "frame"


@dataclass(frozen=True)
class ReportEvidence:
    figures: tuple[Illustration, ...] = ()
    notes: tuple[str, ...] = ()
    runtime: str | None = None

    def html(self) -> str:
        """Embed only generated PNG bytes; all captions/notes are escaped text."""
        figures = "".join(
            f'<figure class="report-illustration report-{figure.kind}">'
            f'<img alt="{escape(figure.caption, quote=True)}" '
            f'src="data:image/png;base64,{base64.b64encode(figure.png).decode("ascii")}">'
            f"<figcaption>{escape(figure.caption)}</figcaption></figure>"
            for figure in self.figures
        )
        return (
            '<section class="report-evidence"><h2>Ảnh và phổ minh họa</h2>'
            "<p>Minh họa nội dung vật chứng, không phải heatmap, bằng chứng mô hình "
            "chú ý hoặc kết luận về tính thật/giả. Chỉ hiển thị tối đa ba khoảng đầu.</p>"
            f"<p>Phương pháp: {VERSION}"
            + (f"; {escape(self.runtime)}" if self.runtime else "")
            + ".</p>"
            + figures
            + "".join(f"<p>{escape(note)}</p>" for note in self.notes)
            + "</section>"
        )


def _png(data: bytes) -> bytes:
    if not 24 <= len(data) <= MAX_PNG or data[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR":
        raise ValueError("Invalid illustration")
    width, height = struct.unpack(">II", data[16:24])
    if not (0 < width <= 1200 and 0 < height <= 720):
        raise ValueError("Illustration bounds")
    offset, has_pixels = 8, False
    while offset + 12 <= len(data):
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        end = offset + size + 12
        if end > len(data):
            break
        kind = data[offset + 4 : offset + 8]
        expected = struct.unpack(">I", data[end - 4 : end])[0]
        if zlib.crc32(data[offset + 4 : end - 4]) & 0xFFFFFFFF != expected:
            break
        has_pixels |= kind == b"IDAT"
        if kind == b"IEND":
            if size == 0 and end == len(data) and has_pixels:
                return data
            break
        offset = end
    raise ValueError("Incomplete illustration")


def _run(tool: Path, args: list[str], deadline: float) -> bytes:
    timeout = min(TOOL_SECONDS, deadline - perf_counter())
    if timeout <= 0:
        raise ValueError("Illustration deadline")
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    result = subprocess.run(
        [str(tool), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=timeout,
        check=False,
        env=worker_environment(),
        **options,
    )
    if result.returncode:
        raise ValueError("Illustration unavailable")
    return result.stdout


def _input(snapshot: Path, start: float, duration: float) -> list[str]:
    return [
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-max_alloc",
        "16777216",
        "-threads",
        "1",
        "-filter_threads",
        "1",
        "-filter_complex_threads",
        "1",
        "-protocol_whitelist",
        "file,pipe",
        "-format_whitelist",
        FORMATS,
        "-ss",
        f"{start:.6f}",
        "-t",
        f"{duration:.6f}",
        "-i",
        str(snapshot),
    ]


class ReportEvidenceBuilder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build(self, job: ForensicJob, row: ForensicJobRow) -> ReportEvidence | None:
        """Opt-in, server paths only; missing/changed sources yield explicit omissions."""
        if not self.settings.forensic_report_evidence:
            return None
        if job.status != "done" or row.payload.get("mode") != "real":
            return ReportEvidence(notes=("Chỉ trích minh họa cho job thật đã hoàn tất.",))
        if not job.suspect_intervals:
            return ReportEvidence(notes=("Không có khoảng nghi ngờ để trích minh họa.",))
        tool = Path(self.settings.forensic_report_ffmpeg or "")
        if not tool.is_absolute() or not tool.is_file():
            return ReportEvidence(notes=("Chưa cấu hình FFmpeg cho ảnh/phổ minh họa.",))
        if not _SLOT.acquire(blocking=False):
            return ReportEvidence(
                notes=("Đang trích minh họa báo cáo khác; lần xuất này chưa có ảnh/phổ.",)
            )
        try:
            return self._build(job, row, tool)
        except Exception:
            # Never include file paths, native errors, or a mismatched image in the report.
            return ReportEvidence(
                notes=("Chưa trích được minh họa từ nguồn khớp SHA-256 vật chứng.",)
            )
        finally:
            _SLOT.release()

    def _build(self, job: ForensicJob, row: ForensicJobRow, tool: Path) -> ReportEvidence:
        deadline = perf_counter() + TOTAL_SECONDS
        if row.job_id != job.job_id or not re.fullmatch(r"job_[A-Za-z0-9_-]{1,80}", job.job_id):
            raise ValueError("Invalid report source")
        # Exact server-owned folder; do not accept an arbitrary DB path or follow links.
        root = Path(self.settings.media_dir).resolve()
        expected = root / "forensic" / job.job_id
        source = Path(row.source_path or "")
        if not source.is_absolute():
            source = Path.cwd() / source
        if (
            not expected.resolve().is_relative_to(root)
            or source.parent.resolve() != expected.resolve()
        ):
            raise ValueError("Source outside job")
        for path in (root / "forensic", expected, source):
            if path.is_symlink() or path.is_junction():
                raise ValueError("Linked source")
        source_stat = source.stat(follow_symlinks=False)
        if not stat.S_ISREG(source_stat.st_mode) or not 0 < source_stat.st_size <= MAX_SOURCE:
            raise ValueError("Source bounds")
        # A private, immutable snapshot makes pre/post hash ABA races irrelevant.
        with tempfile.TemporaryDirectory(prefix="vericlue-report-") as directory:
            snapshot = Path(directory) / "source.bin"
            digest = hashlib.sha256()
            total = 0
            with source.open("rb") as incoming, snapshot.open("wb") as outgoing:
                while chunk := incoming.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_SOURCE or perf_counter() >= deadline:
                        raise ValueError("Source bounds")
                    digest.update(chunk)
                    outgoing.write(chunk)
            if (
                total == 0
                or digest.hexdigest() != job.file_sha256
                or row.file_sha256 != job.file_sha256
            ):
                raise ValueError("Source hash changed")
            runtime = (
                _run(tool, ["-version"], deadline).splitlines()[0].decode("ascii", "replace")[:200]
            )
            figures: list[Illustration] = []
            notes: list[str] = []
            for interval in job.suspect_intervals[:MAX_INTERVALS]:
                start, end = interval.t_start, interval.t_end
                if (
                    not math.isfinite(start)
                    or not math.isfinite(end)
                    or not 0 <= start < end <= 600
                ):
                    notes.append("Bỏ qua khoảng không có mốc thời gian hợp lệ.")
                    continue
                stop = min(end, start + MAX_WINDOW)
                if job.media and job.media.kind == "video":
                    point = (start + stop) / 2
                    try:
                        data = _run(
                            tool,
                            _input(snapshot, point, 1.0)
                            + [
                                "-map",
                                "0:v:0",
                                "-an",
                                "-frames:v",
                                "1",
                                "-vf",
                                "scale=640:360:force_original_aspect_ratio=decrease",
                                "-threads",
                                "1",
                                "-map_metadata",
                                "-1",
                                "-c:v",
                                "png",
                                "-f",
                                "image2pipe",
                                "pipe:1",
                            ],
                            deadline,
                        )
                        figures.append(
                            Illustration(
                                f"Khung hình tại mốc trích yêu cầu {point:g} s; đã thu nhỏ, không bảo đảm PTS chính xác.",
                                _png(data),
                            )
                        )
                    except Exception:
                        notes.append(f"Chưa trích được khung hình cho khoảng {start:g}-{stop:g} s.")
                try:
                    data = _run(
                        tool,
                        _input(snapshot, start, stop - start)
                        + [
                            "-filter_complex",
                            "[0:a:0]aresample=16000,aformat=channel_layouts=mono,"
                            "showspectrumpic=s=320x160:legend=1:color=viridis:scale=log:fscale=lin:win_func=hann[out]",
                            "-map",
                            "[out]",
                            "-frames:v",
                            "1",
                            "-threads",
                            "1",
                            "-map_metadata",
                            "-1",
                            "-c:v",
                            "png",
                            "-f",
                            "image2pipe",
                            "pipe:1",
                        ],
                        deadline,
                    )
                    figures.append(
                        Illustration(
                            f"Phổ âm {start:g}-{stop:g} s; mono 16 kHz, cửa sổ Hann, màu theo cường độ log. "
                            "Trục thời gian trong ảnh tính từ đầu đoạn trích; không phải xác suất giọng AI.",
                            _png(data),
                            kind="spectrum",
                        )
                    )
                except Exception:
                    notes.append(f"Chưa trích được phổ âm cho khoảng {start:g}-{stop:g} s.")
            if len(job.suspect_intervals) > MAX_INTERVALS:
                notes.append("Các khoảng còn lại không được minh họa trong lần xuất này.")
            return ReportEvidence(tuple(figures), tuple(notes), runtime)
