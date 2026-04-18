# CLAUDE.md — Developer Context for AI Sessions

This file gives Claude Code (or any AI assistant) the context needed to continue work on this codebase without re-deriving everything from scratch.

---

## What This System Does

IDX swing trading signal bot for Indonesia Stock Exchange. Identifies stocks breaking 20-day resistance with volume confirmation, ranks signals by quality, and manages positions with trend-following exits.

**The system is profitable in 2024 and 2025. Do not introduce changes that make it unprofitable again.**

---

## Current State (Step 8 — 2026-04-18)

**Backtest results** (fresh Yahoo Finance data, synthetic FF):
- 2024: PF 1.40, +6.4% return, 36% WR, 75 trades
- 2025: PF 1.75, +14.9% return, 46% WR, 98 trades

**Key config values** (all in `config.py`):
```python
breakout_period = 20          # 20-day high (NOT 60)
max_entries_per_week = 6      # Rolling 10-day throttle (the Step 8 fix)
min_hold_days = 5             # Do NOT shorten to 3 (tested, caused -90M)
emergency_stop_pct = 0.12     # Do NOT tighten to 0.10 (tested, worsened)
circuit_breaker_losses = 0    # Disabled (tested, worsened due to cascade)
trend_threshold_pct = 0.15    # +15% triggers trend-follow mode
trend_exit_ma = 10            # Exit when close < MA10 in trend mode
partial_sell_fraction = 0.30  # Sell 30% at +15%
stop_loss_pct = 0.07          # -7% base stop
emergency_stop_pct = 0.12     # -12% emergency (fires even during hold)
```

---

## Architecture

```
main_backtest.py              Entry point: loads data, runs engine, saves reports
config.py                     Single source of truth for ALL parameters
signals/
  signal_combiner.py          Orchestrates: breakout + FF + ranking + hard filters
  technical.py                Computes all indicators (EMA, ATR, RSI, MACD, etc.)
  market_regime.py            IHSG regime: BULL/SIDEWAYS/BEAR via EMA + breadth
backtest/
  engine.py                   Event-driven loop: pending entries → exits → signals
  portfolio.py                Position sizing, stop management, exit conditions
  costs.py                    IDX commission (buy 0.15%, sell 0.25%) + tick sizes
  metrics.py                  Sharpe, Calmar, PF, WR, drawdown
database/
  schema.py                   SQLAlchemy ORM: daily_prices, foreign_flow, broker_summary, etc.
  data_loader.py              Loads data from DB into DataFrames
scraper/
  price_scraper.py            Yahoo Finance scraper, LQ45_TICKERS list (137 tickers)
  flow_scraper.py             Synthetic FF estimator + FundamentalScraper
reports/
  visualizer.py               equity curve, drawdown, heatmap charts
```

---

## Signal Pipeline (per stock, per day)

1. `TechnicalAnalyzer.compute_all_indicators()` — EMA, ATR, RSI, MACD, 52w high, price_vs_ma200, atr_pct, prior_return_5d
2. `_add_breakout_signals()` — close > 20d high, vol 1.5-5x, price ≥ 150, MA200 filter, ATR% filter
3. `_add_foreign_flow_signals()` — FF trend (cumulative + breakout-day check), KSEI 5d filter
4. `_add_accumulation_signals()` — broker accumulation score for hold extension
5. `_compute_signal_quality()` — composite percentile rank score for ranking
6. `_evaluate_signal()` — BUY if is_breakout and not BEAR; SELL if ff_consecutive_sell ≥ 5

---

## Exit Logic (priority order)

1. Emergency stop: loss > 12% at ANY time
2. Min hold: no regular stop for first 5 days (emergency still fires)
3. Trend mode (in_trend_mode=True after +15%): exit only when close < MA10
4. Stop loss: close < stop_price (after day 5); skip once if acc_score > 0 and day ≤ 10
5. Partial profit: sell 30% at +15% (once)
6. Time exit: day ≥ 15 AND gain < 3% AND close < MA10
7. FF exit: ff_consecutive_sell ≥ 5 AND (stock losing OR below MA10) AND is_foreign_driven
8. Regime exit: BEAR → close all

