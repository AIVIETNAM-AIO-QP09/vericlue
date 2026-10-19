"""FACE-04 — sinh `ml/notebooks/finetune_pad.ipynb` từ code THẬT trong repo.

Notebook phải chạy trên Kaggle/Colab mà KHÔNG clone repo (repo private), nên script này nhúng
nguyên văn vào notebook:
- `ml/src/vericlue_ml/face/pad.py`: SCRFD (`ScrfdFaceFinder`) và MiniFASNet (`MiniFasNetClassifier`,
  cách cắt mặt) — để mô hình tinh chỉnh cắm lại hệ thống mà không lệch tiền xử lý;
- `ml/src/vericlue_ml/eval/metrics.py`: `auc`, `eer`, `bpcer`, `apcer_by_attack`;
- `ml/src/vericlue_ml/face/pad_tuning.py`: toàn bộ (lọc trùng, chia nhóm, khử lộ đề, chỉ số…);
- `models/manifest.yaml`: nguồn HF + revision + SHA-256 của minifasnet, scrfd-10g, arcface-mnet,
  dinov2-reg-base.
Commit nguồn và SHA-256 từng file nguồn được ghi vào ô đầu notebook.

Chạy lại mỗi khi sửa các file trên:  uv run --no-sync python scripts/build_pad_notebook.py
Test `ml/tests/test_pad_notebook.py` báo lỗi nếu notebook lệch code.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "ml" / "notebooks" / "finetune_pad.ipynb"
PAD_PY = "ml/src/vericlue_ml/face/pad.py"
METRICS_PY = "ml/src/vericlue_ml/eval/metrics.py"
TUNING_PY = "ml/src/vericlue_ml/face/pad_tuning.py"
MANIFEST = "models/manifest.yaml"
MODEL_IDS = ("minifasnet", "scrfd-10g", "arcface-mnet", "dinov2-reg-base")
PAD_NAMES = (
    "SECOND_FACE_AREA_RATIO",
    "PAD_CROP_SCALE",
    "DET_INPUT_SIZE",
    "DET_CONFIDENCE",
    "DET_NMS",
    "_STRIDES",
    "_ANCHORS_PER_CELL",
    "FaceBox",
    "_letterbox",
    "_nms",
    "ScrfdFaceFinder",
    "_softmax",
    "MiniFasNetClassifier",
)
METRIC_NAMES = ("_vectors", "_threshold", "apcer_by_attack", "bpcer", "auc", "eer")
COMMIT_PREFIX = "SOURCE_COMMIT = "

# Dữ liệu test phụ tải từ Hugging Face (công khai, không cần đăng nhập), ghim revision.
# Chọn tập con giống lần rà soát dữ liệu PAD ngày 19/10 (scratchpad dsresearch/scripts/dl.py).
AUX_HF = {
    "axon_display_replay": {
        "repo": "AxonData/Display_replay_attacks",
        "revision": "f5560f659e185ded62c2f09ff502426b0588406e",
        "license": "CC BY 4.0 (thẻ HF)",
        "limit": None,
    },
    "axon_print": {
        "repo": "AxonData/print-attack-dataset",
        "revision": "9a3f99429fbc0aefa764313c64e285b94d234acc",
        "license": "CC BY 4.0 (thẻ HF)",
        "limit": 5,
        "video_only": True,
    },
    "axon_cutprint": {
        "repo": "AxonData/Anti_Spoofing_Cut_print_attack",
        "revision": "efd7b1cfeb43952057ec4b353a4a9aefdebdc1a3",
        "license": "CC BY 4.0 (thẻ HF)",
        "limit": 5,
        "video_only": True,
    },
    "axon_replay_mobile": {
        "repo": "AxonData/Replay_attack_mobile",
        "revision": "5374f9db418da3b287287158b099207892f0fb06",
        "license": "CC BY 4.0 (thẻ HF)",
        "limit": 7,
        "every": 6,
    },
    "axon_3dpaper": {
        "repo": "AxonData/3D_paper_mask_attack_dataset_for_Liveness",
        "revision": "b50042b2d78ac7d3cd13fb1baa28a9d77ecef53e",
        "license": "CC BY 4.0 (thẻ HF)",
        "limit": 14,
        "video_only": True,
        "exclude": ["144.mp4"],
    },
    "axon_selfies": {
        "repo": "AxonData/face-anti-spoofing-dataset",
        "revision": "89d658fffa10ee93cc3010e53741d435fbadd3f6",
        "license": "CC BY-NC 4.0 (thẻ HF)",
        "limit": None,
        "prefix": "Selfies/",
    },
    "unidata_asian": {
        "repo": "UniqueData/asian-people-liveness-detection-video-dataset",
        "revision": "cc477c4b70e4c8829c7af5c6127fa2b1b69d7c0e",
        "license": "CC BY-NC-ND 4.0 (thẻ HF)",
        "limit": None,
        "prefix": "files/",
    },
}


# ── trích code ───────────────────────────────────────────────────────────────────────────
def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def _node_name(node: ast.stmt) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
        return node.name
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
        return target.id if isinstance(target, ast.Name) else None
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def extract(rel: str, names: tuple[str, ...]) -> str:
    """Lấy nguyên văn các định nghĩa cấp module theo tên (kể cả decorator), giữ thứ tự file."""
    source = _read(rel)
    lines = source.splitlines()
    tree = ast.parse(source)
    found: dict[str, str] = {}
    for node in tree.body:
        name = _node_name(node)
        if name in names:
            decorators = getattr(node, "decorator_list", [])
            start = min([node.lineno, *(d.lineno for d in decorators)])
            found[name] = "\n".join(lines[start - 1 : node.end_lineno])
    missing = [n for n in names if n not in found]
    if missing:
        raise SystemExit(f"{rel} không còn định nghĩa: {missing}")
    ordered = [found[n] for n in sorted(found, key=lambda n: source.index(found[n]))]
    return "\n\n\n".join(ordered)


def module_body(rel: str) -> str:
    """Toàn bộ module trừ `from __future__` và các import `vericlue_ml…` (đã nhúng ở ô trước)."""
    source = _read(rel)
    lines = source.splitlines()
    tree = ast.parse(source)
    drop: set[int] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and (
            node.module == "__future__" or (node.module or "").startswith("vericlue_ml")
        ):
            drop.update(range(node.lineno, node.end_lineno + 1))
    return "\n".join(line for i, line in enumerate(lines, 1) if i not in drop).strip()


def git_commit() -> tuple[str, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--", PAD_PY, METRICS_PY, TUNING_PY, MANIFEST],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return "unknown", True


def manifest_entries() -> dict[str, dict]:
    data = yaml.safe_load(_read(MANIFEST))
    out = {}
    for model in data["models"]:
        if model["id"] in MODEL_IDS:
            out[model["id"]] = {
                "repo": model["source"]["repo"],
                "revision": model["source"]["revision"],
                "license": model["license"],
                "files": [
                    {"path": f["path"], "url": f["url"], "sha256": f["sha256"]}
                    for f in model["files"]
                ],
            }
    missing = [m for m in MODEL_IDS if m not in out]
    if missing:
        raise SystemExit(f"models/manifest.yaml thiếu {missing}")
    return out


# ── nội dung notebook ────────────────────────────────────────────────────────────────────
INTRO = """# VeriClue — Tinh chỉnh PAD (chống ảnh chụp lại màn hình) trên FAS-VN · FACE-04

Notebook này **tự chạy từ đầu đến cuối** bằng nút **Run All** trên Kaggle (GPU T4/P100) hoặc Colab.
Không cần clone repo: mọi đoạn code cần thiết của hệ thống đã được **nhúng sẵn** (ô "NHÚNG TỪ REPO").

**Notebook làm gì**
1. Cài thư viện, tải trọng số từ Hugging Face đúng revision, **kiểm SHA-256**.
2. Kiểm kê FAS-VN (đếm, nhãn, phát hiện ảnh PNG mang đuôi `.jpg`).
3. **Làm sạch**: lọc trùng (SHA-256, dHash), bỏ ảnh mang 2 nhãn, dò mặt SCRFD (đệm viền khi trượt),
   gom người bằng ArcFace + union-find, **chia lại theo nhóm người**: train / calib_fit / calib_ltt / test.
4. **Khử lộ đề**: mọi ảnh đi cùng một đường (cắt mặt như hệ thống → resize → JPEG lại → không EXIF),
   rồi **kiểm**: mô hình chỉ nhìn siêu dữ liệu phải có AUC ≤ 0,6, nếu không notebook **DỪNG**.
5. Đo MiniFASNet gốc (trước tinh chỉnh) trên `calib_fit`.
6. Dạy 2 phương án: (a) MiniFASNet V2 dạy toàn bộ; (b) DINOv2-reg ViT-B/14 dạy vài khối cuối + lớp cuối.
7. Chọn phương án và checkpoint **chỉ trên `calib_fit`** (APCER tại BPCER ≤ 1 %, EER, AUC).
8. Đo test phụ (Axon theo loại tấn công, UniData, Zalo 2022) nếu có.
9. Kiểm cuối: **không bước nào chạm split `test`** (trưởng nhóm tự chạy test một lần sau khi chốt).
10. Xuất **một file zip** để gửi trưởng nhóm.

**Hướng dẫn từng nút bấm:** xem `ml/notebooks/README-pad.md` (trưởng nhóm gửi kèm).

> Dữ liệu FAS-VN: giấy phép trang Kaggle ghi CC BY 4.0 nhưng ảnh có vẻ lấy từ hệ thống eKYC thật →
> **chỉ dùng nghiên cứu, không phân phối lại, không đưa mặt người lên báo cáo/demo công khai.**
"""

CONFIG_MD = """## Bước 0 — Cấu hình

Thường **không cần sửa gì**. Muốn chạy thử nhanh (~10–15 phút) để kiểm tra mọi thứ trước khi chạy thật,
đổi `SMOKE = False` thành `SMOKE = True` ở dòng đầu ô dưới.
Notebook tự nhận đang ở Kaggle, Colab hay máy nhóm.
"""

CONFIG = r"""# Bước 0 — CẤU HÌNH. Chỉ sửa những dòng có chú thích "SỬA ĐƯỢC".
import csv
import io
import json
import math
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

SMOKE = False  # SỬA ĐƯỢC: True = chạy thử nhỏ (vài trăm ảnh, 1 epoch)
if os.environ.get("PAD_SMOKE") == "1":  # máy nhóm: chạy thử tự động
    SMOKE = True
SEED = 42  # giữ 42 để trưởng nhóm đối chiếu được file chia tập

IN_KAGGLE = Path("/kaggle/input").is_dir()
IN_COLAB = "google.colab" in sys.modules
ENV = "kaggle" if IN_KAGGLE else "colab" if IN_COLAB else "local"
USE_DRIVE = True  # SỬA ĐƯỢC (Colab): lưu kết quả + checkpoint vào Google Drive để chạy tiếp khi bị ngắt

if ENV == "kaggle":
    INPUT_ROOT = Path("/kaggle/input")
    OUT_DIR = Path("/kaggle/working")
elif ENV == "colab":
    INPUT_ROOT = Path("/content/data")
    if USE_DRIVE:
        from google.colab import drive

        drive.mount("/content/drive")
        OUT_DIR = Path("/content/drive/MyDrive/vericlue_pad")
    else:
        OUT_DIR = Path("/content/vericlue_pad")
