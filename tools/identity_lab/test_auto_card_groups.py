from auto_card_groups import accepted_id, resolve


def test_accept_requires_agreement_and_confidence():
    assert accepted_id([("123456789012", 0.95), ("123456789012", 0.9)]) == "123456789012"
    assert accepted_id([("123456789012", 0.95), ("123456789013", 0.9)]) is None
    assert accepted_id([("123456789012", 0.95), ("123456789012", 0.5)]) is None
    assert accepted_id([("123456789O12", 0.95)] * 2) is None
    assert accepted_id([("000000000000", 0.95)] * 2) is None


def test_exact_duplicate_propagation_and_conflict():
    rows = [{"image": str(i), "pixel_sha256": "same"} for i in range(2)]
    good, bad = resolve(rows, {"0": "auto_a", "1": None})
    assert len(good) == 2 and not bad
    assert all(r["person_split_verified"] is False for r in good)
    good, bad = resolve(rows, {"0": "auto_a", "1": "auto_b"})
    assert not good and len(bad) == 2


def test_unreadable_image_is_not_assigned_unique_identity():
    good, bad = resolve([{"image": "x", "pixel_sha256": "x"}], {})
    assert not good and bad[0]["reason"] == "id_unreadable_or_uncertain"
