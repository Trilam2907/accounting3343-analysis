# S&P 500 Stock Screener

An interactive Streamlit app for screening S&P 500 companies by sector and financial metrics.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

The app reads `sp500_all_company_metrics.csv` from the repository. This bundled dataset
is a snapshot generated on November 20, 2026; it is not refreshed automatically. The
notebook `Untitled8.ipynb` contains the data collection and metric calculation workflow.

## Deploy to Streamlit Community Cloud

Push this repository to GitHub, then create an app in Streamlit Community Cloud using
this repository, the desired branch, and `app.py` as the main file. The `requirements.txt`
file supplies the app dependencies.

The metrics are provided for educational screening only, are not live market data, and
should not be treated as investment advice.