else:  # máy nhóm (chạy thử): đường dẫn lấy từ biến môi trường
    INPUT_ROOT = Path(os.environ.get("PAD_INPUT_ROOT", "data/raw"))
    OUT_DIR = Path(os.environ.get("PAD_OUT_DIR", "pad_out"))
WORK = OUT_DIR / "pad_work"  # dữ liệu trung gian + checkpoint (giữ lại để chạy tiếp)
FASVN_DIR = os.environ.get("PAD_FASVN_DIR")  # để trống: tự tìm thư mục chứa train_photo/test_photo
LOCAL_MODELS_DIR = os.environ.get("PAD_LOCAL_MODELS_DIR")  # máy nhóm: dùng trọng số sẵn có nếu đúng SHA
AUX_DIRS = [Path(p) for p in os.environ.get("PAD_AUX_DIRS", "").split(os.pathsep) if p]
AUX_FROM_HF = os.environ.get("PAD_AUX_FROM_HF", "0" if ENV == "local" else "1") == "1"
AUX_MAX_FILES = 4 if SMOKE else None  # số file tối đa mỗi bộ test phụ (None = tất cả)

SMOKE_PER_FOLDER = 100  # chạy thử: số ảnh lấy ngẫu nhiên mỗi thư mục (4 thư mục)
JPEG_QUALITY = 90  # chất lượng JPEG chung khi khử lộ đề
DET_PAD_RATIO = 0.33  # đệm viền đen mỗi cạnh khi SCRFD trượt (ảnh cắt quá sát)
DHASH_DUP = 4  # dHash ≤ 4 và CÙNG nhãn → coi là trùng, giữ 1
DHASH_LINK = 8  # dHash ≤ 8 (mọi nhãn) → gom chung nhóm (cặp ảnh gốc / chụp lại)
ARC_THRESHOLD = 0.40  # cosine ArcFace ≥ 0,40 → cùng người (lỏng: thà gộp nhầm còn hơn tách sót)
MAX_GROUP_SHARE = 0.40  # nhóm lớn nhất > 40 % ảnh → dừng (ngưỡng quá lỏng)
FRACTIONS = {"train": 0.60, "calib_fit": 0.15, "calib_ltt": 0.10, "test": 0.15}
MAX_BPCER = 0.01  # chọn mô hình theo APCER tại BPCER ≤ 1 %
# Cỡ file JPEG SAU khi nén lại phản ánh độ nét/kết cấu của chính điểm ảnh (nội dung), không phải siêu
# dữ liệu; chạy thử 19/10 cho AUC ~0,66–0,73 dù chuẩn hóa cỡ mặt. Mặc định chỉ BÁO, không chặn (xem bàn giao FACE-04).
LEAK_GATE_FILE_SIZE = False

RUN_MINIFAS = True  # phương án (a)
RUN_DINO = True  # phương án (b)
EPOCHS_MINIFAS = 1 if SMOKE else 12  # SỬA ĐƯỢC
EPOCHS_DINO = 1 if SMOKE else 6  # SỬA ĐƯỢC
BATCH_MINIFAS = 64 if SMOKE else 256  # giảm nếu báo hết bộ nhớ GPU (CUDA out of memory)
BATCH_DINO = 16 if SMOKE else 48  # giảm xuống 24 hoặc 16 nếu báo hết bộ nhớ GPU
LR_MINIFAS = 2e-4
LR_DINO_BLOCKS = 2e-5
LR_DINO_HEAD = 1e-3
DINO_TRAIN_BLOCKS = 2  # số khối transformer cuối được dạy
DINO_SIZE = 224
EXPORT_DINO_ONNX = True  # thử xuất ONNX cho DINOv2 nếu nó thắng (lỗi thì vẫn có safetensors)
NUM_WORKERS = 0 if os.name == "nt" else 2
N_BOOT = 50 if SMOKE else 500  # số lần bootstrap theo nhóm người cho khoảng tin cậy

random.seed(SEED)
WORK.mkdir(parents=True, exist_ok=True)
CONFIG = {
    k: v
    for k, v in dict(globals()).items()
    if k.isupper()
    and k not in ("SOURCE_FILES", "MANIFEST", "AUX_HF")
    and isinstance(v, (int, float, str, bool, dict, type(None)))
}
CONFIG.update({"ENV": ENV, "WORK": str(WORK), "INPUT_ROOT": str(INPUT_ROOT)})
PREP_KEYS = ("SMOKE", "SEED", "SMOKE_PER_FOLDER", "JPEG_QUALITY", "DET_PAD_RATIO", "DHASH_DUP",
             "DHASH_LINK", "ARC_THRESHOLD", "FRACTIONS", "DINO_SIZE")  # fmt: skip
PREP_HASH = __import__("hashlib").sha256(
    json.dumps({k: CONFIG[k] for k in PREP_KEYS} | {"src": SOURCE_FILES}, sort_keys=True).encode()
).hexdigest()[:12]

# Thời gian ước tính trên Kaggle T4 khi chạy đầy đủ (~11.400 ảnh). Chạy thử (SMOKE) nhanh hơn nhiều.
ESTIMATES = {
    "1": "3–6 phút (tải ~380 MB trọng số)",
    "2": "1–2 phút",
    "3": "30–60 phút (đọc 8,9 GB ảnh, dò mặt, gom người)",
    "4": "1–2 phút",
    "5": "dưới 1 phút",
    "6a": "10–20 phút",
    "6b": "30–60 phút",
    "7": "dưới 1 phút",
    "8": "5–15 phút (tải ~1,7 GB video test phụ)",
    "9": "dưới 1 phút",
    "10": "1–3 phút",
}
TIMINGS: dict[str, float] = {}


@contextmanager
def step(key: str, title: str):
    est = ESTIMATES.get(key, "?") if not SMOKE else "chạy thử: nhanh"
    print(f"\n===== Bước {key}: {title} — ước tính {est} =====", flush=True)
    started = time.time()
    yield
    TIMINGS[key] = round(time.time() - started, 1)
    print(f"===== Xong bước {key} sau {TIMINGS[key] / 60:.1f} phút =====", flush=True)


# Chạy tiếp sau khi bị ngắt (Kaggle): nếu bạn đã "Add Input" output của lần chạy trước,
# sao chép pad_work cũ (dữ liệu đã làm sạch + checkpoint) để không phải làm lại từ đầu.
if ENV == "kaggle" and not (WORK / "prep_done.json").exists():
    for pattern in ("*/pad_work/prep_done.json", "*/*/pad_work/prep_done.json"):
        found = sorted(INPUT_ROOT.glob(pattern))
        if found:
            old = found[0].parent
            print(f"Thấy kết quả lần chạy trước ở {old} → sao chép để chạy tiếp…")
            shutil.copytree(old, WORK, dirs_exist_ok=True)
            break

print(f"Môi trường: {ENV} | SMOKE={SMOKE} | thư mục làm việc: {WORK}")
print("Ước tính thời gian từng bước (Kaggle T4, chạy đầy đủ):")
for key, est in ESTIMATES.items():
    print(f"  Bước {key:>3}: {est}")
print("  Tổng: khoảng 1,5–3 giờ. Notebook in thời gian thật sau mỗi bước.")
"""

EMBED_HEAD = """## Mã nhúng từ repo (KHÔNG sửa tay)

Ba ô dưới được `scripts/build_pad_notebook.py` chép nguyên văn từ repo. Muốn đổi thì sửa file gốc trong
repo rồi chạy lại script — để mô hình tinh chỉnh luôn dùng **đúng** tiền xử lý của hệ thống.
"""

PAD_PREAMBLE = """from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
from numpy.typing import ArrayLike, NDArray


class PadError(Exception):
    # Bản rút gọn của PadError trong pad.py (notebook không dùng ErrorCode).
    def __init__(self, message: str, code: object = None) -> None:
        super().__init__(message)
        self.code = code
"""

METRICS_PREAMBLE = """from sklearn.metrics import roc_auc_score, roc_curve
"""

STEP1 = r"""## Bước 1 — Cài thư viện, tải trọng số đúng revision và kiểm SHA-256

Kaggle/Colab đã có sẵn PyTorch. Ô này chỉ cài thêm vài gói nhỏ (phiên bản ghim) và tải trọng số từ
Hugging Face. Mỗi file được kiểm SHA-256 theo `models/manifest.yaml` của repo — sai là dừng.
"""

STEP1_CODE = r"""with step("1", "Cài thư viện và tải trọng số"):

    def pip(*args: str) -> None:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", *args], check=True)

    def probe(code: str) -> str:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else "ERR"

    if ENV != "local":
        pip("onnx==1.23.2", "safetensors>=0.4")
        has_cuda = "import onnxruntime as o; print('CUDAExecutionProvider' in o.get_available_providers())"
        if probe(has_cuda) != "True":
            subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "-q", "onnxruntime"])
            pip("onnxruntime-gpu==1.31.0")
        if probe("from transformers import Dinov2WithRegistersModel; print(1)") != "1":
            pip("transformers==4.57.6")
        if ENV == "colab":
            pip("kaggle==1.7.4.5")

    import cv2
    import numpy as np
    import onnx
    import sklearn
    import torch
    import transformers
    import onnxruntime as ort

    if hasattr(ort, "preload_dlls"):
        try:
            ort.preload_dlls()  # dùng thư viện CUDA đi kèm PyTorch
        except Exception as exc:  # noqa: BLE001
            print("preload_dlls:", exc)
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    VERSIONS = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "opencv": cv2.__version__,
        "torch": torch.__version__,
        "onnx": onnx.__version__,
        "onnxruntime": ort.__version__,
        "transformers": transformers.__version__,
        "sklearn": sklearn.__version__,
        "gpu": torch.cuda.get_device_name(0) if DEVICE == "cuda" else "none",
    }
    print(json.dumps(VERSIONS, indent=1))
    if DEVICE == "cpu":
        print("CẢNH BÁO: KHÔNG THẤY GPU. Kaggle: Settings → Accelerator → GPU T4 x2 (cần xác minh số điện thoại).")

    WEIGHTS = WORK / "weights"

    def sha256_file(path: Path) -> str:
        digest = __import__("hashlib").sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
        return digest.hexdigest()

    def fetch(model_id: str, filename: str) -> Path:
        entry = MANIFEST[model_id]
        spec = next(f for f in entry["files"] if f["path"] == filename)
        if LOCAL_MODELS_DIR:
            local = Path(LOCAL_MODELS_DIR) / model_id / filename
            if local.is_file() and sha256_file(local) == spec["sha256"]:
                print(f"  OK {model_id}/{filename} (có sẵn trên máy) sha256={spec['sha256']}")
                return local
        dest = WEIGHTS / model_id / filename
        if not dest.is_file() or sha256_file(dest) != spec["sha256"]:
            dest.parent.mkdir(parents=True, exist_ok=True)
            part = dest.with_name(dest.name + ".part")
            for attempt in range(1, 4):
                try:
                    print(f"  tải {model_id}/{filename} (lần {attempt})…", flush=True)
                    urllib.request.urlretrieve(spec["url"], part)
                    break
                except Exception as exc:  # noqa: BLE001
                    print("   lỗi tải:", exc)
                    time.sleep(10 * attempt)
            else:
                raise RuntimeError(
                    f"KHÔNG TẢI ĐƯỢC {model_id}/{filename} từ Hugging Face. Kiểm tra Settings → "
                    "Internet = On, rồi chạy lại. Nếu HF đang lỗi, thử lại sau 15 phút."
                )
            part.replace(dest)
        digest = sha256_file(dest)
        if digest != spec["sha256"]:
            dest.unlink()
            raise RuntimeError(f"SAI SHA-256 {model_id}/{filename}: {digest} ≠ {spec['sha256']}")
        print(f"  OK {model_id}/{filename} rev={entry['revision'][:8]} sha256={digest}")
        return dest

    PATH_MINIFAS = fetch("minifasnet", "minifasnet_v2.onnx")
    PATH_SCRFD = fetch("scrfd-10g", "det_10g.onnx")
    PATH_ARCFACE = fetch("arcface-mnet", "arcface_mnet.onnx")
    DINO_DIR = None
    if RUN_DINO:
        for name in ("config.json", "preprocessor_config.json", "model.safetensors"):
            DINO_DIR = fetch("dinov2-reg-base", name).parent

    def make_session(path: Path):
        options = ort.SessionOptions()
        options.log_severity_level = 3
        if "CUDAExecutionProvider" in ort.get_available_providers():
            try:
                session = ort.InferenceSession(
                    str(path), options, providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
                )
                if "CUDAExecutionProvider" in session.get_providers():
                    return session
            except Exception as exc:  # noqa: BLE001
                print("  ONNX CUDA lỗi, dùng CPU:", str(exc)[:200])
        return ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])

    SCRFD_SESSION = make_session(PATH_SCRFD)
    ARC_SESSION = make_session(PATH_ARCFACE)
    MINIFAS_SESSION = make_session(PATH_MINIFAS)
    FINDER = ScrfdFaceFinder(SCRFD_SESSION)  # đúng lớp của pad.py (chuẩn hóa uniface)
    MINI_SIZE = int(MINIFAS_SESSION.get_inputs()[0].shape[2])
    print("ONNX Runtime dùng:", SCRFD_SESSION.get_providers()[0], "| MiniFASNet vào", MINI_SIZE, "px")
    if SCRFD_SESSION.get_providers()[0] == "CPUExecutionProvider" and not SMOKE:
        print("LƯU Ý: dò mặt chạy CPU nên bước 3 có thể mất 60–90 phút. Vẫn chạy được, cứ để chạy.")
