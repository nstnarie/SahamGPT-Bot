# SahamGPT-Bot — Session Handoff Document
> Last updated: April 3, 2026 (end of session — v8 backtest complete, 2024 backfill next)
> Repo: https://github.com/nstnarie/SahamGPT-Bot (public, Python 100%)
> Paste this at the start of a new chat to resume seamlessly.

---

## ⚠️ CLAUDE: READ THIS BEFORE DOING ANYTHING

1. **Read `DEVELOPER_CONTEXT.py` first** — locked rules, hard parameters, architectural decisions. Do not change anything without backtest evidence.
2. **Never answer workflow interaction questions without reading the actual .yml files first.**
3. **`idx-database` is a shared artifact** — `scrape_broker_summary.yml`, `initial_scrape.yml`, `bootstrap_database.yml`, `daily_signals.yml` all read/write it. **NEVER run in parallel. Always sequential.**
4. **Data loss is unrecoverable.** When in doubt, stop and ask Arie.

---

## 1. Project Overview

**SahamGPT-Bot** is a fully automated IDX swing trading signal system on **GitHub Actions (free tier)**. Sends daily top 5 picks to **Telegram** with optional Claude AI reasoning.

Every weekday at **16:35 WIB**:
1. Downloads prices for ~109 stocks (LQ45 + IDX SMC Liquid) via Yahoo Finance
2. Scrapes real broker flow (Asing/Lokal/Pemerintah) from Stockbit
3. Identifies breakouts with institutional backing + candle filter
4. Sends top 5 to Telegram

---

## 2. Current Version: v8 — Current Backtest Baseline

### 2025 Real Broker Backtest — v8 (CURRENT BASELINE as of April 3, 2026)
| Metric | Value |
|--------|-------|
| Trades | 60 |
| Win Rate | 36.7% |
| Total Return | +14.63% (+Rp 145M) |
| Profit Factor | **1.97** |
| Max Drawdown | -4.11% |
| Sharpe | 1.01 |
| Sortino | 1.79 |
| Calmar | 3.71 |
| Exposure | 71.2% |

Star trades: TINS +Rp 54M (+118%), PTRO +Rp 39M (+45%), EMTK +Rp 32M (+77%), ANTM +Rp 28M (+45%)
TREND_EXIT: 11 trades, all winners, Rp +261M total

### Version progression
| Version | Trades | WR | PnL | PF | Key change |
|---------|--------|----|-----|----|------------|
| v6 real broker | 41 | 34.1% | +Rp 73M | 1.78 | Real broker data integrated |
| v7 | 59 | 33.9% | +Rp 135M | 1.88 | is_foreign_driven = directional consistency |
| **v8** | **60** | **36.7%** | **+Rp 145M** | **1.97** | Broker accumulation hold extension |
| 2024 synthetic | 45 | 33% | -Rp 37M | 0.68 | Real broker backfill pending |

---

## 3. What Changed This Session (April 3, 2026)

### v7: Improved `is_foreign_driven` (`signals/signal_combiner.py:173-179`)
Old: `avg(abs(net_value)) / avg(close×volume) > 5%` — classified 108/109 tickers (useless)
New: directional consistency `abs(sum(net,60d)) / sum(abs(net),60d) > 20%`

### v8: Broker accumulation hold extension

**New function:** `database/data_loader.py` → `load_broker_accumulation_df()`
- Loads all Asing broker rows for a ticker
- Pivots to broker×date matrix
- Rolling 5-day window per broker: active 3+/5 days AND net buyer 4+/5 = "accumulating"
- Returns `accumulation_score` = count(accumulating) - count(distributing) per date

**Hold extension:** `backtest/portfolio.py:check_exit_conditions()`
```python
# 4. REGULAR STOP-LOSS (after day 5)
if current_low <= position.stop_price:
    if acc_score > 0 and position.days_held <= 10:
        return "", 0.0  # skip stop — brokers still accumulating
    return "STOP_LOSS", 1.0
```

**Key learning:** acc_score works as a **hold signal**, NOT an entry filter.
- As entry filter: 84% of breakout days have negative scores (count-based vs value-based conflict)
- As hold signal: meaningful at stop-fire moment — if brokers buying the dip, hold through it

**Wiring:** `main_backtest.py` → `load_broker_accumulation_df()` → `engine.run(broker_data=...)` → `signal_combiner._add_accumulation_signals()` → stored as `accumulation_score` in sig_df → read by engine daily loop → passed to `check_exit_conditions(acc_score=...)`

---

## 4. Entry / Exit Rules

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

