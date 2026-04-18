# SahamGPT-Bot — Session Handoff Document
> Last updated: April 9, 2026 (v21 — All Tier 1-3 experiments complete, awaiting 137t data + merge)
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

## 1. Current Baselines (feature/v10-experiments, post Exp 4 + Exp 12, 109 tickers)

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

### v9 main branch baseline (reference)
45 trades | 37.8% WR | PF 2.14 | +12.74% (+Rp 127M) | DD -3.28% | Sharpe 0.89 | Calmar 4.16

---

## 2. Complete Experiment Results (all Tier 1–3 tested April 2026)

### ACCEPTED (3 experiments active in feature/v10-experiments)

| # | Experiment | 2024 Δ | 2025 Δ | Key finding |
|:---:|---|---|---|---|
| **2** | IHSG Market Filter | baseline | +Rp 10M, PF +0.19 | Gates entries on IHSG < MA20 or daily < -1% |
| **4** | Post-TREND_EXIT Cooldown 30d | baseline | PF +0.17, Calmar +0.27 | Prevents EMTK re-entry trap |
| **12** | Consecutive Loss Throttle | -4.67% vs -6.05% ✅ | +16.61% vs +14.55% ✅ | **Only exp to improve both years** |

### REJECTED (9 experiments)

| # | Experiment | Why rejected |
|:---:|---|---|
| 1 | Emergency Stop -12%→-10% | Clips winners during 5d hold. PF 2.14→1.88 |
| 3 | FF Magnitude Filter | Adds noise, PF decline on 2025 data |
| 5 | Remove Rp 150 Min Price | Sub-Rp150 stocks hit emergency stop immediately |
| 6 | IHSG 5d Momentum Filter | Blocks best breakouts (start of recovery, 5d still negative) |
| 7 | Financial Sector Limit | Never fires — Exp 12 throttle already blocks FS clustering |
| 8 | Breakout Margin ≥1.5% | Reshuffles trades; removed slow-building 2025 winners |
| 9 | Early No-Follow-Through Exit | Cuts slow-building 2024 winners; regime problem not trade mgmt |
| 10 | ATR Volatility Cap 7% | High ATR in 2024 bear = normal; removed winners not losers |
| 11 | Sector Cohort Momentum | yfinance labels too noisy for IDX cohort construction |

---

## 3. Codebase State (feature/v10-experiments, HEAD: 20e9967)

### Active code (accepted experiments)
- `signals/market_regime.py`: `ihsg_entry_ok` gate (Exp 2)
- `signals/signal_combiner.py`: gates BUY on `ihsg_entry_ok` (Exp 2); Exp 11 wiring present but gated by config flag
- `backtest/engine.py`: 30d cooldown on `STOP_LOSS OR TREND_EXIT OR NO_FOLLOWTHROUGH`; Exp 12 consecutive loss throttle (`consecutive_losses`, `throttle_until`)
- `backtest/portfolio.py`: `NO_FOLLOWTHROUGH` exit at priority 3 (Exp 9 — REJECTED, must remove before merge)

### Cleanup required before merging feature → main
1. **`config.py`**: set `exp11_sector_filter_enabled = False`
2. **`backtest/portfolio.py`**: remove `NO_FOLLOWTHROUGH` exit block (Exp 9, rejected)
3. **`backtest/engine.py`**: remove `NO_FOLLOWTHROUGH` from cooldown condition
4. Verify `git status` clean, then trigger `run_backtest.yml` from main to confirm

### Two execution paths — NEVER cross-contaminate
- BACKTEST: `main_backtest.py → backtest/engine.py`
- LIVE: `main_daily.py → signals/signal_combiner.py`

---

## 4. Entry / Exit Rules (feature/v10-experiments, as-accepted)

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
| 9 | Regime | IHSG > MA20 + IHSG daily > -1% *(Exp 2)* |
| 10 | No gap-up | Entry day open not >7% above signal day close |
| 11 | Cluster limit | Max 5 new entries in rolling 10 trading days |
| 12 | Loss throttle | Max 2 entries/10d after 3 consecutive losses *(Exp 12)* |

