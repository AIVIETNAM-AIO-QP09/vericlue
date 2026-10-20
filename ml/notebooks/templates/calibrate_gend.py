# ruff: noqa: E402, F821  (khuôn notebook: import theo ô; SOURCE_* do ô nhúng định nghĩa)
# %% [markdown]
# # FACE-04 — Hiệu chỉnh điểm GenD (calibration, KHÔNG dạy lại mô hình)
#
# Notebook này chấm điểm bằng **GenD gốc** (đúng `face/gend.py`) rồi fit **calibrator** để điểm thô
# thành xác suất, nhằm giảm chuyện người Việt thật bị đẩy sang bước đọc câu oan.
#
# - **Lớp thật (dùng để fit):** người Việt thật FAS-VN `live` (Kaggle `maihongtng/face-anti-spoofing`,
#   CC BY 4.0, ảnh tĩnh → GenD chấm 1 khung) + video gốc RTFS-10k (cùng nguồn với lớp giả).
# - **VLR** (Zenodo 19705466, video bài giảng đã căn mặt) mặc định TẮT (`USE_VLR = False`). Bật thì
#   chỉ báo phân bố điểm để THAM KHẢO, KHÔNG dùng để fit hay chọn gì (quyết định trưởng nhóm 20/10).
# - **Lớp giả:** video ghép mặt RTFS-10k (Kaggle `stplusplus/rtfs-10k`, CC BY-SA 4.0). Nhóm KHÔNG tự
#   tạo deepfake. Không có deepfake người Việt — giới hạn này được ghi vào `card.md`.
# - Mọi mẫu đi cùng một đường: cắt khung vuông quanh mặt → 320×320 → H.264 CRF 23, 25 fps.
# - Chia theo nhóm (người/video gốc/ảnh donor) thành `calib_fit` / `calib_ltt` / `test`.
#   Calibrator chỉ fit trên `calib_fit`. `calib_ltt` chỉ lưu điểm (ROUT-03 chọn ngưỡng sau).
#   **Tập test KHÔNG được đọc** (hàm test tắt mặc định).
#
# Hướng dẫn chạy cho người không chuyên: `ml/notebooks/README-gend.md`.
# **Chạy SMOKE = True trước (≈ 10–15 phút), xong mới đặt SMOKE = False và Run All.**

# %%
# ===================== CẤU HÌNH (chỉ sửa ô này) =====================
SMOKE = True  # True: chạy thử nhỏ để kiểm. False: chạy thật.
SEED = 20261019
DEVICE = "cuda"  # "cuda" hoặc "cpu"

# VLR: chỉ tham khảo, không dùng để fit. Mặc định TẮT cho nhanh (bật thì tải thêm từ Zenodo).
USE_VLR = False

# Số mẫu khi chạy THẬT (SMOKE = False). None = lấy hết.
VLR_PARTS = ["part1", "part2", "part3", "part4", "part5", "part6"]  # bỏ part7 theo trưởng nhóm
VLR_VIDEOS_PER_PART = 40
VLR_CLIPS_PER_VIDEO = 3
N_FAS_LIVE = 800
N_RTFS_REAL = 400
N_RTFS_FAKE = 1200
ARCFACE_THRESHOLD = 0.35  # gom người lỏng tay (thà gộp nhầm còn hơn tách sót)

if SMOKE:
    VLR_PARTS = ["part1"]
    VLR_VIDEOS_PER_PART = 8
    VLR_CLIPS_PER_VIDEO = 2
    N_FAS_LIVE = 24
    N_RTFS_REAL = 12
    N_RTFS_FAKE = 24

# Tập test: chỉ trưởng nhóm bật, MỘT lần, sau khi đã chốt calibrator.
RUN_TEST = False
TEST_CONFIRMATION = ""

# %% [embed]

# %%
# ===================== 0. Thông tin môi trường (gửi kèm khi báo lỗi) =====================
import json as _json

import nb_common as nb

ENV_INFO = nb.environment_report()
print(_json.dumps(ENV_INFO, ensure_ascii=False, indent=1))

# %%
# ===================== 1. Môi trường =====================
import csv
import json
import os
import shutil
import time
import zipfile
from collections import Counter
from pathlib import Path

import nb_common as nb

T0 = time.time()
PLATFORM = nb.detect_platform()
if PLATFORM == "colab":
    nb.mount_colab_drive()
OUT, WORK = nb.default_dirs(PLATFORM, "calibrate_gend" + ("_smoke" if SMOKE else ""))
MODELS = WORK / "models"
for module, package in (
    ("onnxruntime", "onnxruntime-gpu" if DEVICE == "cuda" else "onnxruntime"),
    ("safetensors", None),
    ("transformers", None),
    ("cv2", "opencv-python-headless"),
    ("yaml", "pyyaml"),
    ("pydantic", None),
    ("sklearn", "scikit-learn"),
):
    nb.ensure_import(module, package)
FFMPEG, _ = nb.ensure_ffmpeg(WORK)
os.environ["MODELS_DIR"] = str(MODELS)
os.environ["DEVICE"] = DEVICE
GPU = nb.gpu_info()
print(f"Nền tảng: {PLATFORM} | GPU: {GPU['name']} ({GPU['total_mb']} MB) | SMOKE={SMOKE}")
print(f"Kết quả giữ lại: {OUT}\nNháp: {WORK} | ffmpeg: {nb.ffmpeg_version(FFMPEG)}")
STEP_TIMES: dict[str, float] = {}


