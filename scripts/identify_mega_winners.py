"""
Identify mega-winner stocks on IDX for 2024 and 2025.

A "mega winner" is any stock that experienced >50% price increase
(trough-to-peak) at ANY point during a calendar year.

Algorithm: Max drawup — O(n) scan tracking running minimum (using daily low)
and computing gain to daily high. Records the trough/peak dates and prices
that produced the maximum gain.

Output: mega_winners_analysis.xlsx with three sheets:
  - Mega Winners 2024
  - Mega Winners 2025
  - All Stocks Summary

Standalone script — no dependency on project database or config.
"""

import logging
import time
from datetime import datetime

import pandas as pd
import yfinance as yf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Ticker list (source: scraper/price_scraper.py) ──────────────────────

LQ45_TICKERS = [
    # ── LQ45 (Large Cap) ──
    "ACES", "ADRO", "AKRA", "AMMN", "AMRT", "ANTM", "ASII", "BBCA",
    "BBNI", "BBRI", "BBTN", "BFIN", "BMRI", "BRPT", "BUKA", "CPIN",
    "CTRA", "ESSA", "EXCL", "GGRM", "GOTO", "HRUM", "ICBP", "INCO",
    "INDF", "INKP", "INTP", "ITMG", "JPFA", "KLBF", "MAPA", "MAPI",
    "MBMA", "MDKA", "MEDC", "MIKA", "PGAS", "PGEO", "SMGR", "TBIG",
    "TINS", "TLKM", "TOWR", "TPIA", "UNTR", "UNVR",
    # ── IDX SMC Liquid (Mid Cap — 2nd Tier) ──
    "AALI", "AGII", "AKPI", "ALTO", "ARNA", "BALI",
    "BBKP", "BBSS", "BCIP", "BIRD", "BJTM", "BSDE",
    "BTPS", "CMRY", "DMAS", "DSNG", "DSSA",
    "ELSA", "EMTK", "ERAA", "FILM", "GJTL", "HEXA", "HMSP",
    "HOKI", "HRTA", "IGAR", "INDY", "INTA", "IPOL", "ISAT",
    "JARR", "JSMR", "KBLI", "KIJA", "LINK",
    "LPPF", "MDIA", "MDLN", "MKPI", "MNCN", "MTEL",
    "MYOR", "NCKL", "NIKL", "PNBN", "PTBA", "PTPP", "PTRO", "PWON", "RALS",
    "SCMA", "SIDO", "SILO", "SMRA", "SRTG", "SSMS",
    "TKIM", "TOTL", "TSPC", "WIKA", "WSBP", "WTON",
    # ── Expansion Batch 1 (Apr 2026) ──
    "AADI", "ADMR", "BREN", "BRIS", "CUAN", "DEWA", "PANI", "PSAB",
    "RAJA", "RATU", "WIFI",
    # ── Expansion Batch 2 (Apr 2026) ──
    "ADHI", "AGRO", "AMAN", "ARGO", "ARTO", "ASSA", "AVIA", "BNBA",
    "DOID", "ENRG", "IMAS", "KRAS", "POWR", "SMBR", "SMDR", "WIIM",
    # ── Expansion Batch 3 (Apr 2026) ──
    "INET",
]

# ── Sector mapping (source: scraper/price_scraper.py) ───────────────────

