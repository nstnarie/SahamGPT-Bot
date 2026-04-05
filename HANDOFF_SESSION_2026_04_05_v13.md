# SahamGPT-Bot — Session Handoff Document
> Last updated: April 5, 2026 (v13 — 2024 Q1 complete, Q2 batches 1+2 done, batch 3 running)
> Repo: https://github.com/nstnarie/SahamGPT-Bot (public, Python 100%)
> Paste this at the start of a new chat to resume seamlessly.

---

## ⚠️ CLAUDE: READ THIS BEFORE DOING ANYTHING

1. **Read `DEVELOPER_CONTEXT.py` first** — locked rules, hard parameters, architectural decisions.
2. **Never answer workflow questions without reading the actual .yml files first.**
3. **`idx-database` is shared** — `scrape_broker_summary.yml`, `initial_scrape.yml`, `bootstrap_database.yml`, `daily_signals.yml`. **NEVER run in parallel.**
4. **Data loss is unrecoverable.** When in doubt, stop and ask Arie.

---

## 1. Current Version: v9 — Current Backtest Baseline

### 2025 Real Broker Backtest — v9 (CONFIRMED April 4, 2026 via GitHub Actions run 23958174058)
| Metric | Value |
|--------|-------|
| Trades | 45 |
| Win Rate | 37.8% |
| Total Return | +12.74% (+Rp 127M) |
| Profit Factor | **2.14** |
| Max Drawdown | -3.28% |
| Sharpe | 0.89 |
| Sortino | 1.54 |
| Calmar | **4.16** |
| Exposure | 70.4% |

Star trades: TINS +Rp 54M (+118%), PTRO +Rp 38M (+45%), EMTK +Rp 32M (+77%)
TREND_EXIT: 8 trades, Rp +210M total

### feature/v10-experiments baseline (post Exp 2)
| Metric | Value |
|--------|-------|
| Trades | 42 |
| Win Rate | 40.5% |
| Total Return | +13.73% (+Rp 137M) |
| Profit Factor | **2.33** |
| Max Drawdown | -3.39% |
| Sharpe | 1.02 |
| Calmar | **4.32** |

---

## 2. What Happened This Session (April 5, 2026)

### 2024 Q1 Broker Backfill — COMPLETE ✅
All 6 batch runs completed successfully. All runs status: success.

| Run | Batch | Date Range | Tickers | Records Added |
|-----|-------|-----------|---------|---------------|
| 23958438367 | 1 pt1 | 2024-01-01 → 2024-03-01 | 1–25 | +52,080 |
| 23967693713 | 1 pt2 | 2024-03-01 → 2024-03-31 | 1–25 | +22,120 |
| 23970243812 | 2 | 2024-01-01 → 2024-03-31 | 26–50 | +63,232 |
| 23977448331 | 3 | 2024-01-01 → 2024-03-31 | 51–74 | +47,706 |
| 23982135534 | 4 pt1 | 2024-01-01 → 2024-02-15 | 75+ | +32,539 |
| 23989786558 | 4 pt2 | 2024-02-16 → 2024-03-31 | 75+ | +30,969 |

- **Total added:** +248,646 records
- **DB after Q1:** 1,292,222 records, range 2024-01-02 → 2025-12-30
- **58 trading days** in Q1 2024 (normal — includes Chinese New Year holiday Feb 10)
- DATA_OK=true ✅, BBCA spot-check passed ✅

### export_summary.yml — run 23994101016 ✅
- Confirmed 58 days exported, total 1,292,222 records
- No LOW-coverage days found

### update_split_files.yml — run 23995260146 ✅
- Split verified: 490,967 + 801,255 = 1,292,222 ✅
- `idx_broker_part_a.db`: 19.7MB → 39.9MB (2024 Q1 added to part_a)
- `idx_broker_part_b.db`: unchanged (2025 data)
- Committed to main: `d188a73`

### 2024 Q2 Broker Backfill — IN PROGRESS 🔄
| Run | Batch | Tickers | Status |
|-----|-------|---------|--------|
| 23995308646 | 1 | 1–25 | ✅ Done |
| 23999239806 | 2 | 26–50 | ✅ Done |
| 24003326023 | 3 | 51–74 | 🔄 Running (~4h, started Apr 5) |
| TBD | 4 pt1 | 75+, Apr 1→May 15 | ⬜ |
| TBD | 4 pt2 | 75+, May 15→Jun 30 | ⬜ |

