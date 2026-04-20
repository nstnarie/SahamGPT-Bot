# CLAUDE.md — Developer Context for AI Sessions

This file gives Claude Code (or any AI assistant) the context needed to continue work on this codebase without re-deriving everything from scratch.

---

## What This System Does

IDX swing trading signal bot for Indonesia Stock Exchange. Identifies stocks breaking 20-day resistance with volume confirmation, ranks signals by quality, and manages positions with trend-following exits.

**The system is profitable in 2024 and 2025. Do not introduce changes that make it unprofitable again.**

---

## Current State (Step 13 — 2026-04-19)

**Backtest results** (real Asing broker data, all filters + pyramiding active):

| Year | Return | PF | WR | Trades | Max DD | Source |
|------|--------|----|----|--------|--------|--------|
| 2024 | +17.77% | 2.32 | 47.8% | 46 | -6.70% | Local (real broker data) ✅ |
| 2025 | +40.97% | 4.18 | 59.6% | 52 | -7.44% | Local (real broker data) ✅ |
| 2024 CI | pending | — | — | — | — | GitHub CI (no broker DB) |
| 2025 CI | pending | — | — | — | — | GitHub CI (no broker DB) |

IHSG 2024: -3.33% | IHSG 2025: +20.71%

**Three active entry filters** (all in `EntryFilterConfig`):
1. **fp_ratio < 0.40** (Step 10): blocks high-fp stocks (BBCA, BMRI, BBRI, TLKM). Falls back to `fp_ratios.json` in CI.
2. **breakout_strength >= -8%** (Step 11): blocks extreme overnight gap-downs at entry (T+1). 0 direct BW blocked cross-year.
3. **combined BS/TBA** (Step 11): blocks entry when `breakout_strength < 0 AND top_broker_acc < 0`. BS-/TBA- quadrant has 0 direct BW in 2024+2025. No-op in CI (TBA=0 when broker DB absent).

**Pyramiding** (Steps 12-13, `PyramidConfig`):
- Adds to positions already in trend mode (+15%)
- Trigger: new breakout signal (volume-confirmed) OR new 20-day high (Step 13, no vol req)
- Max 2 adds per position, each 50% of original size
- Stop ratchets up after each add to protect new capital
- Step 13 rationale: grinders like PTRO (+42%, 40d, 2024) never triggered vol-based adds
- Key drivers: INET +107% (145M), RAJA +35% (50M), JARR +50% (59M)

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
# Entry filters
min_breakout_strength = -8.0  # Block extreme gap-downs at entry
use_breakout_strength_filter = True
use_combined_bs_tba_filter = True  # Block BS-/TBA- quadrant
# Pyramiding
enable_pyramiding = True
max_adds = 2
add_size_fraction = 0.50
use_new_high_trigger = True   # Step 13: pyramid on new 20d high (no vol req)
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
  flow_scraper.py             FundamentalScraper only — synthetic FF removed
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
| SIDEWAYS mult = 1.0 | Allow more exposure in sideways | PF 1.34→1.14, DD doubled to -12.54% (2024) |
| partial_sell = 0.0 | Let winners run longer | Big winners 14→8, WR -7pts both years |
| breakout_strength >= 0 filter | Only enter above breakout | Blocks 50% of big winners (gap-down recovery trades) |
| Composite score recalibration | Fix broken Q5 ranking | Zero effect — MPW=6 throttle never binds (max 4 signals/day) |

---

## Key Architectural Decisions (Permanent)

| Decision | Rationale |
|----------|-----------|
| 20-day breakout (not 60d) | Catches 100% of mega-winners at median 13d after trough vs 34d for 60d |
| No RSI/MACD at entry | These indicators are LAGGING. At breakout troughs, both look terrible. |
| No FF at entry | FF at trough has Cohen's d = -0.0001. Zero predictive power. |
| min_hold=5 | Trades surviving 5 days have 49% WR vs 7% for days 1-5. Step 10 re-tested min_hold=3 with real data: day-4 cliff (-132M) worse than day-6 (-126M), TREND_EXIT 16→9 trades. |
| fp_ratio < 0.40 | Step 10: low-fp stocks = 52% WR, +117.7M; high-fp = 32% WR, -100M. High-fp stocks are macro hedge vehicles (BBCA, BMRI, BBRI, TLKM) — breakouts are foreign flow noise, not accumulation. |
| BS >= -8% at entry | Step 11: quick failures average BS=-3.1% to -4.8% (enter below breakout). -8% threshold blocks extreme gap-downs (4 trades/year, 0 BW lost directly). |
| Block BS-/TBA- quadrant | Step 11: when breakout faded (BS<0) AND big money selling (TBA<0), 0 BW in either year. 11+9 trades blocked, all losers directly. No-op in CI. |
| Composite score is no-op | Step 11: MPW=6 throttle never binds — max 4 signals/day observed. Ranking order is irrelevant. Do not tune weights. |
| Trend exit for +15% | Lets position run to +65%, not forced out at +20% by trailing stop |
| MPW=6 throttle | Forces ranking to filter the worst signals; prevents false-breakout clusters |
| No hard position count | Capital is the real limit. With 12% max and 90% exposure: ~7-8 natural max. |
| Real Asing FF (not synthetic) | broker_summary has 2.6M rows (2024-2025, 137 tickers). Pre-aggregated into foreign_flow for fast loading. Synthetic is gone. |
| Lean split file | idx_broker_part_a.db (4.8MB) contains pre-aggregated foreign_flow (72k rows). Workflows restore from this instead of merging 2×100MB broker_summary files. |

---

## Data Sources

