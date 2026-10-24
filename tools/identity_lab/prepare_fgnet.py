"""Download research-hosted FG-NET and prepare adult cross-age roles by filename labels."""

import argparse
import hashlib
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

import requests

SOURCE = "https://yanweifu.github.io/FG_NET_data/index.html"
URL = "https://yanweifu.github.io/FG_NET_data/FGNET.zip"


def parse_name(name):
    match = re.fullmatch(r"(\d{3})A(\d{2})([a-z]?)\.(jpg|jpeg|png)", name, re.IGNORECASE)
    if not match:
        raise ValueError(f"Unrecognized FG-NET image filename: {name}")
    return "fgnet_" + match[1], int(match[2])


def select_roles(rows):
    """One earlier-age domain and a >=3-year later domain; adult images only."""
    groups = defaultdict(list)
    for row in rows:
        if row["age"] >= 18:
            groups[row["identity"]].append(row)
    selected = []
    for _identity, images in sorted(groups.items()):
        earliest = min(r["age"] for r in images)
        later = [r for r in images if r["age"] >= earliest + 3]
        if not later:
            continue
        selected += [{**r, "role": "reference"} for r in images if r["age"] == earliest]
        selected += [{**r, "role": "selfie"} for r in later]
    return selected


def prepare(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    archive = out / "FGNET.zip"
    if not archive.exists():
        part = archive.with_suffix(".part")
        with requests.get(URL, stream=True, timeout=90) as response:
            response.raise_for_status()
            count = 0
            with part.open("wb") as f:
                for chunk in response.iter_content(1024 * 1024):
                    f.write(chunk)
                    count += len(chunk)
                    if count > 1024**3:
                        raise ValueError("Archive unexpectedly exceeds 1 GiB")
                    if count % (10 * 1024 * 1024) == 0:
                        print(f"Downloaded {count // (1024 * 1024)} MiB", flush=True)
        if not zipfile.is_zipfile(part):
            raise ValueError("Download is not a ZIP archive")
        part.replace(archive)
    response = requests.get(SOURCE, timeout=60)
    response.raise_for_status()
    (out / "SOURCE.html").write_text(response.text, encoding="utf-8")
    rows = []
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            p = PurePosixPath(info.filename)
            if "images" not in [x.lower() for x in p.parts] or p.suffix.lower() not in {
                ".jpg",
                ".jpeg",
                ".png",
            }:
                continue
            if info.file_size > 20 * 1024 * 1024 or info.flag_bits & 1:
                raise ValueError("Unexpected oversized/encrypted image")
            identity, age = parse_name(p.name)
            rows.append(
                {
                    "identity": identity,
                    "age": age,
                    "source": info.filename,
                    "file": "images/" + p.name,
                }
            )
        if not rows:
            raise ValueError("No FG-NET images found; inspect archive")
        selected = select_roles(rows)
        (out / "images").mkdir(exist_ok=True)
        seen = set()
        for row in selected:
            if row["file"] in seen:
                raise ValueError("Ambiguous output filename")
            seen.add(row["file"])
            data = z.read(row["source"])
            (out / row["file"]).write_bytes(data)
            row["sha256"] = hashlib.sha256(data).hexdigest()
    audit = {
        "source": SOURCE,
        "revision": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "attribution": "FG-NET, hosted by Yanwei Fu; original age/identity labels from filenames",
        "license": "Research-hosted data; no commercial/redistribution license asserted. Retain source page; local research only.",
        "scope": "Adult face photos across >=3 years; reference/selfie are earlier/later roles, NOT real identity-document/selfie pairs",
        "original_images": len(rows),
        "selected_images": len(selected),
        "selected_identities": len({r["identity"] for r in selected}),
        "min_age": 18,
        "minimum_genuine_age_gap": 3,
        "images": selected,
    }
    (out / "manifest.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in audit.items() if k != "images"}, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    prepare(parser.parse_args().out)
