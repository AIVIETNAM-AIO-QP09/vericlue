"""Real-model plumbing smoke test, NOT a CCCD accuracy benchmark."""

import json
from importlib.metadata import version

import numpy as np
from identity_lab import ROOT, IdentityLab, InputError
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from skimage import data


def main():
    samples = ROOT / "samples"
    results = ROOT / "results"
    samples.mkdir(exist_ok=True)
    results.mkdir(exist_ok=True)
    sheet = Image.new("RGB", (1200, 500), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 38)
    expected = [
        "MẪU THỬ OCR - KHÔNG PHẢI GIẤY TỜ",
        "Họ và tên: NGUYỄN VĂN AN",
        "Ngày sinh: 01/01/2000",
        "Số mẫu: 000000000000",
    ]
    for index, line in enumerate(expected):
        draw.text((35, 35 + index * 100), line, font=font, fill="black")
    sheet.save(samples / "vietnamese_text.png")
    face = Image.fromarray(data.astronaut())
    face.save(samples / "reference.png")
    ImageEnhance.Brightness(face).enhance(0.85).save(samples / "selfie_variant.jpg", quality=85)
    Image.new("RGB", (512, 512), "white").save(samples / "blank.png")
    lab = IdentityLab()
    report = {
        "scope": "Synthetic text and a transformed public sample; NOT independent ID/selfie pairs",
        "versions": {
            p: version(p)
            for p in [
                "paddleocr",
                "paddlepaddle",
                "uniface",
                "onnxruntime",
                "vietocr",
                "torch",
            ]
        },
    }
    print("Running real OCR...", flush=True)
    report["ocr"] = lab.ocr((samples / "vietnamese_text.png").read_bytes())
    report["ocr_expected_lines"] = expected
    print("Running real AdaFace...", flush=True)
    report["face_match"] = lab.match(
        (samples / "reference.png").read_bytes(),
        (samples / "selfie_variant.jpg").read_bytes(),
    )
    try:
        lab.match(
            (samples / "reference.png").read_bytes(),
            (samples / "blank.png").read_bytes(),
        )
        raise AssertionError("Blank image must not produce a match")
    except InputError as exc:
        report["blank_face_error"] = str(exc)
    assert report["ocr"]["lines"], "No OCR output"
    assert any("NGUYỄN VĂN AN" in line["text"] for line in report["ocr"]["lines"])
    assert "000000000000" in report["ocr"]["alternate_candidates"]["id_number_candidates"]
    assert report["ocr"]["document_status"] == "review"
    assert np.isfinite(report["face_match"]["cosine_similarity"])
    assert report["blank_face_error"] == "E_NO_FACE_SELFIE"
    import app as api
    from fastapi.testclient import TestClient

    api.lab = lab
    client = TestClient(api.app)
    response = client.post(
        "/dev/v1/ocr",
        files={
            "image": (
                "sample.png",
                (samples / "vietnamese_text.png").read_bytes(),
                "image/png",
            )
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["lines"]
    response = client.post(
        "/dev/v1/face-match",
        files={
            "reference": (
                "ref.png",
                (samples / "reference.png").read_bytes(),
                "image/png",
            ),
            "selfie": (
                "selfie.jpg",
                (samples / "selfie_variant.jpg").read_bytes(),
                "image/jpeg",
            ),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["decision"] == "not_calibrated"
    report["real_model_api_checks"] = "OCR and face-match multipart requests returned 200"
    (results / "smoke.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Saved results/smoke.json", flush=True)


if __name__ == "__main__":
    main()
