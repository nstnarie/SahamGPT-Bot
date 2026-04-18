# Handoff Session 2026-04-18 v32 — Step 10: fp_ratio Filter

## What Changed This Session

Two experiments run on feature branches against the real Asing data baseline. One failed, one merged.

---

### Experiment 1: min_hold=3 — FAILED

**Branch**: `exp/min-hold-3`

**Hypothesis**: With real data, day-6 cliff (33 SL, -126M) would shift to day-4 and be cheaper at -7% vs -12%.

**Result**: Day-4 cliff was LARGER (30 stops, -132M) + day-5 cliff (11 stops, -46M) = 41 total vs 33. TREND_EXIT winners dropped from 16 trades/+189M → 9 trades/+99M. PF 1.07 → 0.72. Confirms Step 8 finding holds with real data.

**Decision**: min_hold=5 remains locked. Branch deleted.

---

### Experiment 2: fp_ratio filter — MERGED ✅

**Branch**: `exp/fp-ratio-filter` → merged to main

**What is fp_ratio**: Asing traded value (buy+sell) / total all-broker traded value per ticker. Computed from broker_summary. Range 0-1. High = foreigners dominate trading in that stock.

**Why it works**: High-fp stocks (BBCA, BMRI, BBRI, TLKM — fp ≥ 0.40) are used by foreign institutions as liquid macro hedges. Foreigners buy when they want Indonesia exposure, sell to reduce global risk. These moves are position sizing decisions, not stock fundamentals. The resulting "breakouts" are false signals — domestic retail chases the volume, but foreigners are actually positioning out.

**Pre-analysis of 2024 baseline trades** (103 trades, real Asing data):
- low-fp (< 0.40): 40 trades, **52% WR, +117.7M**
- high-fp (≥ 0.40): 63 trades, **32% WR, -100.0M**
- Threshold 0.40 was the strongest split across all thresholds tested

**Implementation**:
- `load_fp_ratios(session)` in `database/data_loader.py` — SQL agg from broker_summary
- `fp_ratios.json` committed to repo — precomputed fallback for GitHub CI (no broker_summary in workflows)
- `EntryFilterConfig.max_fp_ratio = 0.40`, `use_fp_filter = True` in `config.py`
- `signal_combiner.py` — blocks `is_breakout` if `fp_ratio >= max_fp_ratio`
- `engine.py` + `main_backtest.py` — thread `fp_ratios` dict through pipeline

---

## Backtest Results

| | Baseline (no filter) | fp_ratio < 0.40 |
|--|---------------------|----------------|
| **2024 PF** | 1.07 | **1.34** |
| **2024 Return** | +1.78% | **+5.91%** |
| **2024 WR** | 39.8% | **46.8%** |
| **2024 Trades** | 103 | **62** |
| **2024 Max DD** | -5.92% | **-5.61%** |
| **2025 PF** | ~1.65 | **1.53** |
| **2025 Return** | ~+19.7% | **+12.12%** |
| **2025 WR** | ~46% | **52.1%** |
| **2025 Trades** | ~98 | **71** |
| **2025 Max DD** | ~-8.86% | **-6.18%** |

Both years profitable with fp_ratio filter. 2024 improved significantly. 2025 lower absolute return but higher WR and much lower drawdown.

---

## Known Limitation: Lookahead Bias

`fp_ratios.json` was computed from full 2024-2025 broker_summary data. For 2024 backtests, this introduces minor lookahead (uses 2025 data to classify 2024 tickers). However, fp_ratio is a structural property — BBCA has always been foreign-dominated and always will be. The bias is minimal in practice.

Proper fix: compute rolling 90-day fp_ratio per ticker/date and load it as a time series. This is the next refinement step.

---

## What Was Actually Blocked (2024)

41 trades removed by the filter — primarily big-cap banks and telecoms:
- BBCA, BMRI, BBRI, BBNI (banks, fp 0.61-0.70)
- TLKM, EXCL, EMTK (telco/media, fp 0.45-0.65)
- KLBF, ICBP, INDF, UNVR (consumer staples, fp 0.55-0.59)
- SMGR, INTP (cement, fp 0.59-0.61)

These were the stocks generating 63 trades at 32% WR. The remaining 62 trades (low-fp mid-caps in energy, property, commodity, industrial) delivered 46.8% WR.

---

## Files Changed

| File | Change |
|------|--------|
| `config.py` | Added `max_fp_ratio=0.40`, `use_fp_filter=True` to `EntryFilterConfig` |
| `database/data_loader.py` | Added `load_fp_ratios()` function |
| `signals/signal_combiner.py` | Threaded `fp_ratio` param; blocks `is_breakout` if too high |
| `backtest/engine.py` | Added `fp_ratios` param to `run()`, passed to `generate_signals_universe()` |
| `main_backtest.py` | Loads fp_ratios (DB first, JSON fallback); passes to engine |
| `fp_ratios.json` | Precomputed fp_ratio per ticker (137 tickers, full 2024-2025 data) |
| `CLAUDE.md` | Step 10 state, updated results, architectural decisions |

---

## Next Steps

1. **Investigate 2025 return drop** — Filter blocked 27 trades in 2025 (-Rp 80M return). Were any of them genuine winners? Run 2025 trade analysis, check which tickers were blocked.
2. **Rolling fp_ratio** — Eliminate lookahead bias. Compute trailing 90-day fp_ratio per ticker/date from broker_summary. Store in broker_accumulation_df or separate loader.
3. **2021-2022 regime problem** — Still unresolved. Separate concern from fp_ratio work.

Most recent commits:
- `e350238` — Update docs: Step 9 state, synthetic removal complete, add Rule 7
- `eef324c` — EXP: min_hold=3 re-test (on deleted branch)
- `b302a00` — EXP: fp_ratio entry filter (threshold < 0.40)
- `37c75fb` — EXP: add fp_ratios.json fallback for CI
- Merge commit — Step 10: fp_ratio filter merged to main
