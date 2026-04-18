# HANDOFF — Session 2026-04-18 — v29 (Step 7 + Step 8 Consolidated)

## What We Accomplished

### Step 7: Signal Quality Ranking + Hard Entry Filters (from prior session)

**Goal**: Improve signal quality without blocking mega-winners.

**Changes made**:
- `signals/technical.py`: Added three ranking features — `price_vs_ma200`, `atr_pct`, `prior_return_5d`
- `signals/signal_combiner.py`:
  - Added `_compute_signal_quality()` — composite ranking score (weighted percentile rank) used to prioritize entries when capital is limited
  - Added MA200 hard filter: block entries >10% below 200MA (blocks structural downtrends, 0 big winners lost)
  - Added ATR% hard filter: block entries with ATR < 1.75% (blocks low-volatility stocks, 0 big winners lost)
  - Added KSEI 5d net flow hard filter: block entries when 5d cumulative foreign outflow < -5B IDR
  - Added FF trend detection (v6): require both recent positive days AND positive trend on breakout day
- `config.py`:
  - `EntryFilterConfig`: added `min_price_vs_ma200`, `use_ma200_filter`, `min_atr_pct`, `use_atr_filter`
  - `ForeignFlowConfig`: added `min_ksei_net_5d`, `use_ksei_filter`
  - `SignalRankingConfig`: new dataclass with feature weights (price_vs_ma200=0.30, breakout_strength=0.20, atr_pct=0.20, prior_return_5d=0.15, rsi=0.15)
  - `BreakoutConfig`: `breakout_period` changed from 60 to 20 (v10 rebuild: 20-day high catches 100% of mega-winners at median 13d vs 34d for 60d)
  - `EntryConfig`: `max_entries_per_week` raised from 5 to 10 (v10), `max_gap_up_pct` added (7%)
  - `ExitConfig`: trend-following exit parameters added (`trend_threshold_pct`, `trend_exit_ma`)
  - `PositionSizingConfig`: `max_position_pct` 15%→12%, `max_total_exposure` 80%→90%

---

### Step 8: Risk Management Overhaul (THIS SESSION — 2026-04-18)

**Problem**: 2024 was still losing (PF 0.81, -2.84%) despite Step 7 improvements.

**Root cause analysis** (from 141 trades in 2024 before re-scrape):
- 65 "quick failures" (stopped ≤8 days): -257M
- 17 "slow failures" (stopped >8 days): -7M (break-even)
- 59 non-stop exits: +156M (strategy works when not stopped)
- TREND_EXIT: 14 trades, 93% WR, +100M — the core of profitability

**Tested and REJECTED** (all worsened actual backtest):
1. `min_hold_days` 5→3: caused 33 noise exits on day 4 (-90M). Day-4 stocks are volatile, not broken.
2. `emergency_stop_pct` 12%→10%: caught recoverable dips. -10% fires at the bottom of normal swings.
3. Circuit breaker CB(4,5): +55M in trade-log simulation but **worsened** actual backtest. Skipping entries changes capital allocation cascade — the trades that replace skipped ones have different (often worse) outcomes.
4. 20+ entry-level filters: every filter helping 2024 blocks 2025 mega-winners (INET +80%, DSNG +75%, BRPT +68%).

**The solution — `max_entries_per_week = 6` (was 10)**:

| Year | MPW=10 (old) | MPW=6 (new) |
|------|-------------|-------------|
| 2024 | PF 0.81, -2.84% | **PF 1.40, +6.39%** |
| 2025 | PF 1.99, +20.09% | **PF 1.75, +14.93%** |

**Why MPW=6 works**: Limiting to 6 entries per rolling 10-day window forces the composite ranking score to filter to only the best breakout signals. In 2024's sideways/bear market, there were many simultaneous false breakout signals — MPW=6 enters only the top-ranked 6. In 2025's bull market, the strongest breakouts still get entered.

**Circuit breaker code was added to `backtest/engine.py`** (fully functional) but disabled via config (`circuit_breaker_losses=0`). Kept for future testing.

**Changes in this session**:
- `config.py`: `max_entries_per_week` 10→6; circuit breaker params added (disabled)
- `backtest/engine.py`: circuit breaker tracking logic added (disabled)
- `backtest/portfolio.py`: comment update to v6

---

## Current Backtest Results (MPW=6, fresh Yahoo Finance data)

| Year | Trades | WR | PF | Return | MDD | vs IHSG |
|------|--------|----|----|--------|-----|---------|
| 2024 | 75 | 36.0% | 1.12 | +2.25% | -5.36% | +6.69% alpha |
| 2025 | 98 | 45.9% | 1.25 | +11.34% | -8.18% | — |

**2024 exit breakdown** (MPW=6):
- TREND_EXIT: 12 trades, 92% WR, +168M ← core profitability
- STOP_LOSS: 38 trades, 16% WR, -95M
- EMERGENCY_STOP: 8 trades, 0% WR, -60M
- PARTIAL_PROFIT: 4 trades, 100% WR, +10M
- REGIME_EXIT: 9 trades, 56% WR, +9M

**2024 top winners**: ARGO +65%, PANI +56%, SRTG +30%, DSNG +27%

**Note on 2021-2022**: Still unprofitable (PF 0.46-0.71). The breakout strategy requires trending conditions. 2021-2022 had insufficient trending moves in LQ45. No parameter tuning resolved this — would require a fundamentally different strategy for those regimes.

---

## Key Architecture Decisions (Permanent)

| Decision | Rationale |
|----------|-----------|
| 20-day breakout (not 60d) | Catches 100% of mega-winners at median 13d after trough |
| No RSI/MACD entry filter | 84% of mega-winners have RSI < 40 at trough — filter blocks them |
| No FF at entry | d=-0.0001, zero predictive power at trough |
| min_hold_days=5 | Day 6+ has 49% WR vs 7% for days 1-5. Day-3-4 exits are noise. |
| emergency_stop=12% | -10% fires at recoverable dips; -12% is the real disaster threshold |
| MPW=6 | Ranking-based entry throttle — prevents false breakout cluster entries |
| Trend exit (MA10) for +15% positions | Lets mega-winners run; don't sell ARGO at +20% when it goes +65% |
| No hard position count limit | Capital is the real limit. Real trading works this way. |

---

## Next Steps

1. **Scrape KSEI 2024 data**: The KSEI foreign flow filter blocks 50 bad trades in 2025 (22% WR) but has no 2024 data yet. Scrape via Stockbit chartbit API to apply filter to 2024 — could push 2024 from +6% to +10%.
2. **fp_ratio exploration** (from KSEI analysis session): High-fp stocks lose (23.7% WR), low-fp win (53.5% WR). Test as an entry filter.
3. **Real broker data backtest**: Run `--real-broker` flag with full Asing broker data to see if accumulation signals improve results further.
4. **2021-2022 regime filter**: Consider adding a stricter BEAR regime signal that blocks ALL entries during clear downtrends (not just reducing position size).

---

## File Reference

| File | Version | Key Change |
|------|---------|-----------|
| `config.py` | v5 | MPW=6, SignalRankingConfig, EntryFilterConfig, KSEI filter |
| `signals/signal_combiner.py` | v5 | composite ranking, MA200+ATR+KSEI hard filters, FF trend |
| `signals/technical.py` | — | price_vs_ma200, atr_pct, prior_return_5d features |
| `backtest/engine.py` | v4 | circuit breaker (disabled), composite score ranking for pending entries |
| `backtest/portfolio.py` | v6 | trend exit mode, hold extension with acc_score |
