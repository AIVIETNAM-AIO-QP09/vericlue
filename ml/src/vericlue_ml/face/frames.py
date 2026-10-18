"""Đọc khung hình từ video hoặc ảnh cho `face_deepfake` và `quality` (FACE-02).

Video từ trình duyệt (webm VP8/VP9 do MediaRecorder ghi) thường KHÔNG có số khung hoặc thời lượng
đúng trong container, nên không tin `CAP_PROP_FRAME_COUNT`: đọc tuần tự bằng `grab()` để đếm số khung
thật, rồi đọc lại và lấy đúng các khung đều nhau. Khung được trả dần (generator) để không giữ nhiều
khung độ phân giải gốc trong bộ nhớ. Ảnh trả về là BGR (quy ước của OpenCV).

`sample_video` trả thêm số khung ĐÃ YÊU CẦU (`min(count, số khung thật)`): khung giải mã hỏng bị
bỏ qua nhưng vẫn tính là thiếu, để video cắt cụt không thể ra kết quả "đủ khung".
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np

from vericlue_ml.common.result import ErrorCode
from vericlue_ml.face.pad import PadError, _decode

# Chặn video quá dài (bom giải mã): chỉ đếm và lấy mẫu trong chừng này khung đầu (~1 phút ở 30 fps).
# Phần video sau mốc này không được xem xét.
MAX_SCAN_FRAMES = 1800

Frames = Iterator[tuple[int, np.ndarray]]


def even_indices(total: int, count: int) -> list[int]:
    """`count` chỉ số đều nhau trong [0, total-1] (cả hai đầu), bỏ trùng, theo thứ tự tăng."""
    if total <= 0 or count <= 0:
        return []
    if total <= count:
        return list(range(total))
    return sorted({int(i) for i in np.linspace(0, total - 1, count).round()})


def sample_images(paths: list[Path], count: int) -> tuple[int, Frames]:
    """(số ảnh yêu cầu, ảnh đều nhau); ảnh hỏng thì ném PadError(E_DECODE) khi duyệt tới."""
    chosen = even_indices(len(paths), count)

    def generate() -> Frames:
        for i in chosen:
            yield i, _decode(Path(paths[i]))

    return len(chosen), generate()


def read_images(paths: list[Path], count: int) -> list[tuple[int, np.ndarray]]:
    """Như `sample_images` nhưng trả danh sách."""
    return list(sample_images(paths, count)[1])


def sample_video(path: Path, count: int) -> tuple[int, Frames]:
    """Trả (số khung yêu cầu, generator (chỉ số khung, ảnh BGR)) cho `count` khung đều nhau.

    Không mở được hoặc không có khung nào đọc được thì ném PadError(E_DECODE) ngay (lượt đếm khung
    chạy trước khi trả). Generator đóng capture khi duyệt hết hoặc khi bị `close()`.
    """
    import cv2

    def open_capture():
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            capture.release()
            raise PadError("Không mở được video.", ErrorCode.E_DECODE)
        return capture

    try:
        capture = open_capture()
        try:
            total = 0
            while total < MAX_SCAN_FRAMES and capture.grab():
                total += 1
        finally:
            capture.release()
    except PadError:
        raise
    except Exception as exc:
        raise PadError("Không đọc được video.", ErrorCode.E_DECODE) from exc
    if total == 0:
        raise PadError("Video không có khung hình đọc được.", ErrorCode.E_DECODE)

    wanted = even_indices(total, count)
    pending = set(wanted)

    def generate() -> Frames:
        try:
            capture = open_capture()
        except PadError:
            return
        try:
            for index in range(wanted[-1] + 1):
                if not capture.grab():
                    break
                if index in pending:
                    ok, frame = capture.retrieve()
                    if ok and frame is not None and frame.size > 0:
                        yield index, frame
        finally:
            capture.release()

    return len(wanted), generate()


def read_video_frames(path: Path, count: int) -> list[tuple[int, np.ndarray]]:
    """Như `sample_video` nhưng trả danh sách; không giải mã nổi khung nào thì ném PadError(E_DECODE)."""
    try:
        frames = list(sample_video(path, count)[1])
    except PadError:
        raise
    except Exception as exc:
        raise PadError("Không đọc được video.", ErrorCode.E_DECODE) from exc
    if not frames:
        raise PadError("Không giải mã được khung nào của video.", ErrorCode.E_DECODE)
    return frames


def middle_video_frame(path: Path) -> np.ndarray:
    """Khung ở giữa của video (một trong ba khung đều nhau), chỉ giải mã tới khung đó."""
    _, frames = sample_video(path, 3)
    kept: list[np.ndarray] = []
    try:
        for position, (_, frame) in enumerate(frames):
            kept = [frame]
            if position == 1:
                break
    except Exception as exc:
        raise PadError("Không đọc được video.", ErrorCode.E_DECODE) from exc
    finally:
        frames.close()  # type: ignore[attr-defined]
    if not kept:
        raise PadError("Không giải mã được khung nào của video.", ErrorCode.E_DECODE)
    return kept[0]
