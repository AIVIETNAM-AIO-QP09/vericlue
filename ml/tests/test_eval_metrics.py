"""EVAL-01: metric answers from small synthetic samples, without model weights."""

import math

import pytest

from vericlue_ml.common import calibration
from vericlue_ml.eval import metrics


def test_calibration_metrics_are_shared_imports():
    assert metrics.ece is calibration.ece
    assert metrics.brier_score is calibration.brier_score


def test_attack_rates_per_type_and_boundary():
    labels = [0, 0, 1, 1, 1, 1]
    probabilities = [0.2, 0.5, 0.3, 0.5, 0.4, 0.9]
    attack_types = ["genuine", "genuine", "print", "print", "replay", "replay"]
    assert metrics.apcer_by_attack(labels, probabilities, attack_types, 0.5) == {
        "print": 0.5,
        "replay": 0.5,
    }
    assert metrics.bpcer(labels, probabilities, 0.5) == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("probabilities", "expected_apcer", "expected_bpcer", "expected_auc", "expected_eer"),
    [
        ([0.1, 0.2, 0.8, 0.9], 0.0, 0.0, 1.0, 0.0),
        ([0.9, 0.8, 0.2, 0.1], 1.0, 1.0, 0.0, 1.0),
        ([0.5, 0.5, 0.5, 0.5], 0.0, 1.0, 0.5, 0.5),
        ([0.1, 0.9, 0.2, 0.8], 0.5, 0.5, 0.5, 0.5),
    ],
)
def test_known_binary_answers(
    probabilities, expected_apcer, expected_bpcer, expected_auc, expected_eer
):
    labels = [0, 0, 1, 1]
    assert metrics.apcer_by_attack(labels, probabilities, ["", "", "print", "print"], 0.5) == {
        "print": expected_apcer
    }
    assert metrics.bpcer(labels, probabilities, 0.5) == expected_bpcer
    assert metrics.auc(labels, probabilities) == pytest.approx(expected_auc)
    assert metrics.eer(labels, probabilities) == pytest.approx(expected_eer)


def test_eer_known_one_third():
    assert metrics.eer([0, 0, 0, 1, 1, 1], [0.1, 0.5, 0.9, 0.4, 0.6, 0.8]) == pytest.approx(1 / 3)


@pytest.mark.parametrize(
    ("probabilities", "expected"),
    [([0.1, 0.2, 0.8, 0.9], 0.0), ([0.5] * 4, 0.95), ([0.9, 0.8, 0.2, 0.1], 1.0)],
)
def test_descriptive_operating_point_is_only_scalar(probabilities, expected):
    answer = metrics.descriptive_bpcer_at_apcer([0, 0, 1, 1], probabilities)
    assert isinstance(answer, float)
    assert answer == pytest.approx(expected)


@pytest.mark.parametrize("labels", [[0, 0], [1, 1]])
def test_missing_classes_are_undefined(labels):
    probabilities = [0.5] * len(labels)
    assert metrics.auc(labels, probabilities) is None
    assert metrics.eer(labels, probabilities) is None
    assert metrics.descriptive_bpcer_at_apcer(labels, probabilities) is None
    if 0 not in labels:
        assert metrics.bpcer(labels, probabilities, 0.5) is None
    if 1 not in labels:
        assert metrics.apcer_by_attack(labels, probabilities, ["print"] * len(labels), 0.5) == {}


def test_clopper_pearson_extremes_have_known_closed_form():
    total = 10
    upper = 1 - 0.025 ** (1 / total)
    assert metrics.clopper_pearson(0, total) == pytest.approx((0.0, upper))
    assert metrics.clopper_pearson(total, total) == pytest.approx((1 - upper, 1.0))
    assert metrics.clopper_pearson(0, 0) is None


def test_clopper_pearson_balanced_known_interval():
    assert metrics.clopper_pearson(5, 10) == pytest.approx(
        (0.18708602844739852, 0.8129139715526015)
    )


@pytest.mark.parametrize(
    ("labels", "probabilities"),
    [
        ([], []),
        ([0, 1], [0.1]),
        ([0, 2], [0.1, 0.9]),
        ([0, -1], [0.1, 0.9]),
        ([0, 0.5], [0.1, 0.9]),
        ([0, math.nan], [0.1, 0.9]),
        ([0, 1], [-0.01, 0.9]),
        ([0, 1], [0.1, 1.01]),
        ([0, 1], [math.nan, 0.9]),
        ([0, 1], [math.inf, 0.9]),
    ],
)
def test_invalid_metric_vectors_raise(labels, probabilities):
    for function in (metrics.auc, metrics.eer, metrics.descriptive_bpcer_at_apcer):
        with pytest.raises(ValueError):
            function(labels, probabilities)
    with pytest.raises(ValueError):
        metrics.bpcer(labels, probabilities, 0.5)
    with pytest.raises(ValueError):
        metrics.apcer_by_attack(labels, probabilities, ["print"] * len(labels), 0.5)


def test_attack_type_length_must_match():
    with pytest.raises(ValueError):
        metrics.apcer_by_attack([0, 1], [0.1, 0.9], ["print"], 0.5)


@pytest.mark.parametrize("threshold", [math.nan, math.inf, -0.1, 1.1])
def test_invalid_thresholds_raise(threshold):
    with pytest.raises(ValueError):
        metrics.bpcer([0, 1], [0.1, 0.9], threshold)
    with pytest.raises(ValueError):
        metrics.apcer_by_attack([0, 1], [0.1, 0.9], ["", "print"], threshold)


@pytest.mark.parametrize("target", [-0.01, 1.01, math.nan, math.inf])
def test_invalid_descriptive_targets_raise(target):
    with pytest.raises(ValueError):
        metrics.descriptive_bpcer_at_apcer([0, 1], [0.1, 0.9], target=target)


@pytest.mark.parametrize(
    ("successes", "total", "confidence"),
    [
        (-1, 10, 0.95),
        (11, 10, 0.95),
        (0, -1, 0.95),
        (0.5, 10, 0.95),
        (1, 10.5, 0.95),
        (1, 10, 0),
        (1, 10, 1),
        (1, 10, math.nan),
    ],
)
def test_invalid_clopper_pearson_inputs_raise(successes, total, confidence):
    with pytest.raises(ValueError):
        metrics.clopper_pearson(successes, total, confidence=confidence)


def test_descriptive_roc_interpolation_preserves_horizontal_segments():
    # To catch 95% attacks, the .5 genuine sample must be rejected along with .9.
    assert metrics.descriptive_bpcer_at_apcer(
        [0, 0, 0, 1, 1, 1], [0.1, 0.5, 0.9, 0.4, 0.6, 0.8]
    ) == pytest.approx(2 / 3)


def test_partial_tie_requires_interpolated_eer_and_descriptive_rate():
    labels, probabilities = [0, 0, 1, 1], [0.1, 0.5, 0.5, 0.9]
    assert metrics.auc(labels, probabilities) == pytest.approx(0.875)
    assert metrics.eer(labels, probabilities) == pytest.approx(0.25)
    assert metrics.descriptive_bpcer_at_apcer(labels, probabilities) == pytest.approx(0.45)
