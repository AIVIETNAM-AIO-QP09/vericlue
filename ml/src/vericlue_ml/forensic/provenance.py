"""FOR-03 — quét nguồn gốc: thủy vân AudioSeal và chứng nhận C2PA (một chiều, ADR-0008).

Kết luận MỘT CHIỀU:
- có thủy vân AI (AudioSeal) hoặc manifest C2PA hợp lệ khai "do AI tạo" → "Phát hiện thủy vân AI của <công cụ>";
- không có → "Không có tín hiệu nguồn gốc". Câu này KHÔNG có nghĩa là thật (nhiều công cụ không gắn gì).

Cách đặt điểm: `prob_attack = None` luôn luôn (đây không phải xác suất giả mạo và không đi vào hợp nhất).
`score` chỉ để tham khảo = giá trị lớn nhất của xác suất thủy vân trung bình trong cửa sổ WINDOW_SECONDS
(AudioSeal trả xác suất theo từng mẫu); None khi không chạy được AudioSeal.

Nguồn và giấy phép:
- AudioSeal (Meta, facebookresearch/audioseal): code MIT, trọng số `detector_base.pth` MIT
  (models/manifest.yaml: audioseal-detector). Dùng thư viện pip `audioseal` nguyên bản (không chép code).
  Nạp OFFLINE từ `MODELS_DIR/audioseal-detector/detector_base.pth` bằng ĐƯỜNG DẪN file (không dùng tên
  card vì sẽ tải từ HuggingFace); kiểm SHA-256 theo manifest TRƯỚC khi `torch.load`; `nbits=16` bắt buộc.
- C2PA: thư viện pip `c2pa-python` (MIT OR Apache-2.0), đọc manifest nhúng, chặn mạng
  (`remote_manifest_fetch=false`, `ocsp_fetch=false`). Cần `validation_status`, không chỉ tin `is_valid`
  (chứng chỉ thử vẫn `Valid` nhưng `untrusted`). Không cài thư viện → C2PA ghi `unavailable`, không đổ.
- Perth (Resemble/Chatterbox): trọng số bị khóa trong manifest (chờ xác minh quyền, FOR-03) nên
  KHÔNG hỗ trợ; bằng chứng `perth` ghi rõ "chưa hỗ trợ", không giả lập.

Ngưỡng ở đây là hằng số có tên, TẠM, chưa đo trên dữ liệu thật (AGENTS.md luật 9): không phải kết quả.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections.abc import Callable
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import yaml

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import (
    ErrorCode,
    Evidence,
    EvidenceType,
    Module,
    ModuleResult,
    Status,
)

REPO_ROOT = Path(__file__).resolve().parents[4]

AUDIOSEAL_ID = "audioseal-detector"
AUDIOSEAL_FILE = "detector_base.pth"
AUDIOSEAL_NBITS = 16  # bắt buộc: checkpoint không khai nbits
SAMPLE_RATE = 16000

# Hằng số tạm (chưa đo trên dữ liệu thật). AudioSeal mặc định dùng p > 0.5 theo mẫu.
SAMPLE_THRESHOLD = 0.5
WINDOW_SECONDS = 0.5  # trung bình p trong cửa sổ này để bớt nhiễu
WINDOW_THRESHOLD = 0.5  # cửa sổ có p trung bình ≥ mức này thì "có thủy vân"
MIN_INTERVAL_SECONDS = 1.0  # khoảng ngắn hơn bị coi là nhiễu
CHUNK_SECONDS = 20.0  # xử lý theo khúc để giới hạn RAM

TOOL_AUDIOSEAL = "AudioSeal"
CONCLUSION_DETECTED = "Phát hiện thủy vân AI của {tool}"
CONCLUSION_NONE = "Không có tín hiệu nguồn gốc"
NONE_NOTE = (
    "Không có tín hiệu nguồn gốc KHÔNG có nghĩa là thật: nhiều công cụ tạo giả không gắn thủy vân."
)
PERTH_NOTE = (
    "Perth (Resemble/Chatterbox) chưa hỗ trợ: trọng số đang chờ xác minh quyền sử dụng (FOR-03)."
)

# Tên bằng chứng (ModuleResult.evidence) mà pipeline giám định đọc lại.
EV_CONCLUSION = "provenance_conclusion"
EV_TOOL = "watermark_tool"
EV_INTERVALS = "watermark_intervals"
EV_C2PA = "c2pa"
EV_NOTE = "provenance_note"
EV_PERTH = "perth"

_C2PA_KEYS = {"status", "present", "valid", "signer", "ai_generated", "note"}
# Giá trị IPTC digitalSourceType cho nội dung do AI tạo/tổng hợp.
_AI_SOURCE_MARKERS = ("trainedalgorithmicmedia", "algorithmicmedia")


# --- tóm tắt cho pipeline/job ------------------------------------------------------------------


def provenance_summary(result: ModuleResult) -> dict[str, Any]:
    """ModuleResult(provenance) → khối `provenance` của job (khớp ForensicProvenance trong contract)."""
    named: dict[str, list[Evidence]] = {}
    for item in result.evidence:
        named.setdefault(item.name, []).append(item)

    def first(name: str) -> Any:
        return named[name][0].value if name in named else None

    intervals = [
        {
            "t_start": float(i["t_start"]),
            "t_end": float(i["t_end"]),
            "prob": i.get("prob"),
        }
        for i in (first(EV_INTERVALS) or [])
        if isinstance(i, dict) and "t_start" in i and "t_end" in i
    ]
    detected = bool(intervals) or first(EV_TOOL) is not None
    tool = first(EV_TOOL)
    c2pa = first(EV_C2PA)
    if (
        isinstance(c2pa, dict)
        and c2pa.get("ai_generated") is True
        and c2pa.get("valid") is not False
    ):
        detected = True
        tool = tool or c2pa.get("signer") or "C2PA"
    conclusion = first(EV_CONCLUSION)
    if not isinstance(conclusion, str) or not conclusion:
        conclusion = CONCLUSION_DETECTED.format(tool=tool) if detected else CONCLUSION_NONE
    notes = [str(e.value) for e in named.get(EV_NOTE, []) if e.value]
    perth = first(EV_PERTH)
    if perth:
        notes.append(str(perth))
    if not detected:
        notes.append(NONE_NOTE)
    summary: dict[str, Any] = {
        "status": str(result.status),
        "conclusion": conclusion,
        "watermark_detected": detected,
        "tool": tool if detected else None,
        "watermark_intervals": intervals,
        "notes": notes,
    }
    if isinstance(c2pa, dict):
        summary["c2pa"] = {k: v for k, v in c2pa.items() if k in _C2PA_KEYS}
    return summary


# --- AudioSeal ------------------------------------------------------------------------------------


class AudioSealBackend(Protocol):
    """Trả (xác suất thủy vân theo từng mẫu ở 16 kHz, 16 bit thông điệp hoặc None)."""

    def probabilities(self, samples: np.ndarray) -> tuple[np.ndarray, list[int] | None]: ...


class ProvenanceError(Exception):
    def __init__(self, message: str, code: ErrorCode = ErrorCode.E_INTERNAL) -> None:
        super().__init__(message)
        self.code = code


def _models_root(models_dir: Path | str | None) -> Path:
    root = Path(models_dir or os.environ.get("MODELS_DIR") or REPO_ROOT / "models")
    return root if root.is_absolute() else REPO_ROOT / root


def _manifest_entry() -> dict[str, Any]:
    path = Path(os.environ.get("ML_MODELS_MANIFEST") or REPO_ROOT / "models" / "manifest.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for model in data.get("models", []):
        if model.get("id") == AUDIOSEAL_ID:
            for file in model.get("files", []):
                if file.get("path") == AUDIOSEAL_FILE:
                    return {**file, "revision": model.get("source", {}).get("revision", "")}
    raise ProvenanceError(f"Manifest không có {AUDIOSEAL_ID}/{AUDIOSEAL_FILE}.")


def _verified_weights(root: Path) -> tuple[Path, str]:
    """(đường dẫn, revision). Thiếu file hoặc sai SHA-256 → lỗi; KHÔNG bao giờ tải mạng."""
    entry = _manifest_entry()
    path = root / AUDIOSEAL_ID / AUDIOSEAL_FILE
    if not path.is_file():
        raise ProvenanceError(
            f"Thiếu trọng số {AUDIOSEAL_ID}/{AUDIOSEAL_FILE}; chạy scripts/download_models.py."
        )
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    if digest.hexdigest() != entry["sha256"]:
        raise ProvenanceError(
            f"SHA-256 của {AUDIOSEAL_ID}/{AUDIOSEAL_FILE} sai.", ErrorCode.E_INTEGRITY
        )
    return path, str(entry["revision"])


class RealAudioSeal:
    """Bộ dò AudioSeal thật (thư viện `audioseal` + torch, CPU được). Nạp một lần."""

    def __init__(self, path: Path, revision: str) -> None:
        # Windows không có trình biên dịch C++ thì torch.compile của audioseal lỗi.
        os.environ.setdefault("NO_TORCH_COMPILE", "1")
        import torch
        from audioseal import AudioSeal

        self._torch = torch
        # Nạp bằng ĐƯỜNG DẪN file (offline); torch.load(weights_only=False) chỉ chạy SAU khi đã kiểm SHA-256.
        self._detector = AudioSeal.load_detector(str(path), nbits=AUDIOSEAL_NBITS)
        self._detector.eval()
        self.revision = revision

    def probabilities(self, samples: np.ndarray) -> tuple[np.ndarray, list[int] | None]:
        torch = self._torch
        chunk = int(CHUNK_SECONDS * SAMPLE_RATE)
        probs: list[np.ndarray] = []
        message_votes = np.zeros(AUDIOSEAL_NBITS, dtype=np.float64)
        weight = 0.0
        with torch.inference_mode():
            for start in range(0, len(samples), chunk):
                part = samples[start : start + chunk]
                if part.size < SAMPLE_RATE // 10:
                    probs.append(np.zeros(part.size, dtype=np.float32))
                    continue
                x = torch.from_numpy(np.ascontiguousarray(part, dtype=np.float32))[None, None, :]
                result, message = self._detector(x, sample_rate=SAMPLE_RATE)
                p = result[0, 1, :].cpu().numpy()
                probs.append(p)
                votes = message[0].cpu().numpy().astype(np.float64)
                message_votes += votes * p.mean()
                weight += float(p.mean())
        joined = np.concatenate(probs) if probs else np.zeros(0, dtype=np.float32)
        bits = [int(v >= 0.5) for v in message_votes / weight] if weight > 0 else None
        return joined, bits


def watermark_intervals(
    probs: np.ndarray, rate: int = SAMPLE_RATE
) -> tuple[list[dict[str, float | None]], float]:
    """Xác suất theo mẫu → khoảng có thủy vân (giây) và p cửa sổ lớn nhất.

    Chia cửa sổ WINDOW_SECONDS, cửa sổ có p trung bình ≥ WINDOW_THRESHOLD là "có"; các cửa sổ liền kề
    gộp thành khoảng, khoảng ngắn hơn MIN_INTERVAL_SECONDS bị bỏ (nhiễu).
    """
    if probs.size == 0:
        return [], 0.0
    win = max(1, int(WINDOW_SECONDS * rate))
    count = int(np.ceil(probs.size / win))
    means = np.array([probs[i * win : (i + 1) * win].mean() for i in range(count)])
    marked = means >= WINDOW_THRESHOLD
    intervals: list[dict[str, float | None]] = []
    i = 0
    while i < count:
        if not marked[i]:
            i += 1
            continue
        j = i
        while j + 1 < count and marked[j + 1]:
            j += 1
        t0 = i * win / rate
        t1 = min((j + 1) * win, probs.size) / rate
        if t1 - t0 >= MIN_INTERVAL_SECONDS:
            intervals.append(
                {
                    "t_start": round(t0, 3),
                    "t_end": round(t1, 3),
                    "prob": float(means[i : j + 1].mean()),
                }
            )
        i = j + 1
    return intervals, float(means.max())


# --- C2PA -------------------------------------------------------------------------------------------

C2paReader = Callable[[Path], dict[str, Any]]


def read_c2pa(path: Path) -> dict[str, Any]:
    """Đọc manifest C2PA nhúng (offline). Trả dict khớp ForensicProvenance.c2pa (status/present/...).

    status: ok (đọc được, có hoặc không có manifest), unavailable (thiếu thư viện), error (file hỏng).
    """
    try:
        import c2pa
    except ImportError:
        return {
            "status": "unavailable",
            "note": "Chưa cài c2pa-python (extra c2pa); không đọc C2PA.",
        }
    try:
        context = c2pa.Context.from_dict(
            {"verify": {"remote_manifest_fetch": False, "ocsp_fetch": False}}
        )
        reader = c2pa.Reader(str(path), context=context)
    except Exception as exc:  # noqa: BLE001
        if "ManifestNotFound" in type(exc).__name__:
            return {"status": "ok", "present": False, "note": "File không có manifest C2PA."}
        return {"status": "error", "note": f"Không đọc được C2PA ({type(exc).__name__})."}
    try:
        data = json.loads(reader.json())
        return parse_c2pa_manifest(data)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "present": True,
            "note": f"Manifest C2PA lỗi ({type(exc).__name__}).",
        }


def parse_c2pa_manifest(data: dict[str, Any]) -> dict[str, Any]:
    """JSON của c2pa Reader → tóm tắt. Hàm thuần để test không cần thư viện."""
    manifests = data.get("manifests") or {}
    active = manifests.get(data.get("active_manifest") or "", {})
    signer = None
    info = active.get("signature_info") or {}
    signer = info.get("common_name") or info.get("issuer")
    ai_generated: bool | None = None
    for assertion in active.get("assertions") or []:
        label = str(assertion.get("label", ""))
        if label.startswith("c2pa.actions"):
            for action in (assertion.get("data") or {}).get("actions", []):
                source = str(action.get("digitalSourceType", "")).lower().replace("_", "")
                if any(marker in source for marker in _AI_SOURCE_MARKERS):
                    ai_generated = True
    failures = [
        str(s.get("code", ""))
        for s in (data.get("validation_status") or [])
        if str(s.get("code", "")) != "signingCredential.untrusted"
    ]
    untrusted = any(
        str(s.get("code", "")) == "signingCredential.untrusted"
        for s in (data.get("validation_status") or [])
    )
    state = str(data.get("validation_state", ""))
    valid = state in {"Valid", "Trusted"} and not failures
    note = (
        "Chứng chỉ ký chưa được tin cậy (không nằm trong danh sách tin cậy)." if untrusted else ""
    )
    out: dict[str, Any] = {
        "status": "ok",
        "present": True,
        "valid": valid,
        "signer": signer,
        "ai_generated": ai_generated,
    }
    if note:
        out["note"] = note
    return out


# --- bộ phát hiện -----------------------------------------------------------------------------------


def _package_version(name: str) -> str:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return "none"


class ProvenanceDetector:
    """Module `provenance`: AudioSeal (khoảng thủy vân) + C2PA (manifest). Một chiều, prob_attack=None."""

    name = Module.PROVENANCE.value
    version = "audioseal-detector+c2pa@unloaded"

    def __init__(
        self,
        *,
        audioseal: AudioSealBackend | None = None,
        c2pa_reader: C2paReader | None = None,
    ) -> None:
        self._audioseal = audioseal
        self._audioseal_error: ProvenanceError | None = None
        self._c2pa_reader = c2pa_reader or read_c2pa
        self._revision = ""
        self._lock = threading.Lock()
        if audioseal is not None:
            self.version = "audioseal-detector@injected+c2pa@injected"

    def preload(self, *, models_dir: Path | str | None = None) -> None:
        """Nạp AudioSeal một lần (kiểm SHA-256, offline). Lỗi 'dính': không thử lại mỗi lần gọi."""
        with self._lock:
            if self._audioseal is not None or self._audioseal_error is not None:
                return
            try:
                path, revision = _verified_weights(_models_root(models_dir))
                self._audioseal = RealAudioSeal(path, revision)
                self._revision = revision
                self.version = (
                    f"{AUDIOSEAL_ID}@{revision[:8]}+c2pa-python@{_package_version('c2pa-python')}"
                )
            except ProvenanceError as exc:
                self._audioseal_error = exc
            except ImportError:
                self._audioseal_error = ProvenanceError(
                    "Chưa cài thư viện audioseal/torch (extra forensic)."
                )
            except Exception as exc:  # noqa: BLE001
                self._audioseal_error = ProvenanceError(
                    f"Không nạp được AudioSeal ({type(exc).__name__})."
                )

    def _text(self, name: str, value: Any, label: str) -> Evidence:
        return Evidence(type=EvidenceType.TEXT, name=name, value=value, label_vi=label)

    def predict(self, inp: DetectorInput) -> ModuleResult:
        started = time.perf_counter()
        evidence: list[Evidence] = []
        quality: dict[str, float | str | bool | None] = {}
        score: float | None = None
        ran_any = False
        audio_failed = False  # có âm thanh nhưng AudioSeal không chạy được → quét chưa đầy đủ
        detected = False
        tool: str | None = None

        # 1) AudioSeal trên âm thanh
        if inp.audio is None:
            evidence.append(
                self._text(EV_NOTE, "Không có âm thanh để quét thủy vân AudioSeal.", "Ghi chú")
            )
        else:
            self.preload()
            if self._audioseal is None:
                reason = (
                    self._audioseal_error.args[0]
                    if self._audioseal_error
                    else "AudioSeal chưa sẵn sàng."
                )
                evidence.append(self._text(EV_NOTE, f"AudioSeal không chạy: {reason}", "Ghi chú"))
                audio_failed = True
            else:
                try:
                    samples = _load_audio16k(inp.audio)
                    probs, bits = self._audioseal.probabilities(samples)
                    intervals, peak = watermark_intervals(probs)
                    ran_any = True
                    score = peak
                    quality["audio_seconds"] = round(samples.size / SAMPLE_RATE, 3)
                    if intervals:
                        detected = True
                        tool = TOOL_AUDIOSEAL
                        evidence.append(
                            Evidence(
                                type=EvidenceType.SEGMENTS,
                                name=EV_INTERVALS,
                                value=intervals,
                                unit="s",
                                label_vi="Khoảng có thủy vân AudioSeal",
                            )
                        )
                        if bits is not None:
                            word = "".join(str(b) for b in bits)
                            evidence.append(
                                self._text(
                                    EV_NOTE,
                                    f"Thông điệp 16 bit của thủy vân: {word} "
                                    "(công cụ tạo cụ thể không suy ra được từ thông điệp).",
                                    "Ghi chú",
                                )
                            )
                except Exception as exc:  # noqa: BLE001
                    audio_failed = True
                    evidence.append(
                        self._text(
                            EV_NOTE,
                            f"AudioSeal gặp lỗi khi quét ({type(exc).__name__}).",
                            "Ghi chú",
                        )
                    )

        # 2) C2PA trên file gốc (container)
        source = inp.metadata.get("source_file")
        c2pa_info: dict[str, Any] | None = None
        if source:
            c2pa_info = self._c2pa_reader(Path(str(source)))
            evidence.append(
                Evidence(
                    type=EvidenceType.TEXT,
                    name=EV_C2PA,
                    value=c2pa_info,
                    label_vi="Chứng nhận C2PA",
                )
            )
            if c2pa_info.get("status") == "ok":
                ran_any = True
            if c2pa_info.get("ai_generated") is True and c2pa_info.get("valid") is not False:
                detected = True
                tool = tool or c2pa_info.get("signer") or "C2PA"

        # 3) Perth: chưa hỗ trợ
        evidence.append(self._text(EV_PERTH, PERTH_NOTE, "Perth"))
        if audio_failed and not detected:
            evidence.append(
                self._text(
                    EV_NOTE,
                    "Quét chưa đầy đủ: AudioSeal không chạy được, kết quả chỉ phản ánh phần đã quét.",
                    "Ghi chú",
                )
            )

        conclusion = CONCLUSION_DETECTED.format(tool=tool) if detected else CONCLUSION_NONE
        evidence.append(self._text(EV_CONCLUSION, conclusion, "Kết luận nguồn gốc"))
        if detected and tool:
            evidence.append(self._text(EV_TOOL, tool, "Công cụ"))
        return ModuleResult(
            module=Module.PROVENANCE,
            model_version=self.version,
            # Không quét được gì, hoặc AudioSeal không chạy được trên âm thanh có sẵn → degraded: không để
            # `ok` + "Không có tín hiệu nguồn gốc" (không bao giờ hiểu là "thật").
            status=Status.OK if ran_any and not audio_failed else Status.DEGRADED,
            score=score,
            prob_attack=None,
            quality=quality,
            evidence=evidence,
            latency_ms=(time.perf_counter() - started) * 1000,
        )


def _load_audio16k(path: Path) -> np.ndarray:
    from vericlue_ml.forensic.media import _decode_audio_file

    samples = _decode_audio_file(Path(path))
    if samples is None or samples.size == 0:
        raise ProvenanceError("Không đọc được âm thanh (WAV/FLAC/OGG).")
    return samples
