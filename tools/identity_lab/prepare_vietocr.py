"""Download official VietOCR config/weights into the local lab cache."""

import argparse
import hashlib
import json

import requests
import yaml
from identity_lab import MODEL_ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--architecture", choices=["seq2seq", "transformer"], default="seq2seq")
    args = parser.parse_args()
    architecture = args.architecture
    target = MODEL_ROOT / ("vietocr" if architecture == "seq2seq" else "vietocr_transformer")
    target.mkdir(parents=True, exist_ok=True)
    config = {}
    sources = []
    for name in ["base.yml", f"vgg-{architecture}.yml"]:
        url = f"https://vocr.vn/data/vietocr/config/{name}"
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        (target / name).write_bytes(response.content)
        config.update(yaml.safe_load(response.content))
        sources.append(url)
    url = config["weights"]
    sources.append(url)
    weights = target / f"vgg_{architecture}.pth"
    if not weights.exists():
        temporary = weights.with_suffix(".part")
        print(f"Downloading {url}", flush=True)
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    handle.write(chunk)
        temporary.replace(weights)
    config["weights"] = str(weights)
    config["device"] = "cpu"
    config["cnn"]["pretrained"] = False
    config["predictor"]["beamsearch"] = False
    (target / "local.yml").write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    (target / "provenance.json").write_text(
        json.dumps(
            {
                "sources": sources,
                "sha256": hashlib.sha256(weights.read_bytes()).hexdigest(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("VietOCR model prepared.", flush=True)


if __name__ == "__main__":
    main()
