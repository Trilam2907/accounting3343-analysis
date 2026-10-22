from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
UNIVERSE_PATH = APP_DIR / "universe.csv"
SCREENING_PATH = APP_DIR / "sp500_screening_results.csv"
SCORE_COLUMN = "Financial Strength Score (0-9)"
SCORE_COMPONENTS = [
    "Profitability Score (0-4)",
    "Funding Score (0-3)",
    "Efficiency Score (0-2)",
]
RAW_METRIC_COLUMNS = [
    "Net Income",
    "Operating Cash Flow",
    "Total Assets",
    "Prior-Year Total Assets",
    "Total Debt",
    "Equity",
    "Cash",
    "Working Capital",
    "Retained Earnings",
    "EBIT",
    "Market Value of Equity",
    "Total Liabilities",
    "Sales",
]
FLAG_COLUMNS = [
    "STA percentile flag",
    "SNOA percentile flag",
    "Altman Z flag",
]
CONCLUSION_BY_FLAGS = {
    3: "High-priority short research candidate",
    2: "Potential short research candidate",
    1: "Watchlist — limited warning signals",
    0: "Not flagged by this screen",
}
INDUSTRY_OPTIONS = [
    "All industries",
    "Financial Services",
    "Energy",
    "Technology",
    "Other",
]
SECTOR_COLUMN_NAMES = {
    "sector",
    "gics sector",
    "industry",
    "gics industry",
}


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    """Read the saved CSV only; no stock-data requests are made by the dashboard."""
    return pd.read_csv(path)


def source_csv_path() -> Path:
    """Prefer the full universe file and fall back to the generated results CSV."""
    return UNIVERSE_PATH if UNIVERSE_PATH.is_file() else SCREENING_PATH


def find_sector_column(data: pd.DataFrame) -> str | None:
    """Find an existing sector/industry field without inferring from company names."""
    for column in data.columns:
        if str(column).strip().casefold() in SECTOR_COLUMN_NAMES:
            return column
    return None


def classify_sector(value: object) -> str | None:
    """Map a provided sector label into one of the dashboard's four groups."""
    if pd.isna(value) or not str(value).strip():
        return None

    sector = str(value).strip().casefold()
    if any(
        term in sector
        for term in (
            "financial",
            "bank",
            "insurance",
            "capital market",
            "asset management",
            "consumer finance",
            "mortgage",
        )
    ):
        return "Financial Services"
    if any(
        term in sector
        for term in (
            "energy",
            "oil",
            "gas",
            "petroleum",
            "coal",
            "drilling",
            "energy equipment",
        )
    ):
        return "Energy"
    if any(
        term in sector
        for term in (
            "technology",
            "software",
            "semiconductor",
            "information technology",
            "computer",
            "electronic",
        )
    ):
        return "Technology"
    return "Other"


