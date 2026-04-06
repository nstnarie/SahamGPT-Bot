"""
DEVELOPER_CONTEXT.py — Session Continuity Document
=====================================================
Last updated: April 2, 2026

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

  ✅ Artifact download → use dawidd6/action-download-artifact@v6
  ❌ Never use actions/download-artifact@v4 (only works for current run)

  ✅ Batch scraping → always run sequentially, one at a time
  ❌ Never run two batches in parallel (artifact collision)

  ✅ Batch 4 (34 tickers) for a full quarter → split into 2 date-range parts
  ❌ Never run batch 4 for a full quarter in one shot (~5.5hrs, too close to 6hr limit)

  ✅ update_split_files.yml → requires permissions: contents: write
  ❌ Without it, the push to repo will fail silently

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

STATUS = "ACTIVE — v9 backtest complete (2025, PF 2.14, +Rp 127M, DD -3.28%). Next: 2024 broker data backfill."

CURRENT_VERSION = "v9"

LATEST_BACKTEST_RESULTS = {
    "2025_synthetic": {
        "trades": 55, "win_rate": "31%", "pnl": "Rp +60M", "pf": 1.38,
        "note": "SUPERSEDED. Used synthetic FF from ForeignFlow table.",
    },
    "2025_real_broker_v6": {
        "trades": 41, "win_rate": "34.1%", "pnl": "Rp +73M", "pf": 1.78,
        "total_return": "7.30%", "max_drawdown": "-2.82%",
        "sharpe": 0.27, "sortino": 0.52, "calmar": 2.69,
        "note": "SUPERSEDED by v7. is_foreign_driven used abs-ratio > 5% (too permissive).",
        "star_trade": "PTRO: +Rp 39M (+45.1%) + ANTM: +Rp 27.5M (+45.4%)",
    },
    "2025_real_broker_v7": {
        "trades": 59, "win_rate": "33.9%", "pnl": "Rp +135M", "pf": 1.88,
        "total_return": "13.66%", "max_drawdown": "-4.75%",
        "sharpe": 0.93, "sortino": 1.70, "calmar": 2.99, "exposure": "65.3%",
        "note": "SUPERSEDED by v8. is_foreign_driven = directional consistency > 20%.",
        "star_trade": "TINS: +Rp 54M (+118%) + PTRO: +Rp 39M (+45%) + EMTK: +Rp 32M (+77%)",
    },
    "2025_real_broker_v8": {
        "trades": 60, "win_rate": "36.7%", "pnl": "Rp +145M", "pf": 1.97,
        "total_return": "14.63%", "max_drawdown": "-4.11%",
        "sharpe": 1.01, "sortino": 1.79, "calmar": 3.71,
        "note": "SUPERSEDED by v9.",
    },
    "2025_real_broker_v9": {
        "trades": 45, "win_rate": "37.8%", "pnl": "Rp +127M", "pf": 2.14,
        "total_return": "12.74%", "max_drawdown": "-3.28%",
        "sharpe": 0.89, "sortino": 1.54, "calmar": 4.16, "exposure": "70.4%",
        "note": "CURRENT BASELINE. 4 fixes: indicator warmup, gap-up filter, "
                "emergency stop -12%, cluster limit 5/10d.",
        "star_trade": "TINS: +Rp 54M (+118%) + PTRO: +Rp 38M (+45%) + EMTK: +Rp 32M (+77%)",
        "trend_exit": "8 trades, Rp +210M total",
    },
    "2024": {
        "trades": 45, "win_rate": "33%", "pnl": "Rp -37M", "pf": 0.68,
        "note": "Synthetic FF only. Real broker data backfill pending.",
    },
}

# ══════════════════════════════════════════════════════════════
# v10 EXPERIMENT LOG (feature/v10-experiments branch)
# ══════════════════════════════════════════════════════════════

V10_EXPERIMENTS = {
    "exp6_ihsg_5d_momentum": {
        "hypothesis": "Exp 2 single-day IHSG check passes during multi-day rollovers. "
                      "Requiring IHSG 5d return > 0 filters entries during sustained weakness. "
                      "Target: Apr-May 2025 losing cluster (-Rp 27.8M, 7 straight stops).",
        "change": "market_regime.py: added ihsg_5d_return > 0 as third condition in ihsg_entry_ok.",
        "result": {
            "trades": 36, "win_rate": "36.1%", "pnl": "Rp +77M", "pf": 1.86,
            "total_return": "7.68%", "max_drawdown": "-5.22%",
            "sharpe": 0.33, "sortino": 0.64, "calmar": 1.55, "exposure": "57.1%",
        },
        "vs_baseline": "vs Exp 4 baseline (41t, 41.5% WR, PF 2.52, +Rp 145M, Calmar 4.59): "
                       "catastrophic. PF -0.66, WR -5.4pp, return -Rp 68M, Calmar -3.04. "
                       "5-day lookback too backward-looking — blocks big winners (TINS, PTRO, EMTK) "
                       "that break out at the START of a recovery before 5d return turns positive.",
        "verdict": "REJECTED. 5-day IHSG momentum is too restrictive. The best breakouts happen "
                   "at the beginning of recoveries, exactly when 5d return is still negative. "
                   "The single-day IHSG filter (Exp 2) is already the right granularity.",
        "run_id": "24006068747",
        "date": "2026-04-05",
    },
    "exp5_remove_rp150_filter": {
        "hypothesis": "Real market observation found sub-Rp 150 stocks with valid breakout setups "
                      "being silently excluded. Removing filter may improve trade count and return.",
        "change": "signal_combiner.py: removed (df['close'] >= min_price) from is_breakout conditions.",
        "result": {
            "trades": 43, "win_rate": "39.5%", "pnl": "Rp +125M", "pf": 2.09,
            "total_return": "12.52%", "max_drawdown": "-4.29%",
            "sharpe": 0.86, "sortino": 1.48, "calmar": 3.11, "exposure": "69.7%",
        },
        "vs_baseline": "vs Exp 4 baseline (41t, 41.5% WR, PF 2.52, +Rp 145M, Calmar 4.59): "
                       "PF -0.43, WR -2.0pp, return -Rp 20M, DD worse (-3.37%→-4.29%), Calmar -1.48. "
                       "2 new trades unlocked: WTON (Jun 16) and GOTO (Nov 11) — BOTH emergency stops. "
                       "Sub-Rp 150 stocks are too volatile — hit -12% before any exit fires.",
        "verdict": "REJECTED. Rp 150 filter does real work — not filtering junk arbitrarily but "
                   "specifically blocking stocks volatile enough to produce emergency stops. Keep Rp 150.",
        "run_id": "24005950325",
        "date": "2026-04-05",
    },
    "exp4_trend_exit_cooldown": {
        "hypothesis": "After TREND_EXIT (+15%+ gain), block re-entry for 30 trading days. "
                      "Stock is at risk of exhaustion/distribution after a big move. "
                      "EMTK re-entered 17 trading days after TREND_EXIT → -Rp 7.9M emergency stop.",
        "change": "engine.py: cooldown now triggers on STOP_LOSS OR TREND_EXIT (was STOP_LOSS only). "
                  "Reuses existing stop_loss_cooldown_days=30 config value.",
        "result": {
            "trades": 41, "win_rate": "41.5%", "pnl": "Rp +145M", "pf": 2.52,
            "total_return": "14.55%", "max_drawdown": "-3.37%",
            "sharpe": 1.11, "sortino": 1.93, "calmar": 4.59, "exposure": "69.7%",
        },
        "vs_baseline": "vs Exp 2 baseline (42t, 40.5% WR, PF 2.33, +Rp 137M, Calmar 4.32): "
                       "PF +0.19, WR +1.0pp, return +Rp 8M, Sharpe +0.09, Calmar +0.27. "
                       "EMTK Oct re-entry eliminated (-Rp 7.9M emergency stop gone). All metrics improved.",
        "verdict": "ACCEPTED. All metrics improved. 30-day cooldown is the right duration for 2025 data. "
                   "⚠️ Re-test cooldown duration (30d) once full 2024 broker data is available — "
                   "2024 may have different re-entry patterns. New baseline: 41t | 41.5% WR | PF 2.52 | +Rp 145M | Calmar 4.59.",
        "run_id": "24005616009",
        "date": "2026-04-05",
    },
    "exp3_ff_magnitude_filter": {
        "hypothesis": "Require 5-day FF sum > 1.5x 20-day avg absolute flow. Only enter on abnormally strong accumulation.",
        "change": "signal_combiner.py: added ff_magnitude_ok as third condition in ff_full_confirm.",
        "result": {
            "trades": 43, "win_rate": "39.5%", "pnl": "Rp +134M", "pf": 2.25,
            "total_return": "13.36%", "max_drawdown": "-3.39%",
            "sharpe": 0.96, "sortino": 1.59, "calmar": 4.17, "exposure": "69.4%",
        },
        "vs_baseline": "vs Exp 2 baseline (42t, 40.5% WR, PF 2.33, +Rp 137M, Calmar 4.32): "
                       "all metrics declined. PF -0.08, WR -1pp, return -Rp 3M, Sharpe -0.06.",
        "verdict": "REJECTED. Existing count+trend checks already capture quality adequately. "
                   "Magnitude multiplier adds noise without benefit on 2025 dataset. Reverted.",
        "run_id": "23982978951",
        "date": "2026-04-04",
    },
    "exp2_ihsg_market_filter": {
        "hypothesis": "Skip entries on days IHSG close < MA20 or daily return < -1%. Expect fewer trades, higher WR.",
        "change": "market_regime.py: add ihsg_entry_ok column. signal_combiner.py: gate BUY on ihsg_entry_ok.",
        "result": {
            "trades": 42, "win_rate": "40.5%", "pnl": "Rp +137M", "pf": 2.33,
            "total_return": "13.73%", "max_drawdown": "-3.39%",
            "sharpe": 1.02, "sortino": 1.76, "calmar": 4.32, "exposure": "69.7%",
        },
        "vs_baseline": "PF 2.14→2.33, WR +2.7pp, return +Rp 10M, Sharpe 0.89→1.02, Calmar 4.16→4.32. "
                       "DD marginally worse (-3.28%→-3.39%, noise). Trades 45→42.",
        "verdict": "ACCEPTED. All key metrics improved. Filter removes losing entries on weak IHSG days. "
                   "This is the new v10 baseline.",
        "run_id": "23982879523",
        "date": "2026-04-04",
    },
    "exp1_emergency_stop_10pct": {
        "hypothesis": "Tighter emergency stop (-10% vs -12%) reduces worst losses without killing winners.",
        "change": "config.py emergency_stop_pct: 0.12 → 0.10",
        "result": {
            "trades": 45, "win_rate": "37.8%", "pnl": "Rp +111M", "pf": 1.88,
            "total_return": "11.08%", "max_drawdown": "-3.81%",
            "sharpe": 0.70, "sortino": 1.20, "calmar": 3.11, "exposure": "70.4%",
        },
        "vs_baseline": "PF 2.14→1.88, return -Rp 16M, DD worse (-3.28%→-3.81%), Calmar 4.16→3.11.",
        "verdict": "REJECTED. -10% stop clips winners that dip temporarily during the 5-day hold. "
                   "-12% is correctly calibrated. Reverted.",
        "run_id": "23982773904",
        "date": "2026-04-04",
    },
}

# ══════════════════════════════════════════════════════════════
# WHAT'S IN PROGRESS RIGHT NOW (as of 2026-04-01)
# ══════════════════════════════════════════════════════════════

IN_PROGRESS = """
1. BROKER SUMMARY DATA BACKFILL — 2025 FULLY COMPLETE ✅
   - H1 2025 (Jan–Jun): COMPLETE ✅ — 103–109 tickers/day
   - Q3 2025 (Jul–Sep): COMPLETE ✅ — 64 days, 105–107 tickers/day
   - Q4 2025 (Oct–Dec): COMPLETE ✅ — 63 days, 104–107 tickers/day
   - Total records: 1,043,576
   - Split files updated: 242,321 + 801,255 = 1,043,576 ✅
   - Apr 1–7 confirmed Lebaran holiday — no data expected ✅

