"""Tác vụ nền của giám định (FOR-01): mở file, chạy ForensicPipeline, ghi tiến độ và kết quả.

Chạy trong luồng của BackgroundTasks, MỖI bước ghi DB bằng một transaction riêng (transaction của request
đã commit trước khi tác vụ bắt đầu). Chỉ một phân tích chạy một lúc (khóa tiến trình): mô hình nặng, CPU.

Quy tắc trung thực:
- Dùng lại detector đã preload của orchestrator; module nằm ngoài hồ sơ router thì tự nạp (một lần).
- Detector giả lập (version "mock@...") KHÔNG bao giờ được dùng làm bằng chứng giám định: coi như
  `unavailable`, kết luận tổng sẽ là `inconclusive` nếu đó là bước bắt buộc.
- Lipsync luôn `unavailable` ở giám định (cần video đoạn + câu đề bài của VOICE-05).
"""

from __future__ import annotations

import inspect
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vericlue_ml.common.detector import Detector
from vericlue_ml.common.result import Module
from vericlue_ml.forensic.media import FileMediaSource, MediaError
from vericlue_ml.forensic.pipeline import ForensicPipeline, Thresholds
from vericlue_ml.registry import REAL_TASK, get_detector

if TYPE_CHECKING:
    from vericlue_api.core.state import ApplicationState

logger = logging.getLogger(__name__)

_ANALYSIS_LOCK = threading.Lock()

# Mỗi job xếp hàng giữ một luồng của threadpool (chờ khóa). Giới hạn số job chờ để GET /jobs vẫn phục vụ được;
# vượt thì POST trả 429. Hằng số tạm. Hàng đợi một worker thật sự là việc sau (FOR-01 đầy đủ).
MAX_PENDING_JOBS = 8
_PENDING = 0
_PENDING_LOCK = threading.Lock()


def reserve_slot() -> bool:
    """Giữ một chỗ trong hàng đợi giám định; False nếu đã đầy."""
    global _PENDING
    with _PENDING_LOCK:
        if _PENDING >= MAX_PENDING_JOBS:
            return False
        _PENDING += 1
        return True


def release_slot() -> None:
    global _PENDING
    with _PENDING_LOCK:
        _PENDING = max(0, _PENDING - 1)


_OWN_DETECTORS: dict[Module, Detector] = {}
_OWN_LOCK = threading.Lock()

LIPSYNC_REASON_REGISTERED = (
    "Khớp môi cần video đoạn và câu đề bài (VOICE-05); chưa hỗ trợ giám định theo đoạn."
)


def _is_mock(detector: Detector) -> bool:
    return str(getattr(detector, "version", "")).startswith("mock@")


def _load_own(root: ApplicationState, module: Module) -> tuple[Detector | None, str | None]:
    """Nạp (một lần) detector ngoài hồ sơ router, ví dụ provenance ở hồ sơ mvp."""
    with _OWN_LOCK:
        if module in _OWN_DETECTORS:
            return _OWN_DETECTORS[module], None
        try:
            detector = get_detector(module, mock=False)
        except NotImplementedError:
            return None, f"Chưa có mô hình thật ({REAL_TASK[module]})"
        except Exception:  # noqa: BLE001
            logger.warning("forensic_detector_create_failed module=%s", module)
            return None, "Không khởi tạo được mô hình"
        preload = getattr(detector, "preload", None)
        if preload is not None:
            params = inspect.signature(preload).parameters
            kwargs: dict[str, Any] = {}
            if "models_dir" in params:
                kwargs["models_dir"] = Path(root.settings.models_dir)
            if "device" in params:
                kwargs["device"] = root.settings.device
            try:
                preload(**kwargs)
            except Exception:  # noqa: BLE001
                logger.warning("forensic_detector_preload_failed module=%s", module)
                return None, "Không nạp được trọng số mô hình (thiếu file hoặc sai SHA-256)"
        _OWN_DETECTORS[module] = detector
        return detector, None


