from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


DATA_FILE = Path(__file__).parent / "sp500_all_company_metrics.csv"
HISTORY_FILE = Path(__file__).parent / "sp500_three_year_historical_metrics.csv"
IDENTIFIER_COLUMNS = ["Company", "Ticker", "Sector", "Industry", "Reporting Currency"]
STATUS_COLUMN = "Download Status"
METRIC_COLUMNS = [
    "Gross Profitability",
    "Gross Margin (%)",
    "Operating Margin (%)",
    "EBITDA Margin (%)",
    "Net Profit Margin (%)",
    "Return on Assets (%)",
    "Return on Equity (%)",
    "Asset Turnover",
    "Operating Cash Flow / Assets (%)",
    "EPS (Basic)",
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
RANKING_GROUPS = {
    "Quality": [
        ("Gross Profitability", True),
        ("Gross Margin (%)", True),
        ("Operating Margin (%)", True),
        ("EBITDA Margin (%)", True),
        ("Net Profit Margin (%)", True),
        ("Return on Assets (%)", True),
        ("Operating Cash Flow / Assets (%)", True),
    ],
    "Growth": [
        ("EPS Growth (%)", True),
        ("FCF Growth (%)", True),
    ],
    "Value": [("P/E Ratio", False)],
    "Financial Strength": [
        ("Debt/Equity", False),
        ("Current Ratio", "sector_median"),
    ],
    "Capital Allocation": [("Buyback Yield (%)", True)],
}
RANKING_COLUMNS = [
    "Overall Rank",
    "Sector Rank",
    "Composite Score",
    *[f"{group} Score" for group in RANKING_GROUPS],
]
METADATA_COLUMNS = [
    "Calculation Timestamp",
    "Formula Version",
    "Restatement Flag",
]
HISTORY_METRICS = [
    "Revenue",
    "Net Income",
    "EPS (Basic)",
    "Free Cash Flow",
    "Gross Profitability",
    "Gross Margin (%)",
    "Operating Margin (%)",
    "EBITDA Margin (%)",
    "Net Profit Margin (%)",
    "Return on Assets (%)",
    "Return on Equity (%)",
    "Operating Cash Flow / Assets (%)",
    "Asset Turnover",
    "Debt/Equity",
    "Current Ratio",
    "EPS Growth (%)",
    "FCF Growth (%)",
    "STA (%)",
    "SNOA (%)",
]
MONETARY_COLUMNS = {"Revenue", "Net Income", "Free Cash Flow"}
FORMULA_VERSION = "1.1.0"
SNAPSHOT_LABEL = "November 20, 2026"


st.set_page_config(page_title="S&P 500 Stock Screener", page_icon="📊", layout="wide")


@st.cache_data
def load_metrics() -> pd.DataFrame:
    if not DATA_FILE.is_file():
        raise FileNotFoundError(f"Dataset not found: {DATA_FILE.name}")

    data = pd.read_csv(DATA_FILE)
    required = {
        *IDENTIFIER_COLUMNS,
        *METRIC_COLUMNS,
        *METADATA_COLUMNS,
        STATUS_COLUMN,
    }
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Dataset is missing columns: {', '.join(sorted(missing))}")
    for column in METRIC_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data


@st.cache_data
def load_history() -> pd.DataFrame:
    if not HISTORY_FILE.is_file():
        raise FileNotFoundError(f"Historical dataset not found: {HISTORY_FILE.name}")

    data = pd.read_csv(HISTORY_FILE)
    required = {
        "Company",
        "Ticker",
        "Sector",
        "Reporting Currency",
        "Fiscal Year",
        *HISTORY_METRICS,
        *METADATA_COLUMNS,
    }
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(
            f"Historical dataset is missing columns: {', '.join(sorted(missing))}"
        )
    data["Fiscal Year"] = pd.to_numeric(data["Fiscal Year"], errors="coerce")
    for column in HISTORY_METRICS:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["Fiscal Year"])


