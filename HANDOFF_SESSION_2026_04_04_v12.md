# SahamGPT-Bot — Session Handoff Document
> Last updated: April 4, 2026 (v12 — Exp 1 rejected, Exp 2 accepted, Exp 3 rejected. 4a/4b on hold until integration + scraper done)
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

---

## 2. What Happened This Session (April 4, 2026)

### GitHub Actions re-run confirmed v9
- Run ID: 23958174058 — `2025-01-01 to 2025-12-31`, `--real-broker`
- Results identical to local v9 baseline. Code on GitHub is current and correct.
- Trade log downloaded locally: `reports/latest/trade_log.csv`

### 2024 Broker Data Backfill — STARTED
- Run ID: 23958438367 — `scrape_broker_summary.yml`
- Parameters: `start_date=2024-01-01`, `end_date=2024-03-01`, `batch=1` (tickers 1–25)
- Status: triggered, running as of session end
- **Stockbit token was valid at time of trigger** — refresh before next batch

### Safety decision made this session
- User wanted to run backtest and scraper simultaneously — confirmed NOT safe
- Both touch `idx-database` artifact; `run_backtest.yml` uploads `if: always()` with `overwrite: true`
- Race condition: last workflow to finish overwrites the other's data
- Decision: backtest first → completed → then scraper triggered

### Experiment 3 — REJECTED (FF magnitude filter)
- Run ID: 23982978951 — `feature/v10-experiments`, `2025-01-01 to 2025-12-31`, `--real-broker`
- Result: 43 trades | 39.5% WR | PF **2.25** | +Rp 134M | DD -3.39% | Calmar 4.17 | Sharpe 0.96
- vs Exp 2 baseline: PF -0.08, WR -1pp, return -Rp 3M, Sharpe -0.06, Calmar -0.15 — all declined
- Existing count+trend checks already capture FF quality adequately. Magnitude multiplier adds noise. Reverted.

### Experiment 2 — ACCEPTED (IHSG market filter)
- Run ID: 23982879523 — `feature/v10-experiments`, `2025-01-01 to 2025-12-31`, `--real-broker`
- Result: 42 trades | 40.5% WR | PF **2.33** | +Rp 137M | DD -3.39% | Calmar 4.32 | Sharpe 1.02
- vs v9: PF +0.19, WR +2.7pp, return +Rp 10M, Sharpe +0.13, Calmar +0.16. Trades 45→42.
- DD marginally worse (-3.28%→-3.39%) — noise level, not a concern.
- Code: `market_regime.py` computes `ihsg_entry_ok`; `signal_combiner.py` gates BUY on it.
- **This is the new feature-branch baseline.**

### Experiment 1 — REJECTED (emergency stop -12% → -10%)
- Run ID: 23982773904 — `feature/v10-experiments`, `2025-01-01 to 2025-12-31`, `--real-broker`
- Result: 45 trades | 37.8% WR | PF **1.88** | +Rp 111M | DD -3.81% | Calmar 3.11
- vs v9: PF -0.26, return -Rp 16M, DD worse, Calmar -1.05 — all metrics declined
- Learning: -10% stop clips winners that dip temporarily during the 5-day hold period. -12% is correctly calibrated.
- Config reverted to `emergency_stop_pct=0.12` on the feature branch.

### feature/v10-experiments branch — CREATED
- Branch pushed to `origin/feature/v10-experiments`
- **Why:** 2024 broker summary scraper is running. All v10 code experiments must live in this branch. Nothing experimental touches `main` or the shared `idx-database` artifact until the scraper completes.
- **Workflow change:** `run_backtest.yml` — "Save database" step now has `if: always() && github.ref == 'refs/heads/main'`. On the feature branch, the workflow downloads (reads) `idx-database` but never uploads/overwrites it. Main branch retains full read+write behaviour.
- **How to trigger backtest on the branch:** GitHub Actions → Run Backtest → "Run workflow" dropdown → switch branch to `feature/v10-experiments` → fill inputs → Run. Or via CLI: `gh workflow run run_backtest.yml --ref feature/v10-experiments -f start_date=... -f end_date=... -f capital=1000000000 -f real_broker=true`

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

