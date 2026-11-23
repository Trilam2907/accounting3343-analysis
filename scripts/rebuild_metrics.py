import pickle
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT.parent / ".copilot" / "missing"
CACHE_FILE = Path(
    "/Users/eddy/.copilot/session-state/e75952a2-6679-4135-a7c5-c21a93093457/"
    "files/stock_screener_cache/sp500_company_data.pkl"
)
UNIVERSE_FILE = Path(
    "/Users/eddy/.copilot/session-state/e75952a2-6679-4135-a7c5-c21a93093457/"
    "files/stock_screener_cache/sp500_tickers.csv"
)
OUTPUT_SNAPSHOT = ROOT / "sp500_all_company_metrics.csv"
OUTPUT_HISTORY = ROOT / "sp500_three_year_historical_metrics.csv"
FORMULA_VERSION = "1.6.0"


def statement(frame):
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame()
    frame = frame.copy()
    try:
        frame = frame.reindex(
            sorted(frame.columns, key=lambda value: pd.Timestamp(value), reverse=True),
            axis=1,
        )
    except Exception:
        pass
    return frame


def get_value(frame, aliases, column=0):
    if frame is None or frame.empty or frame.shape[1] <= column:
        return np.nan
    normalized = {str(index).strip().lower(): index for index in frame.index}
    for alias in aliases:
        index = normalized.get(alias.strip().lower())
        if index is None:
            continue
        try:
            value = float(frame.loc[index].iloc[column])
            return value if np.isfinite(value) else np.nan
        except (TypeError, ValueError):
            continue
    return np.nan


def safe_div(numerator, denominator):
    if pd.isna(numerator) or pd.isna(denominator):
        return np.nan
    try:
        if float(denominator) == 0:
            return np.nan
        value = float(numerator) / float(denominator)
        return value if np.isfinite(value) else np.nan
    except (TypeError, ValueError, ZeroDivisionError):
        return np.nan


def growth(current, prior, minimum_prior=0.01, maximum=1000.0):
    if pd.isna(current) or pd.isna(prior):
        return np.nan
    if float(prior) <= 0:
        return np.nan
    if abs(float(prior)) < minimum_prior:
        return np.nan
    value = (float(current) - float(prior)) / abs(float(prior)) * 100
    if not np.isfinite(value) or abs(value) > maximum:
        return np.nan
    return value


def positive(value):
    return value if not pd.isna(value) and float(value) > 0 else np.nan


