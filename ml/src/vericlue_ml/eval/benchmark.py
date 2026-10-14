"""Benchmark CPU tái lập cho khung eval; dữ liệu tổng hợp, không phải kết quả mô hình."""

from __future__ import annotations

import argparse
import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np
import scipy
import sklearn

from vericlue_ml.eval.report import Prediction, evaluate


def synthetic_predictions(n_rows: int, n_subjects: int, seed: int) -> list[Prediction]:
    """Mỗi subject có cả hai lớp; điểm beta tổng hợp có phần chồng lấn."""
    if n_subjects < 1 or n_rows < 2 * n_subjects or n_rows % (2 * n_subjects):
        raise ValueError("n_rows cần chia hết cho 2*n_subjects để mỗi người có hai lớp.")
    rng = np.random.default_rng(seed)
    rows = []
    attacks = ("print", "replay", "faceswap")
    for index in range(n_rows):
        block = index // n_subjects
        label = block % 2
        probability = float(rng.beta(7, 3) if label else rng.beta(3, 7))
        rows.append(
            Prediction(
                sample_id=f"synthetic-{index}",
                subject_id=f"subject-{index % n_subjects:06d}",
                label=label,
                attack_type=attacks[(block // 2) % len(attacks)] if label else "bona_fide",
                prob_attack=probability,
                status="ok",
                module="face_pad",
                model_version="synthetic-benchmark@1",
            )
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    """In JSON thời gian toàn evaluate, không tính import và sinh fixture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=10000)
    parser.add_argument("--subjects", type=int, default=500)
    parser.add_argument("--n-bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repo", type=Path)
    args = parser.parse_args(argv)
    rows = synthetic_predictions(args.rows, args.subjects, args.seed)
    started = perf_counter()
    result = evaluate(
        rows,
        dataset="synthetic-bootstrap-benchmark",
        threshold=0.5,
        seed=args.seed,
        n_bootstrap=args.n_bootstrap,
        repo=args.repo,
    )
    elapsed = perf_counter() - started
    print(
        json.dumps(
            {
                "commit": result.commit,
                "date_utc": datetime.now(UTC).isoformat(),
                "model_version": result.groups[0].model_version,
                "dataset": result.dataset,
                "n_rows": args.rows,
                "n_subjects": args.subjects,
                "n_bootstrap": args.n_bootstrap,
                "seed": args.seed,
                "elapsed_seconds": elapsed,
                "scope": "full evaluate; excludes imports and synthetic fixture generation",
                "platform": platform.platform(),
                "processor": platform.processor(),
                "python": platform.python_version(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "sklearn": sklearn.__version__,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
