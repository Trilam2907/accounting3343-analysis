import time
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf


def fetch_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; StudentStockScreener/1.0)"
    }
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    sp500 = pd.read_html(StringIO(response.text))[0]
    return (
        sp500["Symbol"]
        .str.replace(".", "-", regex=False)
        .tolist()
    )


def load_universe_tickers():
    """Use universe.csv tickers when supplied; otherwise fetch the S&P 500 list."""
    universe_path = Path("universe.csv")
    if not universe_path.is_file():
        return fetch_sp500_tickers()

    universe = pd.read_csv(universe_path)
    ticker_column = next(
        (column for column in ["Ticker", "Symbol", "ticker", "symbol"] if column in universe.columns),
        None,
    )
    if ticker_column is None:
        raise ValueError("universe.csv must contain a Ticker or Symbol column.")

    tickers = (
        universe[ticker_column]
        .dropna()
        .astype(str)
        .str.strip()
        .str.replace(".", "-", regex=False)
        .tolist()
    )
    tickers = list(dict.fromkeys(ticker for ticker in tickers if ticker))
    if not tickers:
        raise ValueError("universe.csv does not contain any valid ticker symbols.")
    return tickers


def get_value(statement, row, period):
    """Return a financial statement value, or NaN if unavailable."""
    if statement is None or statement.empty:
        return np.nan
    if row not in statement.index or period not in statement.columns:
        return np.nan

    value = statement.loc[row, period]

    if isinstance(value, pd.Series):
        value = value.iloc[0]

    if pd.isna(value):
        return np.nan

    return float(value)


def first_available(statement, rows, period):
    """Try alternative row names when a field is unavailable."""
    for row in rows:
        value = get_value(statement, row, period)
        if pd.notna(value):
            return value
    return np.nan