### Exit (first trigger wins)
| Priority | Rule |
|----------|------|
| 1 | -15% emergency stop (always) |
| 2 | No stop first 5 days |
| 3 | Close < MA10 after +15% gain |
| 4 | -7% or 1.5xATR, cap -10% (after day 5) — **with hold extension if acc_score > 0 on days 6-10** |
| 5 | Sell 30% at +15% |
| 6 | No +3% in 15 days (+ below MA10) |
| 7 | 5 consecutive net foreign sell days (foreign-driven stocks only, price weakening) |
| 8 | BEAR regime = close all |

### `is_foreign_driven` (v7)
`consistency = abs(sum(net,60d)) / sum(abs(net),60d) > 20%`
— measures if Asing flow is persistently directional. ~60/109 tickers qualify.

### `accumulation_score` (v8)
Per date: count(Asing brokers active 3+/5d AND net buyer 4+/5d) − count(active 3+/5d AND net buyer ≤1/5d)
Used only for hold extension (days 6-10). NOT used as entry filter.

---

## 5. Architecture

### Real broker integration
- `--real-broker` flag → `load_broker_summary_as_ff_df()` (Asing-only net_value)
- `--real-broker` flag → `load_broker_accumulation_df()` (per-broker consistency score)
- Both fallback gracefully if data missing

### Self-healing in `run_backtest.yml`
1. Download `idx-database` artifact
2. Merge broker data from split files (if broker_summary empty)
3. Backfill missing price data from Yahoo Finance
4. Run backtest

### Two execution paths — NEVER cross-contaminate
- BACKTEST: `main_backtest.py → backtest/engine.py`
- LIVE: `main_daily.py → signals/signal_combiner.py`

### Split file fallback
- `idx_broker_part_a.db` (242,321 rows) + `idx_broker_part_b.db` (801,255 rows) in repo root
- `run_backtest.yml` merges on startup if artifact is empty

---

## 6. Database State (as of 2026-04-03)

- **broker_summary:** 1,043,576 records, 2025-01-02 to 2025-12-31, 109 tickers, 95 broker codes
- **daily_prices:** 107 unique tickers

| Period | Status |
|--------|--------|
| 2025 full year | ✅ Complete |
| Apr 1–7 2025 | ✅ Confirmed Lebaran holiday — no data |
| **2024 full year** | ❌ **Not started — NEXT PRIORITY** |

---

## 7. Workflows

| File | Touches idx-database? | Purpose |
|------|-----------------------|---------|
| `daily_signals.yml` | ✅ Yes | Full pipeline → Telegram (weekday 16:35 WIB) |
| `initial_scrape.yml` | ✅ Yes | Historical price download |
| `run_backtest.yml` | ✅ Yes | On-demand backtesting |
| `monthly_optimise.yml` | ✅ Yes | Parameter tuning |
| `scrape_broker_summary.yml` | ✅ Yes | Batch broker data scraping |
| `export_summary.yml` | ❌ No | Export per-day ticker count CSV |
| `bootstrap_database.yml` | ✅ Yes | Merges split files into artifact |
| `update_split_files.yml` | ❌ No | Regenerates split files from artifact |

⚠️ All workflows touching idx-database must run **sequentially, never in parallel**.

### Critical patterns
- `python3 << 'EOF'` heredoc — never `python3 -c "..."`
- Always gate artifact upload on record count check
- `dawidd6/action-download-artifact@v6` — never `actions/download-artifact@v4`
- Batch 4 full quarter → always split into 2 date-range parts (~5.5hr otherwise)

---

## 8. Next Steps (in order)

### IMMEDIATE — 2024 Broker Data Backfill
Refresh Stockbit token before starting. One batch at a time, sequential.

```
Q1 2024: batch1 → batch2 → batch3 → batch4 (Jan 1–Feb 15) → batch4 (Feb 15–Mar 31)
Q2 2024: batch1 → batch2 → batch3 → batch4 (Apr 1–May 15) → batch4 (May 15–Jun 30)
Q3 2024: batch1 → batch2 → batch3 → batch4 (Jul 1–Aug 15) → batch4 (Aug 15–Sep 30)
Q4 2024: batch1 → batch2 → batch3 → batch4 (Oct 1–Nov 15) → batch4 (Nov 15–Dec 31)
```
After each quarter: `export_summary.yml` → verify tickers/day → `update_split_files.yml`

### AFTER 2024 BACKFILL
- Run `run_backtest.yml` with `real_broker=true`, 2024-01-01 to 2024-12-31
- Compare vs synthetic baseline: 45 trades, 33% WR, -Rp 37M, PF 0.68
- Run combined 2024+2025 for full picture

### INTEGRATION & IMPROVEMENT
- Integrate v8 logic into `signal_combiner.py` live path (`main_daily.py`)
- Fix remaining 6–10 day stop-loss tail (now reduced but not eliminated)
- Update `daily_signals.yml` to include live broker scraping
- Paper trade 1 month → go live