def calculate_metrics_from_raw_inputs(data: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Recalculate the requested ratios when their source values are available."""
    result = data.copy()
    if not all(column in result.columns for column in RAW_METRIC_COLUMNS):
        return result, False

    numeric = result[RAW_METRIC_COLUMNS].apply(pd.to_numeric, errors="coerce")
    total_assets = numeric["Total Assets"]
    prior_assets = numeric["Prior-Year Total Assets"]

    sta_valid = (
        numeric["Net Income"].notna()
        & numeric["Operating Cash Flow"].notna()
        & total_assets.gt(0)
    )
    result["STA"] = (
        (numeric["Net Income"] - numeric["Operating Cash Flow"]) / total_assets
    ).where(sta_valid)

    snoa_valid = (
        numeric["Total Debt"].notna()
        & numeric["Equity"].notna()
        & numeric["Cash"].notna()
        & prior_assets.gt(0)
    )
    result["SNOA"] = (
        (numeric["Total Debt"] + numeric["Equity"] - numeric["Cash"])
        / prior_assets
    ).where(snoa_valid)

    altman_valid = (
        total_assets.gt(0)
        & numeric["Working Capital"].notna()
        & numeric["Retained Earnings"].notna()
        & numeric["EBIT"].notna()
        & numeric["Market Value of Equity"].notna()
        & numeric["Total Liabilities"].gt(0)
        & numeric["Sales"].notna()
    )
    result["Altman Z"] = (
        1.2 * numeric["Working Capital"] / total_assets
        + 1.4 * numeric["Retained Earnings"] / total_assets
        + 3.3 * numeric["EBIT"] / total_assets
        + 0.6 * numeric["Market Value of Equity"] / numeric["Total Liabilities"]
        + numeric["Sales"] / total_assets
    ).where(altman_valid)
    return result, True


def validate_p_score(data: pd.DataFrame) -> tuple[bool, str]:
    """Validate the saved nine-signal total against its three documented groups."""
    required = [SCORE_COLUMN, *SCORE_COMPONENTS]
    missing = [column for column in required if column not in data.columns]
    if missing:
        return False, "P-Score unavailable; missing columns: " + ", ".join(missing)

    scores = data[SCORE_COMPONENTS + [SCORE_COLUMN]].apply(pd.to_numeric, errors="coerce")
    expected = scores[SCORE_COMPONENTS].sum(axis=1, min_count=len(SCORE_COMPONENTS))
    complete = expected.notna() & scores[SCORE_COLUMN].notna()
    if not complete.any():
        return False, "P-Score could not be validated because no complete score rows are present."
    if not expected[complete].eq(scores.loc[complete, SCORE_COLUMN]).all():
        return False, "Saved P-Score does not match Profitability + Funding + Efficiency."

    incomplete_count = int((~complete).sum())
    message = "P-Score verified as Profitability (4) + Funding (3) + Efficiency (2), maximum 9."
    if incomplete_count:
        message += f" {incomplete_count} rows have incomplete score inputs and are not fully score-confirmed."
    return True, message


def add_percentile_flags(
    data: pd.DataFrame,
    accrual_percentile: int,
    altman_z_cutoff: float,
) -> pd.DataFrame:
    """Rank STA/SNOA across the whole input universe and calculate its three flags."""
    result = data.copy()
    for metric, percentile_column in [
        ("STA", "STA percentile"),
        ("SNOA", "SNOA percentile"),
    ]:
        if metric not in result.columns:
            result[metric] = float("nan")
        values = pd.to_numeric(result[metric], errors="coerce")
        result[metric] = values
        result[percentile_column] = values.rank(method="average", pct=True) * 100

    if "Altman Z" not in result.columns:
        result["Altman Z"] = float("nan")
    result["Altman Z"] = pd.to_numeric(result["Altman Z"], errors="coerce")

    flag_values = pd.DataFrame(
        {
            FLAG_COLUMNS[0]: result["STA percentile"].ge(accrual_percentile).where(
                result["STA percentile"].notna()
            ),
            FLAG_COLUMNS[1]: result["SNOA percentile"].ge(accrual_percentile).where(
                result["SNOA percentile"].notna()
            ),
            FLAG_COLUMNS[2]: result["Altman Z"].lt(altman_z_cutoff).where(
                result["Altman Z"].notna()
            ),
        },
        index=result.index,
    ).astype("boolean")

    result[FLAG_COLUMNS] = flag_values
    result["Total red flags"] = flag_values.fillna(False).astype(int).sum(axis=1)
    result["Unavailable flags"] = flag_values.isna().sum(axis=1)
    result["Investment conclusion"] = result["Total red flags"].map(
        CONCLUSION_BY_FLAGS
    )
    return result


def qualify_companies(data: pd.DataFrame, minimum_flags: int) -> pd.DataFrame:
    """A known, triggered flag counts; unavailable flags are separately disclosed."""
    return data.loc[data["Total red flags"].ge(minimum_flags)].copy()


def build_funnel_counts(data: pd.DataFrame, minimum_flags: int) -> pd.DataFrame:
    """Build nested company counts by the minimum number of observed red flags."""
    flag_counts = data["Total red flags"]
    counts = [
        ("Starting universe", len(data)),
        ("At least 1 red flag", int(flag_counts.ge(1).sum())),
        ("At least 2 red flags", int(flag_counts.ge(2).sum())),
        ("3 red flags", int(flag_counts.ge(3).sum())),
        (f"Qualifying (≥ {minimum_flags})", int(flag_counts.ge(minimum_flags).sum())),
    ]
    return pd.DataFrame(counts, columns=["Screening stage", "Companies"])


def rank_candidates(data: pd.DataFrame) -> pd.DataFrame:
    """Prioritize more flags, then weaker P-Score; use financial flags to break ties."""
    result = data.copy()
    if SCORE_COLUMN not in result.columns:
        result[SCORE_COLUMN] = float("nan")
    result[SCORE_COLUMN] = pd.to_numeric(result[SCORE_COLUMN], errors="coerce")
    ordering = [
        "Total red flags",
        SCORE_COLUMN,
        "STA percentile",
        "SNOA percentile",
        "Altman Z",
    ]
    ascending = [False, True, False, False, True]
    existing = [column for column in ordering if column in result.columns]
    directions = [ascending[ordering.index(column)] for column in existing]
    return result.sort_values(
        existing,
        ascending=directions,
        na_position="last",
        kind="stable",
    )


def flag_label(value: object) -> str:
    if pd.isna(value):
        return "Unavailable"
    return "Flag" if bool(value) else "No flag"


def main() -> None:
    st.set_page_config(page_title="S&P 500 short research screen", layout="wide")
    st.title("S&P 500 short research screen")
    st.write(
        "This screen highlights companies for additional research. It does not "
        "identify guaranteed profitable short positions or provide investment advice."
    )
    st.info(
        "**Unknown** means the required financial data was unavailable—not that "
        "the company performed poorly."
    )

    path = source_csv_path()
    try:
        raw_data = load_data(str(path))
    except (FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError, OSError) as exc:
        st.error(
            f"Could not load the screening dataset at `{path}`. "
            f"Error: {exc}. Checked files: `{UNIVERSE_PATH}` and `{SCREENING_PATH}`."
        )
        st.stop()

    if raw_data.empty:
        st.error(
            f"The screening dataset at `{path}` loaded 0 rows and contains no "
            f"company records. Available columns: {', '.join(map(str, raw_data.columns)) or 'none'}."
        )
        st.stop()

    data, formulas_recalculated = calculate_metrics_from_raw_inputs(raw_data)
    score_valid, score_message = validate_p_score(data)

    sector_column = find_sector_column(data)
    industry_selection = st.selectbox(
        "Industry",
        INDUSTRY_OPTIONS,
        index=0,
        key=(
            "industry_selection_with_sector"
            if sector_column is not None
            else "industry_selection_without_sector"
        ),
        disabled=sector_column is None,
    )

    if sector_column is None:
        selected_data = data
        st.warning(
            "This dataset has no sector or industry column. Industry-specific "
            "filters require sector data. All industries are shown."
        )
    else:
        industry_categories = data[sector_column].map(classify_sector)
        classified_count = int(industry_categories.notna().sum())
        unknown_count = len(data) - classified_count
        st.caption(
            f"Industry groups use `{sector_column}` from the saved data. "
            f"{classified_count} companies have a sector value; "
            f"{unknown_count} have no sector value and remain unclassified."
        )
        if industry_selection == "All industries":
            selected_data = data
        else:
            selected_data = data.loc[industry_categories.eq(industry_selection)]
            if unknown_count:
                st.info(
                    f"{unknown_count} companies with missing sector data are not "
                    "included in this industry selection."
                )
        st.metric("Companies in selected industry", len(selected_data))

    st.header("Starting universe")
    company_count = (
        data["Ticker"].dropna().nunique() if "Ticker" in data.columns else len(data)
    )
    st.metric("Companies in starting universe", company_count)
    st.caption(f"Source file: `{path.name}`")
    st.caption(
        f"Loaded {len(raw_data):,} rows from `{path.resolve()}` "
        f"with {raw_data.shape[1]} columns."
    )
    with st.expander("Dataset diagnostics"):
        st.write(f"File path: `{path.resolve()}`")
        st.write(f"Rows loaded: {len(raw_data):,}")
        st.write(f"Available columns: {', '.join(map(str, raw_data.columns))}")

    if "Data Retrieval Date" in data.columns:
        retrieval_dates = data["Data Retrieval Date"].dropna().astype(str).unique()
        if len(retrieval_dates) == 1:
            st.caption(f"Data retrieved: {retrieval_dates[0]} (UTC)")
        elif len(retrieval_dates) > 1:
            st.caption(
                "Data retrieval dates vary by row: "
                + ", ".join(sorted(retrieval_dates)[:5])
            )
        else:
            st.warning("The source file has no recorded data retrieval date.")
    else:
        st.warning(
            "This CSV has no recorded data retrieval date. Its exact data age cannot be confirmed."
        )

    if not formulas_recalculated:
        st.warning(
            "Raw inputs for STA, Scaled NOA, and Altman Z are not all present. "
            "Precalculated CSV metrics are being used; their formulas cannot be "
            "recalculated from this file. Run `financial_screen.py` to refresh "
            "universe.csv with the documented raw inputs."
        )
    if score_valid:
        st.caption(score_message)
    else:
        st.warning(score_message)

    table_columns = [
        column
        for column in [
            "Ticker",
            "Latest Fiscal Year",
            "STA",
            "SNOA",
            "Altman Z",
            SCORE_COLUMN,
            "Risk Classification",
        ]
        if column in data.columns
    ]
    search = st.text_input("Search starting universe by ticker", key="universe_search")
    universe_view = selected_data.copy()
    if search.strip() and "Ticker" in universe_view.columns:
        universe_view = universe_view.loc[
            universe_view["Ticker"].astype("string").str.contains(
                search.strip(), case=False, na=False, regex=False
            )
        ]
    if "Risk Classification" in universe_view.columns:
        universe_view["Risk Classification"] = universe_view[
            "Risk Classification"
        ].replace("Insufficient Data", "Unknown")
    if SCORE_COLUMN in universe_view.columns:
        universe_scores = pd.to_numeric(
            universe_view[SCORE_COLUMN], errors="coerce"
        )
        universe_view[SCORE_COLUMN] = universe_scores.map(
            lambda value: "Unknown" if pd.isna(value) else f"{value:g}"
        )
    st.dataframe(
        universe_view[table_columns] if table_columns else universe_view,
        height=320,
        hide_index=True,
        alt="Searchable starting universe with saved financial screening metrics",
    )

    with st.sidebar:
        st.header("Screening controls")
        st.caption(
            "STA and Scaled NOA are ranked across the complete starting universe. "
            "Missing values have no percentile and cannot trigger that flag."
        )
        minimum_flags = st.slider(
            "Red flags required (of 3)",
            min_value=1,
            max_value=3,
            value=2,
            step=1,
            key="minimum_flags",
        )
        accrual_percentile = st.slider(
            "Accrual percentile at or above",
            min_value=50,
            max_value=99,
            value=75,
            step=1,
            key="accrual_percentile",
        )
        altman_z_cutoff = st.slider(
            "Altman Z below",
            min_value=0.0,
            max_value=4.0,
            value=2.0,
            step=0.1,
            key="altman_z_cutoff",
        )

    flagged = add_percentile_flags(data, accrual_percentile, altman_z_cutoff)
    selected_flagged = flagged.loc[selected_data.index]
    qualifying = qualify_companies(selected_flagged, minimum_flags)
    funnel_counts = build_funnel_counts(selected_flagged, minimum_flags)

    st.header("Screening funnel")
    funnel_chart = px.funnel(
        funnel_counts,
        x="Companies",
        y="Screening stage",
        title="Companies by red-flag threshold",
        category_orders={
            "Screening stage": [
                "Starting universe",
                "At least 1 red flag",
                "At least 2 red flags",
                "3 red flags",
                f"Qualifying (≥ {minimum_flags})",
            ]
        },
    )
    funnel_chart.update_traces(textinfo="value")
    st.plotly_chart(
        funnel_chart,
        width="stretch",
        alt="Starting company count and nested counts with one, two, three, and the selected minimum red flags",
    )

    st.header("Qualifying short research candidates")
    st.metric("Companies qualifying", len(qualifying))
    st.caption(
        f"Each percentile flag is set at ≥ {accrual_percentile}; the Altman flag is "
        f"Altman Z < {altman_z_cutoff:.1f}. A company qualifies with at least "
        f"{minimum_flags} triggered flags. Missing flags are shown as unavailable "
        "and are not counted as triggered."
    )

    if qualifying.empty:
        st.info("No companies meet the selected number of red flags.")
        st.download_button(
            "Download qualifying companies",
            data=qualifying.to_csv(index=False).encode("utf-8"),
            file_name="short_research_candidates.csv",
            mime="text/csv",
            width="stretch",
        )
        st.stop()

    ranked = rank_candidates(qualifying)
    if not score_valid:
        st.warning("P-Score is not verified. Ranking uses flag count and risk metrics; P-Score is shown only when available.")

    displayed = ranked.head(10).copy()
    score_values = pd.to_numeric(
        displayed.get(SCORE_COLUMN, pd.Series(index=displayed.index, dtype=float)),
        errors="coerce",
    )
    displayed["P-Score"] = score_values.map(
        lambda value: "Unknown" if pd.isna(value) else f"{value:g}"
    )
    for column in FLAG_COLUMNS:
        if column in displayed.columns:
            displayed[column] = displayed[column].map(flag_label)
    displayed_columns = [
        "Ticker",
        "STA",
        "STA percentile",
        "SNOA",
        "SNOA percentile",
        "Altman Z",
        "P-Score",
        *FLAG_COLUMNS,
        "Total red flags",
        "Unavailable flags",
        "Investment conclusion",
    ]
    displayed_columns = [column for column in displayed_columns if column in displayed.columns]
    st.write(f"Showing {len(displayed)} of {len(qualifying)} qualifying companies (maximum 10).")
    st.dataframe(
        displayed[displayed_columns],
        hide_index=True,
        alt="Ranked short research candidates with metrics, red flags, and conclusions",
    )

    st.download_button(
        "Download all qualifying companies as CSV",
        data=ranked.to_csv(index=False).encode("utf-8"),
        file_name="short_research_candidates.csv",
        mime="text/csv",
        width="stretch",
    )

    with st.expander("Methodology and limitations"):
        st.markdown(
            f"""
            **Flags:** STA percentile ≥ {accrual_percentile}; Scaled NOA percentile ≥
            {accrual_percentile}; and Altman Z-Score < {altman_z_cutoff:.1f}. Percentile
            ranks use average ranks across the full starting universe, with missing
            values excluded from the rank calculation. Missing flags are marked
            unavailable, not silently marked as no flag.

            **Ranking:** qualifying companies are ordered by triggered flag count
            (most first), then P-Score (lowest first as a confirmation signal),
            higher STA percentile, higher Scaled NOA percentile, and lower Altman Z.
            The P-Score is not an additional red flag.

            **P-Score:** the source code calculates nine binary signals:
            four profitability signals (positive ROA, positive operating cash flow
            relative to beginning assets, improving ROA, and operating cash flow
            greater than net income); three funding signals (declining long-term
            debt-to-assets, improving current ratio, and no positive common-share
            issuance); and two efficiency signals (improving gross margin and asset
            turnover). The total is Profitability (0–4) + Funding (0–3) +
            Efficiency (0–2), maximum 9. It is a Piotroski-style F-Score; scores
            with missing required inputs remain unavailable.

            **Metric formulas:** STA = (Net Income − Operating Cash Flow) / Total
            Assets. Scaled NOA = (Total Debt + Equity − Cash) / Prior-Year Total
            Assets. Altman Z = 1.2 × WC/TA + 1.4 × RE/TA + 3.3 × EBIT/TA + 0.6 ×
            MVE/TL + 1.0 × Sales/TA.

            These results are a research screen, not a validated strategy or
            investment recommendation. Altman Z was not designed for consistent
            interpretation across all sectors; banks and other financial companies
            can have balance-sheet structures that make its ratios inappropriate.
            Verify source statements and use sector-specific analysis before drawing
            conclusions.
            """
        )


if __name__ == "__main__":
    main()
