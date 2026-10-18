# Copyright 2025-2026 Yakhyokhuja Valikhujaev (UniFace preprocessing/decoding).
# MIT License; see third_party/licenses/uniface.txt and third_party/README.md.
"""DATA-03 ảnh: nhóm rủi ro ArcFace và nhóm video; chỉ xử lý local."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import tarfile
import time
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

from make_splits import (
    FIELDS,
    ROOT,
    SPLITS,
    Row,
    SplitMap,
    UnionFind,
    _groups,
    _partition,
    fill_calibration_quotas,
    validate_splits,
)

IMAGE_DATASETS = ("zalo2022", "wilddeepfake", "fas_vn", "rtfs10k", "vicocktail", "vn_celeb_faces")


def row_for(data_dir: Path, source: str, path: Path, label: str, attack: str, **extra) -> Row:
    """Tạo hàng CSV tương đối DATA_DIR, không tự gán danh tính."""
    row = dict.fromkeys(FIELDS, "")
    row.update(
        path=path.relative_to(data_dir).as_posix(),
        source=source,
        label=label,
        attack_type=attack,
        **extra,
    )
    return row


def safe_target(folder: Path, member: str) -> Path:
    """Từ chối đường dẫn archive thoát thư mục đích, kể cả drive Windows."""
    if any(p.is_symlink() or p.is_junction() for p in (folder, *folder.parents)):
        raise ValueError(f"Thư mục archive có link/junction: {folder}")
    if (
        "\\" in member
        or ":" in member
        or PurePosixPath(member).is_absolute()
        or ".." in PurePosixPath(member).parts
    ):
        raise ValueError(f"Archive path không hợp lệ: {member}")
    target = (folder / member).resolve()
    if not target.is_relative_to(folder.resolve()):
        raise ValueError(f"Archive path thoát đích: {member}")
    return target


def load_fas(data_dir: Path) -> tuple[list[Row], list[dict]]:
    folder = data_dir / "raw/fas_vn"
    rows, quarantine = [], []
    with zipfile.ZipFile(folder / "face-anti-spoofing.zip") as archive:
        candidates = defaultdict(list)
        for item in archive.infolist():
            if not item.is_dir():
                candidates[(item.CRC, item.file_size)].append(item)
        conflicts = {}
        for items in candidates.values():
            if len({PurePosixPath(i.filename).parts[2] for i in items}) < 2:
                continue
            by_digest = defaultdict(list)
            for item in items:
                by_digest[hashlib.sha256(archive.read(item)).hexdigest()].append(item)
            for digest, duplicates in by_digest.items():
                if len({PurePosixPath(i.filename).parts[2] for i in duplicates}) > 1:
                    conflicts.update({i.filename: digest for i in duplicates})
        for item in sorted(archive.infolist(), key=lambda x: x.filename):
            if item.is_dir():
                continue
            parts = PurePosixPath(item.filename).parts
            label = parts[2] if len(parts) > 3 else ""
            if label not in {"live", "not_live"}:
                raise ValueError(f"FAS nhãn không rõ: {item.filename}")
            if item.filename in conflicts:
                quarantine.append(
                    {
                        "member": item.filename,
                        "sha256": conflicts[item.filename],
                        "reason": "identical_bytes_opposite_labels",
                    }
                )
                continue
            target = safe_target(folder / "extracted", item.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or target.stat().st_size != item.file_size:
                target.write_bytes(archive.read(item))
            rows.append(
                row_for(
                    data_dir,
                    "fas_vn",
                    target,
                    "0" if label == "live" else "1",
                    "bonafide" if label == "live" else "presentation_attack",
                )
            )
    return rows, quarantine


# Rewritten for direct ONNX inference with bounded memory, without UniFace imports.
class FaceEncoder:
    """SCRFD + ArcFace ONNX local; embedding chỉ tồn tại trong RAM."""

    def __init__(self, models_dir: Path):
        import cv2
        import numpy as np
        import onnxruntime as ort
        import yaml

        cv2.setNumThreads(1)
        device = os.environ.get("DATA_SPLIT_DEVICE", "cpu")
        if device not in {"cpu", "cuda"}:
            raise ValueError("DATA_SPLIT_DEVICE phải là cpu hoặc cuda")
        providers = ["CPUExecutionProvider"]
        if device == "cuda":
            if "CUDAExecutionProvider" not in ort.get_available_providers():
                raise ValueError("Môi trường hiện tại không có ONNX CUDA provider")
            ort.preload_dlls(directory="")
            providers = [
                (
                    "CUDAExecutionProvider",
                    {
                        "gpu_mem_limit": 512 * 1024 * 1024,
                        "cudnn_conv_algo_search": "HEURISTIC",
                        "use_tf32": 0,
                    },
                ),
                "CPUExecutionProvider",
            ]
        manifest = yaml.safe_load((ROOT / "models/manifest.yaml").read_text(encoding="utf-8"))
        self.models = {}
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        options.use_deterministic_compute = True
        sessions = []
        for model_id, filename in (
            ("scrfd-10g", "det_10g.onnx"),
            ("arcface-mnet", "arcface_mnet.onnx"),
        ):
            entry = next(m for m in manifest["models"] if m["id"] == model_id)
            file = next(f for f in entry["files"] if f["path"] == filename)
            path = models_dir / model_id / filename
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != file["sha256"]:
                raise ValueError(f"SHA-256 sai: {path}")
            self.models[model_id] = {"revision": entry["source"]["revision"], "sha256": digest}
            session = ort.InferenceSession(str(path), options, providers=providers)
            if device == "cuda" and "CUDAExecutionProvider" not in session.get_providers():
                raise ValueError("Không khởi tạo được CUDA; không âm thầm fallback CPU")
            sessions.append(session)
        self.detector, self.recognizer = sessions
        self.det_input = self.detector.get_inputs()[0].name
        self.rec_input = self.recognizer.get_inputs()[0].name
        if len(self.detector.get_outputs()) != 9:
            raise ValueError("SCRFD phải có 9 đầu ra, gồm 5 landmarks")
        self.centers = {}
        for stride in (8, 16, 32):
            y, x = np.mgrid[: 640 // stride, : 640 // stride]
            centers = (np.stack((x, y), axis=-1).astype(np.float32) * stride).reshape(-1, 2)
            self.centers[stride] = np.repeat(centers, 2, axis=0)
        self.models["runtime"] = {
            "device": device,
            "onnxruntime": ort.__version__,
            "opencv": cv2.__version__,
            "numpy": np.__version__,
            "loader": "direct-onnx-v1",
        }

    def landmarks(self, image):
        """SCRFD letterbox 640, confidence 0,5 và NMS 0,4; giữ mọi mặt."""
        import cv2
        import numpy as np

        height, width = image.shape[:2]
        new_h, new_w = (
            (640, int(640 * width / height)) if height > width else (int(640 * height / width), 640)
        )
        factor = new_h / height
        canvas = np.zeros((640, 640, 3), dtype=np.uint8)
        canvas[:new_h, :new_w] = cv2.resize(image, (new_w, new_h))
        tensor = ((canvas.astype(np.float32) - 127.5) / 127.5).transpose(2, 0, 1)[None]
        outputs = self.detector.run(None, {self.det_input: tensor})
        boxes, scores, points = [], [], []
        for i, stride in enumerate((8, 16, 32)):
            score = outputs[i].ravel()
            keep = np.flatnonzero(score >= 0.5)
            centers = self.centers[stride]
            distance = outputs[i + 3] * stride
            box = np.column_stack(
                (
                    centers[:, 0] - distance[:, 0],
                    centers[:, 1] - distance[:, 1],
                    centers[:, 0] + distance[:, 2],
                    centers[:, 1] + distance[:, 3],
                )
            )
            point = outputs[i + 6].reshape(-1, 5, 2) * stride + centers[:, None, :]
            boxes.extend(box[keep] / factor)
            scores.extend(score[keep])
            points.extend(point[keep] / factor)
        if not scores:
            return []
        boxes = np.asarray(boxes)
        order = np.argsort(scores)[::-1]
        keep = []
        while len(order):
            i = int(order[0])
            keep.append(i)
            rest = order[1:]
            lo = np.maximum(boxes[i, :2], boxes[rest, :2])
            hi = np.minimum(boxes[i, 2:], boxes[rest, 2:])
            intersection = np.prod(np.maximum(0, hi - lo + 1), axis=1)
            area = np.prod(boxes[:, 2:] - boxes[:, :2] + 1, axis=1)
            overlap = intersection / (area[i] + area[rest] - intersection)
            order = rest[overlap <= 0.4]
        return [points[i] for i in keep]

    @staticmethod
    def aligned(image, landmarks):
        """Similarity least-squares toàn bộ 5 mốc, chuẩn ArcFace 112×112."""
        import cv2
        import numpy as np

        target = np.array(
            [
                [38.2946, 51.6963],
                [73.5318, 51.5014],
                [56.0252, 71.7366],
                [41.5493, 92.3655],
                [70.7299, 92.2041],
            ],
            dtype=np.float32,
        )
        x, y = np.asarray(landmarks, dtype=np.float64).T
        design = np.zeros((10, 4), dtype=np.float64)
        design[0::2] = np.column_stack((x, -y, np.ones(5), np.zeros(5)))
        design[1::2] = np.column_stack((y, x, np.zeros(5), np.ones(5)))
        a, b, tx, ty = np.linalg.lstsq(design, target.ravel(), rcond=None)[0]
        transform = np.array([[a, -b, tx], [b, a, ty]], dtype=np.float32)
        return cv2.warpAffine(image, transform, (112, 112), borderValue=0.0)

    def encode(self, path: Path) -> list:
        """Ba khung/video; mọi mặt được thấy liên kết về cùng nhóm video."""
        import cv2
        import numpy as np

        def frames():
            if path.suffix.lower() in {".mp4", ".video", ".webm"}:
                cap = cv2.VideoCapture(str(path))
                try:
                    count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    for fraction in (0.15, 0.5, 0.85):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, int(max(0, count - 1) * fraction))
                        ok, frame = cap.read()
                        if ok:
                            yield frame
                finally:
                    cap.release()
            else:
                frame = cv2.imread(str(path))
                if frame is not None:
                    yield frame

        embeddings = []
        for frame in frames():
            for points in self.landmarks(frame):
                aligned = self.aligned(frame, points)
                tensor = cv2.dnn.blobFromImage(
                    aligned, 1 / 127.5, (112, 112), (127.5,) * 3, swapRB=True
                )
                embedding = self.recognizer.run(None, {self.rec_input: tensor})[0].ravel()
                norm = np.linalg.norm(embedding)
                if not np.isfinite(norm) or norm <= 0:
                    raise ValueError("ArcFace trả vector không hợp lệ")
                embeddings.append(embedding / norm)
        return embeddings

    def close(self) -> None:
        self.detector = self.recognizer = None


def face_components(rows: list[Row], embeddings: list[list], threshold: float) -> list[list[Row]]:
    """Union mọi cặp cosine ≥ ngưỡng, không giữ embedding trên đĩa."""
    import numpy as np

    uf = UnionFind()
    owners, values = [], []
    for i, vectors in enumerate(embeddings):
        uf.find(str(i))
        for vector in vectors:
            owners.append(i)
            values.append(vector)
    if values:
        matrix = np.asarray(values, dtype=np.float32)
        for start in range(0, len(matrix), 256):
            similarities = matrix[start : start + 256] @ matrix.T
            for left, right in zip(*np.where(similarities >= threshold), strict=True):
                a, b = owners[start + int(left)], owners[int(right)]
                if a < b:
                    uf.union(str(a), str(b))
    components = defaultdict(list)
    for i, row in enumerate(rows):
        components[uf.find(str(i))].append(row)
    groups = sorted(components.values(), key=lambda group: group[0]["path"])
    for group in groups:
        identity = "\n".join(sorted(r["path"] for r in group))
        group_id = hashlib.sha256(identity.encode()).hexdigest()[:20]
        for row in group:
            row["group_id"] = group_id
    return groups


def zalo_splits(data_dir: Path, models_dir: Path, seed: int) -> tuple[SplitMap, dict]:
    records = json.loads(
        (data_dir / "raw/zalo2022/selected_manifest.json").read_text(encoding="utf-8")
    )
    zalo = []
    for item in records:
        score = str(item["liveness_score"])
        if score not in {"0", "1"}:
            raise ValueError("Zalo liveness_score không phải 0/1")
        path = safe_target(data_dir / "raw/zalo2022", item["path"])
        zalo.append(
            row_for(
                data_dir,
                "zalo2022",
                path,
                "1" if score == "0" else "0",
                "presentation_attack" if score == "0" else "bonafide",
                source_group=str(item["source_video_id"]),
            )
        )
    fas, quarantine = load_fas(data_dir)
    rows = sorted(zalo + fas, key=lambda row: row["path"])
    encoder = FaceEncoder(models_dir)
    try:
        embeddings = []
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=1) as pool:
            for i, value in enumerate(
                pool.map(encoder.encode, [data_dir / r["path"] for r in rows])
            ):
                embeddings.append(value)
                if (i + 1) % 100 == 0:
                    print(
                        f"ArcFace {i + 1}/{len(rows)}; {time.perf_counter() - started:.1f}s",
                        flush=True,
                    )
        attempts = []
        for threshold in (0.30, 0.35, 0.40, 0.45, 0.50):
            groups = face_components(rows, embeddings, threshold)
            sizes = [sum(r["source"] == "zalo2022" for r in group) for group in groups]
            largest = max(sizes, default=0)
            attempts.append({"cosine": threshold, "largest_zalo": largest})
            if largest <= 0.30 * len(zalo):
                break
        else:
            raise ValueError(f"Component Zalo >30% sau siết: {attempts}")
        result = {source: {split: [] for split in SPLITS} for source in ("zalo2022", "fas_vn")}
        missing = {rows[i]["path"] for i, value in enumerate(embeddings) if not value}
        independent = []
        for group in groups:
            if any(r["source"] == "fas_vn" or r["path"] in missing for r in group):
                for row in group:
                    result[row["source"]]["test"].append(row)
            else:
                independent.append(group)
        partition = _partition(independent, seed)
        for split in SPLITS:
            result["zalo2022"][split].extend(partition[split])
        fill_calibration_quotas({"zalo2022": result["zalo2022"]}, seed)
        report = {
            "arcface": encoder.models,
            "attempts": attempts,
            "selected_cosine": threshold,
            "zalo_component_sizes": sorted((n for n in sizes if n), reverse=True),
            "component_histogram": dict(sorted(Counter(n for n in sizes if n).items())),
            "no_face": dict(Counter(r["source"] for r in rows if r["path"] in missing)),
            "zalo_forced_test": len(result["zalo2022"]["test"]) - len(partition["test"]),
            "quarantine": quarantine,
        }
        return result, report
    finally:
        encoder.close()


def archive_rows(data_dir: Path, source: str) -> list[Row]:
    """Chỉ giải nén thành viên có chỉ mục, giữ nhóm video gốc xuyên archive."""
    folder = data_dir / "raw" / source
    index = [
        json.loads(line)
        for line in (folder / "video_groups.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    archives = defaultdict(list)
    for item in index:
        archives[item["archive"]].append(item)
    rows = []
    for archive_name, items in sorted(archives.items()):
        archive_path = safe_target(folder, archive_name)
        archive_id = hashlib.sha256(archive_name.encode()).hexdigest()[:12]
        with tarfile.open(archive_path) as archive:
            for item in items:
                target = safe_target(folder / "extracted" / archive_id, item["member"])
                info = archive.getmember(item["member"])
                if not info.isfile():
                    raise ValueError("Archive member không phải file thường")
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists() or target.stat().st_size != info.size:
                    with archive.extractfile(info) as stream, target.open("wb") as output:
                        shutil.copyfileobj(stream, output)
                split = item["source_split"]
                label = "1" if split.startswith("fake") else "0"
                origin = str(item.get("video_origin_id") or "")
                if not origin:
                    raise ValueError(f"{source}: thiếu video_origin_id")
                rows.append(
                    row_for(
                        data_dir,
                        source,
                        target,
                        label,
                        "deepfake" if label == "1" else "bonafide",
                        source_group=origin,
                        subject_id=str(item.get("subject_id") or ""),
                    )
                )
    return sorted(rows, key=lambda r: r["path"])


def wild_splits(data_dir: Path, seed: int) -> tuple[SplitMap, dict]:
    groups = _groups(archive_rows(data_dir, "wilddeepfake"))
    remaining = list(groups)
    random.Random(seed).shuffle(remaining)
    part = {split: [] for split in SPLITS}
    # Assign calib before freezing the remaining groups as test; never mine test.
    for split, minimum in (("calib_ltt", 60), ("calib_fit", 100)):
        for label in ("0", "1"):
            candidates = [g for g in remaining if any(r["label"] == label for r in g)]
            target_groups = max(1, math.ceil(len(groups) * 0.1 / 2))
            selected, count = [], 0
            for group in candidates:
                if count >= minimum and len(selected) >= target_groups:
                    break
                selected.append(group)
                count += sum(r["label"] == label for r in group)
            for group in selected:
                remaining.remove(group)
                part[split].extend(group)
    part["test"] = [row for group in remaining for row in group]
    return {"wilddeepfake": part}, {
        "policy": "ADR-0012; no train; video_origin_id across archives",
        "video_groups": len(groups),
    }


def rtfs_splits(data_dir: Path) -> tuple[SplitMap, dict]:
    """RTFS test-only; union video YouTube và ảnh donor xuyên hai generator."""
    folder = data_dir / "raw/rtfs10k"

    def read(name: str) -> list[dict]:
        with (folder / name).open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    originals = {r["filename"]: r for r in read("videos.csv")}
    rows = []
    for path in sorted((folder / "original_videos").glob("*.mp4")):
        item = originals[path.name]
        rows.append(row_for(data_dir, "rtfs10k", path, "0", "bonafide", source_group=item["id"]))
    for generator in ("inswapper", "uniface"):
        metadata = {r["filename"]: r for r in read(f"{generator}.csv")}
        for path in sorted((folder / generator).glob("*.mp4")):
            item = metadata[path.name]
            if item["success"].lower() != "true":
                raise ValueError(f"RTFS sample không success: {path.name}")
            original = originals[item["video"]]
            rows.append(
                row_for(
                    data_dir,
                    "rtfs10k",
                    path,
                    "1",
                    "faceswap",
                    source_group=original["id"],
                    reference_group=item["photo"],
                )
            )
    if not rows:
        raise ValueError("RTFS không có video local")
    _groups(rows)
    return {"rtfs10k": {split: rows if split == "test" else [] for split in SPLITS}}, {
        "policy": "RTFS test-only; union original YouTube id + donor photo; subject_id unknown",
        "videos_csv_sha256": hashlib.sha256((folder / "videos.csv").read_bytes()).hexdigest(),
        "inswapper_csv_sha256": hashlib.sha256((folder / "inswapper.csv").read_bytes()).hexdigest(),
        "uniface_csv_sha256": hashlib.sha256((folder / "uniface.csv").read_bytes()).hexdigest(),
    }


def source_splits(data_dir: Path, models_dir: Path, seed: int) -> tuple[SplitMap, dict]:
    """Chuẩn bị union video ViCocktail ∪ nhãn người vn_celeb cho DATA-04."""
    import pyarrow.parquet as pq

    videos = archive_rows(data_dir, "vicocktail")
    photos = []
    folder = data_dir / "raw/vn_celeb_faces"
    inputs = {}
    for parquet in sorted((folder / "data").glob("*.parquet")):
        inputs[parquet.name] = hashlib.sha256(parquet.read_bytes()).hexdigest()
        for i, item in enumerate(pq.read_table(parquet).to_pylist()):
            subject = str(item["label"] or "").strip()
            if not subject or not item["image"]["bytes"]:
                raise ValueError("vn_celeb thiếu nhãn người hoặc bytes ảnh")
            target = folder / "extracted" / parquet.stem / f"{i:06}.jpg"
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = item["image"]["bytes"]
            if not target.exists() or target.stat().st_size != len(payload):
                target.write_bytes(payload)
            photos.append(
                row_for(data_dir, "vn_celeb_faces", target, "0", "bonafide", subject_id=subject)
            )
    # First keep each known person/video whole, then link corpora by ArcFace.
    groups = _groups(videos) + _groups(photos)
    groups.sort(key=lambda group: group[0]["path"])
    encoder = FaceEncoder(models_dir)
    representatives = []
    embeddings = []
    missing = []
    try:
        for index, group in enumerate(groups):
            ordered = sorted(group, key=lambda r: r["path"])
            chosen = sorted({0, len(ordered) // 2, len(ordered) - 1})
            vectors = []
            for i in chosen:
                vectors.extend(encoder.encode(data_dir / ordered[i]["path"]))
            representatives.append(ordered[0])
            embeddings.append(vectors)
            if not vectors:
                missing.append(ordered[0]["group_id"])
            if (index + 1) % 25 == 0:
                print(f"DATA-04 ArcFace nhóm {index + 1}/{len(groups)}", flush=True)
        face_components(representatives, embeddings, 0.30)
        combined = defaultdict(list)
        for representative, group in zip(representatives, groups, strict=True):
            combined[representative["group_id"]].extend(group)
        # IDs are based on all members, independent of selected representatives.
        components = []
        for group in combined.values():
            identity = "\n".join(sorted(r["path"] for r in group))
            group_id = hashlib.sha256(identity.encode()).hexdigest()[:20]
            for row in group:
                row["group_id"] = group_id
            components.append(group)
        components.sort(key=lambda group: group[0]["path"])
        forced = {
            representative["group_id"]
            for representative, vectors in zip(representatives, embeddings, strict=True)
            if not vectors
        }
        partition = _partition(
            [group for group in components if group[0]["group_id"] not in forced], seed
        )
        partition["test"].extend(
            row for group in components if group[0]["group_id"] in forced for row in group
        )
        result = {
            source: {split: [] for split in SPLITS} for source in ("vicocktail", "vn_celeb_faces")
        }
        for split, rows in partition.items():
            for row in rows:
                result[row["source"]][split].append(row)
        return result, {
            "policy": "DATA-04 chỉ ghép donor/video trong CÙNG split; output kế thừa split cả hai nguồn; không ghép xuyên split",
            "arcface": encoder.models,
            "cosine": 0.30,
            "sampling": "3 clips/video origin; 3 photos/known person, first/middle/last by path; 3 frames/clip, all detected faces",
            "risk": "Không chứng minh độc lập người giữa video; có thể bỏ sót người ngoài các khung/ảnh đã lấy mẫu. Không dùng làm dữ liệu eKYC thực.",
            "input_groups": len(groups),
            "components": len(components),
            "component_sizes": sorted((len(group) for group in components), reverse=True),
            "groups_without_face": len(missing),
            "parquet_sha256": inputs,
        }
    finally:
        encoder.close()


def write_images(data_dir: Path, splits: SplitMap, seed: int, report: dict) -> Path:
    """Ghi CSV nguyên tử theo bộ và SUMMARY riêng, giữ nguyên phần âm thanh."""
    validate_splits(splits, data_dir)
    for source, part in splits.items():
        if source in {"fas_vn", "rtfs10k"} and any(
            part[split] for split in SPLITS if split != "test"
        ):
            raise ValueError(f"{source}: phải test-only")
        if source == "wilddeepfake" and part["train"]:
            raise ValueError("WildDeepfake không được có train")
    output = data_dir / "splits"
    output.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    lines = [
        "# DATA-03 — ảnh",
        "",
        f"Seed: {seed}; commit: {commit}.",
        f"Script SHA-256: {hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}",
        "0=thật, 1=giả. Path tương đối DATA_DIR. Không lưu embedding; group_id là nhóm rủi ro, không phải danh tính xác minh.",
        "ArcFace tự động không bảo đảm tìm hết cùng người; 3 khung/video, mọi mặt được thấy đều union; không rà tay.",
        "Zalo↔FAS liên kết và Zalo không thấy mặt buộc test. FAS/RTFS test-only. Wild chỉ fit/LTT/test theo video; không chứng minh độc lập người giữa video.",
        "Quota khung không tương đương số người/video độc lập; không tự chứng nhận LTT. Không dùng điểm PAD/GenD để chia.",
        "",
    ]
    for source, part in splits.items():
        lines += [
            f"## {source}",
            "",
            "| Bộ | Tập | Mẫu | Thật | Giả | Nhóm |",
            "|---|---|---:|---:|---:|---:|",
        ]
        details = []
        folder = output / source
        folder.mkdir(parents=True, exist_ok=True)
        for split in SPLITS:
            rows = sorted(part[split], key=lambda r: r["path"])
            temp = folder / f"{split}.csv.tmp"
            with temp.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            temp.replace(folder / f"{split}.csv")
            counts = Counter(r["label"] for r in rows)
            lines.append(
                f"| {source} | {split} | {len(rows)} | {counts['0']} | {counts['1']} | {len({r['group_id'] for r in rows})} |"
            )
            attacks = dict(Counter(r["attack_type"] for r in rows))
            details.append(f"- {source}/{split}: attack_type={attacks}")
        lines += ["", *details, ""]
        for split, field, targets, minimum in (
            ("calib_fit", "label", ("0", "1"), 100),
            (
                "calib_ltt",
                "attack_type",
                sorted(
                    {r["attack_type"] for rows in part.values() for r in rows if r["label"] == "1"}
                ),
                60,
            ),
        ):
            counts = Counter(r[field] for r in part[split])
            for target in targets:
                lines.append(
                    f"- {source}/{split} {target}: {counts[target]}/{minimum}; thiếu {max(0, minimum - counts[target])}."
                )
        for name in (
            "selected_manifest.json",
            "video_groups.jsonl",
            "face-anti-spoofing.zip",
            "SOURCE.md",
        ):
            path = data_dir / "raw" / source / name
            if path.exists():
                with path.open("rb") as stream:
                    lines.append(
                        f"- {source}/{name} SHA-256: {hashlib.file_digest(stream, 'sha256').hexdigest()}"
                    )
                if name == "SOURCE.md":
                    lines.extend(
                        line
                        for line in path.read_text(encoding="utf-8").splitlines()
                        if "Revision:" in line or "Nguồn:" in line
                    )
    key = "zalo2022" if "zalo2022" in splits else next(iter(splits))
    summary = output / f"SUMMARY-{key}.md"
    summary.write_text(
        "\n".join(lines)
        + "\n\n```json\n"
        + json.dumps(report, ensure_ascii=False, indent=2)
        + "\n```\n",
        encoding="utf-8",
    )
    # Stable aggregator preserves the existing audio summary.
    main_summary = output / "SUMMARY.md"
    content = (
        main_summary.read_text(encoding="utf-8")
        if main_summary.exists()
        else "# DATA-03 — thống kê chia tập\n"
    )
    content = content.replace(
        "DATA-03 còn doing: chưa có phần ảnh;", "Phần ảnh có báo cáo riêng bên dưới;"
    )
    link = f"- Ảnh {key}: [{summary.name}]({summary.name})"
    if link not in content:
        main_summary.write_text(content + "\n" + link + "\n", encoding="utf-8")
    return summary


def run_images(data_dir: Path, models_dir: Path, names: list[str], seed: int) -> None:
    if "zalo2022" in names or "fas_vn" in names:
        splits, report = zalo_splits(data_dir, models_dir, seed)
        print(write_images(data_dir, splits, seed, report), flush=True)
    if "wilddeepfake" in names:
        splits, report = wild_splits(data_dir, seed)
        print(write_images(data_dir, splits, seed, report), flush=True)
    if "rtfs10k" in names:
        splits, report = rtfs_splits(data_dir)
        print(write_images(data_dir, splits, seed, report), flush=True)
    if "vicocktail" in names or "vn_celeb_faces" in names:
        splits, report = source_splits(data_dir, models_dir, seed)
        print(write_images(data_dir, splits, seed, report), flush=True)
