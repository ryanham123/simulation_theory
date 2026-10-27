#!/usr/bin/env python3
"""
Plot the "before" overall scores from book_scores.json.

Usage:
  python3 scripts/plot_after_scores.py
  python3 scripts/plot_after_scores.py --input book_scores.json --output after_scores.png
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Matplotlib wants a writable config/cache directory in this environment.
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "simulation_theory_book_mpl"),
)
os.environ.setdefault(
    "XDG_CACHE_HOME",
    str(Path(tempfile.gettempdir()) / "simulation_theory_book_cache"),
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot the before overall scores for each entry in book_scores.json."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "book_scores.json",
        help="Path to the JSON score history file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "after_scores.png",
        help="Path to the output image file.",
    )
    return parser.parse_args()


def load_before_scores(path: Path) -> list[int]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Score file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc

    if isinstance(raw, dict):
        entries = [raw]
    elif isinstance(raw, list):
        entries = raw
    else:
        raise SystemExit(f"Expected a JSON object or array in {path}")

    scores: list[int] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise SystemExit(f"Entry {index} is not a JSON object.")

        before = entry.get("before")
        if not isinstance(before, dict):
            raise SystemExit(f'Entry {index} is missing a "before" object.')

        score = before.get("overall_score")
        if not isinstance(score, int):
            raise SystemExit(f'Entry {index} has a non-integer "before.overall_score".')

        scores.append(score)

    if not scores:
        raise SystemExit(f"No valid before scores found in {path}")

    return scores


def plot_scores(scores: list[int], output_path: Path) -> None:
    x_values = list(range(1, len(scores) + 1))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(x_values, scores, marker="o", linewidth=2.5, color="#1f77b4")
    ax.set_title("Before Overall Scores by Entry")
    ax.set_xlabel("Entry")
    ax.set_ylabel("Before Overall Score")
    ax.set_xticks(x_values)
    ax.set_ylim(min(scores) - 20, max(scores) + 20)
    ax.grid(True, linestyle="--", alpha=0.35)

    for x_value, score in zip(x_values, scores):
        ax.annotate(
            str(score),
            (x_value, score),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
        )

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    scores = load_before_scores(args.input.resolve())
    plot_scores(scores, args.output.resolve())
    print(f"Wrote plot to {args.output.resolve()}")


if __name__ == "__main__":
    main()
