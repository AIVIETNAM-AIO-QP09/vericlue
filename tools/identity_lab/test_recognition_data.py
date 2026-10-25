import json

import pytest
from fastapi.testclient import TestClient
from recognition_data import edit_distance, evaluate_records, export_reviewed, write_json
from review_recognition import create_app


def test_cer_counts_missing_predictions_and_preserves_accents():
    rows = [
        {"uid": "a", "split": "valid", "field": "name", "crop_sha256": "a"},
        {"uid": "b", "split": "valid", "field": "id", "crop_sha256": "b"},
    ]
    reviews = {
        "a": {"reviewed": True, "usable": True, "text": "Hòa"},
        "b": {"reviewed": True, "usable": True, "text": "123"},
    }
    predictions = {"a": {"text": "Hoa", "crop_sha256": "a"}}
    score = evaluate_records(rows, reviews, predictions, "valid")["overall"]
    assert score["samples"] == 2 and score["missing_predictions"] == 1
    assert score["cer"] == pytest.approx(4 / 6)
    assert score["exact_match"] == 0
    assert edit_distance("abc", "abc") == 0


def test_unreviewed_proposals_cannot_be_ground_truth():
    with pytest.raises(ValueError, match="No human-reviewed"):
        evaluate_records(
            [{"uid": "a", "split": "valid"}],
            {"a": {"reviewed": False, "usable": True, "text": "123"}},
            {},
            "valid",
        )


def test_review_server_requires_explicit_text_and_token(tmp_path):
    write_json(
        tmp_path / "samples.json",
        [{"uid": "a", "split": "train", "field": "name", "crop": "crops/a.png", "image": "a.jpg"}],
    )
    write_json(tmp_path / "reviews.json", {})
    write_json(tmp_path / "dataset_info.json", {"source_root": str(tmp_path)})
    write_json(tmp_path / "predictions_seq2seq.json", {"a": {"text": "WRONG"}})
    with TestClient(create_app(tmp_path)) as client:
        token = client.get("/samples").json()["token"]
        data = {"text": "Correct", "usable": True, "reviewed": True}
        assert client.post("/review/a", json=data).status_code == 403
        headers = {"X-Review-Token": token}
        assert (
            client.post("/review/a", headers=headers, json={**data, "text": ""}).status_code == 422
        )
        assert client.post("/review/a", headers=headers, json=data).status_code == 200
        assert client.get("/sample/a").json()["proposal"]["text"] == "WRONG"
        assert client.get("/sample/a").json()["review"]["text"] == "Correct"
        assert client.get("/crop/unknown").status_code == 404
    assert json.loads((tmp_path / "reviews.json").read_text())["a"]["text"] == "Correct"


def test_export_without_ground_truth_refuses(tmp_path):
    rows = [{"image": f"{i}.jpg", "pixel_sha256": str(i), "uid": str(i)} for i in range(10)]
    write_json(tmp_path / "samples.json", rows)
    write_json(tmp_path / "reviews.json", {})
    groups = tmp_path / "groups.csv"
    groups.write_text("image,group_id\n" + "".join(f"{i}.jpg,g{i}\n" for i in range(10)))
    with pytest.raises(ValueError, match="Need reviewed"):
        export_reviewed(tmp_path, groups, tmp_path / "export")