2. 2024 BROKER DATA — IN PROGRESS 🔄
   - Q1 batch 1 (2024-01-01 to 2024-03-01, tickers 1–25): RUNNING (GH run 23958438367, Apr 4 2026)
   - Remaining: batch 2→3→batch4-split for Q1, then Q2→Q3→Q4 sequentially
   - After each quarter: export_summary.yml → update_split_files.yml

3. PRICE DATA ✅
   - initial_scrape.yml run on 2026-03-28
   - Covers all 107 tickers from 2021-01-01 to 2026-03-28
   - PTRO and NIKL were initially missing from daily_prices despite being in
     broker_summary. Fixed via self-healing backfill step in run_backtest.yml.

4. TICKER UNIVERSE — EXPANDED (as of 2026-04-06)
   - 136 unique tickers in LQ45_TICKERS (was 109 as of 2026-03-28)
   - 27 new tickers added Apr 6 2026 (scraper/price_scraper.py):
     Batch 1 (high-liquidity): AADI, ADMR, BREN, BRIS, CUAN, DEWA, PANI, PSAB, RAJA, RATU, WIFI
     Batch 2 (additional screening): ADHI, AGRO, AMAN, ARGO, ARTO, ASSA, AVIA, BNBA,
                                      DOID, ENRG, IMAS, KRAS, POWR, SMBR, SMDR, WIIM
   - Excluded (sub-Rp150): MLPL(91), ABBA(44), ACST(98), BKSL(108)
   - Excluded (too thin <Rp1B/day): AMAR(0.11), CMNP(0.37), IMAS excluded then re-added by user,
     MCAS(0.13) — IMAS, ARGO, BNBA added despite thin volume by user decision
   - ENRG shows unusual price (1500) in yfinance — verify manually before scraping
   - Pending: initial_scrape.yml + scrape_broker_summary.yml for 27 new tickers after 2024 backfill

