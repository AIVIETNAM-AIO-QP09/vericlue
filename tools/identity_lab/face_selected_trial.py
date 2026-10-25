"""Run a locked external-validation choice on personal photos, without selecting again."""

import argparse
import json
from importlib.metadata import version
from pathlib import Path

from face_matching import extract_face, pixel_hash
from face_robustness import choose, load_recognizer
from identity_lab import IdentityLab, InputError, cosine, decode_image
from train_face_adapter import sha, write


def verify_selection(report):
    expected, _ = choose(report["models"])
    if report["selected"] != expected:
        raise ValueError("Selection does not match fixed external-data policy")
    if sha(Path(__file__).with_name("face_robustness.py")) != report["protocol"]["code_sha256"]:
        raise ValueError("Selection code changed; rerun external comparison")
    if sha(Path(__file__).with_name("face_matching.py")) != report["alignment_code_sha256"]:
        raise ValueError("Face pipeline changed")
    if any(version(k) != v for k, v in report["runtime"].items()):
        raise ValueError("Runtime differs from validation")
    return expected


def run(comparison, references, selfies, out):
    report = json.loads(Path(comparison).read_text())
    name = verify_selection(report)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    # Lock and persist selection before reading any personal input.
    write(
        out / "selection.json",
        {
            "comparison_sha256": sha(comparison),
            "selected": name,
            "policy": "locked before personal inputs; no refit or per-pair switching",
        },
    )
    lab = IdentityLab(face_model="adaface_ir18")
    lab._load_faces()
    if name != "adaface_ir18":
        lab._recognizer = load_recognizer(name)
    if (
        sha(lab._recognizer.model_path) != report["models"][name]["model_sha256"]
        or sha(lab._detector._model_path) != report["detector_sha256"]
    ):
        raise ValueError("Weights differ from validated weights")
    records, vectors = [], {}
    for role, paths in [("reference", references), ("selfie", selfies)]:
        for i, path in enumerate(paths):
            key = f"{role}_{i}"
            record = {"key": key, "role": role, "file": str(path), "sha256": sha(path)}
            try:
                image = decode_image(Path(path).read_bytes())
                record["pixel_sha256"] = pixel_hash(image)
                vectors[key], evidence = extract_face(lab, image, role.upper(), out / key)
                record.update(status="ok", evidence=evidence)
            except InputError as exc:
                record.update(status="retry", reason=str(exc))
            records.append(record)
    pairs = []
    for ref in [r for r in records if r["role"] == "reference"]:
        for selfie in [r for r in records if r["role"] == "selfie"]:
            errors = [r["reason"] for r in [ref, selfie] if r["status"] != "ok"]
            if ref.get("pixel_sha256") and ref.get("pixel_sha256") == selfie.get("pixel_sha256"):
                errors.append("E_IDENTICAL_INPUTS")
            pairs.append(
                {
                    "reference": ref["file"],
                    "selfie": selfie["file"],
                    "status": "retry" if errors else "ok",
                    "reason": ";".join(errors) or None,
                    "cosine_similarity": None
                    if errors
                    else cosine(vectors[ref["key"]], vectors[selfie["key"]]),
                }
            )
    result = {
        "selected": name,
        "images": records,
        "pairs": pairs,
        "threshold": None,
        "decision": "review",
        "identity_verified": False,
        "scope": "Personal check after externally selected configuration. No labels inferred; no PAD/document authenticity check; no threshold applied.",
    }
    write(out / "report.json", result)
    print(json.dumps({"model": name, "pairs": pairs}, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--references", type=Path, nargs="+", required=True)
    parser.add_argument("--selfies", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.comparison, args.references, args.selfies, args.out)