def add_rankings(data: pd.DataFrame) -> pd.DataFrame:
    ranked = data.copy()
    usable = ranked[STATUS_COLUMN].eq("OK")
    group_scores = pd.DataFrame(index=ranked.index)

    for group_name, factors in RANKING_GROUPS.items():
        factor_scores = []
        for metric, direction in factors:
            values = pd.to_numeric(ranked[metric], errors="coerce").where(usable)
            if metric in {"P/E Ratio", "Debt/Equity", "Current Ratio"}:
                values = values.where(values > 0)

            if direction == "sector_median":
                sector_medians = values.groupby(
                    ranked["Sector"], dropna=False
                ).transform("median")
                relative = -(values - sector_medians).abs()
                score = relative.groupby(
                    ranked["Sector"], dropna=False
                ).rank(pct=True) * 100
            else:
                score = values.groupby(
                    ranked["Sector"], dropna=False
                ).rank(pct=True, ascending=bool(direction)) * 100
            factor_scores.append(score)

        group_scores[f"{group_name} Score"] = pd.concat(
            factor_scores, axis=1
        ).mean(axis=1)

    ranked = pd.concat([ranked, group_scores], axis=1)
    ranked["Composite Score"] = group_scores.mean(axis=1)
    eligible = usable & group_scores.notna().sum(axis=1).ge(3)
    ranked["Overall Rank"] = np.nan
    ranked["Sector Rank"] = np.nan
    ranked.loc[eligible, "Overall Rank"] = (
        ranked.loc[eligible, "Composite Score"]
        .rank(method="min", ascending=False)
        .astype(int)
    )
    ranked.loc[eligible, "Sector Rank"] = (
        ranked.loc[eligible]
        .groupby("Sector", dropna=False)["Composite Score"]
        .rank(method="min", ascending=False)
        .astype(int)
    )
    ranked["Overall Rank"] = ranked["Overall Rank"].astype("Int64")
    ranked["Sector Rank"] = ranked["Sector Rank"].astype("Int64")
    return ranked


def format_number(value: object) -> str:
    if pd.isna(value):
        return "—"
    rounded = f"{float(value):,.2f}".rstrip("0").rstrip(".")
    return "0" if rounded in {"-0", ""} else rounded


def format_amount(value: object, currency: object) -> str:
    if pd.isna(value):
        return "—"
    amount = float(value)
    absolute = abs(amount)
    for threshold, suffix in (
        (1_000_000_000_000, "T"),
        (1_000_000_000, "B"),
        (1_000_000, "M"),
        (1_000, "K"),
    ):
        if absolute >= threshold:
            compact = f"{format_number(amount / threshold)}{suffix}"
            break
    else:
        compact = format_number(amount)
    currency_label = str(currency).strip() if pd.notna(currency) else ""
    return f"{currency_label} {compact}".strip()


def show_table(data: pd.DataFrame, *, height: int | None = None) -> None:
    display_data = data.copy()
    formatters = {
        column: format_number
        for column in display_data.select_dtypes(include="number").columns
    }
    currency = display_data.get(
        "Reporting Currency", pd.Series("", index=display_data.index)
    )
    for column in MONETARY_COLUMNS.intersection(display_data.columns):
        display_data[column] = [
            format_amount(value, currency.loc[index])
            for index, value in display_data[column].items()
        ]
        formatters.pop(column, None)
    options = {"hide_index": True, "width": "stretch"}
    if height is not None:
        options["height"] = height
    st.dataframe(
        display_data.style.format(formatter=formatters, na_rep="—"),
        **options,
    )


st.title("S&P 500 Stock Screener")
st.caption(
    f"Financial statement snapshot: {SNAPSHOT_LABEL}. This is not live market data "
    "or investment advice."
)

try:
    metrics = load_metrics()
    history = load_history()
except (FileNotFoundError, ValueError, pd.errors.ParserError) as error:
    st.error(f"Could not load stock data: {error}")
    st.stop()

metrics = add_rankings(metrics)
successful = metrics[STATUS_COLUMN].eq("OK")
sectors = sorted(metrics["Sector"].dropna().astype(str).unique())

st.sidebar.header("Active screen")
include_download_issues = st.sidebar.checkbox("Include incomplete download rows", value=False)
selected_sectors = st.sidebar.multiselect("Sectors", sectors, default=sectors)
search = st.sidebar.text_input("Company or ticker contains")
selected_metrics = st.sidebar.multiselect(
    "Filter by financial metrics",
    METRIC_COLUMNS,
    help="Rows missing a selected metric are excluded. Missing values are never treated as zero.",
)

screen = metrics.copy()
if not include_download_issues:
    screen = screen[successful]
if selected_sectors:
    screen = screen[screen["Sector"].isin(selected_sectors)]
else:
    screen = screen.iloc[0:0]
if search.strip():
    query = search.strip()
    matches = (
        screen["Company"].fillna("").str.contains(query, case=False, regex=False)
        | screen["Ticker"].fillna("").str.contains(query, case=False, regex=False)
    )
    screen = screen[matches]

