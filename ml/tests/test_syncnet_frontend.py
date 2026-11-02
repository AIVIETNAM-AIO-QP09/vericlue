"""Synthetic oracles for the independent, offline SyncNet spatial candidate."""

from __future__ import annotations

import importlib
import importlib.util

import numpy as np
import pytest


def _frontend():
    name = "vericlue_ml.eval.syncnet_frontend"
    assert importlib.util.find_spec(name) is not None, "Independent frontend is not implemented"
    return importlib.import_module(name)


def _landmarks(points: np.ndarray) -> np.ndarray:
    landmarks = np.zeros((106, 2), dtype=np.float32)
    for indices, point in zip(
        ([43, 48, 49, 51, 50], [101, 102, 103, 104, 105], [74, 77, 83, 86]),
        points,
        strict=True,
    ):
        landmarks[indices] = point
    return landmarks


def test_similarity_recovers_forward_rotation_scale_translation() -> None:
    frontend = _frontend()
    source = np.array([[-1, 0], [1, 0], [0, 3]], dtype=np.float32)
    target = np.array([[10, 18], [10, 22], [4, 20]], dtype=np.float32)

    result = frontend.fit_similarity(source, target)

    np.testing.assert_allclose(result.matrix, [[0, -2, 10], [2, 0, 20]], atol=2e-6)
    # Six centered coordinates, correction=1: std=sqrt(8/5).
    np.testing.assert_allclose(result.bias, [-1.58113883, -1.58113883], atol=2e-6)
    assert result.matrix.dtype == np.float32
    assert result.bias.dtype == np.float32


def test_similarity_uses_ratio_of_stds_instead_of_least_squares_scale() -> None:
    frontend = _frontend()
    result = frontend.fit_similarity(
        np.array([[0, 0], [4, 0], [0, 2]], dtype=np.float32),
        np.array([[0, 0], [2, 0], [0, 2]], dtype=np.float32),
    )
    # The centered sums of squares are 40/3 and 16/3.
    assert np.linalg.norm(result.matrix[:, 0]) == pytest.approx(np.sqrt(0.4), abs=2e-6)


def test_reflected_triangle_is_not_accepted_as_a_reflection() -> None:
    frontend = _frontend()
    source = np.array([[-2, -1], [2, -1], [0, 3]], dtype=np.float32)
    target = source * [-1, 1]
    matrix = frontend.fit_similarity(source, target).matrix
    assert np.linalg.det(matrix[:, :2]) > 0
    transformed = source @ matrix[:, :2].T + matrix[:, 2]
    assert not np.allclose(transformed, target)


@pytest.mark.parametrize(
    "points",
    [
        np.zeros((3, 2)),
        np.array([[0, 0], [1, 1], [2, 2]]),
        np.array([[0, 0], [1, 1], [np.nan, 2]]),
        np.array([[0, 0], [1, 1], [np.inf, 2]]),
        np.ones((2, 2)),
    ],
)
def test_similarity_rejects_nonfinite_or_degenerate_geometry(points: np.ndarray) -> None:
    frontend = _frontend()
    valid = np.array([[0, 0], [2, 0], [1, 2]], dtype=np.float32)
    with pytest.raises(frontend.SyncNetFrontendError):
        frontend.fit_similarity(points, valid)
    with pytest.raises(frontend.SyncNetFrontendError):
        frontend.fit_similarity(valid, points)


def test_landmark_groups_are_rounded_before_and_after_averaging() -> None:
    frontend = _frontend()
    landmarks = _landmarks(np.array([[0, 0], [2.5, 3.5], [7.5, 8.5]]))
    landmarks[[43, 48, 49, 51, 50], 0] = [0.49, 0.49, 0.49, 1.49, 1.49]
    points = frontend.three_points_from_landmarks(landmarks)
    # Rounding the first group's raw mean would produce 1, not 0.
    np.testing.assert_array_equal(points, [[0, 0], [2, 4], [8, 8]])
    assert points.dtype == np.float32


@pytest.mark.parametrize("shape", [(5, 2), (106, 3), (1, 106, 2)])
def test_landmarks_require_the_complete_106_pair_array(shape: tuple[int, ...]) -> None:
    frontend = _frontend()
    with pytest.raises(frontend.SyncNetFrontendError):
        frontend.three_points_from_landmarks(np.zeros(shape))