def calculate(ticker, record, universe_row=None):
    info = record.get("info", {}) or {}
    income = statement(record.get("income"))
    balance = statement(record.get("balance"))
    cashflow = statement(record.get("cashflow"))

    revenue = get_value(income, ["Total Revenue", "Operating Revenue"])
    gross_profit = get_value(income, ["Gross Profit"])
    cost_revenue = get_value(income, ["Cost Of Revenue", "Cost of Revenue"])
    if pd.isna(gross_profit) and not pd.isna(revenue) and not pd.isna(cost_revenue):
        gross_profit = revenue - cost_revenue

    operating_income = get_value(income, ["Operating Income", "Operating Income Loss"])
    depreciation_amortization = get_value(
        income,
        [
            "Depreciation And Amortization In Income Statement",
            "Depreciation Amortization Depletion Income Statement",
            "Reconciled Depreciation",
        ],
    )
    if pd.isna(depreciation_amortization):
        ebitda = get_value(income, ["EBITDA", "Normalized EBITDA"])
    elif operating_income is not np.nan:
        ebitda = operating_income + abs(depreciation_amortization)
    else:
        ebitda = np.nan
    net_income = get_value(income, ["Net Income", "Net Income Common Stockholders",
                                    "Net Income From Continuing Operations"])
    net_income_prior = get_value(income, ["Net Income", "Net Income Common Stockholders",
                                          "Net Income From Continuing Operations"], 1)
    basic_shares = get_value(income, ["Basic Average Shares"])
    basic_shares_prior = get_value(income, ["Basic Average Shares"], 1)
    eps = (
        safe_div(net_income, positive(basic_shares))
        if not pd.isna(net_income)
        else np.nan
    )
    eps_prior = (
        safe_div(net_income_prior, positive(basic_shares_prior))
        if not pd.isna(net_income_prior)
        else np.nan
    )

    total_assets = get_value(balance, ["Total Assets"])
    prior_assets = get_value(balance, ["Total Assets"], 1)
    equity = get_value(balance, ["Stockholders Equity", "Total Equity Gross Minority Interest",
                                 "Common Stock Equity"])
    prior_equity = get_value(balance, ["Stockholders Equity", "Total Equity Gross Minority Interest",
                                       "Common Stock Equity"], 1)

    total_debt = get_value(balance, ["Total Debt"])
    if pd.isna(total_debt):
        current_debt = get_value(balance, ["Current Debt", "Current Debt And Lease Obligation"])
        long_debt = get_value(balance, ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"])
        if not pd.isna(current_debt) or not pd.isna(long_debt):
            total_debt = (0 if pd.isna(current_debt) else current_debt) + (
                0 if pd.isna(long_debt) else long_debt
            )

    cash = get_value(balance, ["Cash Cash Equivalents And Short Term Investments",
                               "Cash And Cash Equivalents", "Cash And Short Term Investments"])
    current_assets = get_value(balance, ["Current Assets"])
    current_liabilities = get_value(balance, ["Current Liabilities"])

    cfo = get_value(cashflow, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities",
                               "Total Cash From Operating Activities"])
    cfo_prior = get_value(cashflow, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities",
                                     "Total Cash From Operating Activities"], 1)
    capex = get_value(cashflow, ["Capital Expenditure", "Capital Expenditures"])
    capex_prior = get_value(cashflow, ["Capital Expenditure", "Capital Expenditures"], 1)
    fcf = cfo + capex if not pd.isna(cfo) and not pd.isna(capex) else np.nan
    fcf_prior = cfo_prior + capex_prior if not pd.isna(cfo_prior) and not pd.isna(capex_prior) else np.nan

    repurchases = get_value(cashflow, ["Repurchase Of Capital Stock", "Repurchase Of Stock"])
    issuance = get_value(cashflow, ["Common Stock Issuance", "Issuance Of Capital Stock",
                                    "Stock Issuance"])
    market_cap = info.get("marketCap", np.nan)
    repurchases = abs(repurchases) if not pd.isna(repurchases) else np.nan
    issuance = abs(issuance) if not pd.isna(issuance) else np.nan
    net_repurchase = (
        repurchases - issuance
        if not pd.isna(repurchases) and not pd.isna(issuance)
        else np.nan
    )
    market_cap = (
        positive(market_cap)
        if not pd.isna(positive(market_cap))
        else np.nan
    )
    enterprise_value = info.get("enterpriseValue", np.nan)
    if pd.isna(enterprise_value) and not pd.isna(market_cap):
        enterprise_value = (
            market_cap
            + (0 if pd.isna(total_debt) else total_debt)
            - (0 if pd.isna(cash) else cash)
        )
    enterprise_value = positive(enterprise_value)
    ebit_tev = safe_div(operating_income, enterprise_value) * 100
    invested_capital = (
        total_debt + equity - cash
        if not any(pd.isna(value) for value in [total_debt, equity, cash])
        else np.nan
    )
    invested_capital = positive(invested_capital)
    roc = safe_div(operating_income, invested_capital) * 100
    if not pd.isna(roc) and abs(float(roc)) > 500:
        roc = np.nan
    fcfta = safe_div(fcf, positive(total_assets)) * 100

    price = info.get("currentPrice", info.get("regularMarketPrice", np.nan))
    trailing_eps = info.get("trailingEps", np.nan)
    pe = info.get("trailingPE", np.nan)
    if pd.isna(pe) and not pd.isna(price) and not pd.isna(positive(trailing_eps)):
        pe = positive(price) / positive(trailing_eps)
    if pd.isna(pe) or float(pe) <= 0 or float(pe) > 1000:
        pe = np.nan

    sta = safe_div(net_income - cfo, positive(total_assets)) * 100 if not pd.isna(net_income) and not pd.isna(cfo) else np.nan
    if not pd.isna(sta) and abs(float(sta)) > 500:
        sta = np.nan

    snoa_numerator = (
        total_debt + equity - cash
        if not any(pd.isna(value) for value in [total_debt, equity, cash])
        else np.nan
    )
    snoa = safe_div(snoa_numerator, positive(prior_assets)) * 100
    fcfta = safe_div(fcf, positive(total_assets)) * 100
    roe = safe_div(net_income, positive(equity)) * 100
    if not pd.isna(roe) and abs(float(roe)) > 500:
        roe = np.nan
    debt_to_equity = safe_div(total_debt, positive(equity))
    if not pd.isna(debt_to_equity) and float(debt_to_equity) > 50:
        debt_to_equity = np.nan
    current_ratio = safe_div(positive(current_assets), positive(current_liabilities))
    if not pd.isna(current_ratio) and float(current_ratio) > 10:
        current_ratio = np.nan

    roe = safe_div(net_income, positive(equity)) * 100
    if not pd.isna(roe) and abs(float(roe)) > 500:
        roe = np.nan
    debt_to_equity = safe_div(total_debt, positive(equity))
    if not pd.isna(debt_to_equity) and float(debt_to_equity) > 50:
        debt_to_equity = np.nan
    current_ratio = safe_div(positive(current_assets), positive(current_liabilities))
    if not pd.isna(current_ratio) and float(current_ratio) > 10:
        current_ratio = np.nan

    sector = (
        universe_row["Sector"]
        if universe_row is not None and pd.notna(universe_row["Sector"])
        else info.get("sector", np.nan)
    )
    company = info.get("longName") or info.get("shortName") or ticker
    if universe_row is not None and pd.notna(universe_row["Company"]):
        company = universe_row["Company"]

    return {
        "Company": company,
        "Ticker": ticker,
        "Sector": sector,
        "Reporting Currency": info.get("currency") or info.get("financialCurrency") or np.nan,
        "Gross Profitability": safe_div(gross_profit, positive(total_assets)),
        "Gross Margin (%)": safe_div(gross_profit, positive(revenue)) * 100,
        "Operating Margin (%)": safe_div(operating_income, positive(revenue)) * 100,
        "EBITDA Margin (%)": safe_div(ebitda, positive(revenue)) * 100,
        "Net Profit Margin (%)": safe_div(net_income, positive(revenue)) * 100,
        "Return on Assets (%)": safe_div(net_income, positive(total_assets)) * 100,
        "Return on Equity (%)": roe,
        "Asset Turnover": safe_div(revenue, positive(total_assets)),
        "Operating Cash Flow / Assets (%)": safe_div(cfo, positive(total_assets)) * 100,
        "FCFTA (%)": fcfta,
        "EBIT/TEV (%)": ebit_tev,
        "ROC (%)": roc,
        "EPS (Basic)": eps,
        "Buyback Yield (%)": safe_div(net_repurchase, positive(market_cap)) * 100,
        "Net Equity Issuance (%)": (
            -safe_div(net_repurchase, positive(market_cap)) * 100
            if not pd.isna(net_repurchase) and not pd.isna(positive(market_cap))
            else np.nan
        ),
        "P/E Ratio": pe,
        "Debt/Equity": debt_to_equity,
        "Current Ratio": current_ratio,
        "EPS Growth (%)": growth(eps, eps_prior, minimum_prior=0.10),
        "FCF Growth (%)": growth(fcf, fcf_prior, minimum_prior=1_000_000),
        "STA (%)": sta,
        "SNOA (%)": snoa,
    }


