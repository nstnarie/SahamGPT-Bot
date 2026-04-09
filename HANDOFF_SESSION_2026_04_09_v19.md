# SahamGPT-Bot — Session Handoff Document
> Last updated: April 9, 2026 (v19 — Exp 8 REJECTED, Exp 9 queued, 28-ticker scrape Run 1 still in progress)
> Repo: https://github.com/nstnarie/SahamGPT-Bot (public, Python 100%)
> Paste this at the start of a new chat to resume seamlessly.

---

## ⚠️ CLAUDE: READ THIS BEFORE DOING ANYTHING

1. **Read `DEVELOPER_CONTEXT.py` first** — locked rules, hard parameters, architectural decisions.
2. **Never answer workflow questions without reading the actual .yml files first.**
3. **`idx-database` is shared** — `scrape_broker_summary.yml`, `initial_scrape.yml`, `bootstrap_database.yml`, `daily_signals.yml`. **NEVER run in parallel.**
4. **Data loss is unrecoverable.** When in doubt, stop and ask Arie.
5. **Always `git status` + confirm code is pushed before triggering any CI run.**
6. **⚠️ Exp 8 code is still in place** — `BreakoutConfig.breakout_margin_pct = 0.015` in `config.py` and the `breakout_threshold` line in `signal_combiner.py`. **Must be reverted before running Exp 9.**

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

## 2. What Happened This Session (April 9, 2026 — continued)

### Exp 8 — Breakout Margin Filter — REJECTED

**Hypothesis:** Require close ≥ 1.5% above 60-day high. Targets 56% fakeout-reversal signature in 2024 losers (15/27 trades: entered breakout, stopped -3% to -7% within 6–10 days).

**Implementation:**
- `config.py`: added `BreakoutConfig.breakout_margin_pct: float = 0.015`
- `signals/signal_combiner.py` `_add_breakout_signals()`: changed `close > high_Nd` to `close > high_Nd * (1 + breakout_margin_pct)`
- Commit: `19d847f` on feature/v10-experiments

**Results:**
| Metric | 2024 Baseline | 2024 Exp 8 | 2025 Baseline | 2025 Exp 8 |
|--------|:---:|:---:|:---:|:---:|
| Total Return | -6.05% | **-8.06%** ❌ | +14.55% | **+2.79%** ❌ |
| Trades | 42 | 30 | 41 | 31 |
| Win Rate | 35.7% | 33.3% | 41.5% | 32.3% |
| Profit Factor | 0.47 | 0.23 | 2.52 | 1.32 |
| Max Drawdown | -6.76% | -8.70% | -3.37% | -3.12% |
| Sharpe | -2.13 | -2.62 | 1.11 | -0.53 |
| Run ID | 24171380283 | 24177676602 | 24171709463 | 24177677897 |

**Why it failed — three distinct failure modes:**

1. **Removed slow-building 2025 winners.** PTRO +45%+14.5% (two legs), DSSA +24.7%, GGRM +14.8%+15.5% — all gone. These stocks grind through resistance over hours, not gap up 1.5% instantly. The 1.5% margin penalises gradual breakouts.

2. **Freed cluster slots → worse replacement trades.** When the margin blocks an early trade, the cluster limit (max 5 in 10 days) opens a slot for a later trade. In 2024 this brought in **TPIA -13.1%** (emergency stop on day 1 — gap-down). In 2025: **AKRA -13.1%**, **BFIN -6.8%**, **BIRD -4.4%**. Reshuffling the entry schedule substituted neutral-to-good trades with worse ones.

3. **2024 fakeout pattern is a regime problem, not an entry precision problem.** Breakouts fire correctly, but the 2024 bear market provides zero follow-through. A fixed entry margin cannot fix zero follow-through. Exp 2 (IHSG regime gate) already addresses this at the macro level.

**Status: REJECTED.** `BreakoutConfig.breakout_margin_pct = 0.015` remains in `config.py` and `breakout_threshold` logic remains in `signal_combiner.py`. **Must be reverted before Exp 9.**

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
- `signals/signal_combiner.py`: gates BUY on `ihsg_entry_ok` (Exp 2); contains Exp 8 breakout_threshold (rejected — must revert); contains Exp 11 wiring (rejected — gated by config flag)
- `backtest/engine.py`: cooldown on `STOP_LOSS OR TREND_EXIT` (Exp 4); passes `stock_sectors` to signal combiner
- `signals/sector_regime.py`: NEW — `SectorRegimeFilter` for Exp 11 (rejected)
- `scraper/price_scraper.py`: `TICKER_SECTORS` dict (yfinance-sourced, fallback for CI)
- `main_backtest.py`: falls back to `TICKER_SECTORS` when DB has no sector data
- `config.py`: `exp11_sector_filter_enabled: bool = True` (must be False before merge), `BreakoutConfig.breakout_margin_pct = 0.015` (must be reverted/removed before Exp 9)

