import json

import pytest
from fastapi.testclient import TestClient
from import_ocr_trials import import_trials
from PIL import Image
from review_recognition import create_app


def test_import_preserves_predictions_without_labels(tmp_path):
    source = tmp_path / "source"
    trial = tmp_path / "trial"
    source.mkdir()
    trial.mkdir()
    Image.new("RGB", (100, 100)).save(source / "card.png")
    Image.new("RGB", (40, 20)).save(trial / "crop.png")
    result = trial / "result.json"
    result.write_text(
        json.dumps(
            {
                "image": "card.png",
                "detections": [
                    {"field": "name", "crop": "crop.png", "box": [0, 0, 40, 20], "text": "proposal"}
                ],
            }
        )
    )
    out = tmp_path / "review"
    assert import_trials([result], source, out) == 1
    assert json.loads((out / "reviews.json").read_text()) == {}
    samples = json.loads((out / "samples.json").read_text())
    client = TestClient(create_app(out))
    assert client.get("/samples?split=train").status_code == 200
    assert client.get("/crop/" + samples[0]["uid"]).status_code == 200
    with pytest.raises(ValueError, match="overwrite"):
        import_trials([result], source, out)
    payload = json.loads(result.read_text())
    payload["detections"][0]["crop"] = "../source/card.png"
    result.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="crop path"):
        import_trials([result], source, tmp_path / "bad")
