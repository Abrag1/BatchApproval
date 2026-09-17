"""
Statistical analysis for the ClearCheck Technologies approval-anomaly case:
threshold/skew diagnostics, one-sample t-tests against industry review-time
standards, the batch-approval ("block") defense, and the pre/post payout
two-sample t-test.

Run directly to print/save all results to outputs/analysis_summary.txt
and outputs/*.csv tables used by the report and dashboard.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
from scipy import stats

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
TECHNICIANS = ["Gary Arnold", "Juan Mendez", "Matt Shawn"]
STANDARDS_MIN = [10, 5, 2, 1]
THRESHOLDS_SEC = [2, 5, 10, 30, 60]


def load():
    df = pd.read_parquet(os.path.join(OUT_DIR, "approvals_clean.parquet"))
    blocks = pd.read_parquet(os.path.join(OUT_DIR, "blocks.parquet"))
    return df, blocks


# ---------------------------------------------------------------- Q1: distribution
def duration_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-technician descriptive stats, following the same convention used in the
    Patelco call-center case (mean/std/min/max/CV, plus a 95% t-distribution CI on
    the mean), extended with skew and speed-threshold shares for this case."""
    rows = []
    for tech, g in df.groupby("Technician"):
        d = g["duration_sec"].dropna()
        n = len(d)
        mean_sec, std_sec = d.mean(), d.std()
        # 95% CI for the mean via the t-distribution (same approach as Patelco.R)
        t_crit = stats.t.ppf(0.975, df=n - 1)
        margin = t_crit * std_sec / np.sqrt(n)
        rows.append(
            {
                "Technician": tech,
                "n_approvals": len(g),
                "n_with_duration": n,
                "mean_sec": mean_sec,
                "median_sec": d.median(),
                "std_sec": std_sec,
                "cv": std_sec / mean_sec,  # coefficient of variation
                "ci95_lower_sec": mean_sec - margin,
                "ci95_upper_sec": mean_sec + margin,
                "skew": stats.skew(d),
                "min_sec": d.min(),
                "p90_sec": d.quantile(0.90),
                "max_sec": d.max(),
                **{f"pct_under_{t}s": (d < t).mean() * 100 for t in THRESHOLDS_SEC},
                "pct_same_minute": (d < 60).mean() * 100,
                "pct_same_second": (d < 1).mean() * 100,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- Q2: one-sample t-tests
def one_sample_tests(df: pd.DataFrame) -> pd.DataFrame:
    """H0: mean review duration == standard (minutes). Alternative: less than
    (technicians are reviewing faster than the standard, i.e. failing it)."""
    rows = []
    for tech, g in df.groupby("Technician"):
        d = g["duration_sec"].dropna()
        for std_min in STANDARDS_MIN:
            std_sec = std_min * 60
            t_stat, p_two = stats.ttest_1samp(d, std_sec)
            # one-sided p-value for mean < standard
            p_one = p_two / 2 if t_stat < 0 else 1 - p_two / 2
            rows.append(
                {
                    "Technician": tech,
                    "standard_min": std_min,
                    "standard_sec": std_sec,
                    "sample_mean_sec": d.mean(),
                    "n": len(d),
                    "t_stat": t_stat,
                    "p_value_two_sided": p_two,
                    "p_value_one_sided_below": p_one,
                    "meets_standard": bool(d.mean() >= std_sec),
                    "significantly_below": bool(t_stat < 0 and p_one < 0.05),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- Q3: batch defense
def block_summary(blocks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for tech, g in blocks.groupby("Technician"):
        multi = g[g["cases_in_block"] > 1]
        rows.append(
            {
                "Technician": tech,
                "n_blocks": len(g),
                "n_single_case_blocks": int((g["cases_in_block"] == 1).sum()),
                "n_multi_case_blocks": len(multi),
                "avg_cases_per_block": g["cases_in_block"].mean(),
                "median_cases_per_block": g["cases_in_block"].median(),
                "max_cases_per_block": g["cases_in_block"].max(),
                "avg_sec_per_case_in_block": multi["avg_duration_sec"].mean(),
                "median_sec_per_case_in_block": multi["avg_duration_sec"].median(),
                "pct_blocks_under_2s_per_case": (multi["avg_duration_sec"] < 2).mean() * 100,
                "pct_blocks_under_5s_per_case": (multi["avg_duration_sec"] < 5).mean() * 100,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- Q4: payout change
def payout_change_tests(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for tech, g in df.groupby("Technician"):
        pre = g.loc[g["period"] == "Pre-change ($50)", "duration_sec"].dropna()
        post = g.loc[g["period"] == "Post-change ($17)", "duration_sec"].dropna()
        has_both = len(pre) > 1 and len(post) > 1
        if has_both:
            t_stat, p_val = stats.ttest_ind(pre, post, equal_var=False)
            # Robustness check: Mann-Whitney U is distribution-free and far less
            # sensitive to the extreme right-skew (skew ~130-160) in these gaps
            # than a mean-based t-test, whose variance estimate is dominated by
            # a handful of multi-day off-shift gaps.
            u_stat, u_p = stats.mannwhitneyu(pre, post, alternative="two-sided")
        else:
            t_stat, p_val, u_stat, u_p = np.nan, np.nan, np.nan, np.nan
        rows.append(
            {
                "Technician": tech,
                "n_pre": len(pre),
                "n_post": len(post),
                "mean_pre_sec": pre.mean() if len(pre) else np.nan,
                "mean_post_sec": post.mean() if len(post) else np.nan,
                "median_pre_sec": pre.median() if len(pre) else np.nan,
                "median_post_sec": post.median() if len(post) else np.nan,
                "has_both_periods": has_both,
                "t_stat": t_stat,
                "p_value": p_val,
                "significant_change_ttest": bool(has_both and p_val < 0.05),
                "mannwhitney_u": u_stat,
                "mannwhitney_p": u_p,
                "significant_change_mannwhitney": bool(has_both and u_p < 0.05),
            }
        )
    return pd.DataFrame(rows)


def main():
    df, blocks = load()

    dur = duration_summary(df)
    ost = one_sample_tests(df)
    blk = block_summary(blocks)
    pay = payout_change_tests(df)

    dur.to_csv(os.path.join(OUT_DIR, "duration_summary.csv"), index=False)
    ost.to_csv(os.path.join(OUT_DIR, "one_sample_tests.csv"), index=False)
    blk.to_csv(os.path.join(OUT_DIR, "block_summary.csv"), index=False)
    pay.to_csv(os.path.join(OUT_DIR, "payout_change_tests.csv"), index=False)

    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print("\n=== DURATION SUMMARY ===")
        print(dur.to_string(index=False))
        print("\n=== ONE-SAMPLE T-TESTS vs INDUSTRY STANDARDS ===")
        print(ost.to_string(index=False))
        print("\n=== BLOCK (BATCH-APPROVAL) SUMMARY ===")
        print(blk.to_string(index=False))
        print("\n=== PAYOUT CHANGE TWO-SAMPLE T-TESTS ===")
        print(pay.to_string(index=False))


if __name__ == "__main__":
    main()
