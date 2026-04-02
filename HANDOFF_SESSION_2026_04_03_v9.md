# SahamGPT-Bot — Session Handoff Document
> Last updated: April 3, 2026 (end of session — v7 backtest complete, 2024 backfill next)
> Repo: https://github.com/nstnarie/SahamGPT-Bot (public, Python 100%)
> Paste this at the start of a new chat to resume seamlessly.

---

## ⚠️ CLAUDE: READ THIS BEFORE DOING ANYTHING

1. **Read `DEVELOPER_CONTEXT.py` first** — it contains locked rules, hard parameters, and architectural decisions. Do not propose changes to anything listed there without backtest evidence.
2. **Never answer workflow interaction questions without reading the actual .yml files first.** Fetch the file, then answer.
3. **`idx-database` is a shared artifact** — `scrape_broker_summary.yml`, `initial_scrape.yml`, `bootstrap_database.yml`, and `daily_signals.yml` all read/write it. **These workflows must NEVER run in parallel.** Always sequential.
4. **Data loss is unrecoverable.** When in doubt, do not proceed — ask Arie first.

---

## 1. Project Overview

**SahamGPT-Bot** is a fully automated IDX (Indonesia Stock Exchange) swing trading signal system running on **GitHub Actions (free tier)**. Sends daily top 5 stock picks to **Telegram** with optional Claude AI reasoning.

Every weekday at **16:35 WIB** it:
1. Downloads prices for ~109 stocks (LQ45 + IDX SMC Liquid) via Yahoo Finance
2. Scrapes real broker flow (Asing/Lokal/Pemerintah) from Stockbit
3. Identifies breakouts with institutional backing + candle filter
4. Sends top 5 to Telegram

---

## 2. Current Version: v7 — Current Backtest Baseline

### 2025 Real Broker Backtest — v7 (CURRENT BASELINE as of April 3, 2026)
| Metric | Value |
|--------|-------|
| Trades | 59 |
| Win Rate | 33.9% |
| Total Return | +13.66% (+Rp 135M) |
| Profit Factor | **1.88** |
| Max Drawdown | -4.75% |
| Sharpe | 0.93 |
| Sortino | 1.70 |
| Calmar | 2.99 |
| Exposure | 65.3% |

Star trades: TINS +Rp 54M (+118%), PTRO +Rp 39M (+45%), EMTK +Rp 32M (+77%), ANTM +Rp 28M (+45%), BRPT +Rp 23M (+55%)
TREND_EXIT: 11 trades, all winners, Rp +259M total

### Previous baselines (superseded)
| Version | Trades | Win Rate | PnL | PF | Note |
|---------|--------|----------|-----|----|------|
| v6 real broker | 41 | 34.1% | Rp +73M | 1.78 | Superseded — abs-ratio formula too permissive |
| v6 synthetic | 55 | 31% | Rp +60M | 1.38 | Superseded — synthetic FF |
| 2024 synthetic | 45 | 33% | Rp -37M | 0.68 | Real broker backfill pending |

---

## 3. What Changed This Session (April 3, 2026)

### v7: Improved `is_foreign_driven` detection in `signals/signal_combiner.py`

**Problem:** Old formula `avg(abs(Asing net_value)) / avg(close × volume) > 5%` classified 108/109 tickers as foreign-driven. `abs()` inflates the ratio — even random noise trading passes the 5% threshold.

**Fix (lines 173–179):**
```python
# OLD (v6)
avg_ff = df["net_foreign"].abs().rolling(60, min_periods=20).mean()
avg_value = (df["close"] * df["volume"]).rolling(60, min_periods=20).mean()
ff_ratio = avg_ff / avg_value.replace(0, np.nan)
df["is_foreign_driven"] = ff_ratio.fillna(0) > 0.05

# NEW (v7)
rolling_sum = df["net_foreign"].rolling(60, min_periods=20).sum()
rolling_abs_sum = df["net_foreign"].abs().rolling(60, min_periods=20).sum()
consistency = rolling_sum.abs() / rolling_abs_sum.replace(0, np.nan)
df["is_foreign_driven"] = consistency.fillna(0) > 0.20
```

**What consistency measures:**
- `1.0` = foreigners always on the same side (strong directional signal)
- `0.0` = random buy/sell (noise — FF filter was randomly blocking valid breakouts)

