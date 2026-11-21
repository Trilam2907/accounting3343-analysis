from pathlib import Path

import pandas as pd
import streamlit as st


DATA_FILE = Path(__file__).parent / "sp500_all_company_metrics.csv"
HISTORY_FILE = Path(__file__).parent / "sp500_three_year_historical_metrics.csv"
IDENTIFIER_COLUMNS = ["Company", "Ticker", "Sector", "Industry"]
STATUS_COLUMN = "Download Status"
METRIC_COLUMNS = [
    "Gross Profitability",
    "Gross Margin (%)",
    "Operating Margin (%)",
    "EBITDA Margin (%)",
    "Net Profit Margin (%)",
    "ROA (%)",
    "ROE (%)",
    "Asset Turnover",
    "Buyback Yield (%)",
    "Net Equity Issuance (%)",
    "P/E Ratio",
    "Debt/Equity",
    "Current Ratio",
    "EPS Growth (%)",
    "FCF Growth (%)",
    "STA (%)",
    "SNOA (%)",
]
HISTORY_METRICS = [
    "Revenue",
    "Net Income",
    "EPS",
    "Free Cash Flow",
    "Gross Margin (%)",
    "Operating Margin (%)",
    "EBITDA Margin (%)",
    "Net Profit Margin (%)",
    "ROA (%)",
    "ROE (%)",
    "Asset Turnover",
    "Debt/Equity",
    "Current Ratio",
    "EPS Growth (%)",
    "FCF Growth (%)",
    "STA (%)",
    "SNOA (%)",
]


@st.cache_data
def load_history() -> pd.DataFrame:
    if not HISTORY_FILE.is_file():
        raise FileNotFoundError(f"Historical dataset not found: {HISTORY_FILE.name}")

    data = pd.read_csv(HISTORY_FILE)
    required_columns = {
        "Company",
        "Ticker",
        "Sector",
        "Fiscal Year",
        *HISTORY_METRICS,
    }
    missing_columns = required_columns.difference(data.columns)
    if missing_columns:
        raise ValueError(
            f"Historical dataset is missing columns: {', '.join(sorted(missing_columns))}"
        )

    data["Fiscal Year"] = pd.to_numeric(data["Fiscal Year"], errors="coerce")
    for column in HISTORY_METRICS:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["Fiscal Year"])


st.set_page_config(page_title="S&P 500 Stock Screener", page_icon="📊", layout="wide")


@st.cache_data
def load_metrics() -> pd.DataFrame:
    if not DATA_FILE.is_file():
        raise FileNotFoundError(f"Metrics dataset not found: {DATA_FILE.name}")

    data = pd.read_csv(DATA_FILE)
    required_columns = set(IDENTIFIER_COLUMNS + METRIC_COLUMNS + [STATUS_COLUMN])
    missing_columns = required_columns.difference(data.columns)
    if missing_columns:
        raise ValueError(f"Metrics dataset is missing columns: {', '.join(sorted(missing_columns))}")

    for column in METRIC_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data


st.title("S&P 500 Stock Screener")
st.caption(
    "Explore company fundamentals from the bundled dataset. Values are a snapshot "
    "generated on November 20, 2026, and are not live market data or investment advice."
)

try:
    metrics = load_metrics()
except (FileNotFoundError, ValueError, pd.errors.ParserError) as error:
    st.error(f"Could not load the stock metrics: {error}")
    st.stop()

successful = metrics[STATUS_COLUMN].eq("OK")
st.sidebar.header("Screening filters")
include_download_issues = st.sidebar.checkbox("Include rows with download issues", value=False)
sectors = sorted(metrics["Sector"].dropna().astype(str).unique())
selected_sectors = st.sidebar.multiselect("Sectors", sectors, default=sectors)
search = st.sidebar.text_input("Company or ticker contains")
selected_metrics = st.sidebar.multiselect(
    "Filter by financial metrics",
    METRIC_COLUMNS,
    help="Choose metrics to add range filters. Companies without a value for a chosen metric are excluded.",
)

filtered = metrics.copy()
if not include_download_issues:
    filtered = filtered[successful]
if selected_sectors:
    filtered = filtered[filtered["Sector"].isin(selected_sectors)]
else:
    filtered = filtered.iloc[0:0]
if search.strip():
    query = search.strip()
    matched = (
        filtered["Company"].fillna("").str.contains(query, case=False, regex=False)
        | filtered["Ticker"].fillna("").str.contains(query, case=False, regex=False)
    )
    filtered = filtered[matched]

