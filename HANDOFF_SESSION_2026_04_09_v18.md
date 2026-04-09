# SahamGPT-Bot — Session Handoff Document
> Last updated: April 9, 2026 (v18 — Exp 11 REJECTED, Exp 8 queued, 28-ticker scrape in progress)
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

### feature/v10-experiments — current baseline (post Exp 4, 2025 only, 109 tickers)
| Metric | Value |
|--------|-------|
| Trades | 41 |
| Win Rate | **41.5%** |
| Total Return | +14.55% (+Rp 145M) |
| Profit Factor | **2.52** |
| Max Drawdown | -3.37% |
| Sharpe | **1.11** |
| Sortino | **1.93** |
| Calmar | **4.59** |

---

## 2. What Happened This Session (April 9, 2026)

### Opus analysis of 2024 vs 2025 trade logs
Downloaded artifacts from runs 24171380283 (2024) and 24171709463 (2025) and ran Opus analysis. Key findings:

**Core insight:** 2024 isn't broken because losses are deeper — avg loss is identical both years (~-5.3%). The problem is the right tail: 2025 had 9 trades >+15% (incl. TINS +118%, EMTK +77%, ANTM +45%); 2024 had only 1 trade above +18% (WIKA). Breakouts fired but follow-through never materialized.

**2024 bear market patterns:**
- 56% of losers (15/27) show "fakeout then reversal" signature: entered breakout, stopped at -3% to -7% within 6–10 days
- 63% of 2024 losers clustered in Aug–Oct 2024 (IHSG sell-off period)
- Hardest hit sectors: Financial Services (~5 losses: BFIN, BBTN×2, BTPS) and Real Estate (~4 losses: DMAS, PWON, SMRA, CTRA)
- Loss rate 70%+ across all entry months → regime issue, not timing issue

### Experiment ranking revised (see Section 5)
Added Exp 11 (Sector Momentum) and Exp 12 (Loss Throttle). Full ranked list produced.

### Exp 11 — Sector Cohort Momentum Filter — REJECTED
- Hypothesis: skip entry when ticker's sector cohort is below its SMA20 (symmetric with Exp 2 IHSG filter)
- Implementation: `signals/sector_regime.py` (new), `signals/signal_combiner.py`, `backtest/engine.py`, `config.py`, `scraper/price_scraper.py` (TICKER_SECTORS fallback), `main_backtest.py`
- Commit: `5b92af8` on feature/v10-experiments

**Results:**
| Metric | 2024 Baseline | 2024 Exp 11 | 2025 Baseline | 2025 Exp 11 |
|--------|:---:|:---:|:---:|:---:|
| Total Return | -6.05% | **-7.77%** ❌ | +14.55% | +14.74% ✅ |
| Trades | 42 | 39 | 41 | 40 |
| Win Rate | 35.7% | 30.8% | 41.5% | 42.5% |
| Profit Factor | 0.47 | 0.38 | 2.52 | 2.57 |
| Max Drawdown | -6.76% | -8.13% | -3.37% | -3.22% |
| Sharpe | -2.13 | -2.59 | 1.11 | 1.13 |
| Run ID | 24171380283 | 24176911049 | 24171709463 | 24176912534 |

**Why it failed:** The filter blocked 6 baseline 2024 trades — some good (TLKM -3.24%, ISAT -1.50%, EXCL -5.43%) but also ICBP +2.08% (winner). Capital freed up flowed into 5 worse trades (MEDC -5.93%, MAPA -8.43%, new INDF entry -4.04%). Blocking one sector just redirected capital into equally bad entries in other sectors.

**Root cause:** yfinance sector labels create noisy cohorts for IDX. The sector groupings are too coarse — TLKM (large-cap telco) and EMTK (volatile mid-cap media) share "Communication Services", diluting each other's cohort signal. The concept is sound but labels need IDX-native GICS classification to work properly. Not worth fixing until Exp 8+9 are validated.

