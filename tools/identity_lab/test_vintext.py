import numpy as np
import pytest
import torch
from train_vintext import collate, distance
from vintext_recognition import annotation, discover, rectify


def test_original_vintext_numeric_label_mapping(tmp_path):
    for number, split in enumerate(["train_images", "test_image", "unseen_test_images"], 1):
        folder = tmp_path / split
        folder.mkdir()
        (folder / f"im{number:04}.jpg").touch()
        (tmp_path / f"gt_{number}.txt").write_text("example", encoding="utf-8")
    images, labels = discover(tmp_path)
    assert len(images) == len(labels) == 3
    assert labels["im0001"].name == "gt_1.txt"
    (tmp_path / "gt_im0001.txt").touch()
    with pytest.raises(ValueError, match="Ambiguous annotation"):
        discover(tmp_path)
    (tmp_path / "gt_im0001.txt").unlink()
    (tmp_path / "gt_1.txt").unlink()
    with pytest.raises(ValueError, match="missing_label_examples"):
        discover(tmp_path)


def test_annotation_preserves_commas_and_accents():
    points, text = annotation("0,0,99,0,99,31,0,31,LÊ, QUANG")
    assert text == "LÊ, QUANG"
    crop = rectify(np.full((32, 100, 3), 255, dtype=np.uint8), points)
    assert crop.shape == (31, 99, 3)
    with pytest.raises(ValueError):
        annotation("wrong format")
    with pytest.raises(ValueError):
        rectify(np.zeros((32, 100, 3), dtype=np.uint8), points + 1000)


def test_mixed_original_and_recognition_crops(tmp_path):
    for number, split in enumerate(["train_images", "test_image", "unseen_test_images"], 1):
        folder = tmp_path / "original" / split
        folder.mkdir(parents=True)
        (folder / f"im{number:04}.jpg").touch()
        (tmp_path / f"gt_{number}.txt").touch()
    crops = tmp_path / "text_recognition_data" / "test_images"
    crops.mkdir(parents=True)
    (crops / "im0001_1.jpg").touch()
    (crops / "im0001_10.jpg").touch()
    images, labels = discover(tmp_path)
    assert set(images) == set(labels) == {"im0001", "im0002", "im0003"}
    (tmp_path / "original" / "unseen_test_images" / "im0003.jpg").unlink()
    with pytest.raises(ValueError, match="official_split_counts"):
        discover(tmp_path)


def test_collate_teacher_forcing_and_cer():
    images, inputs, targets = collate(
        [(torch.ones(3, 32, 40), [1, 4, 2]), (torch.ones(3, 32, 60), [1, 5, 6, 2])]
    )
    assert images.shape == (2, 3, 32, 60)
    assert inputs[:, 0].tolist() == [1, 4, 0]
    assert targets[0].tolist() == [4, 2, 0]
    assert distance("LỄ", "LÊ") == 1


def test_kaggle_val_partition_keeps_its_name(tmp_path):
    for number, split in enumerate(["train_images", "test_image", "val_image"], 1):
        folder = tmp_path / "vintext" / "vintext" / split
        folder.mkdir(parents=True)
        (folder / f"im{number:04}.jpg").touch()
        (tmp_path / f"gt_{number}.txt").touch()
    crops = tmp_path / "text_recognition_data" / "text_recognition_data" / "val_images"
    crops.mkdir(parents=True)
    (crops / "im0003_0.jpg").touch()
    images, labels = discover(tmp_path)
    assert len(images) == len(labels) == 3
    assert images["im0003"][1] == "dataset_val"
    assert {split for _, split in images.values()} == {"train", "test", "dataset_val"}