def resolve_detectors(root: ApplicationState) -> tuple[dict[Module, Detector], dict[Module, str]]:
    detectors: dict[Module, Detector] = {}
    unavailable: dict[Module, str] = {}
    failed = set(root.orchestrator.failed_modules)
    for module in (Module.FACE_DEEPFAKE, Module.VOICE_SPOOF, Module.PROVENANCE):
        detector = root.orchestrator.loaded_detector(module)
        reason: str | None = None
        if detector is None:
            if module.value in failed:
                reason = "Nạp mô hình thất bại khi khởi động API"
            else:
                detector, reason = _load_own(root, module)
        if detector is not None and _is_mock(detector):
            detector, reason = (
                None,
                f"Chỉ có mô-đun giả lập, chưa có mô hình thật ({REAL_TASK[module]})",
            )
        if detector is None:
            unavailable[module] = reason or f"Chưa có mô hình thật ({REAL_TASK[module]})"
        else:
            detectors[module] = detector
    try:
        get_detector(Module.LIPSYNC, mock=False)
        unavailable[Module.LIPSYNC] = LIPSYNC_REASON_REGISTERED
    except NotImplementedError:
        unavailable[Module.LIPSYNC] = f"Chưa có mô hình thật ({REAL_TASK[Module.LIPSYNC]})"
    except Exception:  # noqa: BLE001
        unavailable[Module.LIPSYNC] = "Không khởi tạo được mô hình"
    return detectors, unavailable


def build_pipeline(root: ApplicationState) -> ForensicPipeline:
    """Ngưỡng như eKYC (thresholds.yaml, không sửa); điểm thô → xác suất qua calibrator hiện có."""
    config = root.settings.router_config
    detectors, unavailable = resolve_detectors(root)
    return ForensicPipeline(
        detectors,
        unavailable,
        root.orchestrator.router.calibrators.apply,
        Thresholds(
            face_b=config.face.b, face_a=config.face.a, voice_spoof=config.voice.spoof_threshold
        ),
    )


def run_forensic_job(
    root: ApplicationState,
    job_id: str,
    *,
    open_source: Any = None,
    pipeline_builder: Any = None,
) -> None:
    """Chạy một job đã `queued`. Mọi lỗi thành job `failed` (verdict trống), không bao giờ `authentic`."""
    open_source = open_source or FileMediaSource  # phân giải lúc gọi để test thay được
    pipeline_builder = pipeline_builder or build_pipeline
    try:
        _run_locked(root, job_id, open_source, pipeline_builder)
    finally:
        release_slot()


def _run_locked(
    root: ApplicationState, job_id: str, open_source: Any, pipeline_builder: Any
) -> None:
    with _ANALYSIS_LOCK:
        try:
            with root.transaction() as state:
                state.forensic.mark_running(job_id)
                path = state.forensic.source_path(job_id)
            if path is None:
                return
            source = open_source(Path(path))
            pipeline = pipeline_builder(root)

            def on_progress(stage: str, done: int, total: int) -> None:
                with root.transaction() as state:
                    state.forensic.set_progress(job_id, stage, done, total)

            analysis = pipeline.run(source, on_progress)
            with root.transaction() as state:
                state.forensic.complete(job_id, analysis, source.info.to_dict())
        except MediaError as exc:
            _fail(root, job_id, exc.code, str(exc))
        except Exception:  # noqa: BLE001
            logger.exception("forensic_job_failed job_id=%s", job_id)
            _fail(
                root,
                job_id,
                "analysis_failed",
                "Phân tích gặp lỗi nội bộ; thử lại hoặc báo quản trị.",
            )


def _fail(root: ApplicationState, job_id: str, code: str, message: str) -> None:
    try:
        with root.transaction() as state:
            state.forensic.fail(job_id, code, message)
    except Exception:  # noqa: BLE001
        logger.exception("forensic_job_fail_record_failed job_id=%s", job_id)
