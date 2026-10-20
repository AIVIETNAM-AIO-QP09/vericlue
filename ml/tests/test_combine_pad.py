"""FACE-04 — ml/notebooks/combine_pad.py gộp 2 lần chạy notebook PAD (không cần GPU/trọng số)."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("combine_pad", ROOT / "ml/notebooks/combine_pad.py")
combine_pad = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(combine_pad)

N = 120


def _split_files(variant: str = "") -> dict[str, bytes]:
    head = "rel_path,sha256,label,orig_split,source,status,group_id,split\n"
    body = "".join(
        f"img{i}.jpg,{i:064x},{'live' if i % 2 else 'not_live'},train_photo,{'A' if i % 3 else 'B'},kept,g{i // 2},calib_fit\n"
        for i in range(N)
    )
    files = {"splits.csv": (head + body + variant).encode()}
    for s in ("train", "calib_fit", "calib_ltt", "test"):
        files[f"split_{s}.csv"] = (head + (body if s == "calib_fit" else "")).encode()
    return files


def _scores(models: dict[str, np.ndarray]) -> bytes:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    cols = ["sample_id", "group_id", "label", "source", "split"]
    for k in models:
        cols += [f"raw_attack_score_{k}", f"cal_attack_prob_{k}"]
    w.writerow(cols)
    for i in range(N):
        line = [f"img{i}.jpg", f"g{i // 2}", "live" if i % 2 else "not_live", "A" if i % 3 else "B"]
        line.append("calib_fit")
        for v in models.values():
            line += [f"{v[i]:.6f}", f"{v[i]:.6f}"]
        w.writerow(line)
    return out.getvalue().encode()


def _zip(path: Path, model: str, models: dict[str, np.ndarray], variant: str = "") -> Path:
    files = _split_files(variant)
    metrics = {
        "model": model,
        "smoke": True,
        "source_commit": "abc",
        "dataset": {
            "split_files_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}
        },
    }
    files["metrics.json"] = json.dumps(metrics).encode()
    files["scores_calib_fit.csv"] = _scores(models)
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(f"pad_export_{model}/{name}", data)
    return path


def _probs(seed: int, strength: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    attack = np.array([0 if i % 2 else 1 for i in range(N)])
    return np.clip(0.5 + strength * (attack - 0.5) + rng.normal(0, 0.25, N), 0, 1)


def test_combine_reports_three_candidates_and_recommendation(tmp_path):
    mini = _zip(
        tmp_path / "m.zip",
        "minifasnet",
        {"baseline": _probs(1, 0.2), "minifasnet_ft": _probs(2, 0.5)},
    )
    dino = _zip(tmp_path / "d.zip", "dinov2", {"dinov2_ft": _probs(3, 0.5)})
    assert (
        combine_pad.main(
            [
                "--minifasnet",
                str(mini),
                "--dinov2",
                str(dino),
                "--out",
                str(tmp_path),
                "--n-boot",
                "10",
            ]
        )
        == 0
    )
    result = json.loads((tmp_path / "combine_report.json").read_text(encoding="utf-8"))
    assert set(result["calib_fit"]) == {"baseline", "minifasnet_ft", "dinov2_ft", "combo"}
    assert result["mini_best"] == "minifasnet_ft"
    assert result["recommendation"]["choice"] in {"combo", "minifasnet_ft", "dinov2_ft", "baseline"}
    assert set(result["by_source"]) == {"A", "B"}
    md = (tmp_path / "combine_report.md").read_text(encoding="utf-8")
    assert "Khuyến nghị" in md and "GỘP" in md


def test_combine_refuses_different_splits(tmp_path, capsys):
    mini = _zip(tmp_path / "m.zip", "minifasnet", {"baseline": _probs(1, 0.5)})
    dino = _zip(
        tmp_path / "d.zip",
        "dinov2",
        {"dinov2_ft": _probs(3, 0.5)},
        variant="x.jpg,0,live,a,A,kept,gx,train\n",
    )
    assert (
        combine_pad.main(["--minifasnet", str(mini), "--dinov2", str(dino), "--out", str(tmp_path)])
        == 2
    )
    assert "KHÔNG cùng cách chia" in capsys.readouterr().out
    assert not (tmp_path / "combine_report.md").exists()


def test_combine_refuses_swapped_or_tampered_zip(tmp_path):
    mini = _zip(tmp_path / "m.zip", "minifasnet", {"baseline": _probs(1, 0.5)})
    with pytest.raises(combine_pad.CombineError, match="cần 'dinov2'"):
        combine_pad.load_run(mini, "dinov2")
    tampered = tmp_path / "t.zip"
    with zipfile.ZipFile(mini) as src, zipfile.ZipFile(tampered, "w") as dst:
        for item in src.namelist():
            data = src.read(item)
            if item.endswith("/splits.csv"):
                data += b"extra\n"
            dst.writestr(item, data)
    with pytest.raises(combine_pad.CombineError, match="không khớp SHA-256"):
        combine_pad.load_run(tampered, "minifasnet")
