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

### Dashboard score and filters

The CSV currently contains `Financial Strength Score (0-9)`, so the dashboard reuses that saved aggregate rather than calculating it again. In `financial_screen.py`, that score is calculated as:

```text
Profitability Score (0-4) + Funding Score (0-3) + Efficiency Score (0-2)
```

The Funding Score is already the sum of Leverage, Liquidity, and Equity Issuance scores. Therefore, adding all six listed columns would count those funding signals twice. If the saved aggregate is absent, the dashboard derives the score from Profitability + Leverage + Liquidity + Equity Issuance + Efficiency when those five columns are available; otherwise it uses Profitability + Funding + Efficiency. A derived score is left missing for any row missing one of its required inputs; missing values are never treated as zero.

The sidebar range filters are based on the available numeric values in the CSV for STA, SNOA, Altman Z, and Financial Strength Score. Rows missing a selected filter metric are excluded by that filter. The two Altman categories chart uses the CSV's `Risk Classification` when valid, and falls back to the standard Z-score cutoffs (Distress below 1.81, Grey from 1.81 through 2.99, Safe above 2.99) when the category is unavailable.