for metric in selected_metrics:
    values = metrics[metric].dropna()
    if values.empty:
        st.sidebar.caption(f"{metric}: no reported values")
        screen = screen.iloc[0:0]
        continue

    low, high = float(values.min()), float(values.max())
    if low == high:
        st.sidebar.caption(f"{metric}: {low:.3g} (only reported value)")
        screen = screen[screen[metric].eq(low)]
        continue

    selected_range = st.sidebar.slider(
        metric,
        min_value=low,
        max_value=high,
        value=(low, high),
        key=f"range_{metric}",
        help="Range is based on all available records, before other filters.",
    )
    screen = screen[
        screen[metric].notna()
        & screen[metric].between(selected_range[0], selected_range[1])
    ]

section = st.radio(
    "Section",
    ["Overview", "Stock Screener", "Methodology"],
    horizontal=True,
    label_visibility="collapsed",
)

if section == "Overview":
    st.header("Overview")
    metric_columns = st.columns(4)
    metric_columns[0].metric("S&P 500 universe", f"{len(metrics):,}")
    metric_columns[1].metric("Successful downloads", f"{int(successful.sum()):,}")
    metric_columns[2].metric("Passing active screen", f"{len(screen):,}")
    metric_columns[3].metric("Incomplete downloads", f"{int((~successful).sum()):,}")

    st.info(
        "Ranking converts metrics to sector-relative percentiles, averages them within "
        "five equally weighted groups—Quality, Growth, Value, Financial Strength, and "
        "Capital Allocation—then averages available group scores. A company needs at "
        "least 3 group scores; missing values are not imputed."
    )
    st.subheader("Companies passing the active screen")
    show_table(
        screen[IDENTIFIER_COLUMNS + RANKING_COLUMNS + METRIC_COLUMNS].sort_values(
            "Overall Rank", na_position="last"
        )
    )

    with st.expander("Complete company financial data", expanded=False):
        st.caption(
            "All companies and calculated metrics in the bundled snapshot, including "
            "incomplete-download rows. Missing values appear as —."
        )
        show_table(metrics)

    st.subheader("Metric distributions")
    st.caption(
        "Histograms show the distribution among companies with successful downloads. "
        "Missing values are reported for each metric and are not treated as zero."
    )
    distribution_groups = {
        "Profitability and returns": [
            "Gross Profitability",
            "Gross Margin (%)",
            "Operating Margin (%)",
            "EBITDA Margin (%)",
            "Net Profit Margin (%)",
            "Return on Assets (%)",
            "Return on Equity (%)",
            "Asset Turnover",
            "Operating Cash Flow / Assets (%)",
        ],
        "Valuation and capital allocation": [
            "EPS (Basic)",
            "Buyback Yield (%)",
            "Net Equity Issuance (%)",
            "P/E Ratio",
        ],
        "Financial strength": ["Debt/Equity", "Current Ratio"],
        "Growth and accounting": [
            "EPS Growth (%)",
            "FCF Growth (%)",
            "STA (%)",
            "SNOA (%)",
        ],
    }
    for group_name, group_metrics in distribution_groups.items():
        with st.expander(group_name, expanded=False):
            for start in range(0, len(group_metrics), 2):
                chart_columns = st.columns(2)
                for column, metric in zip(chart_columns, group_metrics[start : start + 2]):
                    values = metrics.loc[successful, metric].dropna()
                    missing_count = int(successful.sum() - len(values))
                    with column:
                        st.markdown(f"**{metric}**")
                        st.caption(
                            f"{len(values):,} available · {missing_count:,} missing"
                        )
                        if values.empty:
                            st.info("No values available.")
                            continue
                        counts, edges = np.histogram(values, bins=min(20, max(1, len(values))))
                        centers = np.round((edges[:-1] + edges[1:]) / 2, 2)
                        chart = pd.DataFrame(
                            {"Companies": counts},
                            index=pd.Index(centers, name=metric),
                        )
                        st.bar_chart(
                            chart,
                            x_label=metric,
                            y_label="Companies",
                            height=220,
                        )

