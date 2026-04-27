# CLAUDE.md — Developer Context for AI Sessions

This file gives Claude Code (or any AI assistant) the context needed to continue work on this codebase without re-deriving everything from scratch.

---

## What This System Does

IDX swing trading signal bot for Indonesia Stock Exchange. Identifies stocks breaking 20-day resistance with volume confirmation, ranks signals by quality, and manages positions with trend-following exits.

**The system is profitable in 2024 and 2025. Do not introduce changes that make it unprofitable again.**

---

## Current State (Step 25 — 2026-04-27)

**Backtest results** (real Asing broker data, ff-corr filter, sector override ON, liquidity filter ON, pyramid T+1 ON, max_adds=5, conditional cash reserve floor=10%):

| Year | Return | PF | WR | Trades | Max DD | Sharpe | Source |
|------|--------|----|----|--------|--------|--------|--------|
| 2023 | +90.5% | 2.20 | 40.9% | 66 | -10.35% | 2.51 | Local ✅ |
| 2024 | +25.8% | 2.95 | 52.0% | 75 | -11.45% | 1.08 | Local ✅ |
| 2025 | +146.6% | 12.21 | 68.5% | 73 | -37.45% | 2.17 | Local ✅ |

IHSG 2023: +6.16% | IHSG 2024: -3.33% | IHSG 2025: +20.71%

Reports: `reports_step25c_floor0.10_2023/`, `reports_step25c_floor0.10_2024/`, `reports_step25c_floor0.10_2025/`

**Note — Step 25 vs Step 24 comparison:**

| Year | Step 24 (prev baseline) | Step 25 (current) | Delta |
|------|-------------------------|-------------------|-------|
| 2023 | +102.7% | +90.5% | −12.2pp |
| 2024 | +25.8% | +25.8% | 0 |
| 2025 | +66.4% | +146.6% | **+80.2pp** |

2025 Max DD increased to −37.45% (from −16.13%): JARR's large position creates equity
swings during the Aug–Oct hold. This is unrealized-gain drawdown, not loss drawdown.

**Step 25: Conditional cash reserve floor** (`cash_reserve_floor = 0.10`):
Pyramid adds are floor-constrained only on days when new entry signals were queued the
previous day (`new_entries_queued` flag in engine.py). When no entries are competing, adds
run freely — preserving CUAN/PANI compounding in 2023. When entries are pending, adds are
blocked if they'd drop cash below 10% of portfolio — reserving cash for the new entry.
Key fix: JARR 2025 now enters Aug 21 at 1065 (correct day), exits Oct 17 at 4275 = +869M.
vs Step 24 cascade: entered Aug 27 at 1345, stopped out Sep 12 at 1610 = +11M.
2024 is completely unaffected — pyramid adds rarely compete with new entries in 2024.

**Step 19: Liquidity filter** (`min_avg_daily_value = 0.5B IDR`):
Blocks stocks with 20-day rolling avg daily value (close × volume) below Rp 500M.
Applied at signal generation time in `_add_breakout_signals()`. Enforces the existing
(but previously dead) `UniverseConfig.min_avg_daily_value` config field.
Tested 0.5B vs 1B: 0.5B preserves BALI, blocks only truly untradeable stocks (ARGO 0.04B,
DSSA early-2024 0.18B, AGII 0.28B). Zero big winners blocked at 0.5B across all 3 years.
2024 drops -3.4pp (was -6.7pp at 1B); 2023 unchanged; 2025 +0.4pp.

**Step 18: ff-price correlation filter replaces fp_ratio** (`ff_corr_ratios.json`):
Previously blocked 61 stocks by volume participation (fp >= 0.45). Now blocks 18 stocks
by actual price influence (Pearson correlation of daily return vs net foreign flow >= 0.30).
Stocks like DSSA (+504%), TPIA (+229%), BREN (+153%), AMMN (+105%) are now allowed.
Blocked (corr >= 0.30): BBRI, BBCA, BMRI, AMAN, ANTM, PSAB, ASII, BBNI, PGAS, UNVR,
TLKM, BRIS, GOTO, PTPP, GJTL, UNTR, INDF, DEWA.

**Step 17: Sector override ON** (`use_sector_override: True`):
Allows entries in blocked sectors (Consumer Cyclical, Financial Services, Industrials)
when breakout_strength > 5% AND vol_ratio > 3x. Added HRTA as BW in 2023.