def step_done(name: str, started: float) -> None:
    STEP_TIMES[name] = round(time.time() - started, 1)
    nb.write_json(OUT / "step_times.json", STEP_TIMES)
    print(f"✔ {name}: {STEP_TIMES[name] / 60:.1f} phút")


# %%
# ===================== 2. Trọng số (đúng revision, kiểm SHA-256) =====================
import yaml

from vericlue_ml.face.gend import FaceDeepfakeDetector
from vericlue_ml.finetune import data04 as d4
from vericlue_ml.finetune import gend_calib as gc
from vericlue_ml.finetune import gend_train as gt

started = time.time()
MANIFEST = yaml.safe_load(Path(os.environ["ML_MODELS_MANIFEST"]).read_text(encoding="utf-8"))
nb.fetch_manifest_model(MANIFEST, "gend-clip-l14", MODELS)
nb.fetch_manifest_model(
    MANIFEST, "clip-vit-large-patch14", MODELS, only=["config.json", "preprocessor_config.json"]
)
nb.fetch_manifest_model(MANIFEST, "scrfd-10g", MODELS)
nb.download(gc.ARCFACE["url"], MODELS / gc.ARCFACE["id"] / gc.ARCFACE["path"], gc.ARCFACE["sha256"])
DETECTOR = FaceDeepfakeDetector(MODELS)
DETECTOR.preload(device=DEVICE)  # kiểm SHA-256 lần nữa và dựng GenD như hệ thống thật
MODEL_VERSION = DETECTOR.version
assert MODEL_VERSION == gc.EXPECTED_MODEL_VERSION, f"Sai phiên bản mô hình: {MODEL_VERSION}"
import onnxruntime as ort

from vericlue_ml.common.device import onnx_providers

ARCFACE_SESSION = ort.InferenceSession(
    str(MODELS / gc.ARCFACE["id"] / gc.ARCFACE["path"]),
    providers=onnx_providers(DEVICE, component="arcface"),
)
print("Mô hình:", MODEL_VERSION)
step_done("2_trong_so", started)

# %%
# ===================== 3. Tìm dữ liệu (Kaggle: Add Input; Colab: tải bằng Kaggle API) =====================
import requests


def kaggle_auth() -> dict:
    """Header xác thực Kaggle API (Colab: Secrets KAGGLE_USERNAME / KAGGLE_KEY)."""
    user, key = os.environ.get("KAGGLE_USERNAME"), os.environ.get("KAGGLE_KEY")
    if PLATFORM == "colab" and not key:
        from google.colab import userdata  # type: ignore[import-not-found]

        user, key = userdata.get("KAGGLE_USERNAME"), userdata.get("KAGGLE_KEY")
    if not key:
        raise RuntimeError(
            "Không thấy dữ liệu Add Input và không có KAGGLE_KEY. Kaggle: bấm Add Input (README); "
            "Colab: thêm KAGGLE_USERNAME và KAGGLE_KEY vào Secrets (biểu tượng chìa khóa)."
        )
    if key.startswith("KGAT_"):
        return {"headers": {"Authorization": f"Bearer {key}"}}
    return {"auth": (user, key)}


def kaggle_dataset_dir(repo: str, env: str) -> Path:
    """Thư mục gốc của bộ dữ liệu: biến môi trường → /kaggle/input (Add Input) → tải ZIP (Colab)."""
    if os.environ.get(env):
        return Path(os.environ[env])
    owner, slug = repo.split("/")
    base = Path("/kaggle/input")
    candidates = [base / slug, base / "datasets" / owner / slug]
    candidates += sorted(p for p in base.glob(f"*/{slug}") if p.is_dir()) if base.is_dir() else []
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    target = WORK / "datasets" / repo.replace("/", "__")
    if (target / ".done").is_file():
        return target
    archive = WORK / "datasets" / (repo.replace("/", "__") + ".zip")
    if not archive.is_file():
        print(f"Tải {repo} bằng Kaggle API (có thể mất 10–30 phút)…")
        with requests.get(
            f"https://www.kaggle.com/api/v1/datasets/download/{repo}",
            stream=True,
            timeout=600,
            **kaggle_auth(),
        ) as response:
            response.raise_for_status()
            part = archive.with_suffix(".part")
            part.parent.mkdir(parents=True, exist_ok=True)
            with part.open("wb") as handle:
                for chunk in response.iter_content(1 << 22):
                    handle.write(chunk)
            part.replace(archive)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(target)
    archive.unlink()
    (target / ".done").write_text("ok")
    return target


started = time.time()
RTFS_ROOT = kaggle_dataset_dir("stplusplus/rtfs-10k", "VC_RTFS_ROOT")
_csv = sorted(RTFS_ROOT.rglob("inswapper.csv"))
RTFS_ROOT = _csv[0].parent if _csv else RTFS_ROOT
FAS_ROOT = kaggle_dataset_dir("maihongtng/face-anti-spoofing", "VC_FAS_ROOT")
print("RTFS-10k:", RTFS_ROOT)
print("FAS-VN  :", FAS_ROOT)
for name in ("videos.csv", "inswapper.csv", "uniface.csv"):
    assert (RTFS_ROOT / name).is_file(), (
        f"Thiếu {name} trong {RTFS_ROOT} — kiểm lại Add Input RTFS-10k."
    )
step_done("3_tim_du_lieu", started)

# %%
# ===================== 4. Lập danh sách mẫu (chưa xem nội dung) =====================
started = time.time()


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


SAMPLES: dict[str, dict] = {}