TICKER_SECTORS: dict = {
    "AALI": "Consumer Defensive", "ACES": "Consumer Cyclical",
    "ADRO": "Energy", "AGII": "Basic Materials",
    "AKPI": "Consumer Cyclical", "AKRA": "Energy",
    "ALTO": "Consumer Defensive", "AMMN": "Basic Materials",
    "AMRT": "Consumer Defensive", "ANTM": "Basic Materials",
    "ARNA": "Industrials", "ASII": "Industrials",
    "BALI": "Communication Services", "BBCA": "Financial Services",
    "BBKP": "Financial Services", "BBNI": "Financial Services",
    "BBRI": "Financial Services", "BBSS": "Industrials",
    "BBTN": "Financial Services", "BCIP": "Real Estate",
    "BFIN": "Financial Services", "BIRD": "Industrials",
    "BJTM": "Financial Services", "BMRI": "Financial Services",
    "BRPT": "Basic Materials", "BSDE": "Real Estate",
    "BTPS": "Financial Services", "BUKA": "Consumer Cyclical",
    "CMRY": "Consumer Defensive", "CPIN": "Consumer Defensive",
    "CTRA": "Real Estate", "DMAS": "Real Estate",
    "DSNG": "Consumer Defensive", "DSSA": "Energy",
    "ELSA": "Energy", "EMTK": "Communication Services",
    "ERAA": "Consumer Cyclical", "ESSA": "Basic Materials",
    "EXCL": "Communication Services", "FILM": "Communication Services",
    "GGRM": "Consumer Defensive", "GJTL": "Consumer Cyclical",
    "GOTO": "Technology", "HEXA": "Industrials",
    "HMSP": "Consumer Defensive", "HOKI": "Consumer Defensive",
    "HRTA": "Consumer Cyclical", "HRUM": "Energy",
    "ICBP": "Consumer Defensive", "IGAR": "Consumer Cyclical",
    "INCO": "Basic Materials", "INDF": "Consumer Defensive",
    "INDY": "Energy", "INKP": "Basic Materials",
    "INTA": "Industrials", "INTP": "Basic Materials",
    "IPOL": "Consumer Cyclical", "ISAT": "Communication Services",
    "ITMG": "Energy", "JARR": "Consumer Defensive",
    "JPFA": "Consumer Defensive", "JSMR": "Industrials",
    "KBLI": "Industrials", "KIJA": "Real Estate",
    "KLBF": "Healthcare", "LINK": "Communication Services",
    "LPPF": "Consumer Cyclical", "MAPA": "Consumer Cyclical",
    "MAPI": "Consumer Cyclical", "MBMA": "Basic Materials",
    "MDIA": "Communication Services", "MDKA": "Basic Materials",
    "MDLN": "Real Estate", "MEDC": "Energy",
    "MIKA": "Healthcare", "MKPI": "Real Estate",
    "MNCN": "Communication Services", "MTEL": "Communication Services",
    "MYOR": "Consumer Defensive", "NCKL": "Basic Materials",
    "NIKL": "Industrials", "PGAS": "Utilities",
    "PGEO": "Utilities", "PNBN": "Financial Services",
    "PTBA": "Energy", "PTPP": "Industrials",
    "PTRO": "Basic Materials", "PWON": "Real Estate",
    "RALS": "Consumer Cyclical", "SCMA": "Communication Services",
    "SIDO": "Healthcare", "SILO": "Healthcare",
    "SMGR": "Basic Materials", "SMRA": "Real Estate",
    "SRTG": "Financial Services", "SSMS": "Consumer Defensive",
    "TBIG": "Communication Services", "TINS": "Basic Materials",
    "TKIM": "Basic Materials", "TLKM": "Communication Services",
    "TOTL": "Industrials", "TOWR": "Real Estate",
    "TPIA": "Basic Materials", "TSPC": "Industrials",
    "UNTR": "Basic Materials", "UNVR": "Consumer Defensive",
    "WIKA": "Industrials", "WSBP": "Basic Materials",
    "WTON": "Basic Materials",
}

# ── Core functions ───────────────────────────────────────────────────────


def download_ticker_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Download OHLCV from yfinance. Returns empty DataFrame on failure."""
    for attempt in range(3):
        try:
            t = yf.Ticker(f"{ticker}.JK")
            df = t.history(start=start, end=end, auto_adjust=False)
            if df is not None and not df.empty:
                df.columns = [c.lower().replace(" ", "_") for c in df.columns]
                df = df.reset_index()
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
                return df
            return pd.DataFrame()
        except Exception as e:
            wait = (2 ** attempt)
            logger.warning(f"{ticker}: attempt {attempt+1} failed ({e}), retrying in {wait}s")
            time.sleep(wait)
    return pd.DataFrame()


def calculate_max_drawup(df: pd.DataFrame) -> dict:
    """
    Calculate maximum trough-to-peak gain within a price series.

    Uses daily low for trough tracking and daily high for peak measurement
    to capture the true intraday maximum drawup.

    Returns dict with drawup stats, or zeros/None if insufficient data.
    """
    if len(df) < 2:
        return {
            "max_drawup_pct": 0.0,
            "trough_date": None, "trough_price": None,
            "peak_date": None, "peak_price": None,
            "move_duration_days": 0,
        }

    running_min = float("inf")
    running_min_date = None
    max_drawup = 0.0
    best = {"trough_date": None, "trough_price": None,
            "peak_date": None, "peak_price": None}

    for _, row in df.iterrows():
        low = row["low"]
        high = row["high"]
        date = row["date"]

        if low < running_min:
            running_min = low
            running_min_date = date

        if running_min > 0:
            gain = (high - running_min) / running_min
            if gain > max_drawup:
                max_drawup = gain
                best["trough_date"] = running_min_date
                best["trough_price"] = running_min
                best["peak_date"] = date
                best["peak_price"] = high

    duration = 0
    if best["trough_date"] is not None and best["peak_date"] is not None:
        duration = (best["peak_date"] - best["trough_date"]).days

    return {
        "max_drawup_pct": round(max_drawup * 100, 2),
        "trough_date": best["trough_date"],
        "trough_price": best["trough_price"],
        "peak_date": best["peak_date"],
        "peak_price": best["peak_price"],
        "move_duration_days": duration,
    }


def analyze_ticker(ticker: str, full_df: pd.DataFrame) -> list:
    """Analyze a ticker's data for both 2024 and 2025, return list of result dicts."""
    results = []
    sector = TICKER_SECTORS.get(ticker, "Unknown")

    for year in [2024, 2025]:
        year_df = full_df[full_df["date"].dt.year == year].copy()
        if year_df.empty:
            continue

        year_df = year_df.dropna(subset=["close", "low", "high"])
        if len(year_df) < 2:
            continue

        year_df = year_df.sort_values("date").reset_index(drop=True)

        drawup = calculate_max_drawup(year_df)
        year_start = year_df.iloc[0]["close"]
        year_end = year_df.iloc[-1]["close"]
        year_return = round((year_end - year_start) / year_start * 100, 2) if year_start > 0 else 0.0

        results.append({
            "ticker": ticker,
            "sector": sector,
            "year": year,
            "max_drawup_pct": drawup["max_drawup_pct"],
            "trough_date": drawup["trough_date"],
            "trough_price": drawup["trough_price"],
            "peak_date": drawup["peak_date"],
            "peak_price": drawup["peak_price"],
            "move_duration_days": drawup["move_duration_days"],
            "year_start_price": round(year_start, 2),
            "year_end_price": round(year_end, 2),
            "year_return_pct": year_return,
        })

    return results