### Exit (first trigger wins)
| Priority | Rule |
|----------|------|
| 1 | -15% emergency stop (always) |
| 2 | No stop first 5 days |
| 3 | Close < MA10 after +15% gain (trend exit) |
| 4 | -7% or 1.5xATR, cap -10% — hold extension if acc_score > 0 on days 6–10 |
| 5 | Sell 30% at +15% |
| 6 | No +3% in 15 days + below MA10 |
| 7 | 5 consecutive net foreign sell days (foreign-driven, price weakening) |
| 8 | BEAR regime = close all |

### Re-entry Cooldown
| Exit Type | Cooldown |
|-----------|----------|
| STOP_LOSS | 30 trading days |
| TREND_EXIT | 30 trading days |

---

## 5. Database State

- **broker_summary:** 2,071,251 records, 2024-01-02 → 2025-12-30 (109 original tickers)
- **28 new tickers:** scrape in progress — Run 2 (2024-Q2, run 24194508163) was running at session end; check status first
- **daily_prices:** 107 tickers, 2021-01-01 to 2026-03-28
- **Split files:** `idx_broker_part_a.db` (1,269,996) + `idx_broker_part_b.db` (801,255) = 2,071,251 ✅

---

## 6. Next Steps (in order)

### Step 1 — Complete 28-ticker broker scrape (main branch)

| Run | Period | Status |
|-----|--------|--------|
| 1 | 2024-Q1 | ✅ Done (24173626928) |
| 2 | 2024-Q2 | 🔄 Check status (24194508163) |
| 3 | 2024-Q3 | ⬜ Pending |
| 4 | 2024-Q4 | ⬜ Pending |
| 5 | 2025-Q1 | ⬜ Pending |
| 6 | 2025-Q2 | ⬜ Pending |
| 7 | 2025-Q3 | ⬜ Pending |
| 8 | 2025-Q4 | ⬜ Pending |

Tickers: `AADI,ADMR,BREN,BRIS,CUAN,DEWA,PANI,PSAB,RAJA,RATU,WIFI,ADHI,AGRO,AMAN,ARGO,ARTO,ASSA,AVIA,BNBA,DOID,ENRG,IMAS,KRAS,POWR,SMBR,SMDR,WIIM,INET`
Use `tickers=` override (not `batch=`). Run sequentially, one at a time.

After all 8 broker runs complete:
- `initial_scrape.yml` — OHLCV for 28 new tickers
- `export_summary.yml` → `update_split_files.yml`

### Step 2 — Re-test Exp 2 + Exp 4 on full 137-ticker dataset
Run `run_backtest.yml` from `feature/v10-experiments`, 2024 + 2025, `real_broker=true`.
Confirm both still accepted with full universe.

### Step 3 — Cleanup + merge
Apply cleanup listed in section 3, then merge `feature/v10-experiments` → `main`.

### ⚠️ Context: Arie is starting an analysis session
Arie is planning a framework analysis (likely Opus on claude.ai) to discuss whether the strategy needs deeper redesign. All v10 experiments may be re-run after that discussion. Do not start merge until Arie confirms the framework design is settled.

---

## 7. Key Run IDs Reference

| Description | Run ID |
|---|---|
| 2024 backtest original baseline (109t) | 24171380283 |
| 2025 backtest original baseline (109t) | 24171709463 |
| **Exp 12 2024 (current baseline, ACCEPTED)** | 24199627413 |
| **Exp 12 2025 (current baseline, ACCEPTED)** | 24199629162 |
| Exp 9 2024 (REJECTED) | 24195290139 |
| Exp 9 2025 (REJECTED) | 24195291735 |
| Exp 7 2024 re-test (REJECTED) | 24200357558 |
| Exp 7 2025 re-test (REJECTED) | 24200358913 |
| Exp 10 2024 (REJECTED) | 24201099244 |
| Exp 10 2025 (REJECTED) | 24201100333 |
| Exp 11 2024 (REJECTED) | 24176911049 |
| Exp 11 2025 (REJECTED) | 24176912534 |
| Exp 8 2024 (REJECTED) | 24177676602 |
| Exp 8 2025 (REJECTED) | 24177677897 |
| 28-ticker scrape Run 1 (2024-Q1) | 24173626928 |
| 28-ticker scrape Run 2 (2024-Q2) | 24194508163 |
