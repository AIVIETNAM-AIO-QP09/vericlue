import numpy as np
import pytest
import torch
from download_face_sample import classify
from train_face_adapter import adapt, balanced_loss, pair_records, split_people


def test_provider_roles_are_explicit_and_numbered_sample_excluded():
    person, role = classify("African/person/Passport.jpg")
    assert role == "reference"
    assert classify("African/person/Phone_indoor_01.JPG") == (person, "selfie")
    assert classify("Selfie & id data - public sample/1/docs/1.jpeg") is None
    with pytest.raises(ValueError):
        classify("African/person/unknown.jpg")


def test_people_split_is_disjoint_and_order_independent():
    rows = [{"identity": str(i)} for i in range(20)] * 2
    splits = split_people(rows)
    assert splits == split_people(rows[::-1])
    assert list(splits.values()).count("train") == 12
    assert list(splits.values()).count("valid") == 4
    assert list(splits.values()).count("test") == 4


def test_adapter_identity_and_invalid_inputs():
    v = np.array([3.0, 4.0])
    np.testing.assert_allclose(adapt(v, np.ones(2)), [0.6, 0.8])
    assert np.linalg.norm(adapt(v, np.array([2.0, 1.0]))) == pytest.approx(1)
    for weights in [np.array([0.0, 1.0]), np.array([float("nan"), 1.0]), np.ones(3)]:
        with pytest.raises(ValueError):
            adapt(v, weights)


def test_balanced_objective_has_gradients_and_requires_both_labels():
    scores = torch.tensor([0.6, 0.3], requires_grad=True)
    loss = balanced_loss(scores, torch.tensor([True, False]))
    loss.backward()
    assert scores.grad[0] < 0 and scores.grad[1] > 0
    with pytest.raises(ValueError):
        balanced_loss(scores, torch.tensor([True, True]))


def test_pairs_never_cross_partitions_and_keep_retry():
    rows = []
    vectors = {}
    for split in ["train", "valid", "test"]:
        for i in range(2):
            for role in ["reference", "selfie"]:
                name = f"{split}-{i}-{role}"
                rows.append(
                    dict(
                        file=name,
                        identity=f"{split}-{i}",
                        role=role,
                        split=split,
                        status="ok",
                        pixel_sha256=name,
                    )
                )
                vectors[name] = np.array([1.0, 1.0])
    rows[-1].update(status="retry", reason="E_NO_FACE_SELFIE")
    result = pair_records(rows, vectors, np.ones(2), "test")
    assert len(result) == 4
    assert all(
        r["reference"].startswith("test-") and r["selfie"].startswith("test-") for r in result
    )
    assert sum(r["same_person"] for r in result) == 2
    assert sum(r["status"] == "retry" for r in result) == 2
    assert all(r["cosine_similarity"] is None for r in result if r["status"] == "retry")