def calculate_metrics(ticker):
    stock = yf.Ticker(ticker)

    income = stock.financials
    balance = stock.balance_sheet
    cashflow = stock.cashflow

    if income.empty or balance.empty or cashflow.empty:
        return {"Ticker": ticker, "Error": "Missing financial statements"}

    periods = sorted(
        set(income.columns) & set(balance.columns) & set(cashflow.columns),
        reverse=True,
    )

    if len(periods) < 2:
        return {"Ticker": ticker, "Error": "Insufficient common periods"}

    current = periods[0]
    previous = periods[1]
    two_years_ago = periods[2] if len(periods) >= 3 else None

    def inc(row, period):
        return get_value(income, row, period)

    def bal(row, period):
        return get_value(balance, row, period)

    def cf(row, period):
        return get_value(cashflow, row, period)

    ni_reported = first_available(
        income,
        ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"],
        current,
    )
    ni = ni_reported

    ni_prev = first_available(
        income,
        ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"],
        previous,
    )

    cfo_reported = first_available(
        cashflow,
        ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
        current,
    )
    cfo = cfo_reported

    assets = bal("Total Assets", current)
    assets_prev = bal("Total Assets", previous)
    assets_2prev = bal("Total Assets", two_years_ago)

    sales = first_available(income, ["Total Revenue", "Operating Revenue"], current)

    sales_prev = first_available(income, ["Total Revenue", "Operating Revenue"], previous)

    gross_profit = first_available(income, ["Gross Profit"], current)

    gross_profit_prev = first_available(income, ["Gross Profit"], previous)

    ebit = first_available(
        income,
        ["EBIT", "Operating Income", "Total Operating Income As Reported"],
        current,
    )

    sta = (
        (ni_reported - cfo_reported) / assets
        if pd.notna(ni_reported)
        and pd.notna(cfo_reported)
        and pd.notna(assets)
        and assets > 0
        else np.nan
    )

    cash = first_available(
        balance,
        [
            "Cash Cash Equivalents And Short Term Investments",
            "Cash And Cash Equivalents",
            "Cash And Cash Equivalents And Short Term Investments",
        ],
        current,
    )
    equity = first_available(
        balance,
        [
            "Stockholders Equity",
            "Common Stock Equity",
            "Total Equity Gross Minority Interest",
            "Total Equity Special Stock",
        ],
        current,
    )

    short_term_debt = first_available(
        balance,
        [
            "Current Debt And Capital Lease Obligation",
            "Current Debt",
            "Current Debt And Finance Lease Obligation",
            "Commercial Paper",
        ],
        current,
    )
    long_term_debt = first_available(
        balance,
        [
            "Long Term Debt And Capital Lease Obligation",
            "Long Term Debt",
            "Long Term Debt And Finance Lease Obligation",
        ],
        current,
    )
    total_debt = first_available(balance, ["Total Debt"], current)
    if pd.isna(total_debt) and pd.notna(short_term_debt) and pd.notna(long_term_debt):
        total_debt = short_term_debt + long_term_debt

    snoa = (
        (total_debt + equity - cash) / assets_prev
        if pd.notna(total_debt)
        and pd.notna(equity)
        and pd.notna(cash)
        and pd.notna(assets_prev)
        and assets_prev > 0
        else np.nan
    )

    working_capital = bal("Working Capital", current)
    if pd.isna(working_capital):
        ca = bal("Current Assets", current)
        cl = bal("Current Liabilities", current)
        if pd.notna(ca) and pd.notna(cl):
            working_capital = ca - cl

    retained = first_available(balance, ["Retained Earnings"], current)

    liabilities = first_available(balance, ["Total Liabilities Net Minority Interest", "Total Liabilities"], current)

    try:
        market_cap = stock.info.get("marketCap", np.nan)
    except Exception:
        market_cap = np.nan

    z = np.nan
    if (
        pd.notna(assets)
        and assets > 0
        and pd.notna(working_capital)
        and pd.notna(retained)
        and pd.notna(ebit)
        and pd.notna(market_cap)
        and pd.notna(liabilities)
        and liabilities > 0
        and pd.notna(sales)
    ):
        x1 = working_capital / assets
        x2 = retained / assets
        x3 = ebit / assets
        x4 = market_cap / liabilities
        x5 = sales / assets

        z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

    if pd.isna(z):
        z_class = "Insufficient Data"
    elif z > 2.99:
        z_class = "Safe"
    elif z >= 1.81:
        z_class = "Grey"
    else:
        z_class = "Distress"

    roa = ni / assets_prev if pd.notna(ni) and pd.notna(assets_prev) and assets_prev > 0 else np.nan
    cfo_roa = cfo / assets_prev if pd.notna(cfo) and pd.notna(assets_prev) and assets_prev > 0 else np.nan
    roa_prev = ni_prev / assets_2prev if pd.notna(ni_prev) and pd.notna(assets_2prev) and assets_2prev > 0 else np.nan

    p1 = int(roa > 0) if pd.notna(roa) else np.nan
    p2 = int(cfo_roa > 0) if pd.notna(cfo_roa) else np.nan
    p3 = int(roa > roa_prev) if pd.notna(roa) and pd.notna(roa_prev) else np.nan
    p4 = int(cfo > ni) if pd.notna(cfo) and pd.notna(ni) else np.nan

    profitability_signals = [p1, p2, p3, p4]
    profitability_score = (
        sum(profitability_signals)
        if all(pd.notna(signal) for signal in profitability_signals)
        else np.nan
    )

    long_debt_prev = first_available(
        balance,
        [
            "Long Term Debt And Capital Lease Obligation",
            "Long Term Debt",
            "Long Term Debt And Finance Lease Obligation",
        ],
        previous,
    )
    leverage = long_term_debt / assets if pd.notna(long_term_debt) and pd.notna(assets) and assets > 0 else np.nan
    leverage_prev = long_debt_prev / assets_prev if pd.notna(long_debt_prev) and pd.notna(assets_prev) and assets_prev > 0 else np.nan

    current_assets = bal("Current Assets", current)
    current_liabilities = bal("Current Liabilities", current)
    previous_current_assets = bal("Current Assets", previous)
    previous_current_liabilities = bal("Current Liabilities", previous)
    current_ratio = (
        current_assets / current_liabilities
        if pd.notna(current_assets) and pd.notna(current_liabilities) and current_liabilities > 0
        else np.nan
    )
    current_ratio_prev = (
        previous_current_assets / previous_current_liabilities
        if pd.notna(previous_current_assets)
        and pd.notna(previous_current_liabilities)
        and previous_current_liabilities > 0
        else np.nan
    )

    l1 = int(leverage < leverage_prev) if pd.notna(leverage) and pd.notna(leverage_prev) else np.nan
    l2 = int(current_ratio > current_ratio_prev) if pd.notna(current_ratio) and pd.notna(current_ratio_prev) else np.nan

    net_issuance = first_available(
        cashflow,
        ["Net Common Stock Issuance", "Proceeds From Stock Option Exercises"],
        current,
    )
    l3 = int(net_issuance <= 0) if pd.notna(net_issuance) else np.nan
    funding_signals = [l1, l2, l3]
    funding_score = (
        sum(funding_signals)
        if all(pd.notna(signal) for signal in funding_signals)
        else np.nan
    )

    margin = gross_profit / sales if pd.notna(gross_profit) and pd.notna(sales) and sales != 0 else np.nan
    margin_prev = gross_profit_prev / sales_prev if pd.notna(gross_profit_prev) and pd.notna(sales_prev) and sales_prev != 0 else np.nan

    turnover = sales / assets_prev if pd.notna(sales) and pd.notna(assets_prev) and assets_prev > 0 else np.nan
    turnover_prev = sales_prev / assets_2prev if pd.notna(sales_prev) and pd.notna(assets_2prev) and assets_2prev > 0 else np.nan

    e1 = int(margin > margin_prev) if pd.notna(margin) and pd.notna(margin_prev) else np.nan
    e2 = int(turnover > turnover_prev) if pd.notna(turnover) and pd.notna(turnover_prev) else np.nan
    efficiency_signals = [e1, e2]
    efficiency_score = (
        sum(efficiency_signals)
        if all(pd.notna(signal) for signal in efficiency_signals)
        else np.nan
    )

    total_score = (
        profitability_score + funding_score + efficiency_score
        if pd.notna(profitability_score)
        and pd.notna(funding_score)
        and pd.notna(efficiency_score)
        else np.nan
    )

    return {
        "Ticker": ticker,
        "Latest Fiscal Year": current.year if hasattr(current, "year") else current,
        "Net Income": ni_reported,
        "Operating Cash Flow": cfo_reported,
        "Total Assets": assets,
        "Prior-Year Total Assets": assets_prev,
        "Total Debt": total_debt,
        "Equity": equity,
        "Cash": cash,
        "Working Capital": working_capital,
        "Retained Earnings": retained,
        "EBIT": ebit,
        "Market Value of Equity": market_cap,
        "Total Liabilities": liabilities,
        "Sales": sales,
        "STA": sta,
        "SNOA": snoa,
        "Altman Z": z,
        "Risk Classification": z_class,
        "Profitability Score (0-4)": profitability_score,
        "Leverage Score": l1,
        "Liquidity Score": l2,
        "Equity Issuance Score": l3,
        "Funding Score (0-3)": funding_score,
        "Efficiency Score (0-2)": efficiency_score,
        "Financial Strength Score (0-9)": total_score,
    }