# RTFS: chia theo video gốc + ảnh donor TRƯỚC, rồi mới lấy mẫu trong từng tập.
rt_videos = read_csv(RTFS_ROOT / "videos.csv")
rt_fakes = [
    r
    for r in read_csv(RTFS_ROOT / "inswapper.csv") + read_csv(RTFS_ROOT / "uniface.csv")
    if r.get("success", "True") == "True"
]
RTFS = gc.split_rtfs(rt_videos, rt_fakes, seed=SEED)
print("RTFS — báo cáo chia:", json.dumps(RTFS.report, ensure_ascii=False))
gen_of = {r["filename"]: r["generator"] for r in rt_fakes}
# Chỉ lấy file có thật trên đĩa (Add Input đầy đủ thì có hết; thiếu thì báo số lượng).
real_ok = [n for n in sorted(RTFS.real) if (RTFS_ROOT / "original_videos" / n).is_file()]
fake_ok = [n for n in sorted(RTFS.fake) if (RTFS_ROOT / gen_of[n] / n).is_file()]
print(
    f"RTFS file có trên đĩa: {len(real_ok)}/{len(RTFS.real)} thật, {len(fake_ok)}/{len(RTFS.fake)} giả"
)
real_names = gc.sample_rows(real_ok, N_RTFS_REAL, SEED)
fake_names = gc.sample_rows(fake_ok, N_RTFS_FAKE, SEED + 1)
for name in real_names:
    split, group = RTFS.real[name]
    SAMPLES[f"rtfs_real__{Path(name).stem}"] = dict(
        source="rtfs_real",
        label=0,
        split=split,
        group_id=group,
        method="",
        raw=str(RTFS_ROOT / "original_videos" / name),
        still=False,
        video_key=group,
    )
for name in fake_names:
    split, group = RTFS.fake[name]
    gen = gen_of[name]
    SAMPLES[f"rtfs_fake__{Path(name).stem}"] = dict(
        source="rtfs_fake",
        label=1,
        split=split,
        group_id=group,
        method=gen,
        raw=str(RTFS_ROOT / gen / name),
        still=False,
        video_key=group,
    )

# FAS-VN live: bỏ trùng byte và ảnh trùng not_live.
fas_files, fas_counts = gc.fas_live_files(FAS_ROOT)
print(f"FAS-VN live: {fas_counts} ({time.time() - started:.0f} s)")
for path in gc.sample_rows(fas_files, N_FAS_LIVE, SEED + 2):
    SAMPLES[f"fas_vn__{path.stem}"] = dict(
        source="fas_vn",
        label=0,
        split="",
        group_id="",
        method="",
        raw=str(path),
        still=True,
        video_key=f"fas:{path.stem}",
    )

# VLR: mục lục ZIP từ xa (chỉ vài MB), chọn clip xen kẽ playlist/video.
vlr_index: dict[str, tuple[str, d4.ZipMember]] = {}
for part in VLR_PARTS if USE_VLR else []:  # VLR tắt mặc định
    url = d4.VLR_URL.format(record=d4.VLR_RECORD, part=part)
    cache = WORK / "vlr_index" / f"{part}.json"  # mục lục ZIP đã đọc (chạy lại thì khỏi tải)
    if cache.is_file():
        members = [d4.ZipMember(**m) for m in json.loads(cache.read_text(encoding="utf-8"))]
    else:
        members = d4.list_remote_zip(url)
        nb.write_json(cache, [m.__dict__ for m in members])
    by_name = {m.name: m for m in members}
    clips = [c for m in members if (c := d4.parse_vlr_member(m.name, m.file_size))]
    chosen = d4.plan_candidates(clips, VLR_VIDEOS_PER_PART, VLR_CLIPS_PER_VIDEO, SEED)
    for clip in chosen:
        vlr_index[clip.clip_id] = (url, by_name[clip.member])
        SAMPLES[f"vlr__{clip.clip_id}"] = dict(
            source="vlr",
            label=0,
            split="",
            group_id="",
            method="",
            raw=str(WORK / "raw" / "vlr" / f"{clip.clip_id}.mp4"),
            still=False,
            video_key=f"vlr:{clip.part}/{clip.playlist}/{clip.video}",
        )
    print(
        f"VLR {part}: {len(clips)} clip trong ZIP, chọn {len(chosen)} ({time.time() - started:.0f} s)"
    )
print("Mẫu theo nguồn:", dict(Counter(s["source"] for s in SAMPLES.values())))
step_done("4_lap_danh_sach", started)

# %%
# ===================== 5. Tải clip VLR (HTTP Range) + dò mặt + ArcFace =====================
import cv2
import numpy as np

started = time.time()
(WORK / "raw" / "vlr").mkdir(parents=True, exist_ok=True)
import threading
from concurrent.futures import ThreadPoolExecutor

_local = threading.local()


def fetch_vlr(item: tuple[str, tuple[str, d4.ZipMember]]) -> None:
    """Tải một clip VLR (HTTP Range); mỗi luồng một session."""
    clip_id, (url, member) = item
    dst = WORK / "raw" / "vlr" / f"{clip_id}.mp4"
    if dst.is_file():
        return
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
    tmp = dst.with_name(dst.name + ".part")
    tmp.write_bytes(d4.fetch_member(url, member, _local.session))
    tmp.replace(dst)


with ThreadPoolExecutor(8) as pool:
    for i, _ in enumerate(pool.map(fetch_vlr, vlr_index.items()), 1):
        if i % 100 == 0 or i == len(vlr_index):
            print("Tải VLR:", gc.eta_text(i, len(vlr_index), time.time() - started))
