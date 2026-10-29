"""Local regression observations; no ground-truth accuracy claim."""

import json
from pathlib import Path

import app as api
from debug_images import save_debug
from fastapi.testclient import TestClient
from identity_lab import IdentityLab, decode_image
from schemas import OCRResult

root = Path(__file__).resolve().parents[2]
lab = IdentityLab()
api.lab = lab
client = TestClient(api.app)
for source in sorted((root / "data/images/test_ocr").glob("*.jfif")):
    data = source.read_bytes()
    result = lab.ocr(data)
    destination = root / "outputs/ocr_debug" / source.stem
    save_debug(decode_image(data), result["lines"], destination, result["fields"])
    (destination / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        source.name, {key: field["status"] for key, field in result["fields"].items()}, flush=True
    )
    assert result["document_status"] == "review"
    assert result["fields"]["id_number"]["value"]
    assert result["fields"]["date_of_birth"]["value"]
    assert result["fields"]["date_of_expiry"]["value"]
    response = client.post("/dev/v1/ocr", files={"image": (source.name, data, "image/jpeg")})
    assert response.status_code == 200, response.text[:100]
    expected = OCRResult(**result).model_dump()["fields"]
    actual = response.json()["fields"]
    (destination / "api_result.json").write_text(response.text, encoding="utf-8")
    # Float confidence can vary slightly across worker threads; check semantic output.
    for key, field in expected.items():
        for attribute in ["value", "status", "candidates", "source_line_ids", "reasons"]:
            assert actual[key][attribute] == field[attribute], (source.name, key, attribute)
    print("API validated", source.name, flush=True)
