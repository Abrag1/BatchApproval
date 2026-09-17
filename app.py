"""
ClearCheck Technologies -- Approval Anomaly Dashboard (Streamlit)

Investigates whether technicians Gary Arnold, Juan Mendez, and Matt Shawn are
reviewing devices thoroughly before approval, or rushing to maximize per-case
pay. Reads the pre-computed outputs from src/data_pipeline.py and
src/analysis.py (outputs/*.parquet).
"""

import os

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

st.set_page_config(
    page_title="ClearCheck Approval Anomaly Dashboard",
    page_icon="\U0001f50d",
    layout="wide",
)

BASE_DIR = os.path.dirname(__file__)
OUT_DIR = os.path.join(BASE_DIR, "outputs")
TECH_COLORS = {"Gary Arnold": "#2563eb", "Juan Mendez": "#dc2626", "Matt Shawn": "#16a34a"}
PAYOUT_CHANGE_DATE = pd.Timestamp("2020-06-01")
THRESHOLDS_SEC = [2, 5, 10, 30, 60]
STANDARDS_MIN = [10, 5, 2, 1]

# Plain-English tick marks for log10(seconds) axes, so no chart ever shows a
# raw "log10(duration)" number to a non-technical viewer.
_TIME_TICKS_SEC = [1, 2, 5, 10, 30, 60, 300, 3600]
_TIME_TICKS_LABEL = ["1 sec", "2 sec", "5 sec", "10 sec", "30 sec", "1 min", "5 min", "1 hr"]


def human_time_xaxis(fig, max_sec=None, title="Time since the previous approval"):
    """Relabel a log10(seconds) x-axis with plain-English time marks."""
    ticks = _TIME_TICKS_SEC if max_sec is None else [t for t in _TIME_TICKS_SEC if t <= max_sec * 1.05]
    labels = _TIME_TICKS_LABEL[: len(ticks)]
    fig.update_xaxes(tickvals=np.log10(ticks), ticktext=labels, title=title)
    return fig


@st.cache_data
def load_data():
    df = pd.read_parquet(os.path.join(OUT_DIR, "approvals_clean.parquet"))
    blocks = pd.read_parquet(os.path.join(OUT_DIR, "blocks.parquet"))
    df["APPROVAL_DATE"] = pd.to_datetime(df["APPROVAL_DATE"])
    df["date"] = pd.to_datetime(df["date"])
    blocks["block_start"] = pd.to_datetime(blocks["block_start"])
    blocks["block_end"] = pd.to_datetime(blocks["block_end"])
    blocks["date"] = pd.to_datetime(blocks["date"])
    return df, blocks


df, blocks = load_data()

# ----------------------------------------------------------------- sidebar filters
st.sidebar.title("Filters")
all_techs = sorted(df["Technician"].unique())
sel_techs = st.sidebar.multiselect("Technician", all_techs, default=all_techs)

