"""
Step 2: Mega-Winner Pattern Analysis

Comprehensive analysis of what patterns predict mega-winner stocks (>50% gain)
BEFORE their moves start. Covers volume accumulation, price action, relative
strength, broker flow, signal simulation, and statistical comparison.

Input: yfinance OHLCV (2023-2025) + broker data from idx-database artifact
Output: mega_winners_pattern_analysis.xlsx with 9 analysis sheets

Standalone script — downloads OHLCV from yfinance, reads broker data from
local SQLite database (provided by workflow artifact).
"""

import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Ticker list & sectors (from scraper/price_scraper.py) ────────────────

LQ45_TICKERS = [
    "ACES", "ADRO", "AKRA", "AMMN", "AMRT", "ANTM", "ASII", "BBCA",
    "BBNI", "BBRI", "BBTN", "BFIN", "BMRI", "BRPT", "BUKA", "CPIN",
    "CTRA", "ESSA", "EXCL", "GGRM", "GOTO", "HRUM", "ICBP", "INCO",
    "INDF", "INKP", "INTP", "ITMG", "JPFA", "KLBF", "MAPA", "MAPI",
    "MBMA", "MDKA", "MEDC", "MIKA", "PGAS", "PGEO", "SMGR", "TBIG",
    "TINS", "TLKM", "TOWR", "TPIA", "UNTR", "UNVR",
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
    "AADI", "ADMR", "BREN", "BRIS", "CUAN", "DEWA", "PANI", "PSAB",
    "RAJA", "RATU", "WIFI",
    "ADHI", "AGRO", "AMAN", "ARGO", "ARTO", "ASSA", "AVIA", "BNBA",
    "DOID", "ENRG", "IMAS", "KRAS", "POWR", "SMBR", "SMDR", "WIIM",
    "INET",
]

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

MIN_LIQUIDITY_BN = 1.0  # Rp 1B/day minimum avg daily value

# ═══════════════════════════════════════════════════════════════
# SECTION 1: DATA LOADING
# ═══════════════════════════════════════════════════════════════


def download_ticker_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Download OHLCV from yfinance. Returns empty DataFrame on failure."""
    for attempt in range(3):
        try:
            t = yf.Ticker(f"{ticker}.JK")
            df = t.history(start=start, end=end, auto_adjust=False)
            if df is not None and not df.empty:
                df = df.reset_index()
                df.columns = [c.lower().replace(" ", "_") for c in df.columns]
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
                elif "datetime" in df.columns:
                    df = df.rename(columns={"datetime": "date"})
                    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
                return df
            return pd.DataFrame()
        except Exception as e:
            wait = 2 ** attempt
            logger.warning(f"{ticker}: attempt {attempt+1} failed ({e}), retry in {wait}s")
            time.sleep(wait)
    return pd.DataFrame()


def load_broker_data(db_path: str) -> pd.DataFrame:
    """Load aggregated daily Asing (foreign) broker flow from SQLite."""
    if not os.path.exists(db_path):
        logger.warning(f"Database not found: {db_path}")
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(db_path)
        # Check if table exists and has data
        count = conn.execute(
            "SELECT COUNT(*) FROM broker_summary"
        ).fetchone()[0]
        if count == 0:
            logger.warning("broker_summary table is empty")
            conn.close()
            return pd.DataFrame()

        # Aggregate per-broker data to daily Asing flow per ticker
        df = pd.read_sql_query("""
            SELECT
                ticker,
                date,
                broker_type,
                SUM(buy_value) as buy_value,
                SUM(sell_value) as sell_value,
                SUM(net_value) as net_value,
                SUM(buy_volume) as buy_volume,
                SUM(sell_volume) as sell_volume,
                SUM(net_volume) as net_volume,
                COUNT(DISTINCT broker_code) as broker_count
            FROM broker_summary
            GROUP BY ticker, date, broker_type
        """, conn)
        conn.close()
        df["date"] = pd.to_datetime(df["date"])
        logger.info(f"Loaded broker data: {len(df):,} rows, "
                     f"dates {df['date'].min().date()} to {df['date'].max().date()}")
        return df
    except Exception as e:
        logger.warning(f"Error loading broker data: {e}")
        return pd.DataFrame()


def get_asing_flow(broker_df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Extract daily Asing (foreign) flow for a single ticker."""
    if broker_df.empty:
        return pd.DataFrame()
    mask = (broker_df["ticker"] == ticker) & (broker_df["broker_type"] == "Asing")
    df = broker_df[mask][["date", "net_value", "buy_value", "sell_value",
                           "net_volume", "broker_count"]].copy()
    df = df.sort_values("date").set_index("date")
    return df