"""

STEP2_MD = """## Bước 2 — Kiểm kê dữ liệu FAS-VN

Kaggle: dataset **`maihongtng/face-anti-spoofing`** phải được "Add Input". Colab: notebook tự tải bằng
Kaggle API (cần 2 secret `KAGGLE_USERNAME`, `KAGGLE_KEY`).
"""

STEP2_CODE = r"""with step("2", "Kiểm kê dữ liệu FAS-VN"):
    if ENV == "colab" and not FASVN_DIR and not list(INPUT_ROOT.glob("*/Image/train_photo")):
        from google.colab import userdata

        os.environ["KAGGLE_USERNAME"] = userdata.get("KAGGLE_USERNAME")
        os.environ["KAGGLE_KEY"] = userdata.get("KAGGLE_KEY")
        target = INPUT_ROOT / "face-anti-spoofing"
        target.mkdir(parents=True, exist_ok=True)
        print("Tải FAS-VN (8,4 GB) bằng Kaggle API, khoảng 5–10 phút…", flush=True)
        subprocess.run(["kaggle", "datasets", "download", "-d", "maihongtng/face-anti-spoofing",
                        "-p", str(target), "--unzip"], check=True)  # fmt: skip

    def find_fasvn() -> Path | None:
        if FASVN_DIR:
            return Path(FASVN_DIR)
        for pattern in ("train_photo", "*/train_photo", "*/*/train_photo", "*/*/*/train_photo",
                        "*/*/*/*/train_photo"):  # fmt: skip
            hits = sorted(INPUT_ROOT.glob(pattern))
            if hits:
                return hits[0].parent
        return None

    FAS_ROOT = find_fasvn()
    if FAS_ROOT is None or not (FAS_ROOT / "train_photo").is_dir():
        raise RuntimeError(
            "KHÔNG TÌM THẤY FAS-VN. Kaggle: bấm 'Add Input' (cột phải) → ô tìm kiếm gõ "
            "'maihongtng/face-anti-spoofing' → bấm dấu + để thêm, rồi Run All lại. "
            "Colab: kiểm tra 2 secret KAGGLE_USERNAME và KAGGLE_KEY."
        )
    RE_A = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_face_image_live_", re.I)
    RE_B = re.compile(r"^(real|spoof)_\d+_", re.I)
    rows: list[dict] = []
    rng = random.Random(SEED)
    for orig_split in ("train_photo", "test_photo"):
        for label in ("live", "not_live"):
            folder = FAS_ROOT / orig_split / label
            files = sorted(p for p in folder.iterdir() if p.is_file())
            if SMOKE:
                files = sorted(rng.sample(files, min(SMOKE_PER_FOLDER, len(files))))
            for p in files:
                source = "A" if RE_A.match(p.name) else "B" if RE_B.match(p.name) else "other"
                rows.append({"rel_path": p.relative_to(FAS_ROOT).as_posix(), "label": label,
                             "orig_split": orig_split, "source": source})  # fmt: skip
    for r in rows:
        with open(FAS_ROOT / r["rel_path"], "rb") as handle:
            head = handle.read(16)
        r["fmt"] = sniff_format(head)
        r["ext_mismatch"] = int(extension_mismatch(r["rel_path"], r["fmt"]))
    N = len(rows)

    def table(keys):
        counts: dict = {}
        for r in rows:
            k = tuple(r[x] for x in keys)
            counts[k] = counts.get(k, 0) + 1
        for k in sorted(counts):
            print("   ", " | ".join(map(str, k)), ":", counts[k])

    print(f"FAS-VN ở {FAS_ROOT}: {N} ảnh" + (" (CHẠY THỬ: lấy mẫu)" if SMOKE else ""))
    print("  Theo thư mục gốc × nhãn × nguồn (A = ảnh tại quầy, B = selfie đánh số):")
    table(("orig_split", "label", "source"))
    print("  Định dạng thật:")
    table(("fmt",))
    print(f"  Ảnh sai đuôi (ví dụ PNG mang đuôi .jpg): {sum(r['ext_mismatch'] for r in rows)}")
    print("  Lưu ý: chia train/test GỐC của FAS-VN KHÔNG được dùng (trùng ảnh, cùng người, lộ đề).")
"""

STEP3_MD = """## Bước 3 — Làm sạch, gom người, chia lại tập

- Đọc từng ảnh **một lần**: SHA-256, dHash, dò mặt SCRFD (trượt thì đệm viền đen rồi dò lại), ArcFace
  (vector chỉ giữ trong RAM, không lưu), cắt mặt y hệt `pad.py` → JPEG lại (bước 4).
- Bỏ: ảnh hỏng, trùng byte (cùng file mang 2 nhãn → bỏ hết), gần trùng cùng nhãn (dHash ≤ 4),
  ảnh không thấy mặt, ảnh 2 mặt cỡ tương đương (hệ thống cũng không chấm những ảnh này).
- Gom nhóm người: dHash ≤ 8 (cặp ảnh gốc / ảnh chụp lại màn hình) **hoặc** ArcFace cos ≥ 0,40,
  nối bằng union-find. Mỗi nhóm nằm trọn ở **một** split.