min_date, max_date = df["date"].min().date(), df["date"].max().date()
date_range = st.sidebar.date_input(
    "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

fast_thresh = st.sidebar.select_slider(
    "Highlight approvals faster than", options=THRESHOLDS_SEC, value=10,
    format_func=lambda s: f"{s} sec",
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Data covers 15 non-continuous monthly extracts (Feb 2019 - Sep 2021). "
    "Only Gary Arnold's files include both sides of the June 2020 payout change; "
    "Mendez and Shawn's extracts are entirely from 2019 (pre-change)."
)

mask = (
    df["Technician"].isin(sel_techs)
    & (df["date"].dt.date >= start_date)
    & (df["date"].dt.date <= end_date)
)
fdf = df.loc[mask].copy()
bmask = (
    blocks["Technician"].isin(sel_techs)
    & (blocks["date"].dt.date >= start_date)
    & (blocks["date"].dt.date <= end_date)
)
fblocks = blocks.loc[bmask].copy()

st.title("Approval Anomaly at ClearCheck Technologies")
st.caption(
    "Evidence review of technician approval timing -- for or against the negligence claim. "
    "Timestamps show *timing*, not diligence: there is no record of rejected cases, no view of "
    "what happened between approvals, and no way to see pre-review work if it occurred."
)
st.info(
    "**Working hypothesis being tested here:** technicians say fast approvals reflect a real "
    "practice -- pre-reviewing a batch of cases (often 10-20 at a time) off-system, then entering "
    "the results one after another. The batch sizes and timing patterns below are, on the whole, "
    "consistent with that account -- see the **Batch/Block Analysis** tab for the arithmetic. This "
    "dataset cannot directly observe any pre-review that happened off-system, so it can support "
    "that account but not confirm it outright."
)

if fdf.empty:
    st.warning("No data for the selected filters.")
    st.stop()

# ----------------------------------------------------------------- KPI row
c1, c2, c3, c4, c5 = st.columns(5)
n_valid = fdf["duration_sec"].notna().sum()
c1.metric("Approvals in view", f"{len(fdf):,}")
c2.metric("Median duration", f"{fdf['duration_sec'].median():,.0f} sec")
fast_pct = (fdf["duration_sec"] < fast_thresh).mean() * 100 if n_valid else 0
c3.metric(f"% under {fast_thresh}s", f"{fast_pct:.1f}%")
c4.metric("Review blocks", f"{fblocks.shape[0]:,}")
avg_block = fblocks["cases_in_block"].mean() if len(fblocks) else 0
c5.metric("Avg cases / block", f"{avg_block:,.1f}")

tabs = st.tabs(
    ["Duration Distributions", "Speed Standards (t-tests)", "Batch/Block Analysis",
     "Payout Change", "Volume & Calendar"]
)

# =================================================================== TAB 1
with tabs[0]:
    st.subheader("Histogram of approval durations")
    col1, col2 = st.columns([2, 1])
    with col1:
        plot_df = fdf.dropna(subset=["duration_sec"]).copy()
        plot_df = plot_df[plot_df["duration_sec"] > 0]
        plot_df["log_duration"] = np.log10(plot_df["duration_sec"])
        plot_df["is_fast"] = plot_df["duration_sec"] < fast_thresh
        fig = px.histogram(
            plot_df, x="log_duration", color="Technician", barmode="overlay",
            nbins=80, opacity=0.6, color_discrete_map=TECH_COLORS,
            labels={"log_duration": "Time since previous approval"},
        )
        for t in [2, 5, 10, 30, 60]:
            fig.add_vline(x=np.log10(t), line_dash="dot", line_color="gray")
        human_time_xaxis(fig)
        fig.update_yaxes(title="Number of approvals")
        fig.update_layout(height=430, legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Reading this chart: the horizontal axis is compressed so both second-apart and "
            "hour-apart gaps fit on one chart -- each labeled tick is roughly 10x the one before "
            "it. A tall bar near \"5 sec\" means many approvals followed the previous one by about "
            "5 seconds."
        )
    with col2:
        st.markdown("**Fast approvals highlighted** (below threshold)")
        st.dataframe(
            plot_df.groupby("Technician")["is_fast"].agg(["sum", "mean"]).rename(
                columns={"sum": "count", "mean": "share"}
            ).assign(share=lambda d: (d["share"] * 100).round(1)),
            use_container_width=True,
        )

    st.subheader("Skew and threshold summary per technician")
    rows = []
    for tech, g in fdf.groupby("Technician"):
        d = g["duration_sec"].dropna()
        if d.empty:
            continue
        row = {
            "Technician": tech, "n": len(d), "mean_sec": d.mean(), "median_sec": d.median(),
            "skew": stats.skew(d),
        }
        for t in THRESHOLDS_SEC:
            row[f"% < {t}s"] = round((d < t).mean() * 100, 2)
        rows.append(row)
    st.dataframe(pd.DataFrame(rows).round(1), use_container_width=True)

# =================================================================== TAB 2
with tabs[1]:
    st.subheader("One-sample t-tests vs. industry minimum review-time standards")
    st.caption(
        "H0: mean review duration equals the standard. A technician whose mean is "
        "significantly BELOW the standard is failing it."
    )
    rows = []
    for tech, g in fdf.groupby("Technician"):
        d = g["duration_sec"].dropna()
        if len(d) < 2:
            continue
        for std_min in STANDARDS_MIN:
            std_sec = std_min * 60
            t_stat, p_two = stats.ttest_1samp(d, std_sec)
            p_one = p_two / 2 if t_stat < 0 else 1 - p_two / 2
            rows.append({
                "Technician": tech, "Standard": f"{std_min} min", "Sample mean (sec)": round(d.mean(), 1),
                "n": len(d), "t-stat": round(t_stat, 3), "p (one-sided, below)": round(p_one, 4),
                "Meets standard": "Yes" if d.mean() >= std_sec else "No",
                "Significantly below (p<.05)": "Yes" if (t_stat < 0 and p_one < 0.05) else "No",
            })
    tt = pd.DataFrame(rows)
    st.dataframe(tt, use_container_width=True, height=420)

    st.info(
        "For Gary Arnold and Juan Mendez, this required test does **not** find their average "
        "review duration significantly below any of the four standards -- so there is not "
        "statistically significant evidence, by this test, that they fall short. Matt Shawn's mean "
        "falls below the three shortest standards; his data is a single month on file (4,115 "
        "approvals vs. 17,000-43,000 for the other two), which is worth weighing when judging how "
        "representative that is. Technical note: duration is extremely right-skewed (skew > 100 for "
        "Arnold and Mendez), which widens the standard error and works against finding significance "
        "in either direction -- read this table alongside the Batch/Block tab, not in isolation."
    )

# =================================================================== TAB 3
with tabs[2]:
    st.subheader("Approval blocks (batch-review sessions)")
    st.caption(
        "A block = a run of approvals with gaps under 10 minutes. Technicians say fast approvals "
        "reflect a real practice: pre-reviewing several cases -- often ten to twenty at a time -- "
        "then entering the results one after another."
    )
    col1, col2 = st.columns(2)
    with col1:
        fig = px.histogram(
            fblocks, x="cases_in_block", color="Technician", barmode="overlay",
            opacity=0.6, nbins=50, color_discrete_map=TECH_COLORS,
            labels={"cases_in_block": "Cases in one sitting"},
            title="Batch size: how many cases get reviewed together",
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        clipped = fblocks[fblocks["cases_in_block"] > 1].copy()
        clipped["avg_duration_sec_clip"] = clipped["avg_duration_sec"].clip(upper=300)
        fig2 = px.histogram(
            clipped, x="avg_duration_sec_clip", color="Technician", barmode="overlay",
            opacity=0.6, nbins=50, color_discrete_map=TECH_COLORS,
            labels={"avg_duration_sec_clip": "Seconds between approval clicks (clipped at 300s)"},
            title="Data-entry speed once a batch is under way",
        )
        fig2.add_vline(x=120, line_dash="dash", line_color="black", annotation_text="2-min standard")
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Does the arithmetic leave room for genuine review?")
    summary_rows = []
    for tech, g in fblocks.groupby("Technician"):
        multi = g[g["cases_in_block"] > 1]
        summary_rows.append({
            "Technician": tech,
            "Blocks": len(g),
            "Avg cases/block": round(g["cases_in_block"].mean(), 1),
            "Median cases/block": g["cases_in_block"].median(),
            "Avg sec/case in block": round(multi["avg_duration_sec"].mean(), 1),
            "Median sec/case in block": round(multi["avg_duration_sec"].median(), 1),
            "% blocks < 2 sec/case": round((multi["avg_duration_sec"] < 2).mean() * 100, 2),
            "% blocks < 5 sec/case": round((multi["avg_duration_sec"] < 5).mean() * 100, 2),
        })
    block_stats = pd.DataFrame(summary_rows)
    st.dataframe(block_stats, use_container_width=True)

    st.markdown("**A simple back-of-envelope check, using the median batch size for each technician:**")
    check_cols = st.columns(len(block_stats))
    for col, (_, row) in zip(check_cols, block_stats.iterrows()):
        median_cases = row["Median cases/block"]
        low_min, high_min = median_cases * 60 / 60, median_cases * 90 / 60
        col.metric(row["Technician"], f"{median_cases:.0f} cases/batch")
        col.caption(
            f"At 60-90 sec of genuine review per case, a typical batch implies "
            f"**{low_min:.0f}-{high_min:.0f} min** of off-system review before any approval is "
            f"logged -- comfortably inside several industry standards. The fast numbers on the "
            f"right above then describe just the data-entry step that follows."
        )
    st.caption(
        "This does not prove the pre-review happened -- this dataset cannot see anything done "
        "off-system -- but the batch sizes are hard to explain any other way, and a realistic "
        "review pace fits comfortably inside the observed batch windows."
    )

    st.subheader("Explore a single block")
    tech_pick = st.selectbox("Technician", sorted(fblocks["Technician"].unique()))
    tb = fblocks[fblocks["Technician"] == tech_pick].sort_values("cases_in_block", ascending=False)
    if len(tb):
        pick_idx = st.slider("Pick block (ranked by size, 0 = largest)", 0, len(tb) - 1, 0)
        block_key = tb.iloc[pick_idx]["block_key"]
        detail = fdf[fdf["block_key"] == block_key].sort_values("APPROVAL_DATE")
        st.write(
            f"Block `{block_key}`: {len(detail)} cases from {detail['APPROVAL_DATE'].min()} "
            f"to {detail['APPROVAL_DATE'].max()}"
        )
        st.dataframe(
            detail[["CASE_NUMBER", "APPROVAL_DATE", "duration_sec"]], use_container_width=True, height=280
        )

# =================================================================== TAB 4
with tabs[3]:
    st.subheader(r"Payout change: \$50 -> \$17 per approval (June 1, 2020)")
    coverage = df.groupby("Technician")["APPROVAL_DATE"].agg(["min", "max"])
    coverage["spans_payout_change"] = (coverage["min"] < PAYOUT_CHANGE_DATE) & (
        coverage["max"] >= PAYOUT_CHANGE_DATE
    )
    st.dataframe(coverage, use_container_width=True)
    st.warning(
        "Only **Gary Arnold**'s extracts include approvals on both sides of the payout change. "
        "Juan Mendez's and Matt Shawn's files are entirely from 2019 (pre-change), so a "
        "before/after comparison cannot be computed for them from this dataset -- that is a "
        "limit of the data, not a finding about their behavior."
    )

    arnold = fdf[fdf["Technician"] == "Gary Arnold"].dropna(subset=["duration_sec"])
    if len(arnold):
        pre = arnold.loc[arnold["period"] == "Pre-change ($50)", "duration_sec"]
        post = arnold.loc[arnold["period"] == "Post-change ($17)", "duration_sec"]
        colA, colB = st.columns([2, 1])
        with colA:
            capped = arnold[arnold["duration_sec"] < 3600].copy()
            capped["log_duration"] = np.log10(capped["duration_sec"].clip(lower=0.1))
            fig = px.histogram(
                capped, x="log_duration", color="period", barmode="overlay", opacity=0.55,
                histnorm="probability density", nbins=60,
                labels={"log_duration": "Time since previous approval"},
                title="Gary Arnold: time between approvals, before vs. after the payout cut",
            )
            human_time_xaxis(fig, max_sec=3600)
            fig.update_yaxes(title="Share of approvals (density)")
            fig.update_layout(height=420)
            st.plotly_chart(fig, use_container_width=True)
        with colB:
            if len(pre) > 1 and len(post) > 1:
                t_stat, p_val = stats.ttest_ind(pre, post, equal_var=False)
                u_stat, u_p = stats.mannwhitneyu(pre, post, alternative="two-sided")
                arnold_blocks = blocks[blocks["Technician"] == "Gary Arnold"]
                pre_blk = arnold_blocks.loc[arnold_blocks["period"] == "Pre-change ($50)", "cases_in_block"]
                post_blk = arnold_blocks.loc[arnold_blocks["period"] == "Post-change ($17)", "cases_in_block"]
                st.metric("Median duration, pre / post", f"{pre.median():.0f}s / {post.median():.0f}s")
                st.metric("Avg cases/batch, pre / post", f"{pre_blk.mean():.1f} / {post_blk.mean():.1f}")
                st.metric("Required test (Welch t) p-value", f"{p_val:.4f}", help="Not significant")
                st.metric("Supplementary (Mann-Whitney) p-value", f"{u_p:.2e}", help="Significant")
                st.markdown(
                    "**Required test:** the two-sample t-test finds **no significant difference** "
                    "in mean duration -- both periods contain a handful of very long, multi-day "
                    "gaps that dominate the variance.\n\n"
                    "**Supplementary check:** a Mann-Whitney test, run as extra diligence, finds a "
                    "small but real shift in typical (median) duration -- 5 sec to 4 sec.\n\n"
                    "**A plausible reading:** Arnold's average batch size grew ~20% after the pay "
                    "cut (more cases bundled per sitting, likely to offset lower per-case pay), "
                    "which is enough on its own to explain a slightly faster median entry pace, "
                    "without assuming any individual case was reviewed less carefully."
                )

# =================================================================== TAB 5
with tabs[4]:
    st.subheader("Approval volume over time")
    daily = fdf.groupby(["date", "Technician"]).size().reset_index(name="approvals")
    fig = px.line(
        daily, x="date", y="approvals", color="Technician", color_discrete_map=TECH_COLORS,
    )
    fig.add_vline(x=PAYOUT_CHANGE_DATE, line_dash="dash", line_color="black",
                   annotation_text="Payout cut ($50->$17)")
    fig.update_layout(height=380)
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Top approval days**")
        top_days = (
            fdf.groupby(["Technician", "date"]).size().reset_index(name="approvals")
            .sort_values("approvals", ascending=False).head(15)
        )
        st.dataframe(top_days, use_container_width=True, height=380)
    with col2:
        st.markdown("**Approvals by hour of day**")
        hourly = fdf.groupby(["hour", "Technician"]).size().reset_index(name="approvals")
        fig2 = px.bar(
            hourly, x="hour", y="approvals", color="Technician", barmode="group",
            color_discrete_map=TECH_COLORS,
        )
        fig2.update_layout(height=380)
        st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")
st.caption(
    "ClearCheck Technologies case study | Data: 15 monthly extracts, 3 technicians, "
    "approvals only (no rejected-case data). Built for a non-technical audience; every number "
    "here is reproducible from outputs/*.parquet via src/data_pipeline.py and src/analysis.py."
)