**Status: REJECTED.** `exp11_sector_filter_enabled: bool = True` remains in config but the filter is a no-op on main (live path doesn't pass stock_sectors). Should be set to False before merging feature → main.

### 28-ticker scrape — IN PROGRESS
- Run 1 triggered: [24173626928](https://github.com/nstnarie/SahamGPT-Bot/actions/runs/24173626928)
- **Still in_progress** at end of session (2024-Q1, 28 tickers, main branch)
- Runs 2–8 pending (one per quarter through 2025-Q4)

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

### Re-entry Cooldown (Exp 4)
| Exit Type | Cooldown |
|-----------|----------|
| STOP_LOSS | 30 trading days |
| TREND_EXIT | 30 trading days |

---

## 4. Architecture

### Two execution paths — NEVER cross-contaminate
- BACKTEST: `main_backtest.py → backtest/engine.py`
- LIVE: `main_daily.py → signals/signal_combiner.py`

### Key files changed in feature/v10-experiments (accepted: Exp 2 + Exp 4)
- `signals/market_regime.py`: adds `ihsg_entry_ok` (Exp 2)
- `signals/signal_combiner.py`: gates BUY on `ihsg_entry_ok` (Exp 2); also contains Exp 11 wiring (rejected but code present, gated by config flag)
- `backtest/engine.py`: cooldown on `STOP_LOSS OR TREND_EXIT` (Exp 4); passes `stock_sectors` to signal combiner
- `signals/sector_regime.py`: NEW — `SectorRegimeFilter` for Exp 11 (rejected)
- `scraper/price_scraper.py`: `TICKER_SECTORS` dict (yfinance-sourced, fallback for CI)
- `main_backtest.py`: falls back to `TICKER_SECTORS` when DB has no sector data

### run_backtest.yml from feature branch
Safe while scraper runs — idx-database upload gated: `if: always() && github.ref == 'refs/heads/main'`

### Before merging feature → main
Set `exp11_sector_filter_enabled: bool = False` in `config.py` (Exp 11 rejected, shouldn't activate in live).

---

## 5. Database State

- **broker_summary:** 2,071,251 records, 2024-01-02 → 2025-12-30 (109 original tickers)
- **28 new tickers:** scrape in progress — Run 1 (2024-Q1) triggered, Runs 2–8 pending
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

### ⚠️ IMMEDIATE PRIORITY — Complete 28-ticker broker scrape (main branch)

Run 1 triggered, still running. Complete Runs 2–8 sequentially, one per quarter:

| Run | start_date | end_date | Status |
|-----|-----------|----------|--------|
| 1 | 2024-01-01 | 2024-03-31 | 🔄 IN PROGRESS (run 24173626928) |
| 2 | 2024-04-01 | 2024-06-30 | ⬜ Pending |
| 3 | 2024-07-01 | 2024-09-30 | ⬜ Pending |
| 4 | 2024-10-01 | 2024-12-31 | ⬜ Pending |
| 5 | 2025-01-01 | 2025-03-31 | ⬜ Pending |
| 6 | 2025-04-01 | 2025-06-30 | ⬜ Pending |
| 7 | 2025-07-01 | 2025-09-30 | ⬜ Pending |
| 8 | 2025-10-01 | 2025-12-31 | ⬜ Pending |

Tickers for all runs: `AADI,ADMR,BREN,BRIS,CUAN,DEWA,PANI,PSAB,RAJA,RATU,WIFI,ADHI,AGRO,AMAN,ARGO,ARTO,ASSA,AVIA,BNBA,DOID,ENRG,IMAS,KRAS,POWR,SMBR,SMDR,WIIM,INET`
Use `tickers=` override field (not `batch=`). After all 8 complete: `initial_scrape.yml` → `export_summary.yml` → `update_split_files.yml`.

### ⚠️ NEXT EXPERIMENT — Exp 8: Breakout Margin Filter

**Hypothesis:** Require close ≥ 1.5% above 60-day high (not a 1-tick break). Targets the 56% fakeout-reversal signature in 2024 losers (15/27 trades: entered breakout, stopped -3% to -7% within 6–10 days).

**Implementation location:** `signals/signal_combiner.py` → `_add_breakout_signals()`, change `is_breakout` condition from `close > high_Nd` to `close > high_Nd * (1 + breakout_margin)`. Add `BreakoutConfig.breakout_margin_pct: float = 0.015` to `config.py`.

**Expected impact (from Opus analysis):**
- 2024: ~7–10 fast-fail stops removed, est. +Rp 25–30M
- 2025: Near-zero risk — monster winners (TINS +118%, EMTK +77%, PTRO +45%, ANTM +45%) had explosive day-1 momentum that easily clears 1.5%

**Why 1.5%:** 1% too thin (still catches noise); 2% too aggressive (may exclude genuine large-cap breakouts like BBRI, TLKM, ASII). 1.5% is the sweet spot.

---

## 8. Full v10 Experiment List (Ranked by Expected Impact)

### TIER 1 — Highest Impact
| Rank | # | Experiment | Status |
|:---:|:---:|---|---|
| 1 | **11** | ~~Sector Cohort Momentum Filter~~ | ❌ **REJECTED** (Apr 9, 2026) — yfinance labels too noisy for IDX cohort grouping |
| 2 | **8** | Breakout Margin Filter (close ≥ 1.5% above 60d high) | ⏸ **NEXT** |
| 3 | **9** | Early No-Follow-Through Exit (no +1% by day 8) | ⏸ On hold |

### TIER 2 — Medium Impact
| Rank | # | Experiment | Status |
|:---:|:---:|---|---|
| 4 | **2** | IHSG Market Filter | ✅ ACCEPTED — re-test on full data |
| 5 | **4** | Post-TREND_EXIT Cooldown 30d | ✅ ACCEPTED — re-test on full data |
| 6 | **12** | Consecutive Loss Throttle (3 losses → max 2 entries for 10d) | ⬜ New |
| 7 | **7** | Financial Sector Entry Limit | ❌ REJECTED — likely superseded by Exp 11 concept; re-test |

### TIER 3 — Low Impact / High Risk
| Rank | # | Experiment | Status |
|:---:|:---:|---|---|
| 8 | **10** | ATR Volatility Cap *(reframe: 7% threshold or regime-conditional)* | ⏸ On hold |
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
| **Exp 11 2024** (sector filter, REJECTED) | 24176911049 |
| **Exp 11 2025** (sector filter, REJECTED) | 24176912534 |
| 28-ticker scrape Run 1 (2024-Q1, main) | 24173626928 |
