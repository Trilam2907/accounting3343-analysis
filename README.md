# accounting3343-analysis

This repository contains a stock-screening notebook and a runnable Python script that pulls S&P 500 tickers, evaluates company financial strength, and saves screening results to CSV files.

## Run the screener

```bash
python3 financial_screen.py
```

The script writes:
- `sp500_screening_results.csv`
- `screening_errors.csv`

## Run the Streamlit dashboard

The dashboard reads the existing `sp500_screening_results.csv` file and does not recalculate the financial formulas when it starts.

```bash
python3 -m pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL shown in the terminal (typically `http://localhost:8501`).

### Screening workflow and score

The dashboard begins with the complete company dataset in `sp500_screening_results.csv`. Search in the starting-universe table only changes which rows are shown in that table; it does not change the screening universe.

The screening funnel applies three rules sequentially. The default cutoffs can be adjusted in the sidebar:

1. **STA ≥ 0** — higher positive scaled total accruals may indicate that reported earnings are less supported by operating cash flow.
2. **SNOA ≥ dataset median** — higher scaled net operating assets indicate greater operating-asset intensity and are used here as a potential weak-return signal.
3. **Altman Z ≤ 2.99** — lower scores can indicate greater financial distress; 2.99 is the upper edge of the traditional grey zone.

At every stage, the dashboard reports how many companies entered, passed, were excluded, and had missing data. The next stage receives only companies that passed the previous one. Rows with missing stage metrics are excluded at that stage and counted as missing.

The CSV currently contains `Financial Strength Score (0-9)`, and the dashboard verifies and reuses it. In `financial_screen.py`, its formula is:

```text
Profitability Score (0-4) + Funding Score (0-3) + Efficiency Score (0-2)
```

The score ranges from 0 to 9; higher values mean more positive financial-strength signals. The short-list sorts qualifying companies by this score from lowest to highest, then uses higher STA, higher SNOA, and lower Altman Z-Score to break ties. It shows up to 10 companies and never duplicates rows. A saved score that does not match the source formula is not used for ranking.

These are screening signals for further research—not predictions, recommendations, or guaranteed short positions. Altman Z-Score models are not equally suitable across industries. In particular, banks and other financial companies have balance sheets that can make working-capital and liability ratios misleading. The CSV has no industry field, so financial companies are not automatically excluded; their results need sector-specific review.
