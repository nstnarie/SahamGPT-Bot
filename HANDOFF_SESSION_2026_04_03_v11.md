# SahamGPT-Bot — Session Handoff Document
> Last updated: April 3, 2026 (end of session — v9 complete, 2024 backfill next)
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

### 2025 Real Broker Backtest — v9 (CURRENT BASELINE as of April 3, 2026)
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

### Version progression (2025 real broker)
| Ver | Trades | WR | PnL | PF | Calmar | Key change |
|-----|--------|----|-----|----|--------|------------|
| v6 | 41 | 34.1% | +Rp 73M | 1.78 | 2.69 | Real broker data |
| v7 | 59 | 33.9% | +Rp 135M | 1.88 | — | is_foreign_driven formula |
| v8 | 60 | 36.7% | +Rp 145M | 1.97 | 3.71 | Accumulation hold extension |
| **v9** | **45** | **37.8%** | **+Rp 127M** | **2.14** | **4.16** | 4 structural fixes |

---

## 2. What Changed This Session (April 3, 2026)

### v7: `is_foreign_driven` directional consistency (`signal_combiner.py:173-179`)
`consistency = abs(sum(net,60d)) / sum(abs(net),60d) > 20%`

### v8: Broker accumulation hold extension (`portfolio.py:check_exit_conditions`)
Skip stop-loss on days 6–10 if `acc_score > 0` (Asing brokers still accumulating dip).

### v9: 4 structural fixes

**1. Indicator warmup** (`main_backtest.py`)
```python
warmup_start = (pd.Timestamp(args.start) - pd.DateOffset(months=5)).date()
pdf = load_prices_as_dataframe(session, ticker, warmup_start, end_dt)
```
Fixes: BBTN's entire Mar–Apr 2025 rally (770→1280) was invisible because 60d high was NaN for first 3 months.

**2. Gap-up entry rejection** (`engine.py`)
```python
if gap_pct > self.config.entry.max_gap_up_pct:  # default 7%
    continue
```
Fixes: EMTK Oct 2 opened +5.4% gap-up → entered at top of rejection candle → -Rp 10M.

**3. Emergency stop -15% → -12%** (`config.py`)
```python
emergency_stop_pct: float = 0.12
```
Saved ~Rp 4M across ESSA and EMTK.

**4. Cluster limit: max 5 entries / 10 trading days** (`engine.py`)
```python
max_entries_per_week: int = 5  # in EntryConfig
# rolling 10-day count in engine — if >= 5, pause new entries
```
Fixes: May 2025 had 13 entries in 8 days (11 losers, -Rp 9M). Reduced to 5 entries.

### What was tried and rejected (broker accumulation as entry filter)
- Count-based `acc_score > 0`: 84% of breakout days negative → 8 trades, 0% WR
- Pre-breakout `max(acc[-15:-1]) > 0`: PF 1.43 (blocked PTRO, EMTK)
- Top-5 value-weighted `top_broker_acc > 0`: PF 1.27 (blocked PTRO +Rp 39M, EMTK +Rp 32M)
- **Key learning:** ff_confirmed (value-weighted aggregate) already captures big money entry signal. Count-based broker filters are redundant and destructive. Accumulation score works ONLY as hold signal (v8), not entry filter.

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

## 4. Architecture

### Key files changed in v9
- `config.py`: `emergency_stop_pct=0.12`, `max_gap_up_pct=0.07`, `max_entries_per_week=5`
- `main_backtest.py`: warmup_start = start - 5 months for price loading
- `backtest/engine.py`: gap-up filter + rolling 10-day cluster limit

### Data pipeline (real broker backtest)
- `load_broker_summary_as_ff_df()` → Asing-only net_value as FF signal
- `load_broker_accumulation_df()` → per-broker consistency score for hold extension
- Both fed via `--real-broker` flag

### Two execution paths — NEVER cross-contaminate
- BACKTEST: `main_backtest.py → backtest/engine.py`
- LIVE: `main_daily.py → signals/signal_combiner.py`

---

## 5. Database State (as of 2026-04-03)

- **broker_summary:** 1,043,576 records, 2025-01-02 to 2025-12-31, 109 tickers
- **2024 full year: NOT STARTED — NEXT PRIORITY**

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

### IMMEDIATE — 2024 Broker Data Backfill
Refresh Stockbit token before starting. One batch at a time, sequential.

```
Q1 2024: batch1 → batch2 → batch3 → batch4 (Jan 1–Feb 15) → batch4 (Feb 15–Mar 31)
Q2 2024: batch1 → batch2 → batch3 → batch4 (Apr 1–May 15) → batch4 (May 15–Jun 30)
Q3 2024: batch1 → batch2 → batch3 → batch4 (Jul 1–Aug 15) → batch4 (Aug 15–Sep 30)
Q4 2024: batch1 → batch2 → batch3 → batch4 (Oct 1–Nov 15) → batch4 (Nov 15–Dec 31)
```
After each quarter: `export_summary.yml` → verify → `update_split_files.yml`

### AFTER 2024 BACKFILL
- Run `run_backtest.yml` real_broker=true, 2024-01-01 to 2024-12-31
- Compare vs synthetic: 45 trades, 33% WR, -Rp 37M, PF 0.68
- Run combined 2024+2025

### INTEGRATION
- Integrate v9 signal logic into live path (`main_daily.py → signal_combiner.py`)
- Update `daily_signals.yml` with live broker scraping
- Paper trade 1 month → go live
