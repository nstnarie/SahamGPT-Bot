# SahamGPT-Bot — Session Handoff Document
> Last updated: April 1, 2026 (end of session — Full 2025 broker data complete, backtesting next)
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

## 2. Current Version: v6 (first profitable)

| Year | Trades | Win Rate | PnL | Profit Factor |
|------|--------|----------|-----|---------------|
| 2024 | 45 | 33% | Rp -37M | 0.68 |
| **2025** | **55** | **31%** | **Rp +60M** | **1.38** |
| Combined | 100 | 32% | Rp +23M | 1.08 |

Star: Trend exit → Rp +240M from 12 trades (avg +26.5%).

Note: Above results use synthetic foreign flow. Re-running with real broker data is the next priority.

---

## 3. Tech Stack

| Component | Choice |
|-----------|--------|
| Language | Python 3 (100%) |
| Database | SQLite via SQLAlchemy ORM (`idx_swing_trader.db`) |
| Price data | Yahoo Finance (`yfinance`, suffix `.JK`, `auto_adjust=False`) |
| Broker flow | Stockbit API (Bearer JWT token auth, ~24hr expiry) |
| Automation | GitHub Actions (8 workflows) |
| Notifications | Telegram Bot API |
| AI reasoning | Anthropic Claude API (`claude-sonnet-4-20250514`) |

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
| 6 | Foreign flow trend | 5-day FF sum > 0, breakout day not net sell |
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

---

## 5. Ticker Universe

**Single source of truth:** `scraper/price_scraper.py` → `LQ45_TICKERS`

**As of 2026-03-28:**
- Removed 8 duplicate tickers from SMC Liquid section: `ACES`, `BFIN`, `BUKA`, `CTRA`, `ITMG`, `KLBF`, `MAPI`, `TBIG`
- Added 2 new tickers: `PTRO`, `NIKL`
- **Total: 109 unique tickers**

`broker_scraper.py` does NOT define its own ticker list — it receives `LQ45_TICKERS` from the workflow.

Batch slicing (in `scrape_broker_summary.yml`):
- Batch 1: `tickers[0:25]`
- Batch 2: `tickers[25:50]`
- Batch 3: `tickers[50:75]`
- Batch 4: `tickers[75:]` — covers **34 tickers** (not 25). Factor into time estimates.

---

## 6. Database State (as of 2026-04-01 end of session)

- **Tables:** broker_summary, stocks, daily_prices, foreign_flow, corporate_actions, index_daily, signal_log
- **broker_summary schema:** id, ticker, date (YYYY-MM-DD), broker_code, broker_type (Asing/Lokal/Pemerintah), buy_value, sell_value, buy_volume, sell_volume, net_value, net_volume
- **Current record count:** 1,043,576
- **Date range in DB:** 2025-01-02 to 2025-12-31
- **Unique tickers:** 109 | **Unique broker codes:** 95

### Broker data quality by period
| Period | Status | Detail |
|--------|--------|--------|
| Q1 2025 (Jan–Mar) | ✅ Complete | 58 days, 103–109 tickers/day |
| Apr 1–7 2025 | ✅ Confirmed holiday | Lebaran + Easter — IDX closed, API returns zeros |
| Apr 8–Jun 30 2025 | ✅ Complete | All 4 batches done, all 109 tickers |
| Q3 2025 (Jul–Sep) | ✅ Complete | 64 days, 105–107 tickers/day, zero low days |
| Q4 2025 (Oct–Dec) | ✅ Complete | 63 days, 104–107 tickers/day, zero low days |
| 2024 full year | ❌ Not started | Only after 2025 backtest confirms improvement |

### Q4 2025 scraping detail
| Batch | Delta | Running Total |
|-------|-------|---------------|
| Baseline (Q3 end) | — | 756,370 |
| B1 Oct–Dec | +84,209 | 840,579 |
| B2 Oct–Dec | +69,214 | 909,793 |
| B3 Oct–Dec | +58,359 | 968,152 |
| B4 Oct–Nov15 | +40,314 | 1,008,466 |
| B4 Nov15–Dec | +35,110 | 1,043,576 |

### Baseline artifact & split files
- **1,043,576 records** is the current baseline
- Split files updated and committed to repo root via `update_split_files.yml` after Q4 completion
- Split verified: 242,321 + 801,255 = 1,043,576 ✅

### Price data
- `initial_scrape.yml` run on 2026-03-28 — covers all 109 tickers from 2021-01-01 to 2026-03-28
- Includes full PTRO and NIKL price history

---

## 7. Workflows

| File | Trigger | Touches idx-database? | Purpose |
|------|---------|----------------------|---------|
| `daily_signals.yml` | Weekday 16:35 WIB | ✅ Yes | Full pipeline → Telegram |
| `initial_scrape.yml` | Manual | ✅ Yes | Historical price download |
| `run_backtest.yml` | Manual | ✅ Yes | On-demand backtesting |
| `monthly_optimise.yml` | Monthly | ✅ Yes | Parameter tuning |
| `scrape_broker_summary.yml` | Manual | ✅ Yes | Batch broker data scraping |
| `export_summary.yml` | Manual | ❌ No | Export per-day ticker count CSV |
| `bootstrap_database.yml` | Manual (one-time) | ✅ Yes | Merges split files into artifact |
| `update_split_files.yml` | Manual | ❌ No | Regenerates split files from artifact |

