# S&P 500 Stock Screener

An interactive Streamlit app for screening S&P 500 companies by sector and financial metrics.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

The app reads `sp500_all_company_metrics.csv` and
`sp500_three_year_historical_metrics.csv` from the repository. These bundled datasets
are snapshots generated on November 20, 2026; they are not refreshed automatically.
Each company record carries its reporting currency, calculation timestamp, formula
version, and a missing restatement flag because the data provider does not expose a
reliable one. The historical dataset contains up to three fiscal-year observations for
each company with available statement data.
Sector filters and peer rankings use the 11 broad GICS sectors from the S&P 500
constituent list, rather than Yahoo Finance's inconsistent sector/category labels.

The app has three sections: an overview with universe and active-screen summaries, a
stock screener with filters and historical trends, and methodology with formulas,
calculation policy, and data-quality coverage. The supplied metric list included only
a subset of the referenced 97 definitions; unprovided definitions are not inferred or
presented as implemented.

Company rankings use sector-relative metric percentiles averaged into Safety, Quality,
Growth, Value, Financial Strength, and Capital Allocation groups. Safety is weighted
25%, Quality 20%, Growth 15%, Value 15%, Financial Strength 15%, and Capital Allocation
10%; weights for missing groups are renormalized across available groups. A company needs
a Safety score and at least three available group scores; missing metrics are not imputed.
Lower STA and SNOA values rank better. Return on Equity and Asset Turnover are included in
Quality. Current Ratio is scored by closeness to its sector median, and Net Equity
Issuance is excluded from the composite because it is the inverse of Buyback Yield.

## Deploy to Streamlit Community Cloud

Push this repository to GitHub, then create an app in Streamlit Community Cloud using
this repository, the desired branch, and `app.py` as the main file. The `requirements.txt`
file supplies the app dependencies.

The metrics are provided for educational screening only, are not live market data, and
should not be treated as investment advice. The three-year history does not include
historical P/E, market capitalization, buyback yields, or net issuance yields.