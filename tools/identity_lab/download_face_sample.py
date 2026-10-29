"""Download the version-pinned CC BY 4.0 AxonData public ID/selfie sample."""

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import requests

REPO = "AxonData/Selfie_and_Official_ID_Photo_Dataset"
REVISION = "5da0a5cc8f9fc8e33e816330f02a8b98a33dc768"
GROUPS = {"African", "Caucasians", "Hispanic", "Middle East", "South Asia"}
DOCS = {"id", "national_id", "passport", "passport_1", "passport_2"}


def get(url):
    response = requests.get(url, timeout=90)
    response.raise_for_status()
    return response


def classify(path):
    p = PurePosixPath(path)
    if (
        len(p.parts) != 3
        or p.parts[0] not in GROUPS
        or p.suffix.lower() not in {".jpg", ".jpeg", ".png"}
    ):
        return None
    if p.stem.lower() in DOCS:
        role = "reference"
    elif p.stem.lower().startswith(("phone_", "webcam_")):
        role = "selfie"
    else:
        raise ValueError(f"Unrecognized role: {path}")
    # Provider folder denotes identity, not a demographic prediction by this tool.
    identity = hashlib.sha256(str(p.parent).encode()).hexdigest()[:16]
    return identity, role


def download(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tree = get(
        f"https://huggingface.co/api/datasets/{REPO}/tree/{REVISION}?recursive=true&limit=1000"
    )
    if "next" in tree.links:
        raise ValueError("Unexpected paginated listing; inspect source before download")
    readme = get(f"https://huggingface.co/datasets/{REPO}/raw/{REVISION}/README.md").text
    if "license: cc-by-4.0" not in readme:
        raise ValueError("Dataset license differs from reviewed CC BY 4.0")
    (out / "SOURCE_README.md").write_text(readme, encoding="utf-8")
    files = [item for item in tree.json() if item["type"] == "file" and classify(item["path"])]

    def fetch(item):
        source = item["path"]
        identity, role = classify(source)
        name = f"{identity}/{PurePosixPath(source).name}"
        target = out / name
        target.parent.mkdir(exist_ok=True)
        expected = item.get("lfs", {}).get("oid")
        data = target.read_bytes() if target.exists() else b""
        if len(data) != item["size"] or (expected and hashlib.sha256(data).hexdigest() != expected):
            data = get(
                f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{quote(source, safe='/')}"
            ).content
            if len(data) != item["size"] or (
                expected and hashlib.sha256(data).hexdigest() != expected
            ):
                raise ValueError(f"Content verification failed: {source}")
            target.write_bytes(data)
        return {
            "identity": identity,
            "role": role,
            "file": name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "source": source,
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(fetch, files))
    manifest = {
        "source": f"https://huggingface.co/datasets/{REPO}",
        "revision": REVISION,
        "license": "CC-BY-4.0",
        "attribution": "AxonData / Axon Labs",
        "scope": "Named public sample folders only; separate numbered sample excluded to avoid possible identity overlap",
        "images": rows,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "files": len(rows),
                "identities": len({r["identity"] for r in rows}),
                "bytes": sum((out / r["file"]).stat().st_size for r in rows),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    download(parser.parse_args().out)