---

## 5. Database State (as of April 4, 2026)

- **broker_summary 2025:** 1,043,576 records, 2025-01-02 to 2025-12-31, 109 tickers ✅
- **broker_summary 2024:** batch 1 in progress (2024-01-01→2024-03-01, tickers 1–25)
- **daily_prices:** 107 tickers, 2021-01-01 to 2026-03-28

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
Q1 2024:
  ✅ batch 1 triggered (2024-01-01→2024-03-01, tickers 1–25)
  ⬜ batch 2 (2024-01-01→2024-03-01, tickers 26–50)
  ⬜ batch 3 (2024-01-01→2024-03-01, tickers 51–75)
  ⬜ batch 4 split: Jan 1–Feb 15 | Feb 15–Mar 31 (tickers 76+)
Q2 2024: batch1 → batch2 → batch3 → batch4 (Apr 1–May 15) → batch4 (May 15–Jun 30)
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
⚠️ **One experiment per session. Backtest → compare vs v9 baseline → accept/reject → document → next.**

v9 baseline: 45 trades | 37.8% WR | PF 2.14 | +Rp 127M | DD -3.28% | Calmar 4.16
**Current baseline (post Exp 2): 42 trades | 40.5% WR | PF 2.33 | +Rp 137M | DD -3.39% | Calmar 4.32**

| # | Experiment | File(s) to change | Hypothesis |
|---|------------|-------------------|------------|
| ~~1~~ | ~~Emergency stop -12% → -10%~~ | ~~`config.py:137`~~ | **REJECTED (2026-04-04, run 23982773904).** PF 2.14→1.88, return -Rp 16M, DD worse. -10% clips recovering winners. -12% stays. |
| ~~2~~ | ~~IHSG market filter (close > MA20, daily > -1%)~~ | ~~`signals/market_regime.py`, `signals/signal_combiner.py`~~ | **ACCEPTED (2026-04-04, run 23982879523).** PF 2.14→2.33, WR +2.7pp, return +Rp 10M, Sharpe 0.89→1.02. New baseline. |
| ~~3~~ | ~~FF magnitude: require 5-day sum > 1.5x 20-day avg absolute flow~~ | ~~`signals/signal_combiner.py`~~ | **REJECTED (2026-04-04, run 23982978951).** PF 2.33→2.25, WR -1pp, Sharpe -0.06. Existing count+trend checks sufficient. Reverted. |
| 4a | Support/resistance detection + break-below exit | `signals/signal_combiner.py`, `backtest/portfolio.py` | Historical price clusters identify structural support. Breaking below → stronger exit signal than time/stop. **ON HOLD — do after integration.** |
| 4b | Averaging up on resistance break | `backtest/engine.py`, `backtest/portfolio.py` | If stock breaks next resistance level while held, add to position. Only attempt after 4a. **ON HOLD.** |

After each experiment:
- Update `DEVELOPER_CONTEXT.py` with result and learning
- Update this handoff doc with the new baseline (if accepted)
- Mark experiment complete in the table above

### INTEGRATION — NEXT STEP (do before 4a/4b)
⚠️ **Only after the 2024 broker scraper is fully complete** (all batches Q1–Q4 done + split files updated).
- Merge `feature/v10-experiments` → `main` via PR (Exp 2 IHSG filter is the only accepted change)
- Run `run_backtest.yml` from main to confirm baseline is stable post-merge
- Then tackle 4a/4b on a fresh branch

**Why 4a/4b must wait:**
1. Both touch `backtest/portfolio.py` and `backtest/engine.py` — core simulation logic, much larger blast radius than entry filters
2. The scraper is still running → merging to main is blocked → no point doing more experiments on the feature branch that can't be validated from main yet
3. 4b depends on 4a being accepted first — two-step dependency

### AFTER INTEGRATION
- Integrate accepted v10 changes into live path (`main_daily.py → signal_combiner.py`)
- Update `daily_signals.yml` with live broker scraping
- Paper trade 1 month → go live
