"""
DEVELOPER_CONTEXT.py — Session Continuity Document
=====================================================
Last updated: March 28, 2026

This file provides full context for any AI assistant or developer
continuing work on this project. Read this first before making changes.

Repository: nstnarie/SahamGPT-Bot (public GitHub)
Owner: Arie
"""

# ══════════════════════════════════════════════════════════════
# AI ASSISTANT OPERATING GUIDELINES
# ══════════════════════════════════════════════════════════════
# MANDATORY: Any AI assistant working on this project MUST follow
# these rules without exception. Violations have caused near data
# loss in the past. These rules exist to protect the project.
# ══════════════════════════════════════════════════════════════

AI_OPERATING_GUIDELINES = """
╔══════════════════════════════════════════════════════════════╗
║         AI ASSISTANT — MANDATORY OPERATING RULES            ║
║  READ AND FOLLOW BEFORE TAKING ANY ACTION ON THIS PROJECT   ║
╚══════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 0: READ BEFORE YOU ANSWER (MOST IMPORTANT RULE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Never answer questions about workflow behaviour, data safety,
file interactions, or code logic without first reading the
actual files. No assumptions, no guessing from memory.

The correct sequence for EVERY question is:
  1. Identify which file(s) are relevant to the question
  2. Fetch and read those files
  3. Answer based on what the code ACTUALLY does

If a file has not been read in this session → fetch it first.
Answering first and verifying after is NEVER acceptable.
Violation of this rule previously caused near data loss.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 1: WORKFLOW PARALLELISM — DEFAULT IS SEQUENTIAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Before saying any two workflows are safe to run in parallel,
verify ALL of the following by reading both workflow files:

  □ Do they restore the same artifact?     → SEQUENTIAL ONLY
  □ Do they write to the same DB tables?   → SEQUENTIAL ONLY
  □ Do they upload to the same artifact?   → SEQUENTIAL ONLY
  □ Do they read from the same DB file?    → SEQUENTIAL ONLY

If ANY answer is YES → workflows must run SEQUENTIALLY.
Default assumption is SEQUENTIAL unless code proves otherwise.

KNOWN SHARED ARTIFACT: `idx-database`
Written by: scrape_broker_summary.yml, initial_scrape.yml,
            bootstrap_database.yml, daily_signals.yml
→ NONE of these may run in parallel with each other.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 2: DATA SAFETY IS NON-NEGOTIABLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Never describe an operation as "safe" or "won't affect data"
without reading the code that handles that data.

Data loss in this project is UNRECOVERABLE because:
  - Historical broker data takes weeks to re-scrape
  - Stockbit token expires every 24 hours
  - GitHub Actions free tier has limited runtime

Before any operation that touches the database or artifacts:
  □ Read the relevant workflow/script
  □ Identify all read and write operations
  □ Confirm no conflicts with other running workflows
  □ Confirm artifact upload is gated on data count check

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 3: NO SPECULATION — ONLY VERIFIED FACTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Arie is data-driven and catches speculation immediately.
Never present assumptions as facts.

  BAD:  "The scraper probably uses upsert so duplicates won't occur"
  GOOD: "Let me check scraper/broker_scraper.py to confirm"

If uncertain → say so explicitly and fetch the relevant file.
If data is not yet available → say so and wait for Arie to
provide it rather than estimating.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 4: BACKTEST CHANGES MUST NEVER BLEED INTO LIVE CODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The project has two completely separate execution paths:

  BACKTEST:  main_backtest.py → backtest/engine.py
  LIVE:      main_daily.py → signals/signal_combiner.py

Changes to backtest logic must NEVER touch live signal files.
Changes to live signals must NEVER affect backtest results.
Always confirm which path a change applies to before editing.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 5: LOCKED PARAMETERS — NEVER CHANGE WITHOUT DATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The following are confirmed working and must NOT be modified
without explicit data justification from a new backtest run:

  - 5-day minimum hold before stop fires
  - Trend exit (MA10) for stocks gaining +15%
  - -15% emergency stop (always active)
  - 60-day breakout period (historical resistance)
  - Volume spike 1.5x–5.0x range
  - RSI 40–75 range
  - Min price Rp 150
  - Max 3 entries per day
  - 30-day cooldown after stop-loss
  - Selling pressure candle filter (upper shadow >40%)
  - Foreign flow trend check (5-day rolling + breakout day)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 6: GITHUB ACTIONS — KNOWN PATTERNS AND PITFALLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Always follow these patterns when writing or modifying workflows:

  ✅ Multi-line Python → always use heredoc:
       python3 << 'EOF'
       ...code...
       EOF
  ❌ Never use: python3 -c "..." for multi-line code (SyntaxError)

  ✅ Artifact uploads → always gate on data count:
       if: steps.check_data.outputs.has_data == 'true'
  ❌ Never upload artifact unconditionally (risks empty DB overwrite)

  ✅ Artifact restore → always set GH_TOKEN:
       env:
         GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  ❌ Never restore artifact without GH_TOKEN (silently fails)

  ✅ Batch scraping → always run sequentially, one at a time
  ❌ Never run two batches in parallel (artifact collision)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 7: HYPOTHESIS-DRIVEN DEVELOPMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Every code change must follow this process:

  1. State the hypothesis explicitly
     ("I expect X to improve because Y")
  2. Make ONE change at a time
  3. Run backtest and collect results
  4. Analyse results against specific numbers
  5. Accept or reject the hypothesis based on data
  6. Document the finding in DEVELOPER_CONTEXT.py

Never make multiple changes simultaneously — isolates causality.
Never proceed to next experiment without documenting the last.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 8: CITE SPECIFIC NUMBERS — NEVER GENERALISE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Arie makes decisions based on specific numbers, not narratives.

  BAD:  "The results improved significantly"
  GOOD: "PF improved from 1.38 to 1.71, trades dropped from 55 to 41"

Always cite:
  - Exact trade counts
  - Exact win rates
  - Exact PnL figures (in Rp)
  - Exact profit factors
  - Which specific trades changed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 9: DOCUMENTATION DISCIPLINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
After every significant finding or change:
  □ Update DEVELOPER_CONTEXT.py with results and learnings
  □ Update HANDOFF_SESSION document with current state
  □ Update NEXT_STEPS to reflect what was completed
  □ Remove debug code that is no longer needed
  □ Note any confirmed false alarms (e.g. Apr 1-7 = public holiday)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 10: WHEN IN DOUBT — STOP AND ASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If any instruction is ambiguous or any action feels risky:
  → STOP
  → State what you are unsure about
  → Ask Arie for clarification before proceeding

It is always better to ask one extra question than to cause
data loss or an incorrect code change that takes hours to fix.
"""

