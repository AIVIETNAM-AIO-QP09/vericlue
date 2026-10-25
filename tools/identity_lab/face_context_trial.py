"""Run the frozen IR18 + no-face recovery candidate, without an identity threshold."""

import argparse
import json
from pathlib import Path

from face_context import context_config, enable_context
from face_matching import match_pair
from identity_lab import IdentityLab
from train_face_adapter import sha, write


def run(prepared, references, selfies, out):
    prepared, out = Path(prepared), Path(out)
    expected = json.loads(prepared.read_text())["pipeline"]
    lab = IdentityLab(face_model="adaface_ir18")
    enable_context(lab)
    if context_config(lab) != expected:
        raise ValueError("Pipeline differs from the evaluated context candidate")
    out.mkdir(parents=True, exist_ok=False)
    # Freeze configuration before opening any personal image.
    write(
        out / "selection.json",
        {
            "prepared_sha256": sha(prepared),
            "pipeline": expected,
            "recognizer": "adaface_ir18",
            "adapter": None,
            "threshold": None,
            "policy": "IR18 baseline with context fallback; no personal-data selection or tuning",
        },
    )
    pairs = []
    for ref in references:
        for selfie in selfies:
            result = match_pair(lab, Path(ref).read_bytes(), Path(selfie).read_bytes())
            result.update(reference_file=str(ref), selfie_file=str(selfie))
            pairs.append(result)
    write(out / "report.json", {"pairs": pairs, "production_ready": False})
    print(
        json.dumps(
            [
                {
                    "reference": p["reference_file"],
                    "selfie": p["selfie_file"],
                    "status": p["status"],
                    "cosine_similarity": p["cosine_similarity"],
                }
                for p in pairs
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--references", type=Path, nargs="+", required=True)
    parser.add_argument("--selfies", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.prepared, args.references, args.selfies, args.out)
