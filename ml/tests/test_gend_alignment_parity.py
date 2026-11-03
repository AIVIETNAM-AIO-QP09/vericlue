"""GenD alignment goldens from pinned upstream, without weights or biometric media.

Numeric fixtures obtained by executing detector.py::align_face at
https://github.com/yermandy/GenD/commit/387a42266dd385fbe8f7626c5d3aa03eea3bfaab
(source SHA256 c7cbdf2dc37ffd5612f3a6b5583027e8eaa42e5eb261eae447bf92b1919eb7b7).
NumPy 2.5.4, OpenCV 4.14.0; synthetic five-point geometry only.
Source MIT, Copyright (c) 2025 Andy; third_party/licenses/GenD-MIT.txt.
These literal destinations are independent of wrapper alignment arithmetic.
"""

from __future__ import annotations

import numpy as np
import pytest

from vericlue_ml.face import gend

cv2 = pytest.importorskip("cv2")

# name, source landmarks, upstream destination landmarks, output side
CASES = [
    (
        "front",
        [[140.0, 150.0], [230.0, 150.0], [185.0, 190.0], [155.0, 230.0], [215.0, 230.0]],
        [
            [116.84614562988281, 145.4615478515625],
            [193.1538543701172, 145.4615478515625],
            [155.0, 188.38461303710938],
            [124.00000762939453, 231.30770874023438],
            [186.0, 231.30770874023438],
        ],
        310,
    ),
    (
        "rotated",
        [
            [183.66114807128906, 148.59107971191406],
            [269.72857666015625, 174.904541015625],
            [215.0, 200.0],
            [174.61599731445312, 229.4810333251953],
            [231.99427795410156, 247.02334594726562],
        ],
        [
            [116.84614562988281, 145.4615478515625],
            [193.1538543701172, 145.4615478515625],
            [155.0, 188.38461303710938],
            [124.00000762939453, 231.30770874023438],
            [186.0, 231.30770874023438],
        ],
        310,
    ),
    (
        "small",
        [
            [140.76881408691406, 218.45762634277344],
            [190.47608947753906, 197.35813903808594],
            [175.0, 230.0],
            [167.80845642089844, 259.1252746582031],
            [200.94664001464844, 245.0589599609375],
        ],
        [
            [70.1076889038086, 87.27693176269531],
            [115.8923110961914, 87.27693176269531],
            [93.0, 113.03076934814453],
            [74.4000015258789, 138.78460693359375],
            [111.5999984741211, 138.78460693359375],
        ],
        186,
    ),
    (
        "large",
        [
            [264.1925964355469, 81.404541015625],
            [359.2860107421875, 164.06797790527344],
            [275.0, 165.0],
            [206.56289672851562, 179.70925903320312],
            [269.95849609375, 234.81822204589844],
        ],
        [
            [163.9615478515625, 204.11538696289062],
            [271.0384521484375, 204.11538696289062],
            [217.5, 264.3461608886719],
            [174.0, 324.576904296875],
            [261.0, 324.576904296875],
        ],
        435,
    ),
    (
        "border",
        [
            [34.4729118347168, 42.99693298339844],
            [53.18898010253906, 40.36656188964844],
            [45.0, 50.0],
            [39.93036651611328, 59.19504165649414],
            [52.40774154663086, 57.44145965576172],
        ],
        [
            [24.5, 30.500001907348633],
            [40.5, 30.500001907348633],
            [32.5, 39.5],
            [26.000001907348633, 48.5],
            [39.0, 48.5],
        ],
        65,
    ),
    (
        "outside",
        [
            [399.3102111816406, 205.39939880371094],
            [579.0635375976562, 214.8198699951172],
            [485.0, 290.0],
            [420.8953552246094, 366.7502136230469],
            [540.7308959960938, 373.030517578125],
        ],
        [
            [234.06924438476562, 291.3923034667969],
            [386.9307861328125, 291.3923034667969],
            [310.5, 377.3769226074219],
            [248.40000915527344, 463.3615417480469],
            [372.6000061035156, 463.3615417480469],
        ],
        621,
    ),
]


@pytest.mark.parametrize(
    ("name", "landmarks", "destination", "side"), CASES, ids=[c[0] for c in CASES]
)
def test_alignment_matches_pinned_upstream_pixels_and_geometry(
    monkeypatch, name, landmarks, destination, side
):
    image = np.random.default_rng(20261103).integers(0, 256, (480, 640, 3), dtype=np.uint8)
    points = np.array(landmarks, dtype=np.float32)
    expected_dst = np.array(destination, dtype=np.float32)
    original = cv2.estimateAffinePartial2D
    expected_matrix = original(points, expected_dst, method=cv2.LMEDS)[0]
    expected = cv2.warpAffine(image, expected_matrix, (side, side), flags=cv2.INTER_LINEAR)
    captured = {}

    def observe(source, target, *args, **kwargs):
        result = original(source, target, *args, **kwargs)
        captured["destination"] = target.copy()
        captured["matrix"] = result[0].copy()
        return result

    monkeypatch.setattr(cv2, "estimateAffinePartial2D", observe)
    actual = gend.align_face(image, points)
    np.testing.assert_array_equal(actual, expected, err_msg=name)
    np.testing.assert_array_equal(captured["destination"], expected_dst)
    np.testing.assert_array_equal(captured["matrix"], expected_matrix)


@pytest.mark.parametrize("injected", [False, True])
def test_new_alignment_does_not_reuse_legacy_calibrator_version(injected):
    detector = gend.FaceDeepfakeDetector(finder=object() if injected else None)
    kind = "injected" if injected else "scrfd-10g"
    legacy = f"gend-clip-l14+{kind}+agg-maxmeantop25-v1"
    assert detector.version != legacy
    assert "+align-upstream-numpy-v2+" in detector.version
    assert detector.frames_version != legacy + "+headturn-3views-v1"


def test_preloaded_alignment_version_cannot_match_legacy_checkpoint_calibrator(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(gend, "shared_scrfd_session", lambda *a: (object(), "bfcc7d48"))
    monkeypatch.setattr(gend, "ScrfdFaceFinder", lambda *a, **k: object())
    monkeypatch.setattr(gend, "_load_classifier", lambda *a: (object(), "891ce014", "32bd6428"))
    detector = gend.FaceDeepfakeDetector(models_dir=tmp_path)
    detector.preload(device="cpu")
    legacy = "gend-clip-l14@891ce014+clip@32bd6428+scrfd-10g@bfcc7d48+agg-maxmeantop25-v1"
    assert detector.version != legacy
    assert "+align-upstream-numpy-v2+" in detector.version