**Step 20: `block_entry_on_ff_consecutive_sell` config flag** (`ForeignFlowConfig`):
Makes existing ff_consecutive_sell BUY-blocking behaviour configurable. `True` = baseline (block BUY when ff_consecutive_sell >= 5). Setting to `False` removes the redundant BUY blocker while FF_EXIT protection for existing positions remains active. Tested `False` in Step 20: JARR 2024 entered but net -3.2M due to pyramid add raising cost basis and brief spike. 2024: −1.08pp. Rejected — `True` is baseline.

**Six active signal/entry filters:**
1. **avg_daily_value_20d >= 0.5B** (Step 19): blocks illiquid stocks at signal generation. Source: `UniverseConfig.min_avg_daily_value`. Applied in `signal_combiner.py`.
2. **ff_corr < 0.30** (Step 18): blocks stocks where foreign flow drives the price. Source: `ff_corr_ratios.json`. Applied at T+1 engine entry.
3. **breakout_strength >= -8%** (Step 11): blocks extreme overnight gap-downs at entry (T+1). 0 direct BW blocked cross-year.
4. **combined BS/TBA** (Step 11): blocks entry when `breakout_strength < 0 AND top_broker_acc < 0`. 0 BW in 2024+2025. No-op in CI.
5. **MA200+BS combined** (Step 15): blocks when `price_vs_ma200 ∈ [0,10%) AND breakout_strength < 0`. 43 trades blocked (3-yr), 20.9% WR, 0 BW, -103.8M PnL.
6. **Sector filter + override** (Step 16/17): blocks Consumer Cyclical, Financial Services, Industrials — but allows when BS > 5% AND vol > 3x.

**Pyramiding** (Steps 12-13-24, `PyramidConfig`):
- Adds to positions already in trend mode (+15%)
- Trigger: new breakout signal (volume-confirmed) OR new 20-day high (Step 13, no vol req)
- Max 5 adds per position (Step 24: raised from 2), each 50% of original size
- Stop ratchets up after each add to protect new capital
- Execution: T+1 open (Step 24: was same-day open — unrealistic as signal is known only at close)
- Step 13 rationale: grinders like PTRO (+42%, 40d, 2024) never triggered vol-based adds
- ⚠️ Cascade risk: with max_adds=5, extra capital in existing winners can block new entries