def main():
    tickers = load_universe_tickers()
    results = []
    errors = []
    retrieval_date = datetime.now(timezone.utc).date().isoformat()

    for i, ticker in enumerate(tickers, start=1):
        try:
            result = calculate_metrics(ticker)
            result["Data Retrieval Date"] = retrieval_date
            if "Error" in result:
                result["Data Error"] = result.pop("Error")
            results.append(result)
        except Exception as exc:  # pragma: no cover - data quality fallback
            errors.append({"Ticker": ticker, "Error": str(exc)})
            results.append(
                {
                    "Ticker": ticker,
                    "Data Retrieval Date": retrieval_date,
                    "Data Error": str(exc),
                }
            )

        if i % 25 == 0:
            print(f"Processed {i}/{len(tickers)} companies")
        time.sleep(0.1)

    screen_df = pd.DataFrame(results)
    errors_df = pd.DataFrame(errors, columns=["Ticker", "Error"])
    screen_df.to_csv("universe.csv", index=False)
    screen_df.to_csv("sp500_screening_results.csv", index=False)

    if "Financial Strength Score (0-9)" not in screen_df.columns:
        print("No P-Score values were generated.")
        errors_df.to_csv("screening_errors.csv", index=False)
        return

    ranked_df = screen_df.dropna(subset=["Financial Strength Score (0-9)"]).copy()
    ranked_df = ranked_df.sort_values(by="Financial Strength Score (0-9)", ascending=True)

    errors_df.to_csv("screening_errors.csv", index=False)

    print("\nCompanies processed:", len(results))
    print("Errors:", len(errors))
    print("\nLowest-scoring 15 companies:")
    print(
        ranked_df[
            [
                "Ticker",
                "STA",
                "SNOA",
                "Altman Z",
                "Risk Classification",
                "Financial Strength Score (0-9)",
            ]
        ].head(15).round(3)
    )


if __name__ == "__main__":
    main()
