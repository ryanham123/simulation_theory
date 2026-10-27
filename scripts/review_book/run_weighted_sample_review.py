#!/usr/bin/env python3
"""
Choose a weighted rating and useful persona, then post a test review.

Usage:
  python3 scripts/run_weighted_sample_review.py
  python3 scripts/run_weighted_sample_review.py --dry-run
  python3 scripts/run_weighted_sample_review.py --seed 42
"""
from __future__ import annotations

import argparse
import random
import subprocess
import sys
from pathlib import Path

from generate_sample_review import PERSONAS

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
TARGET_SCRIPT = SCRIPT_DIR / "generate_sample_review.py"
RATINGS = (5, 4, 3, 2, 1)
WEIGHTS = (60, 30, 5, 3, 2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed",
        type=int,
        help="Optional random seed for reproducible picks.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the chosen command without running it.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    rating = random.choices(RATINGS, weights=WEIGHTS, k=1)[0]
    persona = random.choice(tuple(PERSONAS))
    command = [
        sys.executable,
        str(TARGET_SCRIPT),
        "--rating",
        str(rating),
        "--persona",
        persona,
        "--post-test-review",
    ]

    print(f"Selected rating={rating}, persona={persona}")
    print("Running:", " ".join(command))

    if args.dry_run:
        return 0

    completed = subprocess.run(command, cwd=ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
