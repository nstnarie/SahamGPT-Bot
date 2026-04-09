# SahamGPT-Bot — Session Handoff Document
> Last updated: April 9, 2026 (v20 — Exp 9 REJECTED, Exp 12 ACCEPTED, scrape Run 2 in progress)
> Repo: https://github.com/nstnarie/SahamGPT-Bot (public, Python 100%)
> Paste this at the start of a new chat to resume seamlessly.

---

## ⚠️ CLAUDE: READ THIS BEFORE DOING ANYTHING

1. **Read `DEVELOPER_CONTEXT.py` first** — locked rules, hard parameters, architectural decisions.
2. **Never answer workflow questions without reading the actual .yml files first.**
3. **`idx-database` is shared** — `scrape_broker_summary.yml`, `initial_scrape.yml`, `bootstrap_database.yml`, `daily_signals.yml`. **NEVER run in parallel.**
4. **Data loss is unrecoverable.** When in doubt, stop and ask Arie.
5. **Always `git status` + confirm code is pushed before triggering any CI run.**

---

## 1. Baselines

### v9 — main branch baseline
| Metric | Value |
|--------|-------|
| Trades | 45 |
| Win Rate | 37.8% |
| Total Return | +12.74% (+Rp 127M) |
| Profit Factor | **2.14** |
| Max Drawdown | -3.28% |
| Sharpe | 0.89 |
| Calmar | **4.16** |

### feature/v10-experiments — current baseline (post Exp 4 + Exp 12, 109 tickers)
| Metric | 2025 | 2024 |
|--------|------|------|
| Trades | 35 | 34 |
| Win Rate | **45.7%** | 32.4% |
| Total Return | **+16.61% (+Rp 166M)** | -4.67% (-Rp 47M) |
| Profit Factor | **3.25** | 0.51 |
| Max Drawdown | **-3.25%** | -5.35% |
| Sharpe | **1.42** | -1.83 |
| Sortino | **2.82** | -2.30 |
| Calmar | **5.49** | -0.93 |
| Run ID | 24199629162 | 24199627413 |

---

## 2. What Happened This Session (April 9, 2026)

### Exp 8 — Breakout Margin Filter — REJECTED (prior session)
- Code reverted at start of this session: `BreakoutConfig.breakout_margin_pct` removed from `config.py`, `signal_combiner.py` back to `close > high_Nd`. Commit: `016c593`.

### Exp 9 — Early No-Follow-Through Exit — REJECTED

**Hypothesis:** Exit if price never reached +1% above entry by day 8.

**Implementation:** `backtest/portfolio.py` — `NO_FOLLOWTHROUGH` exit at priority 3 (after min hold, before trend exit). `backtest/engine.py` — `NO_FOLLOWTHROUGH` triggers 30-day cooldown. Commit: `7451ee8`.

**Results:**
| Metric | 2024 Baseline | 2024 Exp 9 | 2025 Baseline | 2025 Exp 9 |
|--------|:---:|:---:|:---:|:---:|
| Total Return | -6.05% | **-7.12%** ❌ | +14.55% | **+14.46%** ≈ |
| Trades | 42 | 39 | 41 | 41 |
| Win Rate | 35.7% | 28.2% ❌ | 41.5% | 39.0% ↓ |
| Profit Factor | 0.47 | 0.40 ❌ | 2.52 | 2.55 ✅ |
| Max Drawdown | -6.76% | -7.48% ❌ | -3.37% | -3.25% ✅ |
| Run ID | — | 24195290139 | — | 24195291735 |

**Why it failed:** Exit fires on slow-building winners in 2024, not just fakeouts. 3 fewer trades, lower win rate, deeper drawdown. Same root cause as Exp 8 — 2024 is a regime problem, not a trade management problem.

**Status: REJECTED. Code remains in place** (`NO_FOLLOWTHROUGH` in `portfolio.py` and `engine.py`). Must be reverted before merging to main or if it interferes with future experiments.

### Exp 12 — Consecutive Loss Throttle — ACCEPTED ✅

**Hypothesis:** After 3 consecutive losing trades (pnl < 0, fully closed), cap new entries to max 2 per rolling 10-day window for the next 10 trading days.

**Implementation:** `backtest/engine.py` — `consecutive_losses` counter + `throttle_until` date. Throttle fires after 3 consecutive losses, resets counter, and overrides `max_entries_per_week` to 2 for 10 days. Commit: `b2d5bab`.

