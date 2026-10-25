from train_card_detector import checkpoint_config_diff


def test_legacy_grouping_metadata_with_same_manifest():
    old = {"manifest_sha256": "same", "smoke": True, "batch_size": 2}
    new = {**old, "grouping": "provided_groups"}
    assert checkpoint_config_diff(old, new) == {}
    assert "grouping" not in old


def test_legacy_migration_does_not_bypass_training_changes():
    old = {"manifest_sha256": "same", "smoke": True, "batch_size": 2}
    new = {**old, "grouping": "provided_groups", "smoke": False}
    assert "smoke" in checkpoint_config_diff(old, new)
    new["manifest_sha256"] = "changed"
    assert "manifest_sha256" in checkpoint_config_diff(old, new)
    assert "grouping" in checkpoint_config_diff(old, new)


def test_explicit_grouping_change_is_rejected():
    old = {"manifest_sha256": "same", "grouping": "provided_groups"}
    assert "grouping" in checkpoint_config_diff(old, {**old, "grouping": "provisional_ocr"})