elif section == "Stock Screener":
    st.header("Stock Screener")
    st.caption(f"{len(screen):,} of {len(metrics):,} companies pass the active filters.")
    st.info(
        "Scores are sector-relative 0–100 percentiles, averaged within five equally "
        "weighted groups: Quality, Growth, Value, Financial Strength, and Capital "
        "Allocation. At least 3 groups are required for an overall rank; missing values "
        "are not imputed. Higher is better except P/E and Debt/Equity, which are "
        "reverse-ranked; Current Ratio scores by closeness to its sector median. "
        "Buyback Yield represents capital allocation; its inverse, Net Equity Issuance, "
        "is excluded to avoid double-counting."
    )
    normalization = st.sidebar.selectbox(
        "Comparison columns",
        ["None", "Percentile rank (0–100)", "Z-score"],
    )

    result = screen[IDENTIFIER_COLUMNS + RANKING_COLUMNS + METRIC_COLUMNS].copy()
    if normalization == "Percentile rank (0–100)":
        for metric in selected_metrics or METRIC_COLUMNS:
            result[f"{metric} Percentile"] = metrics[metric].rank(pct=True) * 100
    elif normalization == "Z-score":
        for metric in selected_metrics or METRIC_COLUMNS:
            deviation = metrics[metric].std()
            if pd.isna(deviation) or deviation == 0:
                result[f"{metric} Z-Score"] = np.nan
            else:
                result[f"{metric} Z-Score"] = (
                    result[metric] - metrics[metric].mean()
                ) / deviation

    result = result.sort_values(
        ["Overall Rank", "Ticker"], kind="stable", na_position="last"
    ).reset_index(drop=True)
    show_table(result, height=600)
    st.download_button(
        "Download passing screen as CSV",
        data=result.to_csv(index=False, na_rep="").encode("utf-8"),
        file_name="sp500_screen_results.csv",
        mime="text/csv",
        disabled=result.empty,
    )

    st.subheader("Three-year historical trends")
    history_tickers = sorted(history["Ticker"].dropna().astype(str).unique())
    history_companies = (
        history.drop_duplicates("Ticker").set_index("Ticker")["Company"].fillna("")
    )
    controls = st.columns(3)
    ticker = controls[0].selectbox(
        "Company",
        history_tickers,
        format_func=lambda value: f"{value} — {history_companies.get(value, value)}",
    )
    history_metric = controls[1].selectbox("Historical metric", HISTORY_METRICS)
    comparison_sector = controls[2].selectbox(
        "Sector comparison",
        ["No comparison", *sorted(history["Sector"].dropna().astype(str).unique())],
    )

    company_history = history[history["Ticker"].astype(str).eq(ticker)].sort_values(
        "Fiscal Year"
    )
    chart_history = company_history.dropna(subset=[history_metric])
    if chart_history.empty:
        st.info(f"No {history_metric} observations are available for this company.")
    else:
        chart_values = chart_history.set_index("Fiscal Year")[[history_metric]].copy()
        chart_label = history_metric
        if history_metric in MONETARY_COLUMNS:
            currency = chart_history["Reporting Currency"].dropna()
            currency_label = currency.iloc[0] if not currency.empty else "Currency"
            maximum = chart_values[history_metric].abs().max()
            divisor, suffix = next(
                (
                    (threshold, unit)
                    for threshold, unit in (
                        (1_000_000_000_000, "T"),
                        (1_000_000_000, "B"),
                        (1_000_000, "M"),
                        (1_000, "K"),
                    )
                    if maximum >= threshold
                ),
                (1, ""),
            )
            chart_values[history_metric] /= divisor
            chart_label = f"{history_metric} ({currency_label} {suffix})".strip()
        st.line_chart(
            chart_values,
            x_label="Fiscal year",
            y_label=chart_label,
        )
        show_table(chart_history[["Fiscal Year", history_metric]].reset_index(drop=True))

    if comparison_sector != "No comparison":
        selected_year = company_history["Fiscal Year"].max()
        peers = history[
            history["Sector"].eq(comparison_sector)
            & history["Fiscal Year"].eq(selected_year)
        ][["Company", "Ticker", "Reporting Currency", history_metric]].dropna(
            subset=[history_metric]
        )
        st.caption(
            f"Sector comparison for fiscal year {int(selected_year)}. "
            "Monetary values are kept separate by reporting currency."
        )
        for currency, currency_peers in peers.groupby("Reporting Currency", dropna=False):
            st.markdown(f"**{currency if pd.notna(currency) else 'Currency unavailable'}**")
            show_table(
                currency_peers.sort_values(
                    history_metric, ascending=False, kind="stable"
                ).reset_index(drop=True)
            )

    st.download_button(
        "Download three-year history as CSV",
        data=history.to_csv(index=False, na_rep="").encode("utf-8"),
        file_name="sp500_three_year_historical_metrics.csv",
        mime="text/csv",
    )

