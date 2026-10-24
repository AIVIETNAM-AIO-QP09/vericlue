"""Run the trained field detector and optional VietOCR on local test images."""

import argparse
import json
import math
import time
from pathlib import Path

import torch
from card_dataset import FIELDS, sha256
from field_recognition import recognize_field
from PIL import Image, ImageDraw, ImageOps
from recognizer_comparison import compare_readers
from torchvision.transforms.functional import to_tensor
from train_card_detector import build_model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("images", type=Path, nargs="+")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--vietocr-models", type=Path)
    parser.add_argument("--secondary-transformer-models", type=Path)
    parser.add_argument(
        "--recognizer-architecture", choices=["seq2seq", "transformer"], default="seq2seq"
    )
    args = parser.parse_args()
    torch.set_num_threads(2)
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if checkpoint["config"]["fields"] != FIELDS:
        raise ValueError("Checkpoint field order differs")
    model = build_model(pretrained=False, image_size=checkpoint["config"]["image_size"])
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval()
    reader = None
    secondary = None
    if args.secondary_transformer_models and (
        not args.vietocr_models or args.recognizer_architecture != "seq2seq"
    ):
        parser.error("Secondary comparison requires primary seq2seq --vietocr-models")
    if args.vietocr_models:
        from vietocr.tool.config import Cfg
        from vietocr.tool.predictor import Predictor

        config = Cfg.load_config_from_file(str(args.vietocr_models / "local.yml"))
        config["device"] = "cpu"
        config["weights"] = str(args.vietocr_models / f"vgg_{args.recognizer_architecture}.pth")
        config["cnn"]["pretrained"] = False
        reader = Predictor(config)
        if args.secondary_transformer_models:
            secondary_config = Cfg.load_config_from_file(
                str(args.secondary_transformer_models / "local.yml")
            )
            secondary_config["weights"] = str(
                args.secondary_transformer_models / "vgg_transformer.pth"
            )
            secondary_config["device"] = "cpu"
            secondary_config["cnn"]["pretrained"] = False
            secondary = Predictor(secondary_config)
    digest = sha256(args.checkpoint)
    for path in args.images:
        destination = args.out / path.stem
        if destination.exists() and any(destination.iterdir()):
            raise ValueError(f"Output not empty; choose a new --out: {destination}")
        destination.mkdir(parents=True, exist_ok=True)
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        overlay = image.copy()
        draw = ImageDraw.Draw(overlay)
        started = time.perf_counter()
        with torch.inference_mode():
            pred = model([to_tensor(image)])[0]
        detections = []
        for box, label, score in zip(pred["boxes"], pred["labels"], pred["scores"], strict=True):
            if float(score) < 0.5:
                continue
            field = FIELDS[int(label) - 1]
            x1, y1, x2, y2 = box.tolist()
            bounds = (
                max(0, math.floor(x1)),
                max(0, math.floor(y1)),
                min(image.width, math.ceil(x2)),
                min(image.height, math.ceil(y2)),
            )
            if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                continue
            crop = image.crop(bounds)
            filename = f"{len(detections):02d}_{field}.png"
            crop.save(destination / filename)
            entry = {
                "field": field,
                "box": list(bounds),
                "detector_score": float(score),
                "crop": filename,
            }
            if reader:
                entry.update(
                    recognize_field(
                        image, bounds, field, reader, destination, f"{len(detections):02d}_{field}"
                    )
                )
            detections.append(entry)
            if secondary:
                secondary_text, secondary_score = secondary.predict(crop, return_prob=True)
                entry["comparison"] = compare_readers(
                    field, entry, str(secondary_text), secondary_score
                )
            draw.rectangle(bounds, outline="red", width=3)
            draw.text(
                (bounds[0], max(0, bounds[1] - 13)), f"{field} {float(score):.2f}", fill="red"
            )
        overlay.save(destination / "overlay.jpg")
        result = {
            "recognizer": args.recognizer_architecture if reader else None,
            "recognizer_sha256": sha256(config["weights"]) if reader else None,
            "secondary_recognizer_sha256": sha256(secondary_config["weights"])
            if secondary
            else None,
            "schema_version": "field-detector-lab/v2",
            "document_status": "review" if detections else "retry",
            "checkpoint_sha256": digest,
            "epoch": checkpoint["epoch"] + 1,
            "image": path.name,
            "coordinate_space": "exif_corrected_input_pixels",
            "elapsed_seconds": round(time.perf_counter() - started, 2),
            "detections": detections,
            "identity_verified": False,
            "missing_fields": sorted(set(FIELDS) - {d["field"] for d in detections}),
            "note": "Experimental field crops; uncalibrated scores, no authenticity check. Duplicate predictions retained for review.",
        }
        (destination / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"{path.name}: {len(detections)} boxes; missing={result['missing_fields']}; {destination}",
            flush=True,
        )


if __name__ == "__main__":
    main()
