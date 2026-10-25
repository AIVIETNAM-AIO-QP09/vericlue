"""Download and SHA-256 verify selected face model using the installed UniFace registry."""

import argparse

from identity_lab import MODEL_ROOT


def main():
    from uniface.constants import AdaFaceWeights, ArcFaceWeights, SCRFDWeights
    from uniface.model_store import verify_model_weights

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recognizer", choices=("adaface_ir18", "arcface_r50"), required=True)
    args = parser.parse_args()
    model = ArcFaceWeights.RESNET if args.recognizer == "arcface_r50" else AdaFaceWeights.IR_18
    for weight in (SCRFDWeights.SCRFD_10G_KPS, model):
        print(
            verify_model_weights(weight, root=str(MODEL_ROOT / "uniface"), max_retries=1),
            flush=True,
        )


if __name__ == "__main__":
    main()