def test_nonfinite_unused_landmark_is_rejected() -> None:
    frontend = _frontend()
    landmarks = _landmarks(np.array([[10, 10], [30, 10], [20, 30]]))
    landmarks[0, 0] = np.nan
    with pytest.raises(frontend.SyncNetFrontendError):
        frontend.three_points_from_landmarks(landmarks)


def test_target_geometry_uses_observed_aspect_and_scale() -> None:
    frontend = _frontend()
    candidate = frontend.SyncNetFrontendCandidate()
    np.testing.assert_allclose(candidate.target_points, [[47.6, 56], [162.4, 56], [105, 112]])
    assert candidate.intermediate_size_wh == (210, 280)
    # A caller cannot mutate the target of subsequent frames through this view.
    candidate.target_points[0] = 0
    assert candidate.target_points[0, 0] == pytest.approx(47.6)


def test_bias_smoothing_uses_full_video_history_and_resets() -> None:
    frontend = _frontend()
    candidate = frontend.SyncNetFrontendCandidate()
    points = (
        np.array([[-10, 0], [10, 0], [0, 20]]),
        np.array([[0, -10], [0, 10], [-20, 0]]),
        np.array([[10, 0], [-10, 0], [0, -20]]),
    )
    results = [
        candidate.geometry_for_frame(_landmarks(value), frame_index=index)
        for index, value in enumerate(points)
    ]
    # From centered sums of squares: target mouth y=0.8960190388,
    # source mouth norm=1.3801311187; h[j]=0.2*h[j-1]+0.8*b[j].
    expected_biases = [[0, -0.48411208], [1.10410489, 0.61999282], [0.22082098, 1.94491869]]
    for result, expected in zip(results, expected_biases, strict=True):
        np.testing.assert_allclose(result.smoothed_bias, expected, atol=2e-6)
        unsmoothed = frontend.fit_similarity(result.source_points, candidate.target_points)
        np.testing.assert_allclose(result.matrix[:, :2], unsmoothed.matrix[:, :2], atol=2e-6)
        np.testing.assert_allclose(
            result.matrix[:, 2], unsmoothed.matrix[:, 2] + expected, atol=1e-5
        )
    # Starting only at the selected window omits earlier history and is different.
    selected_only = frontend.SyncNetFrontendCandidate().geometry_for_frame(
        _landmarks(points[-1]), frame_index=0
    )
    assert not np.allclose(results[-1].matrix, selected_only.matrix)
    candidate.reset()
    after_reset = candidate.geometry_for_frame(_landmarks(points[-1]), frame_index=0)
    np.testing.assert_array_equal(after_reset.matrix, selected_only.matrix)


def test_frame_order_rejects_skips_repeats_and_out_of_order_without_advancing() -> None:
    frontend = _frontend()
    landmarks = _landmarks(np.array([[0, 0], [10, 0], [5, 10]]))
    candidate = frontend.SyncNetFrontendCandidate()
    for wrong in (1, -1, 0.5, True):
        with pytest.raises(frontend.SyncNetFrontendError):
            candidate.geometry_for_frame(landmarks, frame_index=wrong)
    candidate.geometry_for_frame(landmarks, frame_index=0)
    for wrong in (0, 2, -1):
        with pytest.raises(frontend.SyncNetFrontendError):
            candidate.geometry_for_frame(landmarks, frame_index=wrong)
    result = candidate.geometry_for_frame(landmarks, frame_index=1)
    assert result.frame_index == 1


def test_invalid_geometry_does_not_advance_video_state() -> None:
    frontend = _frontend()
    landmarks = _landmarks(np.array([[0, 0], [10, 0], [5, 10]]))
    candidate = frontend.SyncNetFrontendCandidate()
    candidate.geometry_for_frame(landmarks, frame_index=0)
    with pytest.raises(frontend.SyncNetFrontendError):
        candidate.geometry_for_frame(np.zeros((106, 2)), frame_index=1)
    recovered = candidate.geometry_for_frame(landmarks, frame_index=1)
    assert recovered.frame_index == 1


def test_candidate_versions_distinguish_warp_precision() -> None:
    frontend = _frontend()
    float32 = frontend.SyncNetFrontendCandidate(warp_dtype="float32")
    float16 = frontend.SyncNetFrontendCandidate(warp_dtype="float16")
    assert float32.version != float16.version
    assert "independent" in float32.version
    assert "float32" in float32.version
    assert "float16" in float16.version
    with pytest.raises(frontend.SyncNetFrontendError):
        frontend.SyncNetFrontendCandidate(warp_dtype="auto")


