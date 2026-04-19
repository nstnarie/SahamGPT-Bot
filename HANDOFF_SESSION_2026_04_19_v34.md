# Handoff — 2026-04-19 v34

## What Changed This Session

### Step 12: Position Pyramiding

Added the ability to add to winning positions when they break new resistance levels during the hold period.

**Logic**: When a held position enters trend mode (profit >= +15%) AND a new breakout signal fires for the same ticker, the system adds 50% of the original position size. Maximum 2 adds per position. Stop price ratchets up after each add to protect new capital.

**Evidence that drove this**: 61% of big winners (11/18 unique positions) fire at least one additional breakout signal during the hold. First add typically appears at +20-57% from original entry. Simulation showed ~+27M IDR theoretical upside before implementation.

### Files changed

| File | Change |
|------|--------|
| `config.py` | Added `PyramidConfig` dataclass; added `pyramid` field to `FrameworkConfig` |
| `backtest/portfolio.py` | Added `pyramid_count`, `pyramid_shares`, `pyramid_cost` fields to `Position` |
| `backtest/engine.py` | Signal loop now checks held tickers for pyramid eligibility; executes adds immediately; raises stop after each add |

### Key implementation detail

Pyramid add fires in the signal generation loop (step 3) rather than in the pending entries queue (step 1). This means the add executes the same day the signal fires (at that day's open price), not T+1. This is a simplification but is consistent with how the system detects and acts on intraday breakouts.

---

## Current Baselines (main, 2026-04-19, with pyramiding)

| Year | Return | PF | WR | Trades | Max DD | Pyramid adds | Source |
|------|--------|----|----|--------|--------|-------------|--------|
| 2024 | +14.40% | 2.06 | 50.0% | 46 | -6.58% | ~4 | Local |
| 2025 | +39.53% | 4.07 | 59.6% | 52 | -7.46% | ~19 | Local |
| 2024 CI | pending | — | — | — | — | — | GitHub CI |
| 2025 CI | pending | — | — | — | — | — | GitHub CI |

### Pre-pyramiding baselines (for comparison)

| Year | Return | PF | Max DD |
|------|--------|-----|--------|
| 2024 | +13.05% | 2.05 | -4.96% |
| 2025 | +18.29% | 2.44 | -4.29% |

### Top pyramid-amplified trades (2025)

| Ticker | Total PnL | Pyramid adds | Exit |
|--------|-----------|-------------|------|
| INET Nov | 145M | 2 adds @ +57%, +107% | TREND_EXIT |
| JARR | 59M | 1 add @ +25% | TREND_EXIT |
| INET Jul | 56M | 2 adds @ +24%, +39% | TREND_EXIT |
| RAJA | 51M | 2 adds @ +25%, +42% | TREND_EXIT |
| FILM | 34M | 2 adds @ +23%, +33% | TREND_EXIT |

---

## Exit Analysis Findings (Step 12 research, not implemented)

The exit system was analyzed thoroughly. **No exit changes are recommended:**

| Exit type | WR | Total PnL | Verdict |
|-----------|-----|-----------|---------|
| TREND_EXIT | 86% | +334M | Excellent — don't touch |
| PARTIAL_PROFIT | 100% | +68M | Works correctly |
| REGIME_EXIT | 100% | +103M | Works correctly |
| EMERGENCY_STOP | 0% | -130M | Correctly catches broken entries |
| STOP_LOSS | 25% | -62M | Healthy distribution, not clustered |
| TIME_EXIT | 20% | -20M | Too small to optimize (~10 trades) |

Root cause of losses is entry quality (already addressed by BS/TBA filter), not exit logic.

---

## Locked Parameters (Do NOT Change)

Same as v33 — no new locked parameters this session.

---

## Next Steps

1. **Step 3: 2021-2023 validation** — Run backtests on 2021, 2022, 2023 to check if filters + pyramiding hold in older regimes. These years were previously unprofitable (PF 0.46-0.71). Expected: still unprofitable since BEAR regimes have exposure_mult=0, but pyramiding shouldn't worsen them.

2. **CI backtest** — Trigger `analyze_trade_log.yml` workflow for 2024 and 2025 to get GitHub CI numbers with pyramiding.

3. **Daily signal check** — Pyramiding now applies to live signals in `main_daily.py` as well (engine is shared). Verify the daily signal output handles pyramiding gracefully when a position is already held.

---

## Git State

- Branch: `main`
- Latest commit: `cdcab5b` — "Add position pyramiding (Step 12)"
- Previous: `ed83e86` — "Update docs for Step 11 completion"

No open experiment branches.
