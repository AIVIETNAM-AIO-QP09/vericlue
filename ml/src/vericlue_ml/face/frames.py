"""Đọc khung hình từ video hoặc ảnh cho `face_deepfake` và `quality` (FACE-02).

Video từ trình duyệt (webm VP8/VP9 do MediaRecorder ghi) thường KHÔNG có số khung hoặc thời lượng
đúng trong container, nên không tin `CAP_PROP_FRAME_COUNT`: đọc tuần tự bằng `grab()` để đếm số khung
thật, rồi đọc lại và lấy đúng các khung đều nhau. Ảnh trả về là BGR (quy ước của OpenCV).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from vericlue_ml.common.result import ErrorCode
from vericlue_ml.face.pad import PadError, _decode

# Chặn video quá dài (bom giải mã): chỉ đếm và lấy mẫu trong chừng này khung đầu (~5 phút ở 30 fps).
MAX_SCAN_FRAMES = 9000


def even_indices(total: int, count: int) -> list[int]:
    """`count` chỉ số đều nhau trong [0, total-1] (cả hai đầu), bỏ trùng, theo thứ tự tăng."""
    if total <= 0 or count <= 0:
        return []
    if total <= count:
        return list(range(total))
    return sorted({int(i) for i in np.linspace(0, total - 1, count).round()})


def read_images(paths: list[Path], count: int) -> list[tuple[int, np.ndarray]]:
    """Lấy tối đa `count` ảnh đều nhau từ danh sách; ảnh hỏng thì ném PadError(E_DECODE)."""
    return [(i, _decode(Path(paths[i]))) for i in even_indices(len(paths), count)]


def read_video_frames(path: Path, count: int) -> list[tuple[int, np.ndarray]]:
    """Lấy `count` khung đều nhau của video, trả về [(chỉ số khung, ảnh BGR)].

    Không mở được hoặc không đọc nổi khung nào thì ném PadError(E_DECODE).
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
        if total == 0:
            raise PadError("Video không có khung hình đọc được.", ErrorCode.E_DECODE)

        wanted = even_indices(total, count)
        pending = set(wanted)
        capture = open_capture()
        frames: list[tuple[int, np.ndarray]] = []
        try:
            for index in range(wanted[-1] + 1):
                if not capture.grab():
                    break
                if index in pending:
                    ok, frame = capture.retrieve()
                    if ok and frame is not None and frame.size > 0:
                        frames.append((index, frame))
        finally:
            capture.release()
    except PadError:
        raise
    except Exception as exc:
        raise PadError("Không đọc được video.", ErrorCode.E_DECODE) from exc
    if not frames:
        raise PadError("Không giải mã được khung nào của video.", ErrorCode.E_DECODE)
    return frames