print(f"VLR đã có {len(vlr_index)} clip ({time.time() - started:.0f} s)")


def probe(path: Path, still: bool) -> tuple[list[np.ndarray], int, int]:
    """3 khung trong 3 giây đầu (ảnh tĩnh: 1 khung) để dò mặt và cắt khung."""
    if still:
        image = cv2.imread(str(path))
        if image is None:
            return [], 0, 0
        return [image], image.shape[1], image.shape[0]
    capture = cv2.VideoCapture(str(path))
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    width, height = int(capture.get(3)), int(capture.get(4))
    frames = []
    for t in (0.2, 1.5, 2.8):
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, frame = capture.read()
        if ok and frame is not None:
            frames.append(frame)
    capture.release()
    return frames, width, height


def arcface(frame: np.ndarray, landmarks) -> np.ndarray:
    crop = d4.arcface_crop(frame, np.asarray(landmarks, dtype=np.float32))
    blob = d4.arcface_blob([crop])
    vector = ARCFACE_SESSION.run(None, {ARCFACE_SESSION.get_inputs()[0].name: blob})[0]
    return d4.l2_normalize(vector)[0]


FACES_PATH = OUT / "faces.jsonl"
EMB_DIR = WORK / "emb"  # embedding ArcFace chỉ để chia tập; XÓA ở bước 13
EMB_DIR.mkdir(parents=True, exist_ok=True)
EMB_SOURCES = (*gc.VN_SOURCES, "rtfs_real")  # rtfs_real: chỉ để ĐO trùng người giữa các tập
FACES = {}
if FACES_PATH.is_file():
    for line in FACES_PATH.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        FACES[row["sample_id"]] = row
todo = [k for k in SAMPLES if k not in FACES]
t1 = time.time()
with FACES_PATH.open("a", encoding="utf-8") as handle:
    for i, key in enumerate(todo, 1):
        info = SAMPLES[key]
        if info["split"] == "test" and not RUN_TEST:
            # RTFS đã biết tập (chia theo metadata): không mở file test.
            row = dict(sample_id=key, n_frames=0, n_faces=None, boxes=[], width=0, height=0)
            handle.write(json.dumps(row) + "\n")
            FACES[key] = row
            continue
        frames, width, height = probe(Path(info["raw"]), info["still"])
        boxes, embeddings = [], []
        for frame in frames:
            face = DETECTOR._largest_face(frame)
            if face is None:
                continue
            boxes.append([face.x1, face.y1, face.x2, face.y2])
            if info["source"] in EMB_SOURCES:
                embeddings.append(arcface(frame, face.landmarks))
        if embeddings:
            np.save(EMB_DIR / f"{key}.npy", np.stack(embeddings))
        row = dict(
            sample_id=key,
            n_frames=len(frames),
            n_faces=len(boxes),
            boxes=boxes,
            width=width,
            height=height,
        )
        handle.write(json.dumps(row) + "\n")
        handle.flush()
        FACES[key] = row
        if i % 100 == 0 or i == len(todo):
            print("Dò mặt:", gc.eta_text(i, len(todo), time.time() - t1))
detect = Counter()
for key, info in SAMPLES.items():
    if FACES[key]["n_faces"] is not None:  # None = mẫu test RTFS chưa mở
        detect[(info["source"], FACES[key]["n_faces"] > 0)] += 1
print("SCRFD có mặt (nguồn, có mặt): số mẫu →", dict(detect))
step_done("5_do_mat", started)

# %%
# ===================== 6. Chia tập theo nhóm (seed cố định) → splits.csv =====================
started = time.time()
vn_keys = [
    k for k, s in SAMPLES.items() if s["source"] in gc.VN_SOURCES and FACES[k]["n_faces"] > 0
]
vn_emb = [
    np.load(EMB_DIR / f"{k}.npy") if (EMB_DIR / f"{k}.npy").is_file() else np.zeros((0, 512))
    for k in vn_keys
]
vn_groups, VN_GROUP_REPORT = gc.person_groups(
    vn_emb,
    [SAMPLES[k]["source"] for k in vn_keys],
    [SAMPLES[k]["video_key"] for k in vn_keys],
    threshold=ARCFACE_THRESHOLD,
)
vn_split = gc.split_groups(vn_groups, seed=SEED)
for key, group in zip(vn_keys, vn_groups, strict=True):
    SAMPLES[key].update(group_id=group, split=vn_split[group])
print("Nhóm người Việt:", json.dumps(VN_GROUP_REPORT, ensure_ascii=False))
if VN_GROUP_REPORT["largest_group_share"] > 0.3:
    print("CẢNH BÁO: một nhóm người Việt chiếm > 30% mẫu — chia tập sẽ lệch; báo trưởng nhóm.")