---

## What Was Tested and Failed (DO NOT RETRY WITHOUT NEW DATA)

| Change | Why Tested | What Happened |
|--------|-----------|---------------|
| min_hold 5→3 | Day 4-5 emergency stops cost -90M | 33 noise exits on day 4, WR 12%, net -90M |
| emergency_stop 12%→10% | Catch disasters earlier | Fires at recoverable dips, worsened both years |
| Circuit breaker CB(4,5) | Pause after 4 losses | +55M in simulation, worsened in backtest (cascade effect) |
| RSI 40-75 entry filter | Reduce bad entries | Blocks 84% of mega-winners (RSI < 40 at trough) |
| MACD > 0 entry filter | Same | Blocks 76% of mega-winners |
| Selling pressure candle filter | Reduce false entries | Blocked CUAN +511%, SMDR +117% on breakout day |
| 52w-high dist filter | Block structural decliners | All filters block some 2025 mega-winners |
| ATR% > 5% filter | Remove low-vol stocks | Blocks INET +80%, JARR +51%, ENRG +36%, DSNG +75% |
| IHSG momentum filters | Block entries in weak market | 2024 rallies fake, 2025 real — doesn't generalize |
| close > MA50 entry | Confirm uptrend | 68% of mega-winners have bearish MA alignment at trough |

---

## Key Architectural Decisions (Permanent)

| Decision | Rationale |
|----------|-----------|
| 20-day breakout (not 60d) | Catches 100% of mega-winners at median 13d after trough vs 34d for 60d |
| No RSI/MACD at entry | These indicators are LAGGING. At breakout troughs, both look terrible. |
| No FF at entry | FF at trough has Cohen's d = -0.0001. Zero predictive power. |
| min_hold=5 | Trades surviving 5 days have 49% WR vs 7% for days 1-5. |
| Trend exit for +15% | Lets position run to +65%, not forced out at +20% by trailing stop |
| MPW=6 throttle | Forces ranking to filter the worst signals; prevents false-breakout clusters |
| No hard position count | Capital is the real limit. With 12% max and 90% exposure: ~7-8 natural max. |
| Synthetic FF (not real broker) | KSEI scraping only covers 2025+. Synthetic works well enough for entry. |

---

## Data Sources

| Data | Source | Coverage |
|------|--------|----------|
| Price OHLCV | Yahoo Finance (`.JK` suffix) | 2020–present |
| IHSG index | Yahoo Finance (`^JKSE`) | 2020–present |
| Foreign flow (synthetic) | Estimated from price/volume in DB | Whatever is scraped |
| Broker summary (real) | Stockbit chartbit API (`--real-broker` flag) | 2025+ in DB |
| KSEI net flow | Stockbit chartbit (fitemid=3194) | 2025-01-02 to present |

**2024 KSEI data is missing** — this is a known gap. Scraping it would improve 2024 results further (KSEI filter blocks 50 bad trades/yr with 22% WR, 0 BW lost).

---

## GitHub Actions Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `analyze_trade_log.yml` | Manual | Run backtest + full trade log analysis. Use this for research. |
| `run_backtest.yml` | Manual | Run backtest, save equity curve + trade log artifacts |
| `daily_signals.yml` | Cron 16:35 WIB | Daily signal + Telegram notification |
| `initial_scrape.yml` | Manual | One-time full data scrape |
| `bootstrap_database.yml` | Manual | DB setup |
| `scrape_broker_summary.yml` | Manual | Backfill Stockbit broker data |
| `upload_database.yml` | Manual | Upload DB as artifact for use in other workflows |
| `monthly_optimise.yml` | Cron monthly | Walk-forward parameter optimisation |

---

## Next Priorities (as of 2026-04-18)

