"""
Data loading and feature engineering for the ClearCheck Technologies
approval-anomaly case.

Reads every per-technician Excel export in data/, normalizes the
inconsistent column names/types across files, derives review durations
(gap between consecutive approvals by the same technician), flags
review "blocks" (batch-approval sessions), and tags the pre/post payout
period (payout dropped from $50 to $17 on 2020-06-01).

Run directly to regenerate outputs/approvals_clean.parquet and
outputs/blocks.parquet, which the Streamlit dashboard reads.
"""

from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")

PAYOUT_CHANGE_DATE = pd.Timestamp("2020-06-01")
BLOCK_GAP_MINUTES = 10  # a new block starts when the gap to the previous approval >= this

# Canonical name for each technician, keyed off filename prefix
TECH_MAP = {
    "arnold": "Gary Arnold",
    "mendez": "Juan Mendez",
    "shawn": "Matt Shawn",
}

COLUMN_ALIASES = {
    "case_number": "CASE_NUMBER",
    "case number": "CASE_NUMBER",
    "casenumber": "CASE_NUMBER",
    "provider_approving_name": "TECHNICIAN_RAW",
    "provider approving name": "TECHNICIAN_RAW",
    "approval_date": "APPROVAL_DATE",
    "most recent approval date (cst)": "APPROVAL_DATE",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for c in df.columns:
        key = c.strip().lower()
        if key in COLUMN_ALIASES:
            rename[c] = COLUMN_ALIASES[key]
    return df.rename(columns=rename)


def load_raw() -> pd.DataFrame:
    """Load and concatenate every technician Excel file into one long table."""
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.xlsx")))
    if not files:
        raise FileNotFoundError(f"No .xlsx files found in {DATA_DIR}")

    frames = []
    for f in files:
        df = pd.read_excel(f)
        df = _normalize_columns(df)
        fname = os.path.basename(f).lower()
        tech = next((v for k, v in TECH_MAP.items() if k in fname), None)
        if tech is None:
            raise ValueError(f"Could not infer technician from filename: {f}")
        df["Technician"] = tech
        df["source_file"] = os.path.basename(f)
        frames.append(df[["CASE_NUMBER", "APPROVAL_DATE", "Technician", "source_file"]])

    raw = pd.concat(frames, ignore_index=True)
    raw["APPROVAL_DATE"] = pd.to_datetime(raw["APPROVAL_DATE"], errors="coerce")
    return raw


def build_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Clean, dedupe, sort, and derive per-approval features."""
    df = raw.dropna(subset=["APPROVAL_DATE", "CASE_NUMBER"]).copy()
    df["CASE_NUMBER"] = df["CASE_NUMBER"].astype(str)
    df = df.drop_duplicates(subset=["CASE_NUMBER", "Technician", "APPROVAL_DATE"])
    df = df.sort_values(["Technician", "APPROVAL_DATE"]).reset_index(drop=True)

    # Duration = gap to the PREVIOUS approval by the same technician (seconds).
    # First approval per technician has no prior case -> NaN duration (excluded from stats).
    df["prev_approval"] = df.groupby("Technician")["APPROVAL_DATE"].shift(1)
    df["duration_sec"] = (df["APPROVAL_DATE"] - df["prev_approval"]).dt.total_seconds()

    df["date"] = df["APPROVAL_DATE"].dt.date
    df["hour"] = df["APPROVAL_DATE"].dt.hour
    df["weekday"] = df["APPROVAL_DATE"].dt.day_name()
    df["month"] = df["APPROVAL_DATE"].dt.to_period("M").astype(str)
    df["period"] = np.where(
        df["APPROVAL_DATE"] < PAYOUT_CHANGE_DATE, "Pre-change ($50)", "Post-change ($17)"
    )

    # A new block starts at the first approval of a technician, or whenever the
    # gap to the previous approval is >= BLOCK_GAP_MINUTES (i.e. NOT a rapid follow-on).
    is_new_block = df["duration_sec"].isna() | (df["duration_sec"] >= BLOCK_GAP_MINUTES * 60)
    df["block_id"] = is_new_block.groupby(df["Technician"]).cumsum()
    df["block_key"] = df["Technician"] + "_" + df["block_id"].astype(str)
    # Within-block gap: only defined for a case that continues its block (< 10 min
    # after the previous case). The block's first case has no within-block gap --
    # its duration_sec instead reflects the (often much longer) gap since the PRIOR
    # session and must be excluded from "time spent per case inside a block".
    df["within_block_gap_sec"] = np.where(is_new_block, np.nan, df["duration_sec"])

    for thresh in (2, 5, 10, 30, 60):
        df[f"under_{thresh}s"] = df["duration_sec"] < thresh

    return df


def build_blocks(df: pd.DataFrame) -> pd.DataFrame:
    """Summarize each review block (batch-approval session)."""
    valid = df.copy()
    g = valid.groupby(["Technician", "block_key"], as_index=False)
    blocks = g.agg(
        block_start=("APPROVAL_DATE", "min"),
        block_end=("APPROVAL_DATE", "max"),
        cases_in_block=("CASE_NUMBER", "count"),
        avg_duration_sec=("within_block_gap_sec", "mean"),
        median_duration_sec=("within_block_gap_sec", "median"),
        period=("period", "first"),
    )
    blocks["block_span_sec"] = (
        blocks["block_end"] - blocks["block_start"]
    ).dt.total_seconds()
    # Effective seconds spent per case reviewing, over the whole block span
    blocks["sec_per_case_span"] = np.where(
        blocks["cases_in_block"] > 1,
        blocks["block_span_sec"] / (blocks["cases_in_block"] - 1),
        np.nan,
    )
    blocks["date"] = blocks["block_start"].dt.date
    return blocks.sort_values(["Technician", "block_start"]).reset_index(drop=True)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    raw = load_raw()
    df = build_features(raw)
    blocks = build_blocks(df)

    df.to_parquet(os.path.join(OUT_DIR, "approvals_clean.parquet"), index=False)
    blocks.to_parquet(os.path.join(OUT_DIR, "blocks.parquet"), index=False)
    df.to_csv(os.path.join(OUT_DIR, "approvals_clean.csv"), index=False)
    blocks.to_csv(os.path.join(OUT_DIR, "blocks.csv"), index=False)

    print(f"Approvals: {len(df):,} rows across {df['Technician'].nunique()} technicians")
    print(f"Date range: {df['APPROVAL_DATE'].min()} -> {df['APPROVAL_DATE'].max()}")
    print(f"Blocks: {len(blocks):,}")
    print(df.groupby("Technician")["duration_sec"].describe())


if __name__ == "__main__":
    main()