### Before running Exp 9
1. Revert `is_breakout` condition in `signals/signal_combiner.py` from `close > breakout_threshold` back to `close > high_Nd`
2. Remove or zero out `breakout_margin_pct` from `config.py`
3. Confirm `git status` clean and pushed before triggering CI

### Before merging feature → main
- Set `exp11_sector_filter_enabled: bool = False` in `config.py`
- Remove Exp 8 breakout margin residue from `config.py` and `signal_combiner.py`

---

## 5. Database State

- **broker_summary:** 2,071,251 records, 2024-01-02 → 2025-12-30 (109 original tickers)
- **28 new tickers:** scrape in progress — Run 1 (2024-Q1) triggered but still in_progress at session end
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

Run 1 was still `in_progress` at session end (run 24173626928). Check status first. Complete Runs 2–8 sequentially:

| Run | start_date | end_date | Status |
|-----|-----------|----------|--------|
| 1 | 2024-01-01 | 2024-03-31 | 🔄 Check status — may be complete |
| 2 | 2024-04-01 | 2024-06-30 | ⬜ Pending |
| 3 | 2024-07-01 | 2024-09-30 | ⬜ Pending |
| 4 | 2024-10-01 | 2024-12-31 | ⬜ Pending |
| 5 | 2025-01-01 | 2025-03-31 | ⬜ Pending |
| 6 | 2025-04-01 | 2025-06-30 | ⬜ Pending |
| 7 | 2025-07-01 | 2025-09-30 | ⬜ Pending |
| 8 | 2025-10-01 | 2025-12-31 | ⬜ Pending |

Tickers for all runs: `AADI,ADMR,BREN,BRIS,CUAN,DEWA,PANI,PSAB,RAJA,RATU,WIFI,ADHI,AGRO,AMAN,ARGO,ARTO,ASSA,AVIA,BNBA,DOID,ENRG,IMAS,KRAS,POWR,SMBR,SMDR,WIIM,INET`
Use `tickers=` override field (not `batch=`). After all 8: `initial_scrape.yml` → `export_summary.yml` → `update_split_files.yml`.

### ⚠️ NEXT EXPERIMENT — Exp 9: Early No-Follow-Through Exit

**Hypothesis:** If price doesn't achieve +1% gain at any point by day 8 post-entry, exit. Targets the fakeout-reversal pattern on the EXIT side: slow bleeds that eventually hit the -7% stop on day 6-10. Cut them early before the stop fires.

**Why this should work:**
- 2024 losers show "entered breakout → no follow-through → stopped at -3% to -7% on days 6–10"
- 2025 monster winners (TINS +118%, EMTK +77%, PTRO +45%) all showed immediate follow-through — day 1 or 2 they were already up
- An exit at day 8 with no gain would convert many -5% to -7% stops into smaller -2% to -3% exits
- Should not materially affect 2025 big winners

**Implementation location:** `backtest/portfolio.py` — add check in the daily position update loop: if `holding_days >= 8` and `max_price_since_entry < entry_price * 1.01`, exit at market.

**Before implementing:** revert Exp 8 code in `signals/signal_combiner.py` and `config.py` first.

---

## 8. Full v10 Experiment List (Ranked by Expected Impact)

### TIER 1 — Highest Impact
| Rank | # | Experiment | Status |
|:---:|:---:|---|---|
| 1 | **11** | ~~Sector Cohort Momentum Filter~~ | ❌ **REJECTED** (Apr 9) — yfinance labels too noisy |
| 2 | **8** | ~~Breakout Margin Filter (close ≥ 1.5% above 60d high)~~ | ❌ **REJECTED** (Apr 9) — blunt, reshuffles trades |
| 3 | **9** | Early No-Follow-Through Exit (no +1% by day 8) | ⏸ **NEXT** |

### TIER 2 — Medium Impact
| Rank | # | Experiment | Status |
|:---:|:---:|---|---|
| 4 | **2** | IHSG Market Filter | ✅ ACCEPTED — re-test on full data |
| 5 | **4** | Post-TREND_EXIT Cooldown 30d | ✅ ACCEPTED — re-test on full data |
| 6 | **12** | Consecutive Loss Throttle (3 losses → max 2 entries for 10d) | ⬜ New |
| 7 | **7** | Financial Sector Entry Limit | ❌ REJECTED — re-test with 2024 data |

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
| Exp 11 2024 (sector filter, REJECTED) | 24176911049 |
| Exp 11 2025 (sector filter, REJECTED) | 24176912534 |
| **Exp 8 2024** (breakout margin, REJECTED) | 24177676602 |
| **Exp 8 2025** (breakout margin, REJECTED) | 24177677897 |
| 28-ticker scrape Run 1 (2024-Q1, main) | 24173626928 |
