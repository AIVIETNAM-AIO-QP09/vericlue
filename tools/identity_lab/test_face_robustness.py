import numpy as np
import pytest
from face_robustness import SCENARIOS, choose, stress


def test_stress_is_role_specific_deterministic_and_does_not_mutate():
    image = np.random.default_rng(42).integers(0, 256, (112, 112, 3), dtype=np.uint8)
    original = image.copy()
    for scenario in SCENARIOS:
        for role in ["reference", "selfie"]:
            a = stress(image, role, scenario)
            np.testing.assert_array_equal(a, stress(image, role, scenario))
            assert a.shape == image.shape and a.dtype == np.uint8
    np.testing.assert_array_equal(original, image)
    np.testing.assert_array_equal(stress(image, "selfie", "document_lowres"), image)
    np.testing.assert_array_equal(stress(image, "reference", "selfie_shadow"), image)
    assert stress(image, "selfie", "selfie_shadow").mean() < image.mean()
    with pytest.raises(ValueError):
        stress(image, "selfie", "unknown")


def report(error, latency):
    return {
        "embedding_ms_median": latency,
        "scenarios": {
            s: {"validation_operating_point": {"fmr_scored": error, "fnmr_scored": error}}
            for s in SCENARIOS
        },
    }


def test_selection_prefers_fast_when_close_but_accuracy_when_material():
    reports = {"fast": report(0.02, 50), "slow": report(0.015, 300)}
    assert choose(reports)[0] == "fast"
    reports["fast"] = report(0.08, 50)
    assert choose(reports)[0] == "slow"
    reports["fast"]["scenarios"]["clean"]["validation_operating_point"]["fmr_scored"] = None
    with pytest.raises(ValueError):
        choose(reports)
