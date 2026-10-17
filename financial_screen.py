import time
from io import StringIO

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
    two_years_ago = periods[2] if len(periods) >= 3 else previous

    def inc(row, period):
        return get_value(income, row, period)

    def bal(row, period):
        return get_value(balance, row, period)

    def cf(row, period):
        return get_value(cashflow, row, period)

    ni = first_available(
        income,
        ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"],
        current,
    )
    if pd.isna(ni):
        ni = 0.0

    ni_prev = first_available(
        income,
        ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"],
        previous,
    )
    if pd.isna(ni_prev):
        ni_prev = 0.0

    cfo = first_available(
        cashflow,
        ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
        current,
    )
    if pd.isna(cfo):
        cfo = 0.0

    assets = bal("Total Assets", current)
    assets_prev = bal("Total Assets", previous)
    assets_2prev = bal("Total Assets", two_years_ago)
    if pd.isna(assets_prev):
        assets_prev = assets
    if pd.isna(assets_2prev):
        assets_2prev = assets_prev

    sales = first_available(income, ["Total Revenue", "Operating Revenue"], current)
    if pd.isna(sales):
        sales = 0.0

    sales_prev = first_available(income, ["Total Revenue", "Operating Revenue"], previous)
    if pd.isna(sales_prev):
        sales_prev = sales

    gross_profit = first_available(income, ["Gross Profit"], current)
    if pd.isna(gross_profit):
        gross_profit = sales

    gross_profit_prev = first_available(income, ["Gross Profit"], previous)
    if pd.isna(gross_profit_prev):
        gross_profit_prev = sales_prev

    ebit = first_available(
        income,
        ["EBIT", "Operating Income", "Total Operating Income As Reported"],
        current,
    )
    if pd.isna(ebit):
        ebit = ni

    sta = (
        (ni - cfo) / assets
        if pd.notna(ni) and pd.notna(cfo) and pd.notna(assets) and assets != 0
        else 0.0
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
    if pd.isna(cash):
        cash = 0.0

    current_debt = first_available(
        balance,
        [
            "Current Debt And Capital Lease Obligation",
            "Current Debt",
            "Current Debt And Finance Lease Obligation",
            "Commercial Paper",
        ],
        current,
    )
    if pd.isna(current_debt):
        current_debt = 0.0

    long_debt = first_available(
        balance,
        [
            "Long Term Debt And Capital Lease Obligation",
            "Long Term Debt",
            "Long Term Debt And Finance Lease Obligation",
        ],
        current,
    )
    if pd.isna(long_debt):
        long_debt = 0.0

    minority = first_available(balance, ["Minority Interest", "Non Controlling Interest"], current)
    if pd.isna(minority):
        minority = 0.0

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
    if pd.isna(equity):
        equity = assets - long_debt - current_debt

    snoa = 0.0
    if pd.notna(assets) and assets != 0 and pd.notna(equity):
        operating_assets = assets - cash
        operating_liabilities = assets - current_debt - long_debt - minority - equity
        snoa = (operating_assets - operating_liabilities) / assets

    working_capital = bal("Working Capital", current)
    if pd.isna(working_capital):
        ca = bal("Current Assets", current)
        cl = bal("Current Liabilities", current)
        if pd.notna(ca) and pd.notna(cl):
            working_capital = ca - cl
        else:
            working_capital = 0.0

    retained = first_available(balance, ["Retained Earnings"], current)
    if pd.isna(retained):
        retained = 0.0

    liabilities = first_available(balance, ["Total Liabilities Net Minority Interest", "Total Liabilities"], current)
    if pd.isna(liabilities):
        liabilities = assets - equity if pd.notna(equity) else assets

    try:
        market_cap = stock.info.get("marketCap", np.nan)
    except Exception:
        market_cap = np.nan
    if pd.isna(market_cap):
        market_cap = assets

    z = 0.0
    if pd.notna(assets) and assets > 0:
        x1 = working_capital / assets
        x2 = retained / assets
        x3 = ebit / assets
        x4 = market_cap / liabilities if pd.notna(liabilities) and liabilities > 0 else 1.0
        x5 = sales / assets if pd.notna(sales) else 0.0

        z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

    if z > 2.99:
        z_class = "Safe"
    elif z >= 1.81:
        z_class = "Grey"
    else:
        z_class = "Distress"

    roa = ni / assets_prev if (pd.notna(ni) and pd.notna(assets_prev) and assets_prev != 0) else 0.0
    cfo_roa = cfo / assets_prev if (pd.notna(cfo) and pd.notna(assets_prev) and assets_prev != 0) else 0.0
    roa_prev = ni_prev / assets_2prev if (pd.notna(ni_prev) and pd.notna(assets_2prev) and assets_2prev != 0) else 0.0

    p1 = int(roa > 0)
    p2 = int(cfo_roa > 0)
    p3 = int(roa > roa_prev)
    p4 = int(cfo > ni) if pd.notna(cfo) and pd.notna(ni) else 0

    profitability_score = sum([p1, p2, p3, p4])

    long_debt_prev = first_available(
        balance,
        [
            "Long Term Debt And Capital Lease Obligation",
            "Long Term Debt",
            "Long Term Debt And Finance Lease Obligation",
        ],
        previous,
    )
    if pd.isna(long_debt_prev):
        long_debt_prev = 0.0

    leverage = long_debt / assets if (pd.notna(assets) and assets != 0) else 0.0
    leverage_prev = long_debt_prev / assets_prev if (pd.notna(assets_prev) and assets_prev != 0) else 0.0

    current_ratio = (
        bal("Current Assets", current) / bal("Current Liabilities", current)
        if pd.notna(bal("Current Assets", current))
        and pd.notna(bal("Current Liabilities", current))
        and bal("Current Liabilities", current) != 0
        else 1.0
    )
    current_ratio_prev = (
        bal("Current Assets", previous) / bal("Current Liabilities", previous)
        if pd.notna(bal("Current Assets", previous))
        and pd.notna(bal("Current Liabilities", previous))
        and bal("Current Liabilities", previous) != 0
        else 1.0
    )

    l1 = int(leverage < leverage_prev)
    l2 = int(current_ratio > current_ratio_prev)

    net_issuance = first_available(
        cashflow,
        ["Net Common Stock Issuance", "Proceeds From Stock Option Exercises"],
        current,
    )
    l3 = int(net_issuance <= 0) if pd.notna(net_issuance) else 1
    funding_score = sum([l1, l2, l3])

    margin = gross_profit / sales if (pd.notna(sales) and sales != 0) else 0.0
    margin_prev = gross_profit_prev / sales_prev if (pd.notna(sales_prev) and sales_prev != 0) else 0.0

    turnover = sales / assets_prev if (pd.notna(assets_prev) and assets_prev != 0) else 0.0
    turnover_prev = sales_prev / assets_2prev if (pd.notna(assets_2prev) and assets_2prev != 0) else 0.0

    e1 = int(margin > margin_prev)
    e2 = int(turnover > turnover_prev)
    efficiency_score = sum([e1, e2])

    total_score = profitability_score + funding_score + efficiency_score

    return {
        "Ticker": ticker,
        "Latest Fiscal Year": current.year if hasattr(current, "year") else current,
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
    tickers = fetch_sp500_tickers()
    results = []
    errors = []

    for i, ticker in enumerate(tickers, start=1):
        try:
            result = calculate_metrics(ticker)
            results.append(result)
        except Exception as exc:  # pragma: no cover - data quality fallback
            errors.append({"Ticker": ticker, "Error": str(exc)})

        if i % 25 == 0:
            print(f"Processed {i}/{len(tickers)} companies")
        time.sleep(0.1)

    screen_df = pd.DataFrame(results)
    errors_df = pd.DataFrame(errors, columns=["Ticker", "Error"])
    ranked_df = screen_df.dropna(subset=["Financial Strength Score (0-9)"]).copy()
    ranked_df = ranked_df.sort_values(by="Financial Strength Score (0-9)", ascending=True)

    screen_df.to_csv("sp500_screening_results.csv", index=False)
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
