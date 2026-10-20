"""FACE-04 — gộp kết quả 2 lần chạy notebook PAD (Người 1: MiniFASNet, Người 2: DINOv2).

Chạy trên laptop trưởng nhóm (CPU, vài giây):
    uv run --no-sync python ml/notebooks/combine_pad.py --minifasnet <zip MiniFASNet> --dinov2 <zip DINOv2>

Việc làm:
1. Kiểm 2 zip cùng một cách chia tập: SHA-256 của `splits.csv` (và từng `split_*.csv`) phải trùng,
   ghi trong `metrics.json` và tính lại trên file trong zip.
2. Ghép từng mẫu calib_fit theo `sample_id`, kiểm nhãn/nhóm người khớp nhau.
3. Đo trên calib_fit: MiniFASNet (bản tốt hơn giữa gốc/tinh chỉnh), DINOv2, GỘP = max hai xác suất
   tấn công đã hiệu chỉnh (khớp TrustRouter `fusion.method = max`). AUC, EER, APCER@BPCER≤1 %, theo nguồn A/B.
4. In khuyến nghị tiếng Việt (GỘP thắng đơn lẻ tốt nhất theo APCER, hòa thì AUC → "dùng cả hai"),
   ghi `combine_report.md` + `combine_report.json`.
Không đọc split `test`, không chạm `calib_ltt` khi chọn.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from vericlue_ml.face.pad_tuning import combo_max, pad_metrics, rank_key, recommend

SPLIT_FILES = (
    "splits.csv",
    "split_train.csv",
    "split_calib_fit.csv",
    "split_calib_ltt.csv",
    "split_test.csv",
)
MAX_BPCER = 0.01


class CombineError(RuntimeError):
    """Hai lần chạy không ghép được (khác cách chia, khác mẫu, thiếu file)."""


def _read_zip(path: Path) -> dict[str, bytes]:
    """{tên file (bỏ thư mục gốc): byte} của một zip export."""
    with zipfile.ZipFile(path) as zf:
        out = {}
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            out[name.split("/", 1)[-1]] = zf.read(name)
    return out


def load_run(path: Path, expected_model: str) -> dict[str, Any]:
    files = _read_zip(path)
    for need in ("metrics.json", "scores_calib_fit.csv", *SPLIT_FILES):
        if need not in files:
            raise CombineError(f"{path.name}: thiếu {need} — zip không phải bản export mới nhất.")
    metrics = json.loads(files["metrics.json"])
    if metrics.get("model") != expected_model:
        raise CombineError(
            f"{path.name}: là lần chạy '{metrics.get('model')}', cần '{expected_model}'."
        )
    recorded = metrics["dataset"].get("split_files_sha256", {})
    actual = {name: hashlib.sha256(files[name]).hexdigest() for name in SPLIT_FILES}
    for name, digest in actual.items():
        if recorded.get(name) != digest:
            raise CombineError(f"{path.name}: {name} không khớp SHA-256 ghi trong metrics.json.")
    rows = list(csv.DictReader(io.StringIO(files["scores_calib_fit.csv"].decode("utf-8"))))
    if any(r["split"] != "calib_fit" for r in rows):
        raise CombineError(f"{path.name}: scores_calib_fit.csv có mẫu ngoài calib_fit.")
    return {"name": path.name, "metrics": metrics, "split_sha": actual, "rows": rows}


def _metrics(labels: np.ndarray, probs: np.ndarray, groups: list[str], n_boot: int) -> dict:
    return pad_metrics(labels, probs, groups, MAX_BPCER, n_boot, seed=42)


def combine(mini: dict[str, Any], dino: dict[str, Any], n_boot: int = 500) -> dict[str, Any]:
    """Kiểm cùng cách chia, ghép mẫu, đo 3 ứng viên và khuyến nghị."""
    if mini["split_sha"] != dino["split_sha"]:
        diff = [k for k in SPLIT_FILES if mini["split_sha"][k] != dino["split_sha"][k]]
        raise CombineError(
            "Hai lần chạy KHÔNG cùng cách chia tập (khác SHA-256: "
            + ", ".join(diff)
            + "). Không được gộp; cho chạy lại với EXPECTED_SPLITS_SHA = "
            + mini["split_sha"]["splits.csv"]
        )
    by_id = {r["sample_id"]: r for r in dino["rows"]}
    if set(by_id) != {r["sample_id"] for r in mini["rows"]}:
        raise CombineError("Tập mẫu calib_fit của hai lần chạy khác nhau.")
    pairs = []
    for r in sorted(mini["rows"], key=lambda r: r["sample_id"]):
        d = by_id[r["sample_id"]]
        if (r["label"], r["group_id"]) != (d["label"], d["group_id"]):
            raise CombineError(f"Mẫu {r['sample_id']}: nhãn/nhóm khác nhau giữa hai lần chạy.")
        pairs.append((r, d))
    labels = np.array([int(r["label"] == "not_live") for r, _ in pairs])
    groups = [r["group_id"] for r, _ in pairs]
    sources = np.array([r.get("source", "") for r, _ in pairs])

    mini_keys = [
        k for k in ("baseline", "minifasnet_ft") if f"cal_attack_prob_{k}" in mini["rows"][0]
    ]
    if not mini_keys or "cal_attack_prob_dinov2_ft" not in dino["rows"][0]:
        raise CombineError("Thiếu cột xác suất đã hiệu chỉnh (cal_attack_prob_*).")
    probs = {k: np.array([float(r[f"cal_attack_prob_{k}"]) for r, _ in pairs]) for k in mini_keys}
    probs["dinov2_ft"] = np.array([float(d["cal_attack_prob_dinov2_ft"]) for _, d in pairs])
    metrics = {k: _metrics(labels, v, groups, n_boot) for k, v in probs.items()}
    mini_best = min(mini_keys, key=lambda k: rank_key(metrics[k]))
    probs["combo"] = combo_max(probs[mini_best], probs["dinov2_ft"])
    metrics["combo"] = _metrics(labels, probs["combo"], groups, n_boot)
    singles = {k: metrics[k] for k in (*mini_keys, "dinov2_ft")}
    rec = recommend(singles, metrics["combo"])
    rec["combo_members"] = [mini_best, "dinov2_ft"]

    by_source: dict[str, dict] = {}
    for src in sorted(set(sources)):
        mask = sources == src
        if len(set(labels[mask].tolist())) < 2 or (labels[mask] == 0).sum() < 2:
            by_source[src] = {"n": int(mask.sum()), "note": "thiếu một nhãn — không tính"}
            continue
        g = [x for x, m in zip(groups, mask, strict=True) if m]
        by_source[src] = {
            k: {**_metrics(labels[mask], v[mask], g, 0), "n": int(mask.sum())}
            for k, v in probs.items()
            if k in (mini_best, "dinov2_ft", "combo")
        }
    return {
        "splits_sha256": mini["split_sha"]["splits.csv"],
        "n_calib_fit": len(pairs),
        "n_attack": int(labels.sum()),
        "n_groups": len(set(groups)),
        "mini_best": mini_best,
        "calib_fit": metrics,
        "by_source": by_source,
        "recommendation": rec,
        "inputs": {
            "minifasnet": {"zip": mini["name"], "commit": mini["metrics"].get("source_commit")},
            "dinov2": {"zip": dino["name"], "commit": dino["metrics"].get("source_commit")},
        },
        "smoke": bool(mini["metrics"].get("smoke") or dino["metrics"].get("smoke")),
    }


NAMES = {
    "baseline": "MiniFASNet gốc",
    "minifasnet_ft": "MiniFASNet tinh chỉnh",
    "dinov2_ft": "DINOv2-reg tinh chỉnh",
    "combo": "GỘP max (MiniFASNet + DINOv2)",
}


def _fmt(v: Any) -> str:
    return "—" if v is None else f"{v:.4f}"


def report_markdown(result: dict[str, Any]) -> str:
    rec = result["recommendation"]
    lines = [
        "# Gộp PAD MiniFASNet + DINOv2 trên calib_fit (FACE-04)",
        "",
    ]
    if result["smoke"]:
        lines += ["> **CHẠY THỬ (SMOKE)** — số liệu không có giá trị.", ""]
    lines += [
        f"- `splits.csv` SHA-256 `{result['splits_sha256']}` — hai lần chạy KHỚP.",
        f"- calib_fit: {result['n_calib_fit']} mẫu ({result['n_attack']} tấn công), "
        f"{result['n_groups']} nhóm người. Xác suất đã hiệu chỉnh (calibrator fit trên calib_fit).",
        f"- MiniFASNet dùng để gộp: **{NAMES[result['mini_best']]}** (bản tốt hơn trên calib_fit).",
        "",
        "| Ứng viên | AUC | EER | APCER @ BPCER ≤ 1 % | CI95 APCER |",
        "|---|---|---|---|---|",
    ]
    for k, m in result["calib_fit"].items():
        ci = m.get("apcer_ci95")
        ci_txt = f"{ci[0]:.3f}–{ci[1]:.3f}" if ci else "—"
        lines.append(
            f"| {NAMES[k]} | {_fmt(m['auc'])} | {_fmt(m['eer'])} | {_fmt(m['apcer'])} | {ci_txt} |"
        )
    lines += ["", "## Theo nguồn ảnh (A = tại quầy, B = selfie cắt sát)", ""]
    for src, block in result["by_source"].items():
        if "note" in block:
            lines.append(f"- Nguồn {src}: {block['note']} (n={block['n']})")
            continue
        parts = [
            f"{NAMES[k]} AUC {_fmt(m['auc'])}, APCER {_fmt(m['apcer'])}" for k, m in block.items()
        ]
        lines.append(f"- Nguồn {src} (n={next(iter(block.values()))['n']}): " + "; ".join(parts))
    lines += ["", "## Khuyến nghị", ""]
    if rec["choice"] == "combo":
        lines.append(
            f"**DÙNG CẢ HAI**: {NAMES[result['mini_best']]} + DINOv2, gộp max xác suất đã hiệu chỉnh "
            "(khớp TrustRouter `fusion.method = max`). Việc còn mở: wrapper DINOv2 ở server."
        )
    else:
        lines.append(f"**Dùng một mô hình: {NAMES[rec['choice']]}**.")
    lines += [
        f"Lý do: {rec['reason_vi']}",
        "",
        "Quy tắc: GỘP thắng đơn lẻ tốt nhất nếu APCER@BPCER≤1 % thấp hơn; hòa thì AUC cao hơn. "
        "Chỉ dùng calib_fit; calib_ltt và test không được nhìn.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gộp 2 lần chạy notebook PAD (FACE-04).")
    parser.add_argument("--minifasnet", type=Path, required=True, help="zip của Người 1")
    parser.add_argument("--dinov2", type=Path, required=True, help="zip của Người 2")
    parser.add_argument("--out", type=Path, default=Path("."), help="thư mục ghi báo cáo")
    parser.add_argument("--n-boot", type=int, default=500)
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        result = combine(
            load_run(args.minifasnet, "minifasnet"), load_run(args.dinov2, "dinov2"), args.n_boot
        )
    except CombineError as exc:
        print(f"DỪNG: {exc}")
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    md = report_markdown(result)
    (args.out / "combine_report.md").write_text(md, encoding="utf-8")
    (args.out / "combine_report.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False, default=float), encoding="utf-8"
    )
    print(md)
    print(f"Đã ghi {args.out / 'combine_report.md'} và combine_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
