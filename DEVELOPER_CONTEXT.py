"""
DEVELOPER_CONTEXT.py — Session Continuity Document
=====================================================
Last updated: March 21, 2026

This file provides full context for any AI assistant or developer
continuing work on this project. Read this first before making changes.

Repository: nstnarle/SahamGPT (private GitHub)
Owner: Arie Nasution
"""

# ══════════════════════════════════════════════════════════════
# PROJECT STATUS
# ══════════════════════════════════════════════════════════════

STATUS = "ACTIVE — Broker summary integration in progress"

CURRENT_VERSION = "v6"

LATEST_BACKTEST_RESULTS = {
    "2024": {"trades": 45, "win_rate": "33%", "pnl": "Rp -37M", "pf": 0.68},
    "2025": {"trades": 55, "win_rate": "31%", "pnl": "Rp +60M", "pf": 1.38},
    "combined": {"trades": 100, "win_rate": "32%", "pnl": "Rp +23M", "pf": 1.08},
    "note": "2025 is FIRST PROFITABLE YEAR. Trend exit generated Rp +240M from 12 trades.",
}

# ══════════════════════════════════════════════════════════════
# WHAT'S IN PROGRESS RIGHT NOW
# ══════════════════════════════════════════════════════════════

IN_PROGRESS = """
1. STOCKBIT BROKER SUMMARY SCRAPER
   - Files: scraper/broker_scraper.py, scraper/stockbit_auth.py
   - API: exodus.stockbit.com/marketdetectors/{TICKER}?from=...&to=...
   - Auth: Playwright headless browser (reCAPTCHA v3 bypass via stealth)
   - Status: Code built, needs first successful test run
   - Next: Run workflow, verify data, then backfill 2024-2025

2. BROKER DATA → SIGNAL INTEGRATION
   - Once broker data is scraped, integrate into signal_combiner.py
   - Replace synthetic foreign flow with real broker-level data
   - Use Stockbit's "type" field: Asing = foreign, Pemerintah = govt
   - Expected: significant accuracy improvement for foreign-driven stocks
"""

# ══════════════════════════════════════════════════════════════
# VERSION HISTORY (FULL)
# ══════════════════════════════════════════════════════════════

VERSION_HISTORY = {
    "v1": {
        "signal": "Synthetic big money (foreign flow estimate + OBV/AD + VWAP proxy)",
        "entry_threshold": 0.55,
        "stop": "-7% or 2xATR (wider wins) — NO hard cap",
        "result": "303 trades, 34% WR, Rp -608M",
        "problem": "Stop-losses -10% to -23%. Repeat offenders. Signal clustering.",
    },
    "v2": {
        "signal": "Same synthetic, threshold 0.70",
        "stop": "-5% hard cap (too tight)",
        "result": "400 trades, 20% WR, Rp -864M (WORSE)",
        "problem": "-5% too tight for IDX 3-5% daily swings.",
    },
    "v3": {
        "signal": "Same synthetic, threshold 0.75, 2-day confirmation",
        "stop": "-7% with -8% cap",
        "result": "40 trades, 20% WR, Rp -109M",
        "problem": "Signal itself has ~20% accuracy. Can't be fixed by filtering.",
    },
    "v4": {
        "signal": "REBUILT — 20-day breakout + real foreign flow + auto foreign/domestic detection",
        "stop": "-7% with -8% cap, 30-day cooldown, max 3 entries/day",
        "result": "344 trades, 26% WR, Rp -680M",
        "key_finding": "Days 1-5: 7% WR (-754M). Days 11+: 72% WR (+181M). BREAKOUT WORKS but stops kill trades early.",
    },
    "v5": {
        "signal": "60-day breakout (historical resistance) + FF confirmation",
        "new_features": [
            "5-day min hold (stop disabled first 5 days)",
            "Trend exit: +15% gain → only exit when close < MA10",
            "Min price Rp 150",
            "Emergency stop -15%",
            "Risk reduced to 1.5%",
        ],
        "result": "Improved but not final — v6 adds candle/FF fixes",
    },
    "v6": {
        "signal": "v5 + FF trend check + selling pressure candle filter",
        "new_features": [
            "FF TREND: 5-day rolling sum must be positive + breakout day not net sell (ADRO fix)",
            "CANDLE FILTER: upper shadow >40% or close in bottom 1/3 → rejected (MYOR fix)",
        ],
        "result": "2025: +60M PROFITABLE. 2024: -37M near breakeven.",
        "star": "TREND_EXIT: 12 trades, 11 wins, avg +26.5%, Rp +240M total",
    },
}

# ══════════════════════════════════════════════════════════════
# HARD RULES — NEVER CHANGE
# ══════════════════════════════════════════════════════════════

