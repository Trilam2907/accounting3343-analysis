from pathlib import Path

import pandas as pd
import streamlit as st


DATA_PATH = Path(__file__).resolve().with_name("sp500_screening_results.csv")
SCORE_COLUMN = "Financial Strength Score (0-9)"
SCORE_COMPONENTS = [
    "Profitability Score (0-4)",
    "Funding Score (0-3)",
    "Efficiency Score (0-2)",
]
KEY_COLUMNS = [
    "Ticker",
    "STA",
    "SNOA",
    "Altman Z",
    "Risk Classification",
    SCORE_COLUMN,
]


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    """Load saved screening results without fetching stock data."""
    return pd.read_csv(path)


def validate_score_definition(data: pd.DataFrame) -> tuple[bool, str]:
    """Check that the saved aggregate matches the formula in financial_screen.py."""
    required = [SCORE_COLUMN, *SCORE_COMPONENTS]
    missing = [column for column in required if column not in data.columns]
    if missing:
        return False, f"Cannot validate the saved score; missing columns: {', '.join(missing)}."

    components = data[SCORE_COMPONENTS].apply(pd.to_numeric, errors="coerce")
    saved_score = pd.to_numeric(data[SCORE_COLUMN], errors="coerce")
    calculated_score = components.sum(axis=1, min_count=len(SCORE_COMPONENTS))
    comparable = saved_score.notna() & calculated_score.notna()

    if not comparable.any():
        return False, "Cannot validate the saved score because there are no complete score rows."
    if not calculated_score[comparable].eq(saved_score[comparable]).all():
        return False, "The saved aggregate does not match Profitability + Funding + Efficiency."
    if saved_score.isna().any() or calculated_score.isna().any():
        return False, "Some rows have missing score inputs or aggregates; those rows cannot be ranked."

    return True, "Saved score verified: Profitability + Funding + Efficiency (range 0–9)."


def slider_settings(series: pd.Series) -> dict | None:
    """Return data-derived slider bounds, with safe handling for constants and missing values."""
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return None

    data_min = float(values.min())
    data_max = float(values.max())
    slider_min = data_min
    slider_max = data_max
    if data_min == data_max:
        padding = max(abs(data_min) * 0.1, 1.0)
        slider_min -= padding
        slider_max += padding

    span = slider_max - slider_min
    step = 1.0 if values.astype(float).map(lambda value: value.is_integer()).all() else max(span / 1000, 0.000001)
    return {
        "data_min": data_min,
        "data_max": data_max,
        "slider_min": slider_min,
        "slider_max": slider_max,
        "step": step,
    }


def default_cutoff(metric: str, series: pd.Series, settings: dict) -> float:
    """Use intuitive screening defaults, clamped to the observed data range."""
    values = pd.to_numeric(series, errors="coerce").dropna()
    defaults = {
        "STA": 0.0,
        "SNOA": float(values.median()) if not values.empty else settings["data_min"],
        "Altman Z": 2.99,
    }
    value = defaults[metric]
    return min(max(value, settings["data_min"]), settings["data_max"])


def reset_cutoffs(metrics: list[str]) -> None:
    for metric in metrics:
        st.session_state.pop(f"cutoff_{metric}", None)


def apply_screening_funnel(
    data: pd.DataFrame,
    sta_minimum: float,
    snoa_minimum: float,
    altman_z_maximum: float,
) -> tuple[pd.DataFrame, list[dict]]:
    """Apply the three rules sequentially and report each stage's pass/exclusion counts."""
    rules = [
        ("STA", "STA", lambda values: values >= sta_minimum, f"STA ≥ {sta_minimum:.6g}"),
        ("SNOA", "SNOA", lambda values: values >= snoa_minimum, f"SNOA ≥ {snoa_minimum:.6g}"),
        ("Altman Z-Score", "Altman Z", lambda values: values <= altman_z_maximum, f"Altman Z ≤ {altman_z_maximum:.6g}"),
    ]
    current = data.copy()
    stages = []

    for label, column, passes_rule, threshold_text in rules:
        if column not in current.columns:
            stages.append(
                {
                    "name": label,
                    "threshold": threshold_text,
                    "input": len(current),
                    "passed": 0,
                    "excluded": len(current),
                    "missing": len(current),
                    "unavailable": True,
                }
            )
            current = current.iloc[0:0].copy()
            continue

        values = pd.to_numeric(current[column], errors="coerce")
        available = values.notna()
        missing_count = int((~available).sum())
        pass_mask = available & passes_rule(values)
        passed = current.loc[pass_mask].copy()
        input_count = len(current)
        stages.append(
            {
                "name": label,
                "threshold": threshold_text,
                "input": input_count,
                "passed": len(passed),
                "excluded": input_count - len(passed),
                "missing": missing_count,
                "unavailable": False,
            }
        )
        current = passed

    return current.reset_index(drop=True), stages


