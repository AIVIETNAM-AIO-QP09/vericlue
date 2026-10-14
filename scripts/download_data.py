"""Tải dữ liệu công khai VeriClue, seed 42 và giữ nguyên nhóm nguồn.

uv run --group data python scripts/download_data.py --dry-run
uv run --group data python scripts/download_data.py --only vn_celeb_faces vivos
Dữ liệu: DATA_DIR (mặc định ./data); không commit hoặc phân phối lại.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

from data_download_core import (
    Client,
    Dataset,
    DownloadError,
    Plan,
    SkipDataset,
    check_disk,
    remaining_peak,
    safe_path,
    write_source,
)

ROOT = Path(__file__).resolve().parent.parent
GB = 1_000_000_000
SMALL_LIMIT = 30 * GB
SEED = 42

DATASETS = {
    d.name: d
    for d in (
        Dataset(
            "zalo2022",
            "https://www.kaggle.com/datasets/hlly34/liveness-detection-zalo-2022",
            "MIT theo mirror; điều khoản Zalo gốc chưa rõ",
            2_817_457_304,
            3 * GB,
        ),
        Dataset(
            "fas_vn",
            "https://www.kaggle.com/datasets/maihongtng/face-anti-spoofing",
            "CC BY 4.0",
            8_904_892_791,
            9 * GB,
        ),
        Dataset(
            "rtfs10k",
            "https://www.kaggle.com/datasets/stplusplus/rtfs-10k",
            "CC BY-SA 4.0",
            17_659_561_217,
            5 * GB,
        ),
        Dataset(
            "wilddeepfake",
            "https://huggingface.co/datasets/xingjunm/WildDeepfake",
            "Apache-2.0 theo HF",
            72_803_555_730,
            GB,
        ),
        Dataset(
            "celeba_spoof",
            "https://github.com/ZhangYuanhan-AI/CelebA-Spoof",
            "Nghiên cứu phi thương mại; cấm phân phối lại",
            None,
            GB,
        ),
        Dataset(
            "vn_celeb_faces",
            "https://huggingface.co/datasets/fptudsc/face-celeb-vietnamese",
            "Apache-2.0 theo HF; nguồn Kaggle ghi giấy phép chưa rõ",
            80_630_170,
            200_000_000,
        ),
        Dataset(
            "vicocktail",
            "https://huggingface.co/datasets/nguyenvulebinh/ViCocktail",
            "Không ghi — giấy phép chưa rõ",
            113_756_823_154,
            2_300_000_000,
        ),
        Dataset(
            "lavdf",
            "https://huggingface.co/datasets/ControlNet/LAV-DF",
            "CC BY-NC 4.0",
            25_607_198_720,
            GB,
            True,
        ),
        Dataset(
            "mlaad_vi",
            "https://huggingface.co/datasets/mueller91/MLAAD",
            "CC BY-NC 4.0",
            1_599_173_691,
            400_000_000,
            True,
        ),
        Dataset(
            "vispoofdb",
            "https://github.com/studie-e/Vietnamese-Audio-Deepfake-Detection",
            "Không ghi — giấy phép chưa rõ",
            2_400_000_000,
            2_400_000_000,
        ),
        Dataset(
            "vsasv",
            "https://huggingface.co/datasets/hustep-lab/VSASV-Dataset",
            "CC BY-NC 4.0",
            69_218_976_724,
            550_000_000,
            True,
        ),
        Dataset(
            "vimd",
            "https://huggingface.co/datasets/nguyendv02/ViMD_Dataset",
            "CC BY-NC-ND 4.0",
            59_828_312_520,
            800_000_000,
        ),
        Dataset(
            "vivos",
            "https://huggingface.co/datasets/AILAB-VNUHCM/vivos",
            "CC BY-NC-SA 4.0",
            1_474_408_300,
            1_750_000_000,
        ),
    )
}
AUDIO_NAMES = {"mlaad_vi", "vispoofdb", "vsasv", "vimd", "vivos"}
KAGGLE_NAMES = {"zalo2022", "fas_vn", "rtfs10k"}


def resolve_data_dir(value: str | None = None) -> Path:
    """Đường dẫn tương đối DATA_DIR luôn tính từ gốc worktree."""
    path = Path(value or os.environ.get("DATA_DIR") or "./data").expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


def load_credentials() -> tuple[str, tuple[str, str] | None]:
    """Đọc biến môi trường hoặc kaggle.json, không log giá trị bí mật."""
    token = os.environ.get("HF_TOKEN", "")
    user, key = os.environ.get("KAGGLE_USERNAME", ""), os.environ.get("KAGGLE_KEY", "")
    if user and key:
        return token, (user, key)
    folder = Path(os.environ.get("KAGGLE_CONFIG_DIR", str(Path.home() / ".kaggle")))
    credential_file = folder / "kaggle.json"
    if credential_file.exists():
        try:
            credentials = json.loads(credential_file.read_text(encoding="utf-8"))
            user, key = credentials.get("username", ""), credentials.get("key", "")
            if user and key:
                return token, (user, key)
        except (OSError, ValueError):
            print("! Không đọc được kaggle.json; kiểm tra định dạng JSON và quyền đọc.")
    return token, None


def prepare_dataset(dataset: Dataset, client: Client, seed: int, subset: str) -> Plan:
    """Chỉ khám phá metadata; adapter không tải media trước kiểm tra dung lượng."""
    if dataset.name in AUDIO_NAMES:
        from data_download_audio import prepare
    else:
        from data_download_images import prepare
    return prepare(dataset, client, seed, subset)


def redact(message: str, client: Client) -> str:
    """Che credential trước mọi thông báo và SOURCE."""
    secrets = [client.token, os.environ.get("KAGGLE_KEY", "")]
    if client.kaggle_auth:
        secrets.extend(client.kaggle_auth)
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[đã che]")
    return message


def _commit() -> str:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        return revision + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "không xác định"


def main(argv: list[str] | None = None) -> int:
    """Chạy tải; trả 2 khi có bộ bỏ qua, 1 khi lỗi, 0 khi hoàn thành lựa chọn."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--only", nargs="+", choices=sorted(DATASETS), help="chỉ tải các bộ có tên này"
    )
    parser.add_argument("--subset", choices=("small", "full"), default="small")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="chỉ in danh mục và ngân sách, không tải hay tạo file",
    )
    args = parser.parse_args(argv)
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=False)
    except ImportError:
        pass
    root = resolve_data_dir()
    names = args.only or list(DATASETS)
    datasets = [DATASETS[name] for name in names]
    estimate = sum(
        d.budget_bytes if args.subset == "small" else (d.full_bytes or 0) for d in datasets
    )
    print(f"DATA_DIR: {root}")
    print(
        f"Chế độ {args.subset}; seed {SEED}; dự kiến {estimate / GB:.3f} GB + tối thiểu 10 GB trống."
    )
    print(
        "Small: ngân sách đỉnh gồm cache/giải nén. Full: byte nguồn đã biết, giải nén sẽ tính thêm."
    )
    for d in datasets:
        full = f"{d.full_bytes / GB:.3f} GB" if d.full_bytes is not None else "chưa rõ"
        print(f"- {d.name}: small ≤{d.budget_bytes / GB:.3f} GB; full {full}; {d.source}")
    if args.dry_run:
        print("Dry-run: đây là ngân sách, chưa phải danh sách file đã chọn hoặc byte thực tải.")
        return 0
    try:
        if args.subset == "small" and estimate >= SMALL_LIMIT:
            raise DownloadError("Ngân sách small phải dưới 30 GB.")
        cached = sum(
            p.stat().st_size
            for dataset in datasets
            for p in (root / "raw" / dataset.name).rglob("*")
            if p.is_file()
        )
        check_disk(root, max(0, estimate - cached))
    except DownloadError as error:
        print(f"! {error}")
        return 1
    token, kaggle_auth = load_credentials()
    client = Client(token=token, kaggle_auth=kaggle_auth)
    outcomes: dict[str, dict] = {}
    plans: list[Plan] = []
    started = time.monotonic()
    run_commit = _commit()
    try:
        for dataset in datasets:
            try:
                if dataset.gated and not token:
                    raise SkipDataset(
                        "Thiếu HF_TOKEN: đăng nhập huggingface.co, chấp nhận điều khoản trang bộ dữ liệu, tạo token Read tại https://huggingface.co/settings/tokens rồi đặt $env:HF_TOKEN."
                    )
                if dataset.name in KAGGLE_NAMES and not kaggle_auth:
                    raise SkipDataset(
                        "Thiếu Kaggle: vào https://www.kaggle.com/settings/account tạo API credentials, đặt KAGGLE_USERNAME/KAGGLE_KEY hoặc lưu kaggle.json vào ~/.kaggle/."
                    )
                provider_dataset = (
                    replace(
                        dataset,
                        budget_bytes=dataset.budget_bytes
                        - min(5_000_000, dataset.budget_bytes // 100),
                    )
                    if args.subset == "small"
                    else dataset
                )
                plan = prepare_dataset(provider_dataset, client, SEED, args.subset)
                plan.dataset = dataset
                plan.peak_bytes += max(1_000_000, len(plan.files) * 256 + len(plan.groups) * 128)
                if plan.peak_bytes < sum(f.size for f in plan.files) or any(
                    f.size < 0 for f in plan.files
                ):
                    raise DownloadError("Adapter không khai báo đủ dung lượng file tải.")
                if args.subset == "small" and plan.peak_bytes > dataset.budget_bytes:
                    raise SkipDataset(
                        "Nhóm nguồn và chi phí cache vượt ngân sách small; không cắt nhóm hoặc tự tải full."
                    )
                for file in plan.files:
                    safe_path(root / "raw" / dataset.name, file.path)
                plans.append(plan)
            except (SkipDataset, DownloadError) as error:
                reason = redact(str(error), client)
                status = "skipped" if isinstance(error, SkipDataset) else "error"
                outcomes[dataset.name] = {"status": status, "reason": reason}
                print(f"! {dataset.name}: {reason}")
                write_source(
                    Plan(dataset, [], 0), root / "raw" / dataset.name, SEED, status, reason
                )
            except Exception as error:
                reason = f"Không đọc được metadata/dependency ({type(error).__name__}); chạy uv sync --all-packages --group data và kiểm tra nguồn."
                outcomes[dataset.name] = {"status": "error", "reason": reason}
                print(f"! {dataset.name}: {reason}")
                write_source(
                    Plan(dataset, [], 0), root / "raw" / dataset.name, SEED, "error", reason
                )
        required = sum(remaining_peak(p, root / "raw" / p.dataset.name) for p in plans)
        print(
            f"Kế hoạch khả dụng: {len(plans)}/{len(datasets)} bộ, đỉnh dự kiến {required / GB:.3f} GB."
        )
        check_disk(root, required)
        for plan in plans:
            dest = root / "raw" / plan.dataset.name
            before = time.monotonic()
            try:
                check_disk(root, remaining_peak(plan, dest))
                if plan.execute:
                    plan.execute(dest, client)
                else:
                    for file in plan.files:
                        client.download(file, safe_path(dest, file.path))
                status, reason = "complete", ""
                print(f"✓ {plan.dataset.name}: hoàn thành.")
            except (SkipDataset, DownloadError) as error:
                status = "skipped" if isinstance(error, SkipDataset) else "error"
                reason = redact(str(error), client)
                print(f"! {plan.dataset.name}: {reason}")
            except Exception as error:
                # Provider exceptions may contain signed URLs; only their type is safe to report.
                status, reason = (
                    "error",
                    f"Tải/xử lý bị lỗi ({type(error).__name__}); xem dependency/quyền truy cập và chạy lại.",
                )
                print(f"! {plan.dataset.name}: {reason}")
            plan.notes = [redact(note, client) for note in plan.notes]
            plan.groups = [redact(group, client) for group in plan.groups]
            write_source(plan, dest, SEED, status, reason)
            outcomes[plan.dataset.name] = {
                "status": status,
                "reason": reason,
                "seconds": time.monotonic() - before,
                "revision": plan.revision,
            }
        elapsed = time.monotonic() - started
        files = [p for d in datasets for p in (root / "raw" / d.name).rglob("*") if p.is_file()]
        stored = sum(p.stat().st_size for p in files)
        summary = {
            "subset": args.subset,
            "seed": SEED,
            "commit": run_commit,
            "selected": names,
            "seconds": elapsed,
            "stored_bytes": stored,
            "outcomes": outcomes,
            "entire_catalog_complete": len(datasets) == len(DATASETS)
            and all(o["status"] == "complete" for o in outcomes.values()),
        }
        summary_dir = root / "runs"
        summary_dir.mkdir(parents=True, exist_ok=True)
        path = summary_dir / f"{time.time_ns()}-{args.subset}.json"
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Đã lưu {stored / GB:.3f} GB; {elapsed / 60:.2f} phút. Báo cáo: {path}")
        if any(o["status"] == "error" for o in outcomes.values()):
            return 1
        return 2 if any(o["status"] == "skipped" for o in outcomes.values()) else 0
    except DownloadError as error:
        print(f"! {redact(str(error), client)}")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
