"""Download checksum-pinned LFW originals and official development-test pairs."""

import argparse
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

from card_dataset import sha256

SOURCES = {
    "lfw.tgz": (
        "https://ndownloader.figshare.com/files/5976018",
        "055f7d9c632d7370e6fb4afc7468d40f970c34a80d4c6f50ffec63f5a8d536c0",
    ),
    "pairsDevTest.txt": (
        "https://ndownloader.figshare.com/files/5976009",
        "7cb06600ea8b2814ac26e946201cdb304296262aad67d046a16a7ec85d0ff87c",
    ),
}


def parse_pairs(text):
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 1:
            continue
        if len(parts) == 3:
            name, first, second = parts
            other = name
            same = True
        elif len(parts) == 4:
            name, first, other, second = parts
            same = False
        else:
            raise ValueError("Invalid pair line")
        for value in (name, other):
            if not value or "/" in value or "\\" in value or value in {".", ".."}:
                raise ValueError("Invalid person path")
        rows.append(
            {
                "pair_id": len(rows),
                "reference": f"lfw/{name}/{name}_{int(first):04d}.jpg",
                "selfie": f"lfw/{other}/{other}_{int(second):04d}.jpg",
                "same_person": same,
                "reference_identity": name,
                "selfie_identity": other,
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for name, (url, checksum) in SOURCES.items():
        path = root / name
        if not path.exists():
            temporary = path.with_suffix(".part")
            print(f"Downloading {name}", flush=True)
            with (
                urllib.request.urlopen(url, timeout=120) as response,
                temporary.open("wb") as stream,
            ):
                shutil.copyfileobj(response, stream)
            if sha256(temporary) != checksum:
                raise ValueError("Download hash mismatch")
            temporary.replace(path)
        if sha256(path) != checksum:
            raise ValueError(f"Hash mismatch: {name}")
    rows = parse_pairs((root / "pairsDevTest.txt").read_text())
    wanted = {r[key] for r in rows for key in ("reference", "selfie")}
    with tarfile.open(root / "lfw.tgz", "r:gz") as archive:
        for member in archive:
            if member.name not in wanted:
                continue
            target = (root / member.name).resolve()
            if not target.is_relative_to(root) or not member.isfile():
                raise ValueError("Unsafe archive entry")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
    if any(not (root / p).is_file() for p in wanted):
        raise ValueError("Missing pair images")
    (root / "pairs.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (root / "provenance.json").write_text(
        json.dumps(
            {
                "sources": SOURCES,
                "pairs": len(rows),
                "scope": "LFW development test, original 250px photos, not ID/selfie and not official 10-fold evaluation.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Prepared {len(rows)} pairs, {len(wanted)} images", flush=True)


if __name__ == "__main__":
    main()
