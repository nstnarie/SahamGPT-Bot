# SahamGPT-Bot — Session Handoff Document
> Last updated: April 9, 2026 (v17 — 2024+2025 backtests confirmed, backfill bug fixed, ready for new ticker scrape + Opus analysis)
> Repo: https://github.com/nstnarie/SahamGPT-Bot (public, Python 100%)
> Paste this at the start of a new chat to resume seamlessly.

---

## ⚠️ CLAUDE: READ THIS BEFORE DOING ANYTHING

1. **Read `DEVELOPER_CONTEXT.py` first** — locked rules, hard parameters, architectural decisions.
2. **Never answer workflow questions without reading the actual .yml files first.**
3. **`idx-database` is shared** — `scrape_broker_summary.yml`, `initial_scrape.yml`, `bootstrap_database.yml`, `daily_signals.yml`. **NEVER run in parallel.**
4. **Data loss is unrecoverable.** When in doubt, stop and ask Arie.

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

### feature/v10-experiments — current baseline (post Exp 4)
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

### Prior session (April 5–6, 2026)
- Full loss analysis of v9 28 losing trades (-Rp 103M). 5 patterns identified → Exp 6–10 queued.
- Exp 4 ACCEPTED, Exp 5/6/7 REJECTED. See experiment log in DEVELOPER_CONTEXT.py.

### This session (April 9, 2026) — Key events

**2024 backfill complete (carried over from session end):**
All Q1-Q4 2024 broker data scraped and merged → 2,071,251 records, split files updated.

**Critical bug fixed — run_backtest.yml backfill:**
Root cause of "Loaded 2 stocks, IHSG: 0 days" diagnosed and fixed.
- `daily_signals.yml` uploads daily prices (today-only) to idx-database artifact
- Backfill step only checked `date >= warmup_start` (lower bound only)
- Tickers with 2025-only data passed the check → backfill skipped
- main_backtest's `date <= end_date` filter then excluded all 2025 rows → 0 results
- Fix: query now checks BOTH bounds `date >= warmup_start AND date <= end_date`
- Also added IHSG backfill block (same issue for index_daily table)
- Also added `CREATE TABLE IF NOT EXISTS daily_prices/index_daily` for broker-only artifacts
- Applied to both main and feature/v10-experiments

**Synthetic data fully removed:**
`main_backtest.py`: no more fallback from real broker data to synthetic ForeignFlow.
Under `--real-broker`, empty ff means ticker trades on price/volume signals only (FF filter skipped).

**2024 backtest — CONFIRMED WORKING** (run 24171380283, feature/v10-experiments):
| Metric | Value |
|--------|-------|
| Loaded | 109 stocks, IHSG 237 days |
| Trades | 42 |
| Win Rate | 35.7% |
| Total Return | **-6.05%** |
| Profit Factor | 0.47 |
| Max Drawdown | -6.76% (114 days) |
| Sharpe | -2.13 |
| Benchmark Max DD | -11.74% |

**2025 backtest — CONFIRMED BASELINE** (run 24171709463, feature/v10-experiments):
| Metric | Value |
|--------|-------|
| Loaded | 109 stocks, IHSG 236 days |
| Trades | 41 |
| Win Rate | 41.5% |
| Total Return | **+14.55%** |
| Profit Factor | 2.52 |
| Max Drawdown | -3.37% (51 days) |
| Sharpe | 1.11 / Sortino 1.93 / Calmar 4.59 |
| Benchmark Return | +20.71% / Benchmark Max DD -17.76% |

**Key insight from 2024 vs 2025:**
Strategy is regime-sensitive by design (breakout/momentum). 2024 IHSG bear year → false breakouts dominate. 
2025 bull year → strategy excels. Experiments 8-10 target the 2024 false breakout problem specifically.

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
| TREND_EXIT | 30 trading days *(NEW — Exp 4)* |

---

## 4. Architecture

### Two execution paths — NEVER cross-contaminate
- BACKTEST: `main_backtest.py → backtest/engine.py`
- LIVE: `main_daily.py → signals/signal_combiner.py`

### Key files changed in feature/v10-experiments (accepted: Exp 2 + Exp 4)
- `signals/market_regime.py`: adds `ihsg_entry_ok` (Exp 2)
- `signals/signal_combiner.py`: gates BUY on `ihsg_entry_ok` (Exp 2)
- `backtest/engine.py`: cooldown on `STOP_LOSS OR TREND_EXIT` (Exp 4)

### run_backtest.yml from feature branch
Safe while scraper runs — idx-database upload gated: `if: always() && github.ref == 'refs/heads/main'`

---

## 5. Database State

- **broker_summary:** 2,071,251 records, 2024-01-02 → 2025-12-30
- **Q1 2024:** COMPLETE ✅
- **Q2 2024:** COMPLETE ✅ (Apr 6, 2026)
- **Q3 2024:** COMPLETE ✅ (Apr 8, 2026)
- **Q4 2024:** COMPLETE ✅ (Apr 9, 2026) — 5 runs, split files updated
- **daily_prices:** 107 tickers, 2021-01-01 to 2026-03-28 (new tickers not yet scraped)
- **Split files:** `idx_broker_part_a.db` (1,269,996) + `idx_broker_part_b.db` (801,255) = 2,071,251 ✅

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

