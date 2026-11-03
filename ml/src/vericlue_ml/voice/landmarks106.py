"""Pinned 106-point landmarks for offline frontend comparisons, without face selection.

Preprocessing follows MIT InsightFace at revision
3e6486942a1be2da0e5b475fac375ea73264bd21:
python-package/insightface/model_zoo/landmark.py and
python-package/insightface/utils/face_align.py in deepinsight/insightface.
Only the zero-rotation crop, channel reversal and inverse-coordinate recipe
are adapted here; there is no StyleSync implementation or security decision.

The official v0.7 buffalo_l 2d106det.onnx has input data float [None,3,192,192]
and output fc1 float [1,212]. Its graph begins with _minusscalar0 (127.5)
and _mulscalar0 (0.0078125). These were inspected from the pinned artifact
with ONNX 1.20.1 ModelProto, without inference. Consequently external mean/std
are 0/1: send float pixel bytes, never apply (pixel-127.5)/128 a second time.
Weights are restricted to noncommercial research; this module grants no
runtime activation, calibration compatibility or commercial weight license.
"""

# MIT License
# Copyright (c) 2022 Jiankang Deng and Jia Guo
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import numpy as np

MODEL_SHA256 = "f001b856447c413801ef5c42091ed0cd516fcd21f2d6b79635b1e733a7109dbf"
MODEL_SIZE_BYTES = 5_030_888
INPUT_SIDE = 192
LANDMARK_COUNT = 106


def _verified_model_bytes(path: Path) -> bytes:
    if path.stat().st_size != MODEL_SIZE_BYTES:
        raise ValueError("Landmark model size differs from the pinned artifact")
    content = path.read_bytes()
    if len(content) != MODEL_SIZE_BYTES or hashlib.sha256(content).hexdigest() != MODEL_SHA256:
        raise ValueError("Landmark model SHA-256 differs from the pinned artifact")
    return content


def _single_batch_shape(shape: Sequence[object], tail: tuple[int, ...]) -> bool:
    return (
        len(shape) == len(tail) + 1
        and (shape[0] == 1 or shape[0] is None or isinstance(shape[0], str))
        and tuple(shape[1:]) == tail
    )


class Landmark106Provider:
    """One CPU session; explicit caller channel order, no implicit color conversion.

    Every call reverses the caller's three channels exactly once, as upstream's
    swapRB=True does. Thus color_order="rgb" reproduces LatentSync's RGB caller
    and feeds a BGR tensor; color_order="bgr" follows conventional InsightFace
    usage and feeds an RGB tensor. This label documents the caller contract;
    it deliberately does not change the reversal or normalize both to RGB.

    The caller must supply one selected bbox and enforce its own face-count and
    security policies. Results are unrounded original-frame pixel coordinates.
    """

    def __init__(self, model_path: Path | str, *, color_order: Literal["rgb", "bgr"]) -> None:
        if color_order not in ("rgb", "bgr"):
            raise ValueError("color_order must explicitly be 'rgb' or 'bgr'")
        content = _verified_model_bytes(Path(model_path))

        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(
            content, sess_options=options, providers=["CPUExecutionProvider"]
        )
        inputs, outputs = self._session.get_inputs(), self._session.get_outputs()
        if (
            len(inputs) != 1
            or len(outputs) != 1
            or inputs[0].type != "tensor(float)"
            or outputs[0].type != "tensor(float)"
            or not _single_batch_shape(inputs[0].shape, (3, INPUT_SIDE, INPUT_SIDE))
            or not _single_batch_shape(outputs[0].shape, (LANDMARK_COUNT * 2,))
        ):
            raise ValueError("Landmark model must have float NCHW 192 input and 106-pair output")
        self._input_name = inputs[0].name
        self._output_name = outputs[0].name
        self.color_order = color_order
        self.model_tensor_order = "bgr" if color_order == "rgb" else "rgb"

    def predict(self, frame: np.ndarray, bbox: Sequence[float] | np.ndarray) -> np.ndarray:
        """Return finite float32 (106,2) landmarks for one uint8 HWC frame and bbox."""
        import cv2

        if (
            not isinstance(frame, np.ndarray)
            or frame.dtype != np.uint8
            or frame.ndim != 3
            or frame.shape[2] != 3
            or min(frame.shape[:2]) < 1
        ):
            raise ValueError("Landmark frame must be a nonempty uint8 HWC three-channel array")
        # Preserve detector float32 scalar arithmetic before the float64 affine.
        # Early promotion changes OpenCV's quantized bilinear sample positions.
        box = np.asarray(bbox)
        if box.dtype != np.float32:
            box = np.asarray(bbox, dtype=np.float64)
        if box.shape != (4,) or not np.isfinite(box).all():
            raise ValueError("Landmark bbox must be one finite (x0,y0,x1,y1) rectangle")
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            sides = box[2:] - box[:2]
            center = (box[2] + box[0]) / 2, (box[3] + box[1]) / 2
            scale = INPUT_SIDE / (max(sides) * 1.5)
            # Upstream composes center translation and the final +96 in float64,
            # after multiplying each center scalar by scale in its native dtype.
            translation = (
                np.array([-1 * (center[0] * scale), -1 * (center[1] * scale)], dtype=np.float64)
                + INPUT_SIDE / 2
            )
        if (
            not np.isfinite(sides).all()
            or np.any(sides <= 0)
            or not np.isfinite(scale)
            or scale <= 0
            or not np.isfinite(translation).all()
        ):
            raise ValueError("Landmark bbox must have finite positive crop geometry")
        matrix = np.array(
            [[scale, 0, translation[0]], [0, scale, translation[1]]], dtype=np.float64
        )
        inverse = cv2.invertAffineTransform(matrix)
        if not np.isfinite(inverse).all() or inverse[0, 0] <= 0 or inverse[1, 1] <= 0:
            raise ValueError("Landmark crop transform is numerically singular")
        crop = cv2.warpAffine(
            frame,
            matrix,
            (INPUT_SIDE, INPUT_SIDE),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        blob = cv2.dnn.blobFromImage(
            crop,
            scalefactor=1.0,
            size=(INPUT_SIDE, INPUT_SIDE),
            mean=(0, 0, 0),
            swapRB=True,
            crop=False,
        )
        outputs = self._session.run([self._output_name], {self._input_name: blob})
        if len(outputs) != 1:
            raise ValueError("Landmark inference must return exactly one output")
        prediction = np.asarray(outputs[0])
        if (
            prediction.shape != (1, LANDMARK_COUNT * 2)
            or prediction.dtype != np.float32
            or not np.isfinite(prediction).all()
        ):
            raise ValueError("Landmark inference must return 106 finite float32 pairs")
        points = prediction.reshape(LANDMARK_COUNT, 2).copy()
        with np.errstate(over="ignore", invalid="ignore"):
            points += np.float32(1)
            points *= np.float32(INPUT_SIDE // 2)
            result = np.empty_like(points)
            for index, point in enumerate(points):
                homogeneous = np.array([point[0], point[1], 1.0], dtype=np.float32)
                result[index] = np.dot(inverse, homogeneous)
        if not np.isfinite(result).all():
            raise ValueError("Landmark inverse transform produced nonfinite coordinates")
        return result
