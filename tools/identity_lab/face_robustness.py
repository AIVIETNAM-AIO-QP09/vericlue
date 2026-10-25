"""External-data-only comparison: locked stress recipes, train calibration, validation selection.

No personal photo arguments. Synthetic blur/lighting is NOT an ageing simulation.
"""

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from calibrate_faces import fit, metrics
from evaluate_faces import summarize
from face_matching import align_face, face_embedding, pixel_hash
from identity_lab import IdentityLab, InputError, decode_image
from train_face_adapter import pair_records, sha, write

SCENARIOS = ("clean", "document_lowres", "selfie_shadow")


def stress(image, role, scenario):
    if scenario not in SCENARIOS:
        raise ValueError("Unknown stress scenario")
    if scenario == "document_lowres" and role == "reference":
        small = cv2.resize(image, (28, 28), interpolation=cv2.INTER_AREA)
        restored = cv2.resize(small, (112, 112), interpolation=cv2.INTER_LINEAR)
        ok, encoded = cv2.imencode(".jpg", restored, [cv2.IMWRITE_JPEG_QUALITY, 45])
        if not ok:
            raise RuntimeError("JPEG encode failed")
        return cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if scenario == "selfie_shadow" and role == "selfie":
        gradient = np.linspace(0.25, 0.9, image.shape[1])[None, :, None]
        return np.clip(image.astype(float) * gradient, 0, 255).astype(np.uint8)
    return image.copy()


def load_recognizer(name):
    from uniface.constants import AdaFaceWeights
    from uniface.recognition import AdaFace

    weights = {"adaface_ir18": AdaFaceWeights.IR_18, "adaface_ir101": AdaFaceWeights.IR_101}
    if name not in weights:
        raise ValueError("Unsupported recognizer")
    model = AdaFace(model_name=weights[name], providers=["CPUExecutionProvider"])
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    model.session = ort.InferenceSession(
        str(model.model_path), sess_options=options, providers=["CPUExecutionProvider"]
    )
    return model


def choose(reports, tolerance=0.01):
    """Choose fastest near best worst-scenario balanced error, without personal scores."""
    scores = {}
    for name, report in reports.items():
        values = []
        for scenario in SCENARIOS:
            m = report["scenarios"][scenario]["validation_operating_point"]
            if m["fmr_scored"] is None or m["fnmr_scored"] is None:
                raise ValueError("Both classes required")
            values.append((m["fmr_scored"] + m["fnmr_scored"]) / 2)
        scores[name] = max(values)
    best = min(scores.values())
    eligible = [n for n, v in scores.items() if v <= best + tolerance]
    return min(eligible, key=lambda n: reports[n]["embedding_ms_median"]), scores


def run(root, prepared, out):
    root, prepared, out = Path(root).resolve(), Path(prepared), Path(out)
    out.mkdir(parents=True, exist_ok=False)
    data = json.loads((prepared / "prepared.json").read_text())
    # Test identity images and private photos are never opened by this command.
    rows = [r for r in data["images"] if r["split"] in {"train", "valid"}]
    policy = {
        "scenarios": SCENARIOS,
        "calibration": "clean train, target empirical FMR=0; frozen across stress scenarios",
        "selection": "fastest within 0.01 worst-scenario balanced error of best on validation",
        "test_images_read": False,
        "personal_images_read": False,
        "code_sha256": sha(__file__),
        "prepared_sha256": sha(prepared / "prepared.json"),
    }
    write(out / "protocol.json", policy)
    lab = IdentityLab(face_model="adaface_ir18")
    lab._load_faces()
    models = {"adaface_ir18": lab._recognizer, "adaface_ir101": load_recognizer("adaface_ir101")}
    # Warm-up each session before measuring.
    for model in models.values():
        face_embedding(model, np.zeros((112, 112, 3), dtype=np.uint8))
    embeddings = {name: {s: {} for s in SCENARIOS} for name in models}
    times = {name: [] for name in models}
    records = []
    for i, row in enumerate(rows):
        path = (root / row["file"]).resolve()
        if not path.is_relative_to(root) or sha(path) != row["sha256"]:
            raise ValueError("Dataset path/hash mismatch")
        image = decode_image(path.read_bytes())
        if pixel_hash(image) != row["pixel_sha256"]:
            raise ValueError("Decoded source changed")
        record = dict(row)
        try:
            aligned, _ = align_face(lab, image, row["role"].upper())
            record["status"] = "ok"
            for scenario in SCENARIOS:
                transformed = stress(aligned, row["role"], scenario)
                order = list(models)
                if i % 2:
                    order.reverse()
                for name in order:
                    start = time.perf_counter()
                    embeddings[name][scenario][row["file"]] = face_embedding(
                        models[name], transformed
                    )
                    times[name].append((time.perf_counter() - start) * 1000)
        except InputError as exc:
            record.update(status="retry", reason=str(exc))
        records.append(record)
        if (i + 1) % 10 == 0:
            print(f"External train/valid images {i + 1}/{len(rows)}", flush=True)
    reports = {}
    for name, model in models.items():
        all_pairs = {
            scenario: {
                split: pair_records(records, embeddings[name][scenario], np.ones(512), split)
                for split in ["train", "valid"]
            }
            for scenario in SCENARIOS
        }
        threshold = fit(all_pairs["clean"]["train"], 0)["threshold"]
        report = {
            "model_sha256": sha(model.model_path),
            "embedding_ms_median": float(np.median(times[name])),
            "embedding_ms_p95": float(np.quantile(times[name], 0.95)),
            "threshold_research_only": threshold,
            "scenarios": {},
        }
        for scenario in SCENARIOS:
            pairs = all_pairs[scenario]["valid"]
            summary = summarize(pairs)
            summary["note"] = (
                "External validation, identity-disjoint from train calibration. Synthetic stress after alignment, not ageing or live capture."
            )
            report["scenarios"][scenario] = {
                "summary": summary,
                "validation_operating_point": metrics(pairs, threshold),
            }
            write(out / f"{name}_{scenario}_validation_pairs.json", pairs)
        write(out / f"{name}_train_calibration_pairs.json", all_pairs["clean"]["train"])
        reports[name] = report
    selected, scores = choose(reports)
    from importlib.metadata import version

    result = {
        "protocol": policy,
        "models": reports,
        "selected": selected,
        "selection_scores": scores,
        "runtime": {k: version(k) for k in ["uniface", "onnxruntime", "numpy", "opencv-python"]},
        "detector_sha256": sha(lab._detector._model_path),
        "alignment_code_sha256": sha(Path(__file__).with_name("face_matching.py")),
        "limitations": [
            "12 train/4 validation identities only",
            "Validation reused for development",
            "Stress tested after detection/alignment; detector robustness not measured",
            "No actual cross-age dataset in this run",
            "Pretraining overlap unknown",
            "Zero calibration errors is not a population FMR guarantee",
        ],
        "production_ready": False,
    }
    write(out / "comparison.json", result)
    print(
        json.dumps(
            {
                "selected": selected,
                "scores": scores,
                "embedding_ms": {n: r["embedding_ms_median"] for n, r in reports.items()},
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.dataset, args.prepared, args.out)
