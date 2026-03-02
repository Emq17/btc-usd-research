from __future__ import annotations

from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def save_strategy_charts(events_df: pd.DataFrame, outdir: Path) -> List[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []

    if events_df.empty:
        return paths

    data = events_df.sort_values("period_end").copy()
    if "point" not in data.columns:
        data["point"] = np.where(data["win"].astype(int) == 1, 1, -1)
    if "signal_index" not in data.columns:
        data["signal_index"] = np.arange(1, len(data) + 1)
    if "cumulative_points" not in data.columns:
        data["cumulative_points"] = data["point"].cumsum()
    if "cumulative_win_rate" not in data.columns:
        data["cumulative_win_rate"] = data["point"].cumsum() / data["signal_index"]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(data["period_end"], data["cumulative_points"], color="#1f77b4", linewidth=2)
    ax.set_title("Cumulative Points Over Time (Win=+1, Loss=-1)")
    ax.set_ylabel("Cumulative Points")
    ax.set_xlabel("Date")
    ax.grid(alpha=0.25)
    p1 = outdir / "cumulative_points.png"
    fig.tight_layout()
    fig.savefig(p1, dpi=150)
    plt.close(fig)
    paths.append(p1)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(data["period_end"], data["cumulative_win_rate"], color="#2ca02c", linewidth=2)
    ax.set_title("Cumulative Win Rate Over Time")
    ax.set_ylabel("Win Rate")
    ax.set_xlabel("Date")
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.25)
    p2 = outdir / "cumulative_win_rate.png"
    fig.tight_layout()
    fig.savefig(p2, dpi=150)
    plt.close(fig)
    paths.append(p2)

    reason_counts = (
        data.assign(reason=lambda d: np.where(d["invalidated_counter_breakout"], d["invalid_reason"], "valid_signal"))
        .groupby("reason", as_index=False)
        .size()
        .sort_values("size", ascending=False)
    )
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(reason_counts["reason"], reason_counts["size"], color="#ff7f0e")
    ax.set_title("Signal/Invalidation Counts")
    ax.set_ylabel("Count")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(alpha=0.2, axis="y")
    p3 = outdir / "signal_invalidation_counts.png"
    fig.tight_layout()
    fig.savefig(p3, dpi=150)
    plt.close(fig)
    paths.append(p3)

    return paths