def test_resize_truncates_to_uint8_before_lanczos() -> None:
    cv2 = pytest.importorskip("cv2")
    frontend = _frontend()
    pixels = np.array(
        [[[0.9, 80.9, 200.9], [100.9, 140.9, 160.9]], [[220.9, 20.9, 40.9], [150.9, 90.9, 10.9]]],
        dtype=np.float32,
    )
    expected = cv2.resize(pixels.astype(np.uint8), (256, 256), interpolation=cv2.INTER_LANCZOS4)
    actual = frontend.resize_aligned_to_square(pixels)
    np.testing.assert_array_equal(actual, expected)
    wrong_order = cv2.resize(pixels, (256, 256), interpolation=cv2.INTER_LANCZOS4).astype(np.uint8)
    assert not np.array_equal(actual, wrong_order)
    assert actual.dtype == np.uint8


def test_packing_preserves_rgb_and_frame_major_order_and_discards_upper_half() -> None:
    frontend = _frontend()
    frames = np.zeros((16, 256, 256, 3), dtype=np.uint8)
    frames[:, :128] = 255
    frames[0, 128:] = [0, 64, 128]
    frames[1, 128:] = [255, 127, 32]
    frames[15, 128:] = [25, 50, 75]
    tensor = frontend.pack_syncnet_frames(frames)
    assert tensor.shape == (1, 48, 128, 256)
    assert tensor.dtype == np.float32
    assert tensor.flags.c_contiguous
    np.testing.assert_allclose(
        tensor[0, :6, 0, 0],
        [-1, -0.49803922, 0.003921569, 1, -0.003921569, -0.74901961],
        atol=1e-7,
    )
    np.testing.assert_allclose(tensor[0, -3:, -1, -1], [-0.80392157, -0.60784314, -0.41176471])


@pytest.mark.parametrize(
    "frames",
    [
        np.zeros((15, 256, 256, 3), dtype=np.uint8),
        np.zeros((16, 128, 256, 3), dtype=np.uint8),
        np.zeros((16, 256, 256, 3), dtype=np.float32),
    ],
)
def test_packing_rejects_incomplete_or_nonbyte_windows(frames: np.ndarray) -> None:
    frontend = _frontend()
    with pytest.raises(frontend.SyncNetFrontendError):
        frontend.pack_syncnet_frames(frames)


def _colored_ramp() -> np.ndarray:
    rows, columns = np.indices((4, 5))
    return np.stack(
        (10 + 20 * columns, 30 + 10 * rows, 150 + 2 * columns + 3 * rows), axis=2
    ).astype(np.uint8)


@pytest.fixture
def kornia_runtime():
    # Optional licensed primitive, no weights/network/GPU are required.
    torch = pytest.importorskip("torch")
    pytest.importorskip("kornia")
    return torch


def test_warp_identity_preserves_rgb_channel_order(kornia_runtime) -> None:
    frontend = _frontend()
    pixels = _colored_ramp()
    actual = frontend.warp_rgb_kornia(
        pixels, np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32), size_wh=(5, 4)
    )
    assert actual.dtype == np.float32
    np.testing.assert_allclose(actual, pixels, atol=3e-5)


def test_warp_uses_forward_translation_and_constant_127_border(kornia_runtime) -> None:
    frontend = _frontend()
    pixels = _colored_ramp()
    actual = frontend.warp_rgb_kornia(
        pixels, np.array([[1, 0, 1], [0, 1, 0]], dtype=np.float32), size_wh=(5, 4)
    )
    np.testing.assert_allclose(actual[:, 0], 127, atol=3e-5)
    np.testing.assert_allclose(actual[:, 1:], pixels[:, :-1], atol=3e-5)


def test_warp_fractional_border_blends_rgb_with_127(kornia_runtime) -> None:
    frontend = _frontend()
    actual = frontend.warp_rgb_kornia(
        _colored_ramp(), np.array([[1, 0, 0.5], [0, 1, 0.25]], dtype=np.float32), size_wh=(5, 4)
    )
    # Destination (0,0) samples (-0.5,-0.25): source support=0.5*0.75.
    np.testing.assert_allclose(actual[0, 0], [83.125, 90.625, 135.625], atol=5e-5)
    # Destination (2,2) samples (1.5,1.75), inside a colored linear ramp.
    np.testing.assert_allclose(actual[2, 2], [40, 47.5, 158.25], atol=5e-5)