# Nhóm của các tập không được trùng nhau (cos ArcFace giữa hai tập phải < ngưỡng).
_with_emb = [(e, SAMPLES[k]["split"]) for k, e in zip(vn_keys, vn_emb, strict=True) if e.size]
CROSS_SIM = (
    d4.cross_split_max_similarity([e for e, _ in _with_emb], [s for _, s in _with_emb])
    if len({s for _, s in _with_emb}) > 1
    else None
)
print("Cos ArcFace lớn nhất giữa hai tập:", CROSS_SIM)
# RTFS chia theo video YouTube + donor, KHÔNG theo người: đo cos ArcFace lớn nhất giữa calib_fit và
# calib_ltt của RTFS thật (không mở tập test). >= ngưỡng gom = có thể cùng một người ở hai tập.
_rt = [
    (np.load(EMB_DIR / f"{k}.npy"), s["split"])
    for k, s in SAMPLES.items()
    if s["source"] == "rtfs_real" and (EMB_DIR / f"{k}.npy").is_file()
]
RTFS_CROSS_SIM = (
    d4.cross_split_max_similarity([e for e, _ in _rt], [s for _, s in _rt])
    if len({s for _, s in _rt}) > 1
    else None
)
print("RTFS thật — cos ArcFace lớn nhất calib_fit↔calib_ltt:", RTFS_CROSS_SIM)
if RTFS_CROSS_SIM is not None and RTFS_CROSS_SIM >= ARCFACE_THRESHOLD:
    print("LƯU Ý: có thể cùng một người RTFS ở cả calib_fit và calib_ltt (đã ghi vào card.md).")

SPLIT_FIELDS = ["sample_id", "source", "label", "split", "group_id", "method", "n_faces", "raw"]
ROWS = []
for key, info in sorted(SAMPLES.items()):
    if FACES[key]["n_faces"] == 0:
        continue  # không có mặt: không vào tập nào (đã báo ở bước 5); None = test chưa mở
    ROWS.append(
        {
            **{f: info.get(f, "") for f in SPLIT_FIELDS},
            "sample_id": key,
            "n_faces": FACES[key]["n_faces"],
        }
    )