HARD_RULES = """
These are confirmed working and must NOT be modified:

1. 5-day minimum hold before stop fires — PROVEN by v4 data
2. Trend exit (MA10) for stocks that gain +15% — keeps runners (EMTK +77%, DSNG +75%)
3. Min stock price Rp 150 — filters junk
4. Max 3 entries per day — prevents signal clustering
5. 30-day cooldown after stop-loss — prevents repeat offender losses
6. Selling pressure candle filter — catches MYOR-type fake breakouts
7. Foreign flow TREND (not just count) — catches ADRO-type false signals
"""

# ══════════════════════════════════════════════════════════════
# KEY LEARNINGS
# ══════════════════════════════════════════════════════════════

KEY_LEARNINGS = """
1. SIGNAL QUALITY > EXIT MANAGEMENT
   We spent v1-v3 tuning exits (stops, thresholds, holds). None worked because
   the synthetic signal was 20% accurate. v4 rebuilt the signal → immediately better.

2. IDX STOCKS NEED ROOM TO BREATHE
   -5% stop kills everything. -7% with 5-day hold works. IDX has 3-5% daily swings.

3. LET WINNERS RUN
   Selling 50% at +15% (v1) or trailing stops cut the best trades short.
   Trend exit (MA10 break) after +15% gain captures EMTK +77%, DSNG +75%.

4. THE "FEW MEGA-WINNERS" PATTERN
   31% win rate is fine when winners are 3.75x bigger than losers.
   5 trades generated most of the profit. Protect position slots for these.

5. REAL DATA >>> SYNTHETIC ESTIMATES
   Synthetic foreign flow estimation was essentially random noise.
   Real broker data from Stockbit (Asing/Lokal/Pemerintah) is the key.

6. CANDLE STRUCTURE MATTERS
   MYOR breakout on Apr 25 2025 — closed up but long upper shadow.
   Selling pressure filter would have caught it.

7. FOREIGN FLOW TREND, NOT JUST COUNT
   ADRO May 19 2025 — 3 of 5 prior days positive FF, but breakout day
   was net foreign sell. The trend was turning. New logic catches this.
"""

# ══════════════════════════════════════════════════════════════
# REMAINING WEAK SPOTS TO FIX
# ══════════════════════════════════════════════════════════════

WEAK_SPOTS = """
1. 6-10 DAY STOP-LOSSES (biggest remaining drag)
   54 trades in this range: 8% win rate, -215M loss.
   These survived the 5-day hold but got stopped in next week.
   Fix: With real broker data, check if institutions still accumulating.
   If yes, extend hold or widen stop.

2. 2024 STILL SLIGHTLY NEGATIVE (-37M)
   Fewer big trend winners in 2024 (3 vs 9 in 2025).
   Could be market conditions, or broker data might improve entry timing.

3. BROKER DATA NOT YET INTEGRATED INTO BACKTEST
   Current backtests use Yahoo Finance foreign flow estimates.
   Once Stockbit broker data is backfilled, signal quality should improve.
"""

# ══════════════════════════════════════════════════════════════
# NEXT STEPS (IN ORDER)
# ══════════════════════════════════════════════════════════════

NEXT_STEPS = """
1. ✅ Test Stockbit Playwright auto-login (verify reCAPTCHA bypass works)
2. ✅ Small historical scrape test (1 week, 25 tickers)
3. ⬜ Verify scraped data quality (run verify_broker_data.py)
4. ⬜ Backfill full 2024-2025 broker data (batch workflow)
5. ⬜ Integrate real broker data into signal_combiner.py
6. ⬜ Re-run backtests with real broker data
7. ⬜ Fix 6-10 day weak spot using broker accumulation data
8. ⬜ Update daily_signals.yml to include broker scraping
9. ⬜ Paper trade for 1 month
10. ⬜ Go live
"""

# ══════════════════════════════════════════════════════════════
# STOCKBIT API REFERENCE
# ══════════════════════════════════════════════════════════════

STOCKBIT_API = """
Endpoint: GET https://exodus.stockbit.com/marketdetectors/{TICKER}
Params:
  from=YYYY-MM-DD
  to=YYYY-MM-DD
  transaction_type=TRANSACTION_TYPE_NET
  market_board=MARKET_BOARD_REGULER
  investor_type=INVESTOR_TYPE_ALL
  limit=25 (or 50 for all brokers)

Auth: Bearer JWT token (from Playwright login)
Login: POST https://exodus.stockbit.com/login/v6/username
  Requires reCAPTCHA v3 token → must use browser automation

Response structure:
  data.broker_summary.brokers_buy[] — net buyers
    .netbs_broker_code — broker code (e.g. "BK", "AK")
    .type — "Asing" / "Lokal" / "Pemerintah"
    .blot — net lots (positive)
    .bval — net value (positive)
    .bvalv — total value (buy+sell combined)
    .freq — number of transactions

  data.broker_summary.brokers_sell[] — net sellers
    .slot — net lots (negative)
    .sval — net value (negative)
    .svalv — total value

  data.bandar_detector — accumulation/distribution summary
    .broker_accdist — "Acc" / "Dist" / "Neutral"
    .top3/top5/top10 — aggregated signals

Rate limit: ~40 requests per 5 minutes
"""