- **Stockbit token renewed Apr 5 morning — refresh again before batch 4**

---

## 3. Entry / Exit Rules (unchanged from v9)

### Entry (ALL must be true)
| # | Condition | Value |
|---|-----------|-------|
| 1 | Resistance breakout | Close > 60-day high |
| 2 | Volume spike | 1.5x–5.0x 20-day avg |
| 3 | Uptrend | Close > 50-day MA |
| 4 | Min price | >= Rp 150 |
| 5 | No selling pressure | Upper shadow < 40%, close upper 2/3 |
| 6 | Foreign flow trend | 5-day FF sum > 0, breakout day not net sell *(if `is_foreign_driven`)* |
| 7 | RSI | 40–75 |
| 8 | MACD | Histogram > 0 |
| 9 | Regime | Not BEAR |
| 10 | No gap-up | Entry day open not >7% above signal day close |
| 11 | Cluster limit | Max 5 new entries in rolling 10 trading days |

### Exit (first trigger wins)
| Priority | Rule |
|----------|------|
| 1 | -12% emergency stop (always) |
| 2 | No stop first 5 days |
| 3 | Close < MA10 after +15% gain |
| 4 | -7% or 1.5xATR, cap -10% — hold extension if acc_score > 0 on days 6–10 |
| 5 | Sell 30% at +15% |
| 6 | No +3% in 15 days + below MA10 |
| 7 | 5 consecutive net foreign sell days (foreign-driven, price weakening) |
| 8 | BEAR regime = close all |

---

## 4. Architecture (unchanged)

### Two execution paths — NEVER cross-contaminate
- BACKTEST: `main_backtest.py → backtest/engine.py`
- LIVE: `main_daily.py → signals/signal_combiner.py`

### Key files changed in v9
- `config.py`: `emergency_stop_pct=0.12`, `max_gap_up_pct=0.07`, `max_entries_per_week=5`
- `main_backtest.py`: warmup_start = start - 5 months for price loading
- `backtest/engine.py`: gap-up filter + rolling 10-day cluster limit

### Key files changed in feature/v10-experiments (Exp 2 only)
- `signals/market_regime.py`: adds `ihsg_entry_ok` column
- `signals/signal_combiner.py`: gates BUY on `ihsg_entry_ok`

---

## 5. Database State (as of April 5, 2026)

- **broker_summary:** 1,292,222 records, 2024-01-02 → 2025-12-30
- **broker_summary 2024 Q1:** COMPLETE ✅ — 58 trading days, all 109 tickers
- **broker_summary 2024 Q2:** batch 1 in progress (2024-04-01→2024-06-30, tickers 1–25)
- **daily_prices:** 107 tickers, 2021-01-01 to 2026-03-28
- **Split files:** `idx_broker_part_a.db` (490,967) + `idx_broker_part_b.db` (801,255) = 1,292,222 ✅

---

## 6. Workflows

All workflows touching idx-database must run **sequentially, never in parallel.**

| File | Touches idx-database? | Purpose |
|------|-----------------------|---------|
| `daily_signals.yml` | ✅ | Full pipeline → Telegram (weekday 16:35 WIB) |
| `initial_scrape.yml` | ✅ | Historical price download |
| `run_backtest.yml` | ✅ | On-demand backtesting |
| `scrape_broker_summary.yml` | ✅ | Batch broker data scraping |
| `export_summary.yml` | ❌ | Export per-day ticker count CSV |
| `bootstrap_database.yml` | ✅ | Merges split files into artifact |
| `update_split_files.yml` | ❌ | Regenerates split files |

**IMPORTANT:** `run_backtest.yml` uploads idx-database with `if: always()` + `overwrite: true`.
Never run it simultaneously with any scraping workflow.

---

## 7. Next Steps (in order)

### IMMEDIATE — 2024 Broker Data Backfill
Refresh Stockbit token before each session. One batch at a time, sequential.

```
Q1 2024: ✅ COMPLETE (all batches + export + split files updated)

Q2 2024:
  ✅ batch 1 done (run 23995308646, tickers 1–25)
  ✅ batch 2 done (run 23999239806, tickers 26–50)
  🔄 batch 3 RUNNING (run 24003326023, tickers 51–74)
  ⬜ batch 4 pt1 (2024-04-01→2024-05-15, tickers 76+)
  ⬜ batch 4 pt2 (2024-05-15→2024-06-30, tickers 76+)
  ⬜ export_summary.yml → verify → update_split_files.yml

Q3 2024: batch1 → batch2 → batch3 → batch4 (Jul 1–Aug 15) → batch4 (Aug 15–Sep 30)
Q4 2024: batch1 → batch2 → batch3 → batch4 (Oct 1–Nov 15) → batch4 (Nov 15–Dec 31)
```
After each quarter: `export_summary.yml` → verify → `update_split_files.yml`