| Data | Source | Coverage |
|------|--------|----------|
| Price OHLCV | Yahoo Finance (`.JK` suffix) | 2020–present |
| IHSG index | Yahoo Finance (`^JKSE`) | 2020–present |
| Foreign flow (real Asing) | Pre-aggregated from broker_summary into foreign_flow table | 2024-01-02 to present |
| Broker summary (raw) | Stockbit chartbit API | 2023-01-01 to present (2.6M rows 2024-2025 + 2023 scrape in progress, 137 tickers) |
| KSEI net flow | Stockbit chartbit (fitemid=3194) | 2024-2025 (stored in foreign_flow) |

**Architecture**: `broker_summary` (raw Stockbit data) → aggregated into `foreign_flow` (net Asing per ticker/day) → used by backtest and daily signals.

**Split file**: `idx_broker_part_a.db` (4.8MB, committed to repo) contains pre-aggregated `foreign_flow` only. GitHub workflows restore from this instead of committing the full 450MB broker_summary.

**No synthetic data anywhere**: `estimate_and_store()` is fully removed from both `main_backtest.py` and `main_daily.py`. The `upsert_foreign_flow()` function overwrites existing rows — synthetic was silently replacing real data on every daily run. That bug is now fixed.

**When no FF data exists for a ticker** (e.g., data gap): the signal pipeline treats it as a domestic stock with no FF signal — no FF filters applied, no fake values injected.

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

## Next Priorities (as of 2026-04-20)

### ⚠️ MANDATORY — Pre-compute `top_broker_acc` daily CSV for GitHub

**Problem**: Daily signal runs on GitHub with no access to `idx_swing_trader.db`. Result:
- `top_broker_acc = 0` for all tickers → BS/TBA combined filter is a **no-op in live signals**
- BS-/TBA- losers (~19% WR, 0 BW) pass through unfiltered to Telegram
- Live signal quality is lower than what the local backtest shows

**Fix**: Pre-compute `top_broker_acc` per ticker per day from local DB → save as `broker_acc_daily.csv` → commit to repo. Engine loads it as fallback when broker DB absent (same pattern as `fp_ratios.json`).

**Files to touch**: `database/data_loader.py` (pre-compute script), `backtest/engine.py` (load CSV fallback), `signals/signal_combiner.py` (inject into sig_df).

**Do this before trusting live Telegram signals.**

---

### Step 15: Raise volume_spike_max and fp_ratio threshold (pending experiments)

**Root cause found (Step 14 signal funnel analysis)**: 49/66 mega winners in 2024 never generate a signal. Two filters are over-blocking:

1. **`volume_spike_max = 5.0`** — blocks 41/66 mega winners. Mega winner trough breakouts ARE high-volume (TINS=11.5x, NIKL=12.6x, JARR=13.7x). The pump-and-dump cap is too conservative.
   - Experiment: raise to `10.0`
   - File: `config.py:BreakoutConfig.volume_spike_max`

2. **`fp_ratio >= 0.40`** — blocks 36/66 mega winners. Real hedge vehicles have fp > 0.70 (BBCA=0.82, BMRI=0.78). Threshold over-fires on legitimate mega winners (TPIA+250% fp=0.525, BREN+182% fp=0.549, BRIS+96% fp=0.462).
   - Experiment: raise to `0.55`
   - File: `config.py:EntryFilterConfig.max_fp_ratio`

**TINS case confirmed**: March 8 2024 breakout was 11.5x volume (user was right). Blocked by vol_too_high (>5x) AND fp_ratio (0.403). Had 12 near-breakout days, ALL blocked.

Run both 2024 + 2025 for each experiment. Accept only if both improve or one improves / other neutral.

---

### 2023 Broker Summary Scrape (in progress)

**Confirmed**: Stockbit has 2023 data (BBRI Q4 2023 test = 3,711 records).
**Plan**: 4 quarters × 4 batches = 16 sequential runs (one quarter at a time, batch=25 tickers, to stay under 6h GitHub limit).
**Status**: Batch 1 Q1 2023 running (run 24644173063). Continue sequentially until all 16 runs complete.
**Purpose**: Enables 2023 backtest validation — verify filters + pyramiding don't worsen pre-2024 regimes.

```bash
# Template for triggering next run:
gh workflow run scrape_broker_summary.yml \
  --field start_date="2023-01-01" \
  --field end_date="2023-03-31" \
  --field batch="2" \
  --field tickers=""
```

---

### Research / Optional

1. **2021-2023 validation** — Run backtests after 2023 broker data scrape is complete.
2. **Rolling fp_ratio** — Current `fp_ratios.json` uses full 2024-2025 data (minor lookahead bias for 2024 backtest).

---

## Running a Backtest

```bash
# Fresh scrape + backtest (prices only — broker data must be scraped separately)
python main_backtest.py --scrape --start 2024-01-01 --end 2024-12-31 --output reports_2024

# Without scrape (uses cached DB data — recommended when DB already populated)
python main_backtest.py --start 2024-01-01 --end 2024-12-31
```

Note: `--real-broker` flag has been removed. Real Asing data is always used (from `foreign_flow` table).

Reports saved to `--output` dir: `metrics_summary.txt`, `trade_log.csv`, PNG charts.

---

## Handoff Documents

Session handoff docs are in the root directory: `HANDOFF_SESSION_YYYY_MM_DD_vNN.md`

Most recent: `HANDOFF_SESSION_2026_04_19_v34.md` — Step 12: pyramiding merged. Local returns +14.40%/+39.53%, PF 2.06/4.07.

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

**RULE 7 — No synthetic data, ever**
`estimate_and_store()` is removed from all entry points. `upsert_foreign_flow()` overwrites existing rows — never call it with synthetic/estimated data. The only source of foreign flow data is real Stockbit broker_summary aggregated into foreign_flow. If a ticker has no foreign_flow data, it runs without FF signals (not with fake ones).
