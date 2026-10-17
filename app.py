from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


DATA_PATH = Path(__file__).resolve().with_name("sp500_screening_results.csv")
SCORE_COLUMN = "Financial Strength Score (0-9)"
FILTER_COLUMNS = {
    "STA": "STA",
    "SNOA": "SNOA",
    "Altman Z-Score": "Altman Z",
    "Financial Strength Score": SCORE_COLUMN,
}
SCORE_COMPONENT_COLUMNS = [
    "Profitability Score (0-4)",
    "Leverage Score",
    "Liquidity Score",
    "Equity Issuance Score",
    "Funding Score (0-3)",
    "Efficiency Score (0-2)",
]
DISPLAY_COLUMNS = [
    "Ticker",
    "Latest Fiscal Year",
    "STA",
    "SNOA",
    "Altman Z",
    "Risk Classification",
    SCORE_COLUMN,
    *SCORE_COMPONENT_COLUMNS,
]


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    """Load saved screening results without fetching stock data."""
    return pd.read_csv(path)


def prepare_data(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Reuse the saved aggregate score, or safely derive one from available scores."""
    prepared = df.copy()
    if SCORE_COLUMN in prepared.columns:
        prepared[SCORE_COLUMN] = pd.to_numeric(prepared[SCORE_COLUMN], errors="coerce")
        return prepared, "The saved aggregate score from the CSV is being used."

    profitability = "Profitability Score (0-4)"
    leverage = "Leverage Score"
    liquidity = "Liquidity Score"
    issuance = "Equity Issuance Score"
    funding = "Funding Score (0-3)"
    efficiency = "Efficiency Score (0-2)"

    score_inputs = [profitability, leverage, liquidity, issuance, funding, efficiency]
    for column in score_inputs:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")

    if all(column in prepared.columns for column in [profitability, leverage, liquidity, issuance, efficiency]):
        # Funding Score already sums leverage, liquidity, and equity issuance.
        # Use its three underlying signals instead when deriving from components.
        formula_columns = [profitability, leverage, liquidity, issuance, efficiency]
        prepared[SCORE_COLUMN] = prepared[formula_columns].sum(axis=1, min_count=len(formula_columns))
        return prepared, (
            "The aggregate was derived as Profitability + Leverage + Liquidity + "
            "Equity Issuance + Efficiency. Funding Score is excluded because it "
            "already totals the three funding signals."
        )

    if all(column in prepared.columns for column in [profitability, funding, efficiency]):
        formula_columns = [profitability, funding, efficiency]
        prepared[SCORE_COLUMN] = prepared[formula_columns].sum(axis=1, min_count=len(formula_columns))
        return prepared, (
            "The aggregate was derived as Profitability + Funding + Efficiency. "
            "Rows missing any of these scores remain unscored."
        )

    prepared[SCORE_COLUMN] = float("nan")
    return prepared, "A combined score could not be derived because required score columns are unavailable."


def slider_settings(series: pd.Series) -> dict | None:
    """Return actual data bounds and safe Streamlit slider settings."""
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return None

    data_min = float(values.min())
    data_max = float(values.max())
    slider_min = data_min
    slider_max = data_max

    if data_min == data_max:
        # Streamlit requires different slider endpoints for a constant column.
        padding = max(abs(data_min) * 0.1, 1.0)
        slider_min = data_min - padding
        slider_max = data_max + padding

    span = slider_max - slider_min
    if values.astype(float).map(lambda value: value.is_integer()).all():
        step = 1.0
    else:
        step = max(span / 1000, 0.000001)

    return {
        "data_min": data_min,
        "data_max": data_max,
        "slider_min": slider_min,
        "slider_max": slider_max,
        "step": step,
    }


def format_bound(value: float) -> str:
    return f"{value:,.6g}"


def reset_filters(filter_keys: list[str]) -> None:
    for key in filter_keys:
        st.session_state.pop(key, None)
    st.session_state.pop("ticker_search", None)


def apply_filters(
    df: pd.DataFrame,
    selected_ranges: dict[str, tuple[float, float]],
    ticker_query: str,
) -> pd.DataFrame:
    filtered = df.copy()

    if ticker_query.strip() and "Ticker" in filtered.columns:
        filtered = filtered[
            filtered["Ticker"].astype("string").str.contains(
                ticker_query.strip(), case=False, na=False, regex=False
            )
        ]

    for column, selected_range in selected_ranges.items():
        if column not in filtered.columns:
            continue
        values = pd.to_numeric(filtered[column], errors="coerce")
        filtered = filtered[values.notna() & values.between(*selected_range)]

    return filtered.reset_index(drop=True)


def get_risk_category(row: pd.Series) -> str | None:
    categories = {"Distress", "Grey", "Safe"}
    saved_category = row.get("Risk Classification")
    if pd.notna(saved_category) and str(saved_category).strip().title() in categories:
        return str(saved_category).strip().title()

    z_score = pd.to_numeric(pd.Series([row.get("Altman Z")]), errors="coerce").iloc[0]
    if pd.isna(z_score):
        return None
    if z_score > 2.99:
        return "Safe"
    if z_score >= 1.81:
        return "Grey"
    return "Distress"


def show_charts(filtered: pd.DataFrame) -> None:
    st.subheader("Company rankings and risk categories")

    if SCORE_COLUMN in filtered.columns and "Ticker" in filtered.columns:
        ranking = filtered[["Ticker", SCORE_COLUMN]].dropna().nlargest(20, SCORE_COLUMN)
        if ranking.empty:
            st.info("No companies with a financial strength score match the current filters.")
        else:
            ranking = ranking.sort_values(SCORE_COLUMN, ascending=True)
            chart = px.bar(
                ranking,
                x=SCORE_COLUMN,
                y="Ticker",
                orientation="h",
                title="Top 20 matching companies by Financial Strength Score",
                labels={SCORE_COLUMN: "Financial Strength Score", "Ticker": "Company"},
                hover_data={SCORE_COLUMN: ":.2f"},
            )
            st.plotly_chart(chart, width="stretch")
    else:
        st.info("The ranking chart is unavailable because ticker or score data is missing.")

    risk_counts = {"Distress": 0, "Grey": 0, "Safe": 0}
    unclassified_count = 0
    for _, row in filtered.iterrows():
        category = get_risk_category(row)
        if category in risk_counts:
            risk_counts[category] += 1
        else:
            unclassified_count += 1

    risk_df = pd.DataFrame(
        {"Risk Category": list(risk_counts), "Companies": list(risk_counts.values())}
    )
    risk_chart = px.bar(
        risk_df,
        x="Risk Category",
        y="Companies",
        category_orders={"Risk Category": ["Distress", "Grey", "Safe"]},
        title="Companies by Altman Z-Score category",
        color="Risk Category",
        color_discrete_map={"Distress": "#d9534f", "Grey": "#f0ad4e", "Safe": "#5cb85c"},
    )
    st.plotly_chart(risk_chart, width="stretch")
    if unclassified_count:
        st.caption(f"{unclassified_count} matching companies could not be classified because their Altman Z-Score is missing.")


def show_company_details(filtered: pd.DataFrame) -> None:
    st.subheader("Company details")
    if filtered.empty or "Ticker" not in filtered.columns:
        st.info("No matching company is available to select.")
        return

    tickers = sorted(filtered["Ticker"].dropna().astype(str).unique())
    if not tickers:
        st.info("No ticker identifiers are available in the filtered data.")
        return

    ticker = st.selectbox("Choose a company", tickers)
    company = filtered[filtered["Ticker"].astype(str) == ticker].iloc[0]
    detail_columns = [column for column in DISPLAY_COLUMNS if column in filtered.columns]
    details = company[detail_columns].map(
        lambda value: "" if pd.isna(value) else str(value)
    )
    st.dataframe(
        details.to_frame(name="Value"),
        width="stretch",
    )


def main() -> None:
    st.set_page_config(page_title="S&P 500 Financial Screen", layout="wide")
    st.title("S&P 500 Financial Screening Dashboard")

    try:
        df = load_data(str(DATA_PATH))
    except FileNotFoundError:
        st.error(f"Could not find `{DATA_PATH.name}`. Place it in the same folder as `app.py`.")
        st.stop()
    except pd.errors.EmptyDataError:
        st.error(f"`{DATA_PATH.name}` is empty.")
        st.stop()

    if df.empty:
        st.error("The screening CSV has no company rows.")
        st.stop()

    df, score_note = prepare_data(df)
    st.caption(score_note)

    available_filters = {
        label: column for label, column in FILTER_COLUMNS.items() if column in df.columns
    }
    missing_filters = [label for label in FILTER_COLUMNS if label not in available_filters]

    if missing_filters:
        st.warning("These filters are unavailable because their CSV columns are missing: " + ", ".join(missing_filters))

    slider_data = {
        label: slider_settings(df[column])
        for label, column in available_filters.items()
    }
    usable_filters = {
        label: column for label, column in available_filters.items()
        if slider_data[label] is not None
    }
    empty_filters = [label for label in available_filters if slider_data[label] is None]

    with st.sidebar:
        st.header("Filters")
        ticker_query = st.text_input("Search ticker", key="ticker_search")
        selected_ranges = {}
        filter_keys = [f"range_{label}" for label in usable_filters]

        for label, column in usable_filters.items():
            settings = slider_data[label]
            key = f"range_{label}"
            default_range = (settings["data_min"], settings["data_max"])
            if key not in st.session_state:
                st.session_state[key] = default_range

            selected = st.slider(
                label,
                min_value=settings["slider_min"],
                max_value=settings["slider_max"],
                step=settings["step"],
                key=key,
            )
            selected_ranges[column] = selected
            st.caption(
                f"Data: {format_bound(settings['data_min'])} to "
                f"{format_bound(settings['data_max'])} · Selected: "
                f"{format_bound(selected[0])} to {format_bound(selected[1])}"
            )
            missing_count = pd.to_numeric(df[column], errors="coerce").isna().sum()
            if missing_count:
                st.caption(f"{missing_count} rows with missing {label} are excluded by this filter.")

        for label in empty_filters:
            st.caption(f"{label}: unavailable (no numeric values in the CSV)")

        st.button(
            "Reset filters",
            on_click=reset_filters,
            args=(filter_keys,),
            width="stretch",
        )

    filtered = apply_filters(df, selected_ranges, ticker_query)

    st.subheader("Summary")
    summary_columns = st.columns(3)
    summary_columns[0].metric("Companies remaining", len(filtered))
    summary_columns[1].metric("Companies in source CSV", len(df))
    average_score = filtered[SCORE_COLUMN].mean() if SCORE_COLUMN in filtered.columns else float("nan")
    summary_columns[2].metric(
        "Average Financial Strength Score",
        f"{average_score:.2f}" if pd.notna(average_score) else "Unavailable",
    )

    if filtered.empty:
        st.warning("No companies match the current filters. Widen a range or clear the ticker search.")
    else:
        show_charts(filtered)

    st.subheader("Filtered companies")
    table_columns = [column for column in DISPLAY_COLUMNS if column in filtered.columns]
    if filtered.empty:
        st.info("The filtered table is empty.")
    elif table_columns:
        st.dataframe(filtered[table_columns], width="stretch", hide_index=True)
    else:
        st.dataframe(filtered, width="stretch", hide_index=True)

    show_company_details(filtered)
    st.download_button(
        "Download filtered CSV",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name="filtered_screening_results.csv",
        mime="text/csv",
        width="stretch",
    )


if __name__ == "__main__":
    main()