**Impact:** 18 extra trades entered (stocks where FF was noise, not signal). PF 1.78 → 1.88, return 7.3% → 13.66%, Sharpe 0.27 → 0.93.

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
| 6 | Foreign flow trend | 5-day FF sum > 0, breakout day not net sell *(only if `is_foreign_driven`)* |
| 7 | RSI | 40–75 |
| 8 | MACD | Histogram > 0 |
| 9 | Regime | Not BEAR |

### Exit (first trigger wins)
| Priority | Rule |
|----------|------|
| 1 | -15% emergency stop (always) |
| 2 | No stop first 5 days |
| 3 | Close < MA10 after +15% gain |
| 4 | -7% or 1.5xATR, cap -10% (after day 5) |
| 5 | Sell 30% at +15% |
| 6 | No +3% in 15 days |
| 7 | 5 consecutive net foreign sell days |
| 8 | BEAR regime = close all |

### Foreign flow logic (`signals/signal_combiner.py`)
- `is_foreign_driven` = **directional consistency > 20%** (v7) — `abs(sum(net,60d)) / sum(abs(net),60d)`
- Only applies FF filter when `is_foreign_driven = True`
- `ff_confirmed = (3+ of last 5 days positive) AND (5-day rolling sum > 0) AND (today not net sell)`
- When `is_foreign_driven = False` → `ff_confirmed = True` automatically (skip filter)
- Use **Asing-only** flow from `broker_summary` with `--real-broker` flag. Do NOT use Lokal aggregate.

---

## 5. Real Broker Integration (HOW IT WORKS)

### `--real-broker` flag in `run_backtest.yml`
```yaml
${{ github.event.inputs.real_broker == 'true' && '--real-broker' || '' }}
```

### `main_backtest.py`
```python
if args.real_broker:
    ff = load_broker_summary_as_ff_df(session, ticker, start_dt, end_dt)
    if ff.empty:
        ff = load_foreign_flow_df(session, ticker, start_dt, end_dt)
else:
    ff = load_foreign_flow_df(session, ticker, start_dt, end_dt)
```

### `database/data_loader.py` → `load_broker_summary_as_ff_df()`
- Queries `broker_type == 'Asing'` only
- Groups by date, sums `net_value`
- Returns DataFrame with `net_foreign_value` column — same interface as `load_foreign_flow_df()`

### Self-healing steps in `run_backtest.yml` (order)
1. Download `idx-database` artifact
2. **Merge broker data from split files** (if broker_summary is empty → merge from `idx_broker_part_a.db` + `idx_broker_part_b.db`)
3. **Backfill missing price data** (if any ticker in broker_summary has no price rows → fetch from Yahoo Finance)
4. Run backtest

---

## 6. Ticker Universe

**Single source of truth:** `scraper/price_scraper.py` → `LQ45_TICKERS`

**As of 2026-03-28:** 109 unique tickers (added PTRO, NIKL; removed 8 duplicates from SMC Liquid)

Batch slicing (in `scrape_broker_summary.yml`):
- Batch 1: `tickers[0:25]`
- Batch 2: `tickers[25:50]`
- Batch 3: `tickers[50:75]`
- Batch 4: `tickers[75:]` — covers **34 tickers** (not 25). Factor into time estimates.

---

## 7. Database State (as of 2026-04-03 end of session)

- **Tables:** broker_summary, stocks, daily_prices, foreign_flow, corporate_actions, index_daily, signal_log
- **broker_summary:** 1,043,576 records, 2025-01-02 to 2025-12-31, 109 unique tickers, 95 broker codes
- **daily_prices:** 107 unique tickers (PTRO and NIKL included via self-heal backfill)

### Broker data quality by period
| Period | Status | Detail |
|--------|--------|--------|
| Q1 2025 (Jan–Mar) | ✅ Complete | 58 days, 103–109 tickers/day |
| Apr 1–7 2025 | ✅ Confirmed holiday | Lebaran + Easter — IDX closed, API returns zeros |
| Apr 8–Jun 30 2025 | ✅ Complete | All 4 batches done, all 109 tickers |
| Q3 2025 (Jul–Sep) | ✅ Complete | 64 days, 105–107 tickers/day |
| Q4 2025 (Oct–Dec) | ✅ Complete | 63 days, 104–107 tickers/day |
| 2024 full year | ❌ Not started | **Next priority** |

### Split files (fallback if artifact unavailable)
- `idx_broker_part_a.db` (242,321 records) + `idx_broker_part_b.db` (801,255 records)
- Both committed to repo root. `run_backtest.yml` merges on startup if artifact is empty.