for metric in selected_metrics:
    values = metrics[metric].dropna()
    if values.empty:
        st.sidebar.caption(f"{metric}: no values available")
        filtered = filtered.iloc[0:0]
        continue

    low, high = float(values.min()), float(values.max())
    if low == high:
        st.sidebar.caption(f"{metric}: {low:.3g} (only available value)")
        filtered = filtered[filtered[metric].eq(low)]
        continue

    selected_range = st.sidebar.slider(
        metric,
        min_value=low,
        max_value=high,
        value=(low, high),
        key=f"range_{metric}",
        help="Range uses the full dataset, before other filters.",
    )
    filtered = filtered[
        filtered[metric].notna()
        & filtered[metric].between(selected_range[0], selected_range[1])
    ]

st.sidebar.divider()
normalization = st.sidebar.selectbox(
    "Comparison columns",
    ["None", "Percentile rank (0–100)", "Z-score"],
)

left, middle, right = st.columns(3)
left.metric("Companies shown", f"{len(filtered):,}")
middle.metric("Companies with data", f"{int(successful.sum()):,}")
right.metric("Rows with download issues", f"{int((~successful).sum()):,}")

result = filtered[IDENTIFIER_COLUMNS + METRIC_COLUMNS].copy()
if normalization == "Percentile rank (0–100)":
    for metric in selected_metrics or METRIC_COLUMNS:
        result[f"{metric} Percentile"] = metrics[metric].rank(pct=True) * 100
elif normalization == "Z-score":
    for metric in selected_metrics or METRIC_COLUMNS:
        standard_deviation = metrics[metric].std()
        if pd.isna(standard_deviation) or standard_deviation == 0:
            result[f"{metric} Z-Score"] = pd.NA
        else:
            result[f"{metric} Z-Score"] = (
                result[metric] - metrics[metric].mean()
            ) / standard_deviation

result = result.sort_values("Ticker", kind="stable").reset_index(drop=True)
st.dataframe(result, hide_index=True, width="stretch")
st.download_button(
    "Download filtered results as CSV",
    data=result.to_csv(index=False).encode("utf-8"),
    file_name="sp500_screen_results.csv",
    mime="text/csv",
    disabled=result.empty,
)

st.caption(
    "Financial metrics are calculated from annual company statements and Yahoo Finance data. "
    "Some values may be missing or distorted by unusual accounting items; verify data before use."
)

st.divider()
st.header("Three-year historical trends")
st.caption(
    "Historical rows show up to three available annual observations per company. "
    "Coverage varies, and historical P/E and shareholder-yield metrics are not available."
)
try:
    history = load_history()
except (FileNotFoundError, ValueError, pd.errors.ParserError) as error:
    st.error(f"Could not load historical metrics: {error}")
    st.stop()

history_tickers = sorted(history["Ticker"].dropna().astype(str).unique())
if not history_tickers:
    st.info("No historical statement data is available.")
    st.stop()

companies = history.drop_duplicates("Ticker").set_index("Ticker")["Company"].fillna("")
history_controls = st.columns(3)
selected_ticker = history_controls[0].selectbox(
    "Company",
    history_tickers,
    format_func=lambda ticker: f"{ticker} — {companies.get(ticker, ticker)}",
)
selected_history_metric = history_controls[1].selectbox(
    "Historical metric",
    HISTORY_METRICS,
    index=HISTORY_METRICS.index("Revenue"),
)
history_sectors = sorted(history["Sector"].dropna().astype(str).unique())
selected_comparison_sector = history_controls[2].selectbox(
    "Compare sector",
    ["No sector comparison", *history_sectors],
)

company_history = history[history["Ticker"].astype(str).eq(selected_ticker)].sort_values(
    "Fiscal Year"
)
chart_history = company_history.dropna(subset=[selected_history_metric])
if chart_history.empty:
    st.info(f"No {selected_history_metric} observations are available for this company.")
else:
    st.line_chart(
        chart_history.set_index("Fiscal Year")[[selected_history_metric]],
        x_label="Fiscal year",
        y_label=selected_history_metric,
    )
    st.dataframe(
        chart_history[["Fiscal Year", selected_history_metric]].reset_index(drop=True),
        hide_index=True,
        width="stretch",
    )

if selected_comparison_sector != "No sector comparison":
    latest_company_year = company_history["Fiscal Year"].max()
    sector_comparison = history[
        history["Sector"].eq(selected_comparison_sector)
        & history["Fiscal Year"].eq(latest_company_year)
    ][["Company", "Ticker", selected_history_metric]].dropna(
        subset=[selected_history_metric]
    )
    st.subheader(
        f"{selected_comparison_sector} — fiscal year {int(latest_company_year)}"
    )
    st.caption("Sorted by value, not by whether the metric is favorable.")
    st.dataframe(
        sector_comparison.sort_values(
            selected_history_metric, ascending=False, kind="stable"
        ).reset_index(drop=True),
        hide_index=True,
        width="stretch",
    )

st.download_button(
    "Download three-year history as CSV",
    data=history.to_csv(index=False).encode("utf-8"),
    file_name="sp500_three_year_historical_metrics.csv",
    mime="text/csv",
)
