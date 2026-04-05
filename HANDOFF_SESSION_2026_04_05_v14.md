# SahamGPT-Bot — Session Handoff Document
> Last updated: April 5, 2026 (v14 — Exp 4 accepted, new baseline PF 2.52)
> Repo: https://github.com/nstnarie/SahamGPT-Bot (public, Python 100%)
> Paste this at the start of a new chat to resume seamlessly.

---

## ⚠️ CLAUDE: READ THIS BEFORE DOING ANYTHING

1. **Read `DEVELOPER_CONTEXT.py` first** — locked rules, hard parameters, architectural decisions.
2. **Never answer workflow questions without reading the actual .yml files first.**
3. **`idx-database` is shared** — `scrape_broker_summary.yml`, `initial_scrape.yml`, `bootstrap_database.yml`, `daily_signals.yml`. **NEVER run in parallel.**
4. **Data loss is unrecoverable.** When in doubt, stop and ask Arie.

---

## 1. Current Version: v9 — Main Branch Baseline

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

### feature/v10-experiments — Current Baseline (post Exp 4)
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
| Exposure | 69.7% |

---

## 2. What Happened This Session (April 5, 2026 — continued)

### v10 Experiment 4 — ACCEPTED ✅
**Hypothesis:** After TREND_EXIT (+15%+ gain), block re-entry for 30 trading days.
**Change:** `backtest/engine.py` — cooldown triggers on `STOP_LOSS OR TREND_EXIT` (was `STOP_LOSS` only).
**Run:** 24005616009

| Metric | Exp 2 Baseline | Exp 4 | Change |
|--------|---------------|-------|--------|
| Trades | 42 | 41 | -1 |
| Win Rate | 40.5% | 41.5% | +1.0pp |
| Return | +Rp 137M | +Rp 145M | +Rp 8M |
| Profit Factor | 2.33 | **2.52** | +0.19 |
| Sharpe | 1.02 | **1.11** | +0.09 |
| Calmar | 4.32 | **4.59** | +0.27 |

EMTK Oct 2 re-entry eliminated (entered 17 days after TREND_EXIT → -Rp 7.9M emergency stop).
⚠️ **Re-test 30-day cooldown value once full 2024 data available** — 2024 may have different re-entry patterns.

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

## 3. Entry / Exit Rules

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
| 9 | Regime | Not BEAR + IHSG > MA20 + IHSG daily > -1% |
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

### Re-entry Cooldown (updated in Exp 4)
| Exit Type | Cooldown |
|-----------|----------|
| STOP_LOSS | 30 trading days |
| TREND_EXIT | 30 trading days *(NEW — Exp 4)* |
| All others | None |

---

## 4. Architecture

### Two execution paths — NEVER cross-contaminate
- BACKTEST: `main_backtest.py → backtest/engine.py`
- LIVE: `main_daily.py → signals/signal_combiner.py`

### Key files changed in feature/v10-experiments (accepted: Exp 2 + Exp 4)
- `signals/market_regime.py`: adds `ihsg_entry_ok` column (Exp 2)
- `signals/signal_combiner.py`: gates BUY on `ihsg_entry_ok` (Exp 2)
- `backtest/engine.py`: cooldown on STOP_LOSS OR TREND_EXIT (Exp 4)

---

## 5. Database State (as of April 5, 2026)

- **broker_summary:** 1,292,222 records, 2024-01-02 → 2025-12-30
- **broker_summary 2024 Q1:** COMPLETE ✅ — 58 trading days, all 109 tickers
- **broker_summary 2024 Q2:** batches 1+2 done, batch 3 running
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

**run_backtest.yml from feature branch:** safe while scraper runs — idx-database upload gated to `main` only.

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
  ⬜ batch 4 pt1 (2024-04-01→2024-05-15, tickers 75+)
  ⬜ batch 4 pt2 (2024-05-15→2024-06-30, tickers 75+)
  ⬜ export_summary.yml → verify → update_split_files.yml

Q3 2024: batch1 → batch2 → batch3 → batch4 Jul → batch4 Aug → batch4 Sep
Q4 2024: batch1 → batch2 → batch3 → batch4 Oct → batch4 Nov → batch4 Dec
```
After each quarter: `export_summary.yml` → verify → `update_split_files.yml`

### AFTER 2024 BACKFILL — TICKER UNIVERSE EXPANSION
1. Add to `LQ45_TICKERS` in `scraper/price_scraper.py` (append to end):
   - **Confirmed:** BRIS, CUAN, BREN, PANI, ADHI, PSAB, RAJA, DEWA, RATU, DCII, BNLI, TAPG, AADI
   - **Skipped:** WIFI, MLPL (low liquidity, sparse Asing flow)
2. Run `initial_scrape.yml` — fetch OHLCV for new tickers
3. Run `scrape_broker_summary.yml` with `tickers=BRIS,CUAN,...` override, 2024-01-01 → 2025-12-31
4. `export_summary.yml` → `update_split_files.yml` → push to main

⚠️ **Batch 4 = 47 tickers after expansion — run per month (~2.2h), NOT per quarter (~6.7h > 6h limit)**

### v10 EXPERIMENTS — STATUS

**Current baseline (post Exp 4): 41t | 41.5% WR | PF 2.52 | +Rp 145M | DD -3.37% | Calmar 4.59**

| # | Experiment | Status |
|---|------------|--------|
| ~~1~~ | Emergency stop -12% → -10% | **REJECTED** (run 23982773904) |
| ~~2~~ | IHSG market filter | **ACCEPTED** (run 23982879523) |
| ~~3~~ | FF magnitude filter | **REJECTED** (run 23982978951) |
| ~~4~~ | Post-TREND_EXIT cooldown 30d | **ACCEPTED** (run 24005616009) — ⚠️ re-test 30d with 2024 data |
| ~~5~~ | Remove Rp 150 min price filter | **REJECTED** (run 24005950325) — WTON + GOTO both EMERGENCY_STOP. PF 2.52→2.09, -Rp 20M. Filter stays. |
| ~~6~~ | IHSG multi-day momentum filter | **REJECTED** (run 24006068747) — PF 2.52→1.86, -Rp 68M. 5d lookback blocks best breakouts that start recoveries. |
| 7 | Financial sector entry limit | ⬜ Max 2 Financial Services entries per rolling 10 days. 4/4 bank entries lost (-Rp 18.4M). `engine.py` |
| 8 | Breakout margin filter | ⬜ Require close ≥ 1–2% above 60-day high (not just barely above). Targets marginal entries → emergency stops. `signal_combiner.py` |
| 9 | Early no-follow-through exit | ⬜ Exit if no +1% gain by day 8 after hold period. Frees capital from 6 TIME_EXIT dead trades (-Rp 11.1M, avg 16 days). `portfolio.py` |
| 10 | ATR/price volatility cap | ⬜ Skip entries if ATR > 5% of close. Filters whippy stocks that trigger emergency stops. `signal_combiner.py` |
| 7a | Support/resistance detection | ⬜ ON HOLD — do after integration |
| 7b | Averaging up on resistance break | ⬜ ON HOLD (needs 7a) |
| 7c | Chart pattern detection | ⬜ ON HOLD (needs 7a) |

### INTEGRATION (after 2024 backfill + all experiments done)
- Merge `feature/v10-experiments` → `main` (Exp 2 IHSG filter + Exp 4 cooldown)
- Run `run_backtest.yml` from main to confirm stable post-merge
- Integrate into live path (`main_daily.py → signal_combiner.py`)
- Update `daily_signals.yml` with live broker scraping
- Paper trade 1 month → go live