- Lưu `splits.csv` (+ SHA-256) để trưởng nhóm đối chiếu. Ảnh cắt của split `test` bị xóa ngay.
"""

STEP3_CODE = r"""with step("3", "Làm sạch, gom người, chia lại tập"):
    from concurrent.futures import ThreadPoolExecutor

    PREP_MARKER = WORK / "prep_done.json"
    ROWS_CSV = WORK / "rows.csv"
    SPLITS_CSV = WORK / "splits.csv"
    INT_COLS = ("ext_mismatch", "decode_ok", "det_padded", "n_faces", "img_w", "img_h")
    FLOAT_PREFIX = ("o_", "m80_", "m224_", "box_")
    RESUMED = PREP_MARKER.exists() and json.loads(PREP_MARKER.read_text())["prep_hash"] == PREP_HASH
    if RESUMED:
        with open(ROWS_CSV, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        for r in rows:
            for k, v in list(r.items()):
                if k in INT_COLS:
                    r[k] = int(v) if v != "" else 0
                elif k.startswith(FLOAT_PREFIX):
                    r[k] = float(v) if v != "" else float("nan")
        N = len(rows)
        print(f"ĐÃ CÓ kết quả bước 3–4 từ lần chạy trước (prep_hash={PREP_HASH}) → bỏ qua, dùng lại.")
    else:
        N = len(rows)
        CROPS80 = np.lib.format.open_memmap(WORK / "crops80.npy", "w+", np.uint8, (N, MINI_SIZE, MINI_SIZE, 3))
        CROPS224 = np.lib.format.open_memmap(WORK / "crops224.npy", "w+", np.uint8, (N, DINO_SIZE, DINO_SIZE, 3))
        EMB = np.full((N, 512), np.nan, dtype=np.float32)  # chỉ trong RAM (điều kiện của arcface-mnet)
        ARC_IN = ARC_SESSION.get_inputs()[0].name

        def read_one(i: int):
            data = (FAS_ROOT / rows[i]["rel_path"]).read_bytes()
            img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)  # như pad.py
            if img is None:  # GIF hoặc ảnh OpenCV không đọc được → thử PIL
                try:
                    from PIL import Image

                    img = cv2.cvtColor(np.array(Image.open(io.BytesIO(data)).convert("RGB")), cv2.COLOR_RGB2BGR)
                except Exception:  # noqa: BLE001
                    img = None
            return i, data, img

        def prefetch(indices, depth: int = 8):
            with ThreadPoolExecutor(max_workers=4) as pool:
                pending = []
                for i in indices:
                    pending.append(pool.submit(read_one, i))
                    if len(pending) >= depth:
                        yield pending.pop(0).result()
                for fut in pending:
                    yield fut.result()

        started = time.time()
        for n_done, (i, data, img) in enumerate(prefetch(range(N)), 1):
            r = rows[i]
            r["sha256"] = sha256_bytes(data)
            for k, v in meta_features(data).items():
                r["o_" + k] = v  # siêu dữ liệu ẢNH GỐC (để so trước/sau khử lộ đề)
            r["decode_ok"] = int(img is not None)
            r.update({"dhash": "", "face_status": "decode_fail", "det_padded": 0, "n_faces": 0, "img_w": 0, "img_h": 0})
            if img is not None:
                r["img_h"], r["img_w"] = img.shape[:2]
                r["dhash"] = f"{dhash64(img):016x}"
                box, status, padded, n_faces = detect_face(FINDER, img, DET_PAD_RATIO)
                r.update({"face_status": status, "det_padded": int(padded), "n_faces": n_faces})
                if box is not None:
                    r.update({"box_x1": box.x1, "box_y1": box.y1, "box_x2": box.x2, "box_y2": box.y2, "box_conf": box.confidence})
                    aligned = arcface_align(img, box.landmarks)
                    blob = cv2.dnn.blobFromImage(aligned, 1 / 127.5, (112, 112), (127.5,) * 3, swapRB=True)
                    emb = ARC_SESSION.run(None, {ARC_IN: blob})[0].ravel()
                    EMB[i] = emb / max(float(np.linalg.norm(emb)), 1e-12)
                    c80, j80 = jpeg_roundtrip(pad_crop(img, box, MINI_SIZE), JPEG_QUALITY)
                    c224, j224 = jpeg_roundtrip(pad_crop(img, box, DINO_SIZE), JPEG_QUALITY)
                    CROPS80[i], CROPS224[i] = c80, c224
                    for k, v in meta_features(j80).items():
                        r["m80_" + k] = v
                    for k, v in meta_features(j224).items():
                        r["m224_" + k] = v
            if n_done % 250 == 0 or n_done == N:
                rate = n_done / max(time.time() - started, 1e-6)
                print(f"  {n_done}/{N} ảnh, {rate:.1f} ảnh/giây, còn ~{(N - n_done) / rate / 60:.1f} phút", flush=True)
        PREP_RATE = N / max(time.time() - started, 1e-6)

        # ── lọc ──
        labels = [r["label"] for r in rows]
        drop: dict[int, str] = {i: "decode_fail" for i, r in enumerate(rows) if not r["decode_ok"]}
        for i, why in exact_duplicates([r["sha256"] for r in rows], labels).items():
            drop.setdefault(i, why)
        hashes = [int(r["dhash"], 16) if r["dhash"] else 0 for r in rows]
        alive = [i for i in range(N) if i not in drop]
        for i, why in near_duplicate_drops(hashes, labels, alive, DHASH_DUP).items():
            drop.setdefault(i, why)
        for i, r in enumerate(rows):
            if i not in drop and r["face_status"] != "ok":
                drop[i] = r["face_status"]
        kept = [i for i in range(N) if i not in drop]

        # ── gom người ──
        local_pairs = [(a, b) for a, b, _ in hamming_pairs([hashes[i] for i in kept], DHASH_LINK)]
        n_dhash_links = len(local_pairs)
        n_cross_label_dhash = sum(labels[kept[a]] != labels[kept[b]] for a, b in local_pairs)
        arc_pairs = embedding_pairs(EMB[kept], ARC_THRESHOLD)
        del EMB
        group_local = link_groups([rows[i]["rel_path"] for i in kept], local_pairs + arc_pairs)
        sizes: dict[str, int] = {}
        for g in group_local:
            sizes[g] = sizes.get(g, 0) + 1
        largest = max(sizes.values()) if sizes else 0
        group_labels: dict[str, set] = {}
        for k, g in enumerate(group_local):
            group_labels.setdefault(g, set()).add(labels[kept[k]])
        both = {g for g, labs in group_labels.items() if len(labs) > 1}
        print(f"  Giữ {len(kept)}/{N} ảnh; {len(sizes)} nhóm người; nhóm lớn nhất {largest} ảnh")
        print(f"  Cặp dHash ≤ {DHASH_LINK}: {n_dhash_links} (khác nhãn: {n_cross_label_dhash}); cặp ArcFace ≥ {ARC_THRESHOLD}: {len(arc_pairs)}")
        if largest > MAX_GROUP_SHARE * max(len(kept), 1) and len(kept) >= 50:
            raise RuntimeError(
                f"DỪNG: nhóm người lớn nhất chiếm {largest}/{len(kept)} ảnh (> {MAX_GROUP_SHARE:.0%}), "
                "không chia được. Tăng ARC_THRESHOLD ở Bước 0 (ví dụ 0.45) rồi Run All lại."
            )
        split_of = assign_splits(group_local, [labels[i] for i in kept], FRACTIONS, SEED)
        for i, r in enumerate(rows):
            r["status"] = drop.get(i, "kept")
            r["group_id"], r["split"] = "", ""
        for k, i in enumerate(kept):
            rows[i]["group_id"] = group_local[k]
            rows[i]["split"] = split_of[group_local[k]]
        check_split_integrity([rows[i]["group_id"] for i in kept], [rows[i]["split"] for i in kept])

        # Xóa ngay ảnh cắt của split test: từ đây không bước nào được đọc chúng.
        test_idx = [i for i in kept if rows[i]["split"] == "test"]
        if test_idx:
            CROPS80[test_idx] = 0
            CROPS224[test_idx] = 0
        CROPS80.flush()
        CROPS224.flush()
        del CROPS80, CROPS224

        fields = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("rel_path", "label", "split"), k))
        with open(ROWS_CSV, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        split_cols = ["rel_path", "sha256", "label", "orig_split", "source", "fmt", "ext_mismatch", "status",
                      "group_id", "split", "det_padded", "box_x1", "box_y1", "box_x2", "box_y2"]  # fmt: skip
        with open(SPLITS_CSV, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=split_cols, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(sorted(rows, key=lambda r: r["rel_path"]))
        CLEAN_REPORT = {
            "n_images": N,
            "n_kept": len(kept),
            "dropped": {why: sum(1 for v in drop.values() if v == why) for why in sorted(set(drop.values()))},
            "n_groups": len(sizes),
            "largest_group": largest,
            "groups_with_both_labels": len(both),
            "dhash_link_pairs": n_dhash_links,
            "dhash_cross_label_pairs": n_cross_label_dhash,
            "arcface_pairs": len(arc_pairs),
            "det_padded_kept": sum(rows[i]["det_padded"] for i in kept),
            "prep_images_per_second": round(PREP_RATE, 2),
        }
        (WORK / "cleaning_report.json").write_text(json.dumps(CLEAN_REPORT, indent=1, ensure_ascii=False))

    CLEAN_REPORT = json.loads((WORK / "cleaning_report.json").read_text())
    SPLITS_SHA = sha256_file(SPLITS_CSV)
    CROPS80 = np.load(WORK / "crops80.npy", mmap_mode="r")
    CROPS224 = np.load(WORK / "crops224.npy", mmap_mode="r")
    print("Báo cáo làm sạch:", json.dumps(CLEAN_REPORT, indent=1, ensure_ascii=False))
    print("Phân bố sau khi chia (split × nhãn: số ảnh / số nhóm):")
    for s in ("train", "calib_fit", "calib_ltt", "test"):
        part = [r for r in rows if r["split"] == s]
        live = sum(r["label"] == "live" for r in part)
        print(f"  {s:10s}: {len(part):6d} ảnh (live {live}, not_live {len(part) - live}), {len({r['group_id'] for r in part})} nhóm")
    print(f"splits.csv: {SPLITS_CSV}  SHA-256={SPLITS_SHA}")
"""

STEP4_MD = """## Bước 4 — Khử lộ đề và kiểm lộ đề

Mọi ảnh (cả 2 lớp) đã đi cùng một đường ở bước 3: cắt mặt theo `pad.py` → resize → JPEG chất lượng 90
→ không EXIF. Ô dưới **huấn luyện mô hình chỉ dùng siêu dữ liệu** (cỡ ảnh, EXIF, định dạng, số segment,
bảng lượng tử JPEG…) trên ảnh ĐÃ xử lý của train + calib_fit, chia fold theo nhóm người.
**AUC phải ≤ 0,6**; lớn hơn thì notebook DỪNG.

Cỡ file JPEG sau nén lại được in riêng: nó đo độ nét/kết cấu của chính điểm ảnh (ảnh chụp lại màn hình
thường mờ hơn), tức là tín hiệu nội dung mà mô hình nào cũng thấy, nên mặc định chỉ báo chứ không chặn
(`LEAK_GATE_FILE_SIZE` ở Bước 0). Cũng in vài chẩn đoán khác (nguồn ảnh A/B, cỡ mặt) để trưởng nhóm biết.
"""

STEP4_CODE = r"""with step("4", "Khử lộ đề và kiểm lộ đề"):
    DEV_IDX = [i for i, r in enumerate(rows) if r["status"] == "kept" and r["split"] in ("train", "calib_fit")]
    assert_not_test((rows[i]["split"] for i in DEV_IDX), "kiểm lộ đề")
    y_attack = [int(rows[i]["label"] == "not_live") for i in DEV_IDX]
    groups_dev = [rows[i]["group_id"] for i in DEV_IDX]
    meta_keys = sorted(k[4:] for k in rows[DEV_IDX[0]] if k.startswith("m80_"))
    BEFORE = {k: univariate_auc([float(rows[i]["o_" + k]) for i in DEV_IDX], y_attack) for k in meta_keys}
    gate_keys = [k for k in meta_keys if LEAK_GATE_FILE_SIZE or k != "file_bytes"]
    feats = [{f"{p}{k}": float(rows[i][p + k]) for p in ("m80_", "m224_") for k in gate_keys} for i in DEV_IDX]
    LEAK = leak_auc(feats, y_attack, groups_dev, SEED)
    LEAK["gate_features"] = gate_keys
    LEAK["before_per_feature"] = BEFORE
    with_size = [{f"{p}{k}": float(rows[i][p + k]) for p in ("m80_", "m224_") for k in meta_keys} for i in DEV_IDX]
    LEAK["with_file_size"] = leak_auc(with_size, y_attack, groups_dev, SEED)
    LEAK["per_feature"].update(LEAK["with_file_size"]["per_feature"])
    # Chỉ để biết (KHÔNG chặn): những tín hiệu không phải siêu dữ liệu file nhưng vẫn có thể là lối tắt.
    def rel_face(i):
        r = rows[i]
        return math.sqrt(max(r["box_x2"] - r["box_x1"], 1) * max(r["box_y2"] - r["box_y1"], 1) / max(r["img_w"] * r["img_h"], 1))
    LEAK["diagnostic"] = {
        "nguon_A_hay_B": univariate_auc([float(rows[i]["source"] == "A") for i in DEV_IDX], y_attack),
        "phai_dem_vien_moi_thay_mat": univariate_auc([float(rows[i]["det_padded"]) for i in DEV_IDX], y_attack),
        "co_mat_tuong_doi": univariate_auc([rel_face(i) for i in DEV_IDX], y_attack),
    }
    print(f"Số ảnh dùng để kiểm: {len(DEV_IDX)}")
    print(f"{'đặc trưng':16s} {'AUC ảnh gốc':>12s} {'AUC sau xử lý (80 / 224)':>26s}")
    for k in meta_keys:
        print(f"{k:16s} {BEFORE[k]:12.3f} {LEAK['per_feature']['m80_' + k]:12.3f} / {LEAK['per_feature']['m224_' + k]:.3f}")
    print("Mô hình chỉ dùng siêu dữ liệu (sau xử lý, dùng để CHẶN):", {k: round(v, 3) for k, v in LEAK["models"].items()},
          "| đặc trưng:", gate_keys)
    size_auc = LEAK["with_file_size"]["model_auc"]
    print(f"Thêm cỡ file JPEG sau nén lại (tín hiệu NỘI DUNG: độ nét, kết cấu, moiré): AUC = {size_auc:.3f}"
          + ("" if LEAK_GATE_FILE_SIZE else " — chỉ báo, không chặn (LEAK_GATE_FILE_SIZE = False)"))
    print("Chẩn đoán thêm (không chặn):", {k: round(v, 3) for k, v in LEAK["diagnostic"].items()})
    if LEAK["model_auc"] > LEAK_AUC_MAX:
        raise RuntimeError(
            f"DỪNG: mô hình chỉ nhìn siêu dữ liệu vẫn đoán được nhãn (AUC = {LEAK['model_auc']:.3f} > {LEAK_AUC_MAX}). "
            "Kết quả tinh chỉnh sẽ không đáng tin. Hãy gửi màn hình này cho trưởng nhóm, KHÔNG chạy tiếp."
        )
    print(f"ĐẠT: AUC siêu dữ liệu = {LEAK['model_auc']:.3f} ≤ {LEAK_AUC_MAX}")
    (WORK / "leak_check.json").write_text(json.dumps(LEAK, indent=1))
    if not RESUMED:
        PREP_MARKER.write_text(json.dumps({"prep_hash": PREP_HASH, "n": N, "splits_sha256": SPLITS_SHA}))
"""

STEP5_MD = """## Bước 5 — Đo MiniFASNet GỐC (trước tinh chỉnh) trên calib_fit

Điểm tấn công = 1 − p_real (giống `score` của hệ thống). Chỉ số: AUC, EER, ngưỡng tại BPCER ≤ 1 % và
APCER ở ngưỡng đó; khoảng tin cậy 95 % bằng bootstrap **theo nhóm người**.
"""

STEP5_CODE = r"""with step("5", "Đo MiniFASNet gốc trên calib_fit"):
    USED: set[int] = set()  # mọi chỉ số ảnh đã được đọc để dạy/đo — bước 9 kiểm không có ảnh test

    def take_idx(split: str) -> list[int]:
        idx = [i for i, r in enumerate(rows) if r["status"] == "kept" and r["split"] == split]
        assert_not_test([split] + [rows[i]["split"] for i in idx], f"take_idx({split})")
        USED.update(idx)
        return idx

    IDX = {"train": take_idx("train"), "calib_fit": take_idx("calib_fit")}
    LIVE = {s: np.array([int(rows[i]["label"] == "live") for i in idx]) for s, idx in IDX.items()}
    GROUPS = {s: [rows[i]["group_id"] for i in idx] for s, idx in IDX.items()}

    def onnx_p_live(session, idx, batch: int = 256) -> np.ndarray:
        name_in, name_out = session.get_inputs()[0].name, session.get_outputs()[0].name
        out = []
        for s in range(0, len(idx), batch):
            x = np.asarray(CROPS80[idx[s : s + batch]]).astype(np.float32).transpose(0, 3, 1, 2)  # BGR, 0–255
            out.append(_softmax(session.run([name_out], {name_in: x})[0])[:, 1])  # nhãn 1 = thật
        return np.concatenate(out)

    def evaluate(p_live: np.ndarray, n_boot: int = N_BOOT) -> dict:
        return pad_metrics(1 - LIVE["calib_fit"], 1 - p_live, GROUPS["calib_fit"], MAX_BPCER, n_boot, SEED)

    SCORES = {"baseline": onnx_p_live(MINIFAS_SESSION, IDX["calib_fit"])}
    METRICS = {"baseline": evaluate(SCORES["baseline"])}
    HISTORY: dict[str, list] = {}

    def show(name: str, m: dict) -> None:
        ci = m.get("apcer_ci95")
        ci_txt = f" [{ci[0]:.3f}–{ci[1]:.3f}]" if ci else ""
        print(f"  {name:16s} AUC={m['auc']:.4f} EER={m['eer']:.4f} APCER@BPCER≤{MAX_BPCER:.0%}={m['apcer']:.4f}{ci_txt} "
              f"(ngưỡng {m['threshold_at_bpcer']:.4f}, BPCER {m['bpcer']:.4f}; live {m['n_live']}, tấn công {m['n_attack']})")

    show("MiniFASNet gốc", METRICS["baseline"])
"""

STEP6_MD = """## Bước 6 — Tinh chỉnh hai phương án

Tăng cường "camera trước điện thoại rẻ" (tối, nhiễu, mờ, thu nhỏ, JPEG 30–95, lật) áp cho **cả hai lớp**.
Sau mỗi epoch lưu checkpoint vào `pad_work/ckpt/` — nếu bị ngắt, chạy lại notebook sẽ **tự chạy tiếp**.

- **(a) MiniFASNet V2**: chạy đúng đồ thị ONNX gốc bằng PyTorch, dạy toàn bộ trọng số; đầu vào giữ y hệt
  `pad.py` (ảnh BGR 80×80, 0–255, không chuẩn hóa), đầu ra 3 lớp, lớp 1 = thật.
- **(b) DINOv2-reg ViT-B/14** (`facebook/dinov2-with-registers-base`, Apache-2.0): cùng vùng cắt mặt,
  224×224, chuẩn hóa ImageNet; chỉ dạy vài khối cuối + lớp cuối.
"""

STEP6_COMMON = r"""import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader, Dataset

MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def to_input(img: np.ndarray, kind: str):
    if kind == "minifas":  # y hệt MiniFasNetClassifier.p_real: BGR float32 0–255, NCHW
        return torch.from_numpy(np.ascontiguousarray(img.transpose(2, 0, 1)).astype(np.float32))
    rgb = (img[:, :, ::-1].astype(np.float32) / 255.0 - MEAN) / STD
    return torch.from_numpy(np.ascontiguousarray(rgb.transpose(2, 0, 1)))


class CropSet(Dataset):
    def __init__(self, kind: str, idx: list[int], live: np.ndarray, augment: bool) -> None:
        assert_not_test((rows[i]["split"] for i in idx), "CropSet")
        USED.update(idx)
        self.kind, self.idx, self.live, self.augment = kind, list(idx), live, augment
        self.path = WORK / ("crops80.npy" if kind == "minifas" else "crops224.npy")
        self.arr = None
        self.epoch = 0

    def __len__(self) -> int:
        return len(self.idx)

    def __getitem__(self, k: int):
        if self.arr is None:
            self.arr = np.load(self.path, mmap_mode="r")
        img = np.array(self.arr[self.idx[k]])
        if self.augment:
            img = phone_camera_augment(img, np.random.default_rng((SEED, self.epoch, int(self.idx[k]))))
        return to_input(img, self.kind), int(self.live[k])


def trainable_state(model) -> dict:
    names = {n for n, p in model.named_parameters() if p.requires_grad}
    return {k: v.detach().cpu().clone() for k, v in model.state_dict().items() if k in names}


def predict_p_live(model, kind: str, idx: list[int], batch: int) -> np.ndarray:
    loader = DataLoader(CropSet(kind, idx, np.zeros(len(idx)), False), batch_size=batch, num_workers=NUM_WORKERS)
    model.eval()
    out = []
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16, enabled=(kind == "dino" and DEVICE == "cuda")):
        for x, _ in loader:
            out.append(torch.softmax(model(x.to(DEVICE)).float(), dim=1)[:, 1].cpu().numpy())
    return np.concatenate(out)


def fit(name: str, model, groups_params, kind: str, epochs: int, batch: int, loss_fn) -> dict:
    ckdir = WORK / "ckpt" / name
    ckdir.mkdir(parents=True, exist_ok=True)
    last, best = ckdir / "last.pt", ckdir / "best.pt"
    data = CropSet(kind, IDX["train"], LIVE["train"], True)
    gen = torch.Generator().manual_seed(SEED)
    loader = DataLoader(data, batch_size=batch, shuffle=True, drop_last=len(data) > batch,
                        num_workers=NUM_WORKERS, generator=gen)  # fmt: skip
    opt = torch.optim.AdamW(groups_params, weight_decay=1e-4)
    total = max(1, epochs * len(loader))
    warm = max(1, len(loader) // 2)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / warm) * 0.5 * (1 + math.cos(math.pi * min(s, total) / total))
    )
    use_amp = kind == "dino" and DEVICE == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    state = {"epoch": 0, "history": [], "best_key": None, "best_epoch": None}
    if last.exists():
        ck = torch.load(last, map_location=DEVICE, weights_only=False)
        model.load_state_dict(ck["model"], strict=False)
        opt.load_state_dict(ck["opt"])
        sched.load_state_dict(ck["sched"])
        scaler.load_state_dict(ck["scaler"])
        state = ck["state"]
        print(f"  Chạy tiếp {name} từ checkpoint: đã xong {state['epoch']}/{epochs} epoch")
    for epoch in range(state["epoch"], epochs):
        data.epoch = epoch
        model.train()
        t0, seen, loss_sum = time.time(), 0, 0.0
        for step_i, (x, y) in enumerate(loader, 1):
            x, y = x.to(DEVICE, non_blocking=True), y.to(DEVICE)
            with torch.autocast("cuda", dtype=torch.float16, enabled=use_amp):
                logits = model(x)
            loss = loss_fn(logits.float(), y)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            seen += len(y)
            loss_sum += loss.item() * len(y)
            if step_i % 50 == 0:
                rate = seen / (time.time() - t0)
                print(f"    {name} epoch {epoch + 1} bước {step_i}/{len(loader)} loss {loss_sum / seen:.4f} "
                      f"({rate:.0f} ảnh/giây, epoch còn ~{(len(data) - seen) / rate / 60:.1f} phút)", flush=True)
        p = predict_p_live(model, kind, IDX["calib_fit"], batch * 2)
        m = evaluate(p, n_boot=0)
        record = {"epoch": epoch + 1, "loss": loss_sum / max(seen, 1), "seconds": round(time.time() - t0, 1),
                  **{k: m[k] for k in ("auc", "eer", "apcer", "bpcer", "threshold_at_bpcer")}}  # fmt: skip
        state["history"].append(record)
        key = list(selection_key(m))
        if state["best_key"] is None or key < state["best_key"]:
            state["best_key"], state["best_epoch"] = key, epoch + 1
            torch.save(trainable_state(model), best)
        state["epoch"] = epoch + 1
        torch.save({"model": trainable_state(model), "opt": opt.state_dict(), "sched": sched.state_dict(),
                    "scaler": scaler.state_dict(), "state": state}, last)  # fmt: skip
        print(f"  {name} epoch {epoch + 1}/{epochs}: loss {record['loss']:.4f} | calib_fit AUC {m['auc']:.4f} "
              f"EER {m['eer']:.4f} APCER@BPCER≤1% {m['apcer']:.4f} | {record['seconds'] / 60:.1f} phút", flush=True)
    model.load_state_dict(torch.load(best, map_location=DEVICE), strict=False)
    print(f"  {name}: chọn checkpoint epoch {state['best_epoch']} (theo calib_fit)")
    return state


n_live, n_attack = int(LIVE["train"].sum()), int((1 - LIVE["train"]).sum())
W_LIVE, W_ATTACK = len(LIVE["train"]) / (2 * max(n_live, 1)), len(LIVE["train"]) / (2 * max(n_attack, 1))
print(f"train: {n_live} live, {n_attack} not_live → trọng số lớp live {W_LIVE:.2f}, not_live {W_ATTACK:.2f}")
"""

STEP6A_CODE = r"""with step("6a", "Tinh chỉnh MiniFASNet V2 (toàn bộ)"):
    MINI_ONNX = onnx.load(str(PATH_MINIFAS))
    mini_model = build_torch_graph(onnx_to_ir(MINI_ONNX)).to(DEVICE)
    probe_x = np.asarray(CROPS80[IDX["calib_fit"][:8]]).astype(np.float32).transpose(0, 3, 1, 2)
    with torch.no_grad():
        diff = np.abs(mini_model.eval()(torch.from_numpy(probe_x).to(DEVICE)).cpu().numpy()
                      - MINIFAS_SESSION.run(None, {MINIFAS_SESSION.get_inputs()[0].name: probe_x})[0]).max()  # fmt: skip
    print(f"  Đồ thị PyTorch khớp ONNX gốc: lệch tối đa {diff:.2e}")
    assert diff < 1e-2, "Đồ thị PyTorch không khớp MiniFASNet gốc"
    if RUN_MINIFAS:
        HISTORY["minifasnet_ft"] = fit(
            "minifasnet_ft", mini_model, [{"params": list(mini_model.parameters()), "lr": LR_MINIFAS}],
            "minifas", EPOCHS_MINIFAS, BATCH_MINIFAS,
            lambda logits, y: binary_live_loss(logits, y, (W_LIVE, W_ATTACK)),
        )  # fmt: skip
        SCORES["minifasnet_ft"] = predict_p_live(mini_model, "minifas", IDX["calib_fit"], 512)
        METRICS["minifasnet_ft"] = evaluate(SCORES["minifasnet_ft"])
        show("MiniFASNet tinh chỉnh", METRICS["minifasnet_ft"])
"""

STEP6B_CODE = r"""with step("6b", "Tinh chỉnh DINOv2-reg ViT-B/14 (vài khối cuối)"):
    from transformers import Dinov2WithRegistersModel

    class DinoPad(nn.Module):
        def __init__(self, backbone) -> None:
            super().__init__()
            self.backbone = backbone
            self.n_reg = int(backbone.config.num_register_tokens)
            self.head = nn.Linear(2 * backbone.config.hidden_size, 2)  # lớp 1 = thật

        def forward(self, x):
            h = self.backbone(pixel_values=x).last_hidden_state
            return self.head(torch.cat([h[:, 0], h[:, 1 + self.n_reg :].mean(dim=1)], dim=1))

    if RUN_DINO:
        backbone = Dinov2WithRegistersModel.from_pretrained(str(DINO_DIR))
        for p in backbone.parameters():
            p.requires_grad = False
        tuned = list(backbone.encoder.layer[-DINO_TRAIN_BLOCKS:]) + [backbone.layernorm]
        for module in tuned:
            for p in module.parameters():
                p.requires_grad = True
        dino_model = DinoPad(backbone).to(DEVICE)
        n_train = sum(p.numel() for p in dino_model.parameters() if p.requires_grad)
        print(f"  Tham số được dạy: {n_train / 1e6:.1f} triệu / {sum(p.numel() for p in dino_model.parameters()) / 1e6:.1f} triệu")
        class_w = torch.tensor([W_ATTACK, W_LIVE], dtype=torch.float32, device=DEVICE)
        HISTORY["dinov2_ft"] = fit(
            "dinov2_ft", dino_model,
            [{"params": [p for m in tuned for p in m.parameters()], "lr": LR_DINO_BLOCKS},
             {"params": list(dino_model.head.parameters()), "lr": LR_DINO_HEAD}],
            "dino", EPOCHS_DINO, BATCH_DINO,
            lambda logits, y: F.cross_entropy(logits, y, weight=class_w),
        )  # fmt: skip
        SCORES["dinov2_ft"] = predict_p_live(dino_model, "dino", IDX["calib_fit"], BATCH_DINO * 2)
        METRICS["dinov2_ft"] = evaluate(SCORES["dinov2_ft"])
        show("DINOv2 tinh chỉnh", METRICS["dinov2_ft"])
"""

STEP7_MD = """## Bước 7 — Chọn phương án (CHỈ trên calib_fit)

Thứ tự ưu tiên: APCER tại BPCER ≤ 1 % thấp hơn → EER thấp hơn → AUC cao hơn.
`calib_ltt` và `test` KHÔNG được nhìn ở đây.
"""

STEP7_CODE = r"""with step("7", "Chọn phương án trên calib_fit"):
    CANDIDATES = [k for k in ("minifasnet_ft", "dinov2_ft") if k in METRICS]
    WINNER = min(CANDIDATES, key=lambda k: selection_key(METRICS[k])) if CANDIDATES else None
    names = {"baseline": "MiniFASNet gốc (trước)", "minifasnet_ft": "(a) MiniFASNet tinh chỉnh",
             "dinov2_ft": "(b) DINOv2-reg tinh chỉnh"}  # fmt: skip
    print(f"Bảng trước/sau trên calib_fit (live {METRICS['baseline']['n_live']}, tấn công "
          f"{METRICS['baseline']['n_attack']}, {METRICS['baseline'].get('n_groups', '?')} nhóm người):")
    print(f"  {'mô hình':28s} {'AUC':>7s} {'EER':>7s} {'APCER@BPCER≤1%':>15s} {'CI95 APCER':>17s}")
    for k, m in METRICS.items():
        ci = m.get("apcer_ci95") or [float("nan")] * 2
        mark = "  ← CHỌN" if k == WINNER else ""
        print(f"  {names[k]:28s} {m['auc']:7.4f} {m['eer']:7.4f} {m['apcer']:15.4f}   [{ci[0]:.3f}–{ci[1]:.3f}]{mark}")
    BEATS_BASELINE = bool(WINNER) and selection_key(METRICS[WINNER]) < selection_key(METRICS["baseline"])
    if not BEATS_BASELINE:
        print("LƯU Ý: phương án tinh chỉnh tốt nhất KHÔNG hơn MiniFASNet gốc trên calib_fit → nên giữ bản gốc.")
"""

STEP8_MD = """## Bước 8 — Test phụ (nếu có)

- **Axon** (ảnh in, ảnh in cắt, mặt nạ giấy 3D, phát lại màn hình/điện thoại) và **UniData Asian**
  (chỉ người thật → BPCER): tự tải mẫu nhỏ từ Hugging Face (công khai, ghim revision) khi Internet bật;
  hoặc Add Input một dataset Kaggle có tên chứa `axon` / `unique`.
- **Zalo 2022** (khẩu trang): Add Input `hlly34/liveness-detection-zalo-2022`. Thiếu thì bỏ qua.

Ngưỡng dùng ở đây là ngưỡng BPCER ≤ 1 % đã chọn trên calib_fit. Số mẫu rất nhỏ → chỉ để tham khảo.
"""

STEP8_CODE = r"""with step("8", "Đo test phụ"):
    VIDEO_EXT = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
    IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    sources: list[tuple[str, Path]] = []
    if INPUT_ROOT.is_dir():
        for d in sorted(INPUT_ROOT.iterdir()):
            low = d.name.lower()
            if d.is_dir() and ("axon" in low or "unique" in low or "unidata" in low):
                sources.append((low, d))
    for d in AUX_DIRS:
        for sub in sorted(d.iterdir()) if d.is_dir() else []:
            if sub.is_dir() and any(x in sub.name.lower() for x in ("axon", "unique", "unidata")):
                sources.append((sub.name.lower(), sub))
    if AUX_FROM_HF:
        from huggingface_hub import HfApi, hf_hub_download

        api = HfApi()
        for key, spec in AUX_HF.items():
            if any(k == key for k, _ in sources):
                continue
            try:
                files = sorted(api.list_repo_files(spec["repo"], repo_type="dataset", revision=spec["revision"]))
                files = [f for f in files if not f.startswith(".") and Path(f).suffix.lower() in VIDEO_EXT | IMAGE_EXT]
                if spec.get("prefix"):
                    files = [f for f in files if f.startswith(spec["prefix"])]
                if spec.get("video_only"):
                    files = [f for f in files if Path(f).suffix.lower() in VIDEO_EXT]
                files = [f for f in files if Path(f).name not in spec.get("exclude", [])]
                if spec.get("every"):
                    files = files[:: spec["every"]]
                if spec.get("limit"):
                    files = files[: spec["limit"]]
                if AUX_MAX_FILES:
                    files = files[:AUX_MAX_FILES]
                target = WORK / "aux" / key
                for f in files:
                    hf_hub_download(spec["repo"], f, repo_type="dataset", revision=spec["revision"], local_dir=target)
                sources.append((key, target))
                print(f"  tải {key}: {len(files)} file ({spec['repo']}@{spec['revision'][:8]}, {spec['license']})")
            except Exception as exc:  # noqa: BLE001
                print(f"  BỎ QUA {key}: không tải được ({str(exc)[:150]})")
    zalo_csv = None
    for pattern in ("*/label.csv", "*/*/label.csv", "*/*/*/label.csv"):
        for cand in sorted(INPUT_ROOT.glob(pattern)) + [c for d in AUX_DIRS for c in sorted(d.glob(pattern))]:
            with open(cand, encoding="utf-8", errors="ignore") as handle:
                if "liveness_score" in handle.readline():
                    zalo_csv = zalo_csv or cand

    def onnx_p_live_arr(session, crops):
        x = np.asarray(crops).astype(np.float32).transpose(0, 3, 1, 2)
        return _softmax(session.run(None, {session.get_inputs()[0].name: x})[0])[:, 1]
    def torch_p_live(model, kind, crops):
        model.eval()
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16, enabled=(kind == "dino" and DEVICE == "cuda")):
            x = torch.stack([to_input(c, kind) for c in crops]).to(DEVICE)
            return torch.softmax(model(x).float(), dim=1)[:, 1].cpu().numpy()
    models_live: dict = {"baseline": lambda c80, c224: onnx_p_live_arr(MINIFAS_SESSION, c80)}
    if "minifasnet_ft" in METRICS:
        models_live["minifasnet_ft"] = lambda c80, c224: torch_p_live(mini_model, "minifas", c80)
    if "dinov2_ft" in METRICS:
        models_live["dinov2_ft"] = lambda c80, c224: torch_p_live(dino_model, "dino", c224)

    def media_items():
        for key, root in sources:
            files = sorted(p for p in root.rglob("*") if p.is_file() and ".cache" not in p.parts
                           and p.suffix.lower() in VIDEO_EXT | IMAGE_EXT)  # fmt: skip
            if AUX_MAX_FILES:
                files = files[:AUX_MAX_FILES]
            for p in files:
                lab = aux_label_from_path(key, p.relative_to(root).as_posix())
                if lab:
                    yield ("unidata" if "uni" in key else "axon"), key, p, lab[0], lab[1]
        if zalo_csv is not None:
            with open(zalo_csv, newline="", encoding="utf-8") as handle:
                table = list(csv.DictReader(handle))
            by_label = {"1": [], "0": []}
            for t in table:
                by_label.setdefault(str(t["liveness_score"]).strip(), []).append(t)
            picked = table if not AUX_MAX_FILES else by_label["1"][:AUX_MAX_FILES] + by_label["0"][:AUX_MAX_FILES]
            for t in picked:
                p = zalo_csv.parent / "videos" / t["fname"]
                if p.is_file():
                    live = str(t["liveness_score"]).strip() == "1"
                    yield "zalo2022", "zalo2022", p, ("live" if live else "not_live"), ("bona_fide" if live else "replay_or_print")

    AUX_ROWS: list[dict] = []
    for dataset, key, path, label, attack in media_items():
        frames = video_frames(str(path)) if path.suffix.lower() in VIDEO_EXT else [cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)]
        for fi, img in enumerate(frames):
            if img is None:
                continue
            box, status, padded, _ = detect_face(FINDER, img, DET_PAD_RATIO)
            if box is None:
                AUX_ROWS.append({"dataset": dataset, "subset": key, "file": path.name, "frame": fi, "label": label, "attack": attack, "face": status})
                continue
            c80 = jpeg_roundtrip(pad_crop(img, box, MINI_SIZE), JPEG_QUALITY)[0]
            c224 = jpeg_roundtrip(pad_crop(img, box, DINO_SIZE), JPEG_QUALITY)[0]
            row = {"dataset": dataset, "subset": key, "file": path.name, "frame": fi, "label": label, "attack": attack, "face": "ok", "det_padded": int(padded)}
            for name, fn in models_live.items():
                row["attack_score_" + name] = float(1 - fn([c80], [c224])[0])
            AUX_ROWS.append(row)
    AUX_RESULTS: dict = {}
    if not AUX_ROWS:
        print("Không có dữ liệu test phụ (chưa Add Input / Internet tắt) → BỎ QUA, ghi chú trong card.md.")
    for dataset in sorted({r["dataset"] for r in AUX_ROWS}):
        part = [r for r in AUX_ROWS if r["dataset"] == dataset and r["face"] == "ok"]
        n_noface = sum(1 for r in AUX_ROWS if r["dataset"] == dataset and r["face"] != "ok")
        res = {"n_frames": len(part), "n_files": len({(r["subset"], r["file"]) for r in part}), "n_no_face": n_noface, "models": {}}
        y = np.array([int(r["label"] == "not_live") for r in part])
        for name in models_live:
            if not part:
                continue
            s = np.array([r["attack_score_" + name] for r in part])
            t = METRICS[name]["threshold_at_bpcer"]
            m = {"threshold_from_calib_fit": t}
            if (y == 0).any():
                m["bpcer"] = float(np.mean(s[y == 0] >= t))
            if (y == 1).any():
                m["apcer_by_attack"] = apcer_by_attack(y, s, [r["attack"] for r in part], t)
                m["n_by_attack"] = {a: sum(1 for r in part if r["attack"] == a) for a in m["apcer_by_attack"]}
            if len(set(y.tolist())) == 2:
                m["auc"] = auc(y, s)
            res["models"][name] = m
        AUX_RESULTS[dataset] = res
        print(f"\n  {dataset}: {res['n_frames']} khung từ {res['n_files']} file (không thấy mặt: {n_noface})")
        for name, m in res["models"].items():
            print(f"    {name:14s}", json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items() if k != 'threshold_from_calib_fit'}, ensure_ascii=False))
