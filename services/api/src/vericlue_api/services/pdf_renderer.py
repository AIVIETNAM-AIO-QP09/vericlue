"""Optional bounded Node/Chromium PDF worker; no server secrets in the child environment."""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
from contextlib import suppress
from pathlib import Path
from threading import BoundedSemaphore

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.core.pdf_bundle import MAX_PDF_BYTES

MAX_HTML_BYTES = 4 * 1024 * 1024
_SLOT = BoundedSemaphore(1)
_ENV = {
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
    "DISPLAY",
    "XDG_RUNTIME_DIR",
    "PLAYWRIGHT_BROWSERS_PATH",
    "LANG",
    "LC_ALL",
}


def worker_environment() -> dict[str, str]:
    """Do not forward API/master keys, staff tokens, proxy settings or NODE_OPTIONS."""
    return {key: value for key, value in os.environ.items() if key.upper() in _ENV}


def _stop_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        killer = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "taskkill.exe"
        subprocess.run(
            [str(killer), "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    else:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
    process.kill()


class PdfRenderer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def render(self, html: str) -> bytes:
        """Render trusted server HTML only; one worker per API process, bounded deadline."""
        node = Path(self.settings.forensic_pdf_node or "")
        module = Path(self.settings.forensic_pdf_playwright_dir or "")
        if not (
            node.is_absolute()
            and node.is_file()
            and module.is_absolute()
            and (module / "package.json").is_file()
        ):
            raise ApiError(503, "pdf_unavailable", "Chức năng xuất PDF chưa sẵn sàng.")
        if len(html.encode("utf-8")) > MAX_HTML_BYTES:
            raise ApiError(503, "pdf_unavailable", "Báo cáo vượt giới hạn xuất PDF.")
        if not _SLOT.acquire(blocking=False):
            raise ApiError(503, "pdf_busy", "Đang xuất báo cáo khác. Vui lòng thử lại.")
        process = None
        try:
            timeout = self.settings.forensic_pdf_timeout_seconds
            packet = json.dumps(
                {"html": html, "module_dir": str(module), "timeout_ms": int(timeout * 1000)},
                ensure_ascii=False,
            ).encode("utf-8")
            worker = Path(__file__).resolve().parents[1] / "workers" / "render_report.cjs"
            options = (
                {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
                if os.name == "nt"
                else {"start_new_session": True}
            )
            process = subprocess.Popen(
                [str(node), str(worker)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=worker_environment(),
                **options,
            )
            try:
                pdf, _ = process.communicate(packet, timeout=timeout + 5)
            except subprocess.TimeoutExpired:
                _stop_tree(process)
                process.communicate(timeout=5)
                raise ValueError("PDF worker timeout") from None
            if (
                process.returncode != 0
                or not pdf.startswith(b"%PDF-")
                or not 0 < len(pdf) <= MAX_PDF_BYTES
            ):
                raise ValueError("Invalid PDF output")
            return pdf
        except Exception as exc:
            if process is not None and process.poll() is None:
                try:
                    _stop_tree(process)
                    process.communicate(timeout=5)
                except Exception:
                    logging.getLogger(__name__).warning("pdf_worker_cleanup_failed")
            raise ApiError(503, "pdf_unavailable", "Chưa thể xuất PDF lúc này.") from exc
        finally:
            _SLOT.release()