### ⚠️ Parallelism rule
**Any workflow marked "✅ Yes" above MUST run sequentially with all others in that group.**
Never run two idx-database workflows at the same time — the one that finishes last will overwrite the other's data with a stale copy of the DB from the start of its run.

### scrape_broker_summary.yml inputs
- `start_date` / `end_date`
- `batch`: `1` (tickers 0–24) / `2` (25–49) / `3` (50–74) / `4` (75+) / `all`
- `tickers`: optional comma-separated override (e.g. `NIKL,PTRO`) — overrides batch entirely

### Critical workflow patterns
- **Always use `python3 << 'EOF'` heredoc** — never `python3 -c "..."` (causes SyntaxError)
- **Always gate artifact upload** on record count check (`if: steps.check_data.outputs.has_data == 'true'`)
- **Always restore existing DB before scraping** — merge new data in, never replace
- **Artifact download** uses `dawidd6/action-download-artifact@v6` — NOT `actions/download-artifact@v4`
- **Run batches sequentially** — each batch must finish and save artifact before next starts
- **`update_split_files.yml` needs `permissions: contents: write`** to push to repo
- **Batch 4 (34 tickers) for a full quarter (~65 days) takes ~5.5 hours** — always split into 2 date-range parts

---

## 8. Architectural Patterns

- **Split file fallback:** DB > 25MB → split into part_a + part_b committed to repo → workflow merges on startup if artifact unavailable. Update split files after each major data milestone.
- **Data guard:** Always check `COUNT(*) > 0` before saving artifact
- **Heredoc pattern:** All multi-line Python in YAML uses `python3 << 'EOF'`
- **Sequential workflows:** All workflows touching `idx-database` must run one at a time
- **Upsert not replace:** Both price and broker scrapers merge into existing DB, never truncate
- **Duplicate guard in `scrape_historical`:** Per-broker `filter_by(ticker, date, broker_code).first()` check before insert — makes re-runs and date-overlap splits fully safe
- **Verification after scrape:** Always run `export_summary.yml` after all 4 batches → check tickers/day count
- **Zero records ≠ bug:** Check IDX holiday calendar first before investigating empty scrape results
- **`tickers` input for targeted backfill:** Use `tickers=NIKL,PTRO` style to scrape specific tickers without touching others
- **Batch 4 date-split pattern:** For full-quarter batch 4 runs, split into 2 date ranges (~45 days each) to stay within GitHub Actions 6-hour timeout

---

## 9. Constraints

- Cost: Rp 0/month target (GitHub Actions free tier)
- No paid data sources
- IDX: Lot = 100 shares, buy 0.15%, sell 0.25%, slippage 1 tick
- Universe: LQ45 + IDX SMC Liquid (109 unique tickers as of 2026-03-28)
- Stockbit token: Bearer JWT, ~24hr expiry, manual refresh required before each scrape session
- Always verify data with actual numbers — no assumptions
- GitHub file size limit: 25 MB per file (split files must stay under this)
- GitHub Actions timeout: 6 hours per job

### Runtime estimates for scrape_broker_summary.yml
- Per request: avg ~9 seconds (base 8s + random ±2–4s)
- Per batch (25 tickers) × 65 days (one quarter): ~4.1 hours
- Per batch (34 tickers, batch 4) × 65 days: ~5.5 hours — split into 2 date parts to be safe
- Targeted backfill (2 tickers × 128 days): ~37 minutes

---

## 10. Next Steps (in order)

### Backtesting with real broker data — NEXT UP
1. **Integrate real broker data into backtest** — replace synthetic foreign flow with real Asing `net_value` from `broker_summary` table in `backtest/engine.py`
2. **Re-run backtests with full 2025 real broker data** — compare results vs current synthetic baseline (2025: +60M, PF 1.38)
3. **Evaluate results:**
   - If improvement confirmed → proceed to 2024 backfill
   - If no improvement → tune signal logic first

### 2024 Backfill (only after 2025 backtest confirms improvement)
4. Backfill 2024 full year — all 4 batches, split into quarterly chunks:
   ```
   Q1: batches 1→2→3→4, 2024-01-01 to 2024-03-31
   Q2: batches 1→2→3→4, 2024-04-01 to 2024-06-30
   Q3: batches 1→2→3→4, 2024-07-01 to 2024-09-30
   Q4: batches 1→2→3→4, 2024-10-01 to 2024-12-31
   ```
   Batch 4 splits for each quarter:
   - Q1: Jan 1–Feb 15, Feb 15–Mar 31
   - Q2: Apr 1–May 15, May 15–Jun 30
   - Q3: Jul 1–Aug 15, Aug 15–Sep 30
   - Q4: Oct 1–Nov 15, Nov 15–Dec 31
5. Re-run backtests with 2024 + 2025 real broker data

### Integration & improvement
6. Integrate real broker data into `signal_combiner.py` — replace synthetic foreign flow with real Asing `net_value` from `broker_summary` table (live signals)
7. Fix 6–10 day stop-loss weak spot — 54 trades, 8% WR, -215M loss in this range. Use broker accumulation signal to decide whether to hold or exit
8. Update `daily_signals.yml` to include live broker scraping each day
9. Paper trade 1 month → go live