---

## 8. Workflows

| File | Trigger | Touches idx-database? | Purpose |
|------|---------|----------------------|---------|
| `daily_signals.yml` | Weekday 16:35 WIB | ✅ Yes | Full pipeline → Telegram |
| `initial_scrape.yml` | Manual | ✅ Yes | Historical price download |
| `run_backtest.yml` | Manual | ✅ Yes | On-demand backtesting (has --real-broker flag) |
| `monthly_optimise.yml` | Monthly | ✅ Yes | Parameter tuning |
| `scrape_broker_summary.yml` | Manual | ✅ Yes | Batch broker data scraping |
| `export_summary.yml` | Manual | ❌ No | Export per-day ticker count CSV |
| `bootstrap_database.yml` | Manual (one-time) | ✅ Yes | Merges split files into artifact |
| `update_split_files.yml` | Manual | ❌ No | Regenerates split files from artifact |

### ⚠️ Parallelism rule
**Any workflow marked "✅ Yes" MUST run sequentially with all others in that group.**

### Critical workflow patterns
- **Always use `python3 << 'EOF'` heredoc** — never `python3 -c "..."` (SyntaxError with nested quotes)
- **Always gate artifact upload** on record count check
- **Artifact download** → `dawidd6/action-download-artifact@v6` (NOT `actions/download-artifact@v4`)
- **Batch 4 for a full quarter (~65 days) → always split into 2 date-range parts** (~5.5hr otherwise)
- **`update_split_files.yml` needs `permissions: contents: write`**

---

## 9. Architectural Patterns

- **Split file fallback:** DB > 25MB → split into part_a + part_b committed to repo → workflow merges on startup if artifact empty
- **Self-healing backfill:** `run_backtest.yml` checks for tickers in broker_summary with no price data → fetches from Yahoo Finance
- **Asing-only FF:** `load_broker_summary_as_ff_df()` queries `broker_type == 'Asing'` only. Never use Lokal aggregate (noise)
- **is_foreign_driven gate:** directional consistency > 20% (v7). FF filter only applied where Asing flow is persistently directional
- **Two execution paths (NEVER cross-contaminate):**
  - BACKTEST: `main_backtest.py → backtest/engine.py`
  - LIVE: `main_daily.py → signals/signal_combiner.py`
- **Upsert not replace:** Both price and broker scrapers merge into existing DB, never truncate

---

## 10. Constraints

- Cost: Rp 0/month target (GitHub Actions free tier)
- No paid data sources
- IDX: Lot = 100 shares, buy 0.15%, sell 0.25%, slippage 1 tick
- Universe: LQ45 + IDX SMC Liquid (109 unique tickers)
- Stockbit token: Bearer JWT, ~24hr expiry, **manual refresh required before each scrape session**
- GitHub file size limit: 25 MB per file (split files must stay under this)
- GitHub Actions timeout: 6 hours per job

---

## 11. Next Steps (in order)

### IMMEDIATE — 2024 Broker Data Backfill
Refresh Stockbit token before starting. Run sequentially, one batch at a time.

```
Q1 2024: batch1 → batch2 → batch3 → batch4 (Jan 1–Feb 15) → batch4 (Feb 15–Mar 31)
Q2 2024: batch1 → batch2 → batch3 → batch4 (Apr 1–May 15) → batch4 (May 15–Jun 30)
Q3 2024: batch1 → batch2 → batch3 → batch4 (Jul 1–Aug 15) → batch4 (Aug 15–Sep 30)
Q4 2024: batch1 → batch2 → batch3 → batch4 (Oct 1–Nov 15) → batch4 (Nov 15–Dec 31)
```
After each quarter: `export_summary.yml` → verify tickers/day → `update_split_files.yml`

### AFTER 2024 BACKFILL
- Run `run_backtest.yml` with `real_broker=true`, `start_date=2024-01-01`, `end_date=2024-12-31`
- Compare vs synthetic 2024 baseline: 45 trades, 33% WR, Rp -37M, PF 0.68
- Run combined 2024+2025 for full picture

### INTEGRATION & IMPROVEMENT
- Integrate real broker data + v7 `is_foreign_driven` into `signal_combiner.py` (live path)
- Fix 6–10 day stop-loss weak spot (54 trades in v6, 8% WR, -215M)
- Update `daily_signals.yml` to include live broker scraping
- Paper trade 1 month → go live