"""

STEP9_CODE = r"""with step("9", "Kiểm cuối: không chạm split test"):
    TEST_IDX = sorted(i for i, r in enumerate(rows) if r["split"] == "test")
    leaked = USED.intersection(TEST_IDX)
    assert not leaked, f"LỖI NGHIÊM TRỌNG: {len(leaked)} ảnh test đã bị đọc khi dạy/đo!"
    if TEST_IDX:
        assert int(np.asarray(CROPS80[TEST_IDX]).max()) == 0 and int(np.asarray(CROPS224[TEST_IDX]).max()) == 0
    print(f"OK: {len(USED)} ảnh đã dùng (train + calib_fit), 0 ảnh thuộc test ({len(TEST_IDX)} ảnh test chưa từng được dùng).")
    print("Trưởng nhóm sẽ chạy test MỘT lần trên máy sau khi chốt mô hình.")
"""

STEP10_MD = """## Bước 10 — Xuất kết quả (1 file zip)

Zip nằm trong thư mục output (Kaggle: tab **Output** bên phải, thư mục `/kaggle/working`).
Gồm: mô hình, SHA-256, `card.md`, `metrics.json`, `splits.csv`, điểm calib_fit, báo cáo làm sạch.
"""

STEP10_CODE = r"""with step("10", "Xuất kết quả"):
    import zipfile

    stamp = time.strftime("%Y%m%d-%H%M")
    EXP = OUT_DIR / f"pad_export_{stamp}{'_smoke' if SMOKE else ''}"
    EXP.mkdir(parents=True, exist_ok=True)
    EXPORTED: dict = {}
    if "minifasnet_ft" in METRICS:
        new = write_onnx_weights(MINI_ONNX, mini_model.initializer_arrays())
        onnx.checker.check_model(new)
        onnx.save(new, str(EXP / "minifasnet_v2_ft.onnx"))
        sess = ort.InferenceSession(str(EXP / "minifasnet_v2_ft.onnx"), providers=["CPUExecutionProvider"])
        same_io = ([(i.name, i.shape) for i in sess.get_inputs()] == [(i.name, i.shape) for i in MINIFAS_SESSION.get_inputs()]
                   and [(o.name, o.shape) for o in sess.get_outputs()] == [(o.name, o.shape) for o in MINIFAS_SESSION.get_outputs()])  # fmt: skip
        check = IDX["calib_fit"][:64]
        gap = float(np.abs(onnx_p_live(sess, check) - SCORES["minifasnet_ft"][: len(check)]).max())
        clf = MiniFasNetClassifier(sess)  # đúng lớp của pad.py nạp được file mới
        print(f"  minifasnet_v2_ft.onnx: đầu vào/ra giống bản gốc = {same_io}; lệch p_live ONNX vs PyTorch = {gap:.2e}; cỡ {clf._size}")
        assert same_io and gap < 1e-3
        EXPORTED["minifasnet_ft"] = {"file": "minifasnet_v2_ft.onnx", "same_io_as_original": same_io, "max_gap_vs_torch": gap,
                                     "best_epoch": HISTORY["minifasnet_ft"]["best_epoch"]}  # fmt: skip
    if "dinov2_ft" in METRICS:
        from safetensors.torch import save_file

        save_file({k: v.contiguous() for k, v in trainable_state(dino_model).items()}, str(EXP / "dinov2_pad_delta.safetensors"))
        dino_cfg = {
            "base_model": MANIFEST["dinov2-reg-base"]["repo"],
            "base_revision": MANIFEST["dinov2-reg-base"]["revision"],
            "trained_blocks": DINO_TRAIN_BLOCKS,
            "head": "Linear(2*hidden, 2) trên [CLS ‖ trung bình patch (bỏ 4 register)]; softmax[:,1] = p_real",
            "input": f"cắt mặt như pad.py (PAD_CROP_SCALE={PAD_CROP_SCALE}) → {DINO_SIZE}x{DINO_SIZE}, BGR→RGB, /255, chuẩn hóa ImageNet",
            "load": "backbone = Dinov2WithRegistersModel.from_pretrained(base, revision=base_revision); model = DinoPad(backbone); "
                    "model.load_state_dict(safetensors.torch.load_file('dinov2_pad_delta.safetensors'), strict=False)",
            "best_epoch": HISTORY["dinov2_ft"]["best_epoch"],
        }
        (EXP / "dinov2_pad_config.json").write_text(json.dumps(dino_cfg, indent=1, ensure_ascii=False))
        EXPORTED["dinov2_ft"] = {"file": "dinov2_pad_delta.safetensors", **dino_cfg}
        if WINNER == "dinov2_ft" and EXPORT_DINO_ONNX:
            try:
                dino_model.float().eval().cpu()
                emb = dino_model.backbone.embeddings
                probe = torch.from_numpy(np.stack([to_input(np.asarray(CROPS224[i]), "dino").numpy() for i in IDX["calib_fit"][:8]]))
                with torch.no_grad():
                    ref = torch.softmax(dino_model(probe), dim=1)[:, 1].numpy()
                    n_patch = (DINO_SIZE // dino_model.backbone.config.patch_size) ** 2
                    fixed_pos = emb.interpolate_pos_encoding(torch.zeros(1, 1 + n_patch, emb.position_embeddings.shape[-1]), DINO_SIZE, DINO_SIZE).clone()
                # Nội suy bicubic-antialias của vị trí không xuất ONNX được → cố định sẵn cho cỡ 224 (chỉ chạy 224×224).
                emb.interpolate_pos_encoding = lambda embeddings, height, width: fixed_pos.to(embeddings.dtype)
                torch.onnx.export(dino_model, torch.zeros(1, 3, DINO_SIZE, DINO_SIZE), str(EXP / "dinov2_pad.onnx"),
                                  input_names=["input"], output_names=["output"], opset_version=17,
                                  dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}}, dynamo=False)  # fmt: skip
                del emb.interpolate_pos_encoding
                dsess = ort.InferenceSession(str(EXP / "dinov2_pad.onnx"), providers=["CPUExecutionProvider"])
                got = _softmax(dsess.run(None, {"input": probe.numpy()})[0])[:, 1]
                dgap = float(np.abs(got - ref).max())
                print(f"  dinov2_pad.onnx: lệch p_live ONNX vs PyTorch = {dgap:.2e} (chỉ nhận ảnh {DINO_SIZE}×{DINO_SIZE})")
                if dgap > 1e-3:
                    raise ValueError(f"ONNX lệch PyTorch {dgap:.2e}")
                EXPORTED["dinov2_ft"].update({"onnx": "dinov2_pad.onnx", "onnx_max_gap_vs_torch": dgap})
            except Exception as exc:  # noqa: BLE001
                (EXP / "dinov2_pad.onnx").unlink(missing_ok=True)
                EXPORTED["dinov2_ft"]["onnx_error"] = str(exc)[:300]
                print("  Không xuất được ONNX cho DINOv2 (vẫn có safetensors):", str(exc)[:200])

    with open(EXP / "calib_fit_scores.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rel_path", "group_id", "label"] + [f"attack_score_{k}" for k in SCORES])
        for n, i in enumerate(IDX["calib_fit"]):
            writer.writerow([rows[i]["rel_path"], rows[i]["group_id"], rows[i]["label"]] + [f"{1 - SCORES[k][n]:.6f}" for k in SCORES])
    if AUX_ROWS:
        with open(EXP / "aux_scores.csv", "w", newline="", encoding="utf-8") as handle:
            keys = sorted({k for r in AUX_ROWS for k in r})
            writer = csv.DictWriter(handle, fieldnames=keys)
            writer.writeheader()
            writer.writerows(AUX_ROWS)
    for name in ("splits.csv", "cleaning_report.json", "leak_check.json"):
        shutil.copy2(WORK / name, EXP / name)

    model_sha = {f.name: sha256_file(f) for f in sorted(EXP.iterdir()) if f.suffix in (".onnx", ".safetensors")}
    METRICS_JSON = {
        "task": "FACE-04", "smoke": SMOKE, "env": ENV, "source_commit": SOURCE_COMMIT, "source_dirty": SOURCE_DIRTY,
        "source_files_sha256": SOURCE_FILES, "manifest": MANIFEST, "versions": VERSIONS, "config": CONFIG,
        "dataset": {"name": "FAS-VN", "kaggle": "maihongtng/face-anti-spoofing", "license_page": "CC BY 4.0 (đáng ngờ — chỉ nghiên cứu)",
                    "splits_csv_sha256": SPLITS_SHA, "counts": {s: {lab: sum(1 for r in rows if r["split"] == s and r["label"] == lab)
                    for lab in ("live", "not_live")} for s in ("train", "calib_fit", "calib_ltt", "test")}},
        "cleaning": CLEAN_REPORT, "leak_check": {k: LEAK[k] for k in ("model_auc", "models", "gate_features", "per_feature", "before_per_feature", "diagnostic", "with_file_size")},
        "calib_fit": METRICS, "history": {k: v["history"] for k, v in HISTORY.items()},
        "selection": {"rule": "min (APCER@BPCER<=1%, EER, -AUC) trên calib_fit", "winner": WINNER, "beats_baseline": BEATS_BASELINE},
        "aux": AUX_RESULTS, "exported": EXPORTED, "model_sha256": model_sha, "timings_seconds": TIMINGS,
    }  # fmt: skip
    (EXP / "metrics.json").write_text(json.dumps(METRICS_JSON, indent=1, ensure_ascii=False, default=str))

    def fmt(m, k):
        v = m.get(k)
        return "—" if v is None else f"{v:.4f}"

    lines = [
        f"# Thẻ mô hình — PAD tinh chỉnh trên FAS-VN ({'CHẠY THỬ, KHÔNG DÙNG' if SMOKE else 'chạy đầy đủ'})",
        "",
        f"- Task: FACE-04. Notebook `ml/notebooks/finetune_pad.ipynb`, commit nguồn `{SOURCE_COMMIT}`" + (" (có sửa chưa commit)" if SOURCE_DIRTY else ""),
        f"- Chạy lúc {stamp} trên {ENV} ({VERSIONS['gpu']}); seed {SEED}; torch {VERSIONS['torch']}, onnxruntime {VERSIONS['onnxruntime']}",
        f"- Phương án thắng trên calib_fit: **{WINNER}**; hơn MiniFASNet gốc: **{'có' if BEATS_BASELINE else 'không'}**",
        "",
        "## Dữ liệu",
        f"- FAS-VN (`maihongtng/face-anti-spoofing`), {CLEAN_REPORT['n_images']} ảnh đọc, giữ {CLEAN_REPORT['n_kept']} sau làm sạch; bỏ: {CLEAN_REPORT['dropped']}",
        f"- Gom người: {CLEAN_REPORT['n_groups']} nhóm (dHash ≤ {DHASH_LINK} hoặc ArcFace cos ≥ {ARC_THRESHOLD}); nhóm lớn nhất {CLEAN_REPORT['largest_group']} ảnh",
        f"- Chia lại theo nhóm (seed {SEED}): " + ", ".join(f"{s} {sum(METRICS_JSON['dataset']['counts'][s].values())}" for s in ("train", "calib_fit", "calib_ltt", "test")),
        f"- `splits.csv` SHA-256 `{SPLITS_SHA}`. Split `test` CHƯA được dùng.",
        f"- Khử lộ đề: cắt mặt như pad.py → resize → JPEG q{JPEG_QUALITY}, không EXIF. AUC mô hình chỉ siêu dữ liệu = {LEAK['model_auc']:.3f} (ngưỡng ≤ {LEAK_AUC_MAX}); thêm cỡ file JPEG (tín hiệu nội dung) = {LEAK['with_file_size']['model_auc']:.3f}",
        "",
        "## Kết quả trên calib_fit (chọn mô hình chỉ ở đây)",
        "| Mô hình | AUC | EER | APCER @ BPCER ≤ 1 % | CI95 APCER (bootstrap theo nhóm) | Ngưỡng |",
        "|---|---|---|---|---|---|",
    ]
    for k, m in METRICS.items():
        ci = m.get("apcer_ci95")
        lines.append(f"| {k} | {fmt(m, 'auc')} | {fmt(m, 'eer')} | {fmt(m, 'apcer')} | {'—' if not ci else f'{ci[0]:.3f}–{ci[1]:.3f}'} | {fmt(m, 'threshold_at_bpcer')} |")
    lines += ["", f"Số mẫu calib_fit: live {METRICS['baseline']['n_live']}, tấn công {METRICS['baseline']['n_attack']}, {METRICS['baseline'].get('n_groups', '?')} nhóm người.", ""]
    lines += ["## Test phụ (tham khảo, n nhỏ)", ""]
    if AUX_RESULTS:
        for d, res in AUX_RESULTS.items():
            lines.append(f"- {d}: {res['n_frames']} khung / {res['n_files']} file — " + json.dumps(res["models"], ensure_ascii=False, default=float))
    else:
        lines.append("- Không chạy (chưa có dữ liệu test phụ).")
    lines += [
        "",
        "## Tham số",
        f"- (a) MiniFASNet V2: dạy toàn bộ, AdamW lr {LR_MINIFAS}, {EPOCHS_MINIFAS} epoch, batch {BATCH_MINIFAS}; đầu vào/ra giữ nguyên ONNX gốc.",
        f"- (b) DINOv2-reg ViT-B/14 `{MANIFEST['dinov2-reg-base']['repo']}@{MANIFEST['dinov2-reg-base']['revision'][:8]}`: dạy {DINO_TRAIN_BLOCKS} khối cuối + layernorm + đầu tuyến tính, lr {LR_DINO_BLOCKS}/{LR_DINO_HEAD}, {EPOCHS_DINO} epoch, batch {BATCH_DINO}, fp16.",
        "- Tăng cường giống camera trước điện thoại rẻ cho cả 2 lớp: tối, nhiễu, mờ, thu nhỏ, JPEG 30–95, lật.",
        "",
        "## Giới hạn (bắt buộc đọc)",
        "- FAS-VN gần như **chỉ có tấn công chụp lại màn hình**; **thiếu ảnh in giấy, ảnh in cắt, mặt nạ** → mô hình chưa được dạy các kiểu này (xem Axon ở test phụ).",
        "- Giấy phép FAS-VN đáng ngờ (trang ghi CC BY 4.0 nhưng ảnh có vẻ từ hệ thống eKYC thật): **chỉ dùng nghiên cứu**, không phân phối lại, không đưa mặt người lên báo cáo/demo công khai.",
        "- Ảnh live nguồn A chủ yếu chụp tại quầy, không phải selfie; nguồn ảnh tương quan với nhãn (xem `leak_check.json` → diagnostic).",
        "- Nhóm người suy từ ArcFace + dHash (không có mã người thật); có thể còn sót người trùng giữa các split.",
        "- SCRFD `det_10g` và ArcFace `arcface-mnet`: giấy phép nghiên cứu phi thương mại.",
        "- Số đo calib_fit KHÔNG phải kết quả test. Kết quả R1 chỉ có sau khi trưởng nhóm chạy split `test` một lần.",
    ]
    if SMOKE:
        lines.insert(2, "> **CHẠY THỬ (SMOKE)**: vài trăm ảnh, 1 epoch — số liệu không có giá trị, chỉ để kiểm notebook chạy được.\n")
    (EXP / "card.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    sums = [f"{sha256_file(f)}  {f.name}" for f in sorted(EXP.iterdir()) if f.is_file() and f.name != "SHA256SUMS.txt"]
    (EXP / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")
    ZIP = OUT_DIR / f"{EXP.name}.zip"
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(EXP.iterdir()):
            zf.write(f, f"{EXP.name}/{f.name}")
    print(f"\nXONG. File cần gửi trưởng nhóm: {ZIP} ({ZIP.stat().st_size / 1e6:.1f} MB)")
    print("Kaggle: mở tab Output (cột phải) → bấm vào file .zip → Download. Colab: file nằm trong Google Drive/vericlue_pad.")
    print("Thời gian từng bước (phút):", {k: round(v / 60, 1) for k, v in TIMINGS.items()})
"""


def build_cells(commit: str, dirty: bool) -> list[tuple[str, str]]:
    sources = {rel: _sha(rel) for rel in (PAD_PY, METRICS_PY, TUNING_PY, MANIFEST)}
    header = (
        (
            "# === NGUỒN (sinh bởi scripts/build_pad_notebook.py — KHÔNG sửa tay) ===\n"
            f"{COMMIT_PREFIX}{commit!r}\n"
            f"SOURCE_DIRTY = {dirty!r}  # True = file nguồn có sửa chưa commit lúc sinh notebook\n"
            f"SOURCE_FILES = {json.dumps(sources, indent=1)}\n"
            f"MANIFEST = {json.dumps(manifest_entries(), indent=1, ensure_ascii=False)}\n"
            f"AUX_HF = {json.dumps(AUX_HF, indent=1, ensure_ascii=False)}\n"
        )
        .replace(": null", ": None")
        .replace(": true", ": True")
        .replace(": false", ": False")
    )

    def banner(rel: str) -> str:
        return (
            f"# === NHÚNG TỪ {rel} @ {commit[:12]} (sha256 {sources[rel][:16]}…) ===\n"
            "# KHÔNG sửa tay: sửa file trong repo rồi chạy scripts/build_pad_notebook.py.\n"
        )

    pad_cell = banner(PAD_PY) + PAD_PREAMBLE + "\n\n" + extract(PAD_PY, PAD_NAMES) + "\n"
    metrics_cell = (
        banner(METRICS_PY) + METRICS_PREAMBLE + "\n\n" + extract(METRICS_PY, METRIC_NAMES) + "\n"
    )
    tuning_cell = banner(TUNING_PY) + module_body(TUNING_PY) + "\n"
    return [
        ("markdown", INTRO),
        ("code", header),
        ("markdown", CONFIG_MD),
        ("code", CONFIG),
        ("markdown", EMBED_HEAD),
        ("code", pad_cell),
        ("code", metrics_cell),
        ("code", tuning_cell),
        ("markdown", STEP1),
        ("code", STEP1_CODE),
        ("markdown", STEP2_MD),
        ("code", STEP2_CODE),
        ("markdown", STEP3_MD),
        ("code", STEP3_CODE),
        ("markdown", STEP4_MD),
        ("code", STEP4_CODE),
        ("markdown", STEP5_MD),
        ("code", STEP5_CODE),
        ("markdown", STEP6_MD),
        ("code", STEP6_COMMON),
        ("code", STEP6A_CODE),
        ("code", STEP6B_CODE),
        ("markdown", STEP7_MD),
        ("code", STEP7_CODE),
        ("markdown", STEP8_MD),
        ("code", STEP8_CODE),
        ("markdown", "## Bước 9 — Kiểm cuối: không bước nào chạm split `test`\n"),
        ("code", STEP9_CODE),
        ("markdown", STEP10_MD),
        ("code", STEP10_CODE),
    ]


def build_notebook(commit: str, dirty: bool) -> dict:
    cells = []
    for n, (kind, text) in enumerate(build_cells(commit, dirty)):
        lines = text.strip("\n").split("\n")
        source = [line + "\n" for line in lines[:-1]] + [lines[-1]]
        cell = {"cell_type": kind, "id": str(n), "metadata": {}, "source": source}
        if kind == "code":
            cell.update({"execution_count": None, "outputs": []})
        cells.append(cell)
    return {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
            "kaggle": {"accelerator": "gpu", "isGpuEnabled": True, "isInternetEnabled": True},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def render(nb: dict) -> str:
    return json.dumps(nb, indent=1, ensure_ascii=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=NOTEBOOK)
    parser.add_argument("--commit", help="ghi commit này thay cho git HEAD")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    commit, dirty = git_commit()
    if args.commit:
        commit = args.commit
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(build_notebook(commit, dirty)), encoding="utf-8", newline="\n")
    print(f"Đã ghi {args.out} (commit nguồn {commit[:12]}{' + sửa chưa commit' if dirty else ''})")


if __name__ == "__main__":
    main()
