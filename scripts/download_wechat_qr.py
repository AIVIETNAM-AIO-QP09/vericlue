"""Download pinned WeChat QR weights only; verify bytes before atomic installation."""

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api/src"))

from vericlue_api.services.wechat_qr import MODEL_SHA256, MODEL_SUBDIR, REVISION  # noqa: E402


def download(models_dir: Path) -> None:
    """Fetch public OpenCV model files; never overwrite unverified model bytes."""
    root = models_dir.resolve()
    folder = (root / MODEL_SUBDIR).resolve()
    if not folder.is_relative_to(root):
        raise ValueError("Model directory outside MODELS_DIR")
    folder.mkdir(parents=True, exist_ok=True)
    for name, expected in MODEL_SHA256.items():
        target = folder / name
        if target.is_symlink() or not target.resolve().is_relative_to(root):
            raise ValueError("Redirected model file")
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            print(f"Verified: {name}")
            continue
        url = f"https://raw.githubusercontent.com/opencv/opencv_3rdparty/{REVISION}/{name}"
        with urllib.request.urlopen(url, timeout=60) as response:
            content = response.read(2 * 1024 * 1024 + 1)
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f"Unexpected model checksum: {name}")
        temporary = target.with_suffix(target.suffix + ".download")
        # Exclusive create prevents following an existing symlink or partial download.
        with temporary.open("xb") as handle:
            handle.write(content)
        temporary.replace(target)
        print(f"Installed: {name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, required=True)
    download(parser.parse_args().models_dir)