def main():
    logger.info(f"Starting mega-winner analysis for {len(LQ45_TICKERS)} tickers")

    all_results = []
    skipped = []

    for i, ticker in enumerate(LQ45_TICKERS, 1):
        df = download_ticker_data(ticker, "2024-01-01", "2025-12-31")
        if df.empty:
            logger.warning(f"[{i}/{len(LQ45_TICKERS)}] {ticker}: NO DATA — skipped")
            skipped.append(ticker)
        else:
            results = analyze_ticker(ticker, df)
            for r in results:
                label = f"{r['year']} drawup={r['max_drawup_pct']:+.1f}%"
                all_results.append(r)
            years_str = ", ".join(
                f"{r['year']} drawup={r['max_drawup_pct']:+.1f}%"
                for r in results
            ) if results else "no valid data"
            logger.info(f"[{i}/{len(LQ45_TICKERS)}] {ticker}: {years_str}")

        if i < len(LQ45_TICKERS):
            time.sleep(1)

    # Build DataFrame
    df_all = pd.DataFrame(all_results)

    if df_all.empty:
        logger.error("No data collected for any ticker!")
        # Write empty Excel so artifact upload still works
        with pd.ExcelWriter("mega_winners_analysis.xlsx", engine="openpyxl") as w:
            pd.DataFrame().to_excel(w, sheet_name="Mega Winners 2024", index=False)
            pd.DataFrame().to_excel(w, sheet_name="Mega Winners 2025", index=False)
            pd.DataFrame().to_excel(w, sheet_name="All Stocks Summary", index=False)
        return

    # Format date columns as strings for clean Excel output
    for col in ["trough_date", "peak_date"]:
        df_all[col] = pd.to_datetime(df_all[col]).dt.strftime("%Y-%m-%d")

    # Mega winners: >50% max drawup
    mega_2024 = (df_all[(df_all["year"] == 2024) & (df_all["max_drawup_pct"] > 50)]
                 .sort_values("max_drawup_pct", ascending=False)
                 .reset_index(drop=True))
    mega_2025 = (df_all[(df_all["year"] == 2025) & (df_all["max_drawup_pct"] > 50)]
                 .sort_values("max_drawup_pct", ascending=False)
                 .reset_index(drop=True))
    summary = df_all.sort_values(["ticker", "year"]).reset_index(drop=True)

    # Write Excel
    with pd.ExcelWriter("mega_winners_analysis.xlsx", engine="openpyxl") as w:
        mega_2024.to_excel(w, sheet_name="Mega Winners 2024", index=False)
        mega_2025.to_excel(w, sheet_name="Mega Winners 2025", index=False)
        summary.to_excel(w, sheet_name="All Stocks Summary", index=False)

    logger.info("=" * 60)
    logger.info(f"Excel written: mega_winners_analysis.xlsx")
    logger.info(f"Tickers processed: {len(LQ45_TICKERS) - len(skipped)}/{len(LQ45_TICKERS)}")
    logger.info(f"Tickers skipped (no data): {len(skipped)} — {skipped}")
    logger.info(f"Mega winners 2024 (>50% drawup): {len(mega_2024)}")
    logger.info(f"Mega winners 2025 (>50% drawup): {len(mega_2025)}")

    # Print top mega winners
    for year, df_mega in [("2024", mega_2024), ("2025", mega_2025)]:
        if not df_mega.empty:
            logger.info(f"\n── Top Mega Winners {year} ──")
            for _, row in df_mega.head(10).iterrows():
                logger.info(
                    f"  {row['ticker']:6s} ({row['sector']:20s}) "
                    f"drawup={row['max_drawup_pct']:+6.1f}%  "
                    f"trough={row['trough_date']} @ {row['trough_price']:.0f} → "
                    f"peak={row['peak_date']} @ {row['peak_price']:.0f}  "
                    f"({row['move_duration_days']}d)"
                )


if __name__ == "__main__":
    main()