def main():
    universe = pd.read_csv(UNIVERSE_FILE)
    universe["Ticker"] = universe["Ticker"].astype(str).str.replace(".", "-", regex=False)
    universe_by_ticker = universe.set_index("Ticker")

    with open(CACHE_FILE, "rb") as handle:
        records = pickle.load(handle)

    rows = []
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    for ticker, record in records.items():
        universe_row = (
            universe_by_ticker.loc[ticker]
            if ticker in universe_by_ticker.index
            else None
        )
        row = calculate(ticker, record, universe_row)
        status = record.get("download_error")
        if status or not record.get("info"):
            status = status or "Missing company information"
        else:
            status = "OK"
        row["Download Status"] = status
        row["Calculation Timestamp"] = timestamp
        row["Formula Version"] = FORMULA_VERSION
        row["Restatement Flag"] = np.nan
        rows.append(row)

    snapshot = pd.DataFrame(rows)
    snapshot = snapshot.merge(
        universe[["Ticker", "Sector", "Company"]],
        on="Ticker",
        how="left",
        suffixes=("", "_Universe"),
    )
    snapshot["Sector"] = snapshot["Sector"].fillna(snapshot["Sector_Universe"])
    snapshot["Company"] = snapshot["Company"].fillna(snapshot["Company_Universe"])
    snapshot = snapshot.drop(
        columns=[column for column in snapshot.columns if column.endswith("_Universe")]
    )
    snapshot.to_csv(OUTPUT_SNAPSHOT, index=False)

    history_rows = []
    for ticker, record in records.items():
        if record.get("download_error") or not record.get("info"):
            continue
        universe_row = (
            universe_by_ticker.loc[ticker]
            if ticker in universe_by_ticker.index
            else None
        )
        income = statement(record.get("income"))
        balance = statement(record.get("balance"))
        cashflow = statement(record.get("cashflow"))
        info = record.get("info", {}) or {}
        currency = info.get("currency") or info.get("financialCurrency") or np.nan
        sector = (
            universe_row["Sector"]
            if universe_row is not None and pd.notna(universe_row["Sector"])
            else info.get("sector", np.nan)
        )
        company = (
            universe_row["Company"]
            if universe_row is not None and pd.notna(universe_row["Company"])
            else info.get("longName") or info.get("shortName") or ticker
        )

        for column in range(min(3, income.shape[1])):
            try:
                fiscal_year = int(pd.Timestamp(income.columns[column]).year)
            except Exception:
                continue

            revenue = get_value(income, ["Total Revenue", "Operating Revenue"], column)
            gross_profit = get_value(income, ["Gross Profit"], column)
            cost_revenue = get_value(income, ["Cost Of Revenue", "Cost of Revenue"], column)
            if pd.isna(gross_profit) and not pd.isna(revenue) and not pd.isna(cost_revenue):
                gross_profit = revenue - cost_revenue
            operating_income = get_value(income, ["Operating Income", "Operating Income Loss"], column)
            depreciation_amortization = get_value(
                income,
                [
                    "Depreciation And Amortization In Income Statement",
                    "Depreciation Amortization Depletion Income Statement",
                    "Reconciled Depreciation",
                ],
                column,
            )
            if pd.isna(depreciation_amortization):
                ebitda = get_value(income, ["EBITDA", "Normalized EBITDA"], column)
            elif not pd.isna(operating_income):
                ebitda = operating_income + abs(depreciation_amortization)
            else:
                ebitda = np.nan
            net_income = get_value(income, ["Net Income", "Net Income Common Stockholders",
                                            "Net Income From Continuing Operations"], column)
            basic_shares = get_value(income, ["Basic Average Shares"], column)
            basic_shares_prior = get_value(income, ["Basic Average Shares"], column + 1)
            eps = (
                safe_div(net_income, positive(basic_shares))
                if not pd.isna(net_income)
                else np.nan
            )
            eps_prior = (
                safe_div(
                    get_value(
                        income,
                        ["Net Income", "Net Income Common Stockholders",
                         "Net Income From Continuing Operations"],
                        column + 1,
                    ),
                    positive(basic_shares_prior),
                )
                if not pd.isna(basic_shares_prior)
                else np.nan
            )

            assets = get_value(balance, ["Total Assets"], column)
            prior_assets = get_value(balance, ["Total Assets"], column + 1)
            equity = get_value(balance, ["Stockholders Equity", "Total Equity Gross Minority Interest",
                                         "Common Stock Equity"], column)
            prior_equity = get_value(balance, ["Stockholders Equity", "Total Equity Gross Minority Interest",
                                               "Common Stock Equity"], column + 1)
            debt = get_value(balance, ["Total Debt"], column)
            cash = get_value(balance, ["Cash Cash Equivalents And Short Term Investments",
                                       "Cash And Cash Equivalents", "Cash And Short Term Investments"], column)
            current_assets = get_value(balance, ["Current Assets"], column)
            current_liabilities = get_value(balance, ["Current Liabilities"], column)
            cfo = get_value(cashflow, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities",
                                       "Total Cash From Operating Activities"], column)
            capex = get_value(cashflow, ["Capital Expenditure", "Capital Expenditures"], column)
            fcf = cfo + capex if not pd.isna(cfo) and not pd.isna(capex) else np.nan
            cfo_prior = get_value(cashflow, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities",
                                             "Total Cash From Operating Activities"], column + 1)
            capex_prior = get_value(cashflow, ["Capital Expenditure", "Capital Expenditures"], column + 1)
            fcf_prior = cfo_prior + capex_prior if not pd.isna(cfo_prior) and not pd.isna(capex_prior) else np.nan

            sta = safe_div(net_income - cfo, positive(assets)) * 100 if not pd.isna(net_income) and not pd.isna(cfo) else np.nan
            if not pd.isna(sta) and abs(float(sta)) > 500:
                sta = np.nan
            snoa_numerator = (
                debt + equity - cash
                if not any(pd.isna(value) for value in [debt, equity, cash])
                else np.nan
            )
            snoa = safe_div(snoa_numerator, positive(prior_assets)) * 100
            roe = safe_div(net_income, positive(equity)) * 100
            if not pd.isna(roe) and abs(float(roe)) > 500:
                roe = np.nan
            debt_to_equity = safe_div(debt, positive(equity))
            if not pd.isna(debt_to_equity) and float(debt_to_equity) > 50:
                debt_to_equity = np.nan
            current_ratio = safe_div(positive(current_assets), positive(current_liabilities))
            if not pd.isna(current_ratio) and float(current_ratio) > 10:
                current_ratio = np.nan
            fcfta = safe_div(fcf, positive(assets)) * 100

            history_rows.append({
                "Company": company,
                "Ticker": ticker,
                "Sector": sector,
                "Fiscal Year": fiscal_year,
                "Revenue": revenue,
                "Net Income": net_income,
                "EPS (Basic)": eps,
                "Free Cash Flow": fcf,
                "Gross Profitability": safe_div(gross_profit, positive(assets)),
                "Gross Margin (%)": safe_div(gross_profit, positive(revenue)) * 100,
                "Operating Margin (%)": safe_div(operating_income, positive(revenue)) * 100,
                "EBITDA Margin (%)": safe_div(ebitda, positive(revenue)) * 100,
                "Net Profit Margin (%)": safe_div(net_income, positive(revenue)) * 100,
                "Return on Assets (%)": safe_div(net_income, positive(assets)) * 100,
                "Return on Equity (%)": roe,
                "Asset Turnover": safe_div(revenue, positive(assets)),
                "Debt/Equity": debt_to_equity,
                "Current Ratio": current_ratio,
                "EPS Growth (%)": growth(eps, eps_prior, minimum_prior=0.10),
                "FCF Growth (%)": growth(fcf, fcf_prior, minimum_prior=1_000_000),
                "STA (%)": sta,
                "SNOA (%)": snoa,
                "Operating Cash Flow / Assets (%)": safe_div(cfo, positive(assets)) * 100,
                "FCFTA (%)": fcfta,
                "Reporting Currency": currency,
                "Calculation Timestamp": timestamp,
                "Formula Version": FORMULA_VERSION,
                "Restatement Flag": np.nan,
            })

    history = pd.DataFrame(history_rows)
    history.to_csv(OUTPUT_HISTORY, index=False)
    print(f"Saved {len(snapshot)} snapshot rows")
    print(f"Saved {len(history)} historical rows")


if __name__ == "__main__":
    main()