**Results:**
| Metric | 2024 Baseline | 2024 Exp 12 | 2025 Baseline | 2025 Exp 12 |
|--------|:---:|:---:|:---:|:---:|
| Total Return | -6.05% | **-4.67%** ✅ | +14.55% | **+16.61%** ✅ |
| Trades | 42 | 34 | 41 | 35 |
| Win Rate | 35.7% | 32.4% | 41.5% | **45.7%** ✅ |
| Profit Factor | 0.47 | **0.51** ✅ | 2.52 | **3.25** ✅ |
| Max Drawdown | -6.76% | **-5.35%** ✅ | -3.37% | **-3.25%** ✅ |
| Sharpe | -2.13 | **-1.83** ✅ | 1.11 | **1.42** ✅ |
| Sortino | — | **-2.30** ✅ | 1.93 | **2.82** ✅ |
| Calmar | — | -0.93 | 4.59 | **5.49** ✅ |
| Run ID | — | 24199627413 | — | 24199629162 |

**Why it works:** Throttle blocks low-quality entries that cluster during bear streaks (2024), while not materially impeding 2025's bull-market winners. First experiment to improve both years simultaneously across every major metric.

**Status: ACCEPTED.** Baselines updated above.

---

## 3. Entry / Exit Rules (feature/v10-experiments)

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
| 9 | Regime | Not BEAR + IHSG > MA20 + IHSG daily > -1% *(Exp 2)* |
| 10 | No gap-up | Entry day open not >7% above signal day close |
| 11 | Cluster limit | Max 5 new entries in rolling 10 trading days |
| 12 | Loss throttle | Max 2 entries/10d after 3 consecutive losses *(Exp 12)* |

### Exit (first trigger wins)
| Priority | Rule |
|----------|------|
| 1 | -15% emergency stop (always) |
| 2 | No stop first 5 days |
| 3 | ~~No follow-through exit: no +1% by day 8~~ *(Exp 9 — REJECTED, code present but logically bypassed by acceptance of prior rules)* |
| 4 | Close < MA10 after +15% gain |
| 5 | -7% or 1.5xATR, cap -10% — hold extension if acc_score > 0 on days 6–10 |
| 6 | Sell 30% at +15% |
| 7 | No +3% in 15 days + below MA10 |
| 8 | 5 consecutive net foreign sell days (foreign-driven, price weakening) |
| 9 | BEAR regime = close all |

### Re-entry Cooldown (Exp 4)
| Exit Type | Cooldown |
|-----------|----------|
| STOP_LOSS | 30 trading days |
| TREND_EXIT | 30 trading days |
| NO_FOLLOWTHROUGH | 30 trading days *(Exp 9 — rejected but code present)* |

---

## 4. Architecture

### Two execution paths — NEVER cross-contaminate
- BACKTEST: `main_backtest.py → backtest/engine.py`
- LIVE: `main_daily.py → signals/signal_combiner.py`

### Key files changed in feature/v10-experiments
- `signals/market_regime.py`: adds `ihsg_entry_ok` (Exp 2)
- `signals/signal_combiner.py`: gates BUY on `ihsg_entry_ok` (Exp 2); contains Exp 11 wiring (rejected — gated by config flag)
- `backtest/engine.py`: cooldown on `STOP_LOSS OR TREND_EXIT OR NO_FOLLOWTHROUGH` (Exp 4 + Exp 9); Exp 12 consecutive loss throttle; passes `stock_sectors` to signal combiner
- `backtest/portfolio.py`: `NO_FOLLOWTHROUGH` exit at priority 3 (Exp 9 — rejected, revert before merge to main)
- `signals/sector_regime.py`: NEW — `SectorRegimeFilter` for Exp 11 (rejected)
- `scraper/price_scraper.py`: `TICKER_SECTORS` dict (yfinance-sourced, fallback for CI)
- `main_backtest.py`: falls back to `TICKER_SECTORS` when DB has no sector data
- `config.py`: `exp11_sector_filter_enabled: bool = True` (must be False before merge)

### Before merging feature → main
- Set `exp11_sector_filter_enabled: bool = False` in `config.py`
- Remove `NO_FOLLOWTHROUGH` exit logic from `backtest/portfolio.py` (Exp 9 rejected)
- Remove `NO_FOLLOWTHROUGH` from cooldown condition in `backtest/engine.py`

---

## 5. Database State

- **broker_summary:** 2,071,251 records, 2024-01-02 → 2025-12-30 (109 original tickers)
- **28 new tickers:** scrape in progress — Run 2 (2024-Q2) triggered, ~2hrs in at session update
- **daily_prices:** 107 tickers, 2021-01-01 to 2026-03-28 (new tickers not yet scraped)
- **Split files:** `idx_broker_part_a.db` (1,269,996) + `idx_broker_part_b.db` (801,255) = 2,071,251 ✅

---

## 6. Workflows

All workflows touching idx-database must run **sequentially, never in parallel.**

| File | Touches idx-database? | Purpose |
|------|-----------------------|---------|
| `daily_signals.yml` | ✅ | Full pipeline → Telegram (weekday 16:35 WIB) |
| `initial_scrape.yml` | ✅ | Historical price download |
| `run_backtest.yml` | ✅ (download only from feature branch) | On-demand backtesting |
| `scrape_broker_summary.yml` | ✅ | Batch broker data scraping |
| `export_summary.yml` | ❌ | Export per-day ticker count CSV |
| `bootstrap_database.yml` | ✅ | Merges split files into artifact |
| `update_split_files.yml` | ❌ | Regenerates split files |