def get_all_broker_flow(broker_df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Get total flow across all broker types for computing participation rates."""
    if broker_df.empty:
        return pd.DataFrame()
    mask = broker_df["ticker"] == ticker
    df = broker_df[mask].groupby("date").agg({
        "buy_value": "sum", "sell_value": "sum",
    }).rename(columns={"buy_value": "total_buy", "sell_value": "total_sell"})
    df["total_value"] = df["total_buy"] + df["total_sell"]
    return df


# ═══════════════════════════════════════════════════════════════
# SECTION 2: TECHNICAL INDICATORS
# ═══════════════════════════════════════════════════════════════


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all technical indicators on an OHLCV DataFrame."""
    d = df.copy()
    c, h, l, v = d["close"], d["high"], d["low"], d["volume"]

    # Moving averages
    d["ma10"] = c.rolling(10, min_periods=5).mean()
    d["ma20"] = c.rolling(20, min_periods=10).mean()
    d["ma50"] = c.rolling(50, min_periods=30).mean()
    d["ma200"] = c.rolling(200, min_periods=100).mean()

    # RSI(14)
    delta = c.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(span=14, adjust=False).mean()
    avg_loss = loss.ewm(span=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    d["rsi"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    d["macd_line"] = ema12 - ema26
    d["macd_signal"] = d["macd_line"].ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d["macd_line"] - d["macd_signal"]

    # ATR(14)
    tr = pd.concat([
        h - l,
        (h - c.shift(1)).abs(),
        (l - c.shift(1)).abs(),
    ], axis=1).max(axis=1)
    d["atr"] = tr.rolling(14, min_periods=7).mean()
    d["atr_pct"] = d["atr"] / c

    # Volume
    d["vol_avg_20"] = v.rolling(20, min_periods=5).mean()
    d["vol_ratio"] = v / d["vol_avg_20"].replace(0, np.nan)

    # Bollinger Bands
    d["bb_mid"] = c.rolling(20, min_periods=10).mean()
    bb_std = c.rolling(20, min_periods=10).std()
    d["bb_upper"] = d["bb_mid"] + 2 * bb_std
    d["bb_lower"] = d["bb_mid"] - 2 * bb_std
    d["bb_width"] = (d["bb_upper"] - d["bb_lower"]) / d["bb_mid"]

    # OBV (On-Balance Volume)
    obv_direction = np.sign(c.diff()).fillna(0)
    d["obv"] = (v * obv_direction).cumsum()

    # Accumulation/Distribution Line
    clv = ((c - l) - (h - c)) / (h - l).replace(0, np.nan)
    d["ad_line"] = (clv.fillna(0) * v).cumsum()

    # Chaikin Money Flow (20d)
    mfv = clv.fillna(0) * v
    d["cmf_20"] = mfv.rolling(20, min_periods=10).sum() / v.rolling(20, min_periods=10).sum()

    # N-day highs for breakout detection
    for n in [10, 15, 20, 30, 40, 60]:
        d[f"high_{n}d"] = h.rolling(n, min_periods=n).max().shift(1)

    # Selling pressure (from signal_combiner.py)
    candle_range = h - l
    upper_shadow = h - c
    d["upper_shadow_ratio"] = upper_shadow / candle_range.replace(0, np.nan)
    close_position = (c - l) / candle_range.replace(0, np.nan)
    d["has_selling_pressure"] = (
        (d["upper_shadow_ratio"] > 0.40) | (close_position < 0.33)
    )

    # Daily return
    d["return"] = c.pct_change()

    # 52-week high/low
    d["high_52w"] = h.rolling(252, min_periods=60).max()
    d["low_52w"] = l.rolling(252, min_periods=60).min()

    return d


# ═══════════════════════════════════════════════════════════════
# SECTION 3: MEGA-WINNER IDENTIFICATION (from Step 1)
# ═══════════════════════════════════════════════════════════════


def calculate_max_drawup(df: pd.DataFrame) -> dict:
    """Max trough-to-peak gain using daily low for trough, daily high for peak."""
    if len(df) < 2:
        return {"max_drawup_pct": 0, "trough_date": None, "trough_price": None,
                "peak_date": None, "peak_price": None, "move_duration_days": 0}

    running_min = float("inf")
    running_min_date = None
    max_drawup = 0.0
    best = {"trough_date": None, "trough_price": None,
            "peak_date": None, "peak_price": None}

    for _, row in df.iterrows():
        if row["low"] < running_min:
            running_min = row["low"]
            running_min_date = row["date"]
        if running_min > 0:
            gain = (row["high"] - running_min) / running_min
            if gain > max_drawup:
                max_drawup = gain
                best["trough_date"] = running_min_date
                best["trough_price"] = running_min
                best["peak_date"] = row["date"]
                best["peak_price"] = row["high"]

    dur = 0
    if best["trough_date"] is not None and best["peak_date"] is not None:
        dur = (best["peak_date"] - best["trough_date"]).days
    return {
        "max_drawup_pct": round(max_drawup * 100, 2),
        "trough_date": best["trough_date"],
        "trough_price": best["trough_price"],
        "peak_date": best["peak_date"],
        "peak_price": best["peak_price"],
        "move_duration_days": dur,
    }


def identify_mega_winners(all_data: dict, year: int) -> list:
    """Identify liquid mega-winners for a given year."""
    results = []
    for ticker, df in all_data.items():
        ydf = df[df["date"].dt.year == year].copy()
        if len(ydf) < 20:
            continue
        ydf = ydf.dropna(subset=["close", "low", "high"]).sort_values("date").reset_index(drop=True)
        if len(ydf) < 20:
            continue

        drawup = calculate_max_drawup(ydf)
        avg_val_bn = (ydf["close"] * ydf["volume"]).mean() / 1e9

        if drawup["max_drawup_pct"] > 50 and avg_val_bn >= MIN_LIQUIDITY_BN:
            results.append({
                "ticker": ticker,
                "sector": TICKER_SECTORS.get(ticker, "Unknown"),
                "year": year,
                "max_drawup_pct": drawup["max_drawup_pct"],
                "trough_date": drawup["trough_date"],
                "trough_price": drawup["trough_price"],
                "peak_date": drawup["peak_date"],
                "peak_price": drawup["peak_price"],
                "move_duration_days": drawup["move_duration_days"],
                "avg_daily_value_bn": round(avg_val_bn, 3),
            })
    return results


# ═══════════════════════════════════════════════════════════════
# MODULE 1: VOLUME ACCUMULATION ANALYSIS
# ═══════════════════════════════════════════════════════════════


def analyze_volume_accumulation(df_ind: pd.DataFrame, trough_date, trough_idx: int,
                                 asing_flow: pd.DataFrame, all_flow: pd.DataFrame) -> dict:
    """Analyze volume accumulation patterns before a mega-winner's move."""
    result = {}

    # Pre-trough windows
    for lookback in [10, 20, 40]:
        start_idx = max(0, trough_idx - lookback)
        pre = df_ind.iloc[start_idx:trough_idx + 1]
        if len(pre) < 5:
            for k in [f"obv_slope_{lookback}d", f"ad_slope_{lookback}d",
                       f"vol_trend_{lookback}d", f"up_down_vol_ratio_{lookback}d",
                       f"vol_surge_days_{lookback}d", f"vol_price_corr_{lookback}d"]:
                result[k] = np.nan
            continue

        # OBV slope (normalized by starting OBV to make comparable)
        obv_vals = pre["obv"].dropna()
        if len(obv_vals) >= 3:
            x = np.arange(len(obv_vals))
            slope = np.polyfit(x, obv_vals.values, 1)[0]
            obv_range = obv_vals.max() - obv_vals.min()
            result[f"obv_slope_{lookback}d"] = round(slope / max(abs(obv_range), 1) * 100, 4)
        else:
            result[f"obv_slope_{lookback}d"] = np.nan

        # AD line slope
        ad_vals = pre["ad_line"].dropna()
        if len(ad_vals) >= 3:
            x = np.arange(len(ad_vals))
            slope = np.polyfit(x, ad_vals.values, 1)[0]
            ad_range = ad_vals.max() - ad_vals.min()
            result[f"ad_slope_{lookback}d"] = round(slope / max(abs(ad_range), 1) * 100, 4)
        else:
            result[f"ad_slope_{lookback}d"] = np.nan

        # Volume trend slope (linear regression of volume)
        vol_vals = pre["volume"].dropna()
        if len(vol_vals) >= 3:
            x = np.arange(len(vol_vals))
            slope = np.polyfit(x, vol_vals.values, 1)[0]
            result[f"vol_trend_{lookback}d"] = round(slope / max(vol_vals.mean(), 1) * 100, 4)
        else:
            result[f"vol_trend_{lookback}d"] = np.nan

        # Up-volume vs down-volume ratio
        up_vol = pre.loc[pre["return"] > 0, "volume"].sum()
        dn_vol = pre.loc[pre["return"] < 0, "volume"].sum()
        result[f"up_down_vol_ratio_{lookback}d"] = round(
            up_vol / max(dn_vol, 1), 3
        )

        # Volume surge days (>2x 20d average)
        result[f"vol_surge_days_{lookback}d"] = int(
            (pre["vol_ratio"] > 2.0).sum()
        )

        # Volume-price correlation (negative = accumulation pattern)
        if len(pre) >= 5:
            vols = pre["volume"].values
            rets = pre["return"].fillna(0).values
            if np.std(vols) > 0 and np.std(rets) > 0:
                result[f"vol_price_corr_{lookback}d"] = round(
                    np.corrcoef(vols, rets)[0, 1], 4
                )
            else:
                result[f"vol_price_corr_{lookback}d"] = np.nan
        else:
            result[f"vol_price_corr_{lookback}d"] = np.nan

    # CMF at trough
    result["cmf_at_trough"] = _safe_get(df_ind, trough_idx, "cmf_20")

    # Volume ratio at trough
    result["vol_ratio_at_trough"] = _safe_get(df_ind, trough_idx, "vol_ratio")

    # ── Broker-based metrics ──
    if not asing_flow.empty and trough_date is not None:
        for lookback in [10, 20]:
            start = trough_date - pd.Timedelta(days=int(lookback * 1.5))
            af = asing_flow.loc[start:trough_date]
            if len(af) >= 3:
                result[f"asing_net_cum_{lookback}d"] = round(af["net_value"].sum() / 1e9, 3)
                # Trend slope
                x = np.arange(len(af))
                vals = af["net_value"].values
                if np.std(vals) > 0:
                    result[f"asing_flow_slope_{lookback}d"] = round(
                        np.polyfit(x, vals, 1)[0] / max(abs(vals).mean(), 1) * 100, 4
                    )
                else:
                    result[f"asing_flow_slope_{lookback}d"] = np.nan
                # Consistency: % of days with positive net
                result[f"asing_positive_pct_{lookback}d"] = round(
                    (af["net_value"] > 0).mean() * 100, 1
                )
                # Broker count (average distinct Asing brokers)
                result[f"asing_broker_count_{lookback}d"] = round(
                    af["broker_count"].mean(), 1
                )
            else:
                for k in [f"asing_net_cum_{lookback}d", f"asing_flow_slope_{lookback}d",
                           f"asing_positive_pct_{lookback}d", f"asing_broker_count_{lookback}d"]:
                    result[k] = np.nan

        # Foreign participation rate at trough
        if not all_flow.empty and trough_date in asing_flow.index and trough_date in all_flow.index:
            asing_gross = (asing_flow.loc[trough_date, "buy_value"] +
                           asing_flow.loc[trough_date, "sell_value"])
            total = all_flow.loc[trough_date, "total_value"]
            result["asing_participation_pct"] = round(
                asing_gross / max(total, 1) * 100, 2
            ) if total > 0 else np.nan
        else:
            result["asing_participation_pct"] = np.nan
    else:
        for k in ["asing_net_cum_10d", "asing_net_cum_20d",
                   "asing_flow_slope_10d", "asing_flow_slope_20d",
                   "asing_positive_pct_10d", "asing_positive_pct_20d",
                   "asing_broker_count_10d", "asing_broker_count_20d",
                   "asing_participation_pct"]:
            result[k] = np.nan

    return result


# ═══════════════════════════════════════════════════════════════
# MODULE 2: PRICE ACTION & STRUCTURE ANALYSIS
# ═══════════════════════════════════════════════════════════════


def analyze_price_action(df_ind: pd.DataFrame, trough_idx: int) -> dict:
    """Analyze price structure and momentum at the trough."""
    result = {}
    row = df_ind.iloc[trough_idx]
    c = row["close"]

    # Price vs MAs
    for ma in ["ma20", "ma50", "ma200"]:
        val = row.get(ma, np.nan)
        if pd.notna(val) and val > 0:
            result[f"price_vs_{ma}_pct"] = round((c - val) / val * 100, 2)
        else:
            result[f"price_vs_{ma}_pct"] = np.nan

    # MA alignment: bullish (20>50>200), bearish (200>50>20), or mixed
    ma20, ma50, ma200 = row.get("ma20"), row.get("ma50"), row.get("ma200")
    if pd.notna(ma20) and pd.notna(ma50) and pd.notna(ma200):
        if ma20 > ma50 > ma200:
            result["ma_alignment"] = "bullish"
        elif ma200 > ma50 > ma20:
            result["ma_alignment"] = "bearish"
        else:
            result["ma_alignment"] = "mixed"
    else:
        result["ma_alignment"] = "insufficient_data"

    # 52-week position
    h52 = row.get("high_52w", np.nan)
    l52 = row.get("low_52w", np.nan)
    if pd.notna(l52) and l52 > 0:
        result["dist_52w_low_pct"] = round((c - l52) / l52 * 100, 2)
    else:
        result["dist_52w_low_pct"] = np.nan
    if pd.notna(h52) and h52 > 0:
        result["dist_52w_high_pct"] = round((c - h52) / h52 * 100, 2)
    else:
        result["dist_52w_high_pct"] = np.nan

    # RSI at trough
    result["rsi_at_trough"] = _safe_get(df_ind, trough_idx, "rsi")

    # RSI divergence: check if RSI making higher lows while price at/near low
    # Look at RSI 20 days before trough
    start_idx = max(0, trough_idx - 20)
    pre20 = df_ind.iloc[start_idx:trough_idx + 1]
    if len(pre20) >= 10:
        # Find the lowest RSI in first half vs second half
        mid = len(pre20) // 2
        first_half_rsi = pre20.iloc[:mid]["rsi"].min()
        second_half_rsi = pre20.iloc[mid:]["rsi"].min()
        first_half_low = pre20.iloc[:mid]["low"].min()
        second_half_low = pre20.iloc[mid:]["low"].min()
        # Bullish divergence: price makes lower low but RSI makes higher low
        if (pd.notna(first_half_rsi) and pd.notna(second_half_rsi)
                and pd.notna(first_half_low) and pd.notna(second_half_low)):
            result["rsi_divergence"] = (
                "bullish" if second_half_low <= first_half_low * 1.02
                and second_half_rsi > first_half_rsi + 2
                else "none"
            )
        else:
            result["rsi_divergence"] = "insufficient_data"
    else:
        result["rsi_divergence"] = "insufficient_data"

    # MACD at trough
    result["macd_hist_at_trough"] = _safe_get(df_ind, trough_idx, "macd_hist")
    result["macd_line_at_trough"] = _safe_get(df_ind, trough_idx, "macd_line")

    # ATR % at trough
    result["atr_pct_at_trough"] = _safe_get(df_ind, trough_idx, "atr_pct")

    # Bollinger Band width at trough
    result["bb_width_at_trough"] = _safe_get(df_ind, trough_idx, "bb_width")

    # BB width percentile (vs last 120 days)
    bb_start = max(0, trough_idx - 120)
    bb_window = df_ind.iloc[bb_start:trough_idx + 1]["bb_width"].dropna()
    if len(bb_window) >= 20:
        current_bb = row.get("bb_width", np.nan)
        if pd.notna(current_bb):
            result["bb_width_percentile"] = round(
                (bb_window < current_bb).mean() * 100, 1
            )
        else:
            result["bb_width_percentile"] = np.nan
    else:
        result["bb_width_percentile"] = np.nan

    # ATR compression: ATR now vs 60 days ago
    if trough_idx >= 60:
        atr_now = row.get("atr_pct", np.nan)
        atr_60ago = df_ind.iloc[trough_idx - 60].get("atr_pct", np.nan)
        if pd.notna(atr_now) and pd.notna(atr_60ago) and atr_60ago > 0:
            result["atr_compression_ratio"] = round(atr_now / atr_60ago, 3)
        else:
            result["atr_compression_ratio"] = np.nan
    else:
        result["atr_compression_ratio"] = np.nan

    # Consolidation analysis (20d and 40d before trough)
    for lookback in [20, 40]:
        s = max(0, trough_idx - lookback)
        window = df_ind.iloc[s:trough_idx + 1]
        if len(window) >= 10:
            avg_c = window["close"].mean()
            if avg_c > 0:
                result[f"consolidation_range_{lookback}d_pct"] = round(
                    (window["high"].max() - window["low"].min()) / avg_c * 100, 2
                )
            else:
                result[f"consolidation_range_{lookback}d_pct"] = np.nan

            # Higher lows count
            lows = window["low"].values
            hl_count = sum(1 for j in range(1, len(lows)) if lows[j] > lows[j-1])
            result[f"higher_lows_{lookback}d"] = hl_count

            # Range contraction days: daily range < 50% of avg daily range
            daily_range = window["high"] - window["low"]
            avg_range = daily_range.mean()
            if avg_range > 0:
                result[f"range_contraction_days_{lookback}d"] = int(
                    (daily_range < avg_range * 0.5).sum()
                )
            else:
                result[f"range_contraction_days_{lookback}d"] = 0
        else:
            result[f"consolidation_range_{lookback}d_pct"] = np.nan
            result[f"higher_lows_{lookback}d"] = np.nan
            result[f"range_contraction_days_{lookback}d"] = np.nan

    # Prior 60-day return (trend before trough)
    if trough_idx >= 60:
        c60ago = df_ind.iloc[trough_idx - 60]["close"]
        if c60ago > 0:
            result["prior_60d_return_pct"] = round((c - c60ago) / c60ago * 100, 2)
        else:
            result["prior_60d_return_pct"] = np.nan
    else:
        result["prior_60d_return_pct"] = np.nan

    return result


# ═══════════════════════════════════════════════════════════════
# MODULE 3: RELATIVE STRENGTH ANALYSIS
# ═══════════════════════════════════════════════════════════════


def analyze_relative_strength(df_ind: pd.DataFrame, ihsg_df: pd.DataFrame,
                                trough_idx: int, trough_date,
                                all_returns_20d: dict) -> dict:
    """Analyze relative strength vs IHSG and peers."""
    result = {}
    row = df_ind.iloc[trough_idx]

    # RS vs IHSG over 20d and 60d
    for period in [20, 60]:
        if trough_idx >= period:
            stock_ret = (row["close"] / df_ind.iloc[trough_idx - period]["close"]) - 1
            ihsg_row = ihsg_df[ihsg_df.index <= trough_date]
            if len(ihsg_row) >= period:
                ihsg_ret = (ihsg_row.iloc[-1]["close"] / ihsg_row.iloc[-1 - period]["close"]) - 1
                if ihsg_ret != 0:
                    result[f"rs_vs_ihsg_{period}d"] = round(stock_ret / ihsg_ret, 3)
                else:
                    result[f"rs_vs_ihsg_{period}d"] = np.nan
            else:
                result[f"rs_vs_ihsg_{period}d"] = np.nan
        else:
            result[f"rs_vs_ihsg_{period}d"] = np.nan

    # RS rank among all tickers (using 20d return)
    ticker = df_ind.attrs.get("ticker", "")
    if all_returns_20d and ticker in all_returns_20d:
        my_ret = all_returns_20d[ticker]
        all_rets = sorted(all_returns_20d.values(), reverse=True)
        if len(all_rets) > 0:
            rank = all_rets.index(my_ret) + 1 if my_ret in all_rets else len(all_rets)
            result["rs_rank_pct"] = round(rank / len(all_rets) * 100, 1)
        else:
            result["rs_rank_pct"] = np.nan
    else:
        result["rs_rank_pct"] = np.nan

    return result


# ═══════════════════════════════════════════════════════════════
# MODULE 4: SIGNAL SIMULATION & TIMING
# ═══════════════════════════════════════════════════════════════


def simulate_signals(df_ind: pd.DataFrame, trough_idx: int, peak_idx: int,
                      total_gain_pct: float) -> dict:
    """Simulate current system's entry conditions during the rally."""
    result = {
        "signal_fired": False,
        "first_signal_date": None,
        "days_after_trough": None,
        "pct_move_missed": None,
        "blocking_conditions": "",
    }

    trough_price = df_ind.iloc[trough_idx]["close"]
    if trough_price <= 0:
        return result

    # Track which conditions block most often
    blockers = {}

    for i in range(trough_idx, min(peak_idx + 1, len(df_ind))):
        row = df_ind.iloc[i]
        c = row["close"]

        # Check each condition
        conditions = {}
        conditions["breakout_60d"] = pd.notna(row.get("high_60d")) and c > row.get("high_60d", float("inf"))
        conditions["vol_ratio_ok"] = 1.5 <= (row.get("vol_ratio", 0) or 0) <= 5.0
        conditions["above_ma50"] = pd.notna(row.get("ma50")) and c > row["ma50"]
        conditions["min_price_150"] = c >= 150
        conditions["no_selling_pressure"] = not row.get("has_selling_pressure", True)
        conditions["rsi_40_75"] = 40 <= (row.get("rsi", 0) or 0) <= 75
        conditions["macd_positive"] = (row.get("macd_hist", 0) or 0) > 0

        all_pass = all(conditions.values())

        if all_pass and not result["signal_fired"]:
            result["signal_fired"] = True
            result["first_signal_date"] = row["date"]
            result["days_after_trough"] = i - trough_idx
            current_gain = (c - trough_price) / trough_price * 100
            result["pct_move_missed"] = round(
                current_gain / max(total_gain_pct, 0.01) * 100, 1
            )
            break

        # Track blockers
        if not all_pass:
            for cond, passed in conditions.items():
                if not passed:
                    blockers[cond] = blockers.get(cond, 0) + 1

    if not result["signal_fired"]:
        # Sort blockers by frequency
        sorted_blockers = sorted(blockers.items(), key=lambda x: -x[1])
        result["blocking_conditions"] = "; ".join(
            f"{k}({v}d)" for k, v in sorted_blockers[:5]
        )

    return result


def test_breakout_periods(df_ind: pd.DataFrame, trough_idx: int,
                           peak_idx: int, total_gain_pct: float) -> dict:
    """Test multiple breakout periods to find optimal N."""
    result = {}
    trough_price = df_ind.iloc[trough_idx]["close"]
    if trough_price <= 0:
        return result

    for n in [10, 15, 20, 30, 40, 60]:
        col = f"high_{n}d"
        fired = False
        for i in range(trough_idx, min(peak_idx + 1, len(df_ind))):
            row = df_ind.iloc[i]
            if pd.notna(row.get(col)) and row["close"] > row[col]:
                days_after = i - trough_idx
                current_gain = (row["close"] - trough_price) / trough_price * 100
                pct_missed = round(current_gain / max(total_gain_pct, 0.01) * 100, 1)
                result[f"N{n}_days_after_trough"] = days_after
                result[f"N{n}_pct_missed"] = pct_missed
                fired = True
                break
        if not fired:
            result[f"N{n}_days_after_trough"] = np.nan
            result[f"N{n}_pct_missed"] = np.nan

    return result


def test_filter_impact(df_ind: pd.DataFrame, trough_idx: int,
                        peak_idx: int, total_gain_pct: float) -> dict:
    """Test what happens when we remove each filter individually."""
    result = {}
    trough_price = df_ind.iloc[trough_idx]["close"]
    if trough_price <= 0:
        return result

    filters_to_test = {
        "no_min_price": lambda r: True,  # remove min_price=150
        "no_rsi_filter": lambda r: True,  # remove RSI 40-75
        "no_macd_filter": lambda r: True,  # remove MACD > 0
        "no_vol_filter": lambda r: True,  # remove vol_ratio 1.5-5.0
        "no_selling_pressure": lambda r: True,  # remove selling pressure check
    }

    for filter_name, _ in filters_to_test.items():
        fired = False
        for i in range(trough_idx, min(peak_idx + 1, len(df_ind))):
            row = df_ind.iloc[i]
            c = row["close"]

            # Base conditions (always required)
            bo60 = pd.notna(row.get("high_60d")) and c > row.get("high_60d", float("inf"))
            above_ma50 = pd.notna(row.get("ma50")) and c > row["ma50"]

            # Conditions with one filter removed
            if filter_name == "no_min_price":
                ok = bo60 and 1.5 <= (row.get("vol_ratio", 0) or 0) <= 5.0 and above_ma50 and not row.get("has_selling_pressure", True) and 40 <= (row.get("rsi", 0) or 0) <= 75 and (row.get("macd_hist", 0) or 0) > 0
            elif filter_name == "no_rsi_filter":
                ok = bo60 and 1.5 <= (row.get("vol_ratio", 0) or 0) <= 5.0 and above_ma50 and c >= 150 and not row.get("has_selling_pressure", True) and (row.get("macd_hist", 0) or 0) > 0
            elif filter_name == "no_macd_filter":
                ok = bo60 and 1.5 <= (row.get("vol_ratio", 0) or 0) <= 5.0 and above_ma50 and c >= 150 and not row.get("has_selling_pressure", True) and 40 <= (row.get("rsi", 0) or 0) <= 75
            elif filter_name == "no_vol_filter":
                ok = bo60 and above_ma50 and c >= 150 and not row.get("has_selling_pressure", True) and 40 <= (row.get("rsi", 0) or 0) <= 75 and (row.get("macd_hist", 0) or 0) > 0
            elif filter_name == "no_selling_pressure":
                ok = bo60 and 1.5 <= (row.get("vol_ratio", 0) or 0) <= 5.0 and above_ma50 and c >= 150 and 40 <= (row.get("rsi", 0) or 0) <= 75 and (row.get("macd_hist", 0) or 0) > 0
            else:
                ok = False

            if ok:
                days_after = i - trough_idx
                current_gain = (c - trough_price) / trough_price * 100
                pct_missed = round(current_gain / max(total_gain_pct, 0.01) * 100, 1)
                result[f"{filter_name}_days"] = days_after
                result[f"{filter_name}_pct_missed"] = pct_missed
                fired = True
                break

        if not fired:
            result[f"{filter_name}_days"] = np.nan
            result[f"{filter_name}_pct_missed"] = np.nan

    return result


# ═══════════════════════════════════════════════════════════════
# MODULE 5: MOVE CHARACTERISTICS
# ═══════════════════════════════════════════════════════════════


def analyze_move_characteristics(df_ind: pd.DataFrame,
                                   trough_idx: int, peak_idx: int) -> dict:
    """Analyze how the mega-winner move unfolds."""
    result = {}
    rally = df_ind.iloc[trough_idx:peak_idx + 1]
    if len(rally) < 2:
        return result

    trough_price = rally.iloc[0]["close"]
    peak_price = rally.iloc[-1]["high"]
    total_gain = peak_price - trough_price
    if total_gain <= 0 or trough_price <= 0:
        return result

    # Move speed: days to reach 50% of total gain
    half_target = trough_price + total_gain * 0.5
    days_to_50pct = np.nan
    for i, (_, row) in enumerate(rally.iterrows()):
        if row["high"] >= half_target:
            days_to_50pct = i
            break
    result["days_to_50pct_gain"] = days_to_50pct
    total_days = len(rally)
    if pd.notna(days_to_50pct):
        if days_to_50pct < 15:
            result["move_speed"] = "fast"
        elif days_to_50pct < 45:
            result["move_speed"] = "medium"
        else:
            result["move_speed"] = "slow"
    else:
        result["move_speed"] = "unknown"

    # First week gain
    first_5 = rally.head(6)  # trough day + 5 days
    if len(first_5) >= 2:
        result["first_week_gain_pct"] = round(
            (first_5.iloc[-1]["close"] - trough_price) / trough_price * 100, 2
        )
    else:
        result["first_week_gain_pct"] = np.nan

    # Max pullback within rally
    running_high = rally["high"].cummax()
    drawdowns = (rally["low"] - running_high) / running_high
    result["max_pullback_pct"] = round(drawdowns.min() * 100, 2)

    # Pullback frequency (>5%)
    result["pullbacks_gt_5pct"] = int((drawdowns < -0.05).sum())

    # Trend persistence: % of days with positive return
    pos_days = (rally["return"] > 0).sum()
    result["positive_day_pct"] = round(pos_days / max(len(rally) - 1, 1) * 100, 1)

    # Days above MA10 during rally
    above_ma10 = (rally["close"] > rally["ma10"]).sum()
    result["days_above_ma10_pct"] = round(above_ma10 / max(len(rally), 1) * 100, 1)

    # Volume profile: where is volume concentrated?
    if len(rally) >= 6:
        thirds = np.array_split(rally["volume"].values, 3)
        vol_thirds = [t.mean() for t in thirds]
        total_vol = sum(vol_thirds)
        if total_vol > 0:
            result["vol_pct_first_third"] = round(vol_thirds[0] / total_vol * 100, 1)
            result["vol_pct_last_third"] = round(vol_thirds[2] / total_vol * 100, 1)
        else:
            result["vol_pct_first_third"] = np.nan
            result["vol_pct_last_third"] = np.nan
    else:
        result["vol_pct_first_third"] = np.nan
        result["vol_pct_last_third"] = np.nan

    # Gap behavior
    gaps = (rally["open"] - rally["close"].shift(1)) / rally["close"].shift(1)
    result["avg_gap_pct"] = round(gaps.dropna().mean() * 100, 3)
    result["gap_up_days"] = int((gaps > 0.02).sum())

    return result


# ═══════════════════════════════════════════════════════════════
# HELPER
# ═══════════════════════════════════════════════════════════════


def _safe_get(df, idx, col):
    try:
        v = df.iloc[idx][col]
        return round(float(v), 4) if pd.notna(v) else np.nan
    except Exception:
        return np.nan


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════


def main():
    logger.info(f"Step 2: Mega-Winner Pattern Analysis — {len(LQ45_TICKERS)} tickers")

    # ── 1. Download all OHLCV data ──
    logger.info("Downloading OHLCV from yfinance (2023-2025)...")
    all_data = {}
    for i, ticker in enumerate(LQ45_TICKERS, 1):
        df = download_ticker_data(ticker, "2023-01-01", "2025-12-31")
        if not df.empty:
            df = df.dropna(subset=["close", "low", "high"]).sort_values("date").reset_index(drop=True)
            all_data[ticker] = df
        if i % 20 == 0:
            logger.info(f"  Downloaded {i}/{len(LQ45_TICKERS)} tickers")
        if i < len(LQ45_TICKERS):
            time.sleep(1)
    logger.info(f"  Done: {len(all_data)} tickers with data")

    # ── 2. Download IHSG ──
    logger.info("Downloading IHSG index...")
    ihsg_raw = download_ticker_data("^JKSE".replace(".JK", ""), "2023-01-01", "2025-12-31")
    # yfinance uses ^JKSE directly, not with .JK suffix
    if ihsg_raw.empty:
        for attempt in range(3):
            try:
                t = yf.Ticker("^JKSE")
                ihsg_raw = t.history(start="2023-01-01", end="2025-12-31", auto_adjust=False)
                if ihsg_raw is not None and not ihsg_raw.empty:
                    ihsg_raw = ihsg_raw.reset_index()
                    ihsg_raw.columns = [c.lower().replace(" ", "_") for c in ihsg_raw.columns]
                    if "date" in ihsg_raw.columns:
                        ihsg_raw["date"] = pd.to_datetime(ihsg_raw["date"]).dt.tz_localize(None)
                    elif "datetime" in ihsg_raw.columns:
                        ihsg_raw = ihsg_raw.rename(columns={"datetime": "date"})
                        ihsg_raw["date"] = pd.to_datetime(ihsg_raw["date"]).dt.tz_localize(None)
                    break
            except Exception:
                time.sleep(2)

    if not ihsg_raw.empty:
        ihsg_df = ihsg_raw.set_index("date").sort_index()
        logger.info(f"  IHSG: {len(ihsg_df)} days, {ihsg_df.index.min().date()} to {ihsg_df.index.max().date()}")
    else:
        ihsg_df = pd.DataFrame()
        logger.warning("  IHSG data not available")

    # ── 3. Load broker data ──
    db_path = "idx_swing_trader.db"
    broker_df = load_broker_data(db_path)

    # ── 4. Compute indicators for all tickers ──
    logger.info("Computing technical indicators...")
    all_indicators = {}
    for ticker, df in all_data.items():
        ind = compute_indicators(df)
        ind.attrs["ticker"] = ticker
        all_indicators[ticker] = ind
    logger.info(f"  Indicators computed for {len(all_indicators)} tickers")

    # ── 5. Identify mega-winners for both years ──
    mega_winners = []
    for year in [2024, 2025]:
        mw = identify_mega_winners(all_data, year)
        mega_winners.extend(mw)
        logger.info(f"  {year}: {len(mw)} liquid mega-winners identified")

    if not mega_winners:
        logger.error("No mega-winners found!")
        return

    # ── 6. Run all analysis modules ──
    logger.info(f"Analyzing {len(mega_winners)} mega-winners across all modules...")

    volume_rows = []
    price_action_rows = []
    rs_rows = []
    signal_rows = []
    breakout_rows = []
    filter_impact_rows = []
    move_rows = []

    for idx, mw in enumerate(mega_winners):
        ticker = mw["ticker"]
        year = mw["year"]
        trough_date = mw["trough_date"]
        peak_date = mw["peak_date"]

        if ticker not in all_indicators:
            continue

        df_ind = all_indicators[ticker]

        # Find trough and peak indices in the indicator DataFrame
        year_mask = df_ind["date"].dt.year == year
        year_df = df_ind[year_mask]
        if year_df.empty:
            continue

        # Find closest index to trough_date and peak_date
        trough_diffs = (df_ind["date"] - trough_date).abs()
        trough_idx = trough_diffs.idxmin()
        peak_diffs = (df_ind["date"] - peak_date).abs()
        peak_idx = peak_diffs.idxmin()

        if trough_idx >= peak_idx:
            continue

        base = {"ticker": ticker, "sector": mw["sector"], "year": year,
                "max_drawup_pct": mw["max_drawup_pct"],
                "trough_date": trough_date, "peak_date": peak_date,
                "avg_daily_value_bn": mw["avg_daily_value_bn"]}

        # Module 1: Volume accumulation
        asing_flow = get_asing_flow(broker_df, ticker)
        all_flow = get_all_broker_flow(broker_df, ticker)
        vol_result = analyze_volume_accumulation(df_ind, trough_date, trough_idx,
                                                  asing_flow, all_flow)
        volume_rows.append({**base, **vol_result})

        # Module 2: Price action
        pa_result = analyze_price_action(df_ind, trough_idx)
        price_action_rows.append({**base, **pa_result})

        # Module 3: Relative strength
        # Compute 20d return for all tickers at this date for ranking
        all_ret_20d = {}
        for t, ind_df in all_indicators.items():
            t_mask = ind_df["date"] <= trough_date
            t_df = ind_df[t_mask]
            if len(t_df) >= 20:
                ret = (t_df.iloc[-1]["close"] / t_df.iloc[-20]["close"]) - 1
                all_ret_20d[t] = ret
        rs_result = analyze_relative_strength(df_ind, ihsg_df, trough_idx,
                                               trough_date, all_ret_20d)
        rs_rows.append({**base, **rs_result})

        # Module 4: Signal simulation
        sig_result = simulate_signals(df_ind, trough_idx, peak_idx,
                                       mw["max_drawup_pct"])
        signal_rows.append({**base, **sig_result})

        # Breakout period test
        bo_result = test_breakout_periods(df_ind, trough_idx, peak_idx,
                                           mw["max_drawup_pct"])
        breakout_rows.append({**base, **bo_result})

        # Filter impact
        fi_result = test_filter_impact(df_ind, trough_idx, peak_idx,
                                        mw["max_drawup_pct"])
        filter_impact_rows.append({**base, **fi_result})

        # Module 5: Move characteristics
        mc_result = analyze_move_characteristics(df_ind, trough_idx, peak_idx)
        move_rows.append({**base, **mc_result})

        if (idx + 1) % 20 == 0:
            logger.info(f"  Analyzed {idx + 1}/{len(mega_winners)} mega-winners")

    logger.info(f"  Analysis complete for {len(volume_rows)} mega-winners")

    # ── 7. Module 6: Mega vs Non-Mega comparison ──
    logger.info("Computing non-mega-winner baseline for comparison...")
    non_mega_pa = []
    non_mega_vol = []
    for year in [2024, 2025]:
        mega_tickers = {m["ticker"] for m in mega_winners if m["year"] == year}
        for ticker, df in all_data.items():
            if ticker in mega_tickers:
                continue
            if ticker not in all_indicators:
                continue

            ydf = df[df["date"].dt.year == year]
            if len(ydf) < 20:
                continue

            # Use annual low as reference point
            low_idx_in_year = ydf["low"].idxmin()
            low_idx = df.index.get_loc(low_idx_in_year) if low_idx_in_year in df.index else None
            if low_idx is None:
                continue

            df_ind = all_indicators[ticker]
            if low_idx >= len(df_ind):
                continue

            pa = analyze_price_action(df_ind, low_idx)
            pa["ticker"] = ticker
            pa["year"] = year
            pa["is_mega"] = False
            non_mega_pa.append(pa)

            asing_flow = get_asing_flow(broker_df, ticker)
            all_flow = get_all_broker_flow(broker_df, ticker)
            trough_date_nm = df_ind.iloc[low_idx]["date"]
            vol = analyze_volume_accumulation(df_ind, trough_date_nm, low_idx,
                                              asing_flow, all_flow)
            vol["ticker"] = ticker
            vol["year"] = year
            vol["is_mega"] = False
            non_mega_vol.append(vol)

    logger.info(f"  Non-mega baseline: {len(non_mega_pa)} stocks")

    # Build comparison stats
    comparison_rows = []
    if non_mega_pa and price_action_rows:
        mega_pa_df = pd.DataFrame(price_action_rows)
        non_mega_pa_df = pd.DataFrame(non_mega_pa)

        # Combine key volume metrics too
        mega_vol_df = pd.DataFrame(volume_rows)
        non_mega_vol_df = pd.DataFrame(non_mega_vol)

        # Numeric columns to compare
        compare_cols = [
            "rsi_at_trough", "price_vs_ma20_pct", "price_vs_ma50_pct",
            "bb_width_at_trough", "bb_width_percentile", "atr_pct_at_trough",
            "atr_compression_ratio", "consolidation_range_20d_pct",
            "higher_lows_20d", "prior_60d_return_pct",
            "dist_52w_low_pct", "dist_52w_high_pct",
        ]
        vol_compare_cols = [
            "obv_slope_20d", "ad_slope_20d", "cmf_at_trough",
            "vol_trend_20d", "up_down_vol_ratio_20d",
            "vol_surge_days_20d", "vol_price_corr_20d",
            "asing_net_cum_20d", "asing_positive_pct_20d",
        ]

        for col in compare_cols:
            if col in mega_pa_df.columns and col in non_mega_pa_df.columns:
                mega_vals = mega_pa_df[col].dropna()
                non_mega_vals = non_mega_pa_df[col].dropna()
                if len(mega_vals) >= 5 and len(non_mega_vals) >= 5:
                    mega_med = mega_vals.median()
                    non_mega_med = non_mega_vals.median()
                    pooled_std = np.sqrt(
                        (mega_vals.std()**2 + non_mega_vals.std()**2) / 2
                    )
                    effect_size = (mega_med - non_mega_med) / pooled_std if pooled_std > 0 else 0
                    comparison_rows.append({
                        "metric": col,
                        "mega_median": round(mega_med, 4),
                        "mega_p25": round(mega_vals.quantile(0.25), 4),
                        "mega_p75": round(mega_vals.quantile(0.75), 4),
                        "non_mega_median": round(non_mega_med, 4),
                        "non_mega_p25": round(non_mega_vals.quantile(0.25), 4),
                        "non_mega_p75": round(non_mega_vals.quantile(0.75), 4),
                        "effect_size": round(effect_size, 4),
                        "mega_count": len(mega_vals),
                        "non_mega_count": len(non_mega_vals),
                    })

        for col in vol_compare_cols:
            if col in mega_vol_df.columns and col in non_mega_vol_df.columns:
                mega_vals = mega_vol_df[col].dropna()
                non_mega_vals = non_mega_vol_df[col].dropna()
                if len(mega_vals) >= 5 and len(non_mega_vals) >= 5:
                    mega_med = mega_vals.median()
                    non_mega_med = non_mega_vals.median()
                    pooled_std = np.sqrt(
                        (mega_vals.std()**2 + non_mega_vals.std()**2) / 2
                    )
                    effect_size = (mega_med - non_mega_med) / pooled_std if pooled_std > 0 else 0
                    comparison_rows.append({
                        "metric": col,
                        "mega_median": round(mega_med, 4),
                        "mega_p25": round(mega_vals.quantile(0.25), 4),
                        "mega_p75": round(mega_vals.quantile(0.75), 4),
                        "non_mega_median": round(non_mega_med, 4),
                        "non_mega_p25": round(non_mega_vals.quantile(0.25), 4),
                        "non_mega_p75": round(non_mega_vals.quantile(0.75), 4),
                        "effect_size": round(effect_size, 4),
                        "mega_count": len(mega_vals),
                        "non_mega_count": len(non_mega_vals),
                    })

    # Sort comparison by absolute effect size
    comparison_rows.sort(key=lambda x: abs(x.get("effect_size", 0)), reverse=True)

    # ── 8. Write Excel ──
    logger.info("Writing Excel output...")
    out_file = "mega_winners_pattern_analysis.xlsx"

    with pd.ExcelWriter(out_file, engine="openpyxl") as w:
        # Format dates for all DataFrames
        def fmt_dates(rows):
            df = pd.DataFrame(rows)
            for col in df.columns:
                if "date" in col.lower() and df[col].dtype == "datetime64[ns]":
                    df[col] = df[col].dt.strftime("%Y-%m-%d")
            return df

        if volume_rows:
            fmt_dates(volume_rows).to_excel(w, sheet_name="Volume Accumulation", index=False)
        if price_action_rows:
            fmt_dates(price_action_rows).to_excel(w, sheet_name="Price Action", index=False)
        if rs_rows:
            fmt_dates(rs_rows).to_excel(w, sheet_name="Relative Strength", index=False)
        if signal_rows:
            fmt_dates(signal_rows).to_excel(w, sheet_name="Signal Simulation", index=False)
        if breakout_rows:
            fmt_dates(breakout_rows).to_excel(w, sheet_name="Breakout Period Test", index=False)
        if filter_impact_rows:
            fmt_dates(filter_impact_rows).to_excel(w, sheet_name="Filter Impact", index=False)
        if move_rows:
            fmt_dates(move_rows).to_excel(w, sheet_name="Move Characteristics", index=False)
        if comparison_rows:
            pd.DataFrame(comparison_rows).to_excel(w, sheet_name="Mega vs Non-Mega", index=False)

        # Pattern summary (top discriminating features)
        if comparison_rows:
            pd.DataFrame(comparison_rows[:15]).to_excel(
                w, sheet_name="Pattern Summary", index=False
            )

    logger.info(f"Excel written: {out_file}")
    logger.info("=" * 60)

    # ── 9. Print key findings ──
    if signal_rows:
        sig_df = pd.DataFrame(signal_rows)
        fired = sig_df["signal_fired"].sum()
        total = len(sig_df)
        logger.info(f"SIGNAL SIMULATION: {fired}/{total} mega-winners caught by current system "
                     f"({round(fired/total*100, 1)}%)")
        if fired < total:
            not_fired = sig_df[~sig_df["signal_fired"]]
            logger.info(f"  {total - fired} mega-winners MISSED. Top blocking conditions:")
            all_blockers = {}
            for _, row in not_fired.iterrows():
                for b in row.get("blocking_conditions", "").split("; "):
                    if b:
                        cond = b.split("(")[0]
                        all_blockers[cond] = all_blockers.get(cond, 0) + 1
            for cond, cnt in sorted(all_blockers.items(), key=lambda x: -x[1])[:5]:
                logger.info(f"    {cond}: blocked {cnt} mega-winners")

    if breakout_rows:
        bo_df = pd.DataFrame(breakout_rows)
        logger.info("\nBREAKOUT PERIOD COMPARISON (median days after trough / median % missed):")
        for n in [10, 15, 20, 30, 40, 60]:
            days_col = f"N{n}_days_after_trough"
            pct_col = f"N{n}_pct_missed"
            if days_col in bo_df.columns:
                med_days = bo_df[days_col].dropna().median()
                med_pct = bo_df[pct_col].dropna().median()
                caught = bo_df[days_col].notna().sum()
                logger.info(f"  N={n:2d}: median {med_days:5.0f} days, "
                             f"median {med_pct:5.1f}% missed, "
                             f"caught {caught}/{len(bo_df)}")

    if comparison_rows:
        logger.info("\nTOP DISCRIMINATING FEATURES (by effect size):")
        for row in comparison_rows[:10]:
            logger.info(f"  {row['metric']:35s}  mega={row['mega_median']:8.3f}  "
                         f"non-mega={row['non_mega_median']:8.3f}  "
                         f"effect={row['effect_size']:+.3f}")


if __name__ == "__main__":
    main()