1. **Scrape KSEI 2024 foreign flow data** — Stockbit chartbit API, `fitemid=3194`, date range 2024-01-01 to 2024-12-31. Store in `foreign_flow` table. Expected: further improve 2024 by blocking ~50 more bad trades.
2. **fp_ratio exploration** — Prior KSEI analysis showed high-fp stocks lose (23.7% WR), low-fp win (53.5% WR). Test as entry filter. Data is in DB.
3. **Real broker data backtest** — Run `--real-broker` for 2024+2025 to see if Asing accumulation signals improve results.
4. **2021-2022 regime problem** — These years remain unprofitable (PF 0.46-0.71). The breakout strategy needs trending conditions. May require a separate strategy for confirmed BEAR regimes.

---

## Running a Backtest

```bash
# Fresh scrape + backtest
python main_backtest.py --scrape --start 2024-01-01 --end 2024-12-31 --output reports_2024

# Without scrape (uses cached DB data)
python main_backtest.py --start 2024-01-01 --end 2024-12-31

# With real broker data
python main_backtest.py --scrape --real-broker --start 2025-01-01 --end 2025-12-31
```

Reports saved to `--output` dir: `metrics_summary.txt`, `trade_log.csv`, PNG charts.

---

## Handoff Documents

Session handoff docs are in the root directory: `HANDOFF_SESSION_YYYY_MM_DD_vNN.md`

Most recent: `HANDOFF_SESSION_2026_04_18_v29.md` — Step 7+8 consolidated.

Each doc covers: what changed, why it was changed, what was tested and failed, current results, and next steps. **Read the latest one before making any changes.**

---

## AI Assistant Operating Rules

These rules exist because violations caused near data loss in the past.

**RULE 0 — Read before you answer**
Never answer questions about workflow behaviour, data safety, file interactions, or code logic without first reading the actual files. The sequence for every question: (1) identify relevant files, (2) read them, (3) answer based on what code ACTUALLY does.

**RULE 1 — Workflow parallelism: default is SEQUENTIAL**
Before saying two workflows are safe to run in parallel, verify by reading both files:
- Do they restore the same artifact? → SEQUENTIAL ONLY
- Do they write to the same DB tables? → SEQUENTIAL ONLY
- Do they upload to the same artifact name? → SEQUENTIAL ONLY

Known shared artifact `idx-database`: written by `scrape_broker_summary.yml`, `initial_scrape.yml`, `bootstrap_database.yml`, `daily_signals.yml` — NONE may run in parallel with each other.

**RULE 2 — Data safety is non-negotiable**
Historical broker data takes weeks to re-scrape, Stockbit token expires every 24h, GitHub Actions has limited runtime. Data loss is unrecoverable. Before any operation touching the DB or artifacts: read the code, identify all reads/writes, confirm no conflicts.

**RULE 3 — No speculation, only verified facts**
Arie is data-driven and catches speculation immediately. If uncertain, say so and read the code first. Never present assumptions as facts.
- BAD: "The scraper probably uses upsert so duplicates won't occur"
- GOOD: "Let me check scraper/flow_scraper.py to confirm"

**RULE 4 — Backtest changes must not bleed into live code**
Live signals run from `main`. Experiments must be isolated to feature branches or disabled via config flags. Never modify live signal logic as a "quick test".

**RULE 5 — Locked parameters (never change without backtest data)**
These have been tested extensively. Do not change without running a full 2024+2025 backtest to verify:
- `min_hold_days = 5` (tested 3, caused -90M noise exits)
- `emergency_stop_pct = 0.12` (tested 0.10, worsened both years)
- `circuit_breaker_losses = 0` (disabled — cascade effect worsens results)
- `breakout_period = 20` (tested 60, misses mega-winners by 21 days)
- `max_entries_per_week = 6` (tested 3/5/7/8/10 — 6 is the sweet spot)

**RULE 6 — GitHub Actions patterns**
- Always gate artifact upload on a data count check (never overwrite with empty DB)
- Never restore artifact without `GH_TOKEN` (silently fails)
- `dawidd6/action-download-artifact@v6` with `if_no_artifact_found: warn` + `continue-on-error: true` is the correct pattern for optional artifacts
