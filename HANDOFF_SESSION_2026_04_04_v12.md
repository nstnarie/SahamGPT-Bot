# SahamGPT-Bot — Session Handoff Document
> Last updated: April 4, 2026 (v12 — 2024 backfill started, trade log analysis pending)
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

### TRADE LOG ANALYSIS (pending — to do in Claude chat)
- Trade log at: `reports/latest/trade_log.csv`
- Upload to Claude chat: this handoff doc + `DEVELOPER_CONTEXT.py` + `trade_log.csv` + `metrics_summary.txt`
- Key question: what hypotheses to test in v10?
- Known weak spot: 6–10 day stop losses (high count, low WR, large loss pool)

### INTEGRATION
- Integrate v9 signal logic into live path (`main_daily.py → signal_combiner.py`)
- Update `daily_signals.yml` with live broker scraping
- Paper trade 1 month → go live