5. REAL BROKER BACKTEST — COMPLETE ✅ (as of 2026-04-03, v9)
   - 2025 full year with real Asing flow: 45 trades, 37.8% WR, PF 2.14, +Rp 127M
   - v7: is_foreign_driven = directional consistency > 20%
   - v8: hold extension — skip stop days 6-10 if acc_score > 0
   - v9: indicator warmup + gap-up filter + emergency stop -12% + cluster limit 5/10d
   - Integration confirmed working: --real-broker flag in run_backtest.yml
"""

# ══════════════════════════════════════════════════════════════
# DATABASE STATE (verified 2026-04-01)
# ══════════════════════════════════════════════════════════════

DATABASE_STATE = """
File: idx_swing_trader.db (SQLite)
broker_summary record count: 1,043,576
broker_summary date range: 2025-01-02 → 2025-12-31
Unique tickers in broker_summary: 109 | Unique broker codes: 95
Unique tickers in daily_prices: 107 (PTRO and NIKL backfilled via run_backtest.yml self-heal)

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

Data quality (verified via export_summary.yml):
  - H1 2025 (Jan–Jun):  103–109 tickers/day ✅
  - Q3 2025 (Jul–Sep):  105–107 tickers/day, 64 trading days ✅
  - Q4 2025 (Oct–Dec):  104–107 tickers/day, 63 trading days ✅
  - Apr 1–7 2025: confirmed Lebaran holiday — no data exists ✅