### AFTER 2024 BACKFILL
- Run `run_backtest.yml` real_broker=true, 2024-01-01 to 2024-12-31
- Compare vs synthetic: 45 trades, 33% WR, -Rp 37M, PF 0.68
- Run combined 2024+2025

### v10 EXPERIMENTS — ORDERED QUEUE
⚠️ **ALL experiments run on `feature/v10-experiments` branch ONLY.**
⚠️ **Do NOT merge to main and do NOT trigger backtest from main while the 2024 broker scraper is running.**
⚠️ **One experiment per session. Backtest → compare vs baseline → accept/reject → document → next.**

v9 baseline: 45 trades | 37.8% WR | PF 2.14 | +Rp 127M | DD -3.28% | Calmar 4.16
**Current baseline (post Exp 2): 42 trades | 40.5% WR | PF 2.33 | +Rp 137M | DD -3.39% | Calmar 4.32**

| # | Experiment | File(s) to change | Hypothesis |
|---|------------|-------------------|------------|
| ~~1~~ | ~~Emergency stop -12% → -10%~~ | ~~`config.py:137`~~ | **REJECTED (2026-04-04, run 23982773904).** PF 2.14→1.88, return -Rp 16M, DD worse. -10% clips recovering winners. -12% stays. |
| ~~2~~ | ~~IHSG market filter (close > MA20, daily > -1%)~~ | ~~`signals/market_regime.py`, `signals/signal_combiner.py`~~ | **ACCEPTED (2026-04-04, run 23982879523).** PF 2.14→2.33, WR +2.7pp, return +Rp 10M, Sharpe 0.89→1.02. New baseline. |
| ~~3~~ | ~~FF magnitude: require 5-day sum > 1.5x 20-day avg absolute flow~~ | ~~`signals/signal_combiner.py`~~ | **REJECTED (2026-04-04, run 23982978951).** PF 2.33→2.25, WR -1pp, Sharpe -0.06. Existing count+trend checks sufficient. Reverted. |
| 4 | Remove Rp 150 min price filter | `signals/signal_combiner.py` | Real market observation found potential sub-Rp 150 stocks with valid breakout setups. Test if removing the filter improves trade count and return without degrading quality (PF, WR, DD). **NEXT after 2024 backfill complete.** |
| 5a | Support/resistance detection for entry + exit | `signals/signal_combiner.py`, `backtest/engine.py`, `backtest/portfolio.py` | Historical price clusters identify structural support/resistance. **Entry:** only buy when stock breaks above historical resistance (replaces or augments current 60-day high breakout). **Exit:** breaking below support → stronger exit signal than time/stop. **ON HOLD — do after integration.** |
| 5b | Averaging up on resistance break | `backtest/engine.py`, `backtest/portfolio.py` | If stock breaks next resistance level while held, add to position. Only attempt after 5a. **ON HOLD.** |
| 5c | Chart pattern detection (signal logic only) | `signals/signal_combiner.py`, `backtest/engine.py` | Detect patterns (ascending triangle, H&S, IH&S, double bottom/top) from support/resistance structure built in 5a. Use as entry/exit conditions — e.g., skip entry on H&S right shoulder, confirm entry on ascending triangle breakout. Also apply to IHSG for market trend detection (IH&S = bullish). No chart rendering — conclusions only. **ON HOLD — depends on 5a.** |

### INTEGRATION — NEXT STEP (do before 4a/4b)
⚠️ **Only after the 2024 broker scraper is fully complete** (all batches Q1–Q4 done + split files updated).
- Merge `feature/v10-experiments` → `main` via PR (Exp 2 IHSG filter is the only accepted change)
- Run `run_backtest.yml` from main to confirm baseline is stable post-merge
- Then tackle 4a/4b on a fresh branch

### AFTER INTEGRATION
- Integrate accepted v10 changes into live path (`main_daily.py → signal_combiner.py`)
- Update `daily_signals.yml` with live broker scraping
- Paper trade 1 month → go live
