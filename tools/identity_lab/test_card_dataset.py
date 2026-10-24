import csv

import pytest
from card_dataset import grouped_split, parse_labels


def test_mixed_boxes_polygons():
    boxes = parse_labels("0 .5 .5 .4 .2\n0 .1 .2 .4 .2 .4 .6 .1 .6", ["name"], 100, 200)
    assert boxes[0]["xyxy"] == pytest.approx([30, 80, 70, 120])
    assert boxes[1]["xyxy"] == pytest.approx([10, 40, 40, 120])
    assert boxes[1]["polygon"] is not None


@pytest.mark.parametrize(
    "text",
    [
        "0 nan .5 .1 .1",
        "1 .5 .5 .1 .1",
        "0 .1 .1 .8 .8",
        "0 .1 .1 -.1 .1",
        "0 .1 .2 .3",
        "0 -.1 .2 .3 .4 .5 .6",
    ],
)
def test_reject_bad_labels(text):
    with pytest.raises(ValueError):
        parse_labels(text, ["name"], 100, 100)


def test_identity_split_and_duplicate_guard(tmp_path):
    rows = [{"image": f"{i}.jpg", "pixel_sha256": str(i)} for i in range(20)]
    path = tmp_path / "groups.csv"
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["image", "group_id"])
        writer.writeheader()
        writer.writerows({"image": r["image"], "group_id": str(i // 2)} for i, r in enumerate(rows))
    result = grouped_split(rows, path)
    assert {r["split"] for r in result} == {"train", "valid", "test"}
    for i in range(0, 20, 2):
        assert result[i]["split"] == result[i + 1]["split"]
    rows[2]["pixel_sha256"] = rows[0]["pixel_sha256"]
    with pytest.raises(ValueError, match="Identical"):
        grouped_split(rows, path)


def test_missing_identity_is_not_filled_automatically(tmp_path):
    path = tmp_path / "groups.csv"
    path.write_text("image,group_id\na.jpg,\n")
    with pytest.raises(ValueError, match="Fill group_id"):
        grouped_split([{"image": "a.jpg"}], path)
