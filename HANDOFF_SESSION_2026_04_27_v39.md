# Handoff Session 2026-04-27 — v39

## What This Session Did

Two permanent code changes implementing a more realistic and more aggressive pyramiding system.
New baselines established. Cascade problem identified and documented. Rebalancing queued as next step.

---

## Permanent Code Changes

### Step 24A: Pyramid T+1 execution (`pyramid_t1_execution = True`)

**Why**: The original same-day execution used today's open price for pyramid adds, but pyramid
signals are only confirmed at today's close. Today's open is already in the past — you cannot
trade it. T+1 (next day's open) is the only real-world executable price.

**What changed**:
- `config.py`: `PyramidConfig.pyramid_t1_execution` default changed from `False` to `True`
- `backtest/engine.py`: added `pending_pyramid_adds` queue (mirrors `pending_entries`).
  When `pyramid_t1_execution=True`, pyramid triggers queue to `pending_pyramid_adds` on day D
  and execute at day D+1 open in a new step 1b (between pending entries and exit checks).
  When `False`, original same-day behaviour is preserved.

**Effect** (vs old same-day baseline):

| Year | Same-day | T+1 | Delta |
|------|----------|-----|-------|
| 2023 | +48.5% | +35.1% | −13.4pp |
| 2024 | +31.1% | +23.5% | −7.6pp |
| 2025 | +127.9% | +102.3% | −25.6pp |

T+1 is lower because by the time the signal fires at close, the stock has already moved.
Next-day open is higher. But T+1 is the correct model — the same-day numbers were not achievable.

---

### Step 24B: max_adds raised from 2 to 5 (`max_adds = 5`)

**Why**: With max_adds=2, mega-winners like BRPT (2025: 4 qualifying add signals), INET (4 signals),
TINS (3 signals), EMTK (5 signals) were capped at 2 adds, leaving significant compounding on the table.

**What changed**:
- `config.py`: `PyramidConfig.max_adds` default changed from `2` to `5`
- CLI override `--max-adds N` added to `main_backtest.py` for experiment flexibility

**Effect** (T+1 max=2 vs T+1 max=5):

| Year | T+1 max=2 | T+1 max=5 | Delta |
|------|-----------|-----------|-------|
| 2023 | +35.1% | +102.7% | **+67.6pp** |
| 2024 | +23.5% | +25.8% | +2.3pp |
| 2025 | +102.3% | +66.4% | **−35.9pp** |

2023 gains strongly — mega-winners (CUAN, PANI, DOID, WIIM) get more capital compounded in.
2025 loses — explained below (JARR cascade).

---

## Critical Finding: The Pyramid Cascade Problem

### What happened to JARR in 2025

JARR was the biggest winner of 2025 (+3,100% trough-to-peak). With max_adds=5, extra pyramid
adds on BRPT, INET, TINS consumed available cash. When JARR's breakout signal fired on Aug 20
(close 1005), the portfolio had no cash to execute the pending entry.

JARR had to wait until Aug 26 (close 1335) when a new signal fired and cash was available.
Entry was Aug 27 at 1345, instead of Aug 21 at 1065 (+27% higher entry price).

With the late entry:
- Add #1 at 1665 raised stop to 1558
- Add #2 at 1850 raised stop to 1730
- Sep 12 pullback to close 1620 → below stop 1730 → TREND_EXIT at 1610

With the early entry (max=2):
- Add #1 at 1335, stop 1251
- Add #2 at 1665, stop 1558
- Same Sep 12 pullback (close 1620) → above stop 1558 → position survives
- Stock rides to 4275 on Oct 17 → TREND_EXIT at 4275, +220% = +547M

**Net JARR difference: +547M (max=2) vs +11M (max=5) = −542M cascade loss.**

This 542M loss accounts for the majority of the 2025 difference (349M total cross-ticker).

### Why 2023 didn't have this problem

In 2023, no single mega-winner was simultaneously:
- Large enough to generate the cascade-blocking cash demand, AND
- Blocked from its initial entry by that cascade.

The winners were more distributed. Extra adds on CUAN/PANI/DOID went into positions that
were already held — they didn't prevent new entries from executing at the right time.

### Why 2024 was neutral

2024 rarely generates 3+ qualifying pyramid signals per position. The extra capacity of
max_adds=5 is largely idle. Neither benefit nor cascade harm materialises.

---

## Step 24 Final Baselines

| Year | Return | PF | WR | Trades | Max DD | Sharpe |
|------|--------|----|----|--------|--------|--------|
| 2023 | +102.70% | 2.73 | 40.3% | 67 | -9.11% | 2.67 |
| 2024 | +25.83% | 2.95 | 52.0% | 75 | -11.45% | 1.08 |
| 2025 | +66.41% | 9.37 | 71.8% | 78 | -16.13% | 1.83 |

Reports: `reports_step24_2023/`, `reports_step24_2024/`, `reports_step24_2025/`

---

## Next Priority: Rebalancing

The cascade problem is well-understood: pyramid adds on existing winners consume cash and
block new high-quality entries. The solution space is **rebalancing** — some mechanism that
reserves capital for new entries.

Ideas to explore (do NOT implement without Arie's explicit go-ahead):

1. **Hard cash reserve** — Always keep N% of portfolio in cash. Pyramid adds cannot draw
   below this floor. New entries are always funded first.

2. **Per-position size cap** — No single position (initial + all pyramid adds) can exceed
   Y% of portfolio value. Naturally limits how much capital flows into any one winner.

3. **Pyramid funding from partial profits only** — Pyramid adds can only be funded from
   cash released by the same position's partial profit sell, not from general cash.
   Keeps pyramiding self-funding without starving the rest of the portfolio.

4. **Trim-to-enter** — When a new high-quality signal fires and there's insufficient cash,
   trim the smallest or most-extended existing position by a fixed fraction to free capital.

Each approach has different trade-offs. Full 3-year backtest with cascade analysis required
before drawing conclusions. Do NOT run any of these without Arie's explicit go-ahead.

---

## CLI Additions (main_backtest.py)

```bash
# Override pyramid settings for experiments
python main_backtest.py --start 2025-01-01 --end 2025-12-31 \
    --max-adds 3 --pyramid-t1 --output reports_exp_xyz
```

`--max-adds N`: override `PyramidConfig.max_adds` (default now 5)
`--pyramid-t1`: force `pyramid_t1_execution=True` (default now True — flag is for testing False)
