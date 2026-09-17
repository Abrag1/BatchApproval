"""Generate static PNG charts for the written report (outputs/charts/)."""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
CHART_DIR = os.path.join(OUT_DIR, "charts")
TECHNICIANS = ["Gary Arnold", "Juan Mendez", "Matt Shawn"]
COLORS = {"Gary Arnold": "#2563eb", "Juan Mendez": "#dc2626", "Matt Shawn": "#16a34a"}
THRESHOLDS_SEC = [2, 5, 10, 30, 60]

plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white", "font.size": 10})

# Human-readable tick marks for the log-scaled duration axes, so a non-technical
# reader never has to interpret a raw "log10(seconds)" number.
_TIME_TICKS_SEC = [1, 2, 5, 10, 30, 60, 300, 3600]
_TIME_TICKS_LABEL = ["1 sec", "2 sec", "5 sec", "10 sec", "30 sec", "1 min", "5 min", "1 hr"]


def human_time_axis(ax, max_sec=None, compact=False):
    """Replace a log10(seconds) x-axis with plain-English time labels.

    compact=True uses a sparser tick set (for narrow multi-panel subplots,
    where the full tick set overlaps and becomes unreadable)."""
    ticks_sec = _TIME_TICKS_SEC if max_sec is None else [t for t in _TIME_TICKS_SEC if t <= max_sec * 1.05]
    labels = _TIME_TICKS_LABEL[: len(ticks_sec)]
    if compact:
        keep = {"1 sec", "10 sec", "1 min", "5 min", "1 hr"}
        ticks_sec, labels = zip(*[(t, l) for t, l in zip(ticks_sec, labels) if l in keep])
    ax.set_xticks(np.log10(ticks_sec))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_xlabel("Time since previous approval")


def savefig(fig, name):
    os.makedirs(CHART_DIR, exist_ok=True)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, name), dpi=150)
    plt.close(fig)


def main():
    df = pd.read_parquet(os.path.join(OUT_DIR, "approvals_clean.parquet"))
    blocks = pd.read_parquet(os.path.join(OUT_DIR, "blocks.parquet"))

    # 1. Histogram of duration per technician (log-scaled x-axis, plain-English ticks)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
    for ax, tech in zip(axes, TECHNICIANS):
        d = df.loc[(df["Technician"] == tech) & df["duration_sec"].notna(), "duration_sec"]
        d = d[d > 0]
        ax.hist(np.log10(d), bins=60, color=COLORS[tech], alpha=0.85)
        for thresh in [2, 10, 60]:
            ax.axvline(np.log10(thresh), color="black", ls="--", lw=0.8, alpha=0.6)
        ax.set_title(tech)
        human_time_axis(ax, compact=True)
    axes[0].set_ylabel("Number of approvals")
    fig.suptitle(
        "How much time passed before each approval?\n"
        "(dashed lines mark 2 sec, 10 sec, and 1 min -- most approvals fall to the left of them)"
    )
    savefig(fig, "01_duration_histograms_log.png")

    # 2. Fast-approval ratio by threshold, per technician
    fig, ax = plt.subplots(figsize=(7, 4.2))
    x = np.arange(len(THRESHOLDS_SEC))
    width = 0.25
    for i, tech in enumerate(TECHNICIANS):
        d = df.loc[df["Technician"] == tech, "duration_sec"].dropna()
        pct = [(d < t).mean() * 100 for t in THRESHOLDS_SEC]
        ax.bar(x + (i - 1) * width, pct, width, label=tech, color=COLORS[tech])
    ax.set_xticks(x)
    ax.set_xticklabels([f"< {t}s" for t in THRESHOLDS_SEC])
    ax.set_ylabel("% of approvals")
    ax.set_title("Share of approvals under each speed threshold")
    ax.legend()
    savefig(fig, "02_fast_approval_thresholds.png")

    # 3. How many cases get bundled into one batch-review session ("block")
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for tech in TECHNICIANS:
        b = blocks.loc[blocks["Technician"] == tech, "cases_in_block"]
        ax.hist(b, bins=40, alpha=0.5, label=f"{tech} (median {b.median():.0f} cases/session)", color=COLORS[tech])
    ax.set_xlabel("Cases approved in one session (a \"block\")")
    ax.set_ylabel("Number of sessions")
    ax.set_title("Batch size: how many cases get reviewed together in one sitting?")
    ax.legend()
    savefig(fig, "03_cases_per_block.png")

    # 4. How quickly are results ENTERED once a batch review session is under way
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for tech in TECHNICIANS:
        b = blocks.loc[
            (blocks["Technician"] == tech) & (blocks["cases_in_block"] > 1), "avg_duration_sec"
        ].dropna()
        ax.hist(np.clip(b, 0, 300), bins=40, alpha=0.5, label=tech, color=COLORS[tech])
    ax.axvline(120, color="black", ls="--", lw=1, label="2-min industry standard")
    ax.set_xlabel("Seconds between approval clicks, once inside a batch session (clipped at 300s)")
    ax.set_ylabel("Number of sessions")
    ax.set_title("Data-entry speed once a batch is being approved\n(this is entry speed, not proof of how long the earlier review took)")
    ax.legend()
    savefig(fig, "04_sec_per_case_in_block.png")

    # 5. Approvals by hour of day
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6), sharey=True)
    for ax, tech in zip(axes, TECHNICIANS):
        g = df.loc[df["Technician"] == tech]
        g["hour"].value_counts().sort_index().plot(kind="bar", ax=ax, color=COLORS[tech])
        ax.set_title(tech)
        ax.set_xlabel("Hour of day")
    axes[0].set_ylabel("Approvals")
    fig.suptitle("Approval volume by hour of day")
    savefig(fig, "05_hourly_volume.png")

    # 6. Top approval days
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
    for ax, tech in zip(axes, TECHNICIANS):
        g = df.loc[df["Technician"] == tech]
        top = g.groupby("date").size().sort_values(ascending=False).head(10)
        ax.barh([str(d) for d in top.index][::-1], top.values[::-1], color=COLORS[tech])
        ax.set_title(tech)
        ax.set_xlabel("Approvals that day")
    fig.suptitle("Top 10 highest-volume approval days")
    savefig(fig, "06_top_days.png")

    # 7. Pre vs post payout-change duration (Arnold only, since only he has both periods)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    g = df.loc[(df["Technician"] == "Gary Arnold") & df["duration_sec"].notna()]
    for period, color in [("Pre-change ($50)", "#94a3b8"), ("Post-change ($17)", "#2563eb")]:
        d = g.loc[g["period"] == period, "duration_sec"]
        d = d[(d > 0) & (d < 3600)]
        ax.hist(np.log10(d), bins=50, alpha=0.55, label=f"{period} (n={len(d):,})", color=color, density=True)
    human_time_axis(ax, max_sec=3600)
    ax.set_ylabel("Share of approvals (density)")
    ax.set_title("Gary Arnold: time between approvals, before vs. after the June 2020 payout cut")
    ax.legend()
    savefig(fig, "07_payout_change_arnold.png")

    print("Charts written to", CHART_DIR)


if __name__ == "__main__":
    main()