# ══════════════════════════════════════════════════════════════
# PROJECT STATUS
# ══════════════════════════════════════════════════════════════

STATUS = "ACTIVE — Broker summary data backfill in progress (batch scraping)"

CURRENT_VERSION = "v6"

LATEST_BACKTEST_RESULTS = {
    "2024": {"trades": 45, "win_rate": "33%", "pnl": "Rp -37M", "pf": 0.68},
    "2025": {"trades": 55, "win_rate": "31%", "pnl": "Rp +60M", "pf": 1.38},
    "combined": {"trades": 100, "win_rate": "32%", "pnl": "Rp +23M", "pf": 1.08},
    "note": "2025 is FIRST PROFITABLE YEAR. Trend exit generated Rp +240M from 12 trades.",
}

# ══════════════════════════════════════════════════════════════
# WHAT'S IN PROGRESS RIGHT NOW (as of 2026-03-28)
# ══════════════════════════════════════════════════════════════

IN_PROGRESS = """
1. BROKER SUMMARY DATA BACKFILL
   - Historical scrape workflows run in 4 batches (25 tickers each)
   - Q1 2025 (Jan-Mar): VERIFIED COMPLETE ✅
     * 237,302 records, 58 trading days, 105-107 tickers/day, 94 broker codes
     * All 3 broker types populated (Asing/Lokal/Pemerintah)
     * 6 apparent "missing" days confirmed as IDX public holidays
   - Apr 1-7 2025: CONFIRMED PUBLIC HOLIDAY ✅ (Lebaran 2025 — no trading, no data expected)
   - Apr 8 - May 15 2025: PARTIALLY COMPLETE ⚠️
     * Previously showing only 71 tickers/day (should be ~105)
     * Re-run currently IN PROGRESS
   - Remaining periods to scrape after current run completes:
     * 2025-05-16 to 2025-06-30 (verify if already complete)
     * 2024 full year (not yet started)

2. PRICE DATA SCRAPE (initial_scrape.yml)
   - To be run AFTER current broker scrape completes (sequential — shares idx-database artifact)
   - Covers all 109 tickers including newly added PTRO and NIKL
   - start_date: 2021-01-01, end_date: 2026-03-28

3. TICKER UNIVERSE UPDATED ✅
   - Added PTRO and NIKL to LQ45_TICKERS in scraper/price_scraper.py
   - Removed 8 duplicate tickers from SMC Liquid section
   - New total: 109 unique tickers
"""

# ══════════════════════════════════════════════════════════════
# DATABASE STATE (verified 2026-03-28)
# ══════════════════════════════════════════════════════════════

