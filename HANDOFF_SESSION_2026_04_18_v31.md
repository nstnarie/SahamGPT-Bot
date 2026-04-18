# Handoff Session 2026-04-18 v31 — Synthetic FF Fully Purged

## What Changed This Session

Two problems fixed on top of v30:

### Bug Found: Daily Pipeline Was Overwriting Real Data

`main_daily.py` was calling `flow_scraper.estimate_and_store()` on every run. `upsert_foreign_flow()` **updates** existing rows (not INSERT OR IGNORE) — so every daily signal run was silently replacing real Stockbit Asing data with synthetic price-derived estimates. This was discovered by reading the actual `upsert_foreign_flow()` implementation in `database/data_loader.py:62`.

**Fix**: Removed `FlowScraper` import and the entire estimate-and-store loop from `main_daily.py` (lines 100-106 deleted).

### Architectural Clarification

When `foreign_flow` is empty for a ticker (no real data), `signal_combiner.py` sets neutral defaults — NOT synthetic values:
- `is_foreign_driven = False` → stock treated as domestic
- `ff_consecutive_sell = 0` → no FF-based exits
- `ksei_net_5d = NaN` → KSEI filter does not block (NaN fails the `notna()` check)

This is correct behaviour. No fake values are injected.

---

## Files Changed

| File | Change |
|------|--------|
| `main_daily.py` | Removed `FlowScraper` import + `estimate_and_store()` loop |
| `main_backtest.py` | Removed unused `FlowScraper` import (FundamentalScraper kept) |
| `CLAUDE.md` | Step 9 state, real results, no-synthetic rule (Rule 7), updated examples |

---

## Complete Synthetic Removal Status

| Location | Status |
|----------|--------|
| `main_backtest.py` — scrape path | Removed (v30) |
| `main_daily.py` — daily pipeline | Removed (v31) ← this session |
| `main_backtest.py` — FlowScraper import | Removed (v31) |
| `main_daily.py` — FlowScraper import | Removed (v31) |
| `signals/signal_combiner.py` — empty ff_df defaults | Neutral (no-data → skip FF, not fake FF) ✅ |
| `database/data_loader.py` — upsert_foreign_flow | Still used for real data inserts from broker_summary aggregation ✅ |

`estimate_and_store()` and `estimate_foreign_flow_from_prices()` still exist in `flow_scraper.py` as dead code. They are not called from anywhere. They can be deleted in a future cleanup session.

---

## Current Backtest Results (Real Asing Data, MPW=6)

| Year | PF | Return | WR | Trades |
|------|-----|--------|----|--------|
| 2024 | 0.53 | -13.7% | 34% | 101 |
| 2025 | 1.65 | +19.7% | 46% | 98 |

**2024 is the active research problem.** The MPW=6 fix made 2024 profitable with synthetic data (PF 1.40) because synthetic FF was accidentally filtering out more bad trades. With real Asing flows, those trades go through and 2024 loses.

---

## Data Flow (Current State)

```
Stockbit API
    │
    ▼
broker_summary (raw, 2.6M rows, 137 tickers, 2024-2025)
    │
    ▼  [aggregated by update_split_files.yml or manual SQL]
foreign_flow (net Asing per ticker/day, 72k rows)
    │
    ├──▶ idx_broker_part_a.db (4.8MB lean file, committed to repo)
    │        └── restored by run_backtest.yml / analyze_trade_log.yml
    │
    └──▶ main_backtest.py → load_foreign_flow_df() → backtest engine
         main_daily.py   → load_foreign_flow_df() → signal combiner
```

No synthetic data enters this flow anywhere.

---

## Next Steps

1. **Run `Analyze Trade Log` on GitHub** for 2024 with real data (use the workflow, it now restores real foreign_flow from split file)
2. **Download `trade_analysis.md` artifact** and read the exit breakdown
3. **Design feature branch experiment** based on what the real 2024 data shows
4. **Consider fp_ratio filter** — prior analysis: high-fp stocks lose 23.7% WR, low-fp win 53.5% WR

Most recent commits:
- `fc85d95` — Step 9: replace synthetic FF, overhaul split file architecture
- `6732835` — CLAUDE.md + v30 handoff
- `42db5bd` — Remove synthetic FF from daily pipeline (this session's main fix)
