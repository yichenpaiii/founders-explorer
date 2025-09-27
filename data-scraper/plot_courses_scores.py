"""Generate histograms for course aspect scores stored in the CSV output of
``compute_courses_scores.py``.

Run with ``python plot_course_scores.py`` to produce one ``.png`` per score column
under ``data/plots`` (created if missing).
"""

from __future__ import annotations

import os
from typing import Iterable, List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.style.use("seaborn-v0_8")  # pleasant defaults without extra deps
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "#f5f5f5",
    "axes.edgecolor": "#d8d8d8",
    "axes.titleweight": "bold",
})

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "courses_scores.csv")
OUTPUT_DIR = os.path.join(os.path.dirname(CSV_PATH), "plots")
SCORE_COLUMNS: List[str] = [
    "score_skills_cos",
    "score_skills_sigmoid",
    "score_product_cos",
    "score_product_sigmoid",
    "score_venture_cos",
    "score_venture_sigmoid",
    "score_foundations_cos",
    "score_foundations_sigmoid"
]
BINS = 40
BAR_COLOR = "#3C6997"
MEAN_COLOR = "#D45087"
MEDIAN_COLOR = "#2A9D8F"


def _ensure_columns(df: pd.DataFrame, columns: Iterable[str]) -> List[str]:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(f"Missing column(s) in CSV: {joined}")
    return list(columns)


def _plot_hist(series: pd.Series, title: str, out_path: str, bins: int) -> None:
    data = series.dropna().values.astype(float)
    if data.size == 0:
        print(f"[warn] Column '{series.name}' has no numeric data after dropping NaNs; skipping")
        return

    mean_val = float(np.mean(data))
    median_val = float(np.median(data))
    std_val = float(np.std(data))

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(data, bins=bins, color=BAR_COLOR, alpha=0.85, edgecolor="white")
    ax.axvline(mean_val, color=MEAN_COLOR, linewidth=2, linestyle="--", label=f"Mean: {mean_val:.3f}")
    ax.axvline(median_val, color=MEDIAN_COLOR, linewidth=2, linestyle="-.", label=f"Median: {median_val:.3f}")

    ax.set_title(title)
    ax.set_xlabel(series.name)
    ax.set_ylabel("Course count")

    stats_text = (
        f"n={data.size}\n"
        f"μ={mean_val:.3f}\n"
        f"σ={std_val:.3f}"
    )
    ax.text(
        0.98,
        0.95,
        stats_text,
        transform=ax.transAxes,
        va="top",
        ha="right",
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": "#cccccc", "alpha": 0.9},
    )

    ax.legend(loc="upper left", frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", which="major", labelsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"[ok] Saved plot -> {out_path}")
    plt.close(fig)


def main() -> None:
    csv_path = os.path.realpath(CSV_PATH)
    if not os.path.exists(csv_path):
        raise SystemExit(f"CSV file not found: {csv_path}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = pd.read_csv(csv_path)
    columns = _ensure_columns(df, SCORE_COLUMNS)

    for col in columns:
        out_path = os.path.join(OUTPUT_DIR, f"{col}.png")
        _plot_hist(df[col], title=f"Distribution of {col}", out_path=out_path, bins=BINS)


if __name__ == "__main__":
    main()