else:
    st.header("Methodology")
    st.caption(
        f"Formula version {FORMULA_VERSION} · Data snapshot {SNAPSHOT_LABEL}. "
        "Formula definitions below describe the metrics calculated by this app."
    )

    st.subheader("Metric dictionary")
    formula_rows = [
        ("Gross Profitability", "Gross profit ÷ total assets"),
        ("Gross Margin (%)", "Gross profit ÷ revenue × 100"),
        ("Operating Margin (%)", "Operating income ÷ revenue × 100"),
        ("EBITDA Margin (%)", "(Operating income + depreciation and amortization) ÷ revenue × 100"),
        ("Net Profit Margin (%)", "Net income ÷ revenue × 100"),
        ("Return on Assets (%)", "Net income ÷ total assets × 100"),
        ("Return on Equity (%)", "Net income ÷ total equity × 100"),
        ("Asset Turnover", "Revenue ÷ total assets"),
        ("Operating Cash Flow / Assets (%)", "Operating cash flow ÷ total assets × 100"),
        ("EPS (Basic)", "Net income ÷ basic weighted-average shares"),
        ("Buyback Yield (%)", "(Share repurchases − share issuance) ÷ current market capitalization × 100"),
        ("Net Equity Issuance (%)", "(Share issuance − share repurchases) ÷ current market capitalization × 100"),
        ("P/E Ratio", "Current share price ÷ positive trailing EPS"),
        ("Debt/Equity", "Total debt ÷ total equity"),
        ("Current Ratio", "Current assets ÷ current liabilities"),
        ("EPS Growth (%)", "(Current annual EPS − prior annual EPS) ÷ absolute prior annual EPS × 100"),
        ("FCF Growth (%)", "(Current annual free cash flow − prior annual free cash flow) ÷ absolute prior annual free cash flow × 100"),
        ("STA (%)", "(Net income − operating cash flow) ÷ total assets × 100"),
        ("SNOA (%)", "(Total debt + total equity − cash and short-term investments) ÷ prior-year total assets × 100"),
    ]
    show_table(pd.DataFrame(formula_rows, columns=["Metric", "Formula"]))

    st.subheader("Ranking")
    st.markdown(
        "Each metric is converted to a sector-relative percentile. Metric percentiles "
        "are averaged within **Quality**, **Growth**, **Value**, **Financial Strength**, "
        "and **Capital Allocation**, then the five group scores are averaged equally. "
        "At least three available group scores are required to rank a company. Missing "
        "values are excluded, not imputed; Net Equity Issuance is omitted from the score "
        "because it is the inverse of Buyback Yield."
    )

    st.subheader("Calculation policy")
    st.markdown(
        """
- **Missing values:** Missing inputs produce no metric. They display as “—”, are excluded from ranks, and are never replaced with zero or an average.
- **Invalid denominators:** Ratios are omitted when a denominator is missing, zero, or makes the result meaningless. P/E requires positive earnings; ROE and Debt/Equity require positive book equity.
- **Period alignment:** Calculated metrics use the annual fiscal periods provided by the source. Companies with different fiscal year ends are not pooled into calendar periods.
- **Currency:** Each row carries the provider-reported reporting currency. Ratios use numerator and denominator from the same company; monetary sector comparisons are grouped by currency.
- **Share counts:** Basic EPS uses net income divided by reported basic weighted-average shares. Counts are used as supplied; split adjustment by the provider is not independently verified and the app applies no additional adjustment.
- **Restatements:** The provider does not expose a reliable restatement flag in this dataset. The field is missing, rather than marked false; latest revised provider values are used where supplied.
- **Timestamps and versioning:** Every company row records its calculation timestamp and formula version. The bundled snapshot is static and is not recalculated by the deployed app.
- **Growth:** Growth uses the absolute prior-period value in the denominator. A zero or missing prior value produces no growth metric.
"""
    )

    st.subheader("Data quality")
    status_counts = (
        metrics[STATUS_COLUMN].fillna("Status unavailable").value_counts().rename_axis("Download status").reset_index(name="Companies")
    )
    show_table(status_counts)

    coverage = (
        metrics[METRIC_COLUMNS]
        .notna()
        .sum()
        .rename("Available values")
        .to_frame()
        .assign(**{"Universe size": len(metrics)})
        .assign(**{"Coverage (%)": lambda frame: frame["Available values"] / len(metrics) * 100})
        .reset_index(names="Metric")
        .sort_values("Coverage (%)")
    )
    show_table(coverage)
    st.warning(
        "Yahoo Finance coverage can be incomplete, revised, or inconsistent; unusual "
        "values and cross-company accounting differences require review."
    )
    st.caption(
        "These metrics are screening aids, not audited financial data or investment advice."
    )