def test_warp_fully_outside_pixels_are_127(kornia_runtime) -> None:
    frontend = _frontend()
    actual = frontend.warp_rgb_kornia(
        _colored_ramp(), np.array([[1, 0, 10], [0, 1, 10]], dtype=np.float32), size_wh=(5, 4)
    )
    np.testing.assert_allclose(actual, 127, atol=1e-5)


@pytest.mark.parametrize("offset", [0.01, 0.1, 0.5])
def test_fractional_warp_of_saturated_rgb_can_be_resized(kornia_runtime, offset) -> None:
    frontend = _frontend()
    pixels = np.full((8, 9, 3), [0, 127, 255], dtype=np.uint8)
    warped = frontend.warp_rgb_kornia(
        pixels,
        np.array([[1, 0, offset], [0, 1, offset]], dtype=np.float32),
        size_wh=(9, 8),
    )
    resized = frontend.resize_aligned_to_square(warped)
    assert resized.shape == (256, 256, 3)
    assert resized.dtype == np.uint8
    np.testing.assert_allclose(resized[128, 128], [0, 127, 255], atol=1)


def test_candidate_aligns_at_intermediate_aspect_then_returns_rgb_square(kornia_runtime) -> None:
    frontend = _frontend()
    candidate = frontend.SyncNetFrontendCandidate()
    pixels = np.full((128, 192, 3), [20, 80, 200], dtype=np.uint8)
    landmarks = _landmarks(np.array([[48, 56], [162, 56], [105, 112]]))
    result = candidate.align_frame(pixels, landmarks, frame_index=0)
    assert result.shape == (256, 256, 3)
    assert result.dtype == np.uint8
    # Interior pixels retain order across warp/truncate/resize, allowing truncation.
    np.testing.assert_allclose(result[64, 64], [20, 80, 200], atol=1)
    with pytest.raises(frontend.SyncNetFrontendError):
        candidate.align_frame(pixels, landmarks, frame_index=0)


def test_float16_warp_has_no_implicit_float32_fallback(kornia_runtime, monkeypatch) -> None:
    frontend = _frontend()
    from kornia.geometry import transform

    observed = []

    def unavailable_half_kernel(image, matrix, *args, **kwargs):
        observed.append((image.dtype, matrix.dtype))
        raise NotImplementedError("Synthetic backend without half precision")

    monkeypatch.setattr(transform, "warp_affine", unavailable_half_kernel)
    with pytest.raises(frontend.SyncNetFrontendError, match="float16"):
        frontend.warp_rgb_kornia(
            _colored_ramp(),
            np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32),
            size_wh=(5, 4),
            warp_dtype="float16",
        )
    assert observed == [(kornia_runtime.float16, kornia_runtime.float16)]


def test_failed_warp_does_not_advance_video_state(kornia_runtime, monkeypatch) -> None:
    frontend = _frontend()
    from kornia.geometry import transform

    candidate = frontend.SyncNetFrontendCandidate()
    landmarks = _landmarks(np.array([[0, 0], [10, 0], [5, 10]]))

    def unavailable_kernel(*args, **kwargs):
        raise RuntimeError("Synthetic kernel failure")

    with monkeypatch.context() as context:
        context.setattr(transform, "warp_affine", unavailable_kernel)
        with pytest.raises(frontend.SyncNetFrontendError):
            candidate.align_frame(_colored_ramp(), landmarks, frame_index=0)
    assert candidate.geometry_for_frame(landmarks, frame_index=0).frame_index == 0


@pytest.mark.parametrize(
    "matrix,size_wh",
    [
        (np.zeros((2, 3)), (5, 4)),
        (np.full((2, 3), np.nan), (5, 4)),
        (np.eye(2, 3), (1, 4)),
        (np.eye(2, 3), (5, 0)),
    ],
)
def test_warp_rejects_invalid_geometry_before_loading_optional_libraries(matrix, size_wh) -> None:
    frontend = _frontend()
    with pytest.raises(frontend.SyncNetFrontendError):
        frontend.warp_rgb_kornia(_colored_ramp(), matrix, size_wh=size_wh)


@pytest.mark.parametrize("pixels", [np.zeros((4, 5, 3)), np.zeros((4, 5), dtype=np.uint8)])
def test_warp_requires_rgb_byte_input(pixels: np.ndarray) -> None:
    frontend = _frontend()
    with pytest.raises(frontend.SyncNetFrontendError):
        frontend.warp_rgb_kornia(pixels, np.eye(2, 3), size_wh=(5, 4))