DATABASE_STATE = """
File: idx_swing_trader.db (SQLite, ~34MB as of 2026-03-27)
Total records: 401,185 (all tables combined)
Broker summary date range: 2025-01-02 → 2025-06-30

Tables: broker_summary, stocks, daily_prices, foreign_flow,
        corporate_actions, index_daily, signal_log

broker_summary schema:
  id          INTEGER PK
  ticker      TEXT
  date        TEXT  (YYYY-MM-DD)
  broker_code TEXT
  broker_type TEXT  ('Asing' | 'Lokal' | 'Pemerintah')
  buy_value   REAL
  sell_value  REAL
  buy_volume  REAL
  sell_volume REAL
  net_value   REAL
  net_volume  REAL

Q1 2025 data quality (verified):
  - 58/58 trading days present ✅
  - 105-107 tickers per day ✅
  - 94 unique broker codes ✅
  - Broker type distribution: Asing 82,982 | Lokal 132,609 | Pemerintah 21,711 ✅
  - Net foreign flow Q1: Rp -20.3T (net sell) — consistent with IHSG weakness

Apr 1-7 2025: CONFIRMED PUBLIC HOLIDAY (Lebaran) — no data expected ✅

Apr 8 - May 15 2025 data quality (NEEDS RE-VERIFICATION after current run):
  - 24 days present but ALL at 71 tickers (should be ~105) ⚠️
  - Expected to be fixed by current in-progress workflow run

SHARED ARTIFACT WARNING:
  - idx-database is written by: scrape_broker_summary.yml, initial_scrape.yml,
    bootstrap_database.yml, daily_signals.yml
  - NEVER run any two of these workflows simultaneously
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
            "Real Stockbit broker flow scraping via Playwright (replaces synthetic estimates)",
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

8. WORKFLOW ROBUSTNESS MATTERS
   Discovered Mar 28 2026: old scrape workflow had no data guard — would
   overwrite good artifact with empty DB on failed runs. Always gate
   artifact uploads on record count check.

9. USE HEREDOC FOR MULTI-LINE PYTHON IN YAML
   python3 -c "..." with nested quotes causes SyntaxError.
   Always use python3 << 'EOF' ... EOF pattern in GitHub Actions workflows.

10. NEVER RUN WORKFLOWS SHARING idx-database IN PARALLEL
    Discovered Mar 28 2026: running scrape_broker_summary.yml and
    initial_scrape.yml simultaneously risks one workflow overwriting
    the other's data. Each workflow restores the artifact at the start,
    works on its own isolated copy, then uploads at the end —
    the last one to finish wins and the other's changes are lost.
    Always run sequentially. Verify by checking workflow files first.
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

4. APR-MAY 2025 DATA INCOMPLETE (being fixed)
   71 tickers per day instead of ~105 — batch 4 scraper cut off mid-run.
   Re-scrape in progress as of 2026-03-28.
"""

# ══════════════════════════════════════════════════════════════
# NEXT STEPS (IN ORDER)
# ══════════════════════════════════════════════════════════════

NEXT_STEPS = """
IMMEDIATE (in progress):
  ⏳ Re-run broker scrape: 2025-04-08 to 2025-05-15 (currently running)

AFTER CURRENT BROKER SCRAPE COMPLETES:
  1. Remove debug logging from broker_scraper.py
     (the logger.warning with data={data} added for Apr 1-7 investigation)

  2. Verify Apr 8 - May 15 data:
     - Check all days now have ~105 tickers (not 71)
     - Run verify_broker_data.py or manual SQL check

  3. Run initial_scrape.yml for price data (SEQUENTIAL — after broker scrape fully done)
     - start_date: 2021-01-01, end_date: 2026-03-28
     - Covers PTRO and NIKL (newly added tickers)

  4. Audit remaining broker periods:
     - 2025-05-16 to 2025-06-30 (check if already ~105 tickers/day)
     - If showing 71 tickers → re-run those batches too

  5. Backfill 2024 full year broker data:
     - Run batches 1-4 for 2024-01-01 to 2024-12-31
     - 4 batches × ~4 date ranges = ~16 workflow runs

  6. Integrate real broker data into signal_combiner.py:
     - Replace synthetic foreign flow with real Asing net_value from DB
     - Use broker_summary table directly in signal generation

  7. Re-run backtests with real broker data
     - Expected improvement especially in 2024 results

  8. Fix 6-10 day weak spot using broker accumulation signal

  9. Update daily_signals.yml to include live broker scraping each day

  10. Paper trade for 1 month → Go live
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
Auth: Bearer JWT token (~24 hour expiry — must be refreshed manually)
How to refresh token:
  1. Open stockbit.com/symbol/BBCA/chartbit in Chrome (already logged in)
  2. F12 → Network tab → click any exodus.stockbit.com request
  3. Copy Authorization header value (starts with "Bearer eyJ...")
  4. Go to GitHub → Settings → Secrets → update STOCKBIT_TOKEN
Response structure:
  data.broker_summary.brokers_buy[]  — net buyers
    .netbs_broker_code — broker code (e.g. "BK", "AK")
    .type   — "Asing" / "Lokal" / "Pemerintah"
    .blot   — net lots (positive)
    .bval   — net value (positive)
    .bvalv  — total value (buy+sell combined)
    .freq   — number of transactions
  data.broker_summary.brokers_sell[] — net sellers
    .slot   — net lots (negative)
    .sval   — net value (negative)
    .svalv  — total value
  data.bandar_detector — accumulation/distribution summary
    .broker_accdist — "Acc" / "Dist" / "Neutral"
Rate limit: ~40 requests per 5 minutes
"""

# ══════════════════════════════════════════════════════════════
# WORKFLOW REFERENCE
# ══════════════════════════════════════════════════════════════

WORKFLOWS = """
daily_signals.yml         — Week
