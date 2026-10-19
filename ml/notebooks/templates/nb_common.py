"""Tiện ích dùng chung cho notebook GenD (Kaggle / Colab / máy Linux). Được nhúng vào notebook.

Không phải code sản phẩm: chỉ nhận diện nền tảng, cài gói, chạy lệnh có ghi log, đo VRAM, tải file có
kiểm SHA-256 và quản lý ngân sách thời gian của phiên.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import threading
import time
from pathlib import Path

GB = 1024**3


def detect_platform() -> str:
    """'kaggle' | 'colab' | 'local'."""
    if os.environ.get("KAGGLE_KERNEL_RUN_TYPE") or Path("/kaggle/working").is_dir():
        return "kaggle"
    if "google.colab" in sys.modules or os.environ.get("COLAB_RELEASE_TAG"):
        return "colab"
    return "local"


def default_dirs(platform: str, name: str) -> tuple[Path, Path]:
    """(OUT: kết quả cần GIỮ, WORK: nháp có thể mất). Biến môi trường VC_OUT/VC_WORK ghi đè."""
    if os.environ.get("VC_OUT"):
        out = Path(os.environ["VC_OUT"])
    elif platform == "kaggle":
        out = Path("/kaggle/working") / name
    elif platform == "colab":
        out = Path("/content/drive/MyDrive/vericlue") / name
    else:
        out = Path.cwd() / "vc_out" / name
    if os.environ.get("VC_WORK"):
        work = Path(os.environ["VC_WORK"])
    elif platform == "kaggle":
        work = Path("/kaggle/tmp/vc_work") if Path("/kaggle/tmp").is_dir() else Path("/tmp/vc_work")
    elif platform == "colab":
        work = Path("/content/vc_work")
    else:
        work = Path.cwd() / "vc_work"
    out.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    return out, work


def mount_colab_drive() -> None:
    from google.colab import drive  # type: ignore[import-not-found]

    drive.mount("/content/drive")


def _has_pip(python: str) -> bool:
    return subprocess.run([python, "-m", "pip", "--version"], capture_output=True).returncode == 0


def pip_install(packages: list[str], python: str | None = None, extra: list[str] | None = None):
    """Cài gói vào môi trường `python` (mặc định kernel). Có pip thì dùng pip, không thì `uv pip`."""
    python = python or sys.executable
    if _has_pip(python):
        cmd = [python, "-m", "pip", "install", "-q", *packages, *(extra or [])]
    else:
        cmd = [ensure_uv(), "pip", "install", "-q", "-p", python, *packages, *(extra or [])]
    run(cmd)


def ensure_import(module: str, package: str | None = None) -> None:
    """Thiếu module trong kernel thì cài (không đụng gói đã có sẵn của Kaggle/Colab)."""
    import importlib

    try:
        importlib.import_module(module)
    except ImportError:
        pip_install([package or module])


def ensure_uv() -> str:
    found = shutil.which("uv")
    if found:
        return found
    local = Path.home() / ".local" / "bin" / "uv"
    if local.is_file():
        return str(local)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "uv"], check=True)
    found = shutil.which("uv") or str(Path(sys.executable).parent / "uv")
    return found


def run(cmd, *, cwd=None, env=None, log: Path | None = None, timeout: float | None = None):
    """Chạy lệnh; lỗi thì ném RuntimeError kèm 40 dòng cuối log (tiếng Việt)."""
    cmd = [str(c) for c in cmd]
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with open(log, "a", encoding="utf-8") if log else open(os.devnull, "w") as handle:
        handle.write(f"\n$ {' '.join(cmd)}\n")
        handle.flush()
        process = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=timeout,
        )
        handle.write(process.stdout or "")
    if process.returncode != 0:
        tail = "\n".join((process.stdout or "").splitlines()[-40:])
        raise RuntimeError(
            f"Lệnh lỗi (mã {process.returncode}, {time.time() - started:.0f} s): {' '.join(cmd[:6])} …\n{tail}"
        )
    return process


def gpu_info() -> dict:
    try:
        out = (
            subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,driver_version",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            .stdout.strip()
            .splitlines()[0]
        )
        name, total, driver = (x.strip() for x in out.split(","))
        return {"name": name, "total_mb": int(float(total)), "driver": driver}
    except Exception:  # noqa: BLE001
        return {"name": "none", "total_mb": 0, "driver": ""}


def gpu_used_mb() -> int:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return int(float(out.strip().splitlines()[0]))
    except Exception:  # noqa: BLE001
        return 0


class GpuMonitor:
    """Đo đỉnh VRAM toàn GPU (nvidia-smi) trong khi một lệnh chạy; `peak_mb` trừ mức nền lúc bắt đầu."""

    def __init__(self, interval: float = 0.5) -> None:
        self.interval = interval
        self.baseline = 0
        self.peak = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> GpuMonitor:
        self.baseline = gpu_used_mb()
        self.peak = self.baseline
        self.started = time.time()
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()
        return self

    def _poll(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, gpu_used_mb())
            self._stop.wait(self.interval)

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self.seconds = time.time() - self.started

    @property
    def peak_mb(self) -> int:
        return max(0, self.peak - self.baseline)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, dst: Path, sha256: str | None = None, retries: int = 4) -> Path:
    """Tải về `dst` (bỏ qua nếu đã có và đúng SHA-256). Sai SHA-256 thì DỪNG."""
    import requests

    dst = Path(dst)
    if dst.is_file() and (sha256 is None or sha256_file(dst) == sha256):
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    for attempt in range(retries):
        try:
            with requests.get(url, stream=True, timeout=120) as response:
                response.raise_for_status()
                with open(tmp, "wb") as handle:
                    for chunk in response.iter_content(1 << 20):
                        handle.write(chunk)
            break
        except Exception as exc:  # noqa: BLE001
            if attempt == retries - 1:
                raise RuntimeError(f"Không tải được {url}: {exc}") from exc
            time.sleep(5 * (attempt + 1))
    if sha256 is not None:
        actual = sha256_file(tmp)
        if actual != sha256:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"SHA-256 sai cho {dst.name}: {actual} ≠ {sha256}")
    os.replace(tmp, dst)
    return dst


def manifest_files(manifest: dict, model_id: str) -> tuple[dict, list[dict]]:
    entry = next(m for m in manifest["models"] if m["id"] == model_id)
    return entry, entry["files"]


def fetch_manifest_model(
    manifest: dict, model_id: str, models_dir: Path, only: list[str] | None = None
):
    """Tải file của một mô hình theo `models/manifest.yaml` (đúng revision) và kiểm SHA-256."""
    entry, files = manifest_files(manifest, model_id)
    for item in files:
        if only and item["path"] not in only:
            continue
        download(item["url"], Path(models_dir) / model_id / item["path"], item["sha256"])
    return entry


def git_clone(url: str, ref: str, dst: Path) -> Path:
    """Clone đúng commit/tag (idempotent)."""
    dst = Path(dst)
    if (dst / ".git").is_dir():
        head = subprocess.run(
            ["git", "-C", str(dst), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
        if (
            head.startswith(ref)
            or ref
            in subprocess.run(
                ["git", "-C", str(dst), "tag", "--points-at", "HEAD"],
                capture_output=True,
                text=True,
            ).stdout.split()
        ):
            return dst
    if dst.exists():
        shutil.rmtree(dst)
    run(["git", "clone", "-q", url, str(dst)])
    run(["git", "-C", str(dst), "checkout", "-q", ref])
    return dst


def venv_python(env_dir: Path) -> str:
    env_dir = Path(env_dir)
    for candidate in (env_dir / "bin" / "python", env_dir / "Scripts" / "python.exe"):
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(f"Không thấy python trong {env_dir}")


def make_venv(env_dir: Path, python_version: str) -> str:
    env_dir = Path(env_dir)
    if not (env_dir / "pyvenv.cfg").is_file():
        run([ensure_uv(), "venv", "-q", "-p", python_version, str(env_dir)])
    return venv_python(env_dir)


def nvidia_lib_env(python: str, base: dict | None = None) -> dict:
    """Môi trường chạy cho venv: thêm thư viện CUDA/cuDNN của các wheel `nvidia-*` vào LD_LIBRARY_PATH."""
    env = dict(base or os.environ)
    site = subprocess.run(
        [python, "-c", "import site;print(site.getsitepackages()[0])"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    libs = sorted(glob.glob(os.path.join(site, "nvidia", "*", "lib")))
    if libs:
        env["LD_LIBRARY_PATH"] = os.pathsep.join([*libs, env.get("LD_LIBRARY_PATH", "")])
    return env


def ensure_ffmpeg(work: Path) -> tuple[str, str]:
    """(ffmpeg, ffprobe). Kaggle/Colab có sẵn; máy thiếu thì tải bản tĩnh (johnvansickle, GPL) vào WORK/bin.
    ffmpeg chỉ chạy như chương trình rời, không nhúng vào sản phẩm."""
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe
    bin_dir = Path(work) / "bin"
    if not (bin_dir / "ffmpeg").is_file():
        archive = download(
            "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
            Path(work) / "ffmpeg-static.tar.xz",
        )
        bin_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                if member.name.endswith(("/ffmpeg", "/ffprobe")):
                    member.name = Path(member.name).name
                    tar.extract(member, bin_dir)
    os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
    return str(bin_dir / "ffmpeg"), str(bin_dir / "ffprobe")


def ffmpeg_version(ffmpeg: str) -> str:
    return subprocess.run([ffmpeg, "-version"], capture_output=True, text=True).stdout.splitlines()[
        0
    ]


def find_inputs(pattern: str, roots: list[str] | None = None) -> list[Path]:
    """Tìm file khớp mẫu trong các thư mục input (Kaggle: /kaggle/input; Colab: Drive)."""
    roots = roots or ["/kaggle/input", "/content/drive/MyDrive/vericlue", str(Path.cwd())]
    found: list[Path] = []
    for root in roots:
        if Path(root).is_dir():
            found.extend(Path(p) for p in glob.glob(os.path.join(root, pattern), recursive=True))
    return sorted(set(found))


class Budget:
    """Ngân sách thời gian của phiên (Kaggle tối đa 12 giờ): dừng sạch trước khi hết."""

    def __init__(self, hours: float) -> None:
        self.deadline = time.time() + hours * 3600

    def left_h(self) -> float:
        return (self.deadline - time.time()) / 3600

    def ok(self, need_minutes: float = 5) -> bool:
        return time.time() + need_minutes * 60 < self.deadline


def write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def disk_free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / GB
