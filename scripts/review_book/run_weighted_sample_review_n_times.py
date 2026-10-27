#!/usr/bin/env python3
"""
Run the weighted sample review script multiple times.

Usage:
  python3 scripts/run_weighted_sample_review_n_times.py 5
  python3 scripts/run_weighted_sample_review_n_times.py 5 --dry-run
  python3 scripts/run_weighted_sample_review_n_times.py 5 --seed 42
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
TARGET_SCRIPT = SCRIPT_DIR / "run_weighted_sample_review.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "count",
        type=int,
        help="How many times to run the weighted sample review script.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Optional base seed. Each run increments it by 1 for reproducible variation.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print each command without posting any reviews.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.count <= 0:
        raise SystemExit("count must be greater than 0")

    for index in range(args.count):
        command = [sys.executable, str(TARGET_SCRIPT)]
        if args.dry_run:
            command.append("--dry-run")
        if args.seed is not None:
            command.extend(["--seed", str(args.seed + index)])

        print(f"Run {index + 1}/{args.count}")
        print("Running:", " ".join(command))
        completed = subprocess.run(command, cwd=ROOT)
        if completed.returncode != 0:
            print(
                f"Stopped after run {index + 1} failed with exit code {completed.returncode}.",
                file=sys.stderr,
            )
            return completed.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
