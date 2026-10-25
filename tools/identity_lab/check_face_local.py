"""Real-model regression checks using benchmark images; no claim of ID-selfie accuracy."""

import argparse
import json
import os
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient
from serve_face_lab import select_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Choose new output file")
    name, config = select_config(json.loads(args.comparison.read_text(encoding="utf-8")))
    os.environ["FACE_RECOGNIZER"] = config["recognizer"]
    os.environ["FACE_EMBEDDING_MODE"] = config["embedding_mode"]
    import app
    from face_matching import match_pair, pipeline_config
    from identity_lab import decode_image
    from schemas import FacePairResult

    app.lab._load_faces()
    if pipeline_config(app.lab, config["embedding_mode"]) != config:
        raise ValueError("Comparison pipeline does not match current code/models/runtime")
    rows = json.loads((args.comparison.parent / name / "pairs.json").read_text(encoding="utf-8"))
    examples = [
        next(r for r in rows if r["status"] == "ok" and r["same_person"] == label)
        for label in (True, False)
    ]
    results = []
    client = TestClient(app.app)
    for row in examples:
        paths = [(args.dataset / row[key]).resolve() for key in ("reference", "selfie")]
        if any(not p.is_relative_to(args.dataset.resolve()) for p in paths):
            raise ValueError("Dataset path escape")
        reference, selfie = [p.read_bytes() for p in paths]
        plain = match_pair(app.lab, reference, selfie, embedding_mode=config["embedding_mode"])
        FacePairResult.model_validate(plain)
        assert (
            plain["status"] == "ok"
            and abs(plain["cosine_similarity"] - row["cosine_similarity"]) < 1e-6
        )
        image = decode_image(reference)
        h, w = image.shape[:2]
        # A synthetic canvas tests coordinate handling, not card authenticity or card domain performance.
        canvas = np.full((h + 120, w + 160, 3), 240, dtype=np.uint8)
        canvas[60 : 60 + h, 80 : 80 + w] = image
        encoded, png = cv2.imencode(".png", canvas)
        assert encoded
        roi = [80, 60, 80 + w, 60 + h]
        response = client.post(
            "/dev/v2/face-match",
            files={
                "reference": ("canvas.png", png.tobytes(), "image/png"),
                "selfie": ("selfie.jpg", selfie, "image/jpeg"),
            },
            data={"reference_roi": json.dumps(roi)},
        )
        assert response.status_code == 200
        result = response.json()
        FacePairResult.model_validate(result)
        assert result["status"] == "ok" and result["embedding_mode"] == config["embedding_mode"]
        assert abs(result["cosine_similarity"] - plain["cosine_similarity"]) < 1e-6
        np.testing.assert_allclose(
            result["reference"]["bbox"], np.array(plain["reference"]["bbox"]) + [80, 60, 80, 60]
        )
        assert result["identity_verified"] is False and result["threshold"] is None
        results.append(
            {
                "same_person_label": row["same_person"],
                "score": result["cosine_similarity"],
                "roi_and_api_consistent": True,
            }
        )
    response = client.post(
        "/dev/v2/face-match",
        files={"reference": ("r.jpg", reference), "selfie": ("s.jpg", reference)},
    )
    assert response.status_code == 200 and response.json()["reason"] == "E_IDENTICAL_INPUTS"
    report = {
        "selected": name,
        "cases": results,
        "duplicate_rejected": True,
        "scope": "LFW developer regression + synthetic canvas; not CCCD-selfie validation",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