with open(OUT / "splits.csv", "w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=SPLIT_FIELDS)
    writer.writeheader()
    writer.writerows(ROWS)
dist = Counter((r["split"], r["source"]) for r in ROWS)
print("Phân bố (tập, nguồn) → số mẫu:")
for split in gc.CALIB_SPLITS:
    print(f"  {split:9s}", {s: n for (sp, s), n in sorted(dist.items()) if sp == split})
step_done("6_chia_tap", started)

# %%
# ===================== 7. Cắt mặt + mã hóa lại cùng cấu hình (chỉ calib_fit, calib_ltt) =====================
started = time.time()
WORK_ROWS = gt.rows_for(ROWS, ("calib_fit", "calib_ltt"))  # ném lỗi nếu lẫn test
PROC = WORK / "proc"
t1 = time.time()
for i, row in enumerate(WORK_ROWS, 1):
    face = FACES[row["sample_id"]]
    dst = PROC / row["split"] / row["source"] / f"{row['sample_id']}.mp4"
    row["path"] = str(dst)
    if dst.is_file():
        continue
    dst.parent.mkdir(parents=True, exist_ok=True)
    box = gc.square_crop_box(face["boxes"], face["width"], face["height"])
    tmp = dst.with_name(dst.stem + ".tmp.mp4")
    nb.run(
        gc.crop_encode_cmd(FFMPEG, row["raw"], tmp, box, still=SAMPLES[row["sample_id"]]["still"]),
        log=OUT / "logs" / "ffmpeg.log",
    )
    tmp.replace(dst)
    if i % 100 == 0 or i == len(WORK_ROWS):
        print("Mã hóa lại:", gc.eta_text(i, len(WORK_ROWS), time.time() - t1))
step_done("7_ma_hoa_lai", started)

# %%
# ===================== 8. Kiểm lộ đề NGUỒN trên dữ liệu đã xử lý (calib_fit) =====================
started = time.time()
FIT_ROWS = gc.subset(WORK_ROWS, split="calib_fit")
for row in FIT_ROWS:
    row["features"] = d4.video_features(Path(row["path"]))
LEAK = {}
pairs = {
    "vlr_vs_rtfs_fake": (("vlr",), d4.LEAK_FEATURES, "VLR thật và RTFS giả"),
    "rtfs_real_vs_rtfs_fake": (("rtfs_real",), d4.LEAK_FEATURES, "RTFS thật và RTFS giả"),
    # ảnh tĩnh: thời lượng/kích thước file/bitrate không so được với video → chỉ độ nét, độ sáng
    "fas_vn_vs_rtfs_fake": (
        ("fas_vn",),
        ("sharpness", "brightness"),
        "FAS-VN thật (ảnh) và RTFS giả",
    ),
}
for name, (real_sources, features, pair_vi) in pairs.items():
    chosen = gc.subset(FIT_ROWS, source=(*real_sources, "rtfs_fake"))
    if len({r["label"] for r in chosen}) < 2:
        continue
    LEAK[name] = gc.source_leak_report(
        [r["features"] for r in chosen],
        [r["label"] for r in chosen],
        feature_names=features,
        pair_vi=pair_vi,
    )
    print(f"[{name}]", LEAK[name]["message_vi"])
    print("   AUC:", {k: round(v, 3) for k, v in LEAK[name]["auc"].items() if v is not None})
nb.write_json(OUT / "leak_report.json", LEAK)
SOURCE_LEAK_WARNING = any(v["warning"] for k, v in LEAK.items() if k != "rtfs_real_vs_rtfs_fake")
step_done("8_lo_de", started)

# %%
# ===================== 9. Chấm điểm GenD (đúng face/gend.py, 8 khung/clip) =====================
from vericlue_ml.common.detector import DetectorInput

started = time.time()
SCORES_PATH = OUT / "scores_progress.jsonl"
SCORED = {}
if SCORES_PATH.is_file():
    for line in SCORES_PATH.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        SCORED[row["sample_id"]] = row
todo = [r for r in WORK_ROWS if r["sample_id"] not in SCORED]
t1 = time.time()
with nb.GpuMonitor() as monitor, SCORES_PATH.open("a", encoding="utf-8") as handle:
    for i, row in enumerate(todo, 1):
        result = DETECTOR.predict(DetectorInput(video=Path(row["path"])))
        assert result.model_version == MODEL_VERSION
        out = dict(
            sample_id=row["sample_id"],
            status=str(getattr(result.status, "value", result.status)),
            score=result.score,
            frames_used=(result.quality or {}).get("frames_used"),
            error_code=str(getattr(result.error_code, "value", result.error_code or "")),
            latency_ms=round(result.latency_ms, 1),
        )
        handle.write(json.dumps(out) + "\n")
        handle.flush()
        SCORED[row["sample_id"]] = out
        if i % 100 == 0 or i == len(todo):
            print("Chấm điểm:", gc.eta_text(i, len(todo), time.time() - t1))
print(f"Đỉnh VRAM khi chấm: {monitor.peak_mb} MB")
for row in WORK_ROWS:
    row.update(SCORED[row["sample_id"]])
print(
    "Trạng thái (tập, nguồn, status):",
    dict(Counter((r["split"], r["source"], r["status"]) for r in WORK_ROWS)),
)
step_done("9_cham_diem", started)

# %%
# ===================== 10. Fit calibrator trên calib_fit (ADR-0010) + báo cáo =====================
from sklearn.metrics import roc_auc_score

from vericlue_ml.common.calibration import (
    CalibFit,
    CalibrationError,
    CalibrationStore,
    fit,
    reliability_markdown,
)

started = time.time()
OK_CALIB_FIT = [r for r in gc.subset(WORK_ROWS, split="calib_fit") if r["status"] == "ok"]
OK_FIT = gc.subset(OK_CALIB_FIT, source=gc.FIT_SOURCES)  # VLR KHÔNG vào fit
OK_REF = gc.subset(OK_CALIB_FIT, source=gc.REFERENCE_SOURCES)  # chỉ tham khảo
gt.assert_no_test(OK_FIT)
DATASET = "fas_vn(live)+rtfs10k(original_videos,inswapper,uniface)"
CAL = None
try:
    CAL = fit(
        CalibFit(
            scores=[float(r["score"]) for r in OK_FIT],
            labels=[int(r["label"]) for r in OK_FIT],
            subject_ids=[r["group_id"] for r in OK_FIT],
            dataset=DATASET,
        ),
        module="face_deepfake",
        model_version=MODEL_VERSION,
        commit=SOURCE_COMMIT,
    )
except CalibrationError as exc:
    print("KHÔNG fit được calibrator:", exc)
    if not SMOKE:
        raise

REPORT = {"model_version": MODEL_VERSION, "n_calib_fit_ok": len(OK_FIT)}
REPORT["raw_score_summary"] = gc.score_summary(OK_FIT)
labels_fit = [int(r["label"]) for r in OK_FIT]
scores_fit = [float(r["score"]) for r in OK_FIT]
if len(set(labels_fit)) == 2:
    REPORT["auc_raw_all"] = roc_auc_score(labels_fit, scores_fit)
# GenD có tách NGUỒN trong lớp thật không? (VN thật vs RTFS thật; 0,5 là tốt)
real_rows = [r for r in OK_FIT if r["label"] == 0]
is_rtfs = [int(r["source"] == "rtfs_real") for r in real_rows]
if len(set(is_rtfs)) == 2:
    REPORT["auc_score_rtfs_real_vs_vn_real"] = roc_auc_score(
        is_rtfs, [float(r["score"]) for r in real_rows]
    )
if CAL is not None:
    oof = gc.oof_probabilities(CAL, scores_fit, labels_fit, [r["group_id"] for r in OK_FIT])
    insample = CAL.predict(scores_fit)
    for r, p_oof, p_in in zip(OK_FIT, oof, insample, strict=True):
        r["prob_oof"], r["prob"] = float(p_oof), float(p_in)
    REPORT["calibrator"] = {
        "method": CAL.method,
        "n_pos": CAL.n_pos,
        "n_neg": CAL.n_neg,
        "cv_folds": CAL.cv_folds,
        "cv_log_loss": CAL.cv_log_loss,
        "before": CAL.before.model_dump(),
        "after_group_oof": CAL.after.model_dump(),
    }
exceed = {}
for name, sources in (
    ("fas_vn", ("fas_vn",)),
    ("rtfs_real", ("rtfs_real",)),
    ("rtfs_fake", ("rtfs_fake",)),
):
    rows = gc.subset(OK_FIT, source=sources)
    if not rows:
        continue
    raw = np.clip([float(r["score"]) for r in rows], 1e-4, 1 - 1e-4)  # identity hiện tại
    exceed[name] = {"n": len(rows), "truoc_hieu_chinh(identity)": gc.exceed_rates(raw)}
    if CAL is not None:
        exceed[name]["sau_hieu_chinh(ngoai_fold)"] = gc.exceed_rates([r["prob_oof"] for r in rows])
        exceed[name]["sau_hieu_chinh(trong_mau)"] = gc.exceed_rates([r["prob"] for r in rows])
REPORT["exceed_rates_calib_fit"] = exceed
if OK_REF:  # VLR: tham khảo, không ảnh hưởng fit (calibrator chưa từng thấy các mẫu này)
    ref_scores = [float(r["score"]) for r in OK_REF]
    REPORT["tham_khao_vlr"] = {
        "n": len(OK_REF),
        "phan_bo_diem_tho": gc.score_summary(OK_REF),
        "truoc_hieu_chinh(identity)": gc.exceed_rates(np.clip(ref_scores, 1e-4, 1 - 1e-4)),
    }
    if CAL is not None:
        REPORT["tham_khao_vlr"]["sau_hieu_chinh"] = gc.exceed_rates(CAL.predict(ref_scores))
print(json.dumps(REPORT, ensure_ascii=False, indent=1))
print(
    "Ý nghĩa: với người Việt thật, tỉ lệ vượt B=0,15 là tỉ lệ bị đẩy sang bước đọc câu (chặn nhầm);"
)
print("với RTFS giả, đó là tỉ lệ bắt được. Ngưỡng KHÔNG được chọn ở đây (ROUT-03 dùng calib_ltt).")
step_done("10_calibrator", started)

# %%
# ===================== 11. Lưu điểm calib_fit / calib_ltt (KHÔNG chọn ngưỡng) =====================
started = time.time()
SCORE_FIELDS = [
    "sample_id",
    "source",
    "label",
    "split",
    "group_id",
    "method",
    "status",
    "score",
    "frames_used",
    "error_code",
    "prob",
    "prob_oof",
]
for split in ("calib_fit", "calib_ltt"):
    rows = gc.subset(WORK_ROWS, split=split)
    if CAL is not None:
        for r in rows:
            if r["status"] == "ok" and "prob" not in r:
                r["prob"] = float(CAL.predict([float(r["score"])])[0])
    with open(OUT / f"scores_{split}.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Đã lưu scores_{split}.csv ({len(rows)} dòng)")
step_done("11_luu_diem", started)


# %%
# ===================== 12. Tập test — TẮT mặc định (chỉ trưởng nhóm bật một lần) =====================
def run_test() -> None:
    """Chấm và đo trên test bằng calibrator đã chốt. Chỉ chạy khi RUN_TEST=True VÀ câu xác nhận đúng."""
    gt.check_test_unlocked(RUN_TEST, TEST_CONFIRMATION)
    if CAL is None:
        raise RuntimeError("Chưa có calibrator.")
    test_rows = [r for r in ROWS if r["split"] == "test"]
    out_rows = []
    for row in test_rows:
        face = FACES[row["sample_id"]]
        if face["n_faces"] is None:  # mẫu test chưa mở ở bước 5 → dò mặt bây giờ
            info = SAMPLES[row["sample_id"]]
            frames, width, height = probe(Path(info["raw"]), info["still"])
            found = [DETECTOR._largest_face(f) for f in frames]
            boxes = [[b.x1, b.y1, b.x2, b.y2] for b in found if b is not None]
            if not boxes:
                continue
            face = dict(face, n_faces=len(boxes), boxes=boxes, width=width, height=height)
        dst = PROC / "test" / row["source"] / f"{row['sample_id']}.mp4"
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.is_file():
            box = gc.square_crop_box(face["boxes"], face["width"], face["height"])
            nb.run(
                gc.crop_encode_cmd(
                    FFMPEG, row["raw"], dst, box, still=SAMPLES[row["sample_id"]]["still"]
                )
            )
        result = DETECTOR.predict(DetectorInput(video=dst))
        status = str(getattr(result.status, "value", result.status))
        prob = float(CAL.predict([result.score])[0]) if status == "ok" else None
        out_rows.append({**row, "status": status, "score": result.score, "prob": prob})
    with open(OUT / "scores_test.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(out_rows)
    print("Đã chấm test:", len(out_rows))


if RUN_TEST:
    run_test()
else:
    print("Tập test: TẮT (đúng luật). Không có mẫu test nào được mã hóa hay chấm điểm.")

# %%
# ===================== 13. Xuất ZIP gửi trưởng nhóm =====================
started = time.time()
EXPORT = OUT / "export"
if EXPORT.exists():
    shutil.rmtree(EXPORT)
EXPORT.mkdir(parents=True)
cal_rel = ""
if CAL is not None:
    cal_path = CalibrationStore(EXPORT / "calibrators").save(CAL)
    cal_rel = str(cal_path.relative_to(EXPORT)).replace("\\", "/")
for name in (
    "splits.csv",
    "scores_calib_fit.csv",
    "scores_calib_ltt.csv",
    "leak_report.json",
    "step_times.json",
):
    if (OUT / name).is_file():
        shutil.copy2(OUT / name, EXPORT / name)
METRICS = {
    "smoke": SMOKE,
    "seed": SEED,
    "platform": PLATFORM,
    "gpu": GPU,
    "environment": ENV_INFO,
    "source_commit": SOURCE_COMMIT,
    "source_dirty": SOURCE_DIRTY,
    "model_version": MODEL_VERSION,
    "rtfs_split": RTFS.report,
    "vn_groups": VN_GROUP_REPORT,
    "vn_cross_split_max_cos": CROSS_SIM,
    "rtfs_real_cross_split_max_cos_fit_vs_ltt": RTFS_CROSS_SIM,
    "fas_counts": fas_counts,
    "scrfd_detect": {f"{k[0]}|{'co_mat' if k[1] else 'khong_mat'}": v for k, v in detect.items()},
    "split_distribution": {f"{a}|{b}": n for (a, b), n in sorted(dist.items())},
    "source_leak_warning": SOURCE_LEAK_WARNING,
    "report": REPORT,
    "step_seconds": STEP_TIMES,
}
nb.write_json(EXPORT / "metrics.json", METRICS)
leak_lines = "\n".join(f"- {k}: {v['message_vi']}" for k, v in LEAK.items())
cal_text = (
    f"`{cal_rel}` — phương pháp **{CAL.method}**, n_pos={CAL.n_pos}, n_neg={CAL.n_neg}, "
    f"log-loss ngoài-fold {CAL.after.log_loss:.4f} (trước {CAL.before.log_loss:.4f})"
    if CAL is not None
    else "**KHÔNG fit được** (xem metrics.json)."
)
card = f"""# Calibrator GenD (face_deepfake) — FACE-04

- Mô hình: `{MODEL_VERSION}` (GenD gốc, KHÔNG dạy lại)
- Commit nguồn: `{SOURCE_COMMIT}`{" (có sửa chưa commit)" if SOURCE_DIRTY else ""} · seed {SEED} · SMOKE={SMOKE}
- Calibrator: {cal_text}
- Fit CHỈ trên `calib_fit`; `calib_ltt` chỉ lưu điểm cho ROUT-03; tập test KHÔNG được đọc.

## Dữ liệu (số mẫu có mặt, theo tập)
{chr(10).join(f"- {a} / {b}: {n}" for (a, b), n in sorted(dist.items()))}

- Thật (fit): FAS-VN live (Kaggle maihongtng/face-anti-spoofing, CC BY 4.0 — ảnh tĩnh, GenD chấm
  1 khung) + video gốc RTFS-10k (cùng nguồn với lớp giả).
- VLR: {"tham khảo (KHÔNG dùng để fit), phần " + ", ".join(VLR_PARTS) if USE_VLR else "không dùng (USE_VLR = False)"}.
- Giả: RTFS-10k inswapper + uniface (Kaggle stplusplus/rtfs-10k, CC BY-SA 4.0).
- Chia: người Việt theo ArcFace (ngưỡng {ARCFACE_THRESHOLD}) ∪ video nguồn; RTFS theo video YouTube gốc,
  ảnh donor gán một tập, bỏ {RTFS.report["fakes_dropped"]} video giả có donor khác tập
  (đồ thị video–donor ban đầu: {RTFS.report["components_before_cut"]} khối).
- Tiền xử lý: khung vuông {gc.CROP_SCALE}× quanh mặt → {gc.CROP_SIZE}×{gc.CROP_SIZE} → H.264 CRF {gc.ENCODE_CRF},
  {gc.ENCODE_FPS} fps, ≤ {gc.ENCODE_SECONDS:g} s, cho MỌI nguồn; rồi `face/gend.py` (8 khung/clip).

## Lộ đề nguồn
{leak_lines or "- (không tính được)"}
{'- **CẢNH BÁO:** thật và giả đến từ miền khác nhau; calibrator có thể học "nguồn" thay vì "giả".' if SOURCE_LEAK_WARNING else ""}

## Tỉ lệ vượt ngưỡng tạm (B=0,15; A=0,60) trên calib_fit
```
{json.dumps(exceed, ensure_ascii=False, indent=1)}
```

## Giới hạn
- RTFS chia theo video YouTube + ảnh donor, KHÔNG theo người. Cos ArcFace lớn nhất giữa RTFS thật
  ở calib_fit và calib_ltt: {RTFS_CROSS_SIM if RTFS_CROSS_SIM is None else round(RTFS_CROSS_SIM, 4)}
  (ngưỡng gom {ARCFACE_THRESHOLD}; >= ngưỡng nghĩa là có thể cùng một người ở hai tập; tập test không đo).
- **Không có deepfake người Việt**: lớp giả chỉ có RTFS-10k (người nước ngoài, bối cảnh YouTube/hội
  nghị video). Calibrator không đo được khả năng bắt deepfake người Việt.
- FAS-VN là ảnh tĩnh; eKYC thật dùng video. Người Việt thật trong lớp thật chỉ có FAS-VN.
- VLR (video bài giảng đã căn mặt, nén lại) bị GenD chấm cao và lộ đề độ nét so với RTFS nên
  KHÔNG dùng để fit; nếu bật chỉ báo tham khảo.
- `scores_calib_*.csv` có thể chứa dòng `source=vlr` (tham khảo): ROUT-03 phải lọc bỏ.
- Ngưỡng B/A là giá trị tạm của thresholds.yaml; chọn ngưỡng là việc của ROUT-03 trên calib_ltt.

## Reliability (calib_fit, ngoài-fold)
{reliability_markdown(CAL.after_reliability) if CAL is not None else "—"}
"""
(EXPORT / "card.md").write_text(card, encoding="utf-8")
sums = {
    p.relative_to(EXPORT).as_posix(): nb.sha256_file(p)
    for p in sorted(EXPORT.rglob("*"))
    if p.is_file()
}
(EXPORT / "SHA256SUMS.txt").write_text(
    "".join(f"{v}  {k}\n" for k, v in sums.items()), encoding="utf-8"
)
ZIP = OUT / f"gend_calibration_{'smoke_' if SMOKE else ''}{time.strftime('%Y%m%d_%H%M')}.zip"
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(EXPORT.rglob("*")):
        if path.is_file():
            zf.write(path, path.relative_to(EXPORT).as_posix())
step_done("13_xuat_zip", started)
# Embedding ArcFace (sinh trắc) không lưu lâu dài: xóa cùng faces.jsonl (chạy lại sẽ dò mặt lại).
shutil.rmtree(EMB_DIR, ignore_errors=True)
(OUT / "faces.jsonl").unlink(missing_ok=True)
print(f"\nXONG sau {(time.time() - T0) / 60:.1f} phút. Tải file này gửi trưởng nhóm:\n  {ZIP}")
print("SHA-256 zip:", nb.sha256_file(ZIP))
