# Handoff Session 2026-04-27 — v40

## What This Session Did

Designed, implemented, and validated a conditional cash reserve floor (Step 25) to fix the
pyramid cascade problem identified in Step 24. JARR 2025 is now rescued. New baselines
established. One open question remains for the next session.

---

## The Problem Being Solved (Recap)

With max_adds=5, pyramid adds on existing winners (BRPT, INET, TINS in 2025) consumed all
available cash. When JARR's breakout signal fired Aug 20, 2025, the portfolio had no cash.
JARR entered 6 days late at 1345 instead of 1065, then stopped out at 1610 instead of
riding to 4275 = −542M cascade loss.

---

## What Was Tried and Failed (This Session)

### Attempt 1: Unconditional cash reserve floor

Apply floor=10% always. Pyramid adds blocked whenever `cash - add_cost < 10% of portfolio`.

Result: 2025 +153% (JARR rescued), but 2023 −44pp (102.7% → 59.1%).
Root cause: floor throttles ALL adds including CUAN/PANI/DOID compounding that drove 2023.
Too blunt — rejected.

### Attempt 2: Target-based add sizing

Change add size from `pos.shares × 0.50` (compounding) to `target_size × 0.50` (flat 6%).
Intended to let undersized entries "catch up" via normal pyramid adds.

Result: 2023 collapsed to +23%. Root cause: CUAN with 5 adds under old system builds a
position 7.6× the initial (exponentially compounding). Flat 6% per add caps at 3.5× initial.
Reverted immediately.

### Attempt 3: min_entry_fraction = 0.05

Skip entries smaller than 5% of portfolio. Intended to avoid trivial stub positions.

Result: 2023 +30% (vs +103% baseline). Root cause: as portfolio equity grows during the
year, the 5% minimum grows in absolute terms. When cash is 90M and equity is 2B,
5% = 100M → entry blocked even though 90M > 0 (valid entry). Disabled (set to 0.0).

---

## Step 25: Conditional Cash Reserve Floor ✅

### Mechanism

A one-day lookahead flag (`new_entries_queued`) tracks whether new entry signals were
queued at the end of each day. The next day's pyramid add execution (step 1b) checks this
flag:

- `new_entries_queued = False`: no new entries competing → adds run freely, no floor
- `new_entries_queued = True`: entries are pending → adds blocked if `cash - add_cost < floor`

### Code Changes

**`config.py`**:
- `PyramidConfig.cash_reserve_floor = 0.10` — 10% of portfolio reserved when entries pending
- `PositionSizingConfig.min_entry_fraction = 0.0` — disabled

**`backtest/engine.py`**:
- `new_entries_queued: bool = False` — initialized before the main loop
- Step 1b: `floor_amount = equity × floor if new_entries_queued else 0.0` — conditional floor
- Step 3b (after signal generation): `new_entries_queued = len(pending_entries) > 0`

**`main_backtest.py`**:
- `--cash-floor FLOAT` — override `cash_reserve_floor`
- `--min-entry FLOAT` — override `min_entry_fraction`

**`.github/workflows/run_backtest.yml`**:
- `cash_floor` and `min_entry` workflow inputs added

### Floor Sweep Results (conditional floor, 5 values tested)

| Floor | 2023 | 2024 | 2025 |
|-------|------|------|------|
| 0.00 (Step 24 baseline) | +102.7% | +25.8% | +66.4% |
| 0.03 | +93.1% | +25.8% | +65.1% |
| 0.05 | +91.4% | +25.8% | +61.2% |
| **0.10 ← chosen** | **+90.5%** | **+25.8%** | **+146.6%** |
| 0.15 | +23.7% | +25.8% | +45.8% |

floor=0.10 is the non-linear winner: 2025 jumps at floor=0.10 (JARR rescued), while
floor=0.03/0.05 don't preserve enough cash for JARR's entry. floor=0.15 over-constrains.
2024 is completely invariant to all floor values — pyramid adds never compete with new
entries in 2024.

### JARR Verification (floor=0.10 vs Step 24)

| | Step 24 (cascade) | Step 25 (fixed) |
|-|-------------------|-----------------|
| Entry date | Aug 27 | Aug 21 (correct) |
| Entry price | 1345 | 1065 |
| Exit reason | TREND_EXIT Sep 12 | TREND_EXIT Oct 17 |
| Exit price | 1610 | 4275 |
| Net PnL | +11M | +877M |

---

## Step 25 Final Baselines

| Year | Return | PF | WR | Trades | Max DD | Sharpe |
|------|--------|----|----|--------|--------|--------|
| 2023 | +90.49% | 2.20 | 40.9% | 66 | -10.35% | 2.51 |
| 2024 | +25.83% | 2.95 | 52.0% | 75 | -11.45% | 1.08 |
| 2025 | +146.58% | 12.21 | 68.5% | 73 | -37.45% | 2.17 |

Reports: `reports_step25_2023/`, `reports_step25_2024/`, `reports_step25_2025/`

**2025 Max DD note**: −37.45% is driven by JARR's large position creating equity swings
during the Aug–Oct hold period. This is unrealized-gain drawdown (position went from
+100% to +60% mid-hold before recovering), not loss drawdown.

---

## Next Session Priority: 2024 Trade Deep Dive

Arie wants a detailed analysis of 2024 trades. 2024 is uniquely stable across all
pyramid/cascade experiments — +25.8% regardless of floor value, max_adds, or cascade
changes. This suggests 2024 returns are driven entirely by entry/exit quality, not
compounding mechanics. Deep dive to understand: win/loss patterns, holding periods,
which signals are working, and what 2024-specific improvements might look like.

Do NOT start without Arie's explicit go-ahead.

---

## Backlog: Why does 2023 still lose −12pp with the conditional floor?

Expected: CUAN/PANI/DOID adds should run freely on days with no new entries competing.
Actual: 2023 return drops from +102.7% to +90.5% even with conditional logic.

Two possible explanations:
1. **Genuine competition**: new entry signals DO co-occur with CUAN/PANI pyramid add days
   in 2023 — the floor correctly blocked adds that competed with real new entry signals.
   If so, the −12pp is unavoidable and acceptable given the +80pp gain in 2025.
2. **Over-triggering**: `new_entries_queued` fires even when the pending entry was then
   blocked by filters (throttle, sector, gap filter etc.) — the floor applies even though
   the entry never actually executed. A tighter flag (only set when entries actually
   executed, not just queued) might reduce false positives.

Analysis required before deciding whether to refine the mechanism or accept the trade-off.
Do NOT start without Arie's explicit go-ahead.

---

## Key Insight: Why 2024 Never Moves

2024 is completely invariant to all pyramid/floor/cascade changes tested across Steps 21–25.
Reason: 2024 rarely generates 3+ qualifying pyramid add signals per position. max_adds=5
capacity sits mostly idle. No position consumes enough cash via adds to crowd out new entries.
2024 returns are driven by entry/exit quality, not pyramid compounding or cascade effects.
**Use 2024 as a sanity check**: any pyramid-related change that moves 2024 significantly
is a warning sign that something unexpected is happening.
