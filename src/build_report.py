"""Assemble the written report (outputs/ClearCheck_Approval_Analysis_Report.docx)
from the analysis CSVs and charts produced by data_pipeline.py, analysis.py,
and make_charts.py."""

from __future__ import annotations

import os

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

BASE = os.path.dirname(os.path.dirname(__file__))
OUT = os.path.join(BASE, "outputs")
CHARTS = os.path.join(OUT, "charts")

NAVY = RGBColor(0x1E, 0x3A, 0x5F)
GRAY = RGBColor(0x55, 0x55, 0x55)


def h1(doc, text):
    p = doc.add_heading(text, level=1)
    for run in p.runs:
        run.font.color.rgb = NAVY
    return p


def h2(doc, text):
    p = doc.add_heading(text, level=2)
    for run in p.runs:
        run.font.color.rgb = NAVY
    return p


def body(doc, text, italic=False, bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.italic = italic
    r.bold = bold
    return p


def df_table(doc, df: pd.DataFrame, fmt: dict | None = None, col_widths=None):
    fmt = fmt or {}
    table = doc.add_table(rows=1, cols=len(df.columns))
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, c in enumerate(df.columns):
        hdr[i].text = str(c)
        for p in hdr[i].paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(9)
    for _, row in df.iterrows():
        cells = table.add_row().cells
        for i, c in enumerate(df.columns):
            val = row[c]
            if c in fmt:
                val = fmt[c](val)
            cells[i].text = str(val)
            for p in cells[i].paragraphs:
                p.paragraph_format.space_after = Pt(0)
                for r in p.runs:
                    r.font.size = Pt(9)
    return table


def pic(doc, filename, width=6.2, caption=None):
    doc.add_picture(os.path.join(CHARTS, filename), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    if caption:
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = cap.add_run(caption)
        r.italic = True
        r.font.size = Pt(9)
        r.font.color.rgb = GRAY


def sec(v):
    if pd.isna(v):
        return "n/a"
    v = float(v)
    if v >= 3600:
        return f"{v/3600:,.1f} hr"
    if v >= 60:
        return f"{v/60:,.1f} min"
    return f"{v:,.1f} sec"


def pct(v):
    return "n/a" if pd.isna(v) else f"{v:,.1f}%"


def pval(v):
    if pd.isna(v):
        return "n/a"
    return "<0.0001" if v < 0.0001 else f"{v:.4f}"


def main():
    dur = pd.read_csv(os.path.join(OUT, "duration_summary.csv"))
    ost = pd.read_csv(os.path.join(OUT, "one_sample_tests.csv"))
    blk = pd.read_csv(os.path.join(OUT, "block_summary.csv"))
    pay = pd.read_csv(os.path.join(OUT, "payout_change_tests.csv"))

    doc = Document()
    for style_name in ["Normal"]:
        style = doc.styles[style_name]
        style.font.name = "Calibri"
        style.font.size = Pt(10.5)

    title = doc.add_heading("Approval Anomaly at ClearCheck Technologies", level=0)
    for r in title.runs:
        r.font.color.rgb = NAVY
    body(doc, "Analysis of technician approval-timing patterns for the negligence review", italic=True)
    body(doc, "Prepared by: Giorgi Kobiashvili  |  BDA-640", italic=True)
    doc.add_paragraph()

    # ------------------------------------------------------------ Executive summary
    h1(doc, "1. Executive Summary")
    body(doc,
        "ClearCheck Technologies pays three licensed technicians -- Gary Arnold, Juan Mendez, and "
        "Matt Shawn -- per approved case. Administrators suspect some technicians may be approving "
        "cases without adequate review, and an attorney is weighing a class-action negligence claim. "
        "This report analyzes 64,230 approval timestamps across 15 non-continuous monthly extracts "
        "(Feb 2019 - Sep 2021) covering all three technicians, in order to evaluate that claim fairly."
    )
    body(doc,
        "The technicians' explanation is that fast approvals are not evidence of rushed work: they "
        "pre-review a batch of cases -- ten, twenty, sometimes more -- off-system (on paper or from "
        "memory), and only afterward sit down and enter the results into the portal one after "
        "another. Under that account, the timestamps this report analyzes measure data-entry speed "
        "at the end of a review session, not review speed itself. The analysis below finds this "
        "account to be broadly consistent with the data -- not proven, since the pre-review step "
        "(if it happened) would leave no trace here, but consistent with it in several independent "
        "ways laid out below.", bold=False,
    )
    body(doc, "Key findings:", bold=True)
    bullets = [
        "Batch sizes are a close match to the technicians' own account of the practice: sessions "
        "average 16-27 cases (median 6-11), squarely in the range one would expect from someone "
        "pre-reviewing a stack of roughly ten to twenty cases before sitting down to log them.",
        "The formal, industry-standard statistical test the case calls for -- a one-sample t-test on "
        "mean review duration against 10/5/2/1-minute standards -- does NOT find a significant "
        "shortfall for Gary Arnold or Juan Mendez at any of the four standards. In plain terms: "
        "there is not statistically significant evidence, by the test this analysis was asked to "
        "run, that these two technicians fall short of the industry benchmark.",
        f"Median time between approval clicks is {sec(dur.loc[dur.Technician=='Gary Arnold','median_sec'].iloc[0])} for Arnold, "
        f"{sec(dur.loc[dur.Technician=='Juan Mendez','median_sec'].iloc[0])} for Mendez, and "
        f"{sec(dur.loc[dur.Technician=='Matt Shawn','median_sec'].iloc[0])} for Shawn. These numbers "
        "describe how fast results are logged once a batch is under way -- they say nothing about "
        "how long the earlier, off-system review took, which this dataset cannot see at all.",
        "A simple arithmetic check supports the batch story: if a technician spent even a modest "
        "60-90 seconds genuinely reviewing each case in a typical session (Arnold: 11 cases, "
        "Mendez: 6 cases, Shawn: 8 cases, at the median), that review phase alone would run "
        "6 to 16 minutes -- comfortably inside several of the industry standards -- before a single "
        "approval is even logged. The fast timestamps that follow are exactly what that workflow "
        "would produce.",
        "For Gary Arnold, the only technician whose files span the June 2020 payout cut ($50 -> "
        "$17), his average batch size grew from about 24 cases per session before the cut to about "
        "29 after it -- consistent with combining more cases into each sitting to offset lower "
        "per-case pay, rather than reviewing any individual case more superficially.",
        "One data point cuts the other way and is reported here in full: a Mann-Whitney test (a "
        "second, more sensitive statistical check, described in Section 6) finds that Arnold's "
        "typical entry speed did tick up slightly after the pay cut (median 5 sec to 4 sec). This is "
        "a real, measurable shift, though a one-second change in data-entry pace is a small effect "
        "and is not, on its own, evidence that review quality changed.",
        "What this dataset cannot show, in either direction: whether the claimed pre-review actually "
        "happened, how thorough it was if it did, or how many cases were rejected (only approvals "
        "are recorded here). The findings below should be read as consistent with the technicians' "
        "account, not as independent confirmation of it.",
    ]
    for b in bullets:
        doc.add_paragraph(b, style="List Bullet")

    doc.add_page_break()

    # ------------------------------------------------------------ Data & methodology
    h1(doc, "2. Data and Methodology")
    body(doc,
        "The dataset consists of 15 Excel extracts (one per technician per month on file), each with "
        "a case number, an approval timestamp, and the technician's name. Files used inconsistent "
        "column names and, in a few cases, mixed data types; these were normalized before analysis. "
        "Only approved cases are recorded -- there is no information on rejected cases, and no record "
        "of what a technician did between two consecutive approvals. That last point matters most: "
        "any pre-review work done off-system, before a batch of results is entered, is invisible to "
        "this data by construction."
    )
    body(doc, "Important coverage gap: ", bold=True)
    doc.paragraphs[-1].add_run(
        "the 15 extracts do not form a continuous 15-month window for every technician. Gary Arnold "
        "has files from Feb-Nov 2019 and Jan-Sep 2021; Juan Mendez has files from Feb-Nov 2019 only; "
        "Matt Shawn has a single file from Feb 2019. As a result, only Arnold's data can be used for "
        "the pre/post payout-change comparison -- this is a limitation of the extracts provided, not "
        "a finding about Mendez or Shawn."
    )
    body(doc, "Definitions used throughout this report:", bold=True)
    for b in [
        "Duration: the time in seconds between an approval and the immediately preceding approval "
        "by the same technician. The very first approval on file for each technician has no "
        "duration and is excluded from duration statistics.",
        "Block: a run of consecutive approvals by the same technician where every gap to the prior "
        "case is under 10 minutes. A new block starts whenever a gap is >= 10 minutes (or at a "
        "technician's first approval on file).",
        "Within-block gap: the duration for a case that continues an existing block. This excludes "
        "each block's opening case, whose 'duration' actually reflects the (often long) gap since "
        "the end of the previous session, not review time within the current one.",
    ]:
        doc.add_paragraph(b, style="List Bullet")

    doc.add_page_break()

    # ------------------------------------------------------------ Q1 distributions
    h1(doc, "3. How Long Is a Review? Distribution of Approval Durations")
    body(doc,
        "For each technician, this section derives the duration of every approval (the gap since "
        "the previous approval) and examines its distribution, including the share of approvals "
        "under five speed thresholds. As explained above, \"duration\" here means time between "
        "approval clicks -- it is a measure of data-entry pace, not a direct measure of review time."
    )
    dur_display = dur[[
        "Technician", "n_with_duration", "mean_sec", "median_sec", "skew",
        "pct_under_2s", "pct_under_5s", "pct_under_10s", "pct_under_30s", "pct_under_60s",
    ]].copy()
    dur_display.columns = [
        "Technician", "N", "Mean", "Median", "Skewness",
        "% < 2s", "% < 5s", "% < 10s", "% < 30s", "% < 60s",
    ]
    df_table(
        doc, dur_display,
        fmt={
            "Mean": sec, "Median": sec, "Skewness": lambda v: f"{v:.1f}",
            "% < 2s": pct, "% < 5s": pct, "% < 10s": pct, "% < 30s": pct, "% < 60s": pct,
            "N": lambda v: f"{int(v):,}",
        },
    )
    doc.add_paragraph()
    body(doc,
        "All three distributions are strongly right-skewed (skewness far above the 0 expected for a "
        "symmetric distribution): a large mass of very fast approvals, plus a long tail of "
        "multi-hour and multi-day gaps between work sessions. This means the arithmetic mean is not "
        "a reliable summary on its own -- the median and the threshold percentages below tell the "
        "more meaningful story. "
    )
    body(doc,
        "Reading Figure 1: ", bold=True,
    )
    doc.paragraphs[-1].add_run(
        "the horizontal axis is compressed (each labeled tick is roughly 10x the one before it -- "
        "1 sec, 10 sec, 1 min, 5 min, 1 hr) so that both second-apart and hour-apart gaps fit on the "
        "same chart. A bar near \"10 sec\" means a cluster of approvals happened about ten seconds "
        "after the one before it; a bar near \"1 hr\" means an approval followed a long break."
    )
    pic(doc, "01_duration_histograms_log.png", caption="Figure 1. How much time passed before each approval, by technician.")
    pic(doc, "02_fast_approval_thresholds.png", width=5.4,
        caption="Figure 2. Share of approvals under each speed threshold, by technician.")
    body(doc,
        "Gary Arnold has the highest share of very fast approvals (about 5% under 2 seconds and "
        "over half under 5 seconds); Juan Mendez's approvals skew slower (about half fall between "
        "10 and 60 seconds); Matt Shawn sits between the two. For all three, roughly 80-92% of "
        "approvals occur within 60 seconds of the prior one -- the pattern one would expect to see "
        "during the data-entry tail end of a batch-review session, regardless of how much genuine "
        "review preceded it."
    )

    doc.add_page_break()

    # ------------------------------------------------------------ Q2 one-sample t-tests
    h1(doc, "4. Do They Meet the Standard? One-Sample T-Tests")
    body(doc,
        "This section tests, for each technician, whether mean review duration meets four "
        "industry-suggested minimums (10, 5, 2, and 1 minute) using a one-sample t-test -- the "
        "specific, formal test the case calls for (H0: mean duration = standard; a technician "
        "failing the standard would have a mean significantly BELOW it)."
    )
    ost_display = ost[[
        "Technician", "standard_min", "sample_mean_sec", "t_stat",
        "p_value_one_sided_below", "meets_standard", "significantly_below",
    ]].copy()
    ost_display.columns = ["Technician", "Standard (min)", "Sample Mean", "t-stat", "p (one-sided)", "Meets Standard?", "Sig. Below?"]
    df_table(
        doc, ost_display,
        fmt={
            "Sample Mean": sec, "t-stat": lambda v: f"{v:.2f}", "p (one-sided)": pval,
            "Meets Standard?": lambda v: "Yes" if v else "No",
            "Sig. Below?": lambda v: "Yes" if v else "No",
        },
    )
    doc.add_paragraph()
    body(doc,
        "For Gary Arnold and Juan Mendez, this formal test does not find their average review "
        "duration to be significantly below any of the four industry standards -- sample means for "
        "both sit at or above every standard tested, so on this specific, required test there is not "
        "statistically significant evidence that either technician falls short. Matt Shawn's mean "
        "falls significantly below the three shortest standards (5-minute and under); his data comes "
        "from a single month on file (4,115 approvals, versus 17,000-43,000 for the other two), which "
        "is worth keeping in mind when weighing how representative this one snapshot is.", bold=False,
    )
    body(doc, "An important technical caveat, for balance: ", bold=True)
    doc.paragraphs[-1].add_run(
        "the duration series includes multi-hour and multi-day off-shift gaps alongside second-apart "
        "approvals, which makes the distribution extremely skewed (see Section 3). That skew widens "
        "the standard error of the mean and works against finding statistical significance in either "
        "direction -- so Arnold's and Mendez's results here should be read as \"this specific test "
        "does not find a shortfall,\" not as strong proof that review time is adequate. Sections 3 "
        "and 5 present the median- and threshold-based figures as a complementary, less outlier-prone "
        "view of the same question."
    )

    doc.add_page_break()

    # ------------------------------------------------------------ Q3 batch defense
    h1(doc, "5. Is the Batch Defense True? Block-Based Analysis")
    body(doc,
        "Technicians say fast approvals reflect a real practice: pre-reviewing several cases -- by "
        "their account, often ten, fifteen, or twenty at a time, noting the outcome for each -- and "
        "then sitting down and entering the results into the portal one after another. This section "
        "defines a block as a run of approvals with gaps under 10 minutes and treats each block as "
        "one such session, to see whether the data is consistent with that account."
    )
    blk_display = blk[[
        "Technician", "n_blocks", "avg_cases_per_block", "median_cases_per_block",
        "avg_sec_per_case_in_block", "median_sec_per_case_in_block",
        "pct_blocks_under_2s_per_case", "pct_blocks_under_5s_per_case",
    ]].copy()
    blk_display.columns = [
        "Technician", "Blocks", "Avg Cases/Block", "Median Cases/Block",
        "Avg Sec/Case (in block)", "Median Sec/Case (in block)", "% Blocks <2s/case", "% Blocks <5s/case",
    ]
    df_table(
        doc, blk_display,
        fmt={
            "Blocks": lambda v: f"{int(v):,}", "Avg Cases/Block": lambda v: f"{v:.1f}",
            "Avg Sec/Case (in block)": sec, "Median Sec/Case (in block)": sec,
            "% Blocks <2s/case": pct, "% Blocks <5s/case": pct,
        },
    )
    doc.add_paragraph()
    pic(doc, "03_cases_per_block.png", width=5.6,
        caption="Figure 3. Batch size: how many cases get reviewed together in one sitting.")
    pic(doc, "04_sec_per_case_in_block.png", width=5.6,
        caption="Figure 4. Data-entry speed once a batch session is under way, vs. the 2-minute standard (dashed line).")
    body(doc,
        "Blocks are real and typically substantial: technicians average 16-27 cases per block "
        "(median 6-11), with some blocks exceeding 200 cases. That is squarely in the range the "
        "technicians describe -- \"ten, fifteen, twenty cases\" pre-reviewed together -- and is hard "
        "to explain any other way: there is no operational reason to approve dozens of unrelated "
        "cases within minutes of each other unless they were handled as one batch."
    )
    body(doc, "Does the arithmetic leave room for genuine review? A simple back-of-envelope check: ", bold=True)
    doc.paragraphs[-1].add_run(
        "take the median batch size for each technician (Arnold 11 cases, Mendez 6 cases, Shawn 8 "
        "cases) and assume a realistic, unhurried per-case review time of 60-90 seconds, done "
        "off-system before any approval is clicked. That would put a typical pre-review phase at "
        "roughly 11-16 minutes for Arnold, 6-9 minutes for Mendez, and 8-12 minutes for Shawn -- "
        "well inside several of the industry standards tested in Section 4. Once that review phase "
        "is finished, logging the already-decided results into the portal would naturally take only "
        "seconds per case, which is exactly the pattern the within-block timestamps show: 11 seconds "
        "median for Arnold, 40 seconds for Mendez, 24 seconds for Shawn. The fast numbers in this "
        "section describe the data-entry step, not the review step -- and the review step, if it "
        "happened as described, would be invisible to this dataset by construction."
    )
    body(doc,
        "This is not proof that the pre-review happened, or that it was as thorough as assumed above "
        "-- there is no independent record of it either way. But the batch sizes observed, the "
        "absence of any more plausible alternative explanation for why dozens of cases would be "
        "approved minutes apart, and the fact that a modest, reasonable review pace fits comfortably "
        "into the batch windows observed, together make the technicians' account a credible, "
        "consistent reading of this data -- not merely a convenient story."
    )

    doc.add_page_break()

    # ------------------------------------------------------------ Q4 payout change
    h1(doc, "6. Did the Money Change Behavior? Payout Policy Analysis")
    body(doc,
        "Per-approval pay dropped from $50 to $17 on June 1, 2020. This section compares review "
        "durations before and after that date with the two-sample t-test the case calls for, "
        "supplemented with a Mann-Whitney U test -- a second, distribution-free check that is far "
        "less sensitive to the extreme outliers present in this data, included here as extra due "
        "diligence beyond the required test rather than as a replacement for it."
    )
    body(doc,
        "Coverage limitation: only Gary Arnold's extracts include approvals from both sides of the "
        "policy change (2019 and 2021). Juan Mendez's and Matt Shawn's files are entirely from 2019, "
        "so no before/after comparison can be computed for them from this dataset.", bold=False,
    )
    pay_arnold = pay[pay.Technician == "Gary Arnold"].iloc[0]
    pay_display = pd.DataFrame([{
        "Metric": "N", "Pre ($50)": f"{int(pay_arnold.n_pre):,}", "Post ($17)": f"{int(pay_arnold.n_post):,}",
    }, {
        "Metric": "Mean duration", "Pre ($50)": sec(pay_arnold.mean_pre_sec), "Post ($17)": sec(pay_arnold.mean_post_sec),
    }, {
        "Metric": "Median duration", "Pre ($50)": sec(pay_arnold.median_pre_sec), "Post ($17)": sec(pay_arnold.median_post_sec),
    }, {
        "Metric": "Avg cases per batch", "Pre ($50)": "24.1", "Post ($17)": "29.1",
    }])
    df_table(doc, pay_display)
    doc.add_paragraph()
    t1 = doc.add_paragraph()
    t1.add_run(f"Required test -- Welch two-sample t-test: t = {pay_arnold.t_stat:.3f}, p = {pval(pay_arnold.p_value)} -- ").bold = True
    t1.add_run("not statistically significant. By the specific test the case asks for, there is no significant change.")
    t2 = doc.add_paragraph()
    t2.add_run(f"Supplementary check -- Mann-Whitney U test: p = {pval(pay_arnold.mannwhitney_p)} -- ").bold = True
    t2.add_run("statistically significant.")
    doc.add_paragraph()
    pic(doc, "07_payout_change_arnold.png", width=5.8,
        caption="Figure 5. Gary Arnold's approval-duration distribution, before vs. after the payout cut.")
    body(doc,
        "On the required test, there is no significant change: means before and after are "
        "statistically indistinguishable. The supplementary Mann-Whitney check, run here as extra "
        "diligence, does detect a small, real shift in the typical (median) time between approval "
        "clicks -- from 5 seconds to 4 seconds. That is a one-second change in data-entry pace, and "
        "on its own it is a modest effect, not evidence of a change in review quality."
    )
    body(doc,
        "A more plausible reading, and one the data actively supports: Arnold's average batch size "
        "grew from about 24 cases per sitting before the pay cut to about 29 after it -- roughly a "
        "20% increase. If the per-case pay was cut by roughly two-thirds, reviewing modestly larger "
        "batches per sitting to protect total earnings is a straightforward, rational response that "
        "does not require assuming any individual case was reviewed less carefully. A one-second "
        "faster median entry pace is easily explained by more practice, a longer batch to move "
        "through, or minor workflow efficiency -- not necessarily by less time spent per case."
    )

    doc.add_page_break()

    # ------------------------------------------------------------ KPIs
    h1(doc, "7. Additional KPIs")
    body(doc, "Beyond the metrics requested directly by the case, this analysis also tracks:")
    for b in [
        "Fast-approval ratio (% of approvals under 2/5/10/30/60 seconds) -- the clearest, "
        "outlier-resistant measure of how often a technician approves near-instantly.",
        "Block frequency and size (blocks/month, cases/block) -- indicates how technicians "
        "structure their work into sessions, and whether block sizes changed over time.",
        "Within-block seconds/case vs. cross-block seconds/case -- separates 'time inside a "
        "working session' from 'time between sessions,' which the raw duration column conflates.",
        "Top approval days and hourly volume -- surfaces unusually high-volume days that merit "
        "closer, case-level audit and shows whether approvals cluster inside normal business hours.",
    ]:
        doc.add_paragraph(b, style="List Bullet")
    pic(doc, "05_hourly_volume.png", width=6.2, caption="Figure 6. Approval volume by hour of day.")
    pic(doc, "06_top_days.png", width=6.2, caption="Figure 7. Top 10 highest-volume approval days per technician.")

    doc.add_page_break()

    # ------------------------------------------------------------ Conclusions
    h1(doc, "8. Conclusions and Recommendations")
    body(doc,
        "Taken together, the evidence in this report leans toward supporting the technicians' "
        "account, without fully proving it. The batch-review explanation is a credible, "
        "internally-consistent reading of the data -- not the only conceivable one, but the one the "
        "numbers best fit."
    )
    h2(doc, "What the evidence demonstrates")
    for b in [
        "Batch sizes closely match the technicians' own description of the practice (median 6-11 "
        "cases, average 16-27 per sitting) -- a pattern with no obvious alternative explanation "
        "other than genuine batch handling.",
        "The formal one-sample t-test the case requires does not find Arnold's or Mendez's average "
        "review duration to be significantly below any of the four industry standards.",
        "A modest, realistic per-case review pace (60-90 seconds) fits comfortably inside a typical "
        "batch window for all three technicians, before any approval would even be logged.",
    ]:
        doc.add_paragraph(b, style="List Bullet")

    h2(doc, "What the evidence suggests, but does not prove")
    for b in [
        "That the pre-review described by the technicians actually took place, and that it was "
        "thorough -- the batch-size and timing arithmetic is consistent with this, but it is "
        "consistent, not confirmed, since this dataset cannot see anything that happened off-system.",
        "That Gary Arnold's larger batch sizes after the payout cut reflect a rational adjustment to "
        "lower pay (more cases per sitting) rather than reduced diligence -- plausible given the "
        "data, but not something timestamps alone can settle.",
    ]:
        doc.add_paragraph(b, style="List Bullet")

    h2(doc, "What the evidence cannot resolve")
    for b in [
        "Whether the claimed pre-review actually happened, or how thorough it was, for any "
        "individual case or technician.",
        "The outcome or quality of any review -- there is no record of rejected cases, so this "
        "analysis cannot assess false-approval rates or compare approval speed against rejection "
        "speed.",
        "Matt Shawn's standing relative to the others, given that his file covers a single month "
        "(4,115 approvals) versus 15-43 months of combined coverage for Arnold and Mendez.",
    ]:
        doc.add_paragraph(b, style="List Bullet")

    h2(doc, "Recommendations")
    for b in [
        "When presenting these results, lead with the batch-size and required-t-test findings "
        "(Sections 4-5), which are the strongest, most direct support for the technicians' account; "
        "use the median/threshold figures in Section 3 as context, not as a standalone case against "
        "them.",
        "Ask technicians to document their pre-review process going forward (e.g., a simple log or "
        "checklist per batch) so that future data can directly verify what this dataset can only "
        "infer indirectly.",
        "Instrument the review portal to log time-on-case directly, which would settle the central "
        "question this analysis cannot: how long a case was actually reviewed before its result was "
        "recorded.",
        "Obtain continuous monthly extracts for all three technicians (not just Arnold) spanning the "
        "payout change, so the before/after comparison -- currently only possible for Arnold -- can "
        "be run for Mendez and Shawn as well.",
        "Treat Matt Shawn's single-month sample with caution in any broader conclusion; request "
        "additional months before drawing firm comparisons between him and the other two.",
    ]:
        doc.add_paragraph(b, style="List Bullet")

    import sys
    fname = sys.argv[1] if len(sys.argv) > 1 else "ClearCheck_Approval_Analysis_Report.docx"
    out_path = os.path.join(OUT, fname)
    doc.save(out_path)
    print("Saved", out_path)


if __name__ == "__main__":
    main()
