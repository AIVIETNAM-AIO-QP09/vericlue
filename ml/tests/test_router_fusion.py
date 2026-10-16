"""ROUT-02: learned fusion is fit only on synthetic calib_fit data, on CPU."""

import json
import math

import numpy as np
import pytest

from vericlue_ml.router.fusion import FusionFit, LogisticFusion, fit

COMMIT = "a" * 40


def synthetic_calib_fit(**changes):
    payload = {
        "features": [
            [0.05, 0.10, 0.8],
            [0.10, 0.15, 0.8],
            [0.15, 0.20, 0.8],
            [0.20, 0.25, 0.8],
            [0.75, 0.80, 0.8],
            [0.80, 0.85, 0.8],
            [0.85, 0.90, 0.8],
            [0.90, 0.95, 0.8],
        ],
        "labels": [0, 0, 0, 0, 1, 1, 1, 1],
        "subject_ids": [f"synthetic-person-{i}" for i in range(8)],
        "feature_names": [
            "prob_attack:face_pad",
            "prob_attack:face_deepfake",
            "quality:quality:sharpness",
        ],
        "model_versions": {
            "face_pad": "synthetic-pad@1",
            "face_deepfake": "synthetic-df@1",
            "quality": "synthetic-quality@1",
        },
        "dataset": "synthetic-known-separation",
        "split": "calib_fit",
    }
    payload.update(changes)
    return FusionFit(**payload)


def test_synthetic_fit_returns_attack_probability_in_correct_direction():
    data = synthetic_calib_fit()
    model = fit(data, commit=COMMIT)
    probabilities = model.predict(data.features)
    assert isinstance(probabilities, np.ndarray)
    assert probabilities.shape == (8,)
    assert np.isfinite(probabilities).all()
    assert ((probabilities >= 0) & (probabilities <= 1)).all()
    assert max(probabilities[:4]) < min(probabilities[4:])
    assert np.mean(probabilities[:4]) < 0.5 < np.mean(probabilities[4:])


def test_json_roundtrip_preserves_probability_and_contains_no_pickle(tmp_path):
    data = synthetic_calib_fit()
    model = fit(data, commit=COMMIT)
    path = tmp_path / "synthetic-fusion.json"
    model.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    loaded = LogisticFusion.load(path)
    np.testing.assert_allclose(
        loaded.predict(data.features), model.predict(data.features), rtol=1e-12
    )
    # Artifacts remain local to pytest's temporary directory, never ml/configs/.
    assert path.parent == tmp_path


@pytest.mark.parametrize("split", ["calib_ltt", "test", "train", "calib", ""])
def test_only_calib_fit_is_accepted_for_learning(split):
    with pytest.raises(ValueError):
        fit(synthetic_calib_fit(split=split), commit=COMMIT)


@pytest.mark.parametrize(
    "changes",
    [
        {"features": []},
        {"features": [[0.1, 0.2, 0.3], [0.2, 0.3]]},
        {"features": [[0.1, 0.2, 0.3]] * 7},
        {"features": [[0.1, 0.2]] * 8},
        {"features": [[0.1, math.nan, 0.3]] * 8},
        {"features": [[0.1, math.inf, 0.3]] * 8},
        {"labels": [0] * 8},
        {"labels": [1] * 8},
        {"labels": [0, 1]},
        {"labels": [0, 0, 0, 0, 1, 1, 1, 2]},
        {"subject_ids": ["only-one-row"]},
        {"feature_names": ["prob_attack:face_pad"]},
    ],
)
def test_invalid_training_vectors_fail_without_learning(changes):
    with pytest.raises(ValueError):
        fit(synthetic_calib_fit(**changes), commit=COMMIT)


@pytest.mark.parametrize(
    "feature_name",
    [
        "score:face_pad",
        "raw_score:face_pad",
        "face_pad_score",
        "prob_attack:voice_challenge",
        "quality:voice_challenge:syllable_error_rate",
        "voice_challenge",
        "syllable_error_rate",
    ],
)
def test_raw_scores_and_voice_content_are_not_fusion_features(feature_name):
    with pytest.raises(ValueError):
        fit(
            synthetic_calib_fit(
                feature_names=[
                    feature_name,
                    "prob_attack:face_deepfake",
                    "quality:quality:sharpness",
                ]
            ),
            commit=COMMIT,
        )


@pytest.mark.parametrize(
    "features",
    [
        [[0.1, 0.2]],
        [[0.1, 0.2, 0.3, 0.4]],
        [[0.1, math.nan, 0.3]],
        [[0.1, math.inf, 0.3]],
        [[0.1, 0.2, 0.3], [0.1, 0.2]],
        [0.1, 0.2, 0.3],
    ],
)
def test_predict_rejects_wrong_dimensions_and_nonfinite_features(features):
    model = fit(synthetic_calib_fit(), commit=COMMIT)
    with pytest.raises(ValueError):
        model.predict(features)


@pytest.mark.parametrize(
    "versions",
    [
        {},
        {"face_pad": "synthetic-pad@1"},
        {"face_pad": "synthetic-pad@1", "face_deepfake": "", "quality": "quality@1"},
        {"face_pad": "synthetic-pad@1", "face_deepfake": "df@1", "quality": "   "},
    ],
)
def test_training_provenance_covers_all_feature_modules_with_nonempty_versions(versions):
    with pytest.raises(ValueError):
        fit(synthetic_calib_fit(model_versions=versions), commit=COMMIT)


@pytest.mark.parametrize(
    "changes",
    [
        {
            "feature_names": [
                "score:face_pad",
                "prob_attack:face_deepfake",
                "quality:quality:sharpness",
            ]
        },
        {
            "feature_names": [
                "prob_attack:voice_challenge",
                "prob_attack:face_deepfake",
                "quality:quality:sharpness",
            ]
        },
        {
            "feature_names": [
                "prob_attack:face_pad",
                "prob_attack:face_deepfake",
                "quality:voice_challenge:syllable_error_rate",
            ]
        },
        {
            "feature_names": [
                "prob_attack:face_pad",
                "prob_attack:face_pad",
                "quality:quality:sharpness",
            ]
        },
        {"model_versions": {}},
        {"model_versions": {"face_pad": "pad@1"}},
        {"model_versions": {"face_pad": "pad@1", "face_deepfake": "", "quality": "quality@1"}},
        {"dataset": "   "},
        {"commit": "   "},
        {"n_pos": 0},
        {"n_neg": 0},
        {"split": "test"},
    ],
)
def test_loading_rejects_invalid_feature_semantics_and_provenance(tmp_path, changes):
    artifact = fit(synthetic_calib_fit(), commit=COMMIT).model_dump(mode="json")
    artifact.update(changes)
    path = tmp_path / "invalid-synthetic-fusion.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(ValueError):
        LogisticFusion.load(path)


@pytest.mark.parametrize("probability", [-0.01, 1.01])
@pytest.mark.parametrize("column", [0, 1])
def test_predict_rejects_out_of_range_attack_probabilities(probability, column):
    model = fit(synthetic_calib_fit(), commit=COMMIT)
    values = [[0.5, 0.5, 0.8]]
    values[0][column] = probability
    with pytest.raises(ValueError):
        model.predict(values)


def test_quality_feature_keeps_its_own_scale_instead_of_probability_range():
    data = synthetic_calib_fit(features=[[0.1, 0.2, 100.0]] * 4 + [[0.8, 0.9, 100.0]] * 4)
    model = fit(data, commit=COMMIT)
    assert np.isfinite(model.predict([[0.5, 0.5, 100.0]])).all()
