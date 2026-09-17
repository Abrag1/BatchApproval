# ClearCheck Technologies -- Approval Anomaly Case

Python analysis pipeline + Streamlit dashboard investigating whether three
ClearCheck technicians (Gary Arnold, Juan Mendez, Matt Shawn) are reviewing
device-approval cases adequately, for the negligence review described in
`Approval_Case_Study.docx` / `Case Intro.pdf`.

## Project layout

```
project/
  data/                 raw per-technician Excel extracts (CASE_NUMBER, APPROVAL_DATE, Technician)
  src/
    data_pipeline.py     loads + cleans the extracts, derives duration/block features
    analysis.py          one-sample t-tests, block summary, payout two-sample t-test
    make_charts.py        static PNG charts for the written report
    build_report.py       assembles outputs/ClearCheck_Approval_Analysis_Report.docx
    build_notebook.py     assembles notebook/ClearCheck_Approval_Analysis.ipynb
  notebook/               narrated Jupyter notebook (analysis code deliverable)
  outputs/               generated parquet/csv/png/docx (created by the scripts above)
  app.py                 Streamlit dashboard
  requirements.txt
```

`notebook/ClearCheck_Approval_Analysis.ipynb` follows the same structure as the department's prior
Python case solution (Walmart Sales Forecasting): a Business Problem section, a roadmap, data
understanding, EDA framed as numbered Business Questions with Discussion/Business Interpretation
cells after each result, and a closing Business Insights & Recommendations section. It is the
"analysis code" deliverable in the format graders have seen before; `src/*.py` are the same
underlying logic as importable, reusable modules that both the notebook and the dashboard call.

## Reproducing the analysis

```bash
pip install -r requirements.txt
python src/data_pipeline.py   # -> outputs/approvals_clean.parquet, outputs/blocks.parquet
python src/analysis.py        # -> outputs/*.csv (t-tests, block summary, ...)
python src/make_charts.py     # -> outputs/charts/*.png
python src/build_report.py    # -> outputs/ClearCheck_Approval_Analysis_Report.docx

# Optional: rebuild and execute the narrated notebook
pip install nbformat nbconvert ipykernel seaborn
python src/build_notebook.py
jupyter nbconvert --to notebook --execute --inplace notebook/ClearCheck_Approval_Analysis.ipynb
```

## Running the dashboard locally

```bash
streamlit run app.py
```

## Deploying to Streamlit Community Cloud (free)

1. Push this `project/` folder to a **public GitHub repository** (the repo root
   should contain `app.py`, `requirements.txt`, `src/`, and `outputs/` -- the
   dashboard reads its data from the parquet files already checked into
   `outputs/`, so no database or secrets are needed).
2. Go to https://share.streamlit.io (Streamlit Community Cloud), sign in with
   GitHub, and click **New app**.
3. Pick the repository/branch and set the **main file path** to `app.py`
   (or `project/app.py` if the repo root is one level up).
4. Deploy. The build installs `requirements.txt` automatically and gives you a
   public `*.streamlit.app` URL -- test it in a private browser window before
   submitting.

If the `outputs/` parquet files are regenerated (e.g. new data), just
`git push` again; Streamlit Cloud auto-redeploys on every push to the tracked
branch.