Q4 2025 scraping detail:
  Batch 1 (tickers 0–24):    +84,209  → 840,579 total
  Batch 2 (tickers 25–49):   +69,214  → 909,793 total
  Batch 3 (tickers 50–74):   +58,359  → 968,152 total
  Batch 4 (Oct 1–Nov 15):    +40,314  → 1,008,466 total
  Batch 4 (Nov 15–Dec 31):   +35,110  → 1,043,576 total

Split files (fallback if artifact unavailable):
  - Updated after Q4 completion via update_split_files.yml
  - Split verified: 242,321 + 801,255 = 1,043,576 ✅
  - idx_broker_part_a.db + idx_broker_part_b.db in repo root

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
        "result": "2025 real broker: 41 trades, 34.1% WR, PF 1.78, +Rp 73M. SUPERSEDED by v7.",
        "star": "PTRO: +Rp 39M (+45.1%) + ANTM: +Rp 27.5M (+45.4%)",
    },
    "v7": {
        "signal": "v6 + directional consistency for is_foreign_driven detection",
        "new_features": [
            "is_foreign_driven = directional consistency > 20% (was: abs(net)/daily_value > 5%)",
            "Consistency = abs(sum(net,60d)) / sum(abs(net),60d) — measures persistent direction",
            "Old formula classified 108/109 tickers as foreign-driven (abs value is noise)",
        ],
        "result": "2025 real broker: 59 trades, 33.9% WR, PF 1.88, +Rp 135M. SUPERSEDED by v8.",
    },
    "v9": {
        "signal": "v8 + 4 structural fixes",
        "new_features": [
            "Indicator warmup: load prices from 5 months before backtest start (fixes blind first 3 months)",
            "Gap-up entry filter: skip if stock opens >7% above signal day close (EMTK Oct 2 fix)",
            "Emergency stop: -15% → -12% (ESSA/EMTK losses reduced)",
            "Cluster limit: max 5 entries per rolling 10 trading days (May 2025 fix: 13→5 entries)",
        ],
        "result": "2025 real broker: 45 trades, 37.8% WR, PF 2.14, +Rp 127M, DD -3.28%, Calmar 4.16",
        "tradeoff": "Fewer trades (-15) but higher quality. PF +0.17, DD tighter, Calmar improved.",
        "star": "TINS: +Rp 54M (+118%) + PTRO: +Rp 38M (+45%) + EMTK: +Rp 32M (+77%)",
    },
    "v8": {
        "signal": "v7 + broker accumulation hold extension",
        "new_features": [
            "load_broker_accumulation_df() in data_loader.py — per-broker consistency score",
            "accumulation_score = count(Asing brokers accumulating) - count(distributing)",
            "Accumulating broker: active 3+/5 days AND net buyer 4+/5 days",
            "Hold extension in portfolio.py: if acc_score > 0 on days 6-10 → skip stop once",
            "Rationale: dip being bought by institutions → likely temporary, not distribution",
        ],
        "result": "2025 real broker: 60 trades, 36.7% WR, PF 1.97, +Rp 145M, Sharpe 1.01",
        "star": "TINS: +Rp 54M (+118%) + EMTK: +Rp 32M (+77%) + PTRO: +Rp 39M (+45%)",
        "trend_exit": "11 trades, all winners, Rp +261M total",
        "note": "acc_score failed as ENTRY filter (count-based vs value-based conflict). "
                "Works well as EXIT/HOLD signal because it's meaningful at stop-fire moment.",
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

18. INDICATOR WARMUP IS CRITICAL FOR EARLY BACKTEST PERIOD
    Discovered Apr 3 2026: loading prices from backtest start_date means the first
    ~60 trading days (~3 months) have no valid 60-day high or MA50. Stocks like BBTN
    (770→1280 rally starting Mar 25 2025) were entirely invisible. Fix: load prices
    from 5 months before start_date. Trading still begins at start_date. Pure bug fix.

19. ENTRY-DAY GAP-UP IS A REJECTION RISK
    Discovered Apr 3 2026: EMTK Oct 2 2025 — signal fired on Oct 1 (clean candle,
    close at high). Entry next day opened +5.4% gap-up at 1650, spike to 1700, then
    collapsed. Entered at top of rejection candle → emergency stopped -16%, -Rp 10M.
    Fix: skip entry if open > 7% above prior close. Already had gap-DOWN filter.

20. SIGNAL CLUSTERING = FAKE BREAKOUT WEEK
    Discovered Apr 3 2026: May 2025 had 13 entries in 8 days, 11 of 13 were losers
    (-Rp 9M total). Many stocks breaking out simultaneously often means broad market
    euphoria, not stock-specific setups. Fix: max 5 entries per rolling 10 trading days.

17. BROKER ACCUMULATION SCORE WORKS AS HOLD SIGNAL, NOT ENTRY FILTER
    Discovered Apr 3 2026: count-based acc_score (accumulators - distributors) fails
    as an entry filter because 84% of breakout days have negative scores. Root cause:
    1-2 large Asing brokers driving the move are outnumbered by many small sellers.
    ff_confirmed (value-weighted) already captures the large broker activity.
    However, acc_score > 0 works well as a hold extension on days 6-10: if brokers
    are still net-accumulating on the day a stop fires, the dip is institutional buying.
    Result: WR 33.9%→36.7%, PF 1.88→1.97, drawdown improved -4.75%→-4.11%.

16. DIRECTIONAL CONSISTENCY BEATS ABS-RATIO FOR is_foreign_driven DETECTION
    Discovered Apr 3 2026: old formula abs(net)/daily_value > 5% classified 108/109
    tickers as foreign-driven. Even random/noise Asing trading passes the abs threshold.
    New formula: consistency = abs(sum(net,60d)) / sum(abs(net),60d) > 20%.
    This measures whether foreigners trade with persistent direction (1.0 = always same
    side, 0.0 = random). Result: PF 1.78→1.88, return 7.3%→13.66%, Sharpe 0.27→0.93.
    The 18 extra trades came from stocks where the old formula was randomly blocking
    valid breakouts by requiring FF confirmation on noise-flow stocks.

13. LOKAL AGGREGATE FLOW IS NOISE — USE ASING-ONLY
    Tried (Apr 2026): detect dominant investor type per ticker by comparing
    avg |Asing net| vs avg |Lokal net|. Failed catastrophically (PF 0.71, -Rp 31M).
    Root cause: 100+ domestic broker codes aggregated always dwarf ~20 foreign codes
    by raw volume — nearly every stock becomes "Lokal-dominated" and Lokal aggregate
    flow is noise. Asing-only is correct. For non-foreign-driven stocks,
    signal_combiner.py's is_foreign_driven check (Asing ratio > 5% of daily value)
    already skips the FF filter automatically — no special code needed.

14. MISSING PRICE DATA SILENTLY KILLS TICKERS
    PTRO and NIKL had full 2025 broker data (235+ days of Asing activity) but ZERO
    price history in daily_prices. The engine silently skipped them every backtest.
    PTRO alone was worth +Rp 39M (+45.1%) in 2025. Fix: run_backtest.yml now has a
    self-healing backfill step that detects and fetches missing tickers from Yahoo Finance.

15. POSITION SIZING IS ALREADY PERCENTAGE-BASED
    Not fixed-amount. Engine uses: 1.5% equity risk/trade, 12% max per position,
    90% max total exposure, 30% max per sector, 5% settlement buffer.
    Natural max ~7-8 concurrent positions. No hard limit needed.
    Located in backtest/portfolio.py:74-126.

10. NEVER RUN WORKFLOWS SHARING idx-database IN PARALLEL
    Discovered Mar 28 2026: running scrape_broker_summary.yml and
    initial_scrape.yml simultaneously risks one workflow overwriting
    the other's data. Each workflow restores the artifact at the start,
    works on its own isolated copy, then uploads at the end —
    the last one to finish wins and the other's changes are lost.
    Always run sequentially. Verify by checking workflow files first.

11. BATCH 4 NEEDS DATE-RANGE SPLITTING FOR FULL QUARTERS
    Discovered Mar 31 2026: batch 4 covers 34 tickers (not 25).
    A full quarter (~65 trading days) takes ~5.5 hours — dangerously
    close to the GitHub Actions 6-hour timeout. Always split batch 4
    into 2 date-range parts (~45 days each) for full-quarter runs.
    The duplicate guard in scrape_historical makes overlap dates safe.

12. USE dawidd6/action-download-artifact@v6 FOR ARTIFACT RESTORE
    Discovered Mar 29 2026: actions/download-artifact@v4 only downloads
    artifacts from the current run — silently returns nothing for previous
    runs. dawidd6/action-download-artifact@v6 correctly fetches the most
    recent artifact from any previous run. Always use v6.
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
   Could be market conditions, or 2024 broker data might improve entry timing.
   Must backfill 2024 broker data and re-test before drawing conclusions.

3. ALPHA STILL NEGATIVE vs IHSG
   2025 real-broker: +7.30% vs IHSG +20.71%. Alpha = -13.99%.
   Model protects capital well (max DD -2.82% vs IHSG -17.76%)
   but can't match the bull run. May require sector rotation or
   leverage to close the gap — needs more data before deciding.
"""

# ══════════════════════════════════════════════════════════════
# NEXT STEPS (IN ORDER)
# ══════════════════════════════════════════════════════════════

NEXT_STEPS = """
⚠️ BRANCH ISOLATION RULE (active while 2024 broker scraper is running):
  All code experiments must run on branch: feature/v10-experiments
  Do NOT commit experimental code to main.
  Do NOT trigger run_backtest.yml from main.
  Reason: scrape_broker_summary.yml is actively writing to idx-database.
  run_backtest.yml on main uploads idx-database with overwrite=true — this
  would clobber the scraper's work if run while scraping is in progress.
  The feature branch workflow is read-only for idx-database (upload step
  is gated: if: always() && github.ref == 'refs/heads/main').

IMMEDIATE — PARALLEL TRACKS:
  Track A: 2024 broker data backfill (scraper running, sequential batches)
    1. Q1 2024: ✅ batch 1 triggered (2024-01-01→2024-03-01) | batch 2→3→batch4-split pending
    2. Q2 2024: batches 1→2→3, then batch 4 split: Apr 1–May 15, May 15–Jun 30
    3. Q3 2024: batches 1→2→3, then batch 4 split: Jul 1–Aug 15, Aug 15–Sep 30
    4. Q4 2024: batches 1→2→3, then batch 4 split: Oct 1–Nov 15, Nov 15–Dec 31
    After each quarter: export_summary.yml → update_split_files.yml

  Track B: v10 experiments on feature/v10-experiments branch (one per session)
    v9 baseline: 45 trades | 37.8% WR | PF 2.14 | +Rp 127M | DD -3.28% | Calmar 4.16
    Always test: 2025-01-01→2025-12-31 | capital=1B | real_broker=true
    Trigger: gh workflow run run_backtest.yml --ref feature/v10-experiments ...

    ✅ Exp 1: REJECTED — Emergency stop -10% (run 23982773904)
    ✅ Exp 2: ACCEPTED — IHSG market filter (run 23982879523) — baseline PF 2.33
    ✅ Exp 3: REJECTED — FF magnitude filter (run 23982978951)
    ✅ Exp 4: ACCEPTED — Post-TREND_EXIT cooldown 30d (run 24005616009)
              PF 2.33→2.52, WR +1.0pp, return +Rp 8M, Sharpe +0.09, Calmar +0.27
              New baseline: 41t | 41.5% WR | PF 2.52 | +Rp 145M | Calmar 4.59
              ⚠️ Re-test 30d cooldown value once full 2024 data available

    ✅ Exp 5: REJECTED — Remove Rp 150 min price filter (run 24005950325)
              PF 2.52→2.09, WR -2pp, return -Rp 20M, DD worse, Calmar 4.59→3.11.
              2 new sub-Rp 150 trades (WTON, GOTO) both hit EMERGENCY_STOP immediately.
              Rp 150 filter correctly excludes stocks too volatile for the strategy.

    ── From v9 Trade Log Loss Analysis (28 losses, -Rp 103M total) ──

    ✅ Exp 6: REJECTED — IHSG 5-day momentum filter (run 24006068747)
              PF 2.52→1.86, WR -5.4pp, return -Rp 68M, Calmar 4.59→1.55.
              Too backward-looking — best breakouts start recoveries when 5d return still negative.
              Single-day IHSG filter (Exp 2) is already the right granularity.

    ✅ Exp 7: REJECTED — Financial Services sector entry limit (run 24006206306)
              Zero effect — identical results to baseline (41t, PF 2.52, +Rp 145M).
              Root cause: 4 bank entries in 2025 are in May, Jul, Aug, Nov — never within
              the same 10-day window. Limit never fires on 2025 data.
              ⚠️ Re-test with full 2024+2025 data — bank clustering may be more common
              in a fuller dataset. Idea is sound but 2025 alone doesn't expose it.

    ⬜ Exp 8: Breakout margin filter (require close X% above 60-day high)
              File: signals/signal_combiner.py (_add_breakout_signals)
              Hypothesis: current filter passes any close > 60d high, even by 0.1%.
              Marginal breakouts (barely above resistance) fail more often than strong ones.
              Require close to be at least 1–2% above the 60-day high to confirm the
              resistance is genuinely broken and not just noise. May reduce trade count
              but improve WR and PF.
              Pattern source: Emergency stop trades (ESSA, HRUM, EMTK Oct) — marginal entries

    ⬜ Exp 9: Early no-follow-through exit
              File: backtest/portfolio.py (check_exit_conditions)
              Hypothesis: 6 TIME_EXIT losses held 15-18 days with only -1% to -3.9% loss
              (-Rp 11.1M combined). These stocks never moved after the breakout. If a stock
              hasn't gained at least +1% by day 8 (after the 5-day hold), it has no momentum
              and is tying up capital. Exit early to redeploy into stronger setups.
              Risk: may clip slow-starters that eventually move. Watch carefully.
              Pattern source: Trades #8, #17, #24, #25, #26, #28

    ⬜ Exp 10: ATR/price volatility cap
              File: signals/signal_combiner.py or config.py
              Hypothesis: stocks with ATR/price > ~5% are too whippy — normal daily moves
              regularly trigger stops before the trend develops. The emergency stops (ESSA,
              HRUM) were both high-volatility small-caps. Adding a maximum ATR/price ratio
              filter (e.g., skip if ATR > 5% of close) would exclude inherently unstable
              stocks while keeping steady trend candidates.
              Pattern source: Emergency stop trades (-Rp 25.1M from 3 trades)

    ── ON HOLD (complex — do after integration) ──

    ⬜ Exp 7a: Support/resistance detection for entry + exit
              Files: signals/signal_combiner.py, backtest/engine.py, backtest/portfolio.py
              Hypothesis: historical price clusters identify structural support levels.
              Entry: only buy on confirmed resistance breakout (augments 60-day high).
              Exit: break below support → stronger signal than fixed % stop.

    ⬜ Exp 7b: Averaging up on resistance break — ON HOLD (needs 7a)
              Files: backtest/engine.py, backtest/portfolio.py
              Hypothesis: if stock breaks next resistance level while held, add to position.
              Note: engine rewrite required — position currently entered once, never added to.

    ⬜ Exp 7c: Chart pattern detection — ON HOLD (needs 7a)
              Files: signals/signal_combiner.py, backtest/engine.py
              Hypothesis: detect ascending triangle, H&S, IH&S, double bottom/top from 7a's
              S/R structure. Use as entry/exit filters + IHSG trend detection. Conclusions only.

AFTER 2024 BACKFILL — TICKER UNIVERSE EXPANSION (27 new tickers in LQ45_TICKERS):
  5a. Run initial_scrape.yml — fetch OHLCV 2021-01-01→present for all 27 new tickers
  5b. Run scrape_broker_summary.yml with tickers override, date range 2024-01-01→2025-12-31
      (run sequentially, one batch at a time — idx-database shared artifact)
  5c. export_summary.yml → verify counts → update_split_files.yml → push to main
  ⚠️ Verify ENRG price manually before scraping — yfinance shows unusual Rp 1500 close

AFTER 2024 BACKFILL + ACCEPTED v10 EXPERIMENTS:
  6. Re-run backtest for 2024 with real_broker=true
  7. Compare 2024 real vs synthetic (-37M) — expect improvement
  8. Run combined 2024+2025 backtest for full picture (now 136 tickers)
  9. Merge feature/v10-experiments → main via PR
  10. Integrate into live path (main_daily.py → signal_combiner.py)
  11. Update daily_signals.yml with live broker scraping
  12. Paper trade 1 month → go live

COMPLETED (April 5, 2026):
  ✅ Exp 4 ACCEPTED — post-TREND_EXIT cooldown 30d (run 24005616009)
     PF 2.33→2.52 | WR +1pp | +Rp 8M | Calmar 4.32→4.59
     Eliminates EMTK Oct re-entry (-Rp 7.9M emergency stop)
     ⚠️ Re-test 30d cooldown value with full 2024 data

COMPLETED (April 4, 2026):
  ✅ v9 GitHub Actions re-run confirmed — identical results (run 23958174058)
  ✅ 2024 Q1 broker scrape batch 1 triggered (run 23958438367, 2024-01-01→2024-03-01)
  ✅ Trade log downloaded locally: reports/latest/trade_log.csv
  ✅ feature/v10-experiments branch created and pushed
  ✅ run_backtest.yml: idx-database upload gated to main branch only

COMPLETED (April 3, 2026):
  ✅ v9: 4 structural fixes (warmup, gap-up filter, emergency -12%, cluster limit)
  ✅ 2025 real-broker v9: 45 trades, 37.8% WR, PF 2.14, +Rp 127M, Calmar 4.16
  ✅ v8: hold extension in portfolio.py (acc_score > 0 on days 6-10 → skip stop)
  ✅ load_broker_accumulation_df() added to data_loader.py
  ✅ 2025 real-broker v8 backtest: 60 trades, 36.7% WR, PF 1.97, +Rp 145M, Sharpe 1.01
  ✅ v7: is_foreign_driven = directional consistency > 20% in signal_combiner.py
  ✅ 2025 real-broker v7 backtest: 59 trades, 33.9% WR, PF 1.88, +Rp 135M, Sharpe 0.93

COMPLETED (April 2, 2026):
  ✅ Real broker data integrated into backtest via --real-broker flag
  ✅ Self-healing merge step in run_backtest.yml (broker_summary from split files)
  ✅ Self-healing price backfill in run_backtest.yml (PTRO/NIKL from Yahoo Finance)
  ✅ 2025 real-broker v6 backtest: 41 trades, 34.1% WR, PF 1.78, +Rp 73M
  ✅ Dominant investor detection (v3) rejected — Lokal aggregate is noise
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
daily_signals.yml         — Weekday 16:35 WIB — full pipeline → Telegram (touches idx-database)
initial_scrape.yml        — Manual — historical price download (touches idx-database)
run_backtest.yml          — Manual — on-demand backtesting (touches idx-database)
monthly_optimise.yml      — Monthly — parameter tuning (touches idx-database)
scrape_broker_summary.yml — Manual — batch broker data scraping (touches idx-database)
export_summary.yml        — Manual — export per-day ticker count CSV (read-only)
bootstrap_database.yml    — Manual one-time — merges split files into artifact (touches idx-database)
update_split_files.yml    — Manual — regenerates split files from artifact (read-only, pushes to repo)

scrape_broker_summary.yml inputs:
  start_date  — YYYY-MM-DD
  end_date    — YYYY-MM-DD
  batch       — 1 (tickers 0–24) / 2 (25–49) / 3 (50–74) / 4 (75+, 34 tickers) / all
  tickers     — optional comma-separated override e.g. NIKL,PTRO (bypasses batch slicing)

Runtime estimates:
  Batches 1–3 (25 tickers) × 65 trading days: ~4.1 hours
  Batch 4 (34 tickers) × 65 trading days:     ~5.5 hours → ALWAYS split into 2 date-range parts
  Targeted backfill (2 tickers × 128 days):   ~37 minutes
"""