**Key config values** (all in `config.py`):
```python
breakout_period = 20          # 20-day high (NOT 60)
max_entries_per_week = 6      # Rolling 10-day throttle (the Step 8 fix)
min_hold_days = 5             # Do NOT shorten to 3 (tested, caused -90M)
emergency_stop_pct = 0.12     # Do NOT tighten to 0.10 (tested, worsened)
circuit_breaker_losses = 0    # Disabled (tested, worsened due to cascade)
trend_threshold_pct = 0.15    # +15% triggers trend-follow mode
trend_exit_ma = 10            # Exit when close < MA10 in trend mode
trend_exit_ma_big_winner = 20 # Step 16: wider MA20 for positions >= +30%
trend_big_winner_threshold = 0.30  # gain threshold to switch to MA20
partial_sell_fraction = 0.30  # Sell 30% at +10% (Step 16: was +15%)
partial_target_pct = 0.10     # Step 16: lowered from 0.15
stop_loss_pct = 0.07          # -7% base stop
emergency_stop_pct = 0.12     # -12% emergency (fires even during hold)
# Entry filters
min_breakout_strength = -8.0  # Block extreme gap-downs at entry
use_breakout_strength_filter = True
use_combined_bs_tba_filter = True  # Block BS-/TBA- quadrant
use_sector_filter = True      # Step 16: block CC, FS, Industrials
# Liquidity
min_avg_daily_value = 500_000_000  # Step 19: Rp 0.5B 20d rolling avg daily value
# Pyramiding
enable_pyramiding = True
max_adds = 5                  # Step 24: raised from 2 (benefits 2023 +54pp, hurts 2025 -61pp)
add_size_fraction = 0.50
use_new_high_trigger = True   # Step 13: pyramid on new 20d high (no vol req)
pyramid_t1_execution = True   # Step 24: T+1 open (realistic — signal known only at close)
cash_reserve_floor = 0.10    # Step 25: conditional floor — only active when new_entries_queued
# Sizing
min_entry_fraction = 0.0     # Step 25: disabled — shares>=100 check suffices
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

1. `TechnicalAnalyzer.compute_all_indicators()` — EMA, ATR, RSI, MACD, 52w high, price_vs_ma200, atr_pct, prior_return_5d, avg_daily_value_20d
2. `_add_breakout_signals()` — close > 20d high, vol 1.5-5x, price ≥ 150, avg_daily_value_20d ≥ 0.5B, MA200 filter, ATR% filter
3. `_add_foreign_flow_signals()` — FF trend (cumulative + breakout-day check), KSEI 5d filter
4. `_add_accumulation_signals()` — broker accumulation score for hold extension
5. `_compute_signal_quality()` — composite percentile rank score for ranking
6. `_evaluate_signal()` — BUY if is_breakout and not BEAR; SELL if ff_consecutive_sell ≥ 5

---

## Exit Logic (priority order)

1. Emergency stop: loss > 12% at ANY time
2. Min hold: no regular stop for first 5 days (emergency still fires)
3. Trend mode (in_trend_mode=True after +15%): adaptive exit — MA10 for normal, MA20 for gain >= 30% (Step 16)
4. Stop loss: close < stop_price (after day 5); skip once if acc_score > 0 and day ≤ 10
5. Partial profit: sell 30% at +10% (Step 16: was +15%)
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
| volume_spike_max 5→10 | Unblock high-volume mega winners | 2024: +10.64%→+5.69%, PF 1.57→1.27. Only 4 new mega winner tickers genuinely unblocked — the other "41 blocked" were also blocked by fp/price/ma200. |
| fp_ratio 0.45→0.50 | Unblock mid-fp mega winners | 2024: +10.64%→+0.06%, PF 1.57→1.02. High-fp trades are net losers. |
| fp_ratio 0.45→0.55 | Same, more aggressive | 2024: -9.67%, PF 0.65. Catastrophic. |
| fp 0.50 + MA200_BS filter | Compensate for extra losers | 2024: +6.31%, PF 1.32. New filter can't fix bad fp threshold. |
| MA20 for all trend exits | More room for all winners | WR drops to 40.8/61.3/68.2%, DD -32.8%. Too wide for small winners. |
| MA10 2-day confirmation | Reduce false trend exits | Slightly better return (+134%) but WR drops, doesn't help enough. |
| MA10 3-day confirmation | Same | Even less effect, WR same as baseline. |
| MPW 6→8 (rolling 10d) | Capture throttled signals (BRPT) | 2023 -2.4pp, 2024 -10.4pp, 2025 -11pp. Extra trades are lower-quality false breakouts. MPW=6 is confirmed sweet spot. |
| Block 500–999 price range | 500-999 bucket has PF 0.51, 0 big winners | Cascade removes JARR +219% and PTRO +30% via capital/throttle effects. 2025: -61pp. Do not implement. |
| Prior avg daily value ≥ 2B | Block event-spike stocks like DMAS | Blocks HRTA +34% as collateral at every threshold tested (1B–5B). Net effect neutral or negative. |
| 52-week historical resistance breakout | Buy only stocks breaking annual highs | 2023 -16.9pp, 2024 +3pp, 2025 -46pp. Blocks PANI +90% (2023), INET +90%/TINS +96%/BRPT +69% (2025). Mega-winners break out below their prior-year high. |
| block_entry_on_ff_consecutive_sell → False | JARR 2024 was blocked by ff_cs=9 on breakout day | JARR entered but net -3.2M. Pyramid add raised cost basis; brief spike resolved via time exit. 2024: −1.08pp. Rejected. |
| Unconditional cash reserve floor (Step 25 attempt) | Fix JARR cascade without conditional logic | floor=0.10: 2025 +153% but 2023 −44pp. Floor throttles ALL adds including CUAN/PANI compounding. Too blunt. |
| Target-based add sizing (Step 25 attempt) | Undersized entries catch up via flat adds | Breaks 2023 compounding: CUAN adds were exponentially growing (pos.shares×0.5); flat 6% per add caps total position at 42% vs 91%. Reverted. |
| min_entry_fraction=0.05 (Step 25 attempt) | Skip trivially small positions | Blocks entries when portfolio equity has grown (5% of 2B = 100M min, but cash may be 90M). 2023: +30% vs +103%. Disabled (set to 0.0). |
| trend_threshold_pct 0.15→0.10 (Step 21) | Earlier trend mode = earlier pyramid + MA trail; lower pyramid trigger | Monotonic trade-off: 2023 +16.3pp, 2024 −8.3pp, 2025 −4.6pp. 2023 TREND_EXIT 10→15 trades (+145M). 2024 REGIME_EXIT halved (+148M→+78M) — positions exit via MA10 break before regime changes. No cross-year sweet spot. |
| trend_threshold_pct 0.15→0.12 (Step 23) | Compromise between 0.10 and 0.15 | 2023 +2.2pp, 2024 −3.9pp, 2025 −0.9pp. Same direction as Step 21, smaller magnitude. Confirms monotonic relationship — no threshold between 0.10–0.15 helps both years. |
| Separate pyramid trigger at +10% (Step 22) | Decouple pyramid from trend exit — add earlier without changing MA trail | 2023 −5pp, 2024 −2.4pp, 2025 −12pp. Pyramid adds without trend-mode protection raise stop price; pullback triggers raised stop at worse level. Rejected. |
| Pyramid same-day execution (pre-Step 24) | Original design: execute pyramid add at today's open | Unrealistic — signal is confirmed at close, today's open is already in the past. T+1 is the only real-world model. Same-day was slightly optimistic in backtests. |

---

## Key Architectural Decisions (Permanent)

| Decision | Rationale |
|----------|-----------|
| 20-day breakout (not 60d) | Catches 100% of mega-winners at median 13d after trough vs 34d for 60d |
| No RSI/MACD at entry | These indicators are LAGGING. At breakout troughs, both look terrible. |
| No FF at entry | FF at trough has Cohen's d = -0.0001. Zero predictive power. |
| min_hold=5 | Trades surviving 5 days have 49% WR vs 7% for days 1-5. Step 10 re-tested min_hold=3 with real data: day-4 cliff (-132M) worse than day-6 (-126M), TREND_EXIT 16→9 trades. |
| ff_corr < 0.30 | Step 18: replaces old fp_ratio < 0.45. Blocks stocks where foreign flow *actually drives* the price (Pearson corr of daily return vs net foreign flow). fp_ratio measured volume participation — wrong signal. DSSA/TPIA/BREN/AMMN had high fp but low corr, meaning foreigners trade them but don't move them. Now only 18 stocks blocked vs 61 before. Source: `ff_corr_ratios.json`. |
| BS >= -8% at entry | Step 11: quick failures average BS=-3.1% to -4.8% (enter below breakout). -8% threshold blocks extreme gap-downs (4 trades/year, 0 BW lost directly). |
| Block BS-/TBA- quadrant | Step 11: when breakout faded (BS<0) AND big money selling (TBA<0), 0 BW in either year. 11+9 trades blocked, all losers directly. No-op in CI. |
| Composite score is no-op | Step 11: MPW=6 throttle never binds — max 4 signals/day observed. Ranking order is irrelevant. Do not tune weights. |
| Trend exit for +15% | Lets position run to +65%, not forced out at +20% by trailing stop |
| Adaptive MA10/MA20 | Step 16: MA10 for normal trend positions, MA20 for gain >= 30%. Gives mega-winners room through pullbacks. +238% total 3yr (was +126%). DD -30.9% in 2025 is from unrealized gains on mega-winners, not losses. |
| Sector block (CC/FS/Ind) | Step 16: 0 big winners across 3 years in these sectors. ~66 trades blocked, all losers or small winners. |
| PP@10% (was 15%) | Step 16: locks in partial profit earlier. Converts borderline losers to small winners. |
| MPW=6 throttle | Forces ranking to filter the worst signals; prevents false-breakout clusters |
| No hard position count | Capital is the real limit. With 12% max and 90% exposure: ~7-8 natural max. |
| Real Asing FF (not synthetic) | broker_summary has 2.6M rows (2024-2025, 137 tickers). Pre-aggregated into foreign_flow for fast loading. Synthetic is gone. |
| Lean split file | idx_broker_part_a.db (4.8MB) contains pre-aggregated foreign_flow (72k rows). Workflows restore from this instead of merging 2×100MB broker_summary files. |
| Liquidity filter 0.5B | Step 19: blocks stocks with 20d avg daily value < Rp 500M at signal time. Zero big winners blocked across 3 years. Tested 1B (too aggressive, -6.7pp in 2024), settled on 0.5B (only blocks truly untradeable stocks like ARGO 0.04B). |
| Pyramid T+1 + max_adds=5 | Step 24: T+1 is the only realistic execution model. max_adds=5 lets mega-winners compound further. Trade-off: extra adds consume cash, can block new mega-winner entries (JARR cascade: entered 6d late → exited at 1610 instead of 4275 = −542M in 2025). Next priority: rebalancing to reserve cash for new entries. |

---

## Data Sources

| Data | Source | Coverage |
|------|--------|----------|
| Price OHLCV | Yahoo Finance (`.JK` suffix) | 2020–present |
| IHSG index | Yahoo Finance (`^JKSE`) | 2020–present |
| Foreign flow (real Asing) | Pre-aggregated from broker_summary into foreign_flow table | 2024-01-02 to present |
| Broker summary (raw) | Stockbit chartbit API | 2023-01-01 to present (2.6M rows 2024-2025 + 1.3M rows 2023, 137 tickers) ✅ |
| Foreign flow (2023) | Aggregated from 2023 broker_summary | 2023-01-01 to 2023-12-31, 96% coverage ✅ |
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

## Next Priorities (as of 2026-04-27)

### Step 25 Baselines (2026-04-27)

Conditional cash reserve floor (floor=0.10) implemented. Results:

| Year | Return | PF | WR | Trades | Max DD | Sharpe |
|------|--------|----|----|--------|--------|--------|
| 2023 | +90.49% | 2.20 | 40.9% | 66 | -10.35% | 2.51 |
| 2024 | +25.83% | 2.95 | 52.0% | 75 | -11.45% | 1.08 |
| 2025 | +146.58% | 12.21 | 68.5% | 73 | -37.45% | 2.17 |

Reports: `reports_step25c_floor0.10_2023/`, `reports_step25c_floor0.10_2024/`, `reports_step25c_floor0.10_2025/`

**2024 observation**: 2024 return is completely unaffected by any pyramid/floor change tested.
Pyramid adds rarely compete with new entries in 2024 — the floor never meaningfully bites.
2024 is a reliable sanity check: changes to pyramid mechanics should leave it near +25.8%.

---

### 🔴 #1 PRIORITY — Investigate 2023 −12pp loss from conditional floor

**Problem**: Step 25 floor=0.10 costs 2023 −12.2pp (102.7% → 90.5%) even with the
conditional logic. Expected: CUAN/PANI adds should run freely when no new entries compete.
Actual: some adds are still blocked, suggesting new entry signals do co-occur with pyramid
add days on the 2023 mega-winners.

**Goal**: Understand which 2023 adds were blocked and why. Is this unavoidable (genuine
competition between a new entry and a CUAN add on the same day), or is there a refinement
that preserves both?

Do NOT start analysis without Arie's explicit go-ahead.

---

### ⚠️ MANDATORY — Pre-compute `top_broker_acc` daily CSV for GitHub

---

### ⚠️ MANDATORY — Pre-compute `top_broker_acc` daily CSV for GitHub

Daily signal runs on GitHub with no broker DB. BS/TBA combined filter is a no-op in live signals
(84 signals blocked in backtest but all pass through in live). Fix: pre-compute `top_broker_acc`
per ticker/day → `broker_acc_daily.csv` → commit to repo.

**Files to touch**: `database/data_loader.py`, `backtest/engine.py`, `signals/signal_combiner.py`.

---

### Mega Winner Analysis — Complete (2026-04-26)

Ran `scripts/identify_mega_winners.py` extended for 2023. Output: `mega_winners_analysis.xlsx`.
Definition: trough-to-peak drawup > 50% AND avg daily value >= Rp 1B/day.

| Year | Total >50% | Liquid (≥1B/day) | #1 performer |
|------|-----------|------------------|--------------|
| 2023 | 56 | 52 | CUAN +5,629% |
| 2024 | 66 | 53 | PTRO +644% |
| 2025 | 99 | 87 | JARR +3,100% |

Cross-reference `mega_winners_analysis.xlsx` against `trade_log.csv` (Step 24 reports) to compute
capture rate and identify which mega winners were missed and why.

---

### Research / Optional

1. **fp_ratios.json** — Needs regeneration with 2023-2025 data for CI compatibility.
2. **2021-2022 validation** — Run backtests for earlier years once price data confirmed.
3. **SIDEWAYS regime stop-loss pattern** — All 34 stop-losses in 2023 and all 6 emergency stops in 2024 are SIDEWAYS regime. 71% of 2023 stop-losses have negative BS at T+1 entry. Potential filter experiment: block SIDEWAYS entries with BS < 0 (requires cascade-risk analysis first).

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

Most recent: `HANDOFF_SESSION_2026_04_27_v40.md` — Step 25: conditional cash reserve floor (floor=0.10). New baselines: 2023 +90.5%, 2024 +25.8%, 2025 +146.6%. JARR cascade fixed. Next: investigate 2023 −12pp.

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