def candidate_reasons(row: pd.Series, sta_minimum: float, snoa_minimum: float, altman_z_maximum: float) -> str:
    return (
        f"STA {row['STA']:.4g} ≥ {sta_minimum:.4g}; "
        f"SNOA {row['SNOA']:.4g} ≥ {snoa_minimum:.4g}; "
        f"Altman Z {row['Altman Z']:.4g} ≤ {altman_z_maximum:.4g}"
    )


def main() -> None:
    st.set_page_config(page_title="S&P 500 short-candidate research screen", layout="wide")
    st.title("S&P 500 short-candidate research screen")
    st.write(
        "This workflow narrows the full saved S&P 500 dataset using three transparent "
        "financial-risk signals. It identifies companies for further research, not "
        "guaranteed short positions."
    )

    try:
        data = load_data(str(DATA_PATH))
    except FileNotFoundError:
        st.error(f"Could not find `{DATA_PATH.name}`. Keep it in the same folder as `app.py`.")
        st.stop()
    except pd.errors.EmptyDataError:
        st.error(f"`{DATA_PATH.name}` is empty.")
        st.stop()

    if data.empty:
        st.error("The screening results file contains no company rows.")
        st.stop()

    st.header("1. Starting universe")
    initial_count = data["Ticker"].nunique() if "Ticker" in data.columns else len(data)
    st.metric("Companies in the starting dataset", initial_count)

    universe_search = st.text_input(
        "Search the starting-universe table by ticker",
        key="universe_search",
        help="This search changes the table shown here only; the funnel always starts with the complete dataset.",
    )
    universe_table = data.copy()
    if universe_search.strip() and "Ticker" in universe_table.columns:
        universe_table = universe_table[
            universe_table["Ticker"].astype("string").str.contains(
                universe_search.strip(), case=False, na=False, regex=False
            )
        ]

    universe_columns = [column for column in KEY_COLUMNS if column in data.columns]
    if universe_table.empty:
        st.info("No starting-universe rows match that ticker search.")
    else:
        st.dataframe(
            universe_table[universe_columns],
            height=360,
            hide_index=True,
            alt="Searchable starting universe with key financial screening metrics",
        )

    st.header("2. Sequential screening funnel")
    st.markdown(
        """
        The rules are applied in order: **STA → SNOA → Altman Z-Score**. Each rule
        receives only the companies that passed the previous rule. Missing values
        for a rule are excluded at that stage and counted separately.
        """
    )

    metric_labels = {
        "STA": "STA (scaled total accruals)",
        "SNOA": "SNOA (scaled net operating assets)",
        "Altman Z": "Altman Z-Score",
    }
    missing_metrics = [metric_labels[key] for key in metric_labels if key not in data.columns]
    if missing_metrics:
        st.warning("Screening cannot use missing CSV columns: " + ", ".join(missing_metrics))

    metrics_ready = all(metric in data.columns for metric in metric_labels)
    if not metrics_ready:
        st.error("The funnel requires STA, SNOA, and Altman Z columns in the screening CSV.")
        st.stop()

    with st.sidebar:
        st.header("Screening thresholds")
        cutoffs = {}
        for metric in metric_labels:
            settings = slider_settings(data[metric])
            if settings is None:
                cutoffs[metric] = None
                st.caption(f"{metric_labels[metric]}: no numeric data")
                continue

            default = default_cutoff(metric, data[metric], settings)
            cutoffs[metric] = st.slider(
                f"{metric_labels[metric]} cutoff",
                min_value=settings["slider_min"],
                max_value=settings["slider_max"],
                value=default,
                step=settings["step"],
                key=f"cutoff_{metric}",
                help=(
                    "Keep values at or above this cutoff."
                    if metric in {"STA", "SNOA"}
                    else "Keep values at or below this cutoff."
                ),
            )
            st.caption(
                f"Observed data range: {settings['data_min']:.6g} to "
                f"{settings['data_max']:.6g}"
            )

        st.button(
            "Reset cutoffs",
            on_click=reset_cutoffs,
            args=(list(metric_labels),),
            width="stretch",
        )

    if any(value is None for value in cutoffs.values()):
        st.error("At least one screening metric has no numeric data, so the funnel cannot run.")
        st.stop()

    st.markdown(
        """
        **Why these rules?** Higher positive STA can indicate that reported earnings
        are less supported by operating cash flow. Higher SNOA is used as a signal
        of greater operating-asset intensity. A lower Altman Z-Score can indicate
        greater financial distress. These are screening signals—not forecasts or
        investment advice.
        """
    )

    shortlist, stages = apply_screening_funnel(
        data,
        sta_minimum=cutoffs["STA"],
        snoa_minimum=cutoffs["SNOA"],
        altman_z_maximum=cutoffs["Altman Z"],
    )

    for stage in stages:
        if "name" not in stage:
            continue
        with st.container(border=True):
            st.markdown(f"**{stage['name']}** — {stage['threshold']}")
            st.caption(
                f"Input: {stage['input']} · Passed: {stage['passed']} · "
                f"Excluded: {stage['excluded']} · Missing at this stage: {stage['missing']}"
            )

    st.header("3. Final short-list")
    st.caption(
        "Companies passing all three rules are research candidates only. The existing "
        "financial-strength score ranges from 0 to 9, with lower scores indicating "
        "fewer positive financial-strength signals in this screener."
    )

    score_valid, score_message = validate_score_definition(data)
    if score_valid:
        st.success(score_message)
    else:
        st.warning(score_message)

    if shortlist.empty:
        st.info("No companies currently pass all three screening rules. Adjust the cutoffs to explore other results.")
        st.metric("Qualifying research candidates", 0)
        st.stop()

    st.metric("Companies passing all three rules", len(shortlist))
    if not score_valid:
        st.warning("A verified aggregate score is unavailable; candidates are shown without score ranking.")

    result = shortlist.copy()
    result["Screening reasons"] = result.apply(
        lambda row: candidate_reasons(
            row, cutoffs["STA"], cutoffs["SNOA"], cutoffs["Altman Z"]
        ),
        axis=1,
    )

    if score_valid:
        score_values = pd.to_numeric(result[SCORE_COLUMN], errors="coerce")
        result[SCORE_COLUMN] = score_values
        result = result.sort_values(
            by=[SCORE_COLUMN, "STA", "SNOA", "Altman Z"],
            ascending=[True, False, False, True],
            na_position="last",
        )
        ranked = result.head(10)
        unranked_count = len(result) - result[SCORE_COLUMN].notna().sum()
        if unranked_count:
            st.caption(
                f"{unranked_count} qualifying companies have no score and are shown "
                "after score-ranked companies if space remains."
            )
    else:
        ranked = result.sort_values("Ticker").head(10) if "Ticker" in result.columns else result.head(10)
        st.caption("Because the saved score could not be verified, these rows are shown alphabetically, not score-ranked.")

    displayed_count = len(ranked)
    st.write(
        f"Displaying {displayed_count} of {len(shortlist)} qualifying companies "
        "(up to 10; no rows are duplicated)."
    )
    shortlist_columns = [
        column
        for column in [
            "Ticker",
            "STA",
            "SNOA",
            "Altman Z",
            SCORE_COLUMN,
            "Screening reasons",
        ]
        if column in ranked.columns
    ]
    st.dataframe(
        ranked[shortlist_columns],
        hide_index=True,
        alt="Up to ten companies that passed all screening rules, ranked for further research",
    )

if __name__ == "__main__":
    main()