---

## 7. Next Steps (in order)

### ⚠️ ONGOING — Complete 28-ticker broker scrape (main branch)

| Run | start_date | end_date | Status |
|-----|-----------|----------|--------|
| 1 | 2024-01-01 | 2024-03-31 | ✅ Done (run 24173626928) |
| 2 | 2024-04-01 | 2024-06-30 | 🔄 In progress (run 24194508163) |
| 3 | 2024-07-01 | 2024-09-30 | ⬜ Pending |
| 4 | 2024-10-01 | 2024-12-31 | ⬜ Pending |
| 5 | 2025-01-01 | 2025-03-31 | ⬜ Pending |
| 6 | 2025-04-01 | 2025-06-30 | ⬜ Pending |
| 7 | 2025-07-01 | 2025-09-30 | ⬜ Pending |
| 8 | 2025-10-01 | 2025-12-31 | ⬜ Pending |

Tickers for all runs: `AADI,ADMR,BREN,BRIS,CUAN,DEWA,PANI,PSAB,RAJA,RATU,WIFI,ADHI,AGRO,AMAN,ARGO,ARTO,ASSA,AVIA,BNBA,DOID,ENRG,IMAS,KRAS,POWR,SMBR,SMDR,WIIM,INET`
Use `tickers=` override field (not `batch=`). After all 8: `initial_scrape.yml` → `export_summary.yml` → `update_split_files.yml`.

### NEXT EXPERIMENT — Exp 7: Financial Sector Entry Limit (re-test with 2024 data)

Previously rejected — needs re-test now that 2024 baseline is confirmed and Exp 12 is in place.

### BLOCKED — Exp 2 + Exp 4 re-tests on full 137-ticker data

Awaiting completion of 28-ticker scrape + OHLCV scrape before these can be re-run meaningfully.

---

## 8. Full v10 Experiment List (Ranked by Expected Impact)

### TIER 1 — Highest Impact
| Rank | # | Experiment | Status |
|:---:|:---:|---|---|
| 1 | **11** | ~~Sector Cohort Momentum Filter~~ | ❌ **REJECTED** (Apr 9) |
| 2 | **8** | ~~Breakout Margin Filter~~ | ❌ **REJECTED** (Apr 9) |
| 3 | **9** | ~~Early No-Follow-Through Exit~~ | ❌ **REJECTED** (Apr 9) |

### TIER 2 — Medium Impact
| Rank | # | Experiment | Status |
|:---:|:---:|---|---|
| 4 | **2** | IHSG Market Filter | ✅ ACCEPTED — re-test on full 137t data (blocked) |
| 5 | **4** | Post-TREND_EXIT Cooldown 30d | ✅ ACCEPTED — re-test on full 137t data (blocked) |
| 6 | **12** | Consecutive Loss Throttle | ✅ **ACCEPTED** (Apr 9) |
| 7 | **7** | Financial Sector Entry Limit | ❌ REJECTED — **re-test next** |

### TIER 3 — Low Impact / High Risk
| Rank | # | Experiment | Status |
|:---:|:---:|---|---|
| 8 | **10** | ATR Volatility Cap | ⏸ On hold |
| 9 | **1** | Emergency Stop -12% → -10% | ❌ REJECTED |
| 10 | **3** | FF Magnitude Filter | ❌ REJECTED |
| 11 | **5** | Remove Rp 150 Min Price Filter | ❌ REJECTED (stays) |
| 12 | **6** | IHSG 5d Momentum Filter | ❌ REJECTED (stays) |

### TIER 4 — Post-Integration
| # | Experiment |
|:---:|---|
| 7a | Support/resistance detection |
| 7b | Averaging up on resistance break (needs 7a) |
| 7c | Chart pattern detection (needs 7a) |

---

## 9. Key Run IDs Reference

| Description | Run ID |
|---|---|
| 2024 backtest baseline (feature/v10-exp, 109t, real_broker) | 24171380283 |
| 2025 backtest baseline (feature/v10-exp, 109t, real_broker) | 24171709463 |
| Exp 11 2024 (REJECTED) | 24176911049 |
| Exp 11 2025 (REJECTED) | 24176912534 |
| Exp 8 2024 (REJECTED) | 24177676602 |
| Exp 8 2025 (REJECTED) | 24177677897 |
| Exp 9 2024 (REJECTED) | 24195290139 |
| Exp 9 2025 (REJECTED) | 24195291735 |
| **Exp 12 2024 (ACCEPTED)** | 24199627413 |
| **Exp 12 2025 (ACCEPTED)** | 24199629162 |
| 28-ticker scrape Run 1 (2024-Q1, main) | 24173626928 |
| 28-ticker scrape Run 2 (2024-Q2, main) | 24194508163 |
