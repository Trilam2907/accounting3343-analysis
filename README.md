# S&P 500 short-research screener

This project provides a Streamlit research dashboard using saved annual company financial statements. It highlights companies for additional research; it does not predict profitable trades or make investment recommendations.

## Data source and coverage

`financial_screen.py` uses the tickers in `universe.csv` as its source universe when that file exists (accepting a `Ticker` or `Symbol` column). If no universe file exists, it gets S&P 500 constituent symbols from Wikipedia's [List of S&P 500 companies](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies). It then requests financial statements and market capitalization from yfinance. The refreshed source snapshot is written to `universe.csv`; `sp500_screening_results.csv` is kept as a compatible copy. Both include a `Data Retrieval Date` in UTC.

The source file in the repository before this refresh was `sp500_screening_results.csv` with 503 unique tickers. It did not contain raw financial inputs or a retrieval date, so its historical retrieval date could not be verified. The refreshed snapshot covers 503 unique companies and was retrieved on **2026-10-22 (UTC)**; the date and raw inputs are recorded in `universe.csv`. All source-universe symbols are retained; no companies or industries are excluded, including financial firms. Companies with statement or API failures remain represented in the universe with missing fields and are logged in `screening_errors.csv` when a request raises an exception. Missing source values are not replaced with zero for STA, Scaled NOA, Altman Z, or complete P-Scores.

The S&P list changes over time, and yfinance's availability, fiscal periods, and labels can change. Treat each generated CSV as a dated snapshot rather than a live feed. The current data contains annual statement data through the fiscal years reported in the `Latest Fiscal Year` column.

## Metric definitions

- **STA (scaled total accruals):** `(Net Income - Operating Cash Flow) / Total Assets`. A value is missing if net income, operating cash flow, or positive total assets are unavailable.
- **Scaled NOA:** `(Total Debt + Equity - Cash) / Prior-Year Total Assets`. Total debt uses the statement's `Total Debt` when available; otherwise it is the sum of reported current and long-term debt. The value is missing if debt, equity, cash, or positive prior-year assets are unavailable.
- **Altman Z-Score:** `1.2 × WC/TA + 1.4 × RE/TA + 3.3 × EBIT/TA + 0.6 × MVE/TL + 1.0 × Sales/TA`. The app and script require the inputs and positive total assets/liabilities; they do not invent zero or substitute company assets for missing market value.

The market value of equity is the yfinance market capitalization retrieved with the financial statements. It may not correspond exactly to the historical statement date.

## Screening controls and red flags

The app calculates STA and Scaled NOA percentile ranks over the full starting universe using average ranks for tied observations. Missing values receive no percentile and do not trigger their related flag.

1. STA percentile is at or above the selected accrual percentile (default 75).
2. Scaled NOA percentile is at or above the selected accrual percentile (default 75).
3. Altman Z-Score is below the selected cutoff (default 2.0).

The user chooses the minimum number of flags required (1–3, default 2). The known triggered-flag count determines qualification; missing flags are shown as unavailable, are not counted as triggered, and are exposed separately in the table. The funnel shows the starting universe and nested counts with at least one, two, or three flags, plus the selected qualification count.

## P-Score

The saved `Financial Strength Score (0-9)` is the project's Piotroski-style nine-signal score, shown in the app as **P-Score**. Its groups are:

- **Profitability (0–4):** positive ROA; positive operating cash flow relative to beginning assets; ROA improvement; and operating cash flow greater than net income.
- **Funding (0–3):** lower long-term debt-to-assets than the prior period; higher current ratio; and no positive common-share issuance.
- **Efficiency (0–2):** improved gross margin and improved asset turnover.

The total is `Profitability + Funding + Efficiency`, with a maximum of 9. Funding already combines the leverage, liquidity, and issuance signals. A group score and total P-Score are missing when one of their required inputs is missing. The app checks that the saved total equals these three component scores. P-Score is not a fourth red flag. Candidates are ranked by triggered red-flag count descending, STA percentile descending, Scaled NOA percentile descending, P-Score ascending (lower scores rank higher as a confirmation signal), then Altman Z ascending. At each tie-breaker, missing values sort below available values; they are never treated as zero. No duplicate rows are added when fewer than 10 candidates qualify.

## Exclusions and limitations

No industry-wide exclusions are applied. Failed requests or absent statement inputs may make a company's metrics unavailable, so the displayed 503-company count is not a promise that every company has complete data. Check `screening_errors.csv`, `Data Error`, and the missing metric indicators.

The original Altman Z model was not designed for consistent interpretation across all sectors. Banks and other financial companies can have balance-sheet structures that make working-capital and liability ratios unsuitable. They remain in the universe and should be evaluated with sector-specific methods. This screening strategy is not claimed to be validated; thresholds are exploratory controls, results are time-sensitive, and short selling involves substantial risk.

## Run the screener and dashboard

Refresh the saved universe when desired:

```bash
python3 -m pip install -r requirements.txt
python3 financial_screen.py
```

Run the app from the project folder:

```bash
streamlit run app.py
```

The dashboard reads `universe.csv` first and falls back to `sp500_screening_results.csv`. It does not download stock data at app startup. To deploy with Streamlit Community Cloud, push `app.py`, `universe.csv`, and `requirements.txt` to GitHub, choose `app.py` as the main file, and deploy the branch containing those files.