---

## 7. Next Steps (in order)

### ⚠️ CURRENT PRIORITY (Apr 9, 2026)
Two parallel tracks running simultaneously:
1. **MAIN branch**: Scrape new 28 tickers (broker summary + prices)
2. **FEATURE branch**: Opus analysis of 2024+2025 trade logs → brainstorm improvements

### ✅ COMPLETE — 2024 Broker Data Backfill (109 original tickers)
Final: **2,071,251 records** | part_a 1,269,996 + part_b 801,255 ✅ (Apr 9, 2026)

### ✅ COMPLETE — 2024 + 2025 Backtests Confirmed (Apr 9, 2026)
| Year | Trades | WR | Return | PF | Max DD | Sharpe | Run ID |
|------|--------|-----|--------|----|--------|--------|--------|
| 2024 | 42 | 35.7% | -6.05% | 0.47 | -6.76% | -2.13 | 24171380283 |
| 2025 | 41 | 41.5% | +14.55% | 2.52 | -3.37% | 1.11 | 24171709463 |

Both on feature/v10-experiments, 109 tickers, real_broker=true.

### ✅ COMPLETE — Backfill Bug Fixed (Apr 9, 2026)
`run_backtest.yml` "Backfill missing price data" step now checks both date bounds.
Applied to both main and feature/v10-experiments. See DEVELOPER_CONTEXT.py Learning 21+22.

### TICKER UNIVERSE EXPANSION ⬜ IN PROGRESS
LQ45_TICKERS expanded to **137 tickers** on feature/v10-experiments (109 original + 28 new).
New tickers: AADI, ADMR, BREN, BRIS, CUAN, DEWA, PANI, PSAB, RAJA, RATU, WIFI,
             ADHI, AGRO, AMAN, ARGO, ARTO, ASSA, AVIA, BNBA, DOID, ENRG, IMAS,
             KRAS, POWR, SMBR, SMDR, WIIM, INET (added Apr 9)
⚠️ **ENRG: verify price manually** — yfinance shows Rp 1500 (historically ~Rp 100-200).

**Not added:** MLPL(Rp91), ABBA(Rp44), ACST(Rp98), BKSL(Rp108) — sub-Rp150 / AMAR, CMNP, MCAS — too thin (<Rp1B/day)

**Steps remaining:**
1. `scrape_broker_summary.yml` — new 28 tickers, 2024-01-01→2025-12-31 (sequential batches, main branch) ⬜
2. `initial_scrape.yml` — OHLCV 2021-01-01→present for new 28 tickers ⬜
3. `export_summary.yml` → `update_split_files.yml` → push to main ⬜

### v10 EXPERIMENTS — STATUS

> ⚠️ **ALL PENDING EXPERIMENTS ON HOLD** — Will redo the entire experiment suite once the full dataset is ready: 2024+2025 broker summary + price data for all 137 tickers. Results on partial/old-universe data will be invalidated.

**Current baseline (post Exp 4, 2025 data only, 109 tickers): 41t | 41.5% WR | PF 2.52 | +Rp 145M | DD -3.37% | Calmar 4.59**

| # | Experiment | Status |
|---|------------|--------|
| ~~1~~ | Emergency stop -12% → -10% | ❌ REJECTED (run 23982773904) — re-test on full data |
| ~~2~~ | IHSG market filter (daily) | ✅ ACCEPTED (run 23982879523) — re-test on full data |
| ~~3~~ | FF magnitude filter | ❌ REJECTED (run 23982978951) — re-test on full data |
| ~~4~~ | Post-TREND_EXIT cooldown 30d | ✅ ACCEPTED (run 24005616009) — re-test on full data |
| ~~5~~ | Remove Rp 150 min price filter | ❌ REJECTED (run 24005950325) — likely stays rejected |
| ~~6~~ | IHSG 5d momentum filter | ❌ REJECTED (run 24006068747) — likely stays rejected |
| ~~7~~ | Financial sector entry limit | ❌ REJECTED (run 24006206306) — re-test on full data (may fire in 2024) |
| **8** | Breakout margin filter (close ≥1-2% above 60d high) | ⏸ ON HOLD — pending full data |
| **9** | Early no-follow-through exit (no +1% by day 8) | ⏸ ON HOLD — pending full data |
| **10** | ATR/price volatility cap (ATR > 5% of close → skip) | ⏸ ON HOLD — pending full data |
| 7a | Support/resistance detection | ⬜ ON HOLD (post-integration) |
| 7b | Averaging up on resistance break | ⬜ ON HOLD (needs 7a) |
| 7c | Chart pattern detection | ⬜ ON HOLD (needs 7a) |

### INTEGRATION (after full data + experiment re-run complete)
- Merge `feature/v10-experiments` → `main` (accepted experiments only)
- Run `run_backtest.yml` from main to confirm stable post-merge
- Integrate into live path (`main_daily.py → signal_combiner.py`)
- Update `daily_signals.yml` with live broker scraping
- Paper trade 1 month → go live